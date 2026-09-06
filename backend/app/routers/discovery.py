"""Discovery endpoints for autonomous scholarship discovery.

Exposes endpoints for:
- Next-cycle discovery for CLOSED scholarships
- Country-scoped new scholarship discovery
- Discovery candidate management (approve/reject/list)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import ApprovedSource, DiscoveryCandidate, Scholarship
from ..services.discovery_pipeline import DiscoveryPipeline
from ..services.lifecycle_manager import apply_lifecycle_transition, evaluate_lifecycle
from ..services.next_cycle_discovery import (
    NextCycleDiscoveryResult,
    batch_discover_next_cycles,
    discover_next_cycle,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/discover", tags=["discovery"])


def _verify_secret(provided_secret: str | None) -> bool:
    settings = get_settings()
    expected = settings.verification_secret
    if expected is None:
        return False
    if provided_secret is None:
        return False
    return provided_secret == expected


@router.post("/next-cycle")
def discover_next_cycle_endpoint(
    scholarship_id: int = Query(ge=1),
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Discover the next application cycle for a CLOSED scholarship.

    Searches the official source for next-cycle announcements.
    Only marks as UPCOMING when an official call/announcement exists.
    """
    if not _verify_secret(x_verification_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found.",
        )

    if scholarship.status != "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scholarship status is {scholarship.status}, expected closed.",
        )

    result = discover_next_cycle(session, scholarship)

    if result.discovered and result.proposed_status == "upcoming":
        evaluation = evaluate_lifecycle(scholarship, verification_result={"fetch_status": "success"})
        if evaluation.should_transition:
            transition = apply_lifecycle_transition(
                session, scholarship, evaluation, source_url=scholarship.official_source_url
            )
            session.commit()
            return {
                "scholarship_id": scholarship_id,
                "discovered": True,
                "next_cycle_year": result.next_cycle_year,
                "confidence": result.confidence,
                "evidence": result.evidence,
                "transitioned": transition is not None,
                "new_status": scholarship.status,
            }

    return {
        "scholarship_id": scholarship_id,
        "discovered": result.discovered,
        "next_cycle_year": result.next_cycle_year,
        "confidence": result.confidence,
        "evidence": result.evidence,
        "transitioned": False,
        "new_status": scholarship.status,
    }


@router.post("/batch-next-cycle")
def batch_next_cycle_endpoint(
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Discover next cycles for all CLOSED scholarships due for recheck."""
    if not _verify_secret(x_verification_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    today = datetime.now(timezone.utc).date()
    closed_scholarships = session.scalars(
        select(Scholarship).where(
            Scholarship.status == "closed",
            (Scholarship.next_verification_due <= today) | (Scholarship.next_verification_due.is_(None)),
        )
    ).all()

    ids = [s.id for s in closed_scholarships]
    results = batch_discover_next_cycles(session, ids)
    session.commit()

    discovered = [r for r in results if r.discovered]
    return {
        "total_checked": len(results),
        "discovered": len(discovered),
        "results": [
            {
                "scholarship_id": r.scholarship_id,
                "discovered": r.discovered,
                "next_cycle_year": r.next_cycle_year,
                "confidence": r.confidence,
                "proposed_status": r.proposed_status,
                "evidence": r.evidence,
            }
            for r in results
        ],
    }


@router.post("/country/{country}")
def discover_country_scholarships(
    country: str,
    limit: int = Query(default=20, ge=1, le=100),
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Discover new scholarships for a specific country.

    Searches approved official sources for the given country
    and creates discovery candidates for genuinely new programmes.
    """
    if not _verify_secret(x_verification_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    seed_approved_sources(session)
    session.commit()

    sources = session.scalars(
        select(ApprovedSource).where(
            ApprovedSource.is_active.is_(True),
            ApprovedSource.country.ilike(country),
        )
    ).all()

    if not sources:
        return {
            "country": country,
            "sources_checked": 0,
            "discovered": 0,
            "duplicates": 0,
            "rejected": 0,
            "errors": 0,
        }

    pipeline = DiscoveryPipeline(session_factory=None)
    pipeline.now_fn = lambda: datetime.now(timezone.utc)

    all_urls: list[str] = []
    for source in sources:
        patterns = source.discovery_url_patterns or []
        if patterns:
            all_urls.extend(patterns)
        else:
            all_urls.append(f"https://{source.domain}/")

    all_urls = list(dict.fromkeys(all_urls))[:limit]

    discovered = 0
    duplicates = 0
    rejected = 0
    errors = 0

    for url in all_urls:
        try:
            result = pipeline.discover_from_url(url)
            if result.match_type in ("exact_url", "exact_candidate", "near_duplicate", "alias"):
                duplicates += 1
            elif result.status == "rejected":
                rejected += 1
            elif result.status in ("pending", "approved"):
                discovered += 1
            else:
                errors += 1
        except Exception as exc:
            logger.exception("Discovery failed for %s", url)
            errors += 1

    return {
        "country": country,
        "sources_checked": len(sources),
        "urls_checked": len(all_urls),
        "discovered": discovered,
        "duplicates": duplicates,
        "rejected": rejected,
        "errors": errors,
    }


@router.get("/pending")
def list_pending_candidates(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> dict:
    """List pending discovery candidates for admin review."""
    candidates = session.scalars(
        select(DiscoveryCandidate)
        .where(DiscoveryCandidate.status.in_("pending", "review"))
        .order_by(DiscoveryCandidate.created_at.asc())
        .limit(limit)
    ).all()

    return {
        "total": len(candidates),
        "candidates": [
            {
                "id": c.id,
                "source_url": c.source_url,
                "title": c.title,
                "provider": c.provider,
                "country": c.country,
                "status": c.status,
                "confidence": c.confidence,
                "review_reason": c.review_reason,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in candidates
        ],
    }


@router.post("/approve/{candidate_id}")
def approve_candidate_endpoint(
    candidate_id: int,
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Approve a discovery candidate and insert it as a scholarship."""
    if not _verify_secret(x_verification_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    pipeline = DiscoveryPipeline(session_factory=None)
    pipeline.now_fn = lambda: datetime.now(timezone.utc)
    scholarship_id = pipeline.approve_candidate(candidate_id)
    session.commit()

    if scholarship_id is None:
        return {"candidate_id": candidate_id, "status": "duplicate_or_invalid", "scholarship_id": None}

    return {"candidate_id": candidate_id, "status": "approved", "scholarship_id": scholarship_id}


@router.post("/reject/{candidate_id}")
def reject_candidate_endpoint(
    candidate_id: int,
    reason: str = Query(default="Manual rejection"),
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Reject a discovery candidate."""
    if not _verify_secret(x_verification_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    pipeline = DiscoveryPipeline(session_factory=None)
    pipeline.now_fn = lambda: datetime.now(timezone.utc)
    success = pipeline.reject_candidate(candidate_id, reason)
    session.commit()

    return {"candidate_id": candidate_id, "rejected": success, "reason": reason}
