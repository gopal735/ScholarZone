"""Batch image population script — processes first 10 scholarships without verified images.

For each scholarship:
1. Classify as UNIVERSITY / GOVERNMENT / PROVIDER
2. Fetch official page and extract candidate images
3. Run ImageValidator on candidates
4. Persist HIGH confidence via ImageVerifier.mark_image_verified()
5. Mark MEDIUM confidence as HUMAN_REVIEW via ScholarshipReview
6. Leave LOW / no trustworthy image as NULL
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add backend to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.models import Scholarship, ScholarshipReview, ScholarshipVerificationHistory, ImageReview
from app.services.image_discovery import ImageCandidate, ImageDiscoveryService
from app.services.image_validator import ImageValidator, ValidationStatus
from app.services.scholarship_image_verifier import ImageVerifier, ImageSourceType, is_official_domain, extract_domain
from app.services.scholarship_review import create_review
from app.services.admin_image_review import create_image_review as create_admin_image_review
from authoritative_registry import build_authoritative_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_processed_ids() -> set[int]:
    """Build authoritative registry of processed scholarship IDs."""
    registry = build_authoritative_registry()
    return set(registry.keys())


@dataclass
class BatchResult:
    scholarship_id: int
    title: str
    classification: str
    official_source_url: str | None
    best_image_url: str | None
    source_page: str | None
    confidence: str | None
    status: str | None
    rejection_reasons: list[str]
    action: str
    audit_records: int = 0
    review_created: bool = False
    image_kind: str | None = None


def classify_scholarship(scholarship: Scholarship) -> str:
    """Classify scholarship as UNIVERSITY, GOVERNMENT, or PROVIDER."""
    official = (scholarship.official_source or "").lower()
    source_url = (scholarship.official_source_url or "").lower()
    title = scholarship.title.lower()

    government_keywords = [
        "government", "ministry", "federal", "state", "department",
        "sbfi", "seri", "daad", "campus france", "study in india",
        "jasso", "iccr", "fulbright", "educationusa",
    ]
    university_keywords = [
        "university", "université", "universitat", "universität",
        "eth ", "epfl", "mit", "stanford", "harvard", "oxford",
        "cambridge", "college", "institute of technology",
    ]
    provider_keywords = [
        "foundation", "trust", "fund", "organization", "organisation",
        "association", "society", "council", "posco", "tj park",
    ]

    for kw in government_keywords:
        if kw in official or kw in source_url or kw in title:
            return "GOVERNMENT"

    for kw in university_keywords:
        if kw in official or kw in source_url or kw in title:
            return "UNIVERSITY"

    for kw in provider_keywords:
        if kw in official or kw in source_url or kw in title:
            return "PROVIDER"

    if ".edu" in source_url or ".ac." in source_url:
        return "UNIVERSITY"
    if ".gov" in source_url or ".go.kr" in source_url or ".go.jp" in source_url:
        return "GOVERNMENT"

    return "PROVIDER"


def determine_source_type(image_url: str | None, classification: str) -> str | None:
    """Map classification + image domain to ImageSourceType."""
    if not image_url:
        return None

    domain = extract_domain(image_url)
    if not domain:
        return None

    if classification == "UNIVERSITY":
        return ImageSourceType.OFFICIAL_UNIVERSITY.value
    if classification == "GOVERNMENT":
        return ImageSourceType.OFFICIAL_GOVERNMENT.value
    if classification == "PROVIDER":
        if "daad" in domain:
            return ImageSourceType.OFFICIAL_PROVIDER.value
        if "erasmus" in domain or "europa" in domain:
            return ImageSourceType.OFFICIAL_SCHOLARSHIP.value
        return ImageSourceType.OFFICIAL_PROVIDER.value

    if domain.endswith(".edu") or ".ac." in domain:
        return ImageSourceType.OFFICIAL_UNIVERSITY.value
    if domain.endswith(".gov") or domain.endswith(".go.kr") or domain.endswith(".go.jp"):
        return ImageSourceType.OFFICIAL_GOVERNMENT.value

    return ImageSourceType.OFFICIAL_SCHOLARSHIP.value


def discover_best_image(scholarship: Scholarship) -> tuple[ImageCandidate | None, str | None]:
    """Discover best candidate image from official page.

    Returns all candidates to the validator for classification.
    Does NOT pre-filter by kind — the validator handles classification,
    confidence assignment, and rejection.
    """
    if not scholarship.official_source_url:
        return None, None

    discovery = ImageDiscoveryService(timeout=30.0)
    candidates = discovery.discover_from_scholarship(scholarship.official_source_url)

    if not candidates:
        return None, None

    # Prioritize: og:image > twitter:image > json-ld > link-image-src > html-img > common-asset > link-rel-icon
    priority = {
        "og:image": 0,
        "twitter:image": 1,
        "json-ld": 2,
        "link-image-src": 3,
        "html-img": 4,
        "common-asset": 5,
        "link-rel-icon": 6,
    }
    candidates.sort(key=lambda c: (
        priority.get(c.discovery_method, 99),
        -c.fallback_level,
        -(len(c.alt_text or "")),
    ))

    # Only filter out candidates that are clearly unreachable or non-HTTP
    # All other filtering is delegated to the validator
    filtered = [c for c in candidates if c.image_url.startswith("http")]

    if not filtered:
        return None, None

    return filtered[0], scholarship.official_source_url


def process_scholarship(session: Session, scholarship: Scholarship) -> BatchResult:
    """Process a single scholarship for image population."""
    result = BatchResult(
        scholarship_id=scholarship.id,
        title=scholarship.title,
        classification=classify_scholarship(scholarship),
        official_source_url=scholarship.official_source_url,
        best_image_url=None,
        source_page=None,
        confidence=None,
        status=None,
        rejection_reasons=[],
        action="none",
    )

    # Step 1: Discover best candidate image
    candidate, source_page = discover_best_image(scholarship)
    result.source_page = source_page

    if candidate is None:
        result.action = "no_candidate_found"
        result.rejection_reasons.append("No image candidates discovered from official page")
        return result

    result.best_image_url = candidate.image_url

    # Step 2: Run ImageValidator
    validator = ImageValidator(timeout=30.0)
    validation = validator.validate_candidate(
        candidate,
        scholarship_title=scholarship.title,
        official_source_url=scholarship.official_source_url,
    )

    result.confidence = validation.confidence
    result.status = validation.status.value
    result.image_kind = validation.image_kind
    result.rejection_reasons = validation.rejection_reasons[:5]

    logger.info(
        "ID %d (%s): validator=%s confidence=%s relevance=%.2f kind=%s image=%s",
        scholarship.id,
        scholarship.title[:50],
        validation.status.value,
        validation.confidence,
        validation.relevance_score,
        validation.image_kind,
        candidate.image_url[:80],
    )

    # Step 3: Act on validation result
    auto_persist = (
        validation.confidence == "HIGH"
        and validation.status == ValidationStatus.APPROVED
        and validation.image_kind in ("program_image", "official_banner")
    )

    if auto_persist:
        source_type = determine_source_type(candidate.image_url, result.classification)
        if source_type:
            image_verifier = ImageVerifier(session)
            updated = image_verifier.mark_image_verified(
                scholarship_id=scholarship.id,
                image_url=candidate.image_url,
                image_source_url=source_page or candidate.page_url,
                source_type=source_type,
                alt_text=candidate.alt_text,
                image_kind=validation.image_kind,
            )
            session.commit()

            audit_count = session.execute(
                select(ScholarshipVerificationHistory)
                .where(ScholarshipVerificationHistory.scholarship_id == scholarship.id)
                .where(ScholarshipVerificationHistory.field_name == "image_url")
            ).scalars().all()
            result.audit_records = len(audit_count)
            result.action = "persisted" if updated else "already_present"
        else:
            result.action = "no_source_type"
            result.rejection_reasons.append("Could not determine image source type")

    elif validation.confidence == "HIGH" and validation.image_kind == "official_logo":
        result.action = "human_review_logo"
        existing = session.execute(
            select(ImageReview)
            .where(ImageReview.scholarship_id == scholarship.id)
            .where(ImageReview.image_url == candidate.image_url)
            .where(ImageReview.decision == "pending")
        ).scalar_one_or_none()

        if existing is None:
            source_type = determine_source_type(candidate.image_url, result.classification)
            review_result = create_admin_image_review(
                session=session,
                scholarship_id=scholarship.id,
                image_url=candidate.image_url,
                image_kind=validation.image_kind or "official_logo",
                source_page=source_page,
                source_type=source_type,
                relevance_evidence=f"Relevance: {validation.relevance_score:.2f}. Reasons: {'; '.join(validation.rejection_reasons[:3])}",
                licensing_status=validation.licensing_status,
                licensing_evidence=validation.licensing_evidence,
                confidence=validation.confidence,
                reason_for_review=validation.human_review_reason or "Logo fallback candidate",
            )
            session.commit()
            result.review_created = True
            result.audit_records = 1
        else:
            result.audit_records = 1

    elif validation.confidence == "MEDIUM" or validation.status == ValidationStatus.HUMAN_REVIEW:
        result.action = "human_review"
        existing = session.execute(
            select(ImageReview)
            .where(ImageReview.scholarship_id == scholarship.id)
            .where(ImageReview.image_url == candidate.image_url)
            .where(ImageReview.decision == "pending")
        ).scalar_one_or_none()

        if existing is None:
            source_type = determine_source_type(candidate.image_url, result.classification)
            review_result = create_admin_image_review(
                session=session,
                scholarship_id=scholarship.id,
                image_url=candidate.image_url,
                image_kind=validation.image_kind or "program_image",
                source_page=source_page,
                source_type=source_type,
                relevance_evidence=f"Relevance: {validation.relevance_score:.2f}. Reasons: {'; '.join(validation.rejection_reasons[:3])}",
                licensing_status=validation.licensing_status,
                licensing_evidence=validation.licensing_evidence,
                confidence=validation.confidence,
                reason_for_review=validation.human_review_reason or "Medium confidence candidate",
            )
            session.commit()
            result.review_created = True
            result.audit_records = 1
        else:
            result.audit_records = 1

    else:
        result.action = "rejected_low_confidence"
        if not result.rejection_reasons:
            result.rejection_reasons.append(f"Low confidence ({validation.confidence}) or rejected status")

    return result


def get_remaining_count(session: Session) -> int:
    """Get count of scholarships still without verified images."""
    count = session.scalar(
        select(func.count(Scholarship.id))
        .where(Scholarship.image_verified_at.is_(None))
    )
    return count


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    session_factory = get_session_factory()
    session = session_factory()

    logger.info("Querying next 10 scholarships without verified images, excluding processed IDs...")

    processed_ids = get_processed_ids()
    scholarships = session.execute(
        select(Scholarship)
        .where(Scholarship.image_verified_at.is_(None))
        .where(~Scholarship.id.in_(processed_ids))
        .order_by(Scholarship.id)
        .limit(10)
    ).scalars().all()

    selected_ids = [s.id for s in scholarships]
    print("\n" + "=" * 80)
    print("BATCH 4 — Selected IDs for processing")
    print("=" * 80)
    print(f"Selected IDs: {selected_ids}")
    print(f"Count: {len(selected_ids)}")

    # Verify none were previously processed
    previously_processed = [sid for sid in selected_ids if sid in processed_ids]
    if previously_processed:
        print(f"ERROR: Previously processed IDs detected: {previously_processed}")
        session.close()
        return []

    # Verify image_verified_at is NULL for each
    all_null = True
    for s in scholarships:
        if s.image_verified_at is not None:
            print(f"ERROR: ID {s.id} has image_verified_at = {s.image_verified_at}")
            all_null = False
    if not all_null:
        session.close()
        return []

    print("Verification passed: all IDs are new and have image_verified_at = NULL")
    print("=" * 80)

    logger.info("Found %d scholarships to process", len(scholarships))

    results: list[BatchResult] = []

    for scholarship in scholarships:
        try:
            r = process_scholarship(session, scholarship)
            results.append(r)
            logger.info("Processed ID %d -> %s", r.scholarship_id, r.action)
        except Exception as exc:
            logger.exception("Failed to process scholarship %d: %s", scholarship.id, exc)
            results.append(BatchResult(
                scholarship_id=scholarship.id,
                title=scholarship.title,
                classification="UNKNOWN",
                official_source_url=scholarship.official_source_url,
                best_image_url=None,
                source_page=None,
                confidence=None,
                status=None,
                rejection_reasons=[str(exc)],
                action="error",
            ))

    session.close()

    # Print summary
    print("\n" + "=" * 80)
    print("BATCH 4 RESULTS")
    print("=" * 80)

    for r in results:
        print(f"\nID {r.scholarship_id}: {r.title}")
        print(f"  Classification: {r.classification}")
        print(f"  Official Source: {r.official_source_url}")
        print(f"  Best Image URL:  {r.best_image_url}")
        print(f"  Source Page:     {r.source_page}")
        print(f"  Confidence:      {r.confidence}")
        print(f"  Status:          {r.status}")
        print(f"  Action:          {r.action}")
        if r.rejection_reasons:
            print(f"  Reasons:         {'; '.join(r.rejection_reasons[:3])}")
        print(f"  Audit Records:   {r.audit_records}")
        print(f"  Review Created:  {r.review_created}")

    # Statistics
    persisted = sum(1 for r in results if r.action == "persisted")
    already_present = sum(1 for r in results if r.action == "already_present")
    human_review = sum(1 for r in results if r.action == "human_review")
    rejected = sum(1 for r in results if r.action == "rejected_low_confidence")
    no_candidate = sum(1 for r in results if r.action == "no_candidate_found")
    errors = sum(1 for r in results if r.action == "error")

    print("\n" + "-" * 80)
    print("SUMMARY")
    print("-" * 80)
    print(f"Total processed:     {len(results)}")
    print(f"Persisted (new):     {persisted}")
    print(f"Already present:     {already_present}")
    print(f"Human review:        {human_review}")
    print(f"Rejected (low):      {rejected}")
    print(f"No candidate found:  {no_candidate}")
    print(f"Errors:              {errors}")

    # Remaining count
    session_factory2 = get_session_factory()
    session2 = session_factory2()
    remaining = session2.execute(
        select(func.count(Scholarship.id))
        .where(Scholarship.image_verified_at.is_(None))
    ).scalar()
    session2.close()

    print(f"\nRemaining scholarships without verified images: {remaining}")
    print("=" * 80)

    return results


if __name__ == "__main__":
    main()
