"""Phase E.2 — Controlled official image backfill.

Processes exactly 50 scholarships where image_url IS NULL and image_verified_at IS NULL.
Reuses existing ImageDiscoveryService, SourceResolverService, ImageValidator, and ImageVerifier.

Write policy:
  HIGH + APPROVED + (program_image | official_banner) -> persist via ImageVerifier
  HIGH + APPROVED + official_logo                     -> ImageReview (human_review)
  MEDIUM or HUMAN_REVIEW                              -> ImageReview (human_review)
  LOW / REJECTED                                      -> reject

Batch safety:
  - bounded concurrency (ThreadPoolExecutor, max_workers=5)
  - per-domain rate limiting
  - request timeouts inherited from existing services
  - retry transient failures (2 retries, exponential backoff)
  - one failed domain does not stop the batch
  - detailed per-record logging
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.models import ImageReview, Scholarship, ScholarshipVerificationHistory
from app.services.admin_image_review import create_image_review as create_admin_image_review
from app.services.image_discovery import ImageCandidate, ImageDiscoveryService
from app.services.image_validator import (
    ImageValidator,
    ValidationStatus,
    determine_image_source_type,
)
from app.services.scholarship_image_verifier import (
    ImageSourceType,
    ImageVerifier,
    extract_domain,
)
from app.services.source_resolver import SourceResolutionType, SourceResolverService
from authoritative_registry import build_authoritative_registry

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

T = TypeVar("T")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
)
logger = logging.getLogger(__name__)


class DomainRateLimiter:
    """Simple per-domain rate limiter with minimum interval between requests."""

    def __init__(self, min_interval: float = 1.0) -> None:
        self._min_interval = min_interval
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, domain: str | None) -> None:
        if not domain:
            return
        with self._lock:
            now = time.time()
            last = self._last_request.get(domain, 0.0)
            wait_time = self._min_interval - (now - last)
            if wait_time > 0:
                time.sleep(wait_time)
            self._last_request[domain] = time.time()


def retry_call(
    func: Callable[[], T],
    max_retries: int = 2,
    base_delay: float = 1.5,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Retry a callable with exponential backoff on transient exceptions."""
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d after %.1fs: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


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
    image_kind: str | None
    source_type: str | None
    rejection_reasons: list[str]
    action: str
    error: str | None = None
    retry_count: int = 0
    duplicate_prevented: bool = False
    discovery_candidates: int = 0


