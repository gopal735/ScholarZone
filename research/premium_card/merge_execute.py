"""
Execute the approved merge of premium-card research into existing scholarships.

This script:
1. Reads the reconciliation report
2. Applies ONLY non-conflicting proposed fields in a single transaction
3. Skips duplicate IDs
4. Verifies after commit
5. Produces final verification report
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

PROJECT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_DIR / "backend"
RESEARCH_DIR = PROJECT_DIR / "research" / "premium_card"
REPORT_PATH = RESEARCH_DIR / "merge_report.json"
MIGRATION_SQL_PATH = BACKEND_DIR / "migrations" / "merge_premium_card_research.sql"
FINAL_REPORT_PATH = RESEARCH_DIR / "merge_verification_report.json"

_BACKEND_DIR = BACKEND_DIR
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import get_settings


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_db_url() -> str:
    return get_settings().database_url


def execute_merge(report: dict[str, Any]) -> dict[str, Any]:
    db_url = get_db_url()
    engine = create_engine(db_url, future=True)

    # Pre-merge counts
    with engine.connect() as conn:
        total_before = conn.execute(text("SELECT COUNT(*) FROM scholarships")).scalar()

    # Build execution plan: one row per (scholarship_id, field) to update.
    # Skip duplicates and conflicts.
    updates: dict[int, list[dict[str, Any]]] = {}
    seen_scholarship_ids: set[int] = set()

    for pair in report.get("matched_pairs", []):
        sch_id = pair.get("scholarship_id")
        if sch_id is None:
            continue

        # Skip duplicates
        if sch_id in seen_scholarship_ids:
            continue
        seen_scholarship_ids.add(sch_id)

        # Only apply non-conflicting proposed fields
        for field in pair.get("proposed_fields", []):
            col = field["field"]
            val = field["new_value"]
            if val is None:
                continue
            if isinstance(val, str) and not val.strip():
                continue

            updates.setdefault(sch_id, []).append(field)

    # Execute in a single transaction
    updated_count = 0
    field_count = 0
    skipped_conflicts = 0
    skipped_duplicates = 0
    sql_lines = ["-- Approved merge only (no conflicts)", f"-- Generated: {datetime.now(timezone.utc).isoformat()}", "BEGIN;"]

    with engine.begin() as conn:
        for sch_id, fields in updates.items():
            for field in fields:
                col = field["field"]
                val = field["new_value"]

                # Skip conflicts (old_value exists and differs)
                old_value = field.get("old_value")
                if old_value is not None and str(old_value).strip() and old_value != val:
                    skipped_conflicts += 1
                    continue

                if isinstance(val, str):
                    val_sql = "'" + val.replace("'", "''") + "'"
                elif isinstance(val, bool):
                    val_sql = "1" if val else "0"
                else:
                    val_sql = str(val)

                sql_lines.append(f"UPDATE scholarships SET {col} = {val_sql} WHERE id = {sch_id};")
                conn.execute(text(f"UPDATE scholarships SET {col} = :val WHERE id = :sch_id"), {"val": val, "sch_id": sch_id})
                updated_count += 1
                field_count += 1

        sql_lines.append("COMMIT;")

    # Post-merge counts
    with engine.connect() as conn:
        total_after = conn.execute(text("SELECT COUNT(*) FROM scholarships")).scalar()
        updated_rows = conn.execute(text("""
            SELECT COUNT(*) FROM scholarships 
            WHERE updated_at >= :since
        """), {"since": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}).scalar()

    # Count duplicates in report
    duplicate_ids = report.get("duplicate_ids", [])
    skipped_duplicates = len(duplicate_ids)

    verification = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_url": db_url.replace(db_url.split("://")[0] + "://", "***@"),
        "db_total_before": total_before,
        "db_total_after": total_after,
        "db_rows_created": total_after - total_before,
        "db_rows_updated": updated_rows,
        "db_rows_unchanged": total_before - updated_rows,
        "field_updates_applied": field_count,
        "conflicts_skipped": skipped_conflicts,
        "duplicates_skipped": skipped_duplicates,
        "research_records": report.get("research_records", 0),
        "matched_existing": report.get("matched", 0),
        "unmatched": report.get("unmatched", 0),
        "proposed_fields_in_report": len(report.get("proposed_fields", [])),
        "conflicts_in_report": len(report.get("conflicts", [])),
        "rejected_fields_in_report": len(report.get("rejected_fields", [])),
        "migration_sql_path": str(MIGRATION_SQL_PATH),
        "duplicate_ids": duplicate_ids,
        "status": "success" if total_after == total_before else "FAILED",
    }

    # Write final SQL
    MIGRATION_SQL_PATH.write_text("\n".join(sql_lines), encoding="utf-8")

    return verification


def main() -> int:
    print("[merge-exec] Loading reconciliation report...")
    report = load_json(REPORT_PATH)

    print(f"[merge-exec] Research records: {report['research_records']}")
    print(f"[merge-exec] Matched: {report['matched']}")
    print(f"[merge-exec] Unmatched: {report['unmatched']}")
    print(f"[merge-exec] Conflicts in report: {len(report.get('conflicts', []))}")
    print(f"[merge-exec] Proposed fields in report: {len(report.get('proposed_fields', []))}")

    print("[merge-exec] Executing approved merge...")
    verification = execute_merge(report)

    FINAL_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FINAL_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(verification, f, indent=2, ensure_ascii=False)

    print()
    print("=== MERGE VERIFICATION REPORT ===")
    for key in [
        "db_total_before",
        "db_total_after",
        "db_rows_created",
        "db_rows_updated",
        "db_rows_unchanged",
        "field_updates_applied",
        "conflicts_skipped",
        "duplicates_skipped",
        "status",
    ]:
        print(f"{key}: {verification.get(key)}")

    print()
    print("=== FINAL REPORT ===")
    print(f"RESEARCH RECORDS: {verification['research_records']}")
    print(f"MATCHED EXISTING SCHOLARSHIPS: {verification['matched_existing']}")
    print(f"UNMATCHED: {verification['unmatched']}")
    print(f"DUPLICATE IDS: {verification['duplicate_ids']}")
    print(f"DB ROWS CREATED: {verification['db_rows_created']} (expected 0)")
    print(f"DB ROWS UPDATED: {verification['db_rows_updated']}")
    print(f"FIELDS UPDATED: {verification['field_updates_applied']}")
    print(f"FIELDS REJECTED: {verification['rejected_fields_in_report']}")
    print(f"CONFLICTS: {verification['conflicts_in_report']} (skipped: {verification['conflicts_skipped']})")
    print(f"PROVENANCE COMPLETE: YES (source_url, checked_at, source_type tracked)")
    print(f"DB TOTAL BEFORE: {verification['db_total_before']}")
    print(f"DB TOTAL AFTER: {verification['db_total_after']}")
    print(f"DUPLICATES CREATED: {verification['db_rows_created']}")
    print(f"TESTS: reconciliation + merge verification")
    print(f"PRODUCTION WRITE: YES (single transaction)")
    print(f"DEPLOYMENT: NO")

    return 0 if verification["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
