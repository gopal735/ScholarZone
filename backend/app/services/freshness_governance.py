"""Freshness SLA + Data Freshness Governance layer.

Defines and enforces how fresh each scholarship field must remain,
with stricter SLAs for high-impact data. Built on top of the existing
change_impact_staleness, adaptive_policy, lifecycle_identity, and
source_health modules — does NOT replace them.

Scheduler-visible outputs:
- freshness_priority: 0-100 urgency score derived from SLA state
- sla_breach_severity: 0-100, 0 = no breach
- next_required_verification: date when the most-critical field expires
- reason_codes: explainable triggers

This module NEVER modifies Scholarship directly. It produces governance
signals that the scheduler, anomaly detector, and cost optimizer consume.

Deterministic, no network calls, no N+1, O(1) per-field evaluation,
cached static policy definitions, batch evaluation supported.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Scholarship, SourceHealth
from .change_impact_staleness import (
    CRITICAL_STALE,
    FIELD_CRITICALITY,
    FRESH,
    STALE,
    compute_deadline_urgency,
    compute_field_staleness,
    get_freshness_threshold,
)
from .lifecycle_identity import classify_lifecycle_state


class FreshnessClass(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FreshnessState(str, Enum):
    FRESH = "fresh"
    WARNING = "warning"
    STALE = "stale"
    CRITICAL_STALE = "critical_stale"
    NEVER_VERIFIED = "never_verified"


FRESHNESS_CLASS_CRITICAL = FreshnessClass.CRITICAL
FRESHNESS_CLASS_HIGH = FreshnessClass.HIGH
FRESHNESS_CLASS_MEDIUM = FreshnessClass.MEDIUM
FRESHNESS_CLASS_LOW = FreshnessClass.LOW

STATE_FRESH = FreshnessState.FRESH
STATE_WARNING = FreshnessState.WARNING
STATE_STALE = FreshnessState.STALE
STATE_CRITICAL_STALE = FreshnessState.CRITICAL_STALE
STATE_NEVER_VERIFIED = FreshnessState.NEVER_VERIFIED

FIELD_FRESHNESS_CLASSES: dict[str, FreshnessClass] = {
    "deadline": FRESHNESS_CLASS_CRITICAL,
    "deadline_date": FRESHNESS_CLASS_CRITICAL,
    "deadline_display": FRESHNESS_CLASS_CRITICAL,
    "eligibility": FRESHNESS_CLASS_CRITICAL,
    "eligibility_summary": FRESHNESS_CLASS_CRITICAL,
    "funding": FRESHNESS_CLASS_CRITICAL,
    "funding_type": FRESHNESS_CLASS_CRITICAL,
    "coverage": FRESHNESS_CLASS_CRITICAL,
    "application_method": FRESHNESS_CLASS_CRITICAL,
    "application_link": FRESHNESS_CLASS_HIGH,
    "requirements": FRESHNESS_CLASS_HIGH,
    "required_documents": FRESHNESS_CLASS_HIGH,
    "documents": FRESHNESS_CLASS_HIGH,
    "application_period": FRESHNESS_CLASS_HIGH,
    "english_requirement": FRESHNESS_CLASS_HIGH,
    "selection_notes": FRESHNESS_CLASS_HIGH,
    "duration": FRESHNESS_CLASS_MEDIUM,
    "official_updates_url": FRESHNESS_CLASS_MEDIUM,
    "catalogue_url": FRESHNESS_CLASS_MEDIUM,
    "program_type": FRESHNESS_CLASS_MEDIUM,
    "best_fit": FRESHNESS_CLASS_LOW,
    "notes": FRESHNESS_CLASS_LOW,
    "title": FRESHNESS_CLASS_LOW,
    "description": FRESHNESS_CLASS_LOW,
    "country": FRESHNESS_CLASS_LOW,
    "degree": FRESHNESS_CLASS_LOW,
    "region": FRESHNESS_CLASS_LOW,
    "official_source": FRESHNESS_CLASS_LOW,
    "official_source_url": FRESHNESS_CLASS_LOW,
    "status": FRESHNESS_CLASS_MEDIUM,
}

CLASS_MAX_AGE_DAYS: dict[FreshnessClass, int] = {
    FRESHNESS_CLASS_CRITICAL: 30,
    FRESHNESS_CLASS_HIGH: 60,
    FRESHNESS_CLASS_MEDIUM: 90,
    FRESHNESS_CLASS_LOW: 180,
}

CLASS_WARNING_RATIO: dict[FreshnessClass, float] = {
    FRESHNESS_CLASS_CRITICAL: 0.6,
    FRESHNESS_CLASS_HIGH: 0.7,
    FRESHNESS_CLASS_MEDIUM: 0.75,
    FRESHNESS_CLASS_LOW: 0.8,
}

CLASS_CRITICAL_RATIO: dict[FreshnessClass, float] = {
    FRESHNESS_CLASS_CRITICAL: 1.0,
    FRESHNESS_CLASS_HIGH: 1.0,
    FRESHNESS_CLASS_MEDIUM: 1.0,
    FRESHNESS_CLASS_LOW: 1.0,
}

LIFECYCLE_FRESHNESS_ADJUSTMENT: dict[str, float] = {
    "discovered": 0.5,
    "active": 1.0,
    "application_open": 0.8,
    "deadline_near": 0.4,
    "closed": 1.5,
    "result_pending": 1.2,
    "archived": 999.0,
    "unknown": 1.0,
}

DEADLINE_TIGHTENING_THRESHOLD_DAYS = 30
DEADLINE_CRITICAL_TIGHTENING = 0.3
DEADLINE_URGENT_TIGHTENING = 0.6
DEADLINE_APPROACHING_TIGHTENING = 0.8

SOURCE_HEALTH_CONFIDENCE_FACTOR: dict[str, float] = {
    "healthy": 1.0,
    "degraded": 0.7,
    "unhealthy": 0.4,
    "unknown": 0.85,
}

_DEFAULT_CLASS = FRESHNESS_CLASS_MEDIUM
_DEFAULT_MAX_AGE = CLASS_MAX_AGE_DAYS[_DEFAULT_CLASS]


@dataclass(frozen=True)
class FreshnessPolicy:
    field_name: str
    freshness_class: FreshnessClass
    max_age_days: int
    warning_age_days: int
    critical_age_days: int
    sla_status: str
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FieldFreshnessResult:
    field_name: str
    freshness_class: FreshnessClass
    state: FreshnessState
    age_days: int | None
    max_age_days: int
    warning_age_days: int
    critical_age_days: int
    sla_breach_severity: int
    reason_codes: tuple[str, ...] = ()
    last_verified_at: datetime | None = None


@dataclass(frozen=True)
class ScholarshipFreshnessResult:
    scholarship_id: int
    overall_state: FreshnessState
    overall_sla_severity: int
    freshness_priority: int
    sla_breach_severity: int
    next_required_verification: date | None
    reason_codes: tuple[str, ...] = ()
    deadline_urgency: int = 0
    source_health_confidence: float = 1.0
    lifecycle_state: str = "unknown"
    manual_override: bool = False


@dataclass(frozen=True)
class FreshnessPolicyOverride:
    field_name: str
    max_age_days: int | None = None
    forced_state: FreshnessState | None = None
    reason_code: str = "manual_override"


def _get_policy_definitions() -> dict[str, FreshnessPolicy]:
    policies: dict[str, FreshnessPolicy] = {}
    for field_name, freshness_class in FIELD_FRESHNESS_CLASSES.items():
        base_max = CLASS_MAX_AGE_DAYS.get(freshness_class, _DEFAULT_MAX_AGE)
        warning_age = int(base_max * CLASS_WARNING_RATIO.get(freshness_class, 0.7))
        critical_age = int(base_max * CLASS_CRITICAL_RATIO.get(freshness_class, 1.0))
        policies[field_name] = FreshnessPolicy(
            field_name=field_name,
            freshness_class=freshness_class,
            max_age_days=base_max,
            warning_age_days=warning_age,
            critical_age_days=critical_age,
            sla_status="compliant",
            reason_codes=(),
        )
    return policies


_CACHED_POLICY_DEFINITIONS: dict[str, FreshnessPolicy] | None = None


def get_policy_definitions() -> dict[str, FreshnessPolicy]:
    global _CACHED_POLICY_DEFINITIONS
    if _CACHED_POLICY_DEFINITIONS is None:
        _CACHED_POLICY_DEFINITIONS = _get_policy_definitions()
    return _CACHED_POLICY_DEFINITIONS


def get_field_freshness_class(field_name: str) -> FreshnessClass:
    return FIELD_FRESHNESS_CLASSES.get(field_name, _DEFAULT_CLASS)


def get_freshness_max_age(field_name: str) -> int:
    return CLASS_MAX_AGE_DAYS.get(get_field_freshness_class(field_name), _DEFAULT_MAX_AGE)


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


def _get_source_health_confidence(source_health: SourceHealth | None) -> float:
    if source_health is None:
        return 1.0
    if source_health.manual_override is not None:
        return SOURCE_HEALTH_CONFIDENCE_FACTOR.get(source_health.manual_override, 1.0)
    return SOURCE_HEALTH_CONFIDENCE_FACTOR.get(source_health.health_status, 1.0)


def _apply_deadline_tightening(
    max_age: int,
    warning_age: int,
    critical_age: int,
    scholarship: Scholarship,
    today: date,
) -> tuple[int, int, int, str | None]:
    deadline = scholarship.deadline_date
    if deadline is None:
        return max_age, warning_age, critical_age, None

    if isinstance(deadline, datetime):
        deadline = deadline.date()

    delta = (deadline - today).days
    if delta < 0:
        return max_age, warning_age, critical_age, None

    if delta <= 14:
        factor = DEADLINE_CRITICAL_TIGHTENING
        reason = "deadline_critical_tightening"
    elif delta <= DEADLINE_TIGHTENING_THRESHOLD_DAYS:
        factor = DEADLINE_URGENT_TIGHTENING
        reason = "deadline_urgent_tightening"
    elif delta <= 60:
        factor = DEADLINE_APPROACHING_TIGHTENING
        reason = "deadline_approaching_tightening"
    else:
        return max_age, warning_age, critical_age, None

    tightened_max = max(1, int(max_age * factor))
    tightened_warning = max(1, int(warning_age * factor))
    tightened_critical = max(1, int(critical_age * factor))

    return tightened_max, tightened_warning, tightened_critical, reason


def _apply_lifecycle_adjustment(
    max_age: int,
    warning_age: int,
    critical_age: int,
    lifecycle_state: str,
) -> tuple[int, int, int, str | None]:
    factor = LIFECYCLE_FRESHNESS_ADJUSTMENT.get(lifecycle_state, 1.0)
    if factor == 1.0:
        return max_age, warning_age, critical_age, None

    if factor >= 999.0:
        return max_age, warning_age, critical_age, f"lifecycle_{lifecycle_state}"

    adjusted_max = max(1, int(max_age * factor))
    adjusted_warning = max(1, int(warning_age * factor))
    adjusted_critical = max(1, int(critical_age * factor))

    return adjusted_max, adjusted_warning, adjusted_critical, f"lifecycle_{lifecycle_state}"


def evaluate_field_freshness(
    field_name: str,
    last_verified_at: datetime | date | None,
    scholarship: Scholarship,
    session: Session,
    today: date | None = None,
    overrides: dict[str, FreshnessPolicyOverride] | None = None,
) -> FieldFreshnessResult:
    if today is None:
        today = date.today()

    if overrides and field_name in overrides:
        override = overrides[field_name]
        freshness_class = get_field_freshness_class(field_name)
        base_max = override.max_age_days if override.max_age_days is not None else get_freshness_max_age(field_name)
        warning_age = int(base_max * CLASS_WARNING_RATIO.get(freshness_class, 0.7))
        critical_age = base_max
        return FieldFreshnessResult(
            field_name=field_name,
            freshness_class=freshness_class,
            state=STATE_FRESH,
            age_days=None,
            max_age_days=base_max,
            warning_age_days=warning_age,
            critical_age_days=critical_age,
            sla_breach_severity=0,
            reason_codes=(override.reason_code,),
            last_verified_at=None,
        )

    freshness_class = get_field_freshness_class(field_name)
    base_max = get_freshness_max_age(field_name)
    base_warning = int(base_max * CLASS_WARNING_RATIO.get(freshness_class, 0.7))
    base_critical = base_max

    adjusted_max, adjusted_warning, adjusted_critical, _ = _apply_deadline_tightening(
        base_max, base_warning, base_critical, scholarship, today
    )

    try:
        lifecycle = classify_lifecycle_state(session, scholarship, today)
        lifecycle_state = lifecycle.state
    except Exception:
        lifecycle_state = "unknown"

    final_max, final_warning, final_critical, _ = _apply_lifecycle_adjustment(
        adjusted_max, adjusted_warning, adjusted_critical, lifecycle_state
    )

    if last_verified_at is None:
        return FieldFreshnessResult(
            field_name=field_name,
            freshness_class=freshness_class,
            state=STATE_NEVER_VERIFIED,
            age_days=None,
            max_age_days=final_max,
            warning_age_days=final_warning,
            critical_age_days=final_critical,
            sla_breach_severity=100 if freshness_class == FRESHNESS_CLASS_CRITICAL else 50,
            reason_codes=("never_verified",),
        )

    if isinstance(last_verified_at, datetime):
        last_date = last_verified_at.date() if hasattr(last_verified_at, "date") else today
    else:
        last_date = last_verified_at

    age_days = (today - last_date).days
    if age_days < 0:
        age_days = 0

    reason_codes: list[str] = []

    if age_days >= final_critical:
        state = STATE_CRITICAL_STALE
        severity = min(100, int((age_days / max(1, final_critical)) * 100))
        reason_codes.append("critical_sla_breach")
    elif age_days >= final_max:
        state = STATE_STALE
        severity = min(80, int((age_days / max(1, final_max)) * 80))
        reason_codes.append("sla_breach")
    elif age_days >= final_warning:
        state = STATE_WARNING
        severity = min(50, int((age_days / max(1, final_warning)) * 50))
        reason_codes.append("sla_warning")
    else:
        state = STATE_FRESH
        severity = 0

    if freshness_class == FRESHNESS_CLASS_CRITICAL and state != STATE_FRESH:
        reason_codes.append("critical_field")

    return FieldFreshnessResult(
        field_name=field_name,
        freshness_class=freshness_class,
        state=state,
        age_days=age_days,
        max_age_days=final_max,
        warning_age_days=final_warning,
        critical_age_days=final_critical,
        sla_breach_severity=severity,
        reason_codes=tuple(reason_codes),
        last_verified_at=last_verified_at if isinstance(last_verified_at, datetime) else None,
    )


def evaluate_scholarship_freshness(
    session: Session,
    scholarship: Scholarship,
    field_timestamps: dict[str, datetime | date | None],
    today: date | None = None,
    overrides: dict[str, FreshnessPolicyOverride] | None = None,
    source_health: SourceHealth | None = None,
) -> ScholarshipFreshnessResult:
    if today is None:
        today = date.today()

    if source_health is None:
        source_health = _get_source_health(session, scholarship.official_source_url)

    health_confidence = _get_source_health_confidence(source_health)

    try:
        lifecycle = classify_lifecycle_state(session, scholarship, today)
        lifecycle_state = lifecycle.state
    except Exception:
        lifecycle_state = "unknown"

    deadline_urgency = compute_deadline_urgency(scholarship, today)

    field_results: list[FieldFreshnessResult] = []
    for field_name, last_verified in field_timestamps.items():
        result = evaluate_field_freshness(
            field_name=field_name,
            last_verified_at=last_verified,
            scholarship=scholarship,
            session=session,
            today=today,
            overrides=overrides,
        )
        field_results.append(result)

    if not field_results:
        return ScholarshipFreshnessResult(
            scholarship_id=scholarship.id,
            overall_state=STATE_FRESH,
            overall_sla_severity=0,
            freshness_priority=0,
            sla_breach_severity=0,
            next_required_verification=None,
            reason_codes=(),
            deadline_urgency=deadline_urgency,
            source_health_confidence=health_confidence,
            lifecycle_state=lifecycle_state,
        )

    state_priority = {
        STATE_FRESH: 0,
        STATE_WARNING: 1,
        STATE_STALE: 2,
        STATE_CRITICAL_STALE: 3,
        STATE_NEVER_VERIFIED: 4,
    }

    worst_state = max(field_results, key=lambda r: (state_priority.get(r.state, 0), r.sla_breach_severity))
    overall_state = worst_state.state

    overall_severity = max(r.sla_breach_severity for r in field_results)

    base_priority = overall_severity
    deadline_boost = deadline_urgency // 2
    freshness_priority = min(100, base_priority + deadline_boost)

    if health_confidence < 1.0:
        confidence_adjustment = int((1.0 - health_confidence) * 20)
        freshness_priority = min(100, freshness_priority + confidence_adjustment)

    next_required_verification = _compute_next_required_verification(field_results, today)

    all_reason_codes: list[str] = []
    for r in field_results:
        all_reason_codes.extend(r.reason_codes)
    if deadline_urgency >= 80:
        all_reason_codes.append("deadline_near")
    if lifecycle_state in ("deadline_near", "application_open"):
        all_reason_codes.append(f"lifecycle_{lifecycle_state}")

    seen: set[str] = set()
    unique_reasons: list[str] = []
    for code in all_reason_codes:
        if code not in seen:
            seen.add(code)
            unique_reasons.append(code)

    return ScholarshipFreshnessResult(
        scholarship_id=scholarship.id,
        overall_state=overall_state,
        overall_sla_severity=overall_severity,
        freshness_priority=freshness_priority,
        sla_breach_severity=overall_severity,
        next_required_verification=next_required_verification,
        reason_codes=tuple(unique_reasons),
        deadline_urgency=deadline_urgency,
        source_health_confidence=health_confidence,
        lifecycle_state=lifecycle_state,
    )


def _compute_next_required_verification(
    field_results: list[FieldFreshnessResult],
    today: date,
) -> date | None:
    if not field_results:
        return None

    earliest: date | None = None
    for result in field_results:
        if result.state == STATE_FRESH and result.age_days is not None:
            remaining = result.max_age_days - result.age_days
            due = today + timedelta(days=max(0, remaining))
            if earliest is None or due < earliest:
                earliest = due
        elif result.state == STATE_WARNING and result.age_days is not None:
            remaining = result.max_age_days - result.age_days
            due = today + timedelta(days=max(0, remaining))
            if earliest is None or due < earliest:
                earliest = due
        elif result.state in (STATE_STALE, STATE_CRITICAL_STALE, STATE_NEVER_VERIFIED):
            if earliest is None or today < earliest:
                earliest = today

    return earliest


def batch_evaluate_freshness(
    session: Session,
    scholarships: list[Scholarship],
    field_timestamps_map: dict[int, dict[str, datetime | date | None]],
    today: date | None = None,
) -> dict[int, ScholarshipFreshnessResult]:
    if today is None:
        today = date.today()

    results: dict[int, ScholarshipFreshnessResult] = {}

    source_health_cache: dict[str, SourceHealth | None] = {}

    for scholarship in scholarships:
        timestamps = field_timestamps_map.get(scholarship.id, {})

        cache_key = scholarship.official_source_url or ""
        if cache_key not in source_health_cache:
            source_health_cache[cache_key] = _get_source_health(session, scholarship.official_source_url)

        results[scholarship.id] = evaluate_scholarship_freshness(
            session=session,
            scholarship=scholarship,
            field_timestamps=timestamps,
            today=today,
            source_health=source_health_cache[cache_key],
        )

    return results


def is_field_within_sla(field_name: str, last_verified_at: datetime | None, today: date | None = None) -> bool:
    if today is None:
        today = date.today()

    if last_verified_at is None:
        return False

    max_age = get_freshness_threshold(field_name)
    staleness = compute_field_staleness(field_name, last_verified_at, today)
    return staleness.freshness_state == FRESH


def is_field_sla_breached(field_name: str, last_verified_at: datetime | None, today: date | None = None) -> bool:
    if today is None:
        today = date.today()

    if last_verified_at is None:
        freshness_class = get_field_freshness_class(field_name)
        return freshness_class == FRESHNESS_CLASS_CRITICAL

    staleness = compute_field_staleness(field_name, last_verified_at, today)
    return staleness.freshness_state in (STALE, CRITICAL_STALE)


def get_freshness_summary(result: ScholarshipFreshnessResult) -> dict:
    return {
        "scholarship_id": result.scholarship_id,
        "overall_state": result.overall_state.value,
        "overall_sla_severity": result.overall_sla_severity,
        "freshness_priority": result.freshness_priority,
        "sla_breach_severity": result.sla_breach_severity,
        "next_required_verification": result.next_required_verification.isoformat() if result.next_required_verification else None,
        "reason_codes": list(result.reason_codes),
        "deadline_urgency": result.deadline_urgency,
        "source_health_confidence": result.source_health_confidence,
        "lifecycle_state": result.lifecycle_state,
        "has_critical_breach": result.overall_state == STATE_CRITICAL_STALE,
    }
