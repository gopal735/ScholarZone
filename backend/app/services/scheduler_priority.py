"""Deterministic priority calculation for verification scheduling.

Per-record scoring, plus a batched loader so a queue of N candidates costs a
fixed number of queries instead of 5N.

The original implementation called five aggregate queries per scholarship from
inside ``calculate_priority``. At the configured batch size of 100 that is 500
round-trips to Neon every time a queue is filled, which is the single largest
source of avoidable database cost in the scheduled run.

The signals are unchanged. Only the way they are obtained changed:

* the per-record functions remain, with identical arithmetic, because several
  callers and the whole test suite depend on them;
* ``load_priority_signals`` collects the same five values for a whole batch in
  a fixed number of grouped queries, keyed by scholarship id (and by source url
  for fetch attempts, because reliability is a property of a *source*, shared
  by every record pointing at it);
* ``calculate_priority_from_signals`` is then pure arithmetic over that
  dictionary, so scoring a batch is free.

Anything that cannot be grouped is still computed the old way, one record at a
time, so an unknown signal degrades in cost rather than in correctness.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Integer, func, select
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


@dataclass(frozen=True)
class PrioritySignals:
    """Aggregated signals for a whole candidate batch.

    A missing key means "zero for that signal", which is how the per-record
    implementations behaved when the underlying rows did not exist.
    """

    change_counts_window: Mapping[int, int] = field(default_factory=dict)
    change_counts_all: Mapping[int, int] = field(default_factory=dict)
    # source_url -> (total attempts, terminal attempts)
    attempts_by_url: Mapping[str, tuple[int, int]] = field(default_factory=dict)
    # (scholarship_id, source_url) pairs with a retry due now
    retry_due: frozenset[tuple[int, str]] = frozenset()
    review_pending_ids: frozenset[int] = frozenset()


def _domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Signal loaders (batched)
# ---------------------------------------------------------------------------


def load_priority_signals(
    session: Session,
    scholarships: Sequence[Scholarship],
    today: date | None = None,
    config: SchedulerConfig | None = None,
) -> PrioritySignals:
    """Collect every priority signal for a batch in a fixed number of queries.

    Five queries regardless of how many candidates are passed in. The old path
    issued five per candidate.
    """
    config = config or SchedulerConfig()
    today = today or date.today()
    if not scholarships:
        return PrioritySignals()

    ids = [s.id for s in scholarships]
    urls = {s.official_source_url for s in scholarships if s.official_source_url}
    window_start = today - timedelta(days=config.change_frequency_window_days)

    # 1. change frequency, windowed.
    windowed = dict(
        session.execute(
            select(ScholarshipVerificationHistory.scholarship_id, func.count())
            .where(
                ScholarshipVerificationHistory.scholarship_id.in_(ids),
                ScholarshipVerificationHistory.change_type != "unchanged",
                ScholarshipVerificationHistory.created_at >= window_start,
            )
            .group_by(ScholarshipVerificationHistory.scholarship_id)
        ).all()
    )

    # 2. impact, all time.
    #
    # Deliberately NOT windowed. `compute_impact` defines a `window_start` and
    # then does not use it; that dead variable is either a bug or a stale
    # intention. No test and no specification covers it, and windowing it would
    # silently change the ranking of every record with an old history, so the
    # behaviour is preserved exactly and pinned by a regression test. Change it
    # deliberately, not as a side effect of an optimisation.
    all_time = dict(
        session.execute(
            select(ScholarshipVerificationHistory.scholarship_id, func.count())
            .where(
                ScholarshipVerificationHistory.scholarship_id.in_(ids),
                ScholarshipVerificationHistory.change_type != "unchanged",
            )
            .group_by(ScholarshipVerificationHistory.scholarship_id)
        ).all()
    )

    # 3. fetch attempts, grouped in SQL rather than loaded into Python.
    #
    # The old code did `.all()` on every attempt for a source and counted in
    # Python. That is a query returning an unbounded number of rows for a busy
    # source; the aggregate returns one row per source instead.
    attempts_by_url: dict[str, tuple[int, int]] = {}
    if urls:
        for url, total, terminal in session.execute(
            select(
                ScholarshipFetchAttempt.source_url,
                func.count(ScholarshipFetchAttempt.id),
                func.sum(func.cast(ScholarshipFetchAttempt.terminal, Integer)),
            )
            .where(ScholarshipFetchAttempt.source_url.in_(urls))
            .group_by(ScholarshipFetchAttempt.source_url)
        ).all():
            attempts_by_url[url] = (int(total or 0), int(terminal or 0))

    # 4. retries due now.
    retry_due: set[tuple[int, str]] = set()
    if urls:
        retry_due = {
            (int(sid), url)
            for sid, url in session.execute(
                select(ScholarshipFetchAttempt.scholarship_id, ScholarshipFetchAttempt.source_url)
                .where(
                    ScholarshipFetchAttempt.scholarship_id.in_(ids),
                    ScholarshipFetchAttempt.source_url.in_(urls),
                    ScholarshipFetchAttempt.status == "retrying",
                    ScholarshipFetchAttempt.next_retry_at <= func.now(),
                )
            ).all()
        }

    # 5. pending human reviews.
    review_pending_ids = frozenset(
        int(sid)
        for (sid,) in session.execute(
            select(ScholarshipReview.scholarship_id)
            .where(
                ScholarshipReview.scholarship_id.in_(ids),
                ScholarshipReview.decision == "pending",
            )
            .distinct()
        ).all()
    )

    return PrioritySignals(
        change_counts_window=windowed,
        change_counts_all=all_time,
        attempts_by_url=attempts_by_url,
        retry_due=frozenset(retry_due),
        review_pending_ids=review_pending_ids,
    )


# ---------------------------------------------------------------------------
# Pure scoring
# ---------------------------------------------------------------------------


def _capped_percentage(count: int, maximum: int) -> int:
    """Shared by change frequency and impact; identical arithmetic to before."""
    if maximum == 0:
        return 0
    capped = min(count, maximum)
    return int((capped / maximum) * 100)


def calculate_priority_from_signals(
    scholarship: Scholarship,
    signals: PrioritySignals,
    today: date | None = None,
    config: SchedulerConfig | None = None,
) -> PriorityScore:
    """Score one record from pre-aggregated signals. No database access."""
    config = config or SchedulerConfig()
    today = today or date.today()
    sid = scholarship.id

    return PriorityScore(
        scholarship_id=sid,
        staleness=compute_staleness(scholarship, today, config),
        deadline_urgency=compute_deadline_urgency(scholarship, today, config),
        change_frequency=_capped_percentage(
            signals.change_counts_window.get(sid, 0),
            config.change_frequency_max_count,
        ),
        source_reliability=_reliability_from_signals(scholarship, signals),
        retry_pending=_retry_from_signals(scholarship, signals),
        review_pending=100 if sid in signals.review_pending_ids else 0,
        impact=_capped_percentage(
            signals.change_counts_all.get(sid, 0),
            config.change_frequency_max_count,
        ),
    )


def _reliability_from_signals(scholarship: Scholarship, signals: PrioritySignals) -> int:
    if not scholarship.official_source_url:
        return 0
    pair = signals.attempts_by_url.get(scholarship.official_source_url)
    if not pair:
        return 50  # unknown source: neutral, as before
    total, terminal = pair
    if total == 0:
        return 50
    return int((terminal / total) * 100)


def _retry_from_signals(scholarship: Scholarship, signals: PrioritySignals) -> int:
    if not scholarship.official_source_url:
        return 0
    return 100 if (scholarship.id, scholarship.official_source_url) in signals.retry_due else 0


# ---------------------------------------------------------------------------
# Original per-record signals (unchanged behaviour)
# ---------------------------------------------------------------------------


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
    return _capped_percentage(int(count), config.change_frequency_max_count)


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
    """Impact from the record's full change history.

    See ``load_priority_signals`` for why the ``window_start`` below is
    deliberately unused.
    """
    window_start = today - timedelta(days=config.change_frequency_window_days)  # noqa: F841
    count = session.scalar(
        select(func.count(ScholarshipVerificationHistory.id))
        .where(
            ScholarshipVerificationHistory.scholarship_id == scholarship.id,
            ScholarshipVerificationHistory.change_type != "unchanged",
        )
    ) or 0
    return _capped_percentage(int(count), config.change_frequency_max_count)


def calculate_priority(session: Session, scholarship: Scholarship, today: date | None = None) -> PriorityScore:
    """Single-record scoring. Kept for existing callers; scoring a batch should
    use ``load_priority_signals`` + ``calculate_priority_from_signals``."""
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


def batch_calculate_priorities(
    session: Session,
    scholarships: Sequence[Scholarship],
    today: date | None = None,
) -> list[PriorityScore]:
    """Score a whole batch with a fixed query count."""
    config = SchedulerConfig()
    today = today or date.today()
    signals = load_priority_signals(session, scholarships, today, config)
    return [
        calculate_priority_from_signals(s, signals, today, config) for s in scholarships
    ]
