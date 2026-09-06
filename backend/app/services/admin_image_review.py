"""Admin image review service for managing the image review queue.

Provides:
- Create image review entries for MEDIUM-confidence and HIGH-confidence logo candidates
- List pending reviews
- Approve/reject reviews with audit trail
- Never expose review data to public API
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ImageReview, Scholarship, ScholarshipVerificationHistory
from .scholarship_image_verifier import ImageVerifier, is_valid_source_type


@dataclass
class ImageReviewCreateResult:
    review_id: int | None = None
    created: bool = False
    existing_review_id: int | None = None
    error: str | None = None


@dataclass
class ImageReviewDecisionResult:
    success: bool = False
    review_id: int | None = None
    decision: str | None = None
    updated_fields: list[str] = field(default_factory=list)
    error: str | None = None
    concurrency_conflict: bool = False


def _serialize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def create_image_review(
    session: Session,
    scholarship_id: int,
    image_url: str,
    image_kind: str,
    source_page: str | None = None,
    source_type: str | None = None,
    relevance_evidence: str | None = None,
    licensing_status: str | None = None,
    licensing_evidence: str | None = None,
    confidence: str = "MEDIUM",
    reason_for_review: str | None = None,
) -> ImageReviewCreateResult:
    result = ImageReviewCreateResult()

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        result.error = f"scholarship {scholarship_id} not found"
        return result

    existing = session.execute(
        select(ImageReview)
        .where(ImageReview.scholarship_id == scholarship_id)
        .where(ImageReview.image_url == image_url)
        .where(ImageReview.decision == "pending")
    ).scalar_one_or_none()

    if existing is not None:
        result.existing_review_id = existing.id
        result.error = "pending review already exists for this image"
        return result

    now = datetime.now(timezone.utc)
    review = ImageReview(
        scholarship_id=scholarship_id,
        image_url=image_url,
        image_kind=image_kind,
        source_page=source_page,
        source_type=source_type,
        relevance_evidence=relevance_evidence,
        licensing_status=licensing_status,
        licensing_evidence=licensing_evidence,
        confidence=confidence,
        reason_for_review=reason_for_review,
        decision="pending",
        created_at=now,
    )
    session.add(review)
    session.flush()

    result.review_id = review.id
    result.created = True
    return result


def get_pending_image_reviews(session: Session, scholarship_id: int | None = None) -> list[ImageReview]:
    stmt = select(ImageReview).where(ImageReview.decision == "pending").order_by(ImageReview.created_at.asc())
    if scholarship_id is not None:
        stmt = stmt.where(ImageReview.scholarship_id == scholarship_id)
    return list(session.execute(stmt).scalars().all())


def get_image_review(session: Session, review_id: int) -> ImageReview | None:
    return session.get(ImageReview, review_id)


def approve_image_review(
    session: Session,
    review_id: int,
    reviewed_by: str,
    reviewer_note: str | None = None,
) -> ImageReviewDecisionResult:
    result = ImageReviewDecisionResult(review_id=review_id)

    review = session.get(ImageReview, review_id)
    if review is None:
        result.error = f"review {review_id} not found"
        return result

    if review.decision != "pending":
        result.error = f"review already decided: {review.decision}"
        return result

    scholarship = session.get(Scholarship, review.scholarship_id)
    if scholarship is None:
        result.error = f"scholarship {review.scholarship_id} not found"
        return result

    if scholarship.image_url is not None and scholarship.image_url != review.image_url:
        if scholarship.image_verified_at is not None:
            result.error = "Cannot overwrite verified image without explicit clear"
            result.concurrency_conflict = True
            return result

    source_type = review.source_type or "official_scholarship"
    if not is_valid_source_type(source_type):
        result.error = f"Invalid source_type: {source_type}"
        return result

    image_verifier = ImageVerifier(session)
    updated = image_verifier.mark_image_verified(
        scholarship_id=review.scholarship_id,
        image_url=review.image_url,
        image_source_url=review.source_page or scholarship.official_source_url or "",
        source_type=source_type,
        alt_text=None,
        image_kind=review.image_kind,
    )

    if not updated and scholarship.image_url == review.image_url:
        result.success = True
        result.decision = "approved"
        result.updated_fields = ["image_url"]
    elif not updated:
        result.error = "Image was not persisted."
        return result

    now = datetime.now(timezone.utc)
    review.decision = "approved"
    review.reviewed_at = now
    review.reviewed_by = reviewed_by
    review.reviewer_note = reviewer_note

    session.add(ScholarshipVerificationHistory(
        scholarship_id=review.scholarship_id,
        field_name="image_url",
        old_value=scholarship.image_url,
        new_value=review.image_url,
        change_type="modified",
        source_url=review.source_page,
        evidence_text=f"Admin approved image review: {review.reason_for_review or 'manual approval'}",
        confidence="high",
        verification_status="active",
    ))

    try:
        session.flush()
        session.commit()
    except Exception as exc:
        session.rollback()
        result.error = f"transaction failed: {exc}"
        return result

    result.success = True
    result.decision = "approved"
    result.updated_fields = ["image_url", "image_kind"]
    return result


def reject_image_review(
    session: Session,
    review_id: int,
    reviewed_by: str,
    reviewer_note: str | None = None,
) -> ImageReviewDecisionResult:
    result = ImageReviewDecisionResult(review_id=review_id)

    review = session.get(ImageReview, review_id)
    if review is None:
        result.error = f"review {review_id} not found"
        return result

    if review.decision != "pending":
        result.error = f"review already decided: {review.decision}"
        return result

    now = datetime.now(timezone.utc)
    review.decision = "rejected"
    review.reviewed_at = now
    review.reviewed_by = reviewed_by
    review.reviewer_note = reviewer_note

    session.add(ScholarshipVerificationHistory(
        scholarship_id=review.scholarship_id,
        field_name="image_url",
        old_value=None,
        new_value=None,
        change_type="rejected",
        source_url=review.source_page,
        evidence_text=f"Admin rejected image review: {review.reason_for_review or 'manual rejection'}. Note: {reviewer_note or ''}",
        confidence="medium",
        verification_status="active",
    ))

    try:
        session.flush()
        session.commit()
    except Exception as exc:
        session.rollback()
        result.error = f"transaction failed: {exc}"
        return result

    result.success = True
    result.decision = "rejected"
    return result
