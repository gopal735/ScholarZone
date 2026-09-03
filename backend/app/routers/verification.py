"""Secure verification trigger endpoints for cloud scheduler integration.

This router exposes an authenticated endpoint that cloud cron services
(Google Cloud Scheduler, AWS EventBridge, Render Cron, etc.) can call
to trigger scholarship verification rounds.

Security:
- Requires a shared secret via X-Verification-Secret header
- Returns minimal information to prevent information leakage
- Idempotent: concurrent requests are safely handled by the scheduler engine
- Rate-limited by design: cloud cron services control frequency
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status

from ..core.config import get_settings
from ..scheduler_v2 import VerificationRoundResult, run_verification_round

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])

_last_execution_time: float | None = None
_min_interval_seconds: float = 60.0


def _verify_secret(provided_secret: str | None) -> bool:
    """Validate the provided secret against the configured verification secret."""
    settings = get_settings()
    expected = settings.verification_secret
    if expected is None:
        return False
    if provided_secret is None:
        return False
    return provided_secret == expected


@router.post("/verify/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_verification(
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
) -> dict:
    """Trigger a verification round.

    This endpoint is designed to be called by cloud scheduler services.
    Authentication is required via the X-Verification-Secret header.

    Returns 202 Accepted if the verification round was initiated.
    Returns 401 Unauthorized if the secret is missing or invalid.
    Returns 429 Too Many Requests if called too frequently.
    Returns 503 Service Unavailable if the scheduler is not configured.
    """
    global _last_execution_time

    if not _verify_secret(x_verification_secret):
        logger.warning(
            "Unauthorized verification trigger attempt from %s",
            "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    now = time.time()
    if _last_execution_time is not None:
        elapsed = now - _last_execution_time
        if elapsed < _min_interval_seconds:
            logger.warning(
                "Verification trigger rate-limited. Last execution %.1fs ago.",
                elapsed,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Minimum interval between triggers is {_min_interval_seconds}s.",
            )

    _last_execution_time = now

    settings = get_settings()
    if settings.verification_secret is None:
        logger.error(
            "Verification secret not configured. "
            "Set SCHOLARZONE_VERIFICATION_SECRET environment variable."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification scheduler not configured.",
        )

    started_at = datetime.now(timezone.utc).isoformat()

    try:
        result: VerificationRoundResult = run_verification_round()
    except Exception as exc:
        logger.exception("Verification round failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification round failed.",
        )

    completed_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Verification round completed. jobs_submitted=%d jobs_completed=%d jobs_failed=%d started=%s completed=%s",
        result.jobs_submitted,
        result.jobs_completed,
        result.jobs_failed,
        started_at,
        completed_at,
    )

    return {
        "status": "accepted",
        "jobs_submitted": result.jobs_submitted,
        "jobs_completed": result.jobs_completed,
        "jobs_failed": result.jobs_failed,
        "started_at": started_at,
        "completed_at": completed_at,
    }


@router.get("/verify/status")
async def verification_status() -> dict:
    """Get current verification scheduler status.

    This endpoint is unauthenticated and safe to call for health checks.
    It returns only non-sensitive operational status.
    """
    from ..scheduler_v2 import get_engine

    engine = get_engine()

    return {
        "scheduler_running": engine.is_running if engine else False,
        "last_trigger_time": (
            datetime.fromtimestamp(_last_execution_time, tz=timezone.utc).isoformat()
            if _last_execution_time
            else None
        ),
        "min_trigger_interval_seconds": _min_interval_seconds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
