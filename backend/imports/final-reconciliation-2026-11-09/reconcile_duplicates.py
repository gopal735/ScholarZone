"""Generate the duplicate reconciliation reports from the local baseline.

The reports are generated from ``package_baseline.json`` so the FK map and row
counts are reproducible without the production database. The dry run uses an
isolated copy of ``backend/scholarzone.db`` and never touches the source file.

Outputs (all canonical):

* ``duplicate_merge_plan.json``
* ``duplicate_fk_dependency_report.json``
* ``duplicate_merge_dry_run.json``

Run from this directory, before ``build_canonical_package.py``:

    python reconcile_duplicates.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
BACKEND = PACKAGE.parents[1]
DB_PATH = BACKEND / "scholarzone.db"
BASELINE_PATH = PACKAGE / "package_baseline.json"
BASELINE_DATE = "2026-11-10"
DRY_RUN_TIMESTAMP = "2026-11-10T00:00:00+00:00"

MERGE_READY = "MERGE_READY_FOR_OWNER_REVIEW"
BLOCKED = "BLOCKED_MANUAL_REVIEW"

PAIR_SPECS = [
    {
        "pair_id": 1,
        "canonical_id": 183,
        "duplicate_id": 753,
        "classification": MERGE_READY,
        "confidence": "HIGH",
        "evidence_same_programme": (
            "Same university (Lund University), same programme title, same country "
            "(Sweden), same funding label (Partial), and official URL paths on the same "
            "lunduniversity.lu.se domain."
        ),
        "conflicts": [
            {
                "field": "degree",
                "canonical": "Master's, PhD",
                "duplicate": "Bachelor's, Master's",
                "resolution": "Do not rewrite degree in an archive-only plan; owner review.",
            }
        ],
    },
    {
        "pair_id": 2,
        "canonical_id": 270,
        "duplicate_id": 1244,
        "classification": MERGE_READY,
        "confidence": "HIGH",
        "evidence_same_programme": (
            "Same university (Copenhagen Business School), same programme title, same "
            "country (Denmark), and official URL paths on the same cbs.dk domain."
        ),
        "conflicts": [
            {
                "field": "funding",
                "canonical": "Partial",
                "duplicate": "Partial to Full",
                "resolution": "Do not auto-resolve conflicting funding; owner review.",
            },
            {
                "field": "degree",
                "canonical": "Master's, PhD",
                "duplicate": "Master's (MSc)",
                "resolution": "Do not rewrite degree in an archive-only plan; owner review.",
            },
        ],
    },
    {
        "pair_id": 3,
        "canonical_id": 271,
        "duplicate_id": 760,
        "classification": MERGE_READY,
        "confidence": "HIGH",
        "evidence_same_programme": (
            "Same university (University of Copenhagen), same programme title, same "
            "country (Denmark), same funding label (Partial), and official URL paths on "
            "the same ku.dk domain."
        ),
        "conflicts": [
            {
                "field": "degree",
                "canonical": "Master's, PhD",
                "duplicate": "Master's",
                "resolution": "Do not rewrite degree in an archive-only plan; owner review.",
            }
        ],
    },
    {
        "pair_id": 4,
        "canonical_id": 285,
        "duplicate_id": 1277,
        "classification": MERGE_READY,
        "confidence": "HIGH",
        "evidence_same_programme": (
            "Same programme title, same country (Hungary), same funding label (Fully "
            "Funded), and official URLs on the same stipendiumhungaricum.hu domain: "
            "root domain versus /apply_call path."
        ),
        "conflicts": [
            {
                "field": "degree",
                "canonical": "Bachelor's, Master's, One-tier Master's, Doctoral, Non-degree",
                "duplicate": "Bachelor's, Master's, One-tier Master's, PhD, Postdoctoral, Non-degree",
                "resolution": "Do not rewrite degree in an archive-only plan; owner review.",
            }
        ],
    },
    {
        "pair_id": 5,
        "canonical_id": 1217,
        "duplicate_id": 1309,
        "classification": BLOCKED,
        "confidence": "MEDIUM",
        "evidence_same_programme": (
            "Same programme title and country, but the two records use different official "
            "domains: foreign.fulbrightonline.org (application portal) and "
            "fulbright.state.gov (programme information)."
        ),
        "conflicts": [
            {
                "field": "official_source_url",
                "canonical": "https://foreign.fulbrightonline.org",
                "duplicate": "https://fulbright.state.gov",
                "resolution": "Blocked; do not write either URL to the other record.",
            },
            {
                "field": "funding",
                "canonical": "Fully Funded",
                "duplicate": "Partial Funding",
                "resolution": "Blocked; do not auto-resolve funding.",
            },
            {
                "field": "degree",
                "canonical": "Master's, PhD, Research",
                "duplicate": "Bachelor's, Master's, PhD",
                "resolution": "Blocked; owner must confirm programme scope.",
            },
            {
                "field": "region",
                "canonical": "World Top Demand",
                "duplicate": "North America",
                "resolution": "Blocked; owner must confirm canonical region.",
            },
        ],
        "blocking_reason": (
            "Different official domains, funding values, degree scope, and region. "
            "The pair cannot be merged or archived until the Fulbright programme owner "
            "confirms whether the two records describe the same opportunity."
        ),
    },
]

URL_FIELDS = ("official_source_url", "application_link")


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


def pair_ids() -> list[int]:
    ids: list[int] = []
    for spec in PAIR_SPECS:
        ids.extend([spec["canonical_id"], spec["duplicate_id"]])
    return ids


def duplicate_side_total(counts: dict[str, int], spec: dict) -> int:
    return int(counts.get(str(spec["duplicate_id"]), 0))


def canonical_side_total(counts: dict[str, int], spec: dict) -> int:
    return int(counts.get(str(spec["canonical_id"]), 0))


def build_fk_report(baseline: dict) -> dict:
    foreign_keys = baseline["foreign_keys"]
    rows = baseline["scholarships"]
    counts_by_table = foreign_keys["row_counts_by_pair_id"]
    declared = sorted(foreign_keys["declared_fk_tables"], key=lambda item: item["table"])
    ids = pair_ids()

    tables = []
    duplicate_side_rows = 0
    merge_ready_duplicate_rows = 0
    fulbright_duplicate_rows = 0
    total_reference_rows = 0
    tables_with_rows = 0
    collisions_merge_ready = 0
    collisions_all = 0

    for entry in declared:
        table = entry["table"]
        counts = {
            key: int(value)
            for key, value in counts_by_table.get(table, {}).items()
            if int(key) in ids
        }
        total = sum(counts.values())
        total_reference_rows += total
        if total:
            tables_with_rows += 1

        duplicate_rows = 0
        pair_rows = {}
        for spec in PAIR_SPECS:
            canonical_count = int(counts.get(str(spec["canonical_id"]), 0))
            duplicate_count = int(counts.get(str(spec["duplicate_id"]), 0))
            pair_rows[str(spec["pair_id"])] = {
                "canonical_id": spec["canonical_id"],
                "canonical_rows": canonical_count,
                "duplicate_id": spec["duplicate_id"],
                "duplicate_rows": duplicate_count,
            }
            duplicate_rows += duplicate_count
            if spec["classification"] == MERGE_READY:
                merge_ready_duplicate_rows += duplicate_count
            else:
                fulbright_duplicate_rows += duplicate_count
            unique_constraints = foreign_keys["unique_constraints"].get(table, [])
            collision = (
                table == "scholarship_supervisor_coverage"
                and canonical_count > 0
                and duplicate_count > 0
                and any(
                    constraint["columns"] == ["scholarship_id"]
                    for constraint in unique_constraints
                )
            )
            if collision:
                collisions_all += 1
                if spec["classification"] == MERGE_READY:
                    collisions_merge_ready += 1
        duplicate_side_rows += duplicate_rows

        if table == "scholarship_supervisor_coverage":
            assessment = "UNSAFE_UNIQUE_COLLISION"
            reason = (
                "Every scholarship has exactly one coverage row under "
                "UNIQUE(scholarship_id). Reassigning a duplicate-side row to the canonical "
                "row would collide with the canonical coverage row. Preserve the row on the "
                "archived duplicate instead."
            )
        elif total == 0:
            assessment = "NO_ROWS_TO_REASSIGN"
            reason = "No rows reference any of the 10 duplicate-pair IDs in this table."
        else:
            assessment = "REVIEW_REQUIRED"
            reason = "Rows exist; owner review required before any reassignment."

        tables.append(
            {
                "table": table,
                "column": entry["column"],
                "references": entry["references"],
                "on_update": entry["on_update"],
                "on_delete": entry["on_delete"],
                "unique_constraints": foreign_keys["unique_constraints"].get(table, []),
                "reference_rows_total": total,
                "reference_rows_by_pair": pair_rows,
                "duplicate_side_rows": duplicate_rows,
                "reassignment_assessment": assessment,
                "reason": reason,
            }
        )

    append_only_tables = []
    audit_counts = {
        key: int(value)
        for key, value in counts_by_table.get("scholarship_image_audit", {}).items()
        if int(key) in ids
    }
    if audit_counts:
        append_only_tables.append(
            {
                "table": "scholarship_image_audit",
                "column": "scholarship_id",
                "is_foreign_key": False,
                "reference_rows_by_pair_id": audit_counts,
                "reference_rows_total": sum(audit_counts.values()),
                "reassignment_assessment": "APPEND_ONLY_CANNOT_REASSIGN",
                "reason": (
                    "scholarship_image_audit has no FK to scholarships and its triggers "
                    "forbid UPDATE and DELETE. Rows must never be reassigned or removed."
                ),
            }
        )

    pair_summaries = []
    for spec in PAIR_SPECS:
        pair_tables = {}
        pair_duplicate_rows = 0
        for table in tables:
            table_name = table["table"]
            pair_entry = table["reference_rows_by_pair"][str(spec["pair_id"])]
            if pair_entry["canonical_rows"] or pair_entry["duplicate_rows"]:
                pair_tables[table_name] = pair_entry
                pair_duplicate_rows += pair_entry["duplicate_rows"]
        collision = (
            "scholarship_supervisor_coverage" in pair_tables
            and pair_tables["scholarship_supervisor_coverage"]["canonical_rows"] > 0
            and pair_tables["scholarship_supervisor_coverage"]["duplicate_rows"] > 0
        )
        pair_summaries.append(
            {
                "pair_id": spec["pair_id"],
                "ids": [spec["canonical_id"], spec["duplicate_id"]],
                "canonical_id": spec["canonical_id"],
                "duplicate_id": spec["duplicate_id"],
                "classification": spec["classification"],
                "duplicate_side_fk_rows": pair_duplicate_rows,
                "safe_reassignments": 0,
                "unique_collision_if_reassigned": collision,
                "tables_with_rows": pair_tables,
            }
        )

    canonical_with_rows = sum(
        canonical_side_total(counts, spec)
        for spec in PAIR_SPECS
        for counts in [counts_by_table.get("scholarship_supervisor_coverage", {})]
    )

    return {
        "report_version": "2.0",
        "report_date": BASELINE_DATE,
        "database_source": baseline["database_source"],
        "database_sha256": baseline["database_sha256"],
        "introspection": {
            "method": "PRAGMA foreign_key_list and PRAGMA index_list on the baseline SQLite database",
            "scholarship_id_range": [min(ids), max(ids)],
            "declared_fk_references": len(tables),
            "note": (
                "A table can declare more than one FK in the broader schema, but every "
                "dependent table in this database declares exactly one FK to scholarships.id."
            ),
        },
        "summary": {
            "total_pairs": len(PAIR_SPECS),
            "declared_dependent_tables": len(tables),
            "declared_fk_references": len(tables),
            "tables_with_reference_rows_for_pair_ids": tables_with_rows,
            "total_fk_reference_rows_for_pair_ids": total_reference_rows,
            "canonical_side_fk_rows_for_pair_ids": canonical_with_rows,
            "duplicate_side_fk_rows": duplicate_side_rows,
            "merge_ready_duplicate_side_fk_rows": merge_ready_duplicate_rows,
            "fulbright_duplicate_side_fk_rows": fulbright_duplicate_rows,
            "safe_reassignments": 0,
            "rows_to_reassign": 0,
            "rows_preserved_on_archived_duplicates": merge_ready_duplicate_rows,
            "unique_collisions_if_merge_ready_reassigned": collisions_merge_ready,
            "unique_collisions_if_all_pairs_reassigned": collisions_all,
            "non_fk_append_only_tables": len(append_only_tables),
            "non_fk_append_only_rows_for_pair_ids": sum(
                item["reference_rows_total"] for item in append_only_tables
            ),
            "correction_note": (
                "The previous report claimed 13 dependent tables and 20 foreign-key "
                "references. Direct introspection finds 14 dependent tables, 14 declared FK "
                "references, and 10 reference rows for these pair IDs, all in "
                "scholarship_supervisor_coverage. There is also 1 append-only non-FK "
                "scholarship_image_audit row on canonical ID 285."
            ),
        },
        "tables": tables,
        "append_only_non_fk_tables": append_only_tables,
        "pairs": pair_summaries,
    }


def record_summary(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "country": row["country"],
        "degree": row["degree"],
        "funding": row["funding"],
        "status": row["status"],
        "is_archived": bool(row["is_archived"]),
        "official_source_url": row["official_source_url"],
        "application_link": row["application_link"],
    }


def archived_reason(spec: dict, canonical_title: str) -> str:
    reason = (
        f"Duplicate of ID {spec['canonical_id']} ({canonical_title}); "
        f"archive-only {BASELINE_DATE}"
    )
    if len(reason) > 120:
        reason = f"Duplicate of ID {spec['canonical_id']}; archive-only {BASELINE_DATE}"
    return reason


def build_plan(baseline: dict, fk_report: dict) -> dict:
    rows = baseline["scholarships"]
    pairs = []
    merge_ready_ids = []
    blocked_ids = []

    for spec in PAIR_SPECS:
        canonical = rows[str(spec["canonical_id"])]
        duplicate = rows[str(spec["duplicate_id"])]
        if spec["classification"] == MERGE_READY:
            merge_ready_ids.append(spec["pair_id"])
        else:
            blocked_ids.append(spec["pair_id"])

        reason = archived_reason(spec, canonical["title"])
        preconditions = [
            {
                "check": "canonical_exists",
                "expected": True,
                "actual": True,
            },
            {
                "check": "canonical_not_archived",
                "expected": True,
                "actual": not bool(canonical["is_archived"]),
            },
            {
                "check": "duplicate_exists",
                "expected": True,
                "actual": True,
            },
            {
                "check": "duplicate_not_archived",
                "expected": True,
                "actual": not bool(duplicate["is_archived"]),
            },
            {
                "check": "distinct_ids",
                "expected": True,
                "actual": spec["canonical_id"] != spec["duplicate_id"],
            },
            {
                "check": "canonical_official_source_url_is_scalar",
                "expected": True,
                "actual": isinstance(canonical["official_source_url"], str),
            },
            {
                "check": "duplicate_official_source_url_is_scalar",
                "expected": True,
                "actual": isinstance(duplicate["official_source_url"], str),
            },
            {
                "check": "official_source_urls_are_distinct",
                "expected": True,
                "actual": canonical["official_source_url"]
                != duplicate["official_source_url"],
            },
        ]

        if spec["classification"] == MERGE_READY:
            operations = [
                {
                    "step": 1,
                    "operation": "VERIFY_PRECONDITIONS",
                    "kind": "READ_ONLY",
                    "description": (
                        "Confirm both records exist, are active, have distinct scalar "
                        "official_source_url values, and are not already archived."
                    ),
                    "preconditions": preconditions,
                    "expected_rows_affected": 0,
                },
                {
                    "step": 2,
                    "operation": "ARCHIVE_DUPLICATE",
                    "kind": "WRITE",
                    "description": (
                        "Archive the duplicate record only. Status, URL, funding, degree, "
                        "region, and foreign keys are left untouched."
                    ),
                    "sql": (
                        "UPDATE scholarships SET is_archived = 1, "
                        "archived_at = COALESCE(archived_at, :execution_timestamp), "
                        "archived_reason = :archived_reason "
                        "WHERE id = :duplicate_id AND is_archived = 0"
                    ),
                    "parameters": {
                        "execution_timestamp": "EXECUTION_TIMESTAMP",
                        "archived_reason": reason,
                        "duplicate_id": spec["duplicate_id"],
                    },
                    "writes_fields": [
                        "is_archived",
                        "archived_at",
                        "archived_reason",
                    ],
                    "expected_rows_affected": 1,
                },
                {
                    "step": 3,
                    "operation": "VERIFY_POSTCONDITIONS",
                    "kind": "READ_ONLY",
                    "description": (
                        "Confirm the duplicate is archived, the canonical row is unchanged, "
                        "the total row count is unchanged, and no URL or FK row was rewritten."
                    ),
                    "postconditions": [
                        "duplicate is_archived = 1",
                        "duplicate archived_reason is set",
                        "canonical record is byte-identical for all non-audit fields",
                        "scholarships total count is unchanged",
                        "scholarship_supervisor_coverage row count is unchanged",
                        "official_source_url is still a scalar and unique",
                    ],
                    "expected_rows_affected": 0,
                },
            ]
        else:
            operations = [
                {
                    "step": 1,
                    "operation": "REQUIRE_MANUAL_REVIEW",
                    "kind": "READ_ONLY",
                    "description": (
                        "Do not archive, merge, or rewrite either Fulbright record. The "
                        "programme owner must first confirm whether the two official domains "
                        "describe the same opportunity."
                    ),
                    "preconditions": preconditions,
                    "blocking_reason": spec["blocking_reason"],
                    "expected_rows_affected": 0,
                }
            ]

        pairs.append(
            {
                "pair_id": spec["pair_id"],
                "classification": spec["classification"],
                "confidence": spec["confidence"],
                "canonical_id": spec["canonical_id"],
                "duplicate_id": spec["duplicate_id"],
                "canonical_record": record_summary(canonical),
                "duplicate_record": record_summary(duplicate),
                "evidence_same_programme": spec["evidence_same_programme"],
                "conflicts": spec["conflicts"],
                "preconditions": preconditions,
                "operations": operations,
                "fk_handling": {
                    "reassigned_rows": 0,
                    "preserved_duplicate_side_rows": next(
                        pair["duplicate_side_fk_rows"]
                        for pair in fk_report["pairs"]
                        if pair["pair_id"] == spec["pair_id"]
                    ),
                    "reason": (
                        "UNIQUE(scholarship_id) on scholarship_supervisor_coverage makes "
                        "reassignment collide with the canonical coverage row. Keep the "
                        "duplicate coverage row attached to the archived duplicate."
                    ),
                },
                "rollback": (
                    "Restore the pre-state captured by VERIFY_PRECONDITIONS for is_archived, "
                    "archived_at, and archived_reason. No scholarship row is ever deleted."
                ),
                "execution": {
                    "status": "NOT_EXECUTED",
                    "approved_for_execution": False,
                    "execution_gate": "OWNER_APPROVAL_REQUIRED",
                },
                "risk_level": "LOW" if spec["classification"] == MERGE_READY else "MEDIUM",
                "estimated_duration_ms": 50 if spec["classification"] == MERGE_READY else 0,
                "requires_owner_approval": True,
            }
        )

    summary = {
        "total_pairs": len(pairs),
        "merge_ready_for_owner_review": len(merge_ready_ids),
        "blocked_manual_review": len(blocked_ids),
        "plans_approved_for_execution": 0,
        "plans_executed": 0,
        "duplicate_archives_if_approved": len(merge_ready_ids),
        "record_deletions": 0,
        "url_writes": 0,
        "funding_writes": 0,
        "fk_reassignments": 0,
        "status_changes": 0,
        "merge_ready_pair_ids": merge_ready_ids,
        "blocked_pair_ids": blocked_ids,
        "fulbright_pair": {
            "pair_id": 5,
            "canonical_id": 1217,
            "duplicate_id": 1309,
            "status": BLOCKED,
        },
    }

    return {
        "plan_version": "2.0",
        "plan_date": BASELINE_DATE,
        "strategy": "ARCHIVE_ONLY_NO_DATA_REWRITE",
        "execution_status": "NOT_EXECUTED",
        "plans_approved_for_execution": 0,
        "owner_approval_required": True,
        "summary": summary,
        "guarantees": {
            "url_writes": 0,
            "funding_writes": 0,
            "degree_writes": 0,
            "region_writes": 0,
            "status_changes": 0,
            "fk_reassignments": 0,
            "record_deletions": 0,
            "audit_rows_inserted": 0,
        },
        "prerequisites": [
            "Owner approval for each pair, recorded outside this package.",
            "A fresh database backup with verified restore procedure.",
            "Run the archive-only statements on an isolated PostgreSQL copy and compare counts.",
            "Confirm the canonical and duplicate official_source_url values are still distinct and scalar.",
            "Confirm scholarship_supervisor_coverage still has UNIQUE(scholarship_id).",
        ],
        "pairs": pairs,
        "fulbright_block": {
            "pair_id": 5,
            "canonical_id": 1217,
            "duplicate_id": 1309,
            "classification": BLOCKED,
            "executable": False,
            "reason": next(
                spec["blocking_reason"]
                for spec in PAIR_SPECS
                if spec["classification"] == BLOCKED
            ),
            "required_owner_decisions": [
                "Confirm whether foreign.fulbrightonline.org and fulbright.state.gov describe the same opportunity.",
                "Confirm the canonical funding classification.",
                "Confirm the canonical degree scope.",
                "Confirm the canonical region.",
            ],
        },
    }


def postgres_availability() -> dict:
    dsn_candidates = {
        "SCHOLARZONE_DATABASE_URL": os.environ.get("SCHOLARZONE_DATABASE_URL", ""),
        "TEST_DATABASE_URL": os.environ.get("TEST_DATABASE_URL", ""),
        "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
        "SCHOLARZONE_POSTGRES_TEST_DSN": os.environ.get(
            "SCHOLARZONE_POSTGRES_TEST_DSN", ""
        ),
    }
    disposable_dsn = any(
        value.startswith("postgres")
        for key, value in dsn_candidates.items()
        if key in {"TEST_DATABASE_URL", "SCHOLARZONE_POSTGRES_TEST_DSN"}
    )
    checks = {
        "psql_client": shutil.which("psql") is not None,
        "pg_isready_client": shutil.which("pg_isready") is not None,
        "docker_client": shutil.which("docker") is not None,
        "psycopg_installed": importlib.util.find_spec("psycopg") is not None,
        "disposable_test_dsn_present": disposable_dsn,
        "environment_dsn_names_present": [
            key for key, value in dsn_candidates.items() if value
        ],
    }
    available = (
        checks["disposable_test_dsn_present"]
        and (checks["psql_client"] or checks["psycopg_installed"])
    )
    return {
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "attempted": False,
        "checks": checks,
        "reason": (
            "A disposable PostgreSQL test DSN and client are available."
            if available
            else (
                "No disposable PostgreSQL test DSN is configured and no local PostgreSQL "
                "client/server is available. The simulation was not attempted; this is not "
                "reported as a pass."
            )
        ),
        "required_before_execution": (
            "Run the same archive-only updates and the UNIQUE(scholarship_id) collision "
            "probe against an isolated PostgreSQL 16/18 database, then attach the run log."
        ),
    }


def detect_array_urls(con: sqlite3.Connection, ids: list[int]) -> int:
    query = (
        "SELECT COUNT(*) FROM scholarships WHERE id IN ("
        + ",".join("?" for _ in ids)
        + ") AND (typeof(official_source_url) != 'text' OR "
        "trim(official_source_url) LIKE '[%' OR trim(official_source_url) LIKE '{%')"
    )
    return int(con.execute(query, ids).fetchone()[0])


def status_distribution(con: sqlite3.Connection) -> dict[str, int]:
    return {
        row[0]: int(row[1])
        for row in con.execute(
            "SELECT status, COUNT(*) FROM scholarships GROUP BY status ORDER BY status"
        )
    }


def counts(con: sqlite3.Connection) -> dict:
    row = con.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN is_archived=0 THEN 1 ELSE 0 END),0) AS active, "
        "COALESCE(SUM(CASE WHEN is_archived=1 THEN 1 ELSE 0 END),0) AS archived "
        "FROM scholarships"
    ).fetchone()
    return {"total": int(row[0]), "active": int(row[1]), "archived": int(row[2])}


def run_dry_run(baseline: dict, plan: dict) -> dict:
    ids = pair_ids()
    source_hash_before = file_sha256(DB_PATH) if DB_PATH.exists() else None
    if source_hash_before != baseline["database_sha256"]:
        raise SystemExit(
            "The local database does not match package_baseline.json. "
            "Regenerate the baseline with build_canonical_package.py before the dry run."
        )

    results = []
    collision_results = []
    source = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    temp_dir = tempfile.mkdtemp(prefix="scholarzone-duplicate-dry-run-")
    temp_path = Path(temp_dir) / "isolated.sqlite3"
    try:
        target = sqlite3.connect(temp_path)
        try:
            source.backup(target)
            target.execute("PRAGMA foreign_keys = ON")
            before = counts(target)
            before_status = status_distribution(target)
            before_coverage = int(
                target.execute(
                    "SELECT COUNT(*) FROM scholarship_supervisor_coverage"
                ).fetchone()[0]
            )
            before_array_urls = detect_array_urls(target, ids)

            merge_ready = [
                pair
                for pair in plan["pairs"]
                if pair["classification"] == MERGE_READY
            ]
            for pair in merge_ready:
                canonical_id = pair["canonical_id"]
                duplicate_id = pair["duplicate_id"]
                reason = next(
                    item["parameters"]["archived_reason"]
                    for item in pair["operations"]
                    if item["operation"] == "ARCHIVE_DUPLICATE"
                )
                pre_duplicate = target.execute(
                    "SELECT id, title, status, is_archived, archived_at, "
                    "archived_reason, official_source_url, funding, degree, region "
                    "FROM scholarships WHERE id = ?",
                    (duplicate_id,),
                ).fetchone()
                pre_canonical = target.execute(
                    "SELECT id, title, status, is_archived, archived_at, "
                    "archived_reason, official_source_url, funding, degree, region "
                    "FROM scholarships WHERE id = ?",
                    (canonical_id,),
                ).fetchone()

                target.execute("SAVEPOINT collision_probe")
                collision_detected = False
                collision_error = None
                try:
                    target.execute(
                        "UPDATE scholarship_supervisor_coverage "
                        "SET scholarship_id = ? WHERE scholarship_id = ?",
                        (canonical_id, duplicate_id),
                    )
                except sqlite3.IntegrityError as exc:
                    collision_detected = True
                    collision_error = str(exc)
                finally:
                    target.execute("ROLLBACK TO collision_probe")
                    target.execute("RELEASE collision_probe")
                collision_results.append(
                    {
                        "pair_id": pair["pair_id"],
                        "table": "scholarship_supervisor_coverage",
                        "attempted_reassignment": {
                            "from": duplicate_id,
                            "to": canonical_id,
                        },
                        "expected_result": "UNIQUE_COLLISION",
                        "actual_result": (
                            "UNIQUE_COLLISION"
                            if collision_detected
                            else "UNEXPECTED_SUCCESS"
                        ),
                        "error": collision_error,
                        "rows_reassigned": 0,
                    }
                )

                cursor = target.execute(
                    "UPDATE scholarships SET is_archived = 1, "
                    "archived_at = COALESCE(archived_at, ?), "
                    "archived_reason = ? "
                    "WHERE id = ? AND is_archived = 0",
                    (DRY_RUN_TIMESTAMP, reason, duplicate_id),
                )
                rows_affected = cursor.rowcount
                target.commit()

                post_duplicate = target.execute(
                    "SELECT id, title, status, is_archived, archived_at, "
                    "archived_reason, official_source_url, funding, degree, region "
                    "FROM scholarships WHERE id = ?",
                    (duplicate_id,),
                ).fetchone()
                post_canonical = target.execute(
                    "SELECT id, title, status, is_archived, archived_at, "
                    "archived_reason, official_source_url, funding, degree, region "
                    "FROM scholarships WHERE id = ?",
                    (canonical_id,),
                ).fetchone()

                checks = {
                    "rows_affected_1": rows_affected == 1,
                    "duplicate_is_archived": post_duplicate[3] == 1,
                    "duplicate_status_unchanged": post_duplicate[2] == pre_duplicate[2],
                    "duplicate_archived_reason_set": post_duplicate[5] == reason,
                    "duplicate_official_source_url_unchanged": (
                        post_duplicate[6] == pre_duplicate[6]
                    ),
                    "duplicate_funding_unchanged": post_duplicate[7] == pre_duplicate[7],
                    "duplicate_degree_unchanged": post_duplicate[8] == pre_duplicate[8],
                    "duplicate_region_unchanged": post_duplicate[9] == pre_duplicate[9],
                    "canonical_row_unchanged": post_canonical == pre_canonical,
                    "unique_collision_prevented_fk_reassignment": collision_detected,
                }
                results.append(
                    {
                        "pair_id": pair["pair_id"],
                        "canonical_id": canonical_id,
                        "duplicate_id": duplicate_id,
                        "pre_state": {
                            "duplicate_is_archived": bool(pre_duplicate[3]),
                            "duplicate_status": pre_duplicate[2],
                            "duplicate_official_source_url": pre_duplicate[6],
                            "canonical_is_archived": bool(pre_canonical[3]),
                        },
                        "operation": "ARCHIVE_DUPLICATE",
                        "rows_affected": rows_affected,
                        "post_state": {
                            "duplicate_is_archived": bool(post_duplicate[3]),
                            "duplicate_status": post_duplicate[2],
                            "duplicate_archived_at": post_duplicate[4],
                            "duplicate_archived_reason": post_duplicate[5],
                            "duplicate_official_source_url": post_duplicate[6],
                            "canonical_is_archived": bool(post_canonical[3]),
                        },
                        "checks": checks,
                        "result": "PASS" if all(checks.values()) else "FAIL",
                    }
                )

            after = counts(target)
            after_status = status_distribution(target)
            after_coverage = int(
                target.execute(
                    "SELECT COUNT(*) FROM scholarship_supervisor_coverage"
                ).fetchone()[0]
            )
            after_array_urls = detect_array_urls(target, ids)
            scalar_urls = int(
                target.execute(
                    "SELECT COUNT(DISTINCT official_source_url) FROM scholarships "
                    "WHERE id IN ("
                    + ",".join("?" for _ in ids)
                    + ") AND official_source_url IS NOT NULL",
                    ids,
                ).fetchone()[0]
            )
            pair_url_count = int(
                target.execute(
                    "SELECT COUNT(*) FROM scholarships WHERE id IN ("
                    + ",".join("?" for _ in ids)
                    + ") AND official_source_url IS NOT NULL",
                    ids,
                ).fetchone()[0]
            )
            target.close()
        finally:
            target.close()
        source_hash_after = file_sha256(DB_PATH)
        isolated_hash = file_sha256(temp_path)
    finally:
        source.close()
        shutil.rmtree(temp_dir, ignore_errors=True)

    all_passed = all(item["result"] == "PASS" for item in results)
    all_collisions = all(
        item["actual_result"] == "UNIQUE_COLLISION" for item in collision_results
    )
    return {
        "dry_run_version": "2.0",
        "dry_run_date": BASELINE_DATE,
        "mode": "ISOLATED_SQLITE_COPY",
        "source_database": "backend/scholarzone.db",
        "source_database_sha256": source_hash_before,
        "source_database_unchanged": source_hash_before == source_hash_after,
        "isolated_copy_sha256": isolated_hash,
        "postgresql_simulation": postgres_availability(),
        "pairs_tested": results,
        "uniqueness_collision_tests": collision_results,
        "aggregate": {
            "pairs_tested": len(results),
            "pairs_passed": sum(1 for item in results if item["result"] == "PASS"),
            "pairs_failed": sum(1 for item in results if item["result"] != "PASS"),
            "pairs_archived": sum(1 for item in results if item["rows_affected"] == 1),
            "collisions_detected": sum(
                1
                for item in collision_results
                if item["actual_result"] == "UNIQUE_COLLISION"
            ),
            "rows_deleted": 0,
            "url_writes": 0,
            "funding_writes": 0,
            "degree_writes": 0,
            "region_writes": 0,
            "status_changes": 0,
            "fk_rows_reassigned": 0,
            "coverage_rows_before": before_coverage,
            "coverage_rows_after": after_coverage,
            "official_source_url_arrays_before": before_array_urls,
            "official_source_url_arrays_after": after_array_urls,
            "pair_urls_non_null": pair_url_count,
            "pair_urls_distinct": scalar_urls,
            "total_before": before["total"],
            "active_before": before["active"],
            "archived_before": before["archived"],
            "total_after": after["total"],
            "active_after": after["active"],
            "archived_after": after["archived"],
            "status_distribution_before": before_status,
            "status_distribution_after": after_status,
            "all_pair_checks_passed": all_passed,
            "all_collision_probes_passed": all_collisions,
        },
        "database_state_after_dry_run": {
            "total": after["total"],
            "active": after["active"],
            "archived": after["archived"],
            "status_distribution": after_status,
            "merges_executed_in_source_database": 0,
        },
        "limitations": [
            "The simulation ran on an isolated SQLite copy, not on PostgreSQL.",
            "SQLite locking and constraint-error text differ from PostgreSQL; the UNIQUE collision outcome should be reconfirmed on PostgreSQL.",
            "No audit row was inserted because scholarship_restore_records requires source/target version IDs and is not a merge-audit table.",
            "The four archive-only plans were not executed against the source database.",
        ],
    }


def main() -> int:
    if not BASELINE_PATH.exists():
        raise SystemExit(
            "package_baseline.json is missing. Run build_canonical_package.py once "
            "to create the baseline, then run this script."
        )
    baseline = read_json(BASELINE_PATH)
    fk_report = build_fk_report(baseline)
    plan = build_plan(baseline, fk_report)
    dry_run = run_dry_run(baseline, plan)

    write_json(PACKAGE / "duplicate_fk_dependency_report.json", fk_report)
    write_json(PACKAGE / "duplicate_merge_plan.json", plan)
    write_json(PACKAGE / "duplicate_merge_dry_run.json", dry_run)

    aggregate = dry_run["aggregate"]
    print(
        "Wrote duplicate reports: "
        f"{aggregate['pairs_tested']} pairs tested, "
        f"{aggregate['pairs_passed']} passed, "
        f"{aggregate['collisions_detected']} UNIQUE collisions detected, "
        f"PostgreSQL {dry_run['postgresql_simulation']['status']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
