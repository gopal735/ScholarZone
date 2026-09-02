"""Coordinator that bridges verification results to the review workflow.

When the verifier determines that fields cannot be automatically updated
due to conflicts, this coordinator creates review items for human decision.

Integration point:
    verification_result = verify_scholarship(session, scholarship_id)
    reviews_created = create_reviews_from_verification(session, verification_result)

This module is deterministic and read-only except for review creation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .scholarship_review import (
    ConflictReason,
    ReviewCreateResult,
    create_review,
)
from .scholarship_verifier import VerificationResult, VerificationStatus


def _determine_conflict_reason(
    field_name: str,
    changeset: Any,
    evidence_collection: Any,
    confidence_assessment: Any,
) -> str | None:
    """Determine the specific conflict reason for a field that cannot auto-update.

    Returns None if the field is safe for auto-update (no conflict).
    Returns a ConflictReason string if the field requires review.
    """
    if changeset is not None and changeset.identity_conflict:
        for change in changeset.changes:
            if change.field == field_name and change.change_type.value == "identity_conflict":
                return ConflictReason.IDENTITY_CONFLICT

    if evidence_collection is not None:
        evidence_item = evidence_collection.get_evidence_for_field(field_name)
        if evidence_item is not None:
            if evidence_item.status.value == "identity_conflict":
                return ConflictReason.IDENTITY_CONFLICT
            if evidence_item.status.value == "missing":
                return ConflictReason.MISSING_EVIDENCE
            if evidence_item.status.value == "low_confidence":
                return ConflictReason.LOW_CONFIDENCE
            if evidence_item.status.value == "ambiguous":
                return ConflictReason.AMBIGUOUS_EVIDENCE
            if evidence_item.source_type.value == "third_party":
                return ConflictReason.THIRD_PARTY_SOURCE

    if confidence_assessment is not None:
        field_result = confidence_assessment.get_field_result(field_name)
        if field_result is not None:
            if field_result.confidence.value == "conflict":
                return ConflictReason.CONFLICTING_SOURCES
            if field_result.confidence.value == "low":
                return ConflictReason.LOW_CONFIDENCE

    return None


def _extract_source_urls(evidence_collection: Any, field_name: str) -> list[str]:
    """Extract source URLs from evidence collection for a field."""
    if evidence_collection is None:
        return []

    urls = []
    for item in evidence_collection.items:
        if item.field_name == field_name and item.source_url:
            if item.source_url not in urls:
                urls.append(item.source_url)
    return urls


def _extract_evidence_text(evidence_collection: Any, field_name: str) -> str | None:
    """Extract evidence text from evidence collection for a field."""
    if evidence_collection is None:
        return None

    item = evidence_collection.get_evidence_for_field(field_name)
    return item.evidence_text if item else None


def create_reviews_from_verification(
    session: Session,
    verification_result: VerificationResult,
) -> list[ReviewCreateResult]:
    """Create review items for fields that cannot be auto-updated.

    Inspects the verification result's uncertain_fields and creates
    a review item for each field that has a conflict reason.

    Duplicate reviews for the same pending field are prevented.

    Returns a list of ReviewCreateResult for each field processed.
    """
    results: list[ReviewCreateResult] = []

    if verification_result is None:
        return results

    if not verification_result.uncertain_fields:
        return results

    for field_name in verification_result.uncertain_fields:
        conflict_reason = _determine_conflict_reason(
            field_name,
            verification_result.changeset,
            verification_result.evidence_collection,
            verification_result.confidence_assessment,
        )

        if conflict_reason is None:
            continue

        old_value = None
        new_value = None
        if field_name in verification_result.changed_fields:
            old_value, new_value = verification_result.changed_fields[field_name]

        source_urls = _extract_source_urls(
            verification_result.evidence_collection, field_name
        )
        evidence_text = _extract_evidence_text(
            verification_result.evidence_collection, field_name
        )

        confidence = None
        if verification_result.confidence_assessment is not None:
            field_result = verification_result.confidence_assessment.get_field_result(field_name)
            if field_result is not None:
                confidence = field_result.confidence.value

        review_result = create_review(
            session=session,
            scholarship_id=verification_result.scholarship_id,
            field_name=field_name,
            current_value=old_value,
            proposed_value=new_value,
            conflict_reason=conflict_reason,
            verification_state=verification_result.verification_status,
            confidence=confidence,
            source_urls=source_urls,
            evidence_text=evidence_text,
        )

        results.append(review_result)

    if results:
        session.commit()

    return results
