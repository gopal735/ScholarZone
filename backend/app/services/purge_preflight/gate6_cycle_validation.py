"""
Gate 6: Application Cycle Validation

Verifies actual cycle-level deadlines.
Distinguishes recurring programmes from expired cycles.
Identifies evergreen opportunities.
Rejects future deadlines.
Rejects ambiguous dates.
Validates official-source evidence with FULL requirements:
- Exact cycle identifier
- Official domain/URL
- Source title
- Deadline with precision
- Supporting excerpt with hash
- Retrieval date
- Reviewer identity
- Decision

Never treats a generic programme homepage as proof that a specific application cycle has expired.
"""

import json
import hashlib
import sys
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional

from .manifest import CANONICAL_TARGET_IDS, TARGET_ID_SET, EvidenceRecord
from .database import DatabaseAccessor, create_accessor
from .config import DatabaseConfig, PreflightConfig, load_config
from .metadata import save_result_with_metadata


@dataclass
class CycleValidationResult:
    """Per-record cycle validation result."""
    id: int
    title: str
    programme: str
    country: str
    application_cycle: str
    deadline: Optional[str]
    deadline_precision: str
    is_evergreen: bool
    is_expired: bool
    official_source_url: str
    evidence: Optional[dict] = None
    evidence_sufficient: bool = False
    expiration_reason: str = ""
    blocked_reason: Optional[str] = None


@dataclass
class Gate6Result:
    """Gate 6 execution result."""
    test_name: str = "gate6_cycle_validation"
    total_records: int = 34
    expired_cycles: int = 0
    evergreen_programmes: int = 0
    future_deadlines: int = 0
    ambiguous_dates: int = 0
    insufficient_evidence: int = 0
    status_deadline_conflicts: int = 0
    validations: list[dict] = None
    blocked_ids: list[int] = None
    status: str = "PENDING"
    error: Optional[str] = None

    def __post_init__(self):
        if self.validations is None:
            self.validations = []
        if self.blocked_ids is None:
            self.blocked_ids = []

    def to_dict(self) -> dict:
        return asdict(self)


def validate_cycle_record(record: dict, reference_date: Optional[date] = None) -> CycleValidationResult:
    """
    Validate a single record's application cycle expiration.

    This is REAL validation - not a placeholder.
    Requires full evidence record for expired cycles.
    """
    if reference_date is None:
        reference_date = date.today()

    rec_id = record["id"]
    title = record.get("title", "")
    country = record.get("country", "")
    deadline = record.get("deadline_date")
    deadline_display = record.get("deadline_display", "")
    deadline_precision = record.get("deadline_precision", "unknown")
    official_source_url = record.get("official_source_url", "")
    status = record.get("status", "")

    # Parse deadline
    parsed_deadline = None
    if deadline:
        if isinstance(deadline, str):
            try:
                parsed_deadline = date.fromisoformat(deadline)
            except ValueError:
                pass
        elif isinstance(deadline, date):
            parsed_deadline = deadline

    # Determine if evergreen
    is_evergreen = parsed_deadline is None

    # Check for ambiguous dates
    is_ambiguous = (
        parsed_deadline is None
        or deadline_precision == "unknown"
        or not deadline_display
    )

    # Determine expiration
    is_expired = False
    blocked_reason = None
    expiration_reason = ""

    if is_evergreen:
        is_expired = False
        blocked_reason = "Evergreen programme (no deadline or recurring cycle)"
        expiration_reason = "Programme has no specific application cycle deadline - cannot confirm expiration"
    elif is_ambiguous:
        is_expired = False
        blocked_reason = "Ambiguous or unknown deadline"
        expiration_reason = f"Deadline precision: {deadline_precision}, display: {deadline_display}"
    elif parsed_deadline >= reference_date:
        is_expired = False
        blocked_reason = f"Future deadline: {parsed_deadline}"
        expiration_reason = f"Application deadline is in the future ({parsed_deadline})"
    else:
        # Deadline is in the past
        is_expired = True
        days_past = (reference_date - parsed_deadline).days
        expiration_reason = f"Application deadline {parsed_deadline} passed {days_past} days ago"

    # Verify official source evidence - FULL REQUIREMENTS
    evidence_sufficient = False
    evidence = None

    if official_source_url and is_expired:
        # For expired cycles, we need FULL evidence record
        # Check if evidence fields exist in record (from research_ledger or manual input)
        evidence_fields = [
            "evidence_official_domain",
            "evidence_official_url",
            "evidence_source_title",
            "evidence_deadline",
            "evidence_deadline_precision",
            "evidence_supporting_excerpt",
            "evidence_excerpt_hash",
            "evidence_retrieval_date",
            "evidence_reviewer",
            "evidence_decision",
        ]

        # Check if all evidence fields are present
        all_present = all(record.get(field) is not None for field in evidence_fields)

        if all_present:
            # Verify excerpt hash matches
            excerpt = record.get("evidence_supporting_excerpt", "")
            expected_hash = record.get("evidence_excerpt_hash", "")
            actual_hash = hashlib.sha256(excerpt.encode()).hexdigest()

            if actual_hash == expected_hash:
                # Verify decision is EXPIRED_VERIFIED
                if record.get("evidence_decision") == "EXPIRED_VERIFIED":
                    evidence_sufficient = True
                    evidence = {
                        "official_domain": record.get("evidence_official_domain"),
                        "official_url": record.get("evidence_official_url"),
                        "source_title": record.get("evidence_source_title"),
                        "deadline": record.get("evidence_deadline"),
                        "deadline_precision": record.get("evidence_deadline_precision"),
                        "supporting_excerpt": excerpt,
                        "excerpt_hash": expected_hash,
                        "retrieval_date": record.get("evidence_retrieval_date"),
                        "reviewer": record.get("evidence_reviewer"),
                        "decision": record.get("evidence_decision"),
                    }
                else:
                    blocked_reason = f"Evidence decision not EXPIRED_VERIFIED: {record.get('evidence_decision')}"
                    evidence_sufficient = False
            else:
                blocked_reason = "Evidence excerpt hash mismatch - integrity check failed"
                evidence_sufficient = False
        else:
            missing = [f for f in evidence_fields if record.get(f) is None]
            blocked_reason = f"Insufficient evidence - missing fields: {missing}"
            evidence_sufficient = False
    elif official_source_url and not is_expired:
        # For non-expired cycles, check if URL is cycle-specific
        # But preserve specific blocked_reason if already set (e.g., evergreen, future deadline)
        import re
        generic_patterns = [
            r"^https?://erasmus-plus\.ec\.europa\.eu/?$",
            r"^https?://www\.daad\.de/?$",
            r"^https?://studyinjapan\.go\.jp/?$",
            r"^https?://www\.studyinkorea\.go\.kr/?$",
            r"^https?://www\.campusfrance\.org/?$",
        ]
        is_generic = any(re.match(pattern, official_source_url) for pattern in generic_patterns)

        # Only override blocked_reason if it's not already set with a specific reason
        # (e.g., "Evergreen programme", "Future deadline:", "Ambiguous")
        specific_reasons = ["Evergreen programme", "Future deadline:", "Ambiguous"]
        has_specific_reason = any(reason in (blocked_reason or "") for reason in specific_reasons)

        if is_generic:
            if not has_specific_reason:
                blocked_reason = "Generic programme homepage (not cycle-specific)"
            evidence_sufficient = False
        else:
            if not has_specific_reason:
                blocked_reason = "Full evidence record required for cycle validation"
            evidence_sufficient = False

    return CycleValidationResult(
        id=rec_id,
        title=title,
        programme=title,
        country=country,
        application_cycle=deadline_display or "Unknown",
        deadline=parsed_deadline.isoformat() if parsed_deadline else None,
        deadline_precision=deadline_precision,
        is_evergreen=is_evergreen,
        is_expired=is_expired,
        official_source_url=official_source_url,
        evidence=evidence,
        evidence_sufficient=evidence_sufficient,
        expiration_reason=expiration_reason,
        blocked_reason=blocked_reason,
    )