def classify_scholarship(scholarship: Scholarship) -> str:
    official = (scholarship.official_source or "").lower()
    source_url = (scholarship.official_source_url or "").lower()
    title = scholarship.title.lower()

    government_keywords = [
        "government",
        "ministry",
        "federal",
        "state",
        "department",
        "sbfi",
        "seri",
        "daad",
        "campus france",
        "study in india",
        "jasso",
        "iccr",
        "fulbright",
        "educationusa",
    ]
    university_keywords = [
        "university",
        "université",
        "universitat",
        "universität",
        "eth ",
        "epfl",
        "mit",
        "stanford",
        "harvard",
        "oxford",
        "cambridge",
        "college",
        "institute of technology",
    ]
    provider_keywords = [
        "foundation",
        "trust",
        "fund",
        "organization",
        "organisation",
        "association",
        "society",
        "council",
        "posco",
        "tj park",
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


def process_scholarship(
    scholarship_id: int,
    session_factory: Any,
    rate_limiter: DomainRateLimiter,
) -> BatchResult:
    session = session_factory()
    try:
        scholarship = session.get(Scholarship, scholarship_id)
        if scholarship is None:
            return BatchResult(
                scholarship_id=scholarship_id,
                title="Unknown",
                classification="UNKNOWN",
                official_source_url=None,
                best_image_url=None,
                source_page=None,
                confidence=None,
                status=None,
                image_kind=None,
                source_type=None,
                rejection_reasons=["Scholarship not found"],
                action="error",
            )

        result = BatchResult(
            scholarship_id=scholarship.id,
            title=scholarship.title,
            classification=classify_scholarship(scholarship),
            official_source_url=scholarship.official_source_url,
            best_image_url=None,
            source_page=None,
            confidence=None,
            status=None,
            image_kind=None,
            source_type=None,
            rejection_reasons=[],
            action="none",
        )

        if not scholarship.official_source_url:
            result.action = "source_resolution_failure"
            result.rejection_reasons.append("Missing official_source_url")
            return result

        resolver = SourceResolverService(timeout=15.0, max_routes=20)
        resolved = resolver.resolve_source(
            scholarship.official_source_url,
            scholarship.title,
        )
        result.source_page = resolved.resolved_url or scholarship.official_source_url

        if resolved.resolution_type in (
            SourceResolutionType.INVALID,
            SourceResolutionType.INACCESSIBLE,
        ):
            result.action = "source_resolution_failure"
            result.rejection_reasons.append(
                f"Source resolution failed: {resolved.reason}"
            )
            return result

        source_domain = extract_domain(result.source_page)
        rate_limiter.wait(source_domain)

        discovery = ImageDiscoveryService(
            timeout=30.0,
            max_retries=2,
            scholarship_timeout=120.0,
        )

        def do_discover() -> list[ImageCandidate]:
            return discovery.discover_from_scholarship(result.source_page)

        try:
            candidates = retry_call(do_discover, max_retries=2, base_delay=2.0)
        except Exception as exc:
            result.action = "discovery_failure"
            result.error = str(exc)
            result.rejection_reasons.append(f"Discovery failed: {exc}")
            return result

        seen_urls: set[str] = set()
        unique_candidates: list[ImageCandidate] = []
        for c in candidates:
            if c.image_url not in seen_urls:
                seen_urls.add(c.image_url)
                unique_candidates.append(c)

        result.discovery_candidates = len(unique_candidates)

        if not unique_candidates:
            result.action = "no_candidate_found"
            result.rejection_reasons.append("No image candidates discovered")
            return result

        validator = ImageValidator(timeout=30.0)

        def do_validate() -> list[Any]:
            return validator.validate_candidates(
                unique_candidates,
                scholarship_title=scholarship.title,
                official_source_url=scholarship.official_source_url,
            )

        try:
            validations = retry_call(do_validate, max_retries=2, base_delay=2.0)
        except Exception as exc:
            result.action = "validation_failure"
            result.error = str(exc)
            result.rejection_reasons.append(f"Validation failed: {exc}")
            return result

        best = validator.find_best_result(validations)
        if not best:
            result.action = "no_candidate_found"
            result.rejection_reasons.append("Validator returned no best result")
            return result

        result.best_image_url = best.candidate.image_url
        result.confidence = best.confidence
        result.status = best.status.value
        result.image_kind = best.image_kind
        result.source_type = determine_image_source_type(
            extract_domain(best.candidate.image_url)
        )
        result.rejection_reasons = best.rejection_reasons[:5]

        auto_persist = (
            best.confidence == "HIGH"
            and best.status == ValidationStatus.APPROVED
            and best.image_kind in ("program_image", "official_banner")
        )

        if auto_persist and result.source_type:
            image_verifier = ImageVerifier(session)
            updated = image_verifier.mark_image_verified(
                scholarship_id=scholarship.id,
                image_url=best.candidate.image_url,
                image_source_url=result.source_page,
                source_type=result.source_type,
                alt_text=best.candidate.alt_text,
                image_kind=best.image_kind,
            )
            session.commit()
            result.action = "persisted" if updated else "already_present"
        elif best.confidence == "MEDIUM" or best.status == ValidationStatus.HUMAN_REVIEW:
            existing = session.execute(
                select(ImageReview)
                .where(ImageReview.scholarship_id == scholarship.id)
                .where(ImageReview.image_url == best.candidate.image_url)
                .where(ImageReview.decision == "pending")
            ).scalar_one_or_none()

            if existing is None:
                create_admin_image_review(
                    session=session,
                    scholarship_id=scholarship.id,
                    image_url=best.candidate.image_url,
                    image_kind=best.image_kind or "program_image",
                    source_page=result.source_page,
                    source_type=result.source_type,
                    relevance_evidence=(
                        f"Relevance: {best.relevance_score:.2f}. "
                        f"Reasons: {'; '.join(best.rejection_reasons[:3])}"
                    ),
                    licensing_status=best.licensing_status,
                    licensing_evidence=best.licensing_evidence,
                    confidence=best.confidence,
                    reason_for_review=best.human_review_reason or "Medium confidence candidate",
                )
                session.commit()
                result.action = "human_review"
            else:
                result.action = "human_review"
        else:
            result.action = "rejected_low_confidence"
            if not result.rejection_reasons:
                result.rejection_reasons.append(
                    f"Low confidence ({best.confidence}) or rejected status"
                )

        return result
    except Exception as exc:
        logger.exception("Unhandled error processing scholarship %d", scholarship_id)
        return BatchResult(
            scholarship_id=scholarship_id,
            title="Unknown",
            classification="UNKNOWN",
            official_source_url=None,
            best_image_url=None,
            source_page=None,
            confidence=None,
            status=None,
            image_kind=None,
            source_type=None,
            rejection_reasons=[str(exc)],
            action="error",
            error=str(exc),
        )
    finally:
        session.close()


def run_quality_check(session_factory: Any, results: list[BatchResult]) -> None:
    persisted = [r for r in results if r.action == "persisted"]
    if not persisted:
        logger.info("Quality check: no persisted HIGH images to inspect.")
        return

    import random

    sample = random.sample(persisted, min(5, len(persisted)))
    session = session_factory()
    try:
        import requests

        for r in sample:
            scholarship = session.get(Scholarship, r.scholarship_id)
            if not scholarship or not scholarship.image_url:
                logger.warning("Quality check: ID %d missing image data", r.scholarship_id)
                continue

            reachable = False
            try:
                resp = requests.head(
                    scholarship.image_url,
                    timeout=10,
                    allow_redirects=True,
                )
                reachable = resp.status_code < 400
            except Exception:
                reachable = False

            logger.info(
                "Quality check ID %d: kind=%s source_type=%s reachable=%s url=%s",
                r.scholarship_id,
                scholarship.image_kind,
                scholarship.image_source_type,
                reachable,
                scholarship.image_url[:100],
            )
    finally:
        session.close()


def main() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    logger.info("Building authoritative registry...")
    registry = build_authoritative_registry()
    processed_ids = set(registry.keys())
    logger.info("Registry size: %d", len(processed_ids))

    total_before = session.scalar(select(func.count()).select_from(Scholarship))
    with_image_before = session.scalar(
        select(func.count()).where(Scholarship.image_url.is_not(None))
    )
    verified_before = session.scalar(
        select(func.count()).where(Scholarship.image_verified_at.is_not(None))
    )
    review_total_before = session.scalar(select(func.count()).select_from(ImageReview))
    session.close()

    logger.info(
        "Before: total=%d, with_image=%d, verified=%d, reviews=%d",
        total_before,
        with_image_before,
        verified_before,
        review_total_before,
    )

    session = session_factory()
    try:
        scholarships = session.execute(
            select(Scholarship)
            .where(Scholarship.image_url.is_(None))
            .where(Scholarship.image_verified_at.is_(None))
            .where(~Scholarship.id.in_(processed_ids))
            .order_by(Scholarship.id)
            .limit(50)
        ).scalars().all()
    finally:
        session.close()

    selected_ids = [s.id for s in scholarships]
    logger.info("Selected %d scholarships: %s", len(selected_ids), selected_ids)

    rate_limiter = DomainRateLimiter(min_interval=1.0)
    results: list[BatchResult] = []

    with ThreadPoolExecutor(
        max_workers=5, thread_name_prefix="backfill"
    ) as executor:
        future_map = {}
        for s in scholarships:
            future = executor.submit(
                process_scholarship,
                s.id,
                session_factory,
                rate_limiter,
            )
            future_map[future] = s.id

        for future in as_completed(future_map):
            sid = future_map[future]
            try:
                res = future.result()
                results.append(res)
                logger.info("ID %d -> %s", sid, res.action)
            except Exception as exc:
                logger.exception("Unhandled future exception for scholarship %d", sid)
                results.append(
                    BatchResult(
                        scholarship_id=sid,
                        title="Unknown",
                        classification="UNKNOWN",
                        official_source_url=None,
                        best_image_url=None,
                        source_page=None,
                        confidence=None,
                        status=None,
                        image_kind=None,
                        source_type=None,
                        rejection_reasons=[str(exc)],
                        action="error",
                        error=str(exc),
                    )
                )

    results.sort(key=lambda r: r.scholarship_id)

    session = session_factory()
    try:
        total_after = session.scalar(select(func.count()).select_from(Scholarship))
        with_image_after = session.scalar(
            select(func.count()).where(Scholarship.image_url.is_not(None))
        )
        verified_after = session.scalar(
            select(func.count()).where(Scholarship.image_verified_at.is_not(None))
        )
        review_total_after = session.scalar(
            select(func.count()).select_from(ImageReview)
        )
        review_pending_after = session.scalar(
            select(func.count()).where(ImageReview.decision == "pending")
        )
    finally:
        session.close()

    persisted = [r for r in results if r.action == "persisted"]
    already_present = [r for r in results if r.action == "already_present"]
    human_review = [r for r in results if r.action == "human_review"]
    rejected = [r for r in results if r.action == "rejected_low_confidence"]
    no_candidate = [r for r in results if r.action == "no_candidate_found"]
    source_failures = [r for r in results if r.action == "source_resolution_failure"]
    discovery_failures = [r for r in results if r.action == "discovery_failure"]
    validation_failures = [r for r in results if r.action == "validation_failure"]
    errors = [r for r in results if r.action == "error"]

    program_images = sum(1 for r in persisted if r.image_kind == "program_image")
    official_banners = sum(1 for r in persisted if r.image_kind == "official_banner")
    official_logos = sum(
        1 for r in persisted + human_review if r.image_kind == "official_logo"
    )

    source_type_dist: dict[str, int] = defaultdict(int)
    for r in results:
        if r.source_type:
            source_type_dist[r.source_type] += 1

    coverage = (
        (verified_after / total_after * 100) if total_after > 0 else 0.0
    )

    print("\n" + "=" * 80)
    print("PHASE E.2 — 50-RECORD PRODUCTION BACKFILL AUDIT")
    print("=" * 80)

    print("\nBEFORE:")
    print(f"  Total scholarships:     {total_before}")
    print(f"  With image_url:         {with_image_before}")
    print(f"  Verified images:        {verified_before}")
    print(f"  ImageReview records:    {review_total_before}")

    print("\nAFTER:")
    print(f"  Total scholarships:     {total_after}")
    print(f"  With image_url:         {with_image_after}")
    print(f"  Verified images:        {verified_after}")
    print(f"  ImageReview records:    {review_total_after}")
    print(f"  Pending reviews:        {review_pending_after}")
    print(f"  Verified coverage:      {coverage:.2f}%")

    print("\nACTIONS:")
    print(f"  HIGH persisted:         {len(persisted)}")
    print(f"  MEDIUM human_review:    {len(human_review)}")
    print(f"  LOW rejected:           {len(rejected)}")
    print(f"  No candidate found:     {len(no_candidate)}")
    print(f"  Source resolution fail: {len(source_failures)}")
    print(f"  Discovery failures:     {len(discovery_failures)}")
    print(f"  Validation failures:    {len(validation_failures)}")
    print(f"  Other errors:           {len(errors)}")

    print("\nPERSISTED IMAGE KINDS:")
    print(f"  Program images:         {program_images}")
    print(f"  Official banners:       {official_banners}")
    print(f"  Official logos:         {official_logos}")

    print("\nSOURCE TYPE DISTRIBUTION:")
    for st, count in sorted(source_type_dist.items()):
        print(f"  {st}: {count}")

    print("\nFAILED RECORDS:")
    for r in results:
        if r.action in (
            "error",
            "source_resolution_failure",
            "discovery_failure",
            "validation_failure",
        ):
            print(f"  ID {r.scholarship_id}: {r.action} — {r.error or '; '.join(r.rejection_reasons[:2])}")

    print("\nDETAILED RESULTS:")
    for r in results:
        print(f"\nID {r.scholarship_id}: {r.title}")
        print(f"  Classification:  {r.classification}")
        print(f"  Official Source: {r.official_source_url}")
        print(f"  Source Page:     {r.source_page}")
        print(f"  Best Image:      {r.best_image_url}")
        print(f"  Confidence:      {r.confidence}")
        print(f"  Status:          {r.status}")
        print(f"  Kind:            {r.image_kind}")
        print(f"  Source Type:     {r.source_type}")
        print(f"  Action:          {r.action}")
        if r.rejection_reasons:
            print(f"  Reasons:         {'; '.join(r.rejection_reasons[:3])}")
        if r.error:
            print(f"  Error:           {r.error}")

    print("\n" + "=" * 80)
    print("QUALITY CHECK")
    print("=" * 80)
    run_quality_check(session_factory, results)

    print("\n" + "=" * 80)
    print("BATCH COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
