"""Admin-only image review endpoints.

This router exposes endpoints for managing the image review queue:
- List pending image reviews
- Approve an image review
- Reject an image review

Security:
- All endpoints require admin authentication via X-Admin-Secret header
- Public users MUST NOT have access to these endpoints
- Review data is NEVER exposed through public scholarship endpoints
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import String, cast, func, or_, select

from ..core.config import get_settings
from ..database import get_db
from ..models import ImageReview, Scholarship, ScholarshipReview
from ..schemas import ImageReviewDecision, ImageReviewResponse
from ..services.admin_image_review import (
    approve_image_review,
    create_image_review,
    get_image_review,
    get_pending_image_reviews,
    reject_image_review,
)
from ..services.scholarships import get_scholarship_details

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/images", tags=["admin-images"])

#: The queue is reachable in full, but never in one unbounded response. An
#: unlimited limit is how a page of records came to look like the whole
#: catalogue and hid the actual backlog.
MAX_PAGE_SIZE = 100

SORTABLE = {
    "oldest": lambda: ImageReview.created_at.asc(),
    "newest": lambda: ImageReview.created_at.desc(),
    "confidence": lambda: ImageReview.confidence.asc(),
}


def review_queue_counts(session) -> dict[str, int]:
    """Database-wide review depths.

    Aggregated by the database across the entire table. Deriving a count from
    the rows already fetched is precisely the bug that made a real backlog
    display as a handful.
    """
    pending = (
        session.scalar(
            select(func.count(ImageReview.id)).where(ImageReview.decision == "pending")
        )
        or 0
    )
    decided = (
        session.scalar(
            select(func.count(ImageReview.id)).where(ImageReview.decision != "pending")
        )
        or 0
    )
    pending_scholarship = (
        session.scalar(
            select(func.count(ScholarshipReview.id)).where(
                ScholarshipReview.decision == "pending"
            )
        )
        or 0
    )
    needs_review = (
        session.scalar(
            select(func.count(Scholarship.id)).where(
                Scholarship.verification_status == "needs_review",
                Scholarship.verification_status != "quarantined",
            )
        )
        or 0
    )
    return {
        "pending_image_reviews": pending,
        "decided_image_reviews": decided,
        "all_image_reviews": pending + decided,
        "pending_scholarship_reviews": pending_scholarship,
        "scholarships_needing_review": needs_review,
    }


def _verify_admin_secret(provided_secret: str | None) -> bool:
    settings = get_settings()
    expected = getattr(settings, "admin_secret", None)
    if expected is None:
        return False
    if provided_secret is None:
        return False
    return provided_secret == expected


@router.get("/review-queue")
def list_review_queue(
    scholarship_id: int | None = None,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session = Depends(get_db),
    page: int = 1,
    limit: int = 25,
    kind: str | None = None,
    confidence: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    sort: str = "oldest",
    include_decided: bool = False,
) -> dict:
    """List the human review queue, paginated, searchable and filterable.

    The previous version returned a bare, unbounded list with no counts. That
    is why an owner could not find pending work: the page they were on showed
    scholarship records, and the queue itself offered no total, no paging, and
    no way to search. Counts here are computed by the database over the whole
    table, so the number on screen is the real backlog rather than the size of
    whatever was fetched.
    """
    if not _verify_admin_secret(x_admin_secret):
        logger.warning("Unauthorized admin image review queue access attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required to load review queue.",
        )

    limit = max(1, min(int(limit or 25), MAX_PAGE_SIZE))
    page = max(1, int(page or 1))

    stmt = select(ImageReview).join(Scholarship, Scholarship.id == ImageReview.scholarship_id)
    if scholarship_id is not None:
        stmt = stmt.where(ImageReview.scholarship_id == scholarship_id)
    if not include_decided:
        stmt = stmt.where(ImageReview.decision == "pending")
    if kind:
        stmt = stmt.where(ImageReview.image_kind == kind)
    if confidence:
        stmt = stmt.where(ImageReview.confidence == confidence)
    if source_type:
        stmt = stmt.where(ImageReview.source_type == source_type)
    if search:
        needle = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Scholarship.title.ilike(needle),
                Scholarship.official_source.ilike(needle),
                Scholarship.country.ilike(needle),
                # An operator pasting a bare id should find the row.
                cast(ImageReview.scholarship_id, String).like(needle.replace("%", "")),
            )
        )

    # Total for the same filter, not for the whole table: "12 of 40" has to
    # mean the filtered set.
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    order = SORTABLE.get(sort, SORTABLE["oldest"])()
    reviews = (
        session.execute(
            stmt.order_by(order, ImageReview.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    items = []
    for review in reviews:
        scholarship = session.get(Scholarship, review.scholarship_id)
        items.append(
            {
                "id": review.id,
                "scholarship_id": review.scholarship_id,
                "scholarship_title": scholarship.title if scholarship else None,
                "provider": scholarship.official_source if scholarship else None,
                "country": scholarship.country if scholarship else None,
                "image_url": review.image_url,
                "image_kind": review.image_kind,
                "source_page": review.source_page,
                "source_type": review.source_type,
                "relevance_evidence": review.relevance_evidence,
                "licensing_status": review.licensing_status,
                "licensing_evidence": review.licensing_evidence,
                "confidence": review.confidence,
                "reason_for_review": review.reason_for_review,
                "decision": review.decision,
                "reviewed_by": review.reviewed_by,
                "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
                "reviewer_note": review.reviewer_note,
                "created_at": review.created_at.isoformat() if review.created_at else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "counts": review_queue_counts(session),
        "pagination": {
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 0,
            "has_next": page * limit < total,
            "has_prev": page > 1,
            "max_page_size": MAX_PAGE_SIZE,
        },
    }


@router.post("/review/{review_id}/approve", response_model=ImageReviewResponse)
def approve_review(
    review_id: int,
    payload: ImageReviewDecision,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session = Depends(get_db),
) -> ImageReviewResponse:
    if not _verify_admin_secret(x_admin_secret):
        logger.warning("Unauthorized admin image review approval attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )

    if not payload.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval endpoint requires approved=true in payload.",
        )

    result = approve_image_review(
        session=session,
        review_id=review_id,
        reviewed_by="admin",
        reviewer_note=payload.reviewer_note,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Failed to approve review.",
        )

    review = get_image_review(session, review_id)
    scholarship = session.get(Scholarship, review.scholarship_id) if review else None
    return ImageReviewResponse(
        id=review.id,
        scholarship_id=review.scholarship_id,
        scholarship_title=scholarship.title if scholarship else None,
        image_url=review.image_url,
        image_kind=review.image_kind,
        source_page=review.source_page,
        source_type=review.source_type,
        relevance_evidence=review.relevance_evidence,
        licensing_status=review.licensing_status,
        licensing_evidence=review.licensing_evidence,
        confidence=review.confidence,
        reason_for_review=review.reason_for_review,
        decision=review.decision,
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at,
        reviewer_note=review.reviewer_note,
        created_at=review.created_at,
    )


@router.post("/review/{review_id}/reject", response_model=ImageReviewResponse)
def reject_review(
    review_id: int,
    payload: ImageReviewDecision,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session = Depends(get_db),
) -> ImageReviewResponse:
    if not _verify_admin_secret(x_admin_secret):
        logger.warning("Unauthorized admin image review rejection attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )

    if payload.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection endpoint requires approved=false in payload.",
        )

    result = reject_image_review(
        session=session,
        review_id=review_id,
        reviewed_by="admin",
        reviewer_note=payload.reviewer_note,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Failed to reject review.",
        )

    review = get_image_review(session, review_id)
    scholarship = session.get(Scholarship, review.scholarship_id) if review else None
    return ImageReviewResponse(
        id=review.id,
        scholarship_id=review.scholarship_id,
        scholarship_title=scholarship.title if scholarship else None,
        image_url=review.image_url,
        image_kind=review.image_kind,
        source_page=review.source_page,
        source_type=review.source_type,
        relevance_evidence=review.relevance_evidence,
        licensing_status=review.licensing_status,
        licensing_evidence=review.licensing_evidence,
        confidence=review.confidence,
        reason_for_review=review.reason_for_review,
        decision=review.decision,
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at,
        reviewer_note=review.reviewer_note,
        created_at=review.created_at,
    )


@router.post("/review-queue/{review_id}/decision")
def decide_from_queue(
    review_id: int,
    payload: ImageReviewDecision,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session = Depends(get_db),
) -> dict:
    """Approve or reject a queued review and return refreshed queue counts.

    The separate approve/reject endpoints above return only the review row, so
    a client had to re-fetch the whole queue to update its counter - and a
    client that skipped that refetch displayed a stale number forever. This
    returns the new database-wide counts with the decision.
    """
    if not _verify_admin_secret(x_admin_secret):
        logger.warning("Unauthorized admin image review decision attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required to record a review decision.",
        )

    service = approve_image_review if payload.approved else reject_image_review
    result = service(
        session=session,
        review_id=review_id,
        reviewed_by="admin",
        reviewer_note=payload.reviewer_note,
    )
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Failed to record review decision.",
        )

    review = get_image_review(session, review_id)
    return {
        "id": review_id,
        "decision": review.decision if review else None,
        "counts": review_queue_counts(session),
    }