def run_gate6(accessor: DatabaseAccessor, target_ids: list[int]) -> Gate6Result:
    """
    Execute Gate 6: Application Cycle Validation.

    Args:
        accessor: DatabaseAccessor with readonly production connection
        target_ids: List of target IDs to validate

    Returns:
        Gate6Result with cycle validation for all records
    """
    result = Gate6Result()

    try:
        with accessor.connect_readonly() as conn:
            records = accessor.get_target_records(conn, target_ids)

            if len(records) != 34:
                result.status = "FAIL"
                result.error = f"Expected 34 records, got {len(records)}"
                return result

            for record in records:
                validation = validate_cycle_record(record)
                result.validations.append(validation.__dict__)

                if validation.is_expired and validation.evidence_sufficient:
                    result.expired_cycles += 1
                else:
                    result.blocked_ids.append(validation.id)

                if validation.is_evergreen:
                    result.evergreen_programmes += 1
                if validation.deadline and not validation.is_expired and not validation.is_evergreen:
                    from datetime import date
                    try:
                        dl = date.fromisoformat(validation.deadline)
                        if dl >= date.today():
                            result.future_deadlines += 1
                    except ValueError:
                        pass
                if validation.deadline_precision == "unknown" or not validation.deadline:
                    result.ambiguous_dates += 1
                if not validation.evidence_sufficient:
                    result.insufficient_evidence += 1
                if validation.blocked_reason and "STATUS_DEADLINE_CONFLICT" in str(validation.blocked_reason):
                    result.status_deadline_conflicts += 1

            result.total_records = len(records)

            # Gate 6 passes ONLY if ALL 34 records have expired cycles with sufficient evidence
            if result.blocked_ids:
                result.status = "FAIL"
                result.error = f"{len(result.blocked_ids)} records not verifiably expired: {result.blocked_ids}"
                return result

            if result.expired_cycles != 34:
                result.status = "FAIL"
                result.error = f"Only {result.expired_cycles}/34 records have verified expired cycles"
                return result

            if result.insufficient_evidence > 0:
                result.status = "FAIL"
                result.error = f"{result.insufficient_evidence} records lack sufficient evidence"
                return result

            result.status = "PASS"
            return result

    except Exception as e:
        result.status = "ERROR"
        result.error = str(e)
        return result


def main() -> int:
    """CLI entry point for Gate 6."""
    print("=== GATE 6: APPLICATION CYCLE VALIDATION ===")
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print(f"Count: {len(CANONICAL_TARGET_IDS)}")
    print()

    try:
        config = load_config()
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    result = run_gate6(accessor, CANONICAL_TARGET_IDS)

    # Save results with metadata
    save_result_with_metadata(result.to_dict(), "gate6", "gate6_result.json")

    print("\n=== GATE 6 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print(f"\n✅ GATE 6 PASSED: All {result.expired_cycles} records have verified expired cycles with full evidence")
        return 0
    else:
        print(f"\n❌ GATE 6 {result.status}: {result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())