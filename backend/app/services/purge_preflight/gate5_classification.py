"""
Gate 5: Target Classification Validation

Validates all 34 IDs against the canonical manifest.
Verifies exact category membership.
Rejects duplicates, missing IDs, unsupported classifications.
Requires evidence-based classification for each record.

Categories:
- CLOSED: 18 records - application cycle definitively ended
- CLOSING_SOON: 16 records - cycle ending or recently ended
- EVERGREEN: No deadline - CANNOT purge
- UNKNOWN: Insufficient data - CANNOT purge
- BLOCKED: Explicitly blocked - CANNOT purge
- STATUS_DEADLINE_CONFLICT: Past deadline but open status - REQUIRES REVIEW

IMPORTANT: EXPECTED_CLASSIFICATIONS is a REFERENCE MANIFEST only.
Gate 5 compares actual live record data against this reference and reports mismatches explicitly.
NEVER uses EXPECTED_CLASSIFICATIONS as hardcoded truth or sole authorization for purge.
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional

from .manifest import (
    CANONICAL_TARGET_IDS,
    TARGET_ID_SET,
    ClassificationCategory,
    EXPECTED_CLASSIFICATIONS,
    validate_classifications,
    MismatchDetail,
    ClassificationValidationResult,
)
from .database import DatabaseAccessor, create_accessor
from .config import DatabaseConfig, PreflightConfig, load_config
from .metadata import save_result_with_metadata


@dataclass
class Gate5Result:
    """Gate 5 execution result."""
    test_name: str = "gate5_classification"
    total_ids: int = 34
    verified_ids: int = 0
    closed_count: int = 0
    closing_soon_count: int = 0
    evergreen_count: int = 0
    unknown_count: int = 0
    blocked_count: int = 0
    status_deadline_conflict_count: int = 0
    duplicate_ids: list[int] = None
    missing_ids: list[int] = None
    unexpected_ids: list[int] = None
    classification_errors: list[str] = None
    status: str = "PENDING"
    error: Optional[str] = None
    # Detailed per-record classification
    record_classifications: list[dict] = None
    # Archive state tracking
    archived_count: int = 0
    unarchived_count: int = 0
    # NEW: Explicit mismatch reporting
    mismatches: list[dict] = None
    missing_from_db: list[int] = None
    unexpected_in_db: list[int] = None
    category_breakdown: dict = None
    reconciliation_verified: bool = False

    def __post_init__(self):
        if self.duplicate_ids is None:
            self.duplicate_ids = []
        if self.missing_ids is None:
            self.missing_ids = []
        if self.unexpected_ids is None:
            self.unexpected_ids = []
        if self.classification_errors is None:
            self.classification_errors = []
        if self.record_classifications is None:
            self.record_classifications = []
        if self.mismatches is None:
            self.mismatches = []
        if self.missing_from_db is None:
            self.missing_from_db = []
        if self.unexpected_in_db is None:
            self.unexpected_in_db = []
        if self.category_breakdown is None:
            self.category_breakdown = {}

    def to_dict(self) -> dict:
        return asdict(self)


def classify_record(record: dict) -> ClassificationCategory:
    """
    Classify a single record based on its actual data.

    This is the REAL classification logic - not a placeholder.
    """
    status = record.get("status", "").lower()
    deadline = record.get("deadline_date")
    deadline_precision = record.get("deadline_precision", "unknown")
    deadline_display = record.get("deadline_display", "")

    # Parse deadline if string
    parsed_deadline = None
    if deadline and isinstance(deadline, str):
        try:
            parsed_deadline = date.fromisoformat(deadline)
        except ValueError:
            pass
    elif isinstance(deadline, date):
        parsed_deadline = deadline

    # Check if evergreen (no deadline or recurring programme)
    is_evergreen = parsed_deadline is None

    if is_evergreen:
        return ClassificationCategory.EVERGREEN

    # Check for unknown/ambiguous deadline
    if deadline_precision == "unknown" or not deadline_display:
        return ClassificationCategory.UNKNOWN

    if parsed_deadline and parsed_deadline < date.today():
        # Deadline is in the past
        if status in ("closed", "archived"):
            return ClassificationCategory.CLOSED
        elif status in ("closing-soon", "closing_soon"):
            # Past deadline but status is closing-soon - this is expected for CLOSING_SOON
            return ClassificationCategory.CLOSING_SOON
        else:
            # Past deadline but status is NOT closed/archived/closing-soon - CONFLICT
            return ClassificationCategory.STATUS_DEADLINE_CONFLICT

    if parsed_deadline and parsed_deadline >= date.today():
        # Future deadline
        if status in ("closing-soon", "closing_soon"):
            return ClassificationCategory.CLOSING_SOON
        return ClassificationCategory.BLOCKED

    # Ambiguous - no deadline but not evergreen?
    return ClassificationCategory.UNKNOWN


def run_gate5(accessor: DatabaseAccessor, target_ids: list[int]) -> Gate5Result:
    """
    Execute Gate 5: Target Classification Validation.

    Args:
        accessor: DatabaseAccessor with readonly production connection
        target_ids: List of target IDs to classify

    Returns:
        Gate5Result with classification validation and explicit mismatch reporting.
    """
    result = Gate5Result()

    try:
        with accessor.connect_readonly() as conn:
            # Fetch all target records
            records = accessor.get_target_records(conn, target_ids)

            if len(records) != 34:
                result.status = "FAIL"
                result.error = f"Expected 34 records, got {len(records)}"
                return result

            # Classify each record and build detailed report
            classifications = {}
            for record in records:
                rec_id = record["id"]
                classification = classify_record(record)
                classifications[rec_id] = classification

                # Track archive state
                is_archived = record.get("is_archived", False)
                if is_archived:
                    result.archived_count += 1
                else:
                    result.unarchived_count += 1

                # Build detailed classification record
                status = record.get("status", "").lower()
                deadline = record.get("deadline_date")
                deadline_precision = record.get("deadline_precision", "unknown")
                deadline_display = record.get("deadline_display", "")
                official_source_url = record.get("official_source_url", "")
                evidence_provenance = "database_record"  # Classification derived from DB record

                # Parse deadline for reporting
                parsed_deadline = None
                if deadline and isinstance(deadline, str):
                    try:
                        parsed_deadline = date.fromisoformat(deadline)
                    except ValueError:
                        pass
                elif isinstance(deadline, date):
                    parsed_deadline = deadline

                result.record_classifications.append({
                    "id": rec_id,
                    "title": record.get("title", ""),
                    "country": record.get("country", ""),
                    "classification": classification.value,
                    "status": status,
                    "deadline_date": parsed_deadline.isoformat() if parsed_deadline else None,
                    "deadline_display": deadline_display,
                    "deadline_precision": deadline_precision,
                    "is_archived": is_archived,
                    "archived_at": str(record.get("archived_at")) if record.get("archived_at") else None,
                    "archived_reason": record.get("archived_reason"),
                    "official_source_url": official_source_url,
                    "evidence_provenance": evidence_provenance,
                    "classification_reason": _get_classification_reason(classification, status, parsed_deadline, deadline_precision, deadline_display),
                })

            # Validate against expected manifest classifications - returns detailed result
            validation_result: ClassificationValidationResult = validate_classifications(classifications)

            # Populate new explicit mismatch fields
            result.mismatches = [
                {"id": m.id, "expected": m.expected.value, "actual": m.actual.value, "reason": m.reason}
                for m in validation_result.mismatches
            ]
            result.missing_from_db = validation_result.missing_from_db
            result.unexpected_in_db = validation_result.unexpected_in_db
            result.category_breakdown = validation_result.category_breakdown
            result.reconciliation_verified = validation_result.reconciliation_verified

            # Also populate legacy fields for backward compatibility
            result.classification_errors = []
            for m in validation_result.mismatches:
                result.classification_errors.append(f"ID {m.id}: expected {m.expected.value}, got {m.actual.value}")
            for tid in validation_result.missing_from_db:
                result.classification_errors.append(f"Missing classification for ID {tid}")
            for tid in validation_result.unexpected_in_db:
                result.classification_errors.append(f"Unexpected ID in classifications: {tid}")

            if not validation_result.is_valid:
                result.status = "FAIL"
                error_parts = []
                if validation_result.mismatches:
                    mismatch_ids = [str(m.id) for m in validation_result.mismatches]
                    error_parts.append(f"{len(validation_result.mismatches)} mismatches: {', '.join(mismatch_ids)}")
                if validation_result.missing_from_db:
                    error_parts.append(f"{len(validation_result.missing_from_db)} missing from DB: {', '.join(map(str, validation_result.missing_from_db))}")
                if validation_result.unexpected_in_db:
                    error_parts.append(f"{len(validation_result.unexpected_in_db)} unexpected in DB: {', '.join(map(str, validation_result.unexpected_in_db))}")
                if validation_result.category_breakdown.get("evergreen", 0) > 0:
                    error_parts.append(f"{validation_result.category_breakdown['evergreen']} evergreen")
                if validation_result.category_breakdown.get("unknown", 0) > 0:
                    error_parts.append(f"{validation_result.category_breakdown['unknown']} unknown")
                if validation_result.category_breakdown.get("blocked", 0) > 0:
                    error_parts.append(f"{validation_result.category_breakdown['blocked']} blocked")
                if validation_result.category_breakdown.get("status_deadline_conflict", 0) > 0:
                    error_parts.append(f"{validation_result.category_breakdown['status_deadline_conflict']} conflicts")
                result.error = f"Classification validation failed: {', '.join(error_parts)}"
                return result

            # Count categories (for legacy fields)
            for cat in classifications.values():
                if cat == ClassificationCategory.CLOSED:
                    result.closed_count += 1
                elif cat == ClassificationCategory.CLOSING_SOON:
                    result.closing_soon_count += 1
                elif cat == ClassificationCategory.EVERGREEN:
                    result.evergreen_count += 1
                elif cat == ClassificationCategory.UNKNOWN:
                    result.unknown_count += 1
                elif cat == ClassificationCategory.BLOCKED:
                    result.blocked_count += 1
                elif cat == ClassificationCategory.STATUS_DEADLINE_CONFLICT:
                    result.status_deadline_conflict_count += 1

            result.verified_ids = len(classifications)
            result.total_ids = len(target_ids)

            # Check for duplicates in target_ids
            if len(target_ids) != len(set(target_ids)):
                from collections import Counter
                counts = Counter(target_ids)
                result.duplicate_ids = [k for k, v in counts.items() if v > 1]
                result.status = "FAIL"
                result.error = f"Duplicate IDs in target list: {result.duplicate_ids}"
                return result

            # Gate PASS only if: 0 mismatches AND 0 blocked categories AND all 34 IDs reconciled
            if not validation_result.reconciliation_verified:
                result.status = "FAIL"
                result.error = "Reconciliation not verified: mismatches, missing IDs, or blocked categories exist"
                return result

            result.status = "PASS"
            return result

    except Exception as e:
        result.status = "ERROR"
        result.error = str(e)
        return result


def _get_classification_reason(classification: ClassificationCategory, status: str, 
                                deadline: Optional[date], deadline_precision: str, 
                                deadline_display: str) -> str:
    """Generate human-readable classification reason."""
    if classification == ClassificationCategory.CLOSED:
        return f"Status '{status}' with past deadline {deadline} (precision: {deadline_precision})"
    elif classification == ClassificationCategory.CLOSING_SOON:
        return f"Status '{status}' with recent/ending deadline {deadline} (display: {deadline_display})"
    elif classification == ClassificationCategory.EVERGREEN:
        return "No deadline - recurring/rolling programme"
    elif classification == ClassificationCategory.UNKNOWN:
        return f"Ambiguous deadline (precision: {deadline_precision}, display: '{deadline_display}')"
    elif classification == ClassificationCategory.BLOCKED:
        return f"Future deadline: {deadline}"
    elif classification == ClassificationCategory.STATUS_DEADLINE_CONFLICT:
        return f"Past deadline {deadline} but status is '{status}' (not closed/archived)"
    return "Unknown classification"


def main() -> int:
    """CLI entry point for Gate 5."""
    print("=== GATE 5: TARGET CLASSIFICATION VALIDATION ===")
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print(f"Count: {len(CANONICAL_TARGET_IDS)}")
    print()

    try:
        config = load_config(gates_to_run={"gate5"})
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    result = run_gate5(accessor, CANONICAL_TARGET_IDS)

    # Save results with metadata
    save_result_with_metadata(result.to_dict(), "gate5", "gate5_result.json")

    print("\n=== GATE 5 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print(f"\n✅ GATE 5 PASSED: {result.closed_count} closed, {result.closing_soon_count} closing-soon, 0 blocked/evergreen/unknown/conflict")
        print(f"   Reconciliation verified: {result.reconciliation_verified}")
        print(f"   Mismatches: {len(result.mismatches)}")
        print(f"   Missing from DB: {len(result.missing_from_db)}")
        print(f"   Unexpected in DB: {len(result.unexpected_in_db)}")
        return 0
    else:
        print(f"\n❌ GATE 5 {result.status}: {result.error}")
        if result.mismatches:
            print(f"   MISMATCHES ({len(result.mismatches)}):")
            for m in result.mismatches:
                print(f"     ID {m['id']}: expected={m['expected']}, actual={m['actual']}, reason={m['reason']}")
        if result.missing_from_db:
            print(f"   MISSING FROM DB ({len(result.missing_from_db)}): {result.missing_from_db}")
        if result.unexpected_in_db:
            print(f"   UNEXPECTED IN DB ({len(result.unexpected_in_db)}): {result.unexpected_in_db}")
        if result.category_breakdown:
            print(f"   CATEGORY BREAKDOWN: {result.category_breakdown}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())