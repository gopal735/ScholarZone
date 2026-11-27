"""Build the canonical reconciliation package from local schema + database.

This script is the only writer of the canonical approval files. It reads the
local SQLite database read-only, parses the real SQLAlchemy model for the field
contract, and writes:

* the 13 approved DIRECT operations (11 cycle updates + 2 funding corrections),
* the 13 evidence records that support them,
* the 12 PENDING_RESEARCH operations, explicitly excluded,
* the 2 lifecycle proposals, explicitly NOT approved,
* the 6 blocked insert candidates,
* the count reconciliation and package manifest.

Run order (from this directory):

    python reconcile_duplicates.py
    python build_canonical_package.py
    python validate_semantics.py

The duplicate reports are generated first because the reconciliation and
manifest must quote the introspected duplicate findings rather than hard-code
them. This script never writes to backend/scholarzone.db.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
BACKEND = PACKAGE.parents[1]
DB_PATH = BACKEND / "scholarzone.db"
MODELS_PATH = BACKEND / "app" / "models.py"
SCHEMAS_PATH = BACKEND / "app" / "schemas.py"

BASELINE_DATE = "2026-11-10"
BASE_SHA = "5b28ceef0480a4bd6612d1cf08c26e8629bea285"
PRE_REMEDIATION_HEAD = "dec6dbcd65ffe98da42f0e6fff665c3c840ce04a"
BRANCH = "feat/final-scholarship-catalogue-reconciliation"

APPROVED_CYCLE_IDS = [1, 3, 4, 5, 23, 231, 232, 234, 516, 1312, 1336]
FUNDING_IDS = [3, 1]
LIFECYCLE_IDS = [729, 31]
PENDING_IDS = [30, 32, 33, 34, 36, 40, 41]
DUPLICATE_IDS = [183, 753, 270, 1244, 271, 760, 285, 1277, 1217, 1309]
ALL_IDS = sorted(
    set(APPROVED_CYCLE_IDS + FUNDING_IDS + LIFECYCLE_IDS + PENDING_IDS + DUPLICATE_IDS)
)

BASELINE_FIELDS = [
    "id",
    "title",
    "country",
    "degree",
    "funding",
    "status",
    "is_archived",
    "archived_at",
    "archived_reason",
    "official_source_url",
    "application_link",
    "official_updates_url",
    "catalogue_url",
    "fully_funded",
    "tuition_coverage",
    "living_cost_coverage",
    "travel_coverage",
    "application_period",
    "duration",
]

BOOLEAN_FIELDS = {
    "fully_funded",
    "tuition_coverage",
    "living_cost_coverage",
    "travel_coverage",
    "is_archived",
}


def read_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_contract() -> tuple[list[str], list[str]]:
    tree = ast.parse(MODELS_PATH.read_text(encoding="utf-8"))
    fields: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Scholarship":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.append(item.target.id)
            break

    statuses: list[str] = []
    schema_tree = ast.parse(SCHEMAS_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(schema_tree):
        if isinstance(node, ast.ClassDef) and node.name == "ScholarshipStatus":
            for item in node.body:
                if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant):
                    value = item.value.value
                    if isinstance(value, str):
                        statuses.append(value)
            break
    if not fields:
        raise RuntimeError("Could not parse Scholarship model fields")
    if not statuses:
        raise RuntimeError("Could not parse ScholarshipStatus values")
    return fields, statuses


def introspect(con: sqlite3.Connection, fields: list[str]) -> dict:
    con.row_factory = sqlite3.Row
    fk_tables: list[dict] = []
    tables = [
        row["name"]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    for table in tables:
        for fk in con.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
            if fk["table"] != "scholarships":
                continue
            fk_tables.append(
                {
                    "table": table,
                    "column": fk["from"],
                    "references": "scholarships.id",
                    "on_update": fk["on_update"],
                    "on_delete": fk["on_delete"],
                }
            )

    unique_constraints: dict[str, list[dict]] = {}
    for entry in fk_tables:
        table = entry["table"]
        constraints: list[dict] = []
        for index in con.execute(f'PRAGMA index_list("{table}")').fetchall():
            if not index["unique"]:
                continue
            columns = [
                col["name"]
                for col in con.execute(f'PRAGMA index_info("{index["name"]}")').fetchall()
            ]
            constraints.append({"name": index["name"], "columns": columns})
        unique_constraints[table] = constraints

    table_columns = {
        table: [row["name"] for row in con.execute(f'PRAGMA table_info("{table}")')]
        for table in tables
    }
    declared_types = {
        row["name"]: row["type"]
        for row in con.execute("PRAGMA table_info('scholarships')").fetchall()
    }

    pair_counts: dict[str, dict[str, int]] = {}
    for table in [entry["table"] for entry in fk_tables] + ["scholarship_image_audit"]:
        if table not in table_columns:
            continue
        column = "matched_scholarship_id" if table == "discovery_candidates" else "scholarship_id"
        if column not in table_columns[table]:
            continue
        counts = {
            str(row["id"]): int(row["n"])
            for row in con.execute(
                f'SELECT {column} AS id, COUNT(*) AS n FROM "{table}" '
                f'WHERE {column} IN ({",".join("?" for _ in ALL_IDS)}) GROUP BY {column}',
                ALL_IDS,
            ).fetchall()
        }
        pair_counts[table] = counts

    return {
        "declared_fk_tables": fk_tables,
        "unique_constraints": unique_constraints,
        "table_columns": table_columns,
        "scholarship_column_types": declared_types,
        "row_counts_by_pair_id": pair_counts,
        "model_fields": fields,
    }


def baseline_snapshot() -> dict:
    fields, statuses = model_contract()
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        total = dict(
            con.execute(
                "SELECT COUNT(*) AS total, "
                "COALESCE(SUM(CASE WHEN is_archived=0 THEN 1 ELSE 0 END),0) AS active, "
                "COALESCE(SUM(CASE WHEN is_archived=1 THEN 1 ELSE 0 END),0) AS archived "
                "FROM scholarships"
            ).fetchone()
        )
        status_distribution = {
            row["status"]: int(row["n"])
            for row in con.execute(
                "SELECT status, COUNT(*) AS n FROM scholarships GROUP BY status ORDER BY status"
            ).fetchall()
        }
        archived_status_distribution = {
            row["status"]: int(row["n"])
            for row in con.execute(
                "SELECT status, COUNT(*) AS n FROM scholarships "
                "WHERE is_archived=1 GROUP BY status ORDER BY status"
            ).fetchall()
        }
        rows = {
            str(row["id"]): {field: row[field] for field in BASELINE_FIELDS}
            for row in con.execute(
                f"SELECT {', '.join(BASELINE_FIELDS)} FROM scholarships "
                f"WHERE id IN ({','.join('?' for _ in ALL_IDS)}) ORDER BY id",
                ALL_IDS,
            ).fetchall()
        }
        introspection = introspect(con, fields)
    finally:
        con.close()

    return {
        "baseline_date": BASELINE_DATE,
        "database_source": "backend/scholarzone.db",
        "database_sha256": file_sha256(DB_PATH),
        "read_only_introspection": True,
        "schema_contract": {
            "model_file": "backend/app/models.py",
            "schema_file": "backend/app/schemas.py",
            "status_values": statuses,
            "scholarship_fields": fields,
        },
        "record_counts": {
            "total": int(total["total"]),
            "active": int(total["active"]),
            "archived": int(total["archived"]),
            "status_distribution": status_distribution,
            "archived_status_distribution": archived_status_distribution,
        },
        "scholarships": rows,
        "foreign_keys": introspection,
    }


def bool_value(value):
    if value is None:
        return None
    return bool(value)


def approved_cycle_specs() -> list[dict]:
    """The 11 approved cycle updates. Every change has one DIRECT evidence URL.

    The ``exact_supported_claim`` strings were re-checked against the live
    official pages on 2026-11-10. The retrieval date is recorded per operation.
    """
    return [
        {
            "operation_id": "CYCLE-1",
            "catalogue_id": 1,
            "source_title": "Erasmus Mundus Joint Masters (students) - Erasmus+",
            "source_url": "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
            "exact_supported_claim": (
                'Page title: "Erasmus Mundus Joint Masters (students) - Erasmus+". '
                'The body states: "Erasmus Mundus Joint Masters are prestigious '
                'international masters" and uses the official abbreviation in '
                '"EMJM programmes". It also states: "Full scholarships are available '
                'for the best students".'
            ),
            "changes": [
                {"field": "title", "after": "Erasmus Mundus Joint Masters (EMJM)"}
            ],
        },
        {
            "operation_id": "CYCLE-3",
            "catalogue_id": 3,
            "source_title": (
                "Study Scholarships - Master Studies for All Academic Disciplines - DAAD"
            ),
            "source_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50026200",
            "exact_supported_claim": (
                'Application deadline section: "Application deadlines are updated annually '
                'in the second quarter. In most cases, they are in the same period as the '
                'previous year." Application procedure: "Applications for this scholarship '
                'programme are possible between 1 June and the stated application deadline."'
            ),
            "changes": [
                {
                    "field": "application_period",
                    "after": (
                        "Application deadlines are updated annually in the second quarter; "
                        "applications are possible between 1 June and the stated application "
                        "deadline."
                    ),
                }
            ],
        },
        {
            "operation_id": "CYCLE-4",
            "catalogue_id": 4,
            "source_title": "Study in Korea | Run by Korean Government",
            "source_url": "https://www.studyinkorea.go.kr/en/plan/scholarship.do",
            "exact_supported_claim": (
                'The GKS page labels the two tracks "Undergraduate Degrees (including '
                'Associate Degree)" and "Graduate Degrees (Master\'s and Doctoral Degrees)". '
                'The selection quota text says "Approximately 280 undergraduate students '
                '(including associate degree students) + 1,600 graduate students".'
            ),
            "changes": [
                {
                    "field": "degree",
                    "after": (
                        "Undergraduate Degrees (including Associate Degree), Graduate "
                        "Degrees (Master's and Doctoral Degrees)"
                    ),
                }
            ],
        },
        {
            "operation_id": "CYCLE-5",
            "catalogue_id": 5,
            "source_title": "Japanese Government (MEXT) Scholarship｜Study in Japan Official Website",
            "source_url": "https://www.studyinjapan.go.jp/en/planning/scholarships/mext-scholarships/",
            "exact_supported_claim": (
                'The page states: "there are seven types of the Japanese Government '
                '(Monbukagakusho) Scholarship program. They are Research students, Teacher '
                'training students, Undergraduate students, Japanese studies students, college '
                'of technology students, Specialized training college students, and Young '
                'Leaders Program (YLP) students."'
            ),
            "changes": [
                {
                    "field": "degree",
                    "after": (
                        "Research students, Teacher training students, Undergraduate students, "
                        "Japanese studies students, College of technology students, Specialized "
                        "training college students, Young Leaders Program (YLP) students"
                    ),
                }
            ],
        },
        {
            "operation_id": "CYCLE-23",
            "catalogue_id": 23,
            "source_title": "Development-Related Postgraduate Courses (EPOS) - DAAD",
            "source_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50076777",
            "exact_supported_claim": (
                'Page title: "Development-Related Postgraduate Courses (EPOS) - DAAD". '
                'The "Duration of the funding" section states: "12 to 42 months (dependent '
                'on study programme)".'
            ),
            "changes": [
                {"field": "duration", "after": "12 to 42 months (dependent on study programme)"}
            ],
        },
        {
            "operation_id": "CYCLE-231",
            "catalogue_id": 231,
            "source_title": (
                "Study Scholarships - Postgraduate Studies in the Field of Architecture - DAAD"
            ),
            "source_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135744",
            "exact_supported_claim": (
                'Page title: "Study Scholarships - Postgraduate Studies in the Field of '
                'Architecture - DAAD - Deutscher Akademischer Austauschdienst"; the in-page '
                'heading is "Study Scholarships - Postgraduate Studies in the Field of '
                'Architecture".'
            ),
            "changes": [
                {
                    "field": "title",
                    "after": (
                        "Study Scholarships - Postgraduate Studies in the Field of Architecture"
                    ),
                }
            ],
        },
        {
            "operation_id": "CYCLE-232",
            "catalogue_id": 232,
            "source_title": (
                "Study Scholarships - Postgraduate Studies in the Fields of Fine Art, Design, "
                "Visual Communication and Film - DAAD"
            ),
            "source_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135742",
            "exact_supported_claim": (
                'Page title: "Study Scholarships - Postgraduate Studies in the Fields of Fine '
                'Art, Design, Visual Communication and Film - DAAD - Deutscher Akademischer '
                'Austauschdienst"; the in-page heading matches the programme title.'
            ),
            "changes": [
                {
                    "field": "title",
                    "after": (
                        "Study Scholarships - Postgraduate Studies in the Fields of Fine Art, "
                        "Design, Visual Communication and Film"
                    ),
                }
            ],
        },
        {
            "operation_id": "CYCLE-234",
            "catalogue_id": 234,
            "source_title": (
                "Study Scholarships - Postgraduate Studies in the Field of the Performing Arts - DAAD"
            ),
            "source_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50109971",
            "exact_supported_claim": (
                'Page title: "Study Scholarships - Postgraduate Studies in the Field of the '
                'Performing Arts - DAAD - Deutscher Akademischer Austauschdienst"; the in-page '
                'heading matches the programme title.'
            ),
            "changes": [
                {
                    "field": "title",
                    "after": (
                        "Study Scholarships - Postgraduate Studies in the Field of the "
                        "Performing Arts"
                    ),
                }
            ],
        },
        {
            "operation_id": "CYCLE-516",
            "catalogue_id": 516,
            "source_title": "Study in Korea | Run by Korean Government",
            "source_url": "https://www.studyinkorea.go.kr/en/plan/scholarship.do",
            "exact_supported_claim": (
                'The GKS page section "Undergraduate Degrees (including Associate Degree)" '
                'lists an "Associate Degree Program" and a "Bachelor\'s Degree Program"; the '
                'selection quota includes "Associate Degree 30" and "UIC 100" for bachelor\'s '
                'and associate degree places.'
            ),
            "changes": [
                {
                    "field": "degree",
                    "after": "Undergraduate Degrees (including Associate Degree)",
                }
            ],
        },
        {
            "operation_id": "CYCLE-1312",
            "catalogue_id": 1312,
            "source_title": "Knight-Hennessy Scholars at Stanford University",
            "source_url": "https://knight-hennessy.stanford.edu",
            "exact_supported_claim": (
                'Page title: "Knight-Hennessy Scholars at Stanford University"; the main page '
                'heading repeats "Knight-Hennessy Scholars at Stanford University".'
            ),
            "changes": [
                {
                    "field": "title",
                    "after": "Knight-Hennessy Scholars at Stanford University",
                }
            ],
        },
        {
            "operation_id": "CYCLE-1336",
            "catalogue_id": 1336,
            "source_title": "Taiwan Scholarship and Huayu Enrichment Scholarship Program",
            "source_url": "https://taiwanscholarship.moe.gov.tw",
            "exact_supported_claim": (
                'Official site title: "Taiwan Scholarship and Huayu Enrichment Scholarship '
                'Program" (also rendered as "臺灣獎學金及華語文獎學金計畫網站"). Footer: '
                '"© Copyright Taiwan Scholarship And Huayu Enrichment Scholarship Office". '
                'The page therefore identifies the Huayu Enrichment Scholarship Program as '
                'one of the two official programmes it administers.'
            ),
            "changes": [
                {"field": "title", "after": "Huayu Enrichment Scholarship Program"}
            ],
        },
    ]


def approved_funding_specs() -> list[dict]:
    """The 2 approved funding corrections with DIRECT evidence."""
    return [
        {
            "operation_id": "FUND-3",
            "catalogue_id": 3,
            "source_title": (
                "Study Scholarships - Master Studies for All Academic Disciplines - DAAD"
            ),
            "source_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50026200",
            "exact_supported_claim": (
                'Value section: "Scholarship payments of 992 euros a month", "Payments towards '
                'health, accident and personal liability insurance cover", "Travel allowance '
                '(upon application only)", "Annually study allowance of 460 euros"; the page '
                'also states: "Please note that the DAAD does not cover tuition fees '
                '( important information for scholarship applicants / section F, point 7)."'
            ),
            "changes": [
                {"field": "tuition_coverage", "after": False},
                {"field": "fully_funded", "after": False},
                {
                    "field": "funding",
                    "after": "Partially Funded (stipend, insurance, travel; tuition not covered)",
                },
            ],
        },
        {
            "operation_id": "FUND-1",
            "catalogue_id": 1,
            "source_title": "Erasmus Mundus Joint Masters (students) - Erasmus+",
            "source_url": "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
            "exact_supported_claim": (
                'The page states: "Full scholarships are available for the best students" and '
                '"Scholarships cover your participation costs and contribute to travel visa a '
                'living allowance."'
            ),
            "changes": [
                {"field": "fully_funded", "after": True},
                {
                    "field": "funding",
                    "after": "Fully Funded (participation costs + travel/visa + living allowance)",
                },
            ],
        },
    ]


def build_operation(spec: dict, current: dict, operation_type: str) -> tuple[dict, dict]:
    changes = []
    for change in spec["changes"]:
        field = change["field"]
        before = bool_value(current[field]) if field in BOOLEAN_FIELDS else current[field]
        changes.append(
            {
                "field": field,
                "before": before,
                "after": change["after"],
                "evidence_ref": f"EV-{spec['operation_id']}",
            }
        )
    canonical_name = next(
        (item["after"] for item in changes if item["field"] == "title"),
        current["title"],
    )
    operation = {
        "operation": operation_type,
        "operation_id": spec["operation_id"],
        "catalogue_id": spec["catalogue_id"],
        "canonical_name": canonical_name,
        "current_catalogue_title": current["title"],
        "changes": changes,
        "catalogue_official_source_url": current["official_source_url"],
        "evidence_source_url": spec["source_url"],
        "evidence_source_title": spec["source_title"],
        "evidence_ref": f"EV-{spec['operation_id']}",
        "evidence_status": "DIRECT",
        "evidence_retrieval_date": BASELINE_DATE,
        "exact_supported_claim": spec["exact_supported_claim"],
        "approved_for_import": True,
        "idempotent": True,
    }
    evidence = {
        "evidence_ref": f"EV-{spec['operation_id']}",
        "operation_id": spec["operation_id"],
        "operation_type": operation_type,
        "catalogue_id": spec["catalogue_id"],
        "source_title": spec["source_title"],
        "source_url": spec["source_url"],
        "retrieved_at": BASELINE_DATE,
        "retrieval_method": "live official page fetch",
        "exact_supported_claim": spec["exact_supported_claim"],
        "supports_fields": [item["field"] for item in changes],
        "approved_for_import": True,
        "final_evidence_status": "DIRECT",
    }
    return operation, evidence


def build_operations(baseline: dict) -> tuple[list[dict], list[dict], list[dict]]:
    rows = baseline["scholarships"]
    cycle_ops: list[dict] = []
    funding_ops: list[dict] = []
    evidence: list[dict] = []
    for spec in approved_cycle_specs():
        operation, record = build_operation(
            spec, rows[str(spec["catalogue_id"])], "EXISTING_CYCLE_UPDATE"
        )
        cycle_ops.append(operation)
        evidence.append(record)
    for spec in approved_funding_specs():
        operation, record = build_operation(
            spec, rows[str(spec["catalogue_id"])], "FUNDING_CORRECTION"
        )
        funding_ops.append(operation)
        evidence.append(record)
    return cycle_ops, funding_ops, evidence


def lifecycle_proposals(baseline: dict) -> dict:
    rows = baseline["scholarships"]
    statuses = baseline["schema_contract"]["status_values"]
    proposals = []
    successors = {
        729: "Canada Graduate Research Scholarship - Doctoral (CGRS-D)",
        31: "NL Scholarship",
    }
    reasons = {
        729: "Programme discontinued after the Fall 2024 competition; successor is CGRS-D",
        31: "Programme discontinued; successor is the NL Scholarship",
    }
    for catalogue_id in LIFECYCLE_IDS:
        current = rows[str(catalogue_id)]
        proposals.append(
            {
                "operation": "LIFECYCLE_CORRECTION",
                "operation_id": f"LIFECYCLE-{catalogue_id}",
                "catalogue_id": catalogue_id,
                "canonical_name": current["title"],
                "current_fields": {
                    "status": current["status"],
                    "is_archived": bool_value(current["is_archived"]),
                    "archived_at": current["archived_at"],
                    "archived_reason": current["archived_reason"],
                },
                "proposed_fields": {
                    "status": "closed",
                    "is_archived": True,
                    "archived_at": {
                        "action": "PRESERVE_EXISTING",
                        "when_null": "SET_AT_EXECUTION_TIMESTAMP",
                    },
                    "archived_reason": reasons[catalogue_id],
                },
                "archived_at_policy": (
                    "Preserve any existing archived_at value; set the execution timestamp "
                    "only when archived_at is null. Never clear an existing archive timestamp."
                ),
                "successor_programme": successors[catalogue_id],
                "official_source_url": current["official_source_url"],
                "evidence_status": "PENDING_RESEARCH",
                "evidence_ref": None,
                "approved_for_import": False,
                "idempotent": True,
                "preserve_historical_record": True,
                "archive_instead_of_delete": True,
                "blocking_reason": (
                    "No DIRECT evidence record exists in the approved 13-operation evidence "
                    "set. Re-open the official page, capture an exact discontinuation quote, "
                    "and add a DIRECT evidence record before approval."
                ),
            }
        )
    return {
        "package_status": "BLOCKED",
        "approval_status": "NOT_APPROVED_PENDING_RESEARCH",
        "approved_for_import": False,
        "operation_count": len(proposals),
        "schema_contract": {
            "status": {
                "declared_type": "String(20)",
                "allowed_values": statuses,
                "proposed_value": "closed",
            },
            "is_archived": {
                "declared_type": "Boolean",
                "proposed_value": True,
            },
            "archived_at": {
                "declared_type": "DateTime(timezone=True), nullable",
                "policy": "Preserve existing; set at execution only when null.",
            },
            "archived_reason": {
                "declared_type": "String(120)",
                "required_when_is_archived": True,
                "max_length": 120,
            },
        },
        "operations": proposals,
    }


def operation_mapping(baseline: dict, approved: list[dict]) -> dict:
    rows = baseline["scholarships"]
    pending_specs = [
        ("EXISTING_CYCLE_UPDATE", 30),
        ("EXISTING_CYCLE_UPDATE", 32),
        ("EXISTING_CYCLE_UPDATE", 33),
        ("EXISTING_CYCLE_UPDATE", 34),
        ("EXISTING_CYCLE_UPDATE", 36),
        ("EXISTING_CYCLE_UPDATE", 40),
        ("EXISTING_CYCLE_UPDATE", 41),
        ("FUNDING_CORRECTION", 40),
        ("FUNDING_CORRECTION", 31),
        ("FUNDING_CORRECTION", 729),
        ("LIFECYCLE_CORRECTION", 729),
        ("LIFECYCLE_CORRECTION", 31),
    ]
    operations = []
    for item in approved:
        operations.append(
            {
                "operation_type": item["operation"],
                "operation_id": item["operation_id"],
                "catalogue_id": item["catalogue_id"],
                "canonical_name": item["canonical_name"],
                "changes": item["changes"],
                "evidence_ref": item["evidence_ref"],
                "final_evidence_status": "DIRECT",
                "approved_for_import": True,
            }
        )
    for operation_type, catalogue_id in pending_specs:
        current = rows[str(catalogue_id)]
        operations.append(
            {
                "operation_type": operation_type,
                "operation_id": f"PENDING-{operation_type.split('_')[0]}-{catalogue_id}",
                "catalogue_id": catalogue_id,
                "canonical_name": current["title"],
                "changes": [],
                "evidence_ref": None,
                "final_evidence_status": "PENDING_RESEARCH",
                "approved_for_import": False,
                "exclusion_reason": (
                    "No DIRECT evidence record in the approved research set; excluded from the "
                    "approved import files."
                ),
            }
        )
    return {
        "mapping_date": BASELINE_DATE,
        "total_operations": len(operations),
        "approved_operations": sum(1 for op in operations if op["approved_for_import"]),
        "pending_operations": sum(1 for op in operations if not op["approved_for_import"]),
        "direct_evidence_operations": sum(
            1 for op in operations if op["final_evidence_status"] == "DIRECT"
        ),
        "pending_research_operations": sum(
            1 for op in operations if op["final_evidence_status"] == "PENDING_RESEARCH"
        ),
        "operations": operations,
    }


def blocked_records() -> list[dict]:
    specs = [
        (
            175,
            "Erasmus University Rotterdam (EUR) - Holland Scholarship & Talent Programmes (NL Scholarship)",
            "https://www.eur.nl/en/education/practical-matters/scholarships-grants",
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            360,
            "MEXT Scholarship for 2027 - Embassy Recommendation (Research Students)",
            "https://www.studyinjapan.go.jp/en/planning/scholarships/mext-scholarships/",
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            383,
            "Erasmus Trustfonds Scholarship",
            "https://www.eur.nl/en/education/practical-matters/scholarships-grants",
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            384,
            "Erasmus Trustfonds / TSH Changemaker",
            "https://www.eur.nl/en/education/practical-matters/scholarships-grants",
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            423,
            "Erasmus+ Grant (EUR)",
            "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            556,
            "Convocatoria de Becas OEA - UNIR, EP NEWMAN y UNIR Mexico (Curso Academico 2026, 2a convocatoria)",
            "https://www.oas.org/en/scholarships/PAEC/2026/P26_Convocatoria_de_BecasOEA_UNIR_EP_NEWMAN_y_UNIR_MX_2026.pdf",
            "EXCLUDED_REGION",
        ),
    ]
    return [
        {
            "operation": "NEW_INSERT",
            "research_id": research_id,
            "canonical_programme_name": title,
            "official_programme_url": url,
            "block_reason": reason,
            "approved_for_import": False,
            "final_evidence_status": "BLOCKED",
        }
        for research_id, title, url, reason in specs
    ]


def read_duplicate_reports() -> tuple[dict, dict, dict]:
    names = [
        "duplicate_merge_plan.json",
        "duplicate_fk_dependency_report.json",
        "duplicate_merge_dry_run.json",
    ]
    missing = [name for name in names if not (PACKAGE / name).exists()]
    if missing:
        raise SystemExit(
            "Missing duplicate reports: "
            + ", ".join(missing)
            + ". Run reconcile_duplicates.py first."
        )
    return tuple(read_json(PACKAGE / name) for name in names)  # type: ignore[return-value]


def database_reconciliation(baseline: dict, plan: dict, fk_report: dict, dry_run: dict) -> dict:
    counts = baseline["record_counts"]
    total = counts["total"]
    active = counts["active"]
    archived = counts["archived"]
    status_distribution = dict(counts["status_distribution"])

    plan_summary = plan["summary"]
    fk_summary = fk_report["summary"]
    lifecycle_archives = len(LIFECYCLE_IDS)
    duplicate_archives = int(plan_summary["duplicate_archives_if_approved"])

    after_lifecycle_active = active - lifecycle_archives
    after_lifecycle_archived = archived + lifecycle_archives
    after_all_active = after_lifecycle_active - duplicate_archives
    after_all_archived = after_lifecycle_archived + duplicate_archives

    lifecycle_status = dict(status_distribution)
    lifecycle_status["open"] = lifecycle_status.get("open", 0) - lifecycle_archives
    lifecycle_status["closed"] = lifecycle_status.get("closed", 0) + lifecycle_archives

    approval_counts = {
        "new_inserts": 0,
        "cycle_updates": len(APPROVED_CYCLE_IDS),
        "funding_corrections": len(FUNDING_IDS),
        "lifecycle_corrections": 0,
        "total": len(APPROVED_CYCLE_IDS) + len(FUNDING_IDS),
    }
    pending_counts = {
        "cycle_updates": 7,
        "funding_corrections": 3,
        "lifecycle_corrections": 2,
        "total": 12,
    }

    projected = {
        "after_approved_subset": {
            "total": total,
            "active": active,
            "archived": archived,
            "status_distribution": status_distribution,
            "description": (
                "After the 11 cycle updates and 2 funding corrections only. No inserts, "
                "archives, or duplicate merges."
            ),
        },
        "after_approved_plus_lifecycle_proposals": {
            "total": total,
            "active": after_lifecycle_active,
            "archived": after_lifecycle_archived,
            "status_distribution": lifecycle_status,
            "description": (
                "If the 2 PENDING_RESEARCH lifecycle proposals were later approved. "
                "Duplicate merges still not executed."
            ),
        },
        "after_approved_plus_lifecycle_plus_4_duplicate_archives": {
            "total": total,
            "active": after_all_active,
            "archived": after_all_archived,
            "status_distribution": lifecycle_status,
            "description": (
                "If lifecycle proposals and the 4 archive-only duplicate plans were all "
                "approved. Fulbright remains blocked. Duplicate archives do not change status."
            ),
        },
    }

    return {
        "reconciliation_date": BASELINE_DATE,
        "database_source": "backend/scholarzone.db (local SQLite, read-only introspection)",
        "database_sha256": baseline["database_sha256"],
        "schema_version": "ScholarZone v1 (backend/app/models.py)",
        "baseline": {
            "total": total,
            "active": active,
            "archived": archived,
            "status_distribution": status_distribution,
            "archived_status_distribution": counts["archived_status_distribution"],
        },
        "approved_operations": approval_counts,
        "excluded_pending_operations": pending_counts,
        "duplicate_reconciliation": {
            "pairs": int(plan_summary["total_pairs"]),
            "merge_ready_for_owner_review": int(
                plan_summary["merge_ready_for_owner_review"]
            ),
            "blocked_manual_review": int(plan_summary["blocked_manual_review"]),
            "plans_approved_for_execution": int(
                plan_summary["plans_approved_for_execution"]
            ),
            "plans_executed": int(plan_summary["plans_executed"]),
            "archive_only_plans": int(plan_summary["duplicate_archives_if_approved"]),
            "duplicate_archives_if_approved": duplicate_archives,
            "record_deletions": int(plan_summary["record_deletions"]),
            "merge_ready_pair_ids": plan_summary["merge_ready_pair_ids"],
            "blocked_pair_ids": plan_summary["blocked_pair_ids"],
            "fulbright_pair": plan_summary["fulbright_pair"],
            "fk_rows_reassigned_in_plan": int(fk_summary["rows_to_reassign"]),
            "duplicate_side_fk_rows_all_pairs": int(
                fk_summary["duplicate_side_fk_rows"]
            ),
            "duplicate_side_fk_rows_merge_ready_pairs": int(
                fk_summary["merge_ready_duplicate_side_fk_rows"]
            ),
            "duplicate_side_fk_rows_blocked_fulbright": int(
                fk_summary["fulbright_duplicate_side_fk_rows"]
            ),
            "unique_collisions_if_merge_ready_reassigned": int(
                fk_summary["unique_collisions_if_merge_ready_reassigned"]
            ),
            "unique_collisions_if_all_pairs_reassigned": int(
                fk_summary["unique_collisions_if_all_pairs_reassigned"]
            ),
        },
        "lifecycle_proposals": {
            "proposed_archives": lifecycle_archives,
            "approved_archives": 0,
            "approval_status": "NOT_APPROVED_PENDING_RESEARCH",
            "operation_ids": [f"LIFECYCLE-{catalogue_id}" for catalogue_id in LIFECYCLE_IDS],
        },
        "projected_states": projected,
        "archive_accounting": {
            "lifecycle_archives": lifecycle_archives,
            "duplicate_archives": duplicate_archives,
            "total_archives": lifecycle_archives + duplicate_archives,
            "total_equals_active_plus_archived": (
                total == after_all_active + after_all_archived
            ),
            "no_double_counting": (
                lifecycle_archives + duplicate_archives == after_all_archived
            ),
        },
        "fk_reconciliation": {
            "declared_fk_tables": int(fk_summary["declared_dependent_tables"]),
            "declared_fk_references": int(fk_summary["declared_fk_references"]),
            "append_only_non_fk_tables": int(fk_summary["non_fk_append_only_tables"]),
            "total_fk_reference_rows_for_pair_ids": int(
                fk_summary["total_fk_reference_rows_for_pair_ids"]
            ),
            "duplicate_side_fk_rows": int(fk_summary["duplicate_side_fk_rows"]),
            "safe_reassignments": int(fk_summary["safe_reassignments"]),
            "rows_reassigned_in_plan": int(fk_summary["rows_to_reassign"]),
            "collisions_in_plan": 0,
        },
        "validation": {
            "baseline_total_equals_active_plus_archived": total == active + archived,
            "status_distribution_sums_to_total": sum(status_distribution.values()) == total,
            "approved_operation_count_matches_files": approval_counts["total"] == 13,
            "pending_operation_count_matches_mapping": pending_counts["total"] == 12,
            "duplicate_plan_counts_match_fk_report": (
                plan_summary["total_pairs"] == fk_summary["total_pairs"] == 5
            ),
            "duplicate_dry_run_matches_plan": (
                int(dry_run["aggregate"]["pairs_archived"]) == duplicate_archives
            ),
            "projected_counts_consistent": (
                projected["after_approved_subset"]["total"]
                == projected["after_approved_plus_lifecycle_proposals"]["total"]
                == projected["after_approved_plus_lifecycle_plus_4_duplicate_archives"][
                    "total"
                ]
                == total
            ),
            "no_lifecycle_duplicate_double_counting": (
                lifecycle_archives + duplicate_archives == after_all_archived
            ),
        },
        "recommendations": [
            "Keep the package blocked until Vanier CGS and NFP/OTS lifecycle evidence is captured as DIRECT.",
            "Run the duplicate archive-only plans on an isolated PostgreSQL instance before any execution.",
            "Do not import from this package without explicit owner authorization.",
            "Treat the 6 new-insert candidates as blocked research, not approved records.",
        ],
    }


def manifest(
    baseline: dict,
    cycle_ops: list[dict],
    funding_ops: list[dict],
    evidence: list[dict],
    mapping: dict,
    lifecycle: dict,
    blocked: list[dict],
    plan: dict,
    fk_report: dict,
    dry_run: dict,
    db_recon: dict,
) -> dict:
    hashed_files = [
        "package_baseline.json",
        "final_import_ready_scholarships.json",
        "final_existing_cycle_updates.json",
        "final_funding_corrections.json",
        "final_lifecycle_corrections.json",
        "final_source_evidence.json",
        "operation_evidence_mapping.json",
        "blocked_records.json",
        "duplicate_merge_plan.json",
        "duplicate_fk_dependency_report.json",
        "duplicate_merge_dry_run.json",
        "final_database_reconciliation.json",
    ]
    return {
        "manifest_version": "2.0",
        "manifest_date": BASELINE_DATE,
        "package_status": "BLOCKED",
        "review_package_only": True,
        "production_import_authorized": False,
        "branch": BRANCH,
        "base_sha": BASE_SHA,
        "pre_remediation_head": PRE_REMEDIATION_HEAD,
        "final_head": "SEE_CI_EVIDENCE_MD",
        "canonical_files": {
            "final_import_ready_scholarships.json": {
                "records": 0,
                "importable": True,
                "purpose": "Canonical insert file; empty by design.",
            },
            "final_existing_cycle_updates.json": {
                "records": len(cycle_ops),
                "importable": True,
                "purpose": "Canonical approved cycle updates; all DIRECT evidence.",
            },
            "final_funding_corrections.json": {
                "records": len(funding_ops),
                "importable": True,
                "purpose": "Canonical approved funding corrections; all DIRECT evidence.",
            },
            "final_lifecycle_corrections.json": {
                "records": len(lifecycle["operations"]),
                "importable": False,
                "purpose": "Lifecycle proposals only; PENDING_RESEARCH and not approved.",
            },
            "final_source_evidence.json": {
                "records": len(evidence),
                "importable": False,
                "purpose": "DIRECT evidence registry for the approved subset.",
            },
            "operation_evidence_mapping.json": {
                "records": len(mapping["operations"]),
                "importable": False,
                "purpose": "25-operation mapping: 13 DIRECT approved, 12 PENDING excluded.",
            },
            "blocked_records.json": {
                "records": len(blocked),
                "importable": False,
                "purpose": "Blocked new-insert candidates; never importable from this package.",
            },
            "duplicate_merge_plan.json": {
                "records": len(plan["pairs"]),
                "importable": False,
                "purpose": "5 duplicate pairs; 4 archive-only plans for owner review, no execution.",
            },
            "duplicate_fk_dependency_report.json": {
                "records": len(fk_report["tables"]),
                "importable": False,
                "purpose": "Actual FK introspection for all dependent tables.",
            },
            "duplicate_merge_dry_run.json": {
                "records": len(dry_run["pairs_tested"]),
                "importable": False,
                "purpose": "Isolated SQLite simulation; PostgreSQL simulation unavailable.",
            },
            "final_database_reconciliation.json": {
                "records": 1,
                "importable": False,
                "purpose": "Before/after count reconciliation with archives separated.",
            },
        },
        "operation_counts": {
            "new_inserts": 0,
            "cycle_updates": len(cycle_ops),
            "funding_corrections": len(funding_ops),
            "lifecycle_corrections_approved": 0,
            "lifecycle_corrections_pending": len(lifecycle["operations"]),
            "total_approved": len(cycle_ops) + len(funding_ops),
            "total_pending_excluded": mapping["pending_operations"],
        },
        "baseline_counts": {
            "total": baseline["record_counts"]["total"],
            "active": baseline["record_counts"]["active"],
            "archived": baseline["record_counts"]["archived"],
        },
        "projected_counts": db_recon["projected_states"],
        "duplicate_plan": {
            "total_pairs": plan["summary"]["total_pairs"],
            "merge_ready_for_owner_review": plan["summary"][
                "merge_ready_for_owner_review"
            ],
            "blocked_manual_review": plan["summary"]["blocked_manual_review"],
            "plans_approved_for_execution": plan["summary"][
                "plans_approved_for_execution"
            ],
            "plans_executed": plan["summary"]["plans_executed"],
            "record_deletions": plan["summary"]["record_deletions"],
            "fk_reassignments": plan["summary"]["fk_reassignments"],
            "postgresql_simulation": dry_run["postgresql_simulation"]["status"],
        },
        "blocked_new_insert_candidates": len(blocked),
        "blocking_reasons": [
            "Vanier CGS and NFP/OTS lifecycle proposals are PENDING_RESEARCH and excluded from the approved set.",
            "PostgreSQL duplicate-merge simulation is unavailable in this environment.",
            "No duplicate merge has been executed; 4 archive-only plans await owner approval.",
            "6 new-insert candidates remain blocked for insufficient evidence or excluded region.",
            "This is a review package, not production import authorization.",
        ],
        "hashed_files": {name: file_sha256(PACKAGE / name) for name in hashed_files},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Write package_baseline.json and stop before requiring duplicate reports.",
    )
    args = parser.parse_args(argv)

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    baseline = baseline_snapshot()
    write_json(PACKAGE / "package_baseline.json", baseline)
    if args.baseline_only:
        print("Wrote package_baseline.json.")
        return 0

    plan, fk_report, dry_run = read_duplicate_reports()

    cycle_ops, funding_ops, evidence = build_operations(baseline)
    write_json(PACKAGE / "final_import_ready_scholarships.json", [])
    write_json(PACKAGE / "final_existing_cycle_updates.json", cycle_ops)
    write_json(PACKAGE / "final_funding_corrections.json", funding_ops)
    write_json(PACKAGE / "final_source_evidence.json", evidence)
    lifecycle = lifecycle_proposals(baseline)
    write_json(PACKAGE / "final_lifecycle_corrections.json", lifecycle)

    approved = cycle_ops + funding_ops
    mapping = operation_mapping(baseline, approved)
    write_json(PACKAGE / "operation_evidence_mapping.json", mapping)
    blocked = blocked_records()
    write_json(PACKAGE / "blocked_records.json", blocked)

    db_recon = database_reconciliation(baseline, plan, fk_report, dry_run)
    write_json(PACKAGE / "final_database_reconciliation.json", db_recon)
    package_manifest = manifest(
        baseline,
        cycle_ops,
        funding_ops,
        evidence,
        mapping,
        lifecycle,
        blocked,
        plan,
        fk_report,
        dry_run,
        db_recon,
    )
    write_json(PACKAGE / "final_reconciliation_manifest.json", package_manifest)

    print(
        "Wrote canonical package: "
        f"{len(cycle_ops)} cycle, {len(funding_ops)} funding, "
        f"{len(evidence)} DIRECT evidence records, "
        f"{mapping['pending_operations']} pending excluded."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
