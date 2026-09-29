"""Integration point for the intelligent verification scheduler.

Replaces the simple time-based scheduler with a priority-driven,
bounded-concurrency engine that respects retry state and source isolation.

SAFETY FREEZE: The intelligent scheduler is currently frozen due to a
production data mutation bug. See telemetry contract fix in
services/telemetry.py (record_retry, record_terminal_failure).
"""

from __future__ import annotations

import logging
from datetime import date
from dataclasses import dataclass, field

from .database import get_session_factory
from .services.discovery_scheduler import DiscoveryScheduler
from .services.scheduler_config import SchedulerConfig
from .services.scheduler_engine import SchedulerEngine

logger = logging.getLogger(__name__)


_engine: SchedulerEngine | None = None


@dataclass
class VerificationRoundResult:
    """Result of a verification round."""

    jobs_submitted: int
    jobs_completed: int
    jobs_failed: int
    dry_run: bool = False
    planned_candidates: int = 0
    due_retries: int = 0

    def as_dict(self) -> dict:
        """Machine-readable result for the maintenance run record.

        Without this the worker had to fall back to ``str(result)`` and the
        persisted run carried a dataclass repr instead of numbers, so a
        scheduled run left no queryable evidence that it had done anything.
        """
        return {
            "jobs_submitted": self.jobs_submitted,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "dry_run": self.dry_run,
            "planned_candidates": self.planned_candidates,
            "due_retries": self.due_retries,
        }


# SAFETY FREEZE: Set to False to enable the intelligent scheduler.
# Telemetry bug fixed, transaction boundary verified, regression tests pass.
# Controlled rollout in progress (batch_size=3).
_INTELLIGENT_SCHEDULER_FROZEN = False


def create_engine(
    config: SchedulerConfig | None = None,
) -> SchedulerEngine:
    return SchedulerEngine(
        session_factory=get_session_factory(),
        config=config,
    )


def start_scheduler(config: SchedulerConfig | None = None) -> SchedulerEngine:
    global _engine
    if _engine is not None and _engine.is_running:
        return _engine
    _engine = create_engine(config)
    _engine.start()
    return _engine


def get_engine() -> SchedulerEngine | None:
    return _engine


def shutdown_scheduler() -> None:
    global _engine
    if _engine is not None:
        _engine.shutdown(wait=True)
        _engine = None


def plan_verification_round(batch_size: int = 100) -> VerificationRoundResult:
    """Report the work a verification round would do, without doing it.

    The engine commits on every verified record and on retry processing, so a
    "dry run" that still called it was not a dry run. This reads the candidate
    set and the due-retry count only, which makes ``--dry-run`` genuinely
    side-effect free and therefore safe to point at production.
    """
    from sqlalchemy import func, select

    from .models import Scholarship, ScholarshipFetchAttempt

    session = get_session_factory()()
    try:
        today = date.today()
        candidates = session.scalar(
            select(func.count(Scholarship.id)).where(
                Scholarship.official_source_url.isnot(None),
                (Scholarship.next_verification_due <= today)
                | (Scholarship.next_verification_due.is_(None)),
            )
        ) or 0
        retries = session.scalar(
            select(func.count(ScholarshipFetchAttempt.id)).where(
                ScholarshipFetchAttempt.status == "retrying",
                ScholarshipFetchAttempt.next_retry_at <= func.now(),
                ScholarshipFetchAttempt.attempt_count < ScholarshipFetchAttempt.max_attempts,
            )
        ) or 0
        return VerificationRoundResult(
            jobs_submitted=0,
            jobs_completed=0,
            jobs_failed=0,
            dry_run=True,
            planned_candidates=int(candidates),
            due_retries=int(retries),
        )
    finally:
        session.close()


def run_verification_round(dry_run: bool = False) -> VerificationRoundResult:
    """Run a verification round.

    SAFETY: Returns a result with 0 jobs if the intelligent scheduler is frozen.
    This prevents production data mutations until the telemetry contract
    bug and transaction boundary are fixed.

    The scheduler engine is started, jobs are submitted and awaited to
    completion, and the engine is shut down before returning. This ensures
    that when the return value is produced, all background work is done
    and ``scheduler_running`` correctly reflects ``False``.

    When ``dry_run`` is set this returns the plan only and writes nothing.
    """
    global _engine

    if dry_run:
        return plan_verification_round()

    if _INTELLIGENT_SCHEDULER_FROZEN:
        logger.warning(
            "Intelligent scheduler is FROZEN. "
            "run_verification_round() returned 0 to prevent production mutations. "
            "Set _INTELLIGENT_SCHEDULER_FROZEN = False after fixing the telemetry bug."
        )
        return VerificationRoundResult(jobs_submitted=0, jobs_completed=0, jobs_failed=0)

    if _engine is None:
        start_scheduler()
    assert _engine is not None

    _engine.process_due_retries()
    submitted = _engine.submit_batch()

    _engine.wait_for_completion()

    completed = _engine.completed_count
    failed = _engine.failed_count

    _engine.shutdown(wait=True)
    _engine = None

    return VerificationRoundResult(
        jobs_submitted=submitted,
        jobs_completed=completed,
        jobs_failed=failed,
    )


@dataclass
class DiscoveryRoundResult:
    countries_scanned: int
    inserted_scholarships: int
    duplicates: int
    rejected_candidates: int
    errors: int
    image_discoveries_triggered: int
    runtime_ms: float
    dry_run: bool = False
    # Ids created this round, so the caller can assess them right away instead
    # of waiting for a cursor sweep to reach a new high id.
    inserted_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "countries_scanned": self.countries_scanned,
            "inserted_scholarships": self.inserted_scholarships,
            "duplicates": self.duplicates,
            "rejected_candidates": self.rejected_candidates,
            "errors": self.errors,
            "image_discoveries_triggered": self.image_discoveries_triggered,
            "runtime_ms": round(self.runtime_ms, 1),
            "dry_run": self.dry_run,
            "inserted_ids": list(self.inserted_ids),
        }


def run_discovery_round(
    dry_run: bool = False,
    max_workers: int = 4,
    crawl_budget=None,
) -> DiscoveryRoundResult:
    """Run a country-level new-scholarship discovery round.

    Discovers new scholarships for every country currently represented
    in the database, deduplicates against existing records, auto-approves
    verified pending candidates, and enqueues image discovery for newly
    inserted scholarships with NULL image_url.

    Args:
        dry_run: If True, reports expected inserts without mutating data.
        max_workers: Maximum concurrent country discovery workers.
        crawl_budget: Optional ``CrawlBudget`` enabling bounded deep
            crawling. Without it each seed URL is fetched once and not
            followed, which is why a deep round needs one to see anything
            below a portal's front page.

    Returns:
        DiscoveryRoundResult with aggregate metrics.
    """
    scheduler = DiscoveryScheduler(
        dry_run=dry_run,
        max_workers=max_workers,
        crawl_budget=crawl_budget,
    )
    metrics = scheduler.run()

    return DiscoveryRoundResult(
        countries_scanned=metrics.countries_scanned,
        inserted_scholarships=metrics.inserted_scholarships,
        duplicates=metrics.duplicates,
        rejected_candidates=metrics.rejected_candidates,
        errors=metrics.errors,
        image_discoveries_triggered=metrics.image_discoveries_triggered,
        runtime_ms=metrics.runtime_ms,
        inserted_ids=list(metrics.inserted_ids),
    )