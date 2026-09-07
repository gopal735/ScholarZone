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

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..core.config import get_settings
from ..schemas import ScholarshipImageVerifyRequest
from ..services.image_validator import ImageCandidate, ImageValidator
from ..services.scholarship_image_verifier import ImageVerifier, is_valid_source_type
from ..scheduler_v2 import DiscoveryRoundResult, VerificationRoundResult, run_discovery_round, run_verification_round
from ..database import get_db

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


@router.post("/discover/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_discovery(
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    dry_run: bool = False,
    max_workers: int = 4,
) -> dict:
    """Trigger a country-level new-scholarship discovery round.

    This endpoint is designed to be called by cloud scheduler services
    alongside the verification trigger. Authentication is required via
    the X-Verification-Secret header.

    Returns 202 Accepted if the discovery round was initiated.
    Returns 401 Unauthorized if the secret is missing or invalid.
    Returns 503 Service Unavailable if the scheduler is not configured.
    """
    if not _verify_secret(x_verification_secret):
        logger.warning(
            "Unauthorized discovery trigger attempt from %s",
            "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    settings = get_settings()
    if settings.verification_secret is None:
        logger.error(
            "Verification secret not configured. "
            "Set SCHOLARZONE_VERIFICATION_SECRET environment variable."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery scheduler not configured.",
        )

    started_at = datetime.now(timezone.utc).isoformat()

    try:
        result: DiscoveryRoundResult = run_discovery_round(
            dry_run=dry_run,
            max_workers=max_workers,
        )
    except Exception as exc:
        logger.exception("Discovery round failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Discovery round failed.",
        )

    completed_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Discovery round completed. countries_scanned=%d inserted=%d duplicates=%d rejected=%d errors=%d images=%d started=%s completed=%s",
        result.countries_scanned,
        result.inserted_scholarships,
        result.duplicates,
        result.rejected_candidates,
        result.errors,
        result.image_discoveries_triggered,
        started_at,
        completed_at,
    )

    return {
        "status": "accepted",
        "dry_run": dry_run,
        "countries_scanned": result.countries_scanned,
        "inserted_scholarships": result.inserted_scholarships,
        "duplicates": result.duplicates,
        "rejected_candidates": result.rejected_candidates,
        "errors": result.errors,
        "image_discoveries_triggered": result.image_discoveries_triggered,
        "runtime_ms": result.runtime_ms,
        "started_at": started_at,
        "completed_at": completed_at,
    }


@router.post("/images/verify", status_code=status.HTTP_200_OK)
async def verify_image(
    payload: ScholarshipImageVerifyRequest,
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session = Depends(get_db),
) -> dict:
    """Persist a single HIGH-confidence image for a scholarship.

    Authentication:
    - Requires X-Verification-Secret header matching SCHOLARZONE_VERIFICATION_SECRET.

    Behavior:
    - Fetches the scholarship by ID.
    - Revalidates the provided image using the existing ImageValidator.
    - Requires HIGH confidence.
    - Rejects UI/logo/error/social/OG/generic/non-cover images.
    - Rejects HUMAN_REVIEW and REJECTED candidates.
    - Persists ONLY image fields via ImageVerifier.mark_image_verified().
    - Creates ScholarshipVerificationHistory audit for NULL -> image.
    - Idempotent: same image submitted again returns success without duplicate audit.
    - Invalid scholarship ID returns 404.
    """
    if not _verify_secret(x_verification_secret):
        logger.warning(
            "Unauthorized image verification attempt from %s",
            "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    from ..models import Scholarship

    scholarship = session.get(Scholarship, payload.scholarship_id)
    if scholarship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found.",
        )

    if not is_valid_source_type(payload.image_source_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image_source_type: {payload.image_source_type}",
        )

    candidate = ImageCandidate(
        image_url=payload.image_url,
        page_url=scholarship.official_source_url or payload.image_source_url,
        discovery_method="manual_verify",
        alt_text=payload.image_alt_text,
    )

    validator = ImageValidator(timeout=30.0)
    result = validator.validate_candidate(
        candidate,
        scholarship_title=scholarship.title,
        official_source_url=scholarship.official_source_url,
    )

    result.image_kind = validator._classify_image_kind(result)

    if result.confidence != "HIGH":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image confidence is {result.confidence}, required HIGH.",
        )

    if result.status.value not in ("approved",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image validation status is {result.status.value}, required approved.",
        )

    if result.is_generic_image or result.is_ui_asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image rejected as non-content (UI, logo, generic, or error asset).",
        )

    image_verifier = ImageVerifier(session)
    updated = image_verifier.mark_image_verified(
        scholarship_id=payload.scholarship_id,
        image_url=payload.image_url,
        image_source_url=payload.image_source_url,
        source_type=payload.image_source_type,
        alt_text=payload.image_alt_text,
        image_kind=payload.image_kind or result.image_kind,
    )

    if not updated:
        refreshed = session.get(Scholarship, payload.scholarship_id)
        if refreshed.image_url == payload.image_url and refreshed.image_source_url == payload.image_source_url:
            return {
                "status": "unchanged",
                "scholarship_id": payload.scholarship_id,
                "image_url": payload.image_url,
            }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image was not persisted.",
        )

    return {
        "status": "updated",
        "scholarship_id": payload.scholarship_id,
        "image_url": payload.image_url,
    }


@router.post("/images/revalidate", status_code=status.HTTP_200_OK)
async def revalidate_stored_image(
    payload: dict,
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session = Depends(get_db),
) -> dict:
    """Revalidate a persisted image against the current official page.

    Authentication:
    - Requires X-Verification-Secret header matching SCHOLARZONE_VERIFICATION_SECRET.

    Behavior:
    - Fetches the scholarship by ID.
    - If no image is stored, returns HUMAN_REVIEW without mutation.
    - Fetches the current official source page.
    - Checks whether the stored image is still present.
    - CURRENT: updates image_verified_at, writes lightweight audit record.
    - CHANGED / REMOVED / SOURCE_INACCESSIBLE: creates a pending ScholarshipReview
      (if one does not already exist) and writes a stale_detected audit record.
    - Never silently replaces or clears a verified image.
    - Idempotent: repeated identical runs do not create duplicate reviews or
      duplicate stale-detection history within 12 hours.
    """
    if not _verify_secret(x_verification_secret):
        logger.warning(
            "Unauthorized image revalidation attempt from %s",
            "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    from ..models import Scholarship

    scholarship_id = payload.get("scholarship_id")
    if scholarship_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scholarship_id is required.",
        )

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found.",
        )

    image_verifier = ImageVerifier(session)
    result = image_verifier.revalidate_stored_image(scholarship_id)

    return {
        "scholarship_id": result.scholarship_id,
        "status": result.status.value,
        "image_url": result.image_url,
        "official_source_url": result.official_source_url,
        "found_image_urls": result.found_image_urls,
        "evidence": result.evidence,
        "action_taken": result.action_taken,
    }
