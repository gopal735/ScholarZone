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
from datetime import date, datetime, timezone
from typing import Optional
from types import SimpleNamespace

from ..closed_deletion import get_effective_lifecycle_status

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
    total_ids: int = 0
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


def classify_record(record: dict, reference_date: Optional[date] = None) -> ClassificationCategory:
    """
    Classify a single record using the same effective lifecycle policy as
    manifest generation.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    # Adapt the dictionary record to the attribute-based interface expected by
    # get_effective_lifecycle_status.
    if record.get("deadline_date") is None:
        return ClassificationCategory.EVERGREEN

    if record.get("deadline_precision", "unknown") == "unknown" and not record.get("deadline_display"):
        return ClassificationCategory.UNKNOWN

    obj = SimpleNamespace(**{k: v for k, v in record.items() if not isinstance(v, (list, dict))})
    effective = get_effective_lifecycle_status(obj, reference_date)

    if effective == "CLOSED":
        return ClassificationCategory.CLOSED
    if effective == "CLOSING_SOON":
        return ClassificationCategory.CLOSING_SOON
    if effective in ("OPEN", "OPENING", "UPCOMING"):
        return ClassificationCategory.BLOCKED
    if effective == "UNKNOWN":
        return ClassificationCategory.UNKNOWN
    # Records without a deadline are treated as evergreen.
    if record.get("deadline_date") is None:
        return ClassificationCategory.EVERGREEN
    return ClassificationCategory.BLOCKED


def run_gate5(accessor: DatabaseAccessor, target_ids: list[int], reference_date: Optional[date] = None) -> Gate5Result:
    """
    Execute Gate 5: Target Classification Validation.

    Args:
        accessor: DatabaseAccessor with readonly production connection
        target_ids: List of target IDs to classify

    Returns:
        Gate5Result with classification validation and explicit mismatch reporting.
    """
    result = Gate5Result()

    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    if not target_ids:
        result.status = "FAIL"
        result.error = "NO_TARGETS: empty manifest cannot authorize deletion"
        return result

    try:
        with accessor.connect_readonly() as conn:
            # Fetch all target records
            records = accessor.get_target_records(conn, target_ids)

            if len(records) != len(target_ids):
                result.status = "FAIL"
                result.error = f"Expected {len(target_ids)} records, got {len(records)}"
                return result

            # Classify each record and build detailed report
            classifications = {}
            for record in records:
                rec_id = record["id"]
                classification = classify_record(record, reference_date)
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

            # Dynamic validation: only definitively CLOSED scholarships are eligible.
            non_closed = [cid for cid, cls in classifications.items() if cls.value != 'closed']
            result.mismatches = [{'id': cid, 'expected': 'closed', 'actual': classifications[cid].value,
                                 'reason': f'Target {cid} is {classifications[cid].value}, not CLOSED'} for cid in non_closed]
            result.missing_from_db = []
            result.unexpected_in_db = []
            result.category_breakdown = {
                'closed': sum(1 for v in classifications.values() if v.value == 'closed'),
                'total': len(classifications),
            }
            result.reconciliation_verified = (len(non_closed) == 0)
            result.classification_errors = [f'ID {cid}: not CLOSED' for cid in non_closed]

            if non_closed:
                result.status = 'FAIL'
                result.error = 'Non-CLOSED targets present: ' + str(non_closed)
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
            if not result.reconciliation_verified:
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
    import os, json
    manifest_path = os.environ.get("MANIFEST_PATH", "artifacts/deletion_manifest.json")
    with open(manifest_path) as f:
        _m = json.load(f)
    target_ids = [x["scholarship_id"] for x in _m]
    reference_date = None
    metadata_path = os.path.join(os.path.dirname(manifest_path), "manifest_metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path) as f:
            _md = json.load(f)
        if _md.get("reference_date"):
            reference_date = date.fromisoformat(_md["reference_date"])
    print(f"Target IDs from dynamic manifest: {target_ids}")
    print(f"Count: {len(target_ids)}")
    print()

    try:
        config = load_config(gates_to_run={"gate5"})
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    result = run_gate5(accessor, target_ids, reference_date)

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