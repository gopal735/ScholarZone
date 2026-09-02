"""Verification pipeline integrating fetch, extract, diff, evidence, and confidence."""

from __future__ import annotations

import time
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..repositories.scholarships import get_scholarship_by_id
from .official_source_fetcher import OfficialSourceFetchResult, fetch_official_source
from .scholarship_evidence import (
    EvidenceCollection,
    EvidenceStatus,
    SourceType,
    collect_evidence,
    is_authoritative_source,
)
from .scholarship_extractor import (
    ExtractionConfidence,
    ScholarshipExtractionResult,
    extract_scholarship_information,
)
from .scholarship_diff import ChangeSet, FieldChange, FieldChangeType, diff_scholarship
from .telemetry import PipelineStages, record_event
from .telemetry_tracing import VerificationTracer
from .verification_confidence import (
    ConfidenceLevel,
    VerificationAssessment,
    VerificationState,
    assess_confidence,
)


class VerificationFetchStatus:
    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    FAILED = "failed"


class VerificationStatus:
    ACTIVE = "active"
    NEEDS_REVIEW = "needs_review"
    UNCERTAIN = "uncertain"
    FAILED = "failed"


class VerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    scholarship_id: int
    official_source_url: str | None = None
    verification_status: str = VerificationStatus.ACTIVE
    fetch_status: str = Field(default=VerificationFetchStatus.PENDING)
    extracted_fields: dict[str, object] = Field(default_factory=dict)
    changed_fields: dict[str, tuple[object, object]] = Field(default_factory=dict)
    unchanged_fields: list[str] = Field(default_factory=list)
    uncertain_fields: list[str] = Field(default_factory=list)
    automatic_update_candidates: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_reason: str | None = None
    fetch_result: OfficialSourceFetchResult | None = None
    extraction_result: dict[str, object] | None = None
    changeset: ChangeSet | None = None
    evidence_collection: EvidenceCollection | None = None
    confidence_assessment: VerificationAssessment | None = None


def _apply_confidence_safety_gate(
    changeset: ChangeSet,
    extraction_result: ScholarshipExtractionResult | None,
    original_verification_status: str,
    evidence_collection: EvidenceCollection | None = None,
    confidence_assessment: VerificationAssessment | None = None,
) -> tuple[dict[str, tuple[object, object]], list[str], list[str], list[dict[str, object]], str, list[str]]:
    """Apply confidence and safety rules to determine update candidates and verification status.

    Integrates with evidence layer and confidence engine for safety decisions.

    Returns:
        Tuple of (changed_fields, unchanged_fields, uncertain_fields, automatic_update_candidates, verification_status, warnings)
    """
    changed_fields: dict[str, tuple[object, object]] = {}
    unchanged_fields: list[str] = []
    uncertain_fields: list[str] = []
    automatic_update_candidates: list[dict[str, object]] = []
    warnings: list[str] = []

    if extraction_result is None:
        return changed_fields, unchanged_fields, uncertain_fields, automatic_update_candidates, VerificationStatus.FAILED, warnings

    if changeset.identity_conflict:
        for change in changeset.changes:
            if change.change_type == FieldChangeType.MODIFIED:
                changed_fields[change.field] = (change.old_value, change.new_value)
            elif change.change_type == FieldChangeType.IDENTITY_CONFLICT:
                changed_fields[change.field] = (change.old_value, change.new_value)
                warnings.append(f"Identity conflict detected on field '{change.field}'")
            elif change.change_type == FieldChangeType.UNCHANGED:
                unchanged_fields.append(change.field)
            elif change.change_type in (FieldChangeType.ADDED, FieldChangeType.REMOVED):
                uncertain_fields.append(change.field)
        return changed_fields, unchanged_fields, uncertain_fields, automatic_update_candidates, VerificationStatus.NEEDS_REVIEW, warnings

    for change in changeset.changes:
        if change.change_type == FieldChangeType.UNCHANGED:
            unchanged_fields.append(change.field)
        elif change.change_type == FieldChangeType.MODIFIED:
            if change.is_update_candidate and change.confidence == ExtractionConfidence.HIGH:
                if _is_field_confidence_safe(change.field, evidence_collection, confidence_assessment):
                    changed_fields[change.field] = (change.old_value, change.new_value)
                    automatic_update_candidates.append({
                        "field": change.field,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                        "confidence": change.confidence,
                    })
                else:
                    changed_fields[change.field] = (change.old_value, change.new_value)
                    uncertain_fields.append(change.field)
                    warnings.append(f"Field '{change.field}' blocked by confidence/evidence safety gate")
            elif change.confidence == ExtractionConfidence.LOW:
                uncertain_fields.append(change.field)
                warnings.append(f"Low confidence change on '{change.field}' flagged as uncertain")
            else:
                changed_fields[change.field] = (change.old_value, change.new_value)
        elif change.change_type == FieldChangeType.ADDED:
            if change.is_update_candidate and change.confidence == ExtractionConfidence.HIGH:
                if _is_field_confidence_safe(change.field, evidence_collection, confidence_assessment):
                    changed_fields[change.field] = (change.old_value, change.new_value)
                    automatic_update_candidates.append({
                        "field": change.field,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                        "confidence": change.confidence,
                    })
                else:
                    uncertain_fields.append(change.field)
                    warnings.append(f"Field '{change.field}' blocked by confidence/evidence safety gate")
            elif change.confidence == ExtractionConfidence.LOW:
                uncertain_fields.append(change.field)
        elif change.change_type == FieldChangeType.REMOVED:
            uncertain_fields.append(change.field)
            warnings.append(f"Extractor returned None for '{change.field}'; marked as uncertain")

    verification_status = original_verification_status
    if automatic_update_candidates:
        verification_status = original_verification_status
    elif uncertain_fields and not changed_fields:
        verification_status = VerificationStatus.UNCERTAIN

    return changed_fields, unchanged_fields, uncertain_fields, automatic_update_candidates, verification_status, warnings


