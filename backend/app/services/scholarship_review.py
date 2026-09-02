"""Conflict + Human Review workflow for verification candidates that cannot be automatically updated.

This service manages the lifecycle of review items:
- Creation when conflicts block auto-update
- Duplicate prevention for the same unresolved field
- Approval flow: validate -> re-check current value -> apply through safe updater -> write history -> atomic commit
- Rejection flow: mark REJECTED, scholarship unchanged
- Concurrency protection: stale review approval is blocked
- Immutability: review records are append-only audit trail

Safety rules:
1. Conflicted fields MUST NOT be auto-updated.
2. Low-confidence fields MUST NOT be auto-updated.
3. Third-party-only evidence MUST NOT be auto-updated.
4. Identity conflicts MUST NOT be auto-updated.
5. A review approval MUST pass through the existing safe updater.
6. Review approval MUST NOT directly mutate the scholarship model.
7. Approval + scholarship update + history must be ONE transaction.
8. Rejection must leave scholarship data unchanged.
9. Review records are immutable in the decision history.
10. Do not silently discard unresolved conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Scholarship, ScholarshipReview
from .scholarship_history import HistoryEntry, write_verification_history
from .scholarship_updater import apply_verified_updates


class ReviewDecision:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ConflictReason:
    IDENTITY_CONFLICT = "identity_conflict"
    LOW_CONFIDENCE = "low_confidence"
    THIRD_PARTY_SOURCE = "third_party_source"
    CONFLICTING_SOURCES = "conflicting_sources"
    MISSING_EVIDENCE = "missing_evidence"
    AMBIGUOUS_EVIDENCE = "ambiguous_evidence"
    CONCURRENCY_CONFLICT = "concurrency_conflict"


@dataclass
class ReviewCreateResult:
    review_id: int | None = None
    created: bool = False
    existing_review_id: int | None = None
    error: str | None = None


@dataclass
class ReviewDecisionResult:
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


def _values_equal(current: Any | None, expected: Any | None) -> bool:
    if current is None and expected is None:
        return True
    if current is None or expected is None:
        return False
    if isinstance(current, list) and isinstance(expected, list):
        return sorted(str(x) for x in current) == sorted(str(x) for x in expected)
    if isinstance(current, list) and not isinstance(expected, list):
        return sorted(str(x) for x in current) == ([str(expected)] if expected else [])
    if not isinstance(current, list) and isinstance(expected, list):
        return ([str(current)] if current else []) == sorted(str(x) for x in expected)
    return str(current).strip() == str(expected).strip()


def get_pending_review(
    session: Session,
    scholarship_id: int,
    field_name: str,
) -> ScholarshipReview | None:
    stmt = (
        select(ScholarshipReview)
        .where(ScholarshipReview.scholarship_id == scholarship_id)
        .where(ScholarshipReview.field_name == field_name)
        .where(ScholarshipReview.decision == ReviewDecision.PENDING)
    )
    return session.execute(stmt).scalar_one_or_none()


def get_review(session: Session, review_id: int) -> ScholarshipReview | None:
    return session.get(ScholarshipReview, review_id)


def get_pending_reviews(session: Session, scholarship_id: int) -> list[ScholarshipReview]:
    stmt = (
        select(ScholarshipReview)
        .where(ScholarshipReview.scholarship_id == scholarship_id)
        .where(ScholarshipReview.decision == ReviewDecision.PENDING)
        .order_by(ScholarshipReview.created_at.asc())
    )
    return list(session.execute(stmt).scalars().all())


def create_review(
    session: Session,
    scholarship_id: int,
    field_name: str,
    current_value: Any,
    proposed_value: Any,
    conflict_reason: str,
    verification_state: str = "uncertain",
    confidence: str | None = None,
    source_urls: list[str] | None = None,
    evidence_text: str | None = None,
) -> ReviewCreateResult:
    result = ReviewCreateResult()

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        result.error = f"scholarship {scholarship_id} not found"
        return result

    existing = get_pending_review(session, scholarship_id, field_name)
    if existing is not None:
        result.existing_review_id = existing.id
        result.error = "pending review already exists for this field"
        return result

    now = datetime.now(timezone.utc)
    review = ScholarshipReview(
        scholarship_id=scholarship_id,
        field_name=field_name,
        current_value=_serialize_value(current_value),
        proposed_value=_serialize_value(proposed_value),
        conflict_reason=conflict_reason,
        verification_state=verification_state,
        confidence=confidence,
        source_urls=source_urls or [],
        evidence_text=evidence_text,
        decision=ReviewDecision.PENDING,
        created_at=now,
    )
    session.add(review)
    session.flush()

    result.review_id = review.id
    result.created = True
    return result


def approve_review(
    session: Session,
    review_id: int,
    reviewed_by: str,
    reviewer_note: str | None = None,
) -> ReviewDecisionResult:
    result = ReviewDecisionResult(review_id=review_id)

    review = session.get(ScholarshipReview, review_id)
    if review is None:
        result.error = f"review {review_id} not found"
        return result

    if review.decision != ReviewDecision.PENDING:
        result.error = f"review already decided: {review.decision}"
        return result

    scholarship = session.get(Scholarship, review.scholarship_id)
    if scholarship is None:
        result.error = f"scholarship {review.scholarship_id} not found"
        return result

    current_value = getattr(scholarship, review.field_name, None)
    if not _values_equal(current_value, review.current_value):
        result.concurrency_conflict = True
        result.error = "concurrency conflict: current value changed since review creation"
        return result

    candidate = {
        "field": review.field_name,
        "old_value": review.current_value,
        "new_value": review.proposed_value,
        "confidence": review.confidence,
        "is_update_candidate": True,
    }

    update_result = apply_verified_updates(session, review.scholarship_id, [candidate])

    if update_result.concurrency_conflict:
        result.concurrency_conflict = True
        result.error = update_result.error_reason or "concurrency conflict during update"
        return result

    if update_result.update_status == "rejected":
        result.error = update_result.error_reason or "update rejected by safe updater"
        return result

    entries = [
        HistoryEntry(
            field_name=review.field_name,
            old_value=review.current_value,
            new_value=review.proposed_value,
            change_type="modified",
            source_url=review.source_urls[0] if review.source_urls else None,
            evidence_text=review.evidence_text,
            confidence=review.confidence,
            verification_status="approved",
        )
    ]
    write_verification_history(session, review.scholarship_id, entries)

    now = datetime.now(timezone.utc)
    review.decision = ReviewDecision.APPROVED
    review.reviewed_at = now
    review.reviewed_by = reviewed_by
    review.reviewer_note = reviewer_note

    try:
        session.flush()
        session.commit()
    except Exception as exc:
        session.rollback()
        result.error = f"transaction failed: {exc}"
        return result

    result.success = True
    result.decision = ReviewDecision.APPROVED
    result.updated_fields = update_result.updated_fields
    return result


def reject_review(
    session: Session,
    review_id: int,
    reviewed_by: str,
    reviewer_note: str | None = None,
) -> ReviewDecisionResult:
    result = ReviewDecisionResult(review_id=review_id)

    review = session.get(ScholarshipReview, review_id)
    if review is None:
        result.error = f"review {review_id} not found"
        return result

    if review.decision != ReviewDecision.PENDING:
        result.error = f"review already decided: {review.decision}"
        return result

    now = datetime.now(timezone.utc)
    review.decision = ReviewDecision.REJECTED
    review.reviewed_at = now
    review.reviewed_by = reviewed_by
    review.reviewer_note = reviewer_note

    try:
        session.flush()
        session.commit()
    except Exception as exc:
        session.rollback()
        result.error = f"transaction failed: {exc}"
        return result

    result.success = True
    result.decision = ReviewDecision.REJECTED
    return result
