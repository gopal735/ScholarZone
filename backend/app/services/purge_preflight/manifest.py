"""
Canonical Target Manifest for Production Purge Preflight

This module defines the single source of truth for the 34 target records
to be purged. All gates must use these IDs - no duplicate lists allowed.

Classification Categories:
- CLOSED: Application cycle definitively ended, deadline past, status closed/archived
- CLOSING_SOON: Application cycle ending or recently ended (within grace period)
- EVERGREEN: No specific deadline (recurring/rolling programme) - CANNOT purge
- UNKNOWN: Insufficient data to determine status - CANNOT purge
- BLOCKED: Explicitly blocked from purge (e.g., future deadline, active cycle) - CANNOT purge
- STATUS_DEADLINE_CONFLICT: Past deadline but status shows open/active - REQUIRES REVIEW

IMPORTANT: EXPECTED_CLASSIFICATIONS is a REFERENCE MANIFEST only.
It documents the expected classification based on evidence at time of manifest creation.
Gate 5 MUST compare actual live record data against this reference and report mismatches explicitly.
NEVER use EXPECTED_CLASSIFICATIONS as hardcoded truth or sole authorization for purge.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


# The canonical 34 target IDs - SORTED, UNIQUE, IMMUTABLE
# These are the exact IDs from PR #67 that represent expired 2026 application cycles
CANONICAL_TARGET_IDS = [
    2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
    521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
    642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
    788, 1216, 1218, 1278
]

# Pre-computed set for O(1) membership tests
TARGET_ID_SET = frozenset(CANONICAL_TARGET_IDS)


def validate_manifest() -> None:
    """
    Validate the canonical manifest integrity.

    Raises:
        ValueError: If manifest has duplicates, wrong count, or not sorted.
    """
    if len(CANONICAL_TARGET_IDS) != 34:
        raise ValueError(f"Expected 34 target IDs, got {len(CANONICAL_TARGET_IDS)}")

    if len(set(CANONICAL_TARGET_IDS)) != 34:
        raise ValueError("Target IDs contain duplicates")

    if CANONICAL_TARGET_IDS != sorted(CANONICAL_TARGET_IDS):
        raise ValueError("Target IDs are not sorted")

    expected = [
        2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
        521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
        642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
        788, 1216, 1218, 1278
    ]
    if CANONICAL_TARGET_IDS != expected:
        raise ValueError("Target IDs do not match canonical list")


class ClassificationCategory(str, Enum):
    """Classification categories for target records."""
    CLOSED = "closed"
    CLOSING_SOON = "closing-soon"
    EVERGREEN = "evergreen"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"
    STATUS_DEADLINE_CONFLICT = "status-deadline-conflict"


@dataclass(frozen=True)
class EvidenceRecord:
    """Evidence record for cycle validation - Gate 6 requirement."""
    official_domain: str
    official_url: str
    source_title: str
    deadline: Optional[date]
    deadline_precision: str  # "day", "month", "unknown"
    supporting_excerpt: str  # Relevant excerpt from official source
    excerpt_hash: str  # SHA256 hash of excerpt for integrity
    retrieval_date: date
    reviewer: str
    decision: str  # "EXPIRED_VERIFIED", "NOT_EXPIRED", "EVERGREEN", "CONFLICT", "INSUFFICIENT_EVIDENCE"

    def to_dict(self) -> dict:
        return {
            "official_domain": self.official_domain,
            "official_url": self.official_url,
            "source_title": self.source_title,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "deadline_precision": self.deadline_precision,
            "supporting_excerpt": self.supporting_excerpt,
            "excerpt_hash": self.excerpt_hash,
            "retrieval_date": self.retrieval_date.isoformat(),
            "reviewer": self.reviewer,
            "decision": self.decision,
        }


@dataclass(frozen=True)
class TargetRecord:
    """
    Complete target record with expiration justification.

    This is the canonical record format used by all gates.
    Every field must be populated for a record to be PURGE_READY.
    """
    id: int
    title: str
    country: str
    programme: str
    application_cycle: str
    deadline: Optional[date]
    deadline_precision: str  # "day", "month", "unknown"
    current_status: str
    is_evergreen: bool
    official_source_url: str
    expiration_reason: str  # Human-readable justification
    classification: ClassificationCategory
    # Evidence for Gate 6 validation
    evidence: Optional[EvidenceRecord] = None

    def is_expired(self, reference_date: Optional[date] = None) -> bool:
        """Check if this record's application cycle has expired."""
        if reference_date is None:
            reference_date = date.today()
        if self.is_evergreen or self.deadline is None:
            return False
        return self.deadline < reference_date

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "title": self.title,
            "country": self.country,
            "programme": self.programme,
            "application_cycle": self.application_cycle,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "deadline_precision": self.deadline_precision,
            "current_status": self.current_status,
            "is_evergreen": self.is_evergreen,
            "official_source_url": self.official_source_url,
            "expiration_reason": self.expiration_reason,
            "classification": self.classification.value,
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


