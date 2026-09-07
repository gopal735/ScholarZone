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
from dataclasses import dataclass

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


def run_verification_round() -> VerificationRoundResult:
    """Run a verification round.

    SAFETY: Returns a result with 0 jobs if the intelligent scheduler is frozen.
    This prevents production data mutations until the telemetry contract
    bug and transaction boundary are fixed.

    The scheduler engine is started, jobs are submitted and awaited to
    completion, and the engine is shut down before returning. This ensures
    that when the return value is produced, all background work is done
    and ``scheduler_running`` correctly reflects ``False``.
    """
    global _engine

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


def run_discovery_round(
    dry_run: bool = False,
    max_workers: int = 4,
) -> DiscoveryRoundResult:
    """Run a country-level new-scholarship discovery round.

    Discovers new scholarships for every country currently represented
    in the database, deduplicates against existing records, auto-approves
    verified pending candidates, and enqueues image discovery for newly
    inserted scholarships with NULL image_url.

    Args:
        dry_run: If True, reports expected inserts without mutating data.
        max_workers: Maximum concurrent country discovery workers.

    Returns:
        DiscoveryRoundResult with aggregate metrics.
    """
    scheduler = DiscoveryScheduler(
        dry_run=dry_run,
        max_workers=max_workers,
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
    )