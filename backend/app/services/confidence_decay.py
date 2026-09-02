"""Confidence Decay + Evidence Aging layer.

Makes confidence time-aware. Evidence that was highly reliable when verified
gradually loses freshness/confidence as it ages, while remaining fully auditable.

Built on top of freshness_governance, verification_confidence, evidence_arbitration,
and source_health — does NOT replace them.

This module NEVER modifies Scholarship directly. It produces decay signals
that the scheduler, anomaly detector, and cost optimizer consume.

Deterministic: same inputs always produce same outputs.
No network calls. No N+1. O(1) per-field evaluation.
Cached static policy definitions. Batch evaluation supported.

Decay formula:
    decayed_confidence = original_confidence × evidence_freshness_factor × source_reliability_factor

Where:
    evidence_freshness_factor = exp(-0.693 × age_days / half_life)
    source_reliability_factor = confidence factor from source health status
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Scholarship, SourceHealth
from .freshness_governance import (
    FRESHNESS_CLASS_CRITICAL,
    FRESHNESS_CLASS_HIGH,
    FRESHNESS_CLASS_LOW,
    FRESHNESS_CLASS_MEDIUM,
    SOURCE_HEALTH_CONFIDENCE_FACTOR,
    FreshnessClass,
    get_field_freshness_class,
)


class ConfidenceState(str, Enum):
    """Confidence decay states for a field."""
    FRESH = "fresh"
    AGING = "aging"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    NEVER_VERIFIED = "never_verified"


CONFIDENCE_STATE_FRESH = ConfidenceState.FRESH
CONFIDENCE_STATE_AGING = ConfidenceState.AGING
CONFIDENCE_STATE_DEGRADED = ConfidenceState.DEGRADED
CONFIDENCE_STATE_CRITICAL = ConfidenceState.CRITICAL
CONFIDENCE_STATE_NEVER_VERIFIED = ConfidenceState.NEVER_VERIFIED


CLASS_DECAY_HALF_LIFE_DAYS: dict[FreshnessClass, float] = {
    FRESHNESS_CLASS_CRITICAL: 15.0,
    FRESHNESS_CLASS_HIGH: 30.0,
    FRESHNESS_CLASS_MEDIUM: 60.0,
    FRESHNESS_CLASS_LOW: 120.0,
}

_DEFAULT_DECAY_HALF_LIFE_DAYS = 60.0

_AGING_THRESHOLD = 0.65
_DEGRADED_THRESHOLD = 0.40
_CRITICAL_THRESHOLD = 0.15


@dataclass(frozen=True)
class ConfidenceDecayProfile:
    """Structured decay result for a single field.

    Attributes:
        field_name: The ORM field name being assessed
        original_confidence: The confidence value at verification time (0.0-1.0)
        age_days: Days since the evidence was verified
        decay_factor: Combined decay multiplier applied (0.0-1.0)
        decayed_confidence: Final confidence after decay (0.0-1.0)
        freshness_class: The freshness class of the field
        source_reliability: Source health confidence factor (0.0-1.0)
        decay_reason_codes: Explainable triggers for the decay
        confidence_state: The decay state category
    """

    field_name: str
    original_confidence: float
    age_days: int
    decay_factor: float
    decayed_confidence: float
    freshness_class: FreshnessClass
    source_reliability: float
    decay_reason_codes: tuple[str, ...] = ()
    confidence_state: ConfidenceState = CONFIDENCE_STATE_FRESH


@dataclass(frozen=True)
class ScholarshipDecayResult:
    """Complete decay result for a scholarship.

    Attributes:
        scholarship_id: The scholarship ID
        overall_confidence: The minimum decayed confidence across all fields
        confidence_state: The worst confidence state across all fields
        verification_urgency: 0-100, how urgently verification is needed
        field_profiles: Decay profiles for each evaluated field
        next_required_verification: Date when the most-critical field needs re-verification
        reason_codes: Explainable triggers
        source_health_confidence: Overall source health confidence
    """

    scholarship_id: int
    overall_confidence: float
    confidence_state: ConfidenceState
    verification_urgency: int
    field_profiles: tuple[ConfidenceDecayProfile, ...] = ()
    next_required_verification: date | None = None
    reason_codes: tuple[str, ...] = ()
    source_health_confidence: float = 1.0


@dataclass(frozen=True)
class ConfidenceDecayOverride:
    """Manual override for confidence decay.

    Attributes:
        field_name: The field to override
        forced_confidence: Fixed confidence value (bypasses decay)
        forced_state: Fixed confidence state (bypasses classification)
        reason_code: Why the override was applied
    """

    field_name: str
    forced_confidence: float | None = None
    forced_state: ConfidenceState | None = None
    reason_code: str = "manual_override"


def _get_decay_half_life(freshness_class: FreshnessClass) -> float:
    return CLASS_DECAY_HALF_LIFE_DAYS.get(freshness_class, _DEFAULT_DECAY_HALF_LIFE_DAYS)


def _domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _get_source_health(session: Session, source_url: str | None) -> SourceHealth | None:
    if not source_url:
        return None
    domain = _domain(source_url)
    if not domain:
        return None
    return session.scalar(select(SourceHealth).where(SourceHealth.domain == domain))


def _get_source_reliability_factor(source_health: SourceHealth | None) -> float:
    if source_health is None:
        return 1.0
    if source_health.manual_override is not None:
        return SOURCE_HEALTH_CONFIDENCE_FACTOR.get(source_health.manual_override, 1.0)
    return SOURCE_HEALTH_CONFIDENCE_FACTOR.get(source_health.health_status, 1.0)


def compute_evidence_freshness_factor(
    age_days: int,
    freshness_class: FreshnessClass,
) -> float:
    """Compute evidence freshness factor (0.0-1.0) based on age.

    Uses exponential decay with class-specific half-life.
    Critical fields decay faster; stable descriptive fields decay slower.

    Args:
        age_days: Days since the evidence was verified
        freshness_class: The freshness class of the field

    Returns:
        Freshness factor between 0.0 and 1.0
    """
    if age_days <= 0:
        return 1.0

    half_life = _get_decay_half_life(freshness_class)

    factor = math.exp(-0.693 * age_days / half_life)
    return max(0.0, min(1.0, factor))


def compute_decay_factor(
    age_days: int,
    freshness_class: FreshnessClass,
    source_reliability: float,
) -> float:
    """Compute combined decay factor from freshness and source health.

    Args:
        age_days: Days since the evidence was verified
        freshness_class: The freshness class of the field
        source_reliability: Source health confidence factor (0.0-1.0)

    Returns:
        Combined decay factor between 0.0 and 1.0
    """
    freshness_factor = compute_evidence_freshness_factor(age_days, freshness_class)

    combined = freshness_factor * source_reliability
    return max(0.0, min(1.0, combined))


def classify_confidence_state(decayed_confidence: float) -> ConfidenceState:
    """Classify the confidence state from the decayed confidence value.

    Args:
        decayed_confidence: The confidence value after decay (0.0-1.0)

    Returns:
        The corresponding ConfidenceState
    """
    if decayed_confidence >= _AGING_THRESHOLD:
        return CONFIDENCE_STATE_FRESH
    elif decayed_confidence >= _DEGRADED_THRESHOLD:
        return CONFIDENCE_STATE_AGING
    elif decayed_confidence >= _CRITICAL_THRESHOLD:
        return CONFIDENCE_STATE_DEGRADED
    else:
        return CONFIDENCE_STATE_CRITICAL


def evaluate_field_confidence_decay(
    field_name: str,
    original_confidence: float,
    last_verified_at: datetime | date | None,
    source_health: SourceHealth | None = None,
    today: date | None = None,
    overrides: dict[str, ConfidenceDecayOverride] | None = None,
) -> ConfidenceDecayProfile:
    """Evaluate confidence decay for a single field.

    Args:
        field_name: The ORM field name
        original_confidence: The confidence at verification time (0.0-1.0)
        last_verified_at: When the field was last verified
        source_health: Optional source health for the field's source
        today: Optional date for deterministic testing
        overrides: Optional manual overrides per field

    Returns:
        ConfidenceDecayProfile with decay results
    """
    if today is None:
        today = date.today()

    if overrides and field_name in overrides:
        override = overrides[field_name]
        freshness_class = get_field_freshness_class(field_name)
        source_reliability = _get_source_reliability_factor(source_health)

        if override.forced_confidence is not None:
            decayed = max(0.0, min(1.0, override.forced_confidence))
            state = override.forced_state or classify_confidence_state(decayed)
            return ConfidenceDecayProfile(
                field_name=field_name,
                original_confidence=original_confidence,
                age_days=0,
                decay_factor=1.0,
                decayed_confidence=decayed,
                freshness_class=freshness_class,
                source_reliability=source_reliability,
                decay_reason_codes=(override.reason_code,),
                confidence_state=state,
            )

    freshness_class = get_field_freshness_class(field_name)
    source_reliability = _get_source_reliability_factor(source_health)

    if last_verified_at is None:
        return ConfidenceDecayProfile(
            field_name=field_name,
            original_confidence=0.0,
            age_days=0,
            decay_factor=0.0,
            decayed_confidence=0.0,
            freshness_class=freshness_class,
            source_reliability=source_reliability,
            decay_reason_codes=("never_verified",),
            confidence_state=CONFIDENCE_STATE_NEVER_VERIFIED,
        )

    if isinstance(last_verified_at, datetime):
        last_date = last_verified_at.date() if hasattr(last_verified_at, "date") else today
    else:
        last_date = last_verified_at

    age_days = (today - last_date).days
    if age_days < 0:
        age_days = 0

    if original_confidence <= 0.0:
        return ConfidenceDecayProfile(
            field_name=field_name,
            original_confidence=0.0,
            age_days=age_days,
            decay_factor=0.0,
            decayed_confidence=0.0,
            freshness_class=freshness_class,
            source_reliability=source_reliability,
            decay_reason_codes=("no_original_confidence",),
            confidence_state=CONFIDENCE_STATE_NEVER_VERIFIED,
        )

    original_confidence = max(0.0, min(1.0, original_confidence))

    decay_factor = compute_decay_factor(age_days, freshness_class, source_reliability)
    decayed_confidence = max(0.0, min(1.0, original_confidence * decay_factor))

    confidence_state = classify_confidence_state(decayed_confidence)

    reason_codes: list[str] = []
    if age_days > 0:
        reason_codes.append("evidence_aged")
    if freshness_class == FRESHNESS_CLASS_CRITICAL:
        reason_codes.append("critical_field_faster_decay")
    if source_reliability < 1.0:
        reason_codes.append("source_health_acceleration")
    if decay_factor < 1.0:
        reason_codes.append("decay_applied")
    if not reason_codes:
        reason_codes.append("no_decay")

    return ConfidenceDecayProfile(
        field_name=field_name,
        original_confidence=original_confidence,
        age_days=age_days,
        decay_factor=decay_factor,
        decayed_confidence=decayed_confidence,
        freshness_class=freshness_class,
        source_reliability=source_reliability,
        decay_reason_codes=tuple(reason_codes),
        confidence_state=confidence_state,
    )


def evaluate_scholarship_confidence_decay(
    session: Session,
    scholarship: Scholarship,
    field_confidences: dict[str, float],
    field_timestamps: dict[str, datetime | date | None],
    today: date | None = None,
    overrides: dict[str, ConfidenceDecayOverride] | None = None,
    source_health: SourceHealth | None = None,
    _source_health_fetched: bool = False,
) -> ScholarshipDecayResult:
    """Evaluate confidence decay for all fields of a scholarship.

    Args:
        session: Database session
        scholarship: The scholarship to evaluate
        field_confidences: Map of field_name -> original confidence (0.0-1.0)
        field_timestamps: Map of field_name -> last verified date/time
        today: Optional date for deterministic testing
        overrides: Optional manual overrides per field
        source_health: Optional source health (fetched if not provided)
        _source_health_fetched: Internal flag to prevent re-fetching in batch mode

    Returns:
        ScholarshipDecayResult with decay results for all fields
    """
    if today is None:
        today = date.today()

    if source_health is None and not _source_health_fetched:
        source_health = _get_source_health(session, scholarship.official_source_url)

    source_health_confidence = _get_source_reliability_factor(source_health)

    field_profiles: list[ConfidenceDecayProfile] = []
    all_reason_codes: list[str] = []
    earliest_verification: date | None = None

    for field_name in sorted(field_confidences.keys()):
        original_confidence = field_confidences[field_name]
        last_verified = field_timestamps.get(field_name)

        profile = evaluate_field_confidence_decay(
            field_name=field_name,
            original_confidence=original_confidence,
            last_verified_at=last_verified,
            source_health=source_health,
            today=today,
            overrides=overrides,
        )
        field_profiles.append(profile)
        all_reason_codes.extend(profile.decay_reason_codes)

        if profile.confidence_state == CONFIDENCE_STATE_CRITICAL:
            if earliest_verification is None or today < earliest_verification:
                earliest_verification = today
        elif profile.age_days > 0:
            half_life = _get_decay_half_life(profile.freshness_class)
            days_until_critical = int(half_life * 3) - profile.age_days
            due = today + timedelta(days=max(0, days_until_critical))
            if earliest_verification is None or due < earliest_verification:
                earliest_verification = due

    if not field_profiles:
        return ScholarshipDecayResult(
            scholarship_id=scholarship.id,
            overall_confidence=0.0,
            confidence_state=CONFIDENCE_STATE_NEVER_VERIFIED,
            verification_urgency=0,
            field_profiles=(),
            next_required_verification=None,
            reason_codes=(),
            source_health_confidence=source_health_confidence,
        )

    overall_confidence = min(p.decayed_confidence for p in field_profiles)

    state_priority = {
        CONFIDENCE_STATE_FRESH: 0,
        CONFIDENCE_STATE_AGING: 1,
        CONFIDENCE_STATE_DEGRADED: 2,
        CONFIDENCE_STATE_CRITICAL: 3,
        CONFIDENCE_STATE_NEVER_VERIFIED: 4,
    }
    worst_state = max(field_profiles, key=lambda p: state_priority.get(p.confidence_state, 0))
    overall_state = worst_state.confidence_state

    verification_urgency = _compute_verification_urgency(field_profiles, overall_confidence)

    if earliest_verification is None:
        earliest_verification = today

    seen: set[str] = set()
    unique_reasons: list[str] = []
    for code in all_reason_codes:
        if code not in seen:
            seen.add(code)
            unique_reasons.append(code)

    return ScholarshipDecayResult(
        scholarship_id=scholarship.id,
        overall_confidence=overall_confidence,
        confidence_state=overall_state,
        verification_urgency=verification_urgency,
        field_profiles=tuple(field_profiles),
        next_required_verification=earliest_verification,
        reason_codes=tuple(unique_reasons),
        source_health_confidence=source_health_confidence,
    )


def _compute_verification_urgency(
    field_profiles: list[ConfidenceDecayProfile],
    overall_confidence: float,
) -> int:
    """Compute verification urgency score (0-100) from decay profiles."""
    if not field_profiles:
        return 0

    min_factor = min(p.decay_factor for p in field_profiles)
    max_age = max(p.age_days for p in field_profiles)
    has_critical = any(p.confidence_state == CONFIDENCE_STATE_CRITICAL for p in field_profiles)
    has_never = any(p.confidence_state == CONFIDENCE_STATE_NEVER_VERIFIED for p in field_profiles)

    base = int((1.0 - overall_confidence) * 60)
    age_component = min(20, int(max_age / 15))
    factor_component = int((1.0 - min_factor) * 20)

    urgency = base + age_component + factor_component

    if has_critical:
        urgency = max(urgency, 70)
    if has_never:
        urgency = max(urgency, 50)

    return max(0, min(100, urgency))


def batch_evaluate_confidence_decay(
    session: Session,
    scholarships: list[Scholarship],
    field_confidences_map: dict[int, dict[str, float]],
    field_timestamps_map: dict[int, dict[str, datetime | date | None]],
    today: date | None = None,
) -> dict[int, ScholarshipDecayResult]:
    """Batch evaluate confidence decay for multiple scholarships.

    Efficient: caches source health lookups to avoid N+1.

    Args:
        session: Database session
        scholarships: List of scholarships to evaluate
        field_confidences_map: Map of scholarship_id -> field_name -> confidence
        field_timestamps_map: Map of scholarship_id -> field_name -> timestamp
        today: Optional date for deterministic testing

    Returns:
        Dict mapping scholarship_id -> ScholarshipDecayResult
    """
    if today is None:
        today = date.today()

    results: dict[int, ScholarshipDecayResult] = {}
    source_health_cache: dict[str, tuple[SourceHealth | None, bool]] = {}

    for scholarship in scholarships:
        confidences = field_confidences_map.get(scholarship.id, {})
        timestamps = field_timestamps_map.get(scholarship.id, {})

        cache_key = scholarship.official_source_url or ""
        if cache_key not in source_health_cache:
            health = _get_source_health(session, scholarship.official_source_url)
            source_health_cache[cache_key] = (health, True)
        else:
            health, _ = source_health_cache[cache_key]

        results[scholarship.id] = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences=confidences,
            field_timestamps=timestamps,
            today=today,
            source_health=health,
            _source_health_fetched=True,
        )

    return results


def reset_confidence_after_verification(
    current_confidence: float,
    new_verified_confidence: float,
) -> float:
    """Reset confidence after a new successful verification.

    The decay clock is effectively reset by returning the newly verified confidence.

    Args:
        current_confidence: The previous (possibly decayed) confidence
        new_verified_confidence: The confidence from the new verification

    Returns:
        The new confidence value (bounded 0.0-1.0)
    """
    return max(0.0, min(1.0, new_verified_confidence))


def should_trigger_review(
    profile: ConfidenceDecayProfile,
    review_threshold: float = 0.30,
) -> tuple[bool, str]:
    """Determine if a decayed confidence should trigger a review.

    Args:
        profile: The confidence decay profile
        review_threshold: Confidence level below which review is triggered

    Returns:
        Tuple of (should_review, reason)
    """
    if profile.confidence_state == CONFIDENCE_STATE_NEVER_VERIFIED:
        return True, "Field never verified"

    if profile.decayed_confidence < review_threshold:
        return True, f"Confidence below review threshold ({profile.decayed_confidence:.2f} < {review_threshold:.2f})"

    if profile.confidence_state == CONFIDENCE_STATE_CRITICAL:
        return True, "Confidence in critical decay state"

    return False, "Confidence above threshold"


def get_decay_summary(result: ScholarshipDecayResult) -> dict:
    """Produce a scheduler-visible summary of decay results.

    Args:
        result: The scholarship decay result

    Returns:
        Dict with summary metrics
    """
    return {
        "scholarship_id": result.scholarship_id,
        "overall_confidence": result.overall_confidence,
        "confidence_state": result.confidence_state.value,
        "verification_urgency": result.verification_urgency,
        "next_required_verification": result.next_required_verification.isoformat() if result.next_required_verification else None,
        "reason_codes": list(result.reason_codes),
        "source_health_confidence": result.source_health_confidence,
        "field_count": len(result.field_profiles),
        "critical_field_count": sum(
            1 for p in result.field_profiles if p.confidence_state == CONFIDENCE_STATE_CRITICAL
        ),
        "never_verified_count": sum(
            1 for p in result.field_profiles if p.confidence_state == CONFIDENCE_STATE_NEVER_VERIFIED
        ),
    }