# Classification mapping - REFERENCE MANIFEST only
# This documents expected classifications based on evidence at manifest creation time.
# Gate 5 MUST validate against actual live database records and report mismatches explicitly.
# NEVER use this as hardcoded truth or sole authorization for purge operations.
# CLOSED: 18 records - application cycle definitively ended
# CLOSING_SOON: 16 records - cycle ending or recently ended
EXPECTED_CLASSIFICATIONS = {
    # CLOSED: 18 records
    2: ClassificationCategory.CLOSED,
    62: ClassificationCategory.CLOSED,
    103: ClassificationCategory.CLOSED,
    492: ClassificationCategory.CLOSED,
    496: ClassificationCategory.CLOSED,
    497: ClassificationCategory.CLOSED,
    510: ClassificationCategory.CLOSED,
    521: ClassificationCategory.CLOSED,
    556: ClassificationCategory.CLOSED,
    563: ClassificationCategory.CLOSED,
    587: ClassificationCategory.CLOSED,
    588: ClassificationCategory.CLOSED,
    662: ClassificationCategory.CLOSED,
    666: ClassificationCategory.CLOSED,
    788: ClassificationCategory.CLOSED,
    1216: ClassificationCategory.CLOSED,
    1218: ClassificationCategory.CLOSED,
    1278: ClassificationCategory.CLOSED,
    # Note: 496 and 497 are unique IDs, not duplicates

    # CLOSING_SOON: 16 records
    54: ClassificationCategory.CLOSING_SOON,
    59: ClassificationCategory.CLOSING_SOON,
    382: ClassificationCategory.CLOSING_SOON,
    583: ClassificationCategory.CLOSING_SOON,
    592: ClassificationCategory.CLOSING_SOON,
    594: ClassificationCategory.CLOSING_SOON,
    624: ClassificationCategory.CLOSING_SOON,
    626: ClassificationCategory.CLOSING_SOON,
    642: ClassificationCategory.CLOSING_SOON,
    651: ClassificationCategory.CLOSING_SOON,
    652: ClassificationCategory.CLOSING_SOON,
    655: ClassificationCategory.CLOSING_SOON,
    657: ClassificationCategory.CLOSING_SOON,
    677: ClassificationCategory.CLOSING_SOON,
    711: ClassificationCategory.CLOSING_SOON,
    724: ClassificationCategory.CLOSING_SOON,
}


def get_expected_classification(record_id: int) -> ClassificationCategory:
    """Get the expected classification for a target ID."""
    if record_id not in TARGET_ID_SET:
        raise ValueError(f"ID {record_id} not in canonical target set")
    return EXPECTED_CLASSIFICATIONS[record_id]


@dataclass(frozen=True)
class MismatchDetail:
    """Detailed mismatch between expected and actual classification."""
    id: int
    expected: ClassificationCategory
    actual: ClassificationCategory
    reason: str


