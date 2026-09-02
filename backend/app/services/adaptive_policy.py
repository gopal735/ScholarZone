"""Adaptive verification frequency intelligence.

Determines how frequently each scholarship/source should be verified,
using existing health, latency, failures, change history, staleness,
deadline urgency, telemetry, retry state, and lifecycle signals.

Deterministic, explainable, bounded. No network calls. No N+1 queries.
All metrics derived from existing data models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import SourceHealth, Scholarship, ScholarshipFetchAttempt, ScholarshipVerificationHistory
from .change_impact_staleness import (
    CRITICAL_STALE,
    FIELD_CRITICALITY,
    STALE,
    compute_deadline_urgency,
    compute_field_staleness,
    get_freshness_threshold,
)
from .lifecycle_identity import classify_lifecycle_state
from .source_health_service import HealthConfig, classify_health_status, compute_reliability_score
from .telemetry_tracing import get_collector

BASE_INTERVAL_DAYS = 90
MIN_INTERVAL_DAYS = 7
MAX_INTERVAL_DAYS = 180

SOURCE_HEALTH_INTERVAL_FACTOR = {
    "healthy": 1.3,
    "degraded": 0.8,
    "unhealthy": 0.5,
    "unknown": 1.0,
}

LIFECYCLE_INTERVAL_FACTOR = {
    "discovered": 0.5,
    "active": 1.0,
    "application_open": 0.8,
    "deadline_near": 0.3,
    "closed": 2.0,
    "result_pending": 1.5,
    "archived": 999.0,
    "unknown": 1.0,
}

HIGH_CHANGE_THRESHOLD = 5
HIGH_CHANGE_INTERVAL_FACTOR = 0.5
MODERATE_CHANGE_THRESHOLD = 2
MODERATE_CHANGE_INTERVAL_FACTOR = 0.75

LATENCY_SLOW_P95_MS = 5000.0
LATENCY_SLOW_INTERVAL_FACTOR = 0.7
LATENCY_FAST_P95_MS = 1000.0
LATENCY_FAST_INTERVAL_FACTOR = 1.1

CONSECUTIVE_FAILURES_HIGH = 5
CONSECUTIVE_FAILURES_HIGH_INTERVAL_FACTOR = 0.4
CONSECUTIVE_FAILURES_MODERATE = 3
CONSECUTIVE_FAILURES_MODERATE_INTERVAL_FACTOR = 0.6

DEADLINE_CRITICAL_DAYS = 14
DEADLINE_CRITICAL_INTERVAL_FACTOR = 0.25
DEADLINE_URGENT_DAYS = 30
DEADLINE_URGENT_INTERVAL_FACTOR = 0.4
DEADLINE_APPROACHING_DAYS = 60
DEADLINE_APPROACHING_INTERVAL_FACTOR = 0.6

RETRY_STATE_INTERVAL_FACTOR = 0.5

MAX_FIELD_STALENESS_THRESHOLD = 80
FIELD_STALENESS_INTERVAL_FACTOR = 0.6


@dataclass(frozen=True)
class AdaptiveVerificationPolicy:
    recommended_interval_days: int
    priority_multiplier: float
    next_due_at: date
    reason_codes: tuple[str, ...]
    confidence: float


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
    return session.scalar(select(SourceHealth).where(SourceHealth.domain == domain))


def _get_source_health_metrics(
    session: Session,
    source_url: str | None,
) -> tuple[str, float, int]:
    health = _get_source_health(session, source_url)
    if health is None:
        return "unknown", 0.0, 0

    if health.manual_override is not None:
        status = health.manual_override
    else:
        status = health.health_status

    return status, health.reliability_score, health.consecutive_failures


def _compute_source_health_interval_factor(health_status: str) -> float:
    return SOURCE_HEALTH_INTERVAL_FACTOR.get(health_status, 1.0)


def _compute_change_frequency_interval_factor(
    session: Session,
    scholarship: Scholarship,
    today: date,
    window_days: int = 180,
) -> tuple[float, int, str]:
    window_start = today - timedelta(days=window_days)
    count = session.scalar(
        select(func.count(ScholarshipVerificationHistory.id))
        .where(
            ScholarshipVerificationHistory.scholarship_id == scholarship.id,
            ScholarshipVerificationHistory.change_type != "unchanged",
            ScholarshipVerificationHistory.created_at >= window_start,
        )
    ) or 0

    if count >= HIGH_CHANGE_THRESHOLD:
        return HIGH_CHANGE_INTERVAL_FACTOR, count, "high_change_frequency"
    elif count >= MODERATE_CHANGE_THRESHOLD:
        return MODERATE_CHANGE_INTERVAL_FACTOR, count, "moderate_change_frequency"
    return 1.0, count, ""


def _compute_latency_interval_factor(
    source_health: SourceHealth | None,
) -> tuple[float, str]:
    if source_health is None or source_health.p95_latency_ms is None:
        return 1.0, ""

    p95 = source_health.p95_latency_ms
    if p95 >= LATENCY_SLOW_P95_MS:
        return LATENCY_SLOW_INTERVAL_FACTOR, "slow_source_latency"
    elif p95 <= LATENCY_FAST_P95_MS:
        return LATENCY_FAST_INTERVAL_FACTOR, "fast_source_latency"
    return 1.0, ""


def _compute_consecutive_failures_interval_factor(
    consecutive_failures: int,
) -> tuple[float, str]:
    if consecutive_failures >= CONSECUTIVE_FAILURES_HIGH:
        return CONSECUTIVE_FAILURES_HIGH_INTERVAL_FACTOR, "high_consecutive_failures"
    elif consecutive_failures >= CONSECUTIVE_FAILURES_MODERATE:
        return CONSECUTIVE_FAILURES_MODERATE_INTERVAL_FACTOR, "moderate_consecutive_failures"
    return 1.0, ""


def _compute_deadline_interval_factor(
    scholarship: Scholarship,
    today: date,
) -> tuple[float, str]:
    if scholarship.deadline_date is None:
        return 1.0, ""

    deadline = scholarship.deadline_date
    if isinstance(deadline, datetime):
        deadline = deadline.date()

    delta = (deadline - today).days
    if delta < 0:
        return 1.0, ""
    if delta <= DEADLINE_CRITICAL_DAYS:
        return DEADLINE_CRITICAL_INTERVAL_FACTOR, "deadline_critical"
    elif delta <= DEADLINE_URGENT_DAYS:
        return DEADLINE_URGENT_INTERVAL_FACTOR, "deadline_urgent"
    elif delta <= DEADLINE_APPROACHING_DAYS:
        return DEADLINE_APPROACHING_INTERVAL_FACTOR, "deadline_approaching"
    return 1.0, ""


def _compute_retry_state_interval_factor(
    session: Session,
    scholarship: Scholarship,
) -> tuple[float, str]:
    if not scholarship.official_source_url:
        return 1.0, ""

    active_retry = session.scalar(
        select(ScholarshipFetchAttempt)
        .where(
            ScholarshipFetchAttempt.scholarship_id == scholarship.id,
            ScholarshipFetchAttempt.source_url == scholarship.official_source_url,
            ScholarshipFetchAttempt.status == "retrying",
        )
    )
    if active_retry is not None:
        return RETRY_STATE_INTERVAL_FACTOR, "active_retry_state"
    return 1.0, ""


def _compute_field_staleness_interval_factor(
    scholarship: Scholarship,
    today: date,
) -> tuple[float, str]:
    if scholarship.last_verified_at is None:
        return 1.0, ""

    last_verified = scholarship.last_verified_at
    if isinstance(last_verified, datetime):
        last_verified = last_verified.date()

    max_staleness = 0
    stalest_field = ""
    for field_name in FIELD_CRITICALITY:
        staleness = compute_field_staleness(field_name, last_verified, today)
        if staleness.staleness_score > max_staleness:
            max_staleness = staleness.staleness_score
            stalest_field = field_name

    if max_staleness >= MAX_FIELD_STALENESS_THRESHOLD:
        return FIELD_STALENESS_INTERVAL_FACTOR, f"stale_critical_field:{stalest_field}"
    return 1.0, ""


def _compute_lifecycle_interval_factor(
    session: Session,
    scholarship: Scholarship,
    today: date,
) -> tuple[float, str, bool]:
    lifecycle = classify_lifecycle_state(session, scholarship, today)
    factor = LIFECYCLE_INTERVAL_FACTOR.get(lifecycle.state, 1.0)
    reason = f"lifecycle_{lifecycle.state}" if lifecycle.state != "unknown" else ""
    return factor, reason, lifecycle.is_terminal


def _compute_priority_multiplier(
    health_status: str,
    deadline_factor: float,
    change_factor: float,
    lifecycle_terminal: bool,
) -> float:
    if lifecycle_terminal:
        return 0.0

    multiplier = 1.0

    if health_status == "unhealthy":
        multiplier *= 0.5
    elif health_status == "degraded":
        multiplier *= 0.8

    multiplier *= 1.0 / max(0.1, deadline_factor)
    multiplier *= 1.0 / max(0.1, change_factor)

    return max(0.1, min(2.0, multiplier))


def compute_adaptive_policy(
    session: Session,
    scholarship: Scholarship,
    today: date | None = None,
) -> AdaptiveVerificationPolicy:
    if today is None:
        today = date.today()

    reason_codes: list[str] = []
    confidence_factors: list[float] = []

    health_status, reliability_score, consecutive_failures = _get_source_health_metrics(
        session, scholarship.official_source_url
    )

    health_factor = _compute_source_health_interval_factor(health_status)
    if health_status != "unknown":
        reason_codes.append(f"source_{health_status}")
        confidence_factors.append(reliability_score / 100.0)

    change_factor, change_count, change_reason = _compute_change_frequency_interval_factor(
        session, scholarship, today
    )
    if change_reason:
        reason_codes.append(change_reason)
        confidence_factors.append(min(1.0, change_count / HIGH_CHANGE_THRESHOLD))

    source_health = _get_source_health(session, scholarship.official_source_url)
    latency_factor, latency_reason = _compute_latency_interval_factor(source_health)
    if latency_reason:
        reason_codes.append(latency_reason)
        confidence_factors.append(0.8)

    failure_factor, failure_reason = _compute_consecutive_failures_interval_factor(consecutive_failures)
    if failure_reason:
        reason_codes.append(failure_reason)
        confidence_factors.append(min(1.0, consecutive_failures / CONSECUTIVE_FAILURES_HIGH))

    deadline_factor, deadline_reason = _compute_deadline_interval_factor(scholarship, today)
    if deadline_reason:
        reason_codes.append(deadline_reason)
        confidence_factors.append(0.9)

    retry_factor, retry_reason = _compute_retry_state_interval_factor(session, scholarship)
    if retry_reason:
        reason_codes.append(retry_reason)
        confidence_factors.append(0.7)

    staleness_factor, staleness_reason = _compute_field_staleness_interval_factor(scholarship, today)
    if staleness_reason:
        reason_codes.append(staleness_reason)
        confidence_factors.append(0.85)

    lifecycle_factor, lifecycle_reason, lifecycle_terminal = _compute_lifecycle_interval_factor(
        session, scholarship, today
    )
    if lifecycle_reason:
        reason_codes.append(lifecycle_reason)
        confidence_factors.append(0.95)

    if lifecycle_terminal:
        recommended_interval = MAX_INTERVAL_DAYS
        priority_mult = 0.0
        reason_codes = [f"lifecycle_terminal"]

        confidence = 1.0
        if confidence_factors:
            confidence = sum(confidence_factors) / len(confidence_factors)

        next_due = today + timedelta(days=recommended_interval)

        return AdaptiveVerificationPolicy(
            recommended_interval_days=recommended_interval,
            priority_multiplier=priority_mult,
            next_due_at=next_due,
            reason_codes=tuple(reason_codes),
            confidence=round(confidence, 3),
        )

    combined_factor = (
        health_factor
        * change_factor
        * latency_factor
        * failure_factor
        * deadline_factor
        * retry_factor
        * staleness_factor
        * lifecycle_factor
    )

    raw_interval = BASE_INTERVAL_DAYS * combined_factor
    recommended_interval = int(max(MIN_INTERVAL_DAYS, min(MAX_INTERVAL_DAYS, raw_interval)))

    priority_mult = _compute_priority_multiplier(
        health_status, deadline_factor, change_factor, lifecycle_terminal
    )

    if confidence_factors:
        confidence = sum(confidence_factors) / len(confidence_factors)
    else:
        confidence = 0.5

    next_due = today + timedelta(days=recommended_interval)

    return AdaptiveVerificationPolicy(
        recommended_interval_days=recommended_interval,
        priority_multiplier=priority_mult,
        next_due_at=next_due,
        reason_codes=tuple(reason_codes),
        confidence=round(confidence, 3),
    )


def compute_next_due_date(
    session: Session,
    scholarship: Scholarship,
    today: date | None = None,
) -> date:
    policy = compute_adaptive_policy(session, scholarship, today)
    return policy.next_due_at