def _is_field_confidence_safe(
    field_name: str,
    evidence_collection: EvidenceCollection | None,
    confidence_assessment: VerificationAssessment | None,
) -> bool:
    """Check if a field passes the confidence/evidence safety gate.

    Hard safety rules:
    - NO EVIDENCE -> NO AUTO UPDATE
    - LOW CONFIDENCE -> NO AUTO UPDATE
    - THIRD-PARTY SOURCE -> NO AUTO UPDATE
    - CONFLICT -> NO AUTO UPDATE
    - IDENTITY CONFLICT -> NO AUTO UPDATE
    """
    if evidence_collection is None:
        return False

    evidence_item = evidence_collection.get_evidence_for_field(field_name)
    if evidence_item is None:
        return False

    if evidence_item.status == EvidenceStatus.MISSING:
        return False

    if evidence_item.status == EvidenceStatus.LOW_CONFIDENCE:
        return False

    if evidence_item.status == EvidenceStatus.IDENTITY_CONFLICT:
        return False

    if evidence_item.status == EvidenceStatus.AMBIGUOUS:
        return False

    if not is_authoritative_source(evidence_item.source_type):
        return False

    if confidence_assessment is None:
        return False

    field_result = confidence_assessment.get_field_result(field_name)
    if field_result is None:
        return False

    if field_result.confidence == ConfidenceLevel.LOW:
        return False

    if field_result.confidence == ConfidenceLevel.CONFLICT:
        return False

    if field_result.verification_state == VerificationState.UNSUPPORTED:
        return False

    if field_result.verification_state == VerificationState.UNCERTAIN:
        return False

    if not field_result.is_update_candidate:
        return False

    return True


