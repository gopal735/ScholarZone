"""Deterministic priority calculation for verification scheduling."""

from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Scholarship, ScholarshipFetchAttempt, ScholarshipReview, ScholarshipVerificationHistory
from .scheduler_config import SchedulerConfig


@dataclass(frozen=True)
class PriorityScore:
    scholarship_id: int
    staleness: int = 0
    deadline_urgency: int = 0
    change_frequency: int = 0
    source_reliability: int = 0
    retry_pending: int = 0
    review_pending: int = 0
    impact: int = 0

    @property
    def total(self) -> int:
        cfg = SchedulerConfig()
        return (
            self.staleness * cfg.staleness_weight
            + self.deadline_urgency * cfg.deadline_urgency_weight
            + self.change_frequency * cfg.change_frequency_weight
            + self.source_reliability * cfg.source_reliability_weight
            + self.retry_pending * cfg.retry_pending_weight
            + self.review_pending * cfg.review_pending_weight
            + self.impact * cfg.impact_weight
        )

    def to_sort_key(self) -> tuple:
        return (-self.total, -self.deadline_urgency, -self.staleness, self.scholarship_id)


def _domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def compute_staleness(scholarship: Scholarship, today: date, config: SchedulerConfig) -> int:
    if scholarship.next_verification_due is None:
        return 100
    delta = (today - scholarship.next_verification_due).days
    if delta <= 0:
        return 0
    capped = min(delta, config.staleness_max_days)
    return int((capped / config.staleness_max_days) * 100)


def compute_deadline_urgency(scholarship: Scholarship, today: date, config: SchedulerConfig) -> int:
    if scholarship.deadline_date is None:
        return 0
    delta = (scholarship.deadline_date - today).days
    if delta < 0:
        return 0
    if delta > config.deadline_urgency_window_days:
        return 0
    window = config.deadline_urgency_window_days
    return int(((window - delta) / window) * 100)


def compute_change_frequency(session: Session, scholarship: Scholarship, today: date, config: SchedulerConfig) -> int:
    window_start = today - timedelta(days=config.change_frequency_window_days)
    count = session.scalar(
        select(func.count(ScholarshipVerificationHistory.id))
        .where(
            ScholarshipVerificationHistory.scholarship_id == scholarship.id,
            ScholarshipVerificationHistory.change_type != "unchanged",
            ScholarshipVerificationHistory.created_at >= window_start,
        )
    ) or 0
    capped = min(count, config.change_frequency_max_count)
    if config.change_frequency_max_count == 0:
        return 0
    return int((capped / config.change_frequency_max_count) * 100)


def compute_source_reliability(session: Session, scholarship: Scholarship) -> int:
    if not scholarship.official_source_url:
        return 0
    attempts = (
        session.query(ScholarshipFetchAttempt)
        .filter(ScholarshipFetchAttempt.source_url == scholarship.official_source_url)
        .all()
    )
    if not attempts:
        return 50
    total = len(attempts)
    terminal = sum(1 for a in attempts if a.terminal)
    if total == 0:
        return 50
    failure_rate = terminal / total
    return int(failure_rate * 100)


def compute_retry_pending(session: Session, scholarship: Scholarship, today: date) -> int:
    if not scholarship.official_source_url:
        return 0
    stmt = (
        select(ScholarshipFetchAttempt)
        .where(
            ScholarshipFetchAttempt.scholarship_id == scholarship.id,
            ScholarshipFetchAttempt.source_url == scholarship.official_source_url,
            ScholarshipFetchAttempt.status == "retrying",
            ScholarshipFetchAttempt.next_retry_at <= func.now(),
        )
    )
    due = session.scalars(stmt).first()
    return 100 if due is not None else 0


def compute_review_pending(session: Session, scholarship: Scholarship) -> int:
    count = session.scalar(
        select(func.count(ScholarshipReview.id))
        .where(
            ScholarshipReview.scholarship_id == scholarship.id,
            ScholarshipReview.decision == "pending",
        )
    ) or 0
    return 100 if count > 0 else 0


def compute_impact(session: Session, scholarship: Scholarship, today: date, config: SchedulerConfig) -> int:
    window_start = today - timedelta(days=config.change_frequency_window_days)
    count = session.scalar(
        select(func.count(ScholarshipVerificationHistory.id))
        .where(
            ScholarshipVerificationHistory.scholarship_id == scholarship.id,
            ScholarshipVerificationHistory.change_type != "unchanged",
        )
    ) or 0
    capped = min(count, config.change_frequency_max_count)
    if config.change_frequency_max_count == 0:
        return 0
    return int((capped / config.change_frequency_max_count) * 100)


def calculate_priority(session: Session, scholarship: Scholarship, today: date | None = None) -> PriorityScore:
    config = SchedulerConfig()
    if today is None:
        today = date.today()

    return PriorityScore(
        scholarship_id=scholarship.id,
        staleness=compute_staleness(scholarship, today, config),
        deadline_urgency=compute_deadline_urgency(scholarship, today, config),
        change_frequency=compute_change_frequency(session, scholarship, today, config),
        source_reliability=compute_source_reliability(session, scholarship),
        retry_pending=compute_retry_pending(session, scholarship, today),
        review_pending=compute_review_pending(session, scholarship),
        impact=compute_impact(session, scholarship, today, config),
    )
