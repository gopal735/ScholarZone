"""Semantic validation for the final reconciliation package.

The validator is intentionally independent of the database. It reads the
committed canonical files plus ``package_baseline.json`` and fails closed when
any of the following is wrong:

* unsupported lifecycle status or missing archive fields,
* approved operation without DIRECT evidence,
* PENDING_RESEARCH operation marked approved,
* unsafe URL arrays or URL rewrites in the duplicate plan,
* incomplete FK map or inconsistent FK totals,
* contradictory canonical and legacy files,
* inconsistent projected counts.

Usage:

    python validate_semantics.py             # validate and write the report
    python validate_semantics.py --self-test # mutate copies and prove checks fire
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
BASELINE_DATE = "2026-11-10"
ALLOWED_STATUSES = {"open", "upcoming", "closing-soon", "closed"}
URL_FIELDS = {
    "official_source_url",
    "application_link",
    "official_updates_url",
    "catalogue_url",
}
ARCHIVE_FIELDS = {"is_archived", "archived_at", "archived_reason"}
MODEL_FIELDS_REQUIRED = True

REQUIRED_JSON = [
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
    "final_reconciliation_manifest.json",
    "legacy/import-files/manifest.json",
]

EXPECTED_APPROVED_IDS = {
    "CYCLE-1",
    "CYCLE-3",
    "CYCLE-4",
    "CYCLE-5",
    "CYCLE-23",
    "CYCLE-231",
    "CYCLE-232",
    "CYCLE-234",
    "CYCLE-516",
    "CYCLE-1312",
    "CYCLE-1336",
    "FUND-3",
    "FUND-1",
}
EXPECTED_CYCLE_IDS = {item for item in EXPECTED_APPROVED_IDS if item.startswith("CYCLE-")}
EXPECTED_FUNDING_IDS = {"FUND-3", "FUND-1"}
EXPECTED_CYCLE_CHANGES = {
    "CYCLE-1": {"title": "Erasmus Mundus Joint Masters (EMJM)"},
    "CYCLE-3": {
        "application_period": (
            "Application deadlines are updated annually in the second quarter; "
            "applications are possible between 1 June and the stated application deadline."
        )
    },
    "CYCLE-4": {
        "degree": (
            "Undergraduate Degrees (including Associate Degree), Graduate "
            "Degrees (Master's and Doctoral Degrees)"
        )
    },
    "CYCLE-5": {
        "degree": (
            "Research students, Teacher training students, Undergraduate students, "
            "Japanese studies students, College of technology students, Specialized "
            "training college students, Young Leaders Program (YLP) students"
        )
    },
    "CYCLE-23": {"duration": "12 to 42 months (dependent on study programme)"},
    "CYCLE-231": {
        "title": "Study Scholarships - Postgraduate Studies in the Field of Architecture"
    },
    "CYCLE-232": {
        "title": (
            "Study Scholarships - Postgraduate Studies in the Fields of Fine Art, "
            "Design, Visual Communication and Film"
        )
    },
    "CYCLE-234": {
        "title": (
            "Study Scholarships - Postgraduate Studies in the Field of the Performing Arts"
        )
    },
    "CYCLE-516": {
        "degree": "Undergraduate Degrees (including Associate Degree)"
    },
    "CYCLE-1312": {"title": "Knight-Hennessy Scholars at Stanford University"},
    "CYCLE-1336": {"title": "Huayu Enrichment Scholarship Program"},
}
EXPECTED_FUNDING_CHANGES = {
    "FUND-3": {
        "tuition_coverage": False,
        "fully_funded": False,
        "funding": "Partially Funded (stipend, insurance, travel; tuition not covered)",
    },
    "FUND-1": {
        "fully_funded": True,
        "funding": "Fully Funded (participation costs + travel/visa + living allowance)",
    },
}
EXPECTED_BASELINE = {
    "total": 830,
    "active": 830,
    "archived": 0,
    "status_distribution": {"open": 820, "closed": 6, "closing-soon": 4},
}
EXPECTED_AFTER_APPROVED = (830, 830, 0, {"open": 820, "closed": 6, "closing-soon": 4})
EXPECTED_AFTER_LIFECYCLE = (830, 828, 2, {"open": 818, "closed": 8, "closing-soon": 4})
EXPECTED_AFTER_ALL = (830, 824, 6, {"open": 818, "closed": 8, "closing-soon": 4})
LEGACY_FILES = {
    "existing_cycle_updates.json": "final_existing_cycle_updates.json",
    "funding_corrections.json": "final_funding_corrections.json",
    "import_ready_scholarships.json": "final_import_ready_scholarships.json",
    "import_validation_report.json": "final_import_validation_report.json",
    "discontinued_programmes.json": "final_lifecycle_corrections.json",
    "reconciliation_manifest.json": "final_reconciliation_manifest.json",
    "source_evidence.json": "final_source_evidence.json",
    "duplicate_reconciliation_report.json": "duplicate_merge_plan.json",
}


def add(errors: list[dict], code: str, message: str, path: str | None = None) -> None:
    item = {"code": code, "message": message}
    if path:
        item["path"] = path
    errors.append(item)


def read_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_iso_date(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def is_scalar(value) -> bool:
    return isinstance(value, (str, bool, int, float)) or value is None


def find_forbidden_status(obj, path: str = "") -> list[str]:
    """Return paths where a legacy ``discontinued`` status is used."""
    hits: list[str] = []
    if isinstance(obj, dict):
        if "corrected_status" in obj:
            hits.append(f"{path}.corrected_status")
        for key, value in obj.items():
            if key == "status" and value == "discontinued":
                hits.append(f"{path}.status")
            hits.extend(find_forbidden_status(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(find_forbidden_status(value, f"{path}[{index}]"))
    return hits


def find_url_arrays(obj, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in URL_FIELDS and isinstance(value, (list, dict)):
                hits.append(f"{path}.{key}")
            hits.extend(find_url_arrays(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(find_url_arrays(value, f"{path}[{index}]"))
    return hits


def load_package(package: Path) -> tuple[dict, list[dict]]:
    data: dict = {}
    errors: list[dict] = []
    for name in REQUIRED_JSON:
        path = package / name
        if not path.exists():
            add(errors, "JSON_FILE_MISSING", f"Required file is missing: {name}", name)
            continue
        try:
            data[name] = read_json(path)
        except json.JSONDecodeError as exc:
            add(errors, "JSON_SYNTAX_ERROR", f"Invalid JSON: {exc}", name)
    readme = package / "legacy" / "README.md"
    if readme.exists():
        data["legacy/README.md"] = readme.read_text(encoding="utf-8")
    else:
        add(errors, "LEGACY_README_MISSING", "legacy/README.md is missing")
    return data, errors


def validate(data: dict, package: Path | None = None, check_hashes: bool = True) -> list[dict]:
    errors: list[dict] = []

    baseline = data.get("package_baseline.json")
    if not isinstance(baseline, dict):
        add(errors, "BASELINE_INVALID", "package_baseline.json must be an object")
        baseline = {}
    counts = baseline.get("record_counts", {})
    rows = baseline.get("scholarships", {})
    schema = baseline.get("schema_contract", {})
    model_fields = set(schema.get("scholarship_fields", []))
    allowed_statuses = set(schema.get("status_values", [])) or ALLOWED_STATUSES

    if counts:
        if counts.get("total") != counts.get("active", 0) + counts.get("archived", 0):
            add(errors, "BASELINE_COUNT_MISMATCH", "Baseline total != active + archived")
        if (
            counts.get("total") != EXPECTED_BASELINE["total"]
            or counts.get("active") != EXPECTED_BASELINE["active"]
            or counts.get("archived") != EXPECTED_BASELINE["archived"]
        ):
            add(
                errors,
                "BASELINE_COUNT_MISMATCH",
                f"Baseline counts changed: {counts.get('total')}/"
                f"{counts.get('active')}/{counts.get('archived')}",
            )
        if counts.get("status_distribution") != EXPECTED_BASELINE["status_distribution"]:
            add(
                errors,
                "BASELINE_STATUS_MISMATCH",
                f"Baseline status distribution changed: {counts.get('status_distribution')}",
            )

    # --- canonical insert file -------------------------------------------------
    inserts = data.get("final_import_ready_scholarships.json")
    if not isinstance(inserts, list):
        add(errors, "CANONICAL_INSERTS_INVALID", "Insert file must be a JSON array")
    elif len(inserts) != 0:
        add(
            errors,
            "CANONICAL_INSERTS_NONZERO",
            f"Canonical insert file must be empty; found {len(inserts)} records",
        )

    # --- approved operations and evidence -------------------------------------
    cycle_ops = data.get("final_existing_cycle_updates.json")
    funding_ops = data.get("final_funding_corrections.json")
    evidence = data.get("final_source_evidence.json")
    if not isinstance(cycle_ops, list):
        add(errors, "APPROVED_FILE_INVALID", "Cycle updates must be a JSON array")
        cycle_ops = []
    if not isinstance(funding_ops, list):
        add(errors, "APPROVED_FILE_INVALID", "Funding corrections must be a JSON array")
        funding_ops = []
    if not isinstance(evidence, list):
        add(errors, "EVIDENCE_FILE_INVALID", "Evidence registry must be a JSON array")
        evidence = []

    approved = cycle_ops + funding_ops
    approved_ids = [op.get("operation_id") for op in approved if isinstance(op, dict)]
    if len(cycle_ops) != 11:
        add(errors, "APPROVED_COUNT_MISMATCH", f"Expected 11 cycle updates, found {len(cycle_ops)}")
    if len(funding_ops) != 2:
        add(
            errors,
            "APPROVED_COUNT_MISMATCH",
            f"Expected 2 funding corrections, found {len(funding_ops)}",
        )
    if set(approved_ids) != EXPECTED_APPROVED_IDS:
        add(
            errors,
            "APPROVED_ID_MISMATCH",
            f"Approved operation IDs differ: {sorted(set(approved_ids) ^ EXPECTED_APPROVED_IDS)}",
        )
    if len(approved_ids) != len(set(approved_ids)):
        add(errors, "APPROVED_ID_DUPLICATE", "Approved operation IDs are not unique")

    if len(evidence) != 13:
        add(errors, "EVIDENCE_COUNT_MISMATCH", f"Expected 13 evidence records, found {len(evidence)}")
    evidence_refs = {
        item.get("evidence_ref") for item in evidence if isinstance(item, dict)
    }
    if None in evidence_refs or len(evidence_refs) != len(evidence):
        add(errors, "EVIDENCE_REF_INVALID", "Evidence refs must be non-null and unique")
    evidence_by_ref = {
        item.get("evidence_ref"): item for item in evidence if isinstance(item, dict)
    }

    for op in approved:
        if not isinstance(op, dict):
            add(errors, "APPROVED_OPERATION_INVALID", "Approved operation must be an object")
            continue
        operation_id = op.get("operation_id", "<missing>")
        if op.get("approved_for_import") is not True:
            add(
                errors,
                "APPROVED_OPERATION_NOT_APPROVED",
                f"{operation_id} is not marked approved_for_import",
            )
        if op.get("evidence_status") != "DIRECT":
            add(
                errors,
                "APPROVED_EVIDENCE_NOT_DIRECT",
                f"{operation_id} has evidence_status != DIRECT",
            )
        evidence_ref = op.get("evidence_ref")
        if not evidence_ref or evidence_ref not in evidence_by_ref:
            add(
                errors,
                "APPROVED_EVIDENCE_MISSING",
                f"{operation_id} has no matching DIRECT evidence record",
            )
            continue
        record = evidence_by_ref[evidence_ref]
        if record.get("operation_id") != operation_id:
            add(
                errors,
                "APPROVED_EVIDENCE_MISMATCH",
                f"{operation_id} evidence points at {record.get('operation_id')}",
            )
        if record.get("approved_for_import") is not True:
            add(
                errors,
                "APPROVED_EVIDENCE_NOT_APPROVED",
                f"{operation_id} evidence is not marked approved",
            )
        source_url = record.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith("https://"):
            add(
                errors,
                "EVIDENCE_SOURCE_URL_INVALID",
                f"{operation_id} evidence source_url is not a scalar https URL",
            )
        claim = record.get("exact_supported_claim")
        if not isinstance(claim, str) or len(claim.strip()) < 30:
            add(
                errors,
                "EVIDENCE_CLAIM_MISSING",
                f"{operation_id} lacks an exact supported claim",
            )
        if not is_iso_date(record.get("retrieved_at")):
            add(
                errors,
                "EVIDENCE_DATE_INVALID",
                f"{operation_id} retrieval date is not ISO 8601",
            )

        changes = op.get("changes")
        if not isinstance(changes, list) or not changes:
            add(errors, "APPROVED_CHANGES_MISSING", f"{operation_id} has no changes")
            continue
        changed_fields = []
        for change in changes:
            if not isinstance(change, dict):
                add(errors, "APPROVED_CHANGE_INVALID", f"{operation_id} change is not an object")
                continue
            field = change.get("field")
            changed_fields.append(field)
            if field == "cycle_info":
                add(
                    errors,
                    "UNSUPPORTED_FIELD",
                    f"{operation_id} targets non-existent field cycle_info",
                )
            if field in URL_FIELDS:
                add(
                    errors,
                    "UNSAFE_URL_WRITE",
                    f"{operation_id} writes URL field {field}; URL fields are immutable in this package",
                )
            if model_fields and field not in model_fields:
                add(
                    errors,
                    "UNSUPPORTED_FIELD",
                    f"{operation_id} targets field not present in Scholarship model: {field}",
                )
            if not is_scalar(change.get("after")):
                add(
                    errors,
                    "UNSUPPORTED_FIELD_VALUE",
                    f"{operation_id}.{field} after value is not scalar",
                )
            if change.get("before") == change.get("after"):
                add(
                    errors,
                    "NOOP_CHANGE",
                    f"{operation_id}.{field} before equals after",
                )
        if set(changed_fields) != set(record.get("supports_fields", [])):
            add(
                errors,
                "EVIDENCE_FIELD_MISMATCH",
                f"{operation_id} evidence fields do not match changed fields",
            )
        baseline_row = rows.get(str(op.get("catalogue_id")))
        if baseline_row and op.get("catalogue_official_source_url") != baseline_row.get(
            "official_source_url"
        ):
            add(
                errors,
                "CANONICAL_URL_MISMATCH",
                f"{operation_id} catalogue_official_source_url differs from baseline",
            )
        if op.get("catalogue_id") in {31, 729}:
            add(
                errors,
                "PENDING_MARKED_APPROVED",
                f"{operation_id} targets pending lifecycle record {op.get('catalogue_id')}",
            )

    for operation_id, expected in {**EXPECTED_CYCLE_CHANGES, **EXPECTED_FUNDING_CHANGES}.items():
        op = next((item for item in approved if item.get("operation_id") == operation_id), None)
        if op is None:
            continue
        actual = {change.get("field"): change.get("after") for change in op.get("changes", [])}
        if actual != expected:
            add(
                errors,
                "APPROVED_CHANGE_VALUE_MISMATCH",
                f"{operation_id} changes differ from the reviewed values: {actual}",
            )

    # --- operation evidence mapping -------------------------------------------
    mapping = data.get("operation_evidence_mapping.json")
    if not isinstance(mapping, dict):
        add(errors, "MAPPING_INVALID", "operation_evidence_mapping.json must be an object")
        mapping_ops = []
    else:
        mapping_ops = mapping.get("operations", [])
        if mapping.get("total_operations") != 25:
            add(errors, "MAPPING_COUNT_MISMATCH", "Mapping total_operations must be 25")
        if len(mapping_ops) != 25:
            add(
                errors,
                "MAPPING_COUNT_MISMATCH",
                f"Mapping must contain 25 operations; found {len(mapping_ops)}",
            )
        approved_mapping = [
            op for op in mapping_ops if op.get("approved_for_import") is True
        ]
        pending_mapping = [
            op for op in mapping_ops if op.get("approved_for_import") is False
        ]
        if len(approved_mapping) != 13:
            add(errors, "MAPPING_COUNT_MISMATCH", "Mapping must contain 13 approved operations")
        if len(pending_mapping) != 12:
            add(errors, "MAPPING_COUNT_MISMATCH", "Mapping must contain 12 pending operations")
        if mapping.get("approved_operations") != len(approved_mapping):
            add(errors, "MAPPING_COUNT_MISMATCH", "approved_operations header is inconsistent")
        if mapping.get("pending_operations") != len(pending_mapping):
            add(errors, "MAPPING_COUNT_MISMATCH", "pending_operations header is inconsistent")
        if mapping.get("direct_evidence_operations") != 13:
            add(errors, "MAPPING_COUNT_MISMATCH", "direct_evidence_operations must be 13")
        if mapping.get("pending_research_operations") != 12:
            add(errors, "MAPPING_COUNT_MISMATCH", "pending_research_operations must be 12")
        mapping_approved_ids = {op.get("operation_id") for op in approved_mapping}
        if mapping_approved_ids != EXPECTED_APPROVED_IDS:
            add(errors, "MAPPING_ID_MISMATCH", "Approved mapping IDs differ from approved files")
        for op in mapping_ops:
            if op.get("final_evidence_status") == "PENDING_RESEARCH" and (
                op.get("approved_for_import") is not False
            ):
                add(
                    errors,
                    "PENDING_MARKED_APPROVED",
                    f"{op.get('operation_id')} is PENDING_RESEARCH but marked approved",
                )
        for op in pending_mapping:
            if op.get("final_evidence_status") != "PENDING_RESEARCH":
                add(
                    errors,
                    "PENDING_MARKED_APPROVED",
                    f"{op.get('operation_id')} pending op has non-pending evidence status",
                )
            if op.get("approved_for_import") is not False:
                add(
                    errors,
                    "PENDING_MARKED_APPROVED",
                    f"{op.get('operation_id')} pending op is marked approved",
                )
            if op.get("evidence_ref") is not None:
                add(
                    errors,
                    "PENDING_MARKED_APPROVED",
                    f"{op.get('operation_id')} pending op has an evidence reference",
                )
            if op.get("changes"):
                add(
                    errors,
                    "PENDING_MARKED_APPROVED",
                    f"{op.get('operation_id')} pending op carries approved changes",
                )

    # --- lifecycle proposals ---------------------------------------------------
    lifecycle = data.get("final_lifecycle_corrections.json")
    if not isinstance(lifecycle, dict):
        add(errors, "LIFECYCLE_INVALID", "Lifecycle file must be an object")
        lifecycle_ops = []
    else:
        lifecycle_ops = lifecycle.get("operations", [])
        if lifecycle.get("package_status") != "BLOCKED":
            add(errors, "LIFECYCLE_STATUS_INVALID", "Lifecycle package status must be BLOCKED")
        if lifecycle.get("approval_status") != "NOT_APPROVED_PENDING_RESEARCH":
            add(
                errors,
                "LIFECYCLE_STATUS_INVALID",
                "Lifecycle approval status must be NOT_APPROVED_PENDING_RESEARCH",
            )
        if lifecycle.get("approved_for_import") is not False:
            add(
                errors,
                "PENDING_MARKED_APPROVED",
                "Lifecycle file must not be approved for import",
            )
        if len(lifecycle_ops) != 2:
            add(
                errors,
                "LIFECYCLE_COUNT_MISMATCH",
                f"Expected 2 lifecycle proposals, found {len(lifecycle_ops)}",
            )
        if {op.get("operation_id") for op in lifecycle_ops} != {
            "LIFECYCLE-729",
            "LIFECYCLE-31",
        }:
            add(errors, "LIFECYCLE_ID_MISMATCH", "Lifecycle operation IDs differ")
        for op in lifecycle_ops:
            operation_id = op.get("operation_id", "<missing>")
            proposed = op.get("proposed_fields", {})
            if not isinstance(proposed, dict):
                add(errors, "LIFECYCLE_ARCHIVE_FIELD_MISSING", f"{operation_id} has no proposed_fields")
                continue
            status = proposed.get("status")
            if status not in allowed_statuses or status != "closed":
                add(
                    errors,
                    "LIFECYCLE_STATUS_INVALID",
                    f"{operation_id} proposed status is unsupported: {status!r}",
                )
            if proposed.get("is_archived") is not True:
                add(
                    errors,
                    "LIFECYCLE_ARCHIVE_FIELD_MISSING",
                    f"{operation_id} proposed is_archived must be true",
                )
            reason = proposed.get("archived_reason")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 120:
                add(
                    errors,
                    "LIFECYCLE_ARCHIVE_FIELD_MISSING",
                    f"{operation_id} has no valid archived_reason (max 120 chars)",
                )
            archived_at = proposed.get("archived_at")
            if not (
                isinstance(archived_at, dict)
                and archived_at.get("action") == "PRESERVE_EXISTING"
                and archived_at.get("when_null") == "SET_AT_EXECUTION_TIMESTAMP"
            ):
                add(
                    errors,
                    "LIFECYCLE_ARCHIVE_FIELD_MISSING",
                    f"{operation_id} lacks an explicit archived_at preservation policy",
                )
            if "corrected_status" in op:
                add(
                    errors,
                    "DISCONTINUED_STATUS",
                    f"{operation_id} uses legacy corrected_status",
                )
            if op.get("approved_for_import") is not False:
                add(errors, "PENDING_MARKED_APPROVED", f"{operation_id} is marked approved")
            if op.get("evidence_status") != "PENDING_RESEARCH":
                add(
                    errors,
                    "PENDING_MARKED_APPROVED",
                    f"{operation_id} is not PENDING_RESEARCH",
                )
            if op.get("evidence_ref") is not None:
                add(
                    errors,
                    "PENDING_MARKED_APPROVED",
                    f"{operation_id} has an evidence reference",
                )
            if op.get("archive_instead_of_delete") is not True:
                add(
                    errors,
                    "LIFECYCLE_ARCHIVE_FIELD_MISSING",
                    f"{operation_id} does not guarantee archive-instead-of-delete",
                )
            if op.get("preserve_historical_record") is not True:
                add(
                    errors,
                    "LIFECYCLE_ARCHIVE_FIELD_MISSING",
                    f"{operation_id} does not preserve the historical record",
                )
            if not op.get("blocking_reason"):
                add(
                    errors,
                    "LIFECYCLE_ARCHIVE_FIELD_MISSING",
                    f"{operation_id} has no blocking reason",
                )

    # --- duplicate plan --------------------------------------------------------
    plan = data.get("duplicate_merge_plan.json")
    if not isinstance(plan, dict):
        add(errors, "DUPLICATE_PLAN_INVALID", "Duplicate plan must be an object")
        pairs = []
        plan_summary = {}
    else:
        pairs = plan.get("pairs", [])
        plan_summary = plan.get("summary", {})
        if plan.get("execution_status") != "NOT_EXECUTED":
            add(
                errors,
                "DUPLICATE_PLAN_EXECUTED",
                "Duplicate plan must remain NOT_EXECUTED",
            )
        if plan.get("plans_approved_for_execution") != 0:
            add(
                errors,
                "DUPLICATE_PLAN_APPROVED",
                "No duplicate plan may be approved for execution",
            )
        expected_summary = {
            "total_pairs": 5,
            "merge_ready_for_owner_review": 4,
            "blocked_manual_review": 1,
            "plans_approved_for_execution": 0,
            "plans_executed": 0,
            "duplicate_archives_if_approved": 4,
            "record_deletions": 0,
            "url_writes": 0,
            "funding_writes": 0,
            "fk_reassignments": 0,
            "status_changes": 0,
        }
        for key, expected in expected_summary.items():
            if plan_summary.get(key) != expected:
                add(
                    errors,
                    "DUPLICATE_SUMMARY_MISMATCH",
                    f"Duplicate plan {key} must be {expected!r}, found {plan_summary.get(key)!r}",
                )
        if len(pairs) != 5:
            add(errors, "DUPLICATE_PAIR_COUNT", f"Expected 5 duplicate pairs, found {len(pairs)}")
        classifications = [pair.get("classification") for pair in pairs]
        if classifications.count("MERGE_READY_FOR_OWNER_REVIEW") != 4:
            add(errors, "DUPLICATE_PAIR_COUNT", "Expected 4 merge-ready pairs")
        if classifications.count("BLOCKED_MANUAL_REVIEW") != 1:
            add(errors, "DUPLICATE_PAIR_COUNT", "Expected 1 blocked pair")

        for pair in pairs:
            pair_id = pair.get("pair_id")
            canonical = rows.get(str(pair.get("canonical_id")))
            duplicate = rows.get(str(pair.get("duplicate_id")))
            if not canonical or not duplicate:
                add(
                    errors,
                    "DUPLICATE_ID_MISSING",
                    f"Pair {pair_id} references IDs absent from baseline",
                )
                continue
            for field in URL_FIELDS:
                value = canonical.get(field)
                if isinstance(value, (list, dict)):
                    add(
                        errors,
                        "UNSAFE_URL_ARRAY",
                        f"Pair {pair_id} canonical {field} is an array",
                    )
                value = duplicate.get(field)
                if isinstance(value, (list, dict)):
                    add(
                        errors,
                        "UNSAFE_URL_ARRAY",
                        f"Pair {pair_id} duplicate {field} is an array",
                    )
            if canonical.get("official_source_url") == duplicate.get(
                "official_source_url"
            ):
                add(
                    errors,
                    "DUPLICATE_URL_COLLISION",
                    f"Pair {pair_id} has identical official_source_url values",
                )
            writes = [
                op for op in pair.get("operations", []) if op.get("kind") == "WRITE"
            ]
            for op in pair.get("operations", []):
                sql = op.get("sql", "")
                if not isinstance(sql, str):
                    add(errors, "DUPLICATE_PLAN_INVALID", f"Pair {pair_id} SQL is not text")
                    continue
                lowered = sql.lower()
                if "json_group_array" in lowered or "json_group_object" in lowered:
                    add(
                        errors,
                        "UNSAFE_URL_WRITE",
                        f"Pair {pair_id} uses a JSON aggregate in SQL",
                    )
                if "delete from" in lowered or "insert into" in lowered:
                    add(
                        errors,
                        "UNSAFE_URL_WRITE",
                        f"Pair {pair_id} contains a forbidden DELETE/INSERT",
                    )
                if "official_source_url" in lowered:
                    add(
                        errors,
                        "UNSAFE_URL_WRITE",
                        f"Pair {pair_id} writes official_source_url",
                    )
                for field in ("funding", "degree", "region", "status"):
                    if f"{field} =" in lowered:
                        add(
                            errors,
                            "UNSAFE_URL_WRITE",
                            f"Pair {pair_id} rewrites {field}",
                        )
            if pair.get("classification") == "MERGE_READY_FOR_OWNER_REVIEW":
                if len(writes) != 1:
                    add(
                        errors,
                        "DUPLICATE_PLAN_INVALID",
                        f"Pair {pair_id} must have exactly one write operation",
                    )
                for op in writes:
                    if op.get("operation") != "ARCHIVE_DUPLICATE":
                        add(
                            errors,
                            "DUPLICATE_PLAN_INVALID",
                            f"Pair {pair_id} write operation is not ARCHIVE_DUPLICATE",
                        )
                    if set(op.get("writes_fields", [])) - ARCHIVE_FIELDS:
                        add(
                            errors,
                            "DUPLICATE_PLAN_INVALID",
                            f"Pair {pair_id} writes fields outside the archive contract",
                        )
                    if op.get("expected_rows_affected") != 1:
                        add(
                            errors,
                            "DUPLICATE_PLAN_INVALID",
                            f"Pair {pair_id} must expect exactly one archived row",
                        )
                    if "where id = :duplicate_id and is_archived = 0" not in op.get(
                        "sql", ""
                    ).lower():
                        add(
                            errors,
                            "DUPLICATE_PLAN_INVALID",
                            f"Pair {pair_id} archive SQL lacks the idempotency predicate",
                        )
                    reason = op.get("parameters", {}).get("archived_reason", "")
                    if not isinstance(reason, str) or len(reason) > 120:
                        add(
                            errors,
                            "DUPLICATE_PLAN_INVALID",
                            f"Pair {pair_id} archived_reason exceeds 120 characters",
                        )
                if pair.get("execution", {}).get("status") != "NOT_EXECUTED":
                    add(
                        errors,
                        "DUPLICATE_PLAN_EXECUTED",
                        f"Pair {pair_id} is not marked NOT_EXECUTED",
                    )
                if pair.get("execution", {}).get("approved_for_execution") is not False:
                    add(
                        errors,
                        "DUPLICATE_PLAN_APPROVED",
                        f"Pair {pair_id} must not be approved for execution",
                    )
            elif pair.get("classification") == "BLOCKED_MANUAL_REVIEW":
                if writes:
                    add(
                        errors,
                        "DUPLICATE_PLAN_APPROVED",
                        f"Blocked pair {pair_id} must not contain write operations",
                    )
                if pair.get("canonical_id") != 1217 or pair.get("duplicate_id") != 1309:
                    add(
                        errors,
                        "FULBRIGHT_BLOCK_MISSING",
                        "The blocked pair must be Fulbright IDs 1217/1309",
                    )
            else:
                add(
                    errors,
                    "DUPLICATE_PAIR_COUNT",
                    f"Pair {pair_id} has unknown classification",
                )

        fulbright = plan.get("fulbright_block", {})
        if fulbright.get("duplicate_id") != 1309 or fulbright.get("executable") is not False:
            add(errors, "FULBRIGHT_BLOCK_MISSING", "Fulbright block is missing or executable")

    # --- FK report -------------------------------------------------------------
    fk = data.get("duplicate_fk_dependency_report.json")
    if not isinstance(fk, dict):
        add(errors, "FK_REPORT_INVALID", "FK report must be an object")
        fk_summary = {}
        fk_tables = []
    else:
        fk_summary = fk.get("summary", {})
        fk_tables = fk.get("tables", [])
        baseline_fk = baseline.get("foreign_keys", {}).get("declared_fk_tables", [])
        expected_tables = {(item["table"], item["column"]) for item in baseline_fk}
        actual_tables = {(item.get("table"), item.get("column")) for item in fk_tables}
        if expected_tables != actual_tables:
            add(
                errors,
                "FK_MAP_INCOMPLETE",
                f"FK map differs from schema introspection: {sorted(expected_tables ^ actual_tables)}",
            )
        if len(fk_tables) != 14:
            add(errors, "FK_MAP_INCOMPLETE", f"Expected 14 FK tables, found {len(fk_tables)}")
        if fk_summary.get("declared_dependent_tables") != 14:
            add(errors, "FK_MAP_INCOMPLETE", "declared_dependent_tables must be 14")
        if fk_summary.get("declared_fk_references") != 14:
            add(errors, "FK_TOTAL_MISMATCH", "declared_fk_references must be 14")
        if fk_summary.get("total_pairs") != 5:
            add(errors, "FK_TOTAL_MISMATCH", "FK report total_pairs must be 5")

        recomputed_total = 0
        recomputed_duplicate = 0
        recomputed_merge_ready = 0
        recomputed_fulbright = 0
        collisions_all = 0
        collisions_merge_ready = 0
        pair_ids = {pair.get("pair_id") for pair in pairs}
        for table in fk_tables:
            pair_rows = table.get("reference_rows_by_pair", {})
            total = sum(
                int(entry.get("canonical_rows", 0)) + int(entry.get("duplicate_rows", 0))
                for entry in pair_rows.values()
            )
            if total != table.get("reference_rows_total"):
                add(
                    errors,
                    "FK_TOTAL_MISMATCH",
                    f"{table.get('table')} row total does not match pair breakdown",
                )
            recomputed_total += total
            duplicate_rows = sum(
                int(entry.get("duplicate_rows", 0)) for entry in pair_rows.values()
            )
            if duplicate_rows != table.get("duplicate_side_rows"):
                add(
                    errors,
                    "FK_TOTAL_MISMATCH",
                    f"{table.get('table')} duplicate-side total is inconsistent",
                )
            recomputed_duplicate += duplicate_rows
            for pair_id, entry in pair_rows.items():
                if pair_id not in {str(item) for item in pair_ids}:
                    add(errors, "FK_MAP_INCOMPLETE", f"Unknown pair id {pair_id} in FK map")
                if int(entry.get("canonical_rows", 0)) and int(
                    entry.get("duplicate_rows", 0)
                ):
                    collisions_all += 1
                    pair = next(
                        (item for item in pairs if str(item.get("pair_id")) == pair_id),
                        None,
                    )
                    if pair and pair.get("classification") == "MERGE_READY_FOR_OWNER_REVIEW":
                        collisions_merge_ready += 1
                    if table.get("table") == "scholarship_supervisor_coverage":
                        constraints = table.get("unique_constraints", [])
                        if not any(
                            item.get("columns") == ["scholarship_id"]
                            for item in constraints
                        ):
                            add(
                                errors,
                                "FK_UNIQUE_CONSTRAINT_MISSING",
                                "Coverage table lacks UNIQUE(scholarship_id)",
                            )
        for pair in pairs:
            pair_id = pair.get("pair_id")
            duplicate_id = str(pair.get("duplicate_id"))
            duplicate_rows = sum(
                int(
                    table.get("reference_rows_by_pair", {})
                    .get(str(pair_id), {})
                    .get("duplicate_rows", 0)
                )
                for table in fk_tables
            )
            if duplicate_rows != pair.get("fk_handling", {}).get(
                "preserved_duplicate_side_rows"
            ):
                add(
                    errors,
                    "FK_TOTAL_MISMATCH",
                    f"Pair {pair_id} FK handling does not match FK report",
                )
            if pair.get("classification") == "MERGE_READY_FOR_OWNER_REVIEW":
                recomputed_merge_ready += duplicate_rows
            else:
                recomputed_fulbright += duplicate_rows
        if recomputed_total != fk_summary.get("total_fk_reference_rows_for_pair_ids"):
            add(errors, "FK_TOTAL_MISMATCH", "Total FK reference rows do not sum to summary")
        if recomputed_duplicate != fk_summary.get("duplicate_side_fk_rows"):
            add(errors, "FK_TOTAL_MISMATCH", "Duplicate-side FK rows do not sum to summary")
        if recomputed_merge_ready != fk_summary.get(
            "merge_ready_duplicate_side_fk_rows"
        ):
            add(
                errors,
                "FK_TOTAL_MISMATCH",
                "Merge-ready duplicate-side FK rows do not sum to summary",
            )
        if recomputed_fulbright != fk_summary.get("fulbright_duplicate_side_fk_rows"):
            add(
                errors,
                "FK_TOTAL_MISMATCH",
                "Fulbright duplicate-side FK rows do not sum to summary",
            )
        if collisions_merge_ready != fk_summary.get(
            "unique_collisions_if_merge_ready_reassigned"
        ):
            add(
                errors,
                "FK_TOTAL_MISMATCH",
                "Merge-ready collision count does not match summary",
            )
        if collisions_all != fk_summary.get("unique_collisions_if_all_pairs_reassigned"):
            add(
                errors,
                "FK_TOTAL_MISMATCH",
                "All-pair collision count does not match summary",
            )
        if fk_summary.get("safe_reassignments") != 0:
            add(errors, "FK_TOTAL_MISMATCH", "safe_reassignments must be 0")
        if fk_summary.get("rows_to_reassign") != 0:
            add(errors, "FK_TOTAL_MISMATCH", "rows_to_reassign must be 0")
        append_only = fk.get("append_only_non_fk_tables", [])
        if len(append_only) != 1 or append_only[0].get("table") != "scholarship_image_audit":
            add(errors, "FK_MAP_INCOMPLETE", "Append-only image audit table is missing")
        elif append_only[0].get("reference_rows_total") != 1:
            add(errors, "FK_TOTAL_MISMATCH", "Image audit row count must be 1")

    # --- dry run ---------------------------------------------------------------
    dry = data.get("duplicate_merge_dry_run.json")
    if not isinstance(dry, dict):
        add(errors, "DRY_RUN_INVALID", "Dry run must be an object")
        dry_aggregate = {}
    else:
        dry_aggregate = dry.get("aggregate", {})
        if dry.get("mode") != "ISOLATED_SQLITE_COPY":
            add(errors, "DRY_RUN_INVALID", "Dry run must use an isolated SQLite copy")
        if dry.get("source_database_sha256") != baseline.get("database_sha256"):
            add(errors, "DRY_RUN_SOURCE_MISMATCH", "Dry run source SHA differs from baseline")
        if dry.get("source_database_unchanged") is not True:
            add(errors, "DRY_RUN_SOURCE_CHANGED", "Source database changed during dry run")
        tested = dry.get("pairs_tested", [])
        if len(tested) != 4:
            add(errors, "DRY_RUN_INVALID", f"Expected 4 dry-run pairs, found {len(tested)}")
        for item in tested:
            if item.get("result") != "PASS":
                add(errors, "DRY_RUN_FAILED", f"Pair {item.get('pair_id')} dry run failed")
            if item.get("rows_affected") != 1:
                add(errors, "DRY_RUN_INVALID", f"Pair {item.get('pair_id')} did not archive 1 row")
            if not all(item.get("checks", {}).values()):
                add(
                    errors,
                    "DRY_RUN_FAILED",
                    f"Pair {item.get('pair_id')} has failing checks",
                )
        collisions = dry.get("uniqueness_collision_tests", [])
        if len(collisions) != 4:
            add(errors, "DRY_RUN_INVALID", "Expected 4 uniqueness collision probes")
        for item in collisions:
            if item.get("actual_result") != "UNIQUE_COLLISION":
                add(
                    errors,
                    "DRY_RUN_FAILED",
                    f"Pair {item.get('pair_id')} collision probe did not collide",
                )
            if item.get("rows_reassigned") != 0:
                add(errors, "DRY_RUN_INVALID", "Collision probe reassigned rows")
        expected_aggregate = {
            "pairs_tested": 4,
            "pairs_passed": 4,
            "pairs_failed": 0,
            "pairs_archived": 4,
            "collisions_detected": 4,
            "total_before": 830,
            "active_before": 830,
            "archived_before": 0,
            "total_after": 830,
            "active_after": 826,
            "archived_after": 4,
            "coverage_rows_before": 830,
            "coverage_rows_after": 830,
            "official_source_url_arrays_before": 0,
            "official_source_url_arrays_after": 0,
            "pair_urls_non_null": 10,
            "pair_urls_distinct": 10,
            "rows_deleted": 0,
            "url_writes": 0,
            "funding_writes": 0,
            "degree_writes": 0,
            "region_writes": 0,
            "status_changes": 0,
            "fk_rows_reassigned": 0,
        }
        for key, expected in expected_aggregate.items():
            if dry_aggregate.get(key) != expected:
                add(
                    errors,
                    "DRY_RUN_INVALID",
                    f"Dry-run aggregate {key} must be {expected!r}, found {dry_aggregate.get(key)!r}",
                )
        if dry_aggregate.get("status_distribution_before") != EXPECTED_BASELINE[
            "status_distribution"
        ]:
            add(errors, "DRY_RUN_INVALID", "Dry-run pre-status distribution changed")
        if dry_aggregate.get("status_distribution_after") != EXPECTED_BASELINE[
            "status_distribution"
        ]:
            add(errors, "DRY_RUN_INVALID", "Duplicate archives changed status distribution")
        postgres = dry.get("postgresql_simulation", {})
        if postgres.get("status") not in {"UNAVAILABLE", "PASS"}:
            add(errors, "DRY_RUN_INVALID", "PostgreSQL simulation status is invalid")
        if postgres.get("status") == "PASS" and not postgres.get("evidence"):
            add(errors, "DRY_RUN_INVALID", "PostgreSQL PASS lacks run evidence")
        if postgres.get("status") == "UNAVAILABLE" and not postgres.get("reason"):
            add(errors, "DRY_RUN_INVALID", "PostgreSQL UNAVAILABLE lacks a reason")
        state = dry.get("database_state_after_dry_run", {})
        if state.get("total") != 830 or state.get("active") != 826 or state.get("archived") != 4:
            add(errors, "DRY_RUN_INVALID", "Post-dry-run state is inconsistent")
        if state.get("merges_executed_in_source_database") != 0:
            add(errors, "DRY_RUN_INVALID", "Dry run must not execute in the source database")

    # --- count reconciliation --------------------------------------------------
    db = data.get("final_database_reconciliation.json")
    if not isinstance(db, dict):
        add(errors, "RECONCILIATION_INVALID", "Database reconciliation must be an object")
        projected = {}
    else:
        baseline_block = db.get("baseline", {})
        if (
            baseline_block.get("total") != EXPECTED_BASELINE["total"]
            or baseline_block.get("active") != EXPECTED_BASELINE["active"]
            or baseline_block.get("archived") != EXPECTED_BASELINE["archived"]
        ):
            add(errors, "PROJECTED_COUNT_MISMATCH", "Reconciliation baseline counts changed")
        expected_approved = {
            "new_inserts": 0,
            "cycle_updates": 11,
            "funding_corrections": 2,
            "lifecycle_corrections": 0,
            "total": 13,
        }
        if db.get("approved_operations") != expected_approved:
            add(
                errors,
                "PROJECTED_COUNT_MISMATCH",
                f"Approved operation counts changed: {db.get('approved_operations')}",
            )
        expected_pending = {
            "cycle_updates": 7,
            "funding_corrections": 3,
            "lifecycle_corrections": 2,
            "total": 12,
        }
        if db.get("excluded_pending_operations") != expected_pending:
            add(
                errors,
                "PROJECTED_COUNT_MISMATCH",
                f"Pending operation counts changed: {db.get('excluded_pending_operations')}",
            )
        duplicate_block = db.get("duplicate_reconciliation", {})
        if (
            duplicate_block.get("pairs") != 5
            or duplicate_block.get("merge_ready_for_owner_review") != 4
            or duplicate_block.get("blocked_manual_review") != 1
            or duplicate_block.get("plans_approved_for_execution") != 0
            or duplicate_block.get("plans_executed") != 0
            or duplicate_block.get("archive_only_plans") != 4
            or duplicate_block.get("duplicate_archives_if_approved") != 4
            or duplicate_block.get("record_deletions") != 0
        ):
            add(
                errors,
                "PROJECTED_COUNT_MISMATCH",
                "Duplicate reconciliation counts changed",
            )
        if duplicate_block.get("fk_rows_reassigned_in_plan") != fk_summary.get(
            "rows_to_reassign"
        ):
            add(errors, "FK_TOTAL_MISMATCH", "Reconciliation FK reassignment count differs")
        if duplicate_block.get("duplicate_side_fk_rows_all_pairs") != fk_summary.get(
            "duplicate_side_fk_rows"
        ):
            add(errors, "FK_TOTAL_MISMATCH", "Reconciliation duplicate-side FK count differs")
        lifecycle_block = db.get("lifecycle_proposals", {})
        if lifecycle_block.get("proposed_archives") != 2:
            add(errors, "PROJECTED_COUNT_MISMATCH", "Lifecycle archive count must be 2")
        if lifecycle_block.get("approved_archives") != 0:
            add(errors, "PROJECTED_COUNT_MISMATCH", "Lifecycle approved archive count must be 0")
        projected = db.get("projected_states", {})
        expected_states = {
            "after_approved_subset": EXPECTED_AFTER_APPROVED,
            "after_approved_plus_lifecycle_proposals": EXPECTED_AFTER_LIFECYCLE,
            "after_approved_plus_lifecycle_plus_4_duplicate_archives": EXPECTED_AFTER_ALL,
        }
        for name, expected in expected_states.items():
            state = projected.get(name, {})
            total, active, archived, distribution = expected
            actual = (
                state.get("total"),
                state.get("active"),
                state.get("archived"),
                state.get("status_distribution"),
            )
            if actual != expected:
                add(
                    errors,
                    "PROJECTED_COUNT_MISMATCH",
                    f"{name} must be total={total}, active={active}, archived={archived}, "
                    f"statuses={distribution}; found {actual}",
                )
            if state.get("total") != state.get("active", 0) + state.get("archived", 0):
                add(
                    errors,
                    "PROJECTED_COUNT_MISMATCH",
                    f"{name} total != active + archived",
                )
        accounting = db.get("archive_accounting", {})
        if (
            accounting.get("lifecycle_archives") != 2
            or accounting.get("duplicate_archives") != 4
            or accounting.get("total_archives") != 6
            or accounting.get("total_equals_active_plus_archived") is not True
            or accounting.get("no_double_counting") is not True
        ):
            add(errors, "PROJECTED_COUNT_MISMATCH", "Archive accounting is inconsistent")
        fk_block = db.get("fk_reconciliation", {})
        if (
            fk_block.get("declared_fk_tables") != 14
            or fk_block.get("declared_fk_references") != 14
            or fk_block.get("append_only_non_fk_tables") != 1
            or fk_block.get("total_fk_reference_rows_for_pair_ids") != 10
            or fk_block.get("duplicate_side_fk_rows") != 5
            or fk_block.get("safe_reassignments") != 0
            or fk_block.get("rows_reassigned_in_plan") != 0
            or fk_block.get("collisions_in_plan") != 0
        ):
            add(errors, "FK_TOTAL_MISMATCH", "Reconciliation FK totals are inconsistent")
        if not all(db.get("validation", {}).values()):
            add(errors, "PROJECTED_COUNT_MISMATCH", "Reconciliation validation flags are not all true")

    # --- manifest --------------------------------------------------------------
    manifest = data.get("final_reconciliation_manifest.json")
    if not isinstance(manifest, dict):
        add(errors, "MANIFEST_INVALID", "Manifest must be an object")
    else:
        if manifest.get("package_status") != "BLOCKED":
            add(errors, "MANIFEST_INVALID", "Manifest package_status must be BLOCKED")
        if manifest.get("review_package_only") is not True:
            add(errors, "MANIFEST_INVALID", "Manifest must be review-package only")
        if manifest.get("production_import_authorized") is not False:
            add(errors, "MANIFEST_INVALID", "Manifest must not authorize production import")
        if manifest.get("branch") != "feat/final-scholarship-catalogue-reconciliation":
            add(errors, "MANIFEST_INVALID", "Manifest branch is wrong")
        if manifest.get("base_sha") != "5b28ceef0480a4bd6612d1cf08c26e8629bea285":
            add(errors, "MANIFEST_INVALID", "Manifest base SHA is wrong")
        if manifest.get("pre_remediation_head") != "dec6dbcd65ffe98da42f0e6fff665c3c840ce04a":
            add(errors, "MANIFEST_INVALID", "Manifest pre-remediation SHA is wrong")
        expected_counts = {
            "new_inserts": 0,
            "cycle_updates": 11,
            "funding_corrections": 2,
            "lifecycle_corrections_approved": 0,
            "lifecycle_corrections_pending": 2,
            "total_approved": 13,
            "total_pending_excluded": 12,
        }
        if manifest.get("operation_counts") != expected_counts:
            add(errors, "MANIFEST_COUNT_MISMATCH", "Manifest operation counts are wrong")
        expected_file_counts = {
            "final_import_ready_scholarships.json": 0,
            "final_existing_cycle_updates.json": 11,
            "final_funding_corrections.json": 2,
            "final_lifecycle_corrections.json": 2,
            "final_source_evidence.json": 13,
            "operation_evidence_mapping.json": 25,
            "blocked_records.json": 6,
            "duplicate_merge_plan.json": 5,
            "duplicate_fk_dependency_report.json": 14,
            "duplicate_merge_dry_run.json": 4,
            "final_database_reconciliation.json": 1,
        }
        canonical_files = manifest.get("canonical_files", {})
        for name, expected in expected_file_counts.items():
            if canonical_files.get(name, {}).get("records") != expected:
                add(
                    errors,
                    "MANIFEST_COUNT_MISMATCH",
                    f"Manifest record count for {name} must be {expected}",
                )
        if manifest.get("blocked_new_insert_candidates") != 6:
            add(errors, "MANIFEST_COUNT_MISMATCH", "Manifest blocked candidate count must be 6")
        if manifest.get("duplicate_plan", {}).get("total_pairs") != 5:
            add(errors, "MANIFEST_COUNT_MISMATCH", "Manifest duplicate pair count must be 5")
        if manifest.get("duplicate_plan", {}).get("merge_ready_for_owner_review") != 4:
            add(errors, "MANIFEST_COUNT_MISMATCH", "Manifest merge-ready count must be 4")
        if manifest.get("duplicate_plan", {}).get("blocked_manual_review") != 1:
            add(errors, "MANIFEST_COUNT_MISMATCH", "Manifest blocked pair count must be 1")
        if check_hashes and package is not None:
            for name, expected in manifest.get("hashed_files", {}).items():
                path = package / name
                if not path.exists():
                    add(errors, "MANIFEST_HASH_MISMATCH", f"Hashed file is missing: {name}")
                    continue
                if file_sha256(path) != expected:
                    add(errors, "MANIFEST_HASH_MISMATCH", f"Hash mismatch for {name}")

    # --- blocked records -------------------------------------------------------
    blocked = data.get("blocked_records.json")
    if not isinstance(blocked, list) or len(blocked) != 6:
        add(errors, "BLOCKED_RECORD_COUNT", "blocked_records.json must contain 6 records")
    else:
        for record in blocked:
            if record.get("approved_for_import") is not False:
                add(errors, "PENDING_MARKED_APPROVED", "Blocked record is marked approved")
            if record.get("final_evidence_status") != "BLOCKED":
                add(errors, "PENDING_MARKED_APPROVED", "Blocked record is not marked BLOCKED")

    # --- legacy archive --------------------------------------------------------
    legacy = data.get("legacy/import-files/manifest.json")
    legacy_readme = data.get("legacy/README.md", "")
    if not isinstance(legacy, dict):
        add(errors, "LEGACY_MANIFEST_INVALID", "Legacy manifest must be an object")
    else:
        if legacy.get("importable") is not False:
            add(errors, "LEGACY_CONTRADICTION", "Legacy archive must be non-importable")
        entries = legacy.get("files", [])
        if len(entries) != len(LEGACY_FILES):
            add(
                errors,
                "LEGACY_CONTRADICTION",
                f"Legacy manifest must list {len(LEGACY_FILES)} files; found {len(entries)}",
            )
        seen = set()
        for entry in entries:
            filename = entry.get("filename")
            seen.add(filename)
            expected_replacement = LEGACY_FILES.get(filename)
            if expected_replacement is None:
                add(errors, "LEGACY_CONTRADICTION", f"Unknown legacy file: {filename}")
                continue
            if entry.get("status") != "SUPERSEDED":
                add(
                    errors,
                    "LEGACY_CONTRADICTION",
                    f"{filename} is not marked SUPERSEDED",
                )
            if entry.get("importable") is not False:
                add(
                    errors,
                    "LEGACY_CONTRADICTION",
                    f"{filename} is marked importable",
                )
            if entry.get("superseded_by") != expected_replacement:
                add(
                    errors,
                    "LEGACY_CONTRADICTION",
                    f"{filename} does not point to {expected_replacement}",
                )
            if entry.get("superseded_by") == filename:
                add(
                    errors,
                    "LEGACY_CONTRADICTION",
                    f"{filename} supersedes itself",
                )
            if not entry.get("reason"):
                add(errors, "LEGACY_CONTRADICTION", f"{filename} has no superseded reason")
        if seen != set(LEGACY_FILES):
            add(
                errors,
                "LEGACY_CONTRADICTION",
                f"Legacy manifest file set differs: {sorted(seen ^ set(LEGACY_FILES))}",
            )
        if package is not None:
            for filename in LEGACY_FILES:
                if (package / filename).exists():
                    add(
                        errors,
                        "LEGACY_FILE_AT_ROOT",
                        f"Superseded file still exists at package root: {filename}",
                    )
                if not (package / "legacy" / "import-files" / filename).exists():
                    add(
                        errors,
                        "LEGACY_CONTRADICTION",
                        f"Legacy file is missing: {filename}",
                    )
        if "superseded" not in legacy_readme.lower() or "not importable" not in legacy_readme.lower():
            add(
                errors,
                "LEGACY_CONTRADICTION",
                "legacy/README.md must state SUPERSEDED and not importable",
            )

    # --- global status and URL safety -----------------------------------------
    canonical_keys = [
        "final_existing_cycle_updates.json",
        "final_funding_corrections.json",
        "final_lifecycle_corrections.json",
        "final_source_evidence.json",
        "operation_evidence_mapping.json",
        "duplicate_merge_plan.json",
        "duplicate_fk_dependency_report.json",
        "duplicate_merge_dry_run.json",
        "final_database_reconciliation.json",
        "final_reconciliation_manifest.json",
    ]
    for key in canonical_keys:
        obj = data.get(key)
        if obj is None:
            continue
        for hit in find_forbidden_status(obj, key):
            add(errors, "DISCONTINUED_STATUS", f"Legacy discontinued status at {hit}")
        for hit in find_url_arrays(obj, key):
            add(errors, "UNSAFE_URL_ARRAY", f"URL field is an array at {hit}")
        serialized = json.dumps(obj, ensure_ascii=False)
        if "json_group_array(" in serialized:
            add(errors, "UNSAFE_URL_WRITE", f"json_group_array found in {key}")

    return errors


def validate_package(package: Path) -> dict:
    data, load_errors = load_package(package)
    errors = list(load_errors)
    try:
        errors.extend(validate(data, package, check_hashes=True))
    except Exception as exc:  # pragma: no cover - defensive guard
        add(
            errors,
            "VALIDATOR_EXCEPTION",
            f"{type(exc).__name__}: {exc}",
        )
    data_names = sorted(data)
    report = {
        "validation_timestamp": BASELINE_DATE,
        "validator_version": "2.0",
        "package_status": "BLOCKED",
        "review_package_only": True,
        "production_import_authorized": False,
        "semantic_validation": "PASS" if not errors else "FAIL",
        "json_files_loaded": len(data_names),
        "json_files": data_names,
        "operation_counts": {
            "approved_direct": 13,
            "pending_research_excluded": 12,
            "blocked_insert_candidates": 6,
            "duplicate_pairs": 5,
            "duplicate_merge_ready": 4,
            "duplicate_blocked": 1,
        },
        "counts": {
            "baseline": EXPECTED_BASELINE,
            "after_approved_subset": {
                "total": EXPECTED_AFTER_APPROVED[0],
                "active": EXPECTED_AFTER_APPROVED[1],
                "archived": EXPECTED_AFTER_APPROVED[2],
            },
            "after_lifecycle_proposals": {
                "total": EXPECTED_AFTER_LIFECYCLE[0],
                "active": EXPECTED_AFTER_LIFECYCLE[1],
                "archived": EXPECTED_AFTER_LIFECYCLE[2],
            },
            "after_all_proposed": {
                "total": EXPECTED_AFTER_ALL[0],
                "active": EXPECTED_AFTER_ALL[1],
                "archived": EXPECTED_AFTER_ALL[2],
            },
        },
        "environment": {
            "postgresql_simulation": data.get("duplicate_merge_dry_run.json", {})
            .get("postgresql_simulation", {})
            .get("status", "UNKNOWN"),
            "duplicate_plans_executed": 0,
        },
        "blocking_reasons": [
            "Vanier CGS and NFP/OTS lifecycle proposals remain PENDING_RESEARCH.",
            "PostgreSQL duplicate-merge simulation is unavailable in this environment.",
            "No duplicate merge has been executed; 4 archive-only plans await owner approval.",
            "6 new-insert candidates remain blocked.",
            "This package is a review package, not production import authorization.",
        ],
        "errors": errors,
        "error_count": len(errors),
    }
    return report


def run_self_test(package: Path = PACKAGE) -> list[dict]:
    data, load_errors = load_package(package)
    if load_errors:
        raise RuntimeError(f"Self-test could not load the package: {load_errors}")
    baseline_errors = validate(data, package, check_hashes=False)
    if baseline_errors:
        raise RuntimeError(f"Self-test baseline is not valid: {baseline_errors}")

    mutations = [
        (
            "lifecycle_status_unsupported",
            lambda d: d["final_lifecycle_corrections.json"]["operations"][0][
                "proposed_fields"
            ].__setitem__("status", "discontinued"),
            "LIFECYCLE_STATUS_INVALID",
        ),
        (
            "lifecycle_missing_archived_reason",
            lambda d: d["final_lifecycle_corrections.json"]["operations"][0][
                "proposed_fields"
            ].pop("archived_reason"),
            "LIFECYCLE_ARCHIVE_FIELD_MISSING",
        ),
        (
            "lifecycle_missing_archived_at_policy",
            lambda d: d["final_lifecycle_corrections.json"]["operations"][1][
                "proposed_fields"
            ].pop("archived_at"),
            "LIFECYCLE_ARCHIVE_FIELD_MISSING",
        ),
        (
            "approved_operation_missing_direct_evidence",
            lambda d: d["final_existing_cycle_updates.json"][0].__setitem__(
                "evidence_ref", "EV-MISSING"
            ),
            "APPROVED_EVIDENCE_MISSING",
        ),
        (
            "pending_marked_approved",
            lambda d: next(
                op
                for op in d["operation_evidence_mapping.json"]["operations"]
                if op["approved_for_import"] is False
            ).__setitem__("approved_for_import", True),
            "PENDING_MARKED_APPROVED",
        ),
        (
            "unsafe_url_array_write",
            lambda d: next(
                op
                for op in d["duplicate_merge_plan.json"]["pairs"][0]["operations"]
                if op["operation"] == "ARCHIVE_DUPLICATE"
            ).__setitem__(
                "sql",
                "UPDATE scholarships SET official_source_url = "
                "json_group_array(official_source_url) WHERE id = :duplicate_id",
            ),
            "UNSAFE_URL_WRITE",
        ),
        (
            "incomplete_fk_map",
            lambda d: d["duplicate_fk_dependency_report.json"]["tables"].pop(),
            "FK_MAP_INCOMPLETE",
        ),
        (
            "inconsistent_fk_total",
            lambda d: d["duplicate_fk_dependency_report.json"]["summary"].__setitem__(
                "total_fk_reference_rows_for_pair_ids",
                d["duplicate_fk_dependency_report.json"]["summary"][
                    "total_fk_reference_rows_for_pair_ids"
                ]
                + 1,
            ),
            "FK_TOTAL_MISMATCH",
        ),
        (
            "legacy_marked_importable",
            lambda d: d["legacy/import-files/manifest.json"]["files"][0].__setitem__(
                "importable", True
            ),
            "LEGACY_CONTRADICTION",
        ),
        (
            "projected_count_mismatch",
            lambda d: d["final_database_reconciliation.json"]["projected_states"][
                "after_approved_plus_lifecycle_plus_4_duplicate_archives"
            ].__setitem__("active", 825),
            "PROJECTED_COUNT_MISMATCH",
        ),
    ]

    results = []
    for name, mutate, expected_code in mutations:
        mutated = copy.deepcopy(data)
        try:
            mutate(mutated)
            mutated_errors = validate(mutated, package, check_hashes=False)
            codes = {error["code"] for error in mutated_errors}
            caught = expected_code in codes
            actual_codes = sorted(codes)
        except Exception as exc:  # pragma: no cover - defensive guard
            caught = False
            actual_codes = [f"EXCEPTION:{type(exc).__name__}:{exc}"]
        results.append(
            {
                "mutation": name,
                "expected_error": expected_code,
                "caught": caught,
                "actual_codes": actual_codes,
            }
        )
    return results


def write_validation_report(report: dict, package: Path = PACKAGE) -> None:
    path = package / "final_import_validation_report.json"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Mutate in-memory copies and verify each forbidden condition is caught.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Validate without writing final_import_validation_report.json.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        results = run_self_test(PACKAGE)
        failures = [item for item in results if not item["caught"]]
        print(json.dumps(results, indent=2, ensure_ascii=False))
        if failures:
            print(
                f"SELF-TEST FAILED: {len(failures)} mutation(s) were not caught.",
                file=sys.stderr,
            )
            return 1
        print(f"SELF-TEST PASSED: {len(results)} mutation checks caught.")
        return 0

    report = validate_package(PACKAGE)
    if not args.no_report:
        write_validation_report(report)
    print(
        json.dumps(
            {
                "semantic_validation": report["semantic_validation"],
                "error_count": report["error_count"],
                "package_status": report["package_status"],
                "postgresql_simulation": report["environment"][
                    "postgresql_simulation"
                ],
            },
            indent=2,
        )
    )
    return 0 if report["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
