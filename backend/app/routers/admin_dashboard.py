"""Admin dashboard endpoints for maintenance and monitoring.

Provides private, authenticated endpoints for:
- Run statistics
- Scholarship status breakdown
- Verification queue depth
- Source health overview
- Image review pending count
- Discovery queue status
- Operational retry/terminal failure counts
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import (
    ApprovedSource,
    DiscoveryCandidate,
    ImageReview,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipReview,
    ScholarshipVerificationHistory,
    SourceHealth,
)
from ..services.source_health_service import classify_health_status, compute_reliability_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin_secret(provided_secret: str | None) -> bool:
    settings = get_settings()
    expected = getattr(settings, "admin_secret", None)
    if expected is None:
        return False
    if provided_secret is None:
        return False
    return provided_secret == expected


@router.get("/dashboard")
def get_dashboard(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Get comprehensive admin dashboard statistics.

    Returns counts and metrics for monitoring the autonomous system.
    """
    if not _verify_admin_secret(x_admin_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )

    now = datetime.now(timezone.utc)

    total_scholarships = session.scalar(select(func.count(Scholarship.id))) or 0

    status_counts: dict[str, int] = {}
    for row in session.query(Scholarship.status, func.count(Scholarship.id)).group_by(Scholarship.status).all():
        status_counts[row[0] or "unknown"] = row[1]

    open_count = status_counts.get("open", 0)
    upcoming_count = status_counts.get("upcoming", 0)
    closed_count = status_counts.get("closed", 0)
    closing_soon_count = status_counts.get("closing-soon", 0)

    verified_count = session.scalar(select(func.count(Scholarship.id)).where(Scholarship.is_verified.is_(True))) or 0
    unverified_count = total_scholarships - verified_count

    last_verified = session.scalar(
        select(func.max(Scholarship.last_verified_at))
    )

    pending_reviews = session.scalar(
        select(func.count(ScholarshipReview.id)).where(ScholarshipReview.decision == "pending")
    ) or 0

    pending_image_reviews = session.scalar(
        select(func.count(ImageReview.id)).where(ImageReview.decision == "pending")
    ) or 0

    pending_discovery = session.scalar(
        select(func.count(DiscoveryCandidate.id)).where(
            DiscoveryCandidate.status.in_("pending", "review")
        )
    ) or 0

    retrying_count = session.scalar(
        select(func.count(ScholarshipFetchAttempt.id)).where(
            ScholarshipFetchAttempt.status == "retrying"
        )
    ) or 0

    terminal_failures = session.scalar(
        select(func.count(ScholarshipFetchAttempt.id)).where(
            ScholarshipFetchAttempt.terminal.is_(True)
        )
    ) or 0

    total_fetch_attempts = session.scalar(
        select(func.count(ScholarshipFetchAttempt.id))
    ) or 0

    source_health_rows = session.scalars(select(SourceHealth)).all()
    healthy_sources = sum(1 for s in source_health_rows if s.health_status == "healthy")
    degraded_sources = sum(1 for s in source_health_rows if s.health_status == "degraded")
    unhealthy_sources = sum(1 for s in source_health_rows if s.health_status == "unhealthy")

    total_history = session.scalar(select(func.count(ScholarshipVerificationHistory.id))) or 0
    material_changes = session.scalar(
        select(func.count(ScholarshipVerificationHistory.id)).where(
            ScholarshipVerificationHistory.change_type != "unchanged"
        )
    ) or 0

    today_str = now.date().isoformat()
    verified_today = session.scalar(
        select(func.count(Scholarship.id)).where(Scholarship.last_verified_at == now.date())
    ) or 0

    due_today = session.scalar(
        select(func.count(Scholarship.id)).where(
            Scholarship.next_verification_due == now.date()
        )
    ) or 0

    return {
        "timestamp": now.isoformat(),
        "scholarships": {
            "total": total_scholarships,
            "open": open_count,
            "upcoming": upcoming_count,
            "closed": closed_count,
            "closing_soon": closing_soon_count,
            "verified": verified_count,
            "unverified": unverified_count,
            "last_verified_at": last_verified.isoformat() if last_verified else None,
        },
        "verification": {
            "verified_today": verified_today,
            "due_today": due_today,
            "pending_reviews": pending_reviews,
            "total_history_entries": total_history,
            "material_changes": material_changes,
        },
        "discovery": {
            "pending_candidates": pending_discovery,
        },
        "images": {
            "pending_reviews": pending_image_reviews,
        },
        "fetch": {
            "total_attempts": total_fetch_attempts,
            "retrying": retrying_count,
            "terminal_failures": terminal_failures,
        },
        "sources": {
            "total": len(source_health_rows),
            "healthy": healthy_sources,
            "degraded": degraded_sources,
            "unhealthy": unhealthy_sources,
        },
    }


@router.get("/dashboard/summary")
def get_dashboard_summary(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Get a lightweight dashboard summary."""
    if not _verify_admin_secret(x_admin_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )

    now = datetime.now(timezone.utc)
    total = session.scalar(select(func.count(Scholarship.id))) or 0

    status_breakdown = {}
    for row in session.query(Scholarship.status, func.count(Scholarship.id)).group_by(Scholarship.status).all():
        status_breakdown[row[0] or "unknown"] = row[1]

    pending_reviews = session.scalar(
        select(func.count(ScholarshipReview.id)).where(ScholarshipReview.decision == "pending")
    ) or 0

    pending_image_reviews = session.scalar(
        select(func.count(ImageReview.id)).where(ImageReview.decision == "pending")
    ) or 0

    return {
        "timestamp": now.isoformat(),
        "total_scholarships": total,
        "status_breakdown": status_breakdown,
        "pending_reviews": pending_reviews,
        "pending_image_reviews": pending_image_reviews,
    }


@router.get("/sources/health")
def get_source_health(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Get source health overview."""
    if not _verify_admin_secret(x_admin_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )

    sources = session.scalars(select(SourceHealth).order_by(SourceHealth.domain)).all()

    return {
        "sources": [
            {
                "domain": s.domain,
                "health_status": s.health_status,
                "reliability_score": s.reliability_score,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "consecutive_failures": s.consecutive_failures,
                "avg_latency_ms": s.avg_latency_ms,
                "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
                "last_failure_at": s.last_failure_at.isoformat() if s.last_failure_at else None,
                "manual_override": s.manual_override,
            }
            for s in sources
        ]
    }


@router.get("/queue/depth")
def get_queue_depth(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Get verification and discovery queue depths."""
    if not _verify_admin_secret(x_admin_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )

    today = date.today()
    due_count = session.scalar(
        select(func.count(Scholarship.id)).where(
            (Scholarship.next_verification_due <= today) | (Scholarship.next_verification_due.is_(None)),
            Scholarship.official_source_url.isnot(None),
        )
    ) or 0

    retrying_count = session.scalar(
        select(func.count(ScholarshipFetchAttempt.id)).where(
            ScholarshipFetchAttempt.status == "retrying"
        )
    ) or 0

    pending_discovery = session.scalar(
        select(func.count(DiscoveryCandidate.id)).where(
            DiscoveryCandidate.status.in_("pending", "review")
        )
    ) or 0

    return {
        "verification_due": due_count,
        "retrying": retrying_count,
        "pending_discovery": pending_discovery,
    }
