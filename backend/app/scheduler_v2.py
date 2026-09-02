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

from .database import get_session_factory
from .services.scheduler_config import SchedulerConfig
from .services.scheduler_engine import SchedulerEngine

logger = logging.getLogger(__name__)

_engine: SchedulerEngine | None = None

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


def run_verification_round() -> int:
    """Run a verification round.

    SAFETY: Returns 0 immediately if the intelligent scheduler is frozen.
    This prevents production data mutations until the telemetry contract
    bug and transaction boundary are fixed.
    """
    if _INTELLIGENT_SCHEDULER_FROZEN:
        logger.warning(
            "Intelligent scheduler is FROZEN. "
            "run_verification_round() returned 0 to prevent production mutations. "
            "Set _INTELLIGENT_SCHEDULER_FROZEN = False after fixing the telemetry bug."
        )
        return 0
    if _engine is None:
        start_scheduler()
    assert _engine is not None
    _engine.process_due_retries()
    return _engine.submit_batch()
