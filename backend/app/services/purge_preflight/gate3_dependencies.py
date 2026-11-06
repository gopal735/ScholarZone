"""
Gate 3: Foreign Key and Dependency Inspection

Uses PostgreSQL catalog metadata with correct schema-aware joins.
Inspects ALL foreign keys referencing scholarships.id.

Requirements:
- Correct schema identification
- Correct constraint identification
- Correct column identification
- Correct handling of composite foreign keys
- ON DELETE behavior
- ON UPDATE behavior
- CASCADE detection
- Reference counts for every target ID (per-target)
- Reference counts for every referencing table (aggregate)
- Safe dynamic SQL identifier quoting
- No untrusted string concatenation for table or column names
- Fails closed on any inspection error
- Disposable PostgreSQL tests for single/composite FK cases
"""

import json
import sys
from dataclasses import dataclass, asdict
from typing import Optional

from .manifest import CANONICAL_TARGET_IDS, TARGET_ID_SET
from .database import DatabaseAccessor, create_accessor, ForeignKeyInfo
from .config import DatabaseConfig, PreflightConfig, load_config
from .metadata import save_result_with_metadata


@dataclass
class Gate3Result:
    """Gate 3 execution result."""
    test_name: str = "gate3_dependencies"
    fk_metadata: list[dict] = None
    cascade_fk_count: int = 0
    cascade_details: list[dict] = None
    reference_counts: dict[str, int] = None
    per_target_reference_counts: dict[int, dict[str, int]] = None
    total_references_to_targets: int = 0
    inspection_errors: list[str] = None
    safe_to_delete: bool = False
    status: str = "PENDING"
    error: Optional[str] = None
    # Detailed reporting
    referencing_tables: list[dict] = None
    target_ids_with_references: dict[int, list[str]] = None

    def __post_init__(self):
        if self.fk_metadata is None:
            self.fk_metadata = []
        if self.cascade_details is None:
            self.cascade_details = []
        if self.reference_counts is None:
            self.reference_counts = {}
        if self.per_target_reference_counts is None:
            self.per_target_reference_counts = {}
        if self.inspection_errors is None:
            self.inspection_errors = []
        if self.referencing_tables is None:
            self.referencing_tables = []
        if self.target_ids_with_references is None:
            self.target_ids_with_references = {}

    def to_dict(self) -> dict:
        return asdict(self)


