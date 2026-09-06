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

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..core.config import get_settings
from ..database import get_db
from ..models import Scholarship
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


def _verify_admin_secret(provided_secret: str | None) -> bool:
    settings = get_settings()
    expected = getattr(settings, "admin_secret", None)
    if expected is None:
        return False
    if provided_secret is None:
        return False
    return provided_secret == expected


@router.get("/review-queue", response_model=list[ImageReviewResponse])
def list_review_queue(
    scholarship_id: int | None = None,
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    session = Depends(get_db),
) -> list[ImageReviewResponse]:
    if not _verify_admin_secret(x_admin_secret):
        logger.warning("Unauthorized admin image review queue access attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )

    reviews = get_pending_image_reviews(session, scholarship_id=scholarship_id)
    response = []
    for review in reviews:
        scholarship = session.get(Scholarship, review.scholarship_id)
        response.append(ImageReviewResponse(
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
        ))
    return response


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
