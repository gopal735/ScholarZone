"""Change impact and field-level staleness intelligence.

Determines:
1. How important a detected field change is (ChangeImpact)
2. How stale each scholarship field is (FieldStaleness)
3. How urgently the field/scholarship should be re-verified

Deterministic, no network calls, no duplicate persistence.
All metrics derived from existing Scholarship, ScholarshipVerificationHistory,
ScholarshipFetchAttempt, and SourceHealth data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Scholarship, SourceHealth

CRITICAL = "critical"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

IMPACT_LEVELS = frozenset({CRITICAL, HIGH, MEDIUM, LOW})

FRESH = "fresh"
STALE = "stale"
CRITICAL_STALE = "critical-stale"

FRESHNESS_STATES = frozenset({FRESH, STALE, CRITICAL_STALE})

FIELD_CRITICALITY: dict[str, str] = {
    "deadline_date": CRITICAL,
    "deadline": CRITICAL,
    "deadline_display": CRITICAL,
    "eligibility": CRITICAL,
    "eligibility_summary": CRITICAL,
    "funding": CRITICAL,
    "funding_type": CRITICAL,
    "coverage": CRITICAL,
    "application_method": CRITICAL,
    "application_link": CRITICAL,
    "required_documents": HIGH,
    "documents": HIGH,
    "requirements": HIGH,
    "duration": HIGH,
    "application_period": HIGH,
    "english_requirement": HIGH,
    "selection_notes": HIGH,
    "best_fit": MEDIUM,
    "program_type": MEDIUM,
    "notes": MEDIUM,
    "catalogue_url": MEDIUM,
    "official_updates_url": MEDIUM,
    "title": LOW,
    "description": LOW,
    "country": LOW,
    "degree": LOW,
    "region": LOW,
    "official_source": LOW,
    "official_source_url": LOW,
    "status": LOW,
}

FIELD_FRESHNESS_THRESHOLD_DAYS: dict[str, int] = {
    "deadline_date": 7,
    "deadline": 7,
    "deadline_display": 7,
    "eligibility": 30,
    "eligibility_summary": 30,
    "funding": 30,
    "funding_type": 30,
    "coverage": 30,
    "application_method": 30,
    "application_link": 14,
    "required_documents": 60,
    "documents": 60,
    "requirements": 60,
    "duration": 90,
    "application_period": 30,
    "english_requirement": 90,
    "selection_notes": 60,
    "best_fit": 180,
    "program_type": 180,
    "notes": 180,
    "catalogue_url": 90,
    "official_updates_url": 90,
    "title": 180,
    "description": 180,
    "country": 365,
    "degree": 365,
    "region": 365,
    "official_source": 180,
    "official_source_url": 180,
    "status": 7,
}

DEFAULT_FRESHNESS_THRESHOLD_DAYS = 90

DEADLINE_CRITICAL_DAYS = 14
DEADLINE_URGENT_DAYS = 30
DEADLINE_APPROACHING_DAYS = 60

SOURCE_HEALTH_CONFIDENCE_FACTOR: dict[str, float] = {
    "healthy": 1.0,
    "degraded": 0.7,
    "unhealthy": 0.4,
    "unknown": 0.85,
}


@dataclass(frozen=True)
class ChangeImpact:
    field_name: str
    impact_level: str
    impact_score: int
    reason: str


@dataclass(frozen=True)
class FieldStaleness:
    field_name: str
    last_verified_at: datetime | None
    age_days: int | None
    freshness_threshold_days: int
    staleness_score: int
    freshness_state: str


@dataclass(frozen=True)
class UrgencyScore:
    scholarship_id: int
    overall_urgency: int
    field_urgencies: list[tuple[str, int]]
    deadline_urgency: int
    source_health_confidence: float


def get_field_criticality(field_name: str) -> str:
    return FIELD_CRITICALITY.get(field_name, LOW)


def get_freshness_threshold(field_name: str) -> int:
    return FIELD_FRESHNESS_THRESHOLD_DAYS.get(field_name, DEFAULT_FRESHNESS_THRESHOLD_DAYS)


def compute_impact_score(impact_level: str) -> int:
    if impact_level == CRITICAL:
        return 100
    if impact_level == HIGH:
        return 70
    if impact_level == MEDIUM:
        return 40
    return 10


def compute_change_impact(field_name: str, old_value: object | None, new_value: object | None) -> ChangeImpact:
    criticality = get_field_criticality(field_name)
    score = compute_impact_score(criticality)

    if old_value is None and new_value is not None:
        reason = f"new {criticality}-critical field populated"
    elif old_value is not None and new_value is None:
        reason = f"{criticality}-critical field cleared"
    elif old_value != new_value:
        reason = f"{criticality}-critical field changed"
    else:
        reason = f"no change in {criticality}-critical field"
        score = 0

    return ChangeImpact(
        field_name=field_name,
        impact_level=criticality,
        impact_score=score,
        reason=reason,
    )


def _domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _get_source_health(session: Session, source_url: str | None) -> SourceHealth | None:
    if not source_url:
        return None
    domain = _domain(source_url)
    if not domain:
        return None
    return session.scalar(
        select(SourceHealth).where(SourceHealth.domain == domain)
    )


def get_source_health_confidence(source_health: SourceHealth | None) -> float:
    if source_health is None:
        return 1.0
    if source_health.manual_override is not None:
        return SOURCE_HEALTH_CONFIDENCE_FACTOR.get(source_health.manual_override, 1.0)
    return SOURCE_HEALTH_CONFIDENCE_FACTOR.get(source_health.health_status, 1.0)


def compute_field_staleness(
    field_name: str,
    last_verified_at: datetime | None,
    today: date | None = None,
) -> FieldStaleness:
    if today is None:
        today = date.today()

    threshold = get_freshness_threshold(field_name)

    if last_verified_at is None:
        return FieldStaleness(
            field_name=field_name,
            last_verified_at=None,
            age_days=None,
            freshness_threshold_days=threshold,
            staleness_score=100,
            freshness_state=CRITICAL_STALE,
        )

    if isinstance(last_verified_at, datetime):
        last_date = last_verified_at.date() if hasattr(last_verified_at, "date") else today
    else:
        last_date = last_verified_at

    age_days = (today - last_date).days
    if age_days < 0:
        age_days = 0

    if age_days >= threshold * 2:
        state = CRITICAL_STALE
    elif age_days >= threshold:
        state = STALE
    else:
        state = FRESH

    score = min(100, int((age_days / threshold) * 100)) if threshold > 0 else 0

    return FieldStaleness(
        field_name=field_name,
        last_verified_at=last_verified_at,
        age_days=age_days,
        freshness_threshold_days=threshold,
        staleness_score=score,
        freshness_state=state,
    )


def compute_deadline_urgency(scholarship: Scholarship, today: date | None = None) -> int:
    if today is None:
        today = date.today()

    deadline = scholarship.deadline_date
    if deadline is None:
        return 0

    if isinstance(deadline, datetime):
        deadline = deadline.date()

    delta = (deadline - today).days
    if delta < 0:
        return 0
    if delta <= DEADLINE_CRITICAL_DAYS:
        return 100
    if delta <= DEADLINE_URGENT_DAYS:
        return 80
    if delta <= DEADLINE_APPROACHING_DAYS:
        return 50
    return 10


def compute_field_urgency(
    impact: ChangeImpact,
    staleness: FieldStaleness,
    deadline_urgency: int,
) -> int:
    if impact.impact_level == CRITICAL:
        base_weight = 3
    elif impact.impact_level == HIGH:
        base_weight = 2
    else:
        base_weight = 1

    staleness_component = staleness.staleness_score * base_weight

    if deadline_urgency >= 80:
        deadline_component = 50
    elif deadline_urgency >= 50:
        deadline_component = 25
    else:
        deadline_component = 0

    if staleness.freshness_state == CRITICAL_STALE:
        stale_bonus = 30
    elif staleness.freshness_state == STALE:
        stale_bonus = 15
    else:
        stale_bonus = 0

    raw = staleness_component + deadline_component + stale_bonus
    return min(100, raw)


def compute_overall_urgency(field_urgencies: list[tuple[str, int]], deadline_urgency: int) -> int:
    if not field_urgencies:
        return deadline_urgency

    max_field = max(score for _, score in field_urgencies)
    avg_field = sum(score for _, score in field_urgencies) // len(field_urgencies)

    combined = max_field + (avg_field // 2) + (deadline_urgency // 2)
    return min(100, combined)


def assess_scholarship_fields(
    session: Session,
    scholarship: Scholarship,
    field_timestamps: dict[str, datetime | None],
    today: date | None = None,
) -> list[tuple[ChangeImpact, FieldStaleness]]:
    if today is None:
        today = date.today()

    results = []
    for field_name, last_verified in field_timestamps.items():
        impact = compute_change_impact(field_name, None, None)
        staleness = compute_field_staleness(field_name, last_verified, today)
        results.append((impact, staleness))

    return results


def compute_urgency(
    session: Session,
    scholarship: Scholarship,
    field_timestamps: dict[str, datetime | None],
    today: date | None = None,
) -> UrgencyScore:
    if today is None:
        today = date.today()

    deadline_urgency = compute_deadline_urgency(scholarship, today)
    source_health = _get_source_health(session, scholarship.official_source_url)
    confidence = get_source_health_confidence(source_health)

    field_urgencies: list[tuple[str, int]] = []
    for field_name, last_verified in field_timestamps.items():
        impact = compute_change_impact(field_name, None, None)
        staleness = compute_field_staleness(field_name, last_verified, today)
        urgency = compute_field_urgency(impact, staleness, deadline_urgency)

        adjusted_urgency = int(urgency * (2.0 - confidence))
        adjusted_urgency = max(0, min(100, adjusted_urgency))

        field_urgencies.append((field_name, adjusted_urgency))

    overall = compute_overall_urgency(field_urgencies, deadline_urgency)

    return UrgencyScore(
        scholarship_id=scholarship.id,
        overall_urgency=overall,
        field_urgencies=field_urgencies,
        deadline_urgency=deadline_urgency,
        source_health_confidence=confidence,
    )


def batch_assess_staleness(
    scholarships: list[Scholarship],
    field_timestamps_map: dict[int, dict[str, datetime | None]],
    today: date | None = None,
) -> dict[int, list[tuple[ChangeImpact, FieldStaleness]]]:
    if today is None:
        today = date.today()

    results: dict[int, list[tuple[ChangeImpact, FieldStaleness]]] = {}
    for scholarship in scholarships:
        timestamps = field_timestamps_map.get(scholarship.id, {})
        results[scholarship.id] = assess_scholarship_fields(
            None, scholarship, timestamps, today
        )
    return results


def rank_fields_by_urgency(urgency: UrgencyScore) -> list[tuple[str, int]]:
    return sorted(urgency.field_urgencies, key=lambda x: (-x[1], x[0]))


def is_field_stale(field_name: str, last_verified_at: datetime | None, today: date | None = None) -> bool:
    staleness = compute_field_staleness(field_name, last_verified_at, today)
    return staleness.freshness_state in (STALE, CRITICAL_STALE)


def is_field_critical_stale(field_name: str, last_verified_at: datetime | None, today: date | None = None) -> bool:
    staleness = compute_field_staleness(field_name, last_verified_at, today)
    return staleness.freshness_state == CRITICAL_STALE