def run_gate3(accessor: DatabaseAccessor, target_ids: list[int]) -> Gate3Result:
    """
    Execute Gate 3: Foreign Key and Dependency Inspection.

    Args:
        accessor: DatabaseAccessor with readonly production connection
        target_ids: List of target IDs to check references for

    Returns:
        Gate3Result with complete FK metadata and reference counts
    """
    result = Gate3Result()

    try:
        with accessor.connect_readonly() as conn:
            # 1. Discover ALL foreign keys referencing scholarships.id
            fk_metadata = accessor.get_all_foreign_keys(conn)
            result.fk_metadata = [
                {
                    "constraint_name": fk.constraint_name,
                    "table_schema": fk.table_schema,
                    "table_name": fk.table_name,
                    "column_names": fk.column_names,
                    "referenced_table_schema": fk.referenced_table_schema,
                    "referenced_table_name": fk.referenced_table_name,
                    "referenced_column_names": fk.referenced_column_names,
                    "on_delete": fk.on_delete_action,
                    "on_update": fk.on_update_action,
                    "is_cascade": fk.is_cascade,
                    "is_composite": fk.is_composite,
                }
                for fk in fk_metadata
            ]

            # 2. Check for CASCADE on any FK to scholarships
            cascade_fks = [fk for fk in fk_metadata if fk.is_cascade]
            result.cascade_fk_count = len(cascade_fks)
            result.cascade_details = [
                {
                    "constraint_name": fk.constraint_name,
                    "table_name": fk.table_name,
                    "column_names": fk.column_names,
                    "on_delete": fk.on_delete_action,
                    "on_update": fk.on_update_action,
                    "is_composite": fk.is_composite,
                }
                for fk in cascade_fks
            ]

            # 3. Count references to target IDs across ALL referencing tables
            # This MUST succeed for all tables - any failure fails the gate
            reference_counts = {}
            total_refs = 0
            inspection_errors = []
            referencing_tables = []
            target_ids_with_references = {tid: [] for tid in target_ids}

            for fk in fk_metadata:
                try:
                    count = accessor.count_references(conn, fk, target_ids)
                    if fk.is_composite:
                        key = f"{fk.table_name}.({','.join(fk.column_names)})"
                    else:
                        key = f"{fk.table_name}.{fk.column_names[0]}"
                    reference_counts[key] = count
                    total_refs += count

                    # Build referencing tables detail
                    referencing_tables.append({
                        "table_name": fk.table_name,
                        "column_names": fk.column_names,
                        "constraint_name": fk.constraint_name,
                        "on_delete": fk.on_delete_action,
                        "on_update": fk.on_update_action,
                        "is_cascade": fk.is_cascade,
                        "is_composite": fk.is_composite,
                        "aggregate_reference_count": count,
                    })

                    # Track per-target references
                    per_target = accessor.count_references_per_target(conn, fk, target_ids)
                    for tid, cnt in per_target.items():
                        if cnt > 0:
                            target_ids_with_references[tid].append(key)

                except Exception as e:
                    if fk.is_composite:
                        key = f"{fk.table_name}.({','.join(fk.column_names)})"
                    else:
                        key = f"{fk.table_name}.{fk.column_names[0]}"
                    error_msg = f"Failed to inspect {key}: {e}"
                    inspection_errors.append(error_msg)
                    # Mark as error - will fail closed
                    reference_counts[key] = -1

            result.reference_counts = reference_counts
            result.total_references_to_targets = total_refs
            result.inspection_errors = inspection_errors
            result.referencing_tables = referencing_tables

            # Remove target IDs with no references for cleaner output
            result.target_ids_with_references = {tid: tables for tid, tables in target_ids_with_references.items() if tables}

            # 4. Per-target reference counts (detailed breakdown)
            try:
                per_target = accessor.count_all_references_per_target(conn, target_ids)
                result.per_target_reference_counts = per_target
            except Exception as e:
                inspection_errors.append(f"Per-target reference count failed: {e}")
                # Will fail closed due to inspection_errors

            # 5. Determine safe_to_delete - STRICT REQUIREMENTS
            # - Complete metadata discovery (no errors)
            # - Successful inspection of all relevant tables
            # - No unknown references (all counts >= 0)
            # - No CASCADE behavior
            # - Zero references to target IDs (aggregate AND per-target)
            # - No inspection errors

            has_inspection_errors = len(inspection_errors) > 0
            has_unknown_references = any(c < 0 for c in reference_counts.values())
            has_cascade = result.cascade_fk_count > 0
            has_references = total_refs > 0

            # Also check per-target: no target should have any references
            has_per_target_refs = False
            if result.per_target_reference_counts:
                for tid, refs in result.per_target_reference_counts.items():
                    if any(count > 0 for count in refs.values()):
                        has_per_target_refs = True
                        break

            result.safe_to_delete = (
                not has_inspection_errors
                and not has_unknown_references
                and not has_cascade
                and not has_references
                and not has_per_target_refs
            )

            if not result.safe_to_delete:
                reasons = []
                if has_inspection_errors:
                    reasons.append(f"{len(inspection_errors)} inspection errors")
                if has_unknown_references:
                    reasons.append("unknown reference counts")
                if has_cascade:
                    reasons.append(f"{result.cascade_fk_count} CASCADE FKs")
                if has_references:
                    reasons.append(f"{total_refs} aggregate references to targets")
                if has_per_target_refs:
                    reasons.append("per-target references found")
                result.status = "FAIL"
                result.error = "Safe to delete: NO - " + "; ".join(reasons)
                return result

            result.status = "PASS"
            return result

    except Exception as e:
        result.status = "ERROR"
        result.error = str(e)
        return result


def main() -> int:
    """CLI entry point for Gate 3."""
    print("=== GATE 3: FOREIGN KEY AND DEPENDENCY INSPECTION ===")
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print(f"Count: {len(CANONICAL_TARGET_IDS)}")
    print()

    try:
        config = load_config(gates_to_run={"gate3"})
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    result = run_gate3(accessor, CANONICAL_TARGET_IDS)

    # Save results with metadata
    save_result_with_metadata(result.to_dict(), "gate3", "gate3_result.json")

    print("\n=== GATE 3 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print("\n✅ GATE 3 PASSED: No CASCADE, zero references, complete inspection")
        return 0
    else:
        print(f"\n❌ GATE 3 {result.status}: {result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())