def verify_scholarship(session: Session, scholarship_id: int) -> VerificationResult | None:
    """Run the full verification pipeline: fetch, extract, diff, evidence, confidence, safety gate.

    Read-only: does not modify the database.

    Pipeline:
        Official Source -> Fetch -> Extract -> Diff -> Evidence Collection
        -> Confidence Assessment -> Safety Gate -> Final VerificationResult
    """
    scholarship = get_scholarship_by_id(session, scholarship_id)
    if scholarship is None:
        return None

    official_url = scholarship.official_source_url
    if not official_url:
        return VerificationResult(
            scholarship_id=scholarship.id,
            verification_status=scholarship.verification_status,
            fetch_status=VerificationFetchStatus.PENDING,
            error_reason="official_source_url is missing",
            warnings=["Scholarship has no official_source_url; automatic verification cannot proceed"],
        )

    normalized_url = official_url.strip().rstrip("/")
    parsed = urlsplit(normalized_url)
    if not normalized_url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return VerificationResult(
            scholarship_id=scholarship.id,
            official_source_url=official_url,
            verification_status=scholarship.verification_status,
            fetch_status=VerificationFetchStatus.PENDING,
            error_reason="official_source_url is not a valid URL",
            warnings=["official_source_url is not a valid URL"],
        )

    with VerificationTracer(
        scholarship_id=scholarship.id,
        source=normalized_url,
    ) as tracer:
        fetch_start = time.monotonic()
        fetch_result = fetch_official_source(normalized_url)
        fetch_duration_ms = (time.monotonic() - fetch_start) * 1000.0
        tracer.record_fetch(fetch_duration_ms, fetch_result.success, fetch_result.error_type)

        if not fetch_result.success:
            tracer.finish(success=False, error_type=fetch_result.error_type)
            return VerificationResult(
                scholarship_id=scholarship.id,
                official_source_url=normalized_url,
                verification_status=scholarship.verification_status,
                fetch_status=VerificationFetchStatus.FAILED,
                fetch_result=fetch_result,
                error_reason=fetch_result.error_reason,
                warnings=[f"Fetch failed: {fetch_result.error_reason}"],
            )

        extraction_start = time.monotonic()
        extraction_result = extract_scholarship_information(fetch_result.content or "", normalized_url)
        extraction_duration_ms = (time.monotonic() - extraction_start) * 1000.0
        tracer.record_extraction(extraction_duration_ms, True)

        diff_start = time.monotonic()
        changeset = diff_scholarship(scholarship, extraction_result)
        diff_duration_ms = (time.monotonic() - diff_start) * 1000.0
        tracer.record_diff(diff_duration_ms, True)

        evidence_start = time.monotonic()
        evidence_collection = collect_evidence(
            scholarship_id=scholarship.id,
            source_url=normalized_url,
            source_content=fetch_result.content or "",
            extraction_result=extraction_result,
            changeset=changeset,
        )
        evidence_duration_ms = (time.monotonic() - evidence_start) * 1000.0
        tracer.record_evidence(evidence_duration_ms, True)

        identity_conflict_fields: set[str] = set()
        if changeset.identity_conflict:
            for change in changeset.changes:
                if change.change_type == FieldChangeType.IDENTITY_CONFLICT:
                    identity_conflict_fields.add(change.field)

        confidence_start = time.monotonic()
        confidence_assessment = assess_confidence(
            scholarship_id=scholarship.id,
            evidence_items=evidence_collection.items,
            identity_conflict_fields=identity_conflict_fields,
        )
        confidence_duration_ms = (time.monotonic() - confidence_start) * 1000.0
        tracer.record_confidence(confidence_duration_ms, True)

        changed_fields, unchanged_fields, uncertain_fields, automatic_update_candidates, verification_status, gate_warnings = _apply_confidence_safety_gate(
            changeset, extraction_result, scholarship.verification_status, evidence_collection, confidence_assessment
        )

        tracer.finish(success=True)

    all_warnings = list(extraction_result.extraction_notes) + gate_warnings

    return VerificationResult(
        scholarship_id=scholarship.id,
        official_source_url=normalized_url,
        verification_status=verification_status,
        fetch_status=VerificationFetchStatus.SUCCESS,
        extracted_fields=extraction_result.model_dump(),
        changed_fields=changed_fields,
        unchanged_fields=unchanged_fields,
        uncertain_fields=uncertain_fields,
        automatic_update_candidates=automatic_update_candidates,
        warnings=all_warnings,
        error_reason=None,
        fetch_result=fetch_result,
        extraction_result=extraction_result.model_dump(),
        changeset=changeset,
        evidence_collection=evidence_collection,
        confidence_assessment=confidence_assessment,
    )
