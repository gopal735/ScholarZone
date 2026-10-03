"""Confidence: how much of this record was actually knowable.

Confidence is not fit. A scholarship can be a near-perfect fit for a student and
still deserve low confidence because the awarding body never published a tuition
figure, or because the record has never been re-verified. Conflating the two
would let a strong-looking number borrow authority it does not have.

The score is the weighted sum of four ratios, each computed only from stored
record state:

    35%  data completeness     how many scoring-relevant fields are populated
    25%  provenance quality    whether the record has verified official backing
    25%  requirement explicitness  whether published conditions are checkable
    15%  verification freshness   how recently the record was last verified

Every ratio is a documented fraction of named fields, not a subjective rating.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import (
    CONFIDENCE_BANDS,
    CONFIDENCE_WEIGHTS,
    VERIFICATION_FRESHNESS_STEPS,
)
from .normalize import normalise_text
from .requirements import ReadRequirements
from .types import EvidenceStatus, ScholarshipFacts


#: Fields whose presence makes a record usable for matching at all. Counted as
#: the data-completeness denominator so the ratio is stable as the catalogue
#: grows.
COMPLETENESS_FIELDS: tuple[str, ...] = (
    "country",
    "degree_levels",
    "funding_label",
    "program_type",
    "deadline_date",
    "eligibility_summary",
    "english_requirement",
    "tuition_coverage",
    "official_source_url",
)

#: Provenance signals, each contributing equally.
PROVENANCE_SIGNALS: tuple[str, ...] = (
    "official_source_url",
    "official_source",
    "is_verified",
    "catalogue_url",
    "official_updates_url",
    "programme_verification",
)


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    label: str
    label_display: str
    evidence: EvidenceStatus


def _band_for(score: float, bands) -> tuple[str, str]:
    for threshold, key, display in bands:
        if score >= threshold:
            return key, display
    last_key, last_display = bands[-1][1], bands[-1][2]
    return last_key, last_display


def _completeness(facts: ScholarshipFacts) -> float:
    """Fraction of the scoring-relevant fields that are populated.

    A coverage entry counts even when it is a single line, because the engine
    reads it as evidence rather than as a number. What matters here is whether
    the field exists at all.
    """
    populated = 0
    for name in COMPLETENESS_FIELDS:
        value = getattr(facts, name, None)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        populated += 1
    if facts.coverage:
        populated += 1
    if facts.requirements or facts.eligibility:
        populated += 1

    denominator = len(COMPLETENESS_FIELDS) + 2
    return round(min(1.0, populated / denominator) * 100.0, 1)


def _provenance(facts: ScholarshipFacts) -> float:
    """Fraction of provenance signals present."""
    present = 0
    for name in PROVENANCE_SIGNALS:
        value = getattr(facts, name, None)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        present += 1
    if facts.verification_status == "active":
        present += 1
    denominator = len(PROVENANCE_SIGNALS) + 1
    return round(min(1.0, present / denominator) * 100.0, 1)


def _explicitness(read: ReadRequirements, facts: ScholarshipFacts) -> float:
    """How much of what the record publishes is actually checkable.

    Six dimensions are considered. A record that states "citizens of X, minimum
    IELTS 6.5, under 30" scores highly even with no document list, because those
    are conditions a student can check. A record with prose eligibility and no
    thresholds scores poorly, because almost nothing about it can be verified
    against a profile.
    """
    checks = 0
    satisfied = 0

    checks += 1
    if read.academic_minimum is not None or read.academic_minimum_absent_by_publication:
        satisfied += 1

    checks += 1
    if read.language_minimum is not None or read.language_not_required:
        satisfied += 1

    checks += 1
    if read.nationality is not None:
        satisfied += 1

    checks += 1
    if read.age is not None:
        satisfied += 1

    checks += 1
    if facts.funding_label and (facts.tuition_coverage is not None or facts.living_cost_coverage is not None):
        satisfied += 1

    checks += 1
    if facts.documents:
        satisfied += 1

    return round(satisfied / checks * 100.0, 1)


def _freshness(facts: ScholarshipFacts, as_of: date) -> float:
    """How recently the record was verified, banded deterministically.

    LOCKED banded model, expressed in :mod:`config` as
    ``VERIFICATION_FRESHNESS_STEPS``:

        <=  90 days  ->  1.00
        <= 180 days  ->  0.75
        <= 365 days  ->  0.50
        <= 730 days  ->  0.25
        otherwise    ->  0.00
        never verified -> 0.00

    An earlier version of this engine interpolated linearly between the fresh and
    stale bounds and floored the result at 0.30, which meant a record verified
    four years ago still earned a third of the freshness weight - an unbounded
    credit for evidence nobody had refreshed. A step function with no floor is
    both the locked specification and the more honest statement about our own
    verification process.

    A verification date in the future is treated as fresh rather than as an
    error: the clock is injected and a test may pin ``as_of`` earlier than the
    stored date.
    """
    if not facts.last_verified_date:
        return 0.0
    try:
        verified = date.fromisoformat(facts.last_verified_date)
    except (TypeError, ValueError):
        return 0.0

    age_days = (as_of - verified).days
    if age_days < 0:
        return 100.0

    for bound_days, quality in VERIFICATION_FRESHNESS_STEPS:
        if age_days <= bound_days:
            return round(quality * 100.0, 1)

    # Past the final bound, or older than any band: this record is outside every
    # window ScholarZone treats as usable evidence.
    return 0.0


def compute_confidence(
    facts: ScholarshipFacts,
    read: ReadRequirements,
    as_of: date,
) -> ConfidenceResult:
    """Compute the confidence score and its evidence breakdown."""
    completeness = _completeness(facts)
    provenance = _provenance(facts)
    explicitness = _explicitness(read, facts)
    freshness = _freshness(facts, as_of)

    weighted = (
        completeness / 100.0 * CONFIDENCE_WEIGHTS["data_completeness"]
        + provenance / 100.0 * CONFIDENCE_WEIGHTS["provenance_quality"]
        + explicitness / 100.0 * CONFIDENCE_WEIGHTS["requirement_explicitness"]
        + freshness / 100.0 * CONFIDENCE_WEIGHTS["verification_freshness"]
    )
    score = round(min(100.0, weighted * 100.0), 1)
    label, display = _band_for(score, CONFIDENCE_BANDS)

    return ConfidenceResult(
        score=score,
        label=label,
        label_display=display,
        evidence=EvidenceStatus(
            has_official_source=bool(facts.official_source_url or facts.official_source),
            is_verified=bool(facts.is_verified),
            verification_status=facts.verification_status,
            last_verified_date=facts.last_verified_date,
            coverage_ratio=completeness,
            provenance_ratio=provenance,
            explicitness_ratio=explicitness,
            freshness_ratio=freshness,
        ),
    )


def confidence_label(score: float) -> tuple[str, str]:
    """Public helper so the API can label a stored score consistently."""
    return _band_for(score, CONFIDENCE_BANDS)