"""Source health intelligence service.

Derives health metrics, reliability scores, and health status from
persisted fetch-attempt data. No network requests. No duplicated state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from ..models import ScholarshipFetchAttempt, SourceHealth

logger = logging.getLogger(__name__)

HEALTHY = "healthy"
DEGRADED = "degraded"
UNHEALTHY = "unhealthy"
UNKNOWN = "unknown"

HEALTH_STATES = frozenset({HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN})

DEFAULT_RELIABILITY_THRESHOLD_HEALTHY = 80.0
DEFAULT_RELIABILITY_THRESHOLD_DEGRADED = 50.0
DEFAULT_CONSECUTIVE_FAILURES_DEGRADED = 3
DEFAULT_CONSECUTIVE_FAILURES_UNHEALTHY = 5
DEFAULT_MIN_ATTEMPTS_FOR_KNOWN = 3


@dataclass(frozen=True)
class HealthConfig:
    reliability_threshold_healthy: float = DEFAULT_RELIABILITY_THRESHOLD_HEALTHY
    reliability_threshold_degraded: float = DEFAULT_RELIABILITY_THRESHOLD_DEGRADED
    consecutive_failures_degraded: int = DEFAULT_CONSECUTIVE_FAILURES_DEGRADED
    consecutive_failures_unhealthy: int = DEFAULT_CONSECUTIVE_FAILURES_UNHEALTHY
    min_attempts_for_known: int = DEFAULT_MIN_ATTEMPTS_FOR_KNOWN
    window_days: int = 30


def extract_domain(source_url: str) -> str | None:
    if not source_url:
        return None
    try:
        parsed = urlparse(source_url.strip())
        return parsed.netloc.lower() if parsed.netloc else None
    except Exception:
        return None


def compute_reliability_score(
    success_count: int,
    failure_count: int,
    timeout_count: int,
    rate_limit_count: int,
    consecutive_failures: int,
    total_count: int,
) -> float:
    if total_count == 0:
        return 0.0

    success_ratio = success_count / total_count

    if failure_count > 0:
        failure_ratio = failure_count / total_count
    else:
        failure_ratio = 0.0

    if timeout_count > 0:
        timeout_ratio = timeout_count / total_count
    else:
        timeout_ratio = 0.0

    if rate_limit_count > 0:
        rate_limit_ratio = rate_limit_count / total_count
    else:
        rate_limit_ratio = 0.0

    recency_factor = max(0.0, 1.0 - (consecutive_failures * 0.15))

    base_score = success_ratio * 100.0
    penalty = (failure_ratio * 30.0) + (timeout_ratio * 20.0) + (rate_limit_ratio * 15.0)
    consecutive_penalty = min(30.0, consecutive_failures * 5.0)

    score = (base_score - penalty - consecutive_penalty) * (0.7 + 0.3 * recency_factor)

    return max(0.0, min(100.0, score))


def classify_health_status(
    reliability_score: float,
    total_count: int,
    consecutive_failures: int,
    config: HealthConfig,
) -> str:
    if total_count == 0:
        return UNKNOWN

    if total_count < config.min_attempts_for_known:
        if consecutive_failures >= config.consecutive_failures_unhealthy:
            return UNHEALTHY
        if consecutive_failures >= config.consecutive_failures_degraded:
            return DEGRADED
        return UNKNOWN

    if consecutive_failures >= config.consecutive_failures_unhealthy:
        return UNHEALTHY

    if reliability_score >= config.reliability_threshold_healthy:
        if consecutive_failures < config.consecutive_failures_degraded:
            return HEALTHY
        return DEGRADED

    if reliability_score >= config.reliability_threshold_degraded:
        return DEGRADED

    return UNHEALTHY


def get_source_health(session: Session, domain: str) -> SourceHealth | None:
    return session.scalar(
        select(SourceHealth).where(SourceHealth.domain == domain)
    )


def get_all_source_health(session: Session) -> list[SourceHealth]:
    return list(session.scalars(select(SourceHealth)).all())


def refresh_all_source_health(
    session: Session,
    config: HealthConfig | None = None,
    now: datetime | None = None,
) -> list[SourceHealth]:
    config = config or HealthConfig()
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(days=config.window_days)

    domains = _aggregate_domains(session, window_start)

    all_domains = set(domains.keys())
    existing_domains = session.execute(
        select(SourceHealth.domain)
    ).scalars().all()
    for d in existing_domains:
        if d:
            all_domains.add(d)

    results = []
    for domain in sorted(all_domains):
        metrics = domains.get(domain, _empty_metrics())
        health = _upsert_health(session, domain, metrics, config, now)
        results.append(health)

    session.flush()
    return results


def refresh_source_health(
    session: Session,
    domain: str,
    config: HealthConfig | None = None,
    now: datetime | None = None,
) -> SourceHealth:
    config = config or HealthConfig()
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(days=config.window_days)

    metrics = _aggregate_single_domain(session, domain, window_start)
    health = _upsert_health(session, domain, metrics, config, now)
    session.flush()
    return health


def get_domain_for_source_url(session: Session, source_url: str) -> str | None:
    domain = extract_domain(source_url)
    if domain is None:
        return None
    return domain


def is_source_healthy(
    session: Session,
    domain: str,
    config: HealthConfig | None = None,
) -> bool:
    health = get_source_health(session, domain)
    if health is None:
        return True
    if health.manual_override is not None:
        return health.manual_override == HEALTHY
    return health.health_status in (HEALTHY, UNKNOWN)


def _domain_filter(domain: str):
    """Create a filter that matches source_url belonging to the given domain.
    
    Matches URLs where the domain appears as a complete hostname component,
    not as a substring of a larger domain.
    """
    return or_(
        ScholarshipFetchAttempt.source_url.like(f"%://{domain}/%"),
        ScholarshipFetchAttempt.source_url.like(f"%://{domain}"),
    )


def _aggregate_domains(
    session: Session,
    window_start: datetime,
) -> dict[str, _DomainMetrics]:
    rows = session.execute(
        select(
            ScholarshipFetchAttempt.source_url,
            func.count().label("total"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.status == "resolved", 1),
                    else_=0,
                )
            ).label("successes"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.status == "terminal", 1),
                    else_=0,
                )
            ).label("terminals"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.last_error_type == "timeout", 1),
                    else_=0,
                )
            ).label("timeouts"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.last_error_type == "rate_limited", 1),
                    else_=0,
                )
            ).label("rate_limits"),
            func.max(ScholarshipFetchAttempt.last_attempt_at).label("last_attempt"),
        )
        .where(ScholarshipFetchAttempt.last_attempt_at >= window_start)
        .group_by(ScholarshipFetchAttempt.source_url)
    ).all()

    by_domain: dict[str, _DomainMetrics] = {}
    for row in rows:
        domain = extract_domain(row.source_url)
        if domain is None:
            continue

        if domain not in by_domain:
            by_domain[domain] = _DomainMetrics()

        m = by_domain[domain]
        m.total += row.total or 0
        m.successes += row.successes or 0
        m.terminals += row.terminals or 0
        m.timeouts += row.timeouts or 0
        m.rate_limits += row.rate_limits or 0
        if row.last_attempt:
            if m.last_attempt_at is None or row.last_attempt > m.last_attempt_at:
                m.last_attempt_at = row.last_attempt

    for domain in by_domain:
        m = by_domain[domain]
        m.consecutive_failures = _compute_consecutive_failures(session, domain, window_start)
        m.last_success_at = _compute_last_success(session, domain, window_start)
        m.last_failure_at = _compute_last_failure(session, domain, window_start)

    return by_domain


def _aggregate_single_domain(
    session: Session,
    domain: str,
    window_start: datetime,
) -> _DomainMetrics:
    row = session.execute(
        select(
            func.count().label("total"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.status == "resolved", 1),
                    else_=0,
                )
            ).label("successes"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.status == "terminal", 1),
                    else_=0,
                )
            ).label("terminals"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.last_error_type == "timeout", 1),
                    else_=0,
                )
            ).label("timeouts"),
            func.sum(
                case(
                    (ScholarshipFetchAttempt.last_error_type == "rate_limited", 1),
                    else_=0,
                )
            ).label("rate_limits"),
            func.max(ScholarshipFetchAttempt.last_attempt_at).label("last_attempt"),
        )
        .where(
            _domain_filter(domain),
            ScholarshipFetchAttempt.last_attempt_at >= window_start,
        )
    ).first()

    m = _DomainMetrics()
    if row and row.total:
        m.total = row.total or 0
        m.successes = row.successes or 0
        m.terminals = row.terminals or 0
        m.timeouts = row.timeouts or 0
        m.rate_limits = row.rate_limits or 0
        m.last_attempt_at = row.last_attempt

    m.consecutive_failures = _compute_consecutive_failures(session, domain, window_start)
    m.last_success_at = _compute_last_success(session, domain, window_start)
    m.last_failure_at = _compute_last_failure(session, domain, window_start)

    return m


def _compute_consecutive_failures(
    session: Session,
    domain: str,
    window_start: datetime,
) -> int:
    attempts = session.scalars(
        select(ScholarshipFetchAttempt)
        .where(
            _domain_filter(domain),
            ScholarshipFetchAttempt.last_attempt_at >= window_start,
        )
        .order_by(ScholarshipFetchAttempt.last_attempt_at.desc())
    ).all()

    count = 0
    for attempt in attempts:
        if attempt.status == "resolved":
            break
        count += 1
    return count


def _compute_last_success(
    session: Session,
    domain: str,
    window_start: datetime,
) -> datetime | None:
    row = session.scalar(
        select(func.max(ScholarshipFetchAttempt.last_attempt_at))
        .where(
            _domain_filter(domain),
            ScholarshipFetchAttempt.status == "resolved",
            ScholarshipFetchAttempt.last_attempt_at >= window_start,
        )
    )
    return row


def _compute_last_failure(
    session: Session,
    domain: str,
    window_start: datetime,
) -> datetime | None:
    row = session.scalar(
        select(func.max(ScholarshipFetchAttempt.last_attempt_at))
        .where(
            _domain_filter(domain),
            ScholarshipFetchAttempt.status.in_(("terminal", "retrying")),
            ScholarshipFetchAttempt.last_attempt_at >= window_start,
        )
    )
    return row


def _upsert_health(
    session: Session,
    domain: str,
    metrics: _DomainMetrics,
    config: HealthConfig,
    now: datetime,
) -> SourceHealth:
    existing = session.scalar(
        select(SourceHealth).where(SourceHealth.domain == domain)
    )

    if existing is None:
        existing = SourceHealth(domain=domain)
        session.add(existing)

    total = metrics.total
    successes = metrics.successes

    existing.success_count = successes
    existing.failure_count = total - successes
    existing.timeout_count = metrics.timeouts
    existing.rate_limit_count = metrics.rate_limits
    existing.terminal_failure_count = metrics.terminals
    existing.consecutive_failures = metrics.consecutive_failures
    existing.last_success_at = metrics.last_success_at
    existing.last_failure_at = metrics.last_failure_at
    existing.computed_at = now

    reliability = compute_reliability_score(
        success_count=successes,
        failure_count=total - successes,
        timeout_count=metrics.timeouts,
        rate_limit_count=metrics.rate_limits,
        consecutive_failures=metrics.consecutive_failures,
        total_count=total,
    )
    existing.reliability_score = reliability

    if existing.manual_override is not None:
        existing.health_status = existing.manual_override
    else:
        existing.health_status = classify_health_status(
            reliability_score=reliability,
            total_count=total,
            consecutive_failures=metrics.consecutive_failures,
            config=config,
        )

    return existing


def _empty_metrics() -> _DomainMetrics:
    return _DomainMetrics()


class _DomainMetrics:
    def __init__(self) -> None:
        self.total: int = 0
        self.successes: int = 0
        self.terminals: int = 0
        self.timeouts: int = 0
        self.rate_limits: int = 0
        self.consecutive_failures: int = 0
        self.last_attempt_at: datetime | None = None
        self.last_success_at: datetime | None = None
        self.last_failure_at: datetime | None = None