@dataclass(frozen=True)
class ClassificationValidationResult:
    """Result of classification validation with detailed mismatch reporting."""
    is_valid: bool
    mismatches: list[MismatchDetail]
    missing_from_db: list[int]
    unexpected_in_db: list[int]
    category_breakdown: dict[str, int]
    reconciliation_verified: bool


def validate_classifications(classifications: dict[int, ClassificationCategory]) -> ClassificationValidationResult:
    """
    Validate classification mapping against canonical expectations.

    Returns:
        ClassificationValidationResult with detailed mismatch information.
        NEVER hides mismatches - all discrepancies are explicitly reported.
    """
    mismatches = []
    missing_from_db = []
    unexpected_in_db = []

    # Check all canonical IDs have classifications
    for tid in CANONICAL_TARGET_IDS:
        if tid not in classifications:
            missing_from_db.append(tid)
        elif classifications[tid] != EXPECTED_CLASSIFICATIONS[tid]:
            mismatches.append(MismatchDetail(
                id=tid,
                expected=EXPECTED_CLASSIFICATIONS[tid],
                actual=classifications[tid],
                reason=f"Expected {EXPECTED_CLASSIFICATIONS[tid].value}, got {classifications[tid].value}"
            ))

    # Check for extra IDs
    for tid in classifications:
        if tid not in TARGET_ID_SET:
            unexpected_in_db.append(tid)

    # Check for duplicates in values (should not happen with dict)
    seen = set()
    for tid, cat in classifications.items():
        key = (tid, cat)
        if key in seen:
            mismatches.append(MismatchDetail(
                id=tid,
                expected=EXPECTED_CLASSIFICATIONS.get(tid, ClassificationCategory.UNKNOWN),
                actual=cat,
                reason=f"Duplicate classification entry: {tid}={cat.value}"
            ))
        seen.add(key)

    # Category breakdown
    category_breakdown = {
        "closed": sum(1 for v in classifications.values() if v == ClassificationCategory.CLOSED),
        "closing_soon": sum(1 for v in classifications.values() if v == ClassificationCategory.CLOSING_SOON),
        "evergreen": sum(1 for v in classifications.values() if v == ClassificationCategory.EVERGREEN),
        "unknown": sum(1 for v in classifications.values() if v == ClassificationCategory.UNKNOWN),
        "blocked": sum(1 for v in classifications.values() if v == ClassificationCategory.BLOCKED),
        "status_deadline_conflict": sum(1 for v in classifications.values() if v == ClassificationCategory.STATUS_DEADLINE_CONFLICT),
        "total": len(classifications),
    }

    # Verify counts match expectation (reference only - not hardcoded truth)
    expected_closed = 18
    expected_closing_soon = 16

    reconciliation_verified = (
        len(mismatches) == 0 and
        len(missing_from_db) == 0 and
        len(unexpected_in_db) == 0 and
        category_breakdown["closed"] == expected_closed and
        category_breakdown["closing_soon"] == expected_closing_soon and
        category_breakdown["evergreen"] == 0 and
        category_breakdown["unknown"] == 0 and
        category_breakdown["blocked"] == 0 and
        category_breakdown["status_deadline_conflict"] == 0
    )

    is_valid = (
        len(mismatches) == 0 and
        len(missing_from_db) == 0 and
        len(unexpected_in_db) == 0 and
        category_breakdown["evergreen"] == 0 and
        category_breakdown["unknown"] == 0 and
        category_breakdown["blocked"] == 0 and
        category_breakdown["status_deadline_conflict"] == 0
    )

    return ClassificationValidationResult(
        is_valid=is_valid,
        mismatches=mismatches,
        missing_from_db=missing_from_db,
        unexpected_in_db=unexpected_in_db,
        category_breakdown=category_breakdown,
        reconciliation_verified=reconciliation_verified,
    )


# Validate on import
validate_manifest()