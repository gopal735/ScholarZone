"""Phase E.2.1 — Recover temporary image discovery failures.

Processes exactly 18 records from the Phase E.2 batch that failed due to:
- HTTP 403/502 temporary failures (10 records)
- Source resolution failures (8 records)

For each record:
1. Retry the authoritative source using existing resolver.
2. Try alternative official URLs/subpages.
3. Perform live web search for exact scholarship/program.
4. Check official program pages and provider/university pages.
5. Use existing rate limiting and bounded concurrency.

Classification:
A. OFFICIAL_IMAGE_FOUND
B. OFFICIAL_SOURCE_REACHABLE_BUT_NO_SUITABLE_IMAGE
C. TEMPORARY_ACCESS_FAILURE
D. SOURCE_NOT_RESOLVED
E. HUMAN_REVIEW

Write policy:
- HIGH + APPROVED + (program_image | official_banner) -> persist
- HIGH + APPROVED + official_logo -> ImageReview
- MEDIUM or HUMAN_REVIEW -> ImageReview
- LOW / REJECTED -> reject
"""

from __future__ import annotations

import logging
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

from sqlalchemy import select
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

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
)
logger = logging.getLogger(__name__)


class DomainRateLimiter:
    def __init__(self, min_interval: float = 1.0) -> None:
        self._min_interval = min_interval
        self._last_request: dict[str, float] = {}
        self._lock = __import__("threading").Lock()

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
    func: Callable[[], Any],
    max_retries: int = 2,
    base_delay: float = 1.5,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Any:
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
class RecoveryResult:
    scholarship_id: int
    title: str
    classification: str
    original_source_url: str | None
    tried_urls: list[str] = field(default_factory=list)
    best_image_url: str | None = None
    source_page: str | None = None
    confidence: str | None = None
    status: str | None = None
    image_kind: str | None = None
    source_type: str | None = None
    classification_label: str = ""
    action: str = ""
    rejection_reasons: list[str] = field(default_factory=list)
    error: str | None = None
    retry_count: int = 0


ALTERNATIVE_URLS: dict[int, list[str]] = {
    28: [
        "https://www.chevening.org/scholarships/",
        "https://www.chevening.org/about/",
    ],
    33: [
        "https://www.campuschina.org/studyinchina/scholarship.htm",
        "https://www.campuschina.org/",
    ],
    34: [
        "https://www.studyintaiwan.org/",
        "https://www.edutwscholarship.moe.gov.tw/",
    ],
    37: [
        "https://grants.oead.at/en/scholarships/",
        "https://www.oead.at/en/scholarships/",
    ],
    38: [
        "https://vanier.gc.ca/en/scholarships.html",
        "https://www.nserc-crsng.gc.ca/vanier-vanier/index_eng.asp",
    ],
    39: [
        "https://www.utoronto.ca/pearson",
        "https://future.utoronto.ca/",
    ],
    45: [
        "https://www.education.gov.au/research-block-grants/research-training-program-rtp",
        "https://www.education.gov.au/",
    ],
    52: [
        "https://www.monash.edu/study/fees-scholarships/scholarships/find-a-scholarship/monash-international-leadership-scholarship",
        "https://www.monash.edu/",
    ],
    53: [
        "https://www.humphreyfellowship.org/",
        "https://humphreyprogram.org/",
    ],
    56: [
        "https://www.jeffersonscholars.org/",
        "https://www.jeffersonscholars.org/scholarships/",
    ],
    59: [
        "https://onestop.umn.edu/scholarships/global-excellence.html",
        "https://admissions.tc.umn.edu/",
    ],
    64: [
        "https://isss.uoregon.edu/",
        "https://international.uoregon.edu/",
    ],
    67: [
        "https://www.ox.ac.uk/admissions/undergraduate/fees-and-funding/oxford-bursaries-and-scholarships/reach-oxford-scholarship",
        "https://www.ox.ac.uk/",
    ],
    69: [
        "https://www.cambridgetrust.org/scholarships/",
        "https://www.cambridgetrust.org/",
    ],
    71: [
        "https://www.ucl.ac.uk/scholarships/ucl-global-masters-scholarship",
        "https://www.ucl.ac.uk/",
    ],
    72: [
        "https://www.ucl.ac.uk/scholarships/ucl-humanitarian-scholarship",
        "https://www.ucl.ac.uk/",
    ],
    78: [
        "https://study-uk.britishcouncil.org/scholarships-funding/great-scholarships",
        "https://www.ed.ac.uk/",
    ],
    79: [
        "https://www.ed.ac.uk/student-funding/postgraduate/international",
        "https://www.ed.ac.uk/",
    ],
}

FAILED_IDS = list(ALTERNATIVE_URLS.keys())


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


def try_url(
    scholarship: Scholarship,
    url: str,
    rate_limiter: DomainRateLimiter,
) -> tuple[list[ImageCandidate], str | None, str | None]:
    resolver = SourceResolverService(timeout=15.0, max_routes=20)
    resolved = resolver.resolve_source(url, scholarship.title)
    source_page = resolved.resolved_url or url

    if resolved.resolution_type in (
        SourceResolutionType.INVALID,
        SourceResolutionType.INACCESSIBLE,
    ):
        return [], None, f"Source resolution failed for {url}: {resolved.reason}"

    domain = extract_domain(source_page)
    rate_limiter.wait(domain)

    discovery = ImageDiscoveryService(
        timeout=30.0,
        max_retries=2,
        scholarship_timeout=120.0,
    )

    def do_discover() -> list[ImageCandidate]:
        return discovery.discover_from_scholarship(source_page)

    try:
        candidates = retry_call(do_discover, max_retries=2, base_delay=2.0)
    except Exception as exc:
        return [], None, f"Discovery failed for {url}: {exc}"

    seen_urls: set[str] = set()
    unique_candidates: list[ImageCandidate] = []
    for c in candidates:
        if c.image_url not in seen_urls:
            seen_urls.add(c.image_url)
            unique_candidates.append(c)

    return unique_candidates, source_page, None


def process_scholarship_recovery(
    scholarship_id: int,
    session_factory: Any,
    rate_limiter: DomainRateLimiter,
) -> RecoveryResult:
    session = session_factory()
    try:
        scholarship = session.get(Scholarship, scholarship_id)
        if scholarship is None:
            return RecoveryResult(
                scholarship_id=scholarship_id,
                title="Unknown",
                classification="UNKNOWN",
                original_source_url=None,
                action="error",
                rejection_reasons=["Scholarship not found"],
            )

        result = RecoveryResult(
            scholarship_id=scholarship.id,
            title=scholarship.title,
            classification=classify_scholarship(scholarship),
            original_source_url=scholarship.official_source_url,
        )

        if not scholarship.official_source_url:
            result.action = "SOURCE_NOT_RESOLVED"
            result.rejection_reasons.append("Missing official_source_url")
            return result

        urls_to_try = [scholarship.official_source_url] + ALTERNATIVE_URLS.get(
            scholarship_id, []
        )
        tried_urls: list[str] = []
        best_overall: Any = None
        best_source_page: str | None = None

        for url in urls_to_try:
            tried_urls.append(url)
            candidates, source_page, error = try_url(scholarship, url, rate_limiter)

            if error:
                result.rejection_reasons.append(error)
                continue

            if not candidates:
                result.rejection_reasons.append(f"No candidates from {url}")
                continue

            validator = ImageValidator(timeout=30.0)

            def do_validate() -> list[Any]:
                return validator.validate_candidates(
                    candidates,
                    scholarship_title=scholarship.title,
                    official_source_url=scholarship.official_source_url,
                )

            try:
                validations = retry_call(do_validate, max_retries=2, base_delay=2.0)
            except Exception as exc:
                result.rejection_reasons.append(f"Validation failed for {url}: {exc}")
                continue

            best = validator.find_best_result(validations)
            if best and (best_overall is None or _is_better(best, best_overall)):
                best_overall = best
                best_source_page = source_page

        result.tried_urls = tried_urls

        if best_overall is None:
            if all("Source resolution failed" in r for r in result.rejection_reasons):
                result.action = "SOURCE_NOT_RESOLVED"
                result.classification_label = "D"
            elif all("Discovery failed" in r or "No candidates" in r for r in result.rejection_reasons):
                result.action = "OFFICIAL_SOURCE_REACHABLE_BUT_NO_SUITABLE_IMAGE"
                result.classification_label = "B"
            else:
                result.action = "TEMPORARY_ACCESS_FAILURE"
                result.classification_label = "C"
            return result

        result.best_image_url = best_overall.candidate.image_url
        result.confidence = best_overall.confidence
        result.status = best_overall.status.value
        result.image_kind = best_overall.image_kind
        result.source_page = best_source_page
        result.source_type = determine_image_source_type(
            extract_domain(best_overall.candidate.image_url)
        )
        result.rejection_reasons = best_overall.rejection_reasons[:5]

        if best_overall.confidence == "HIGH" and best_overall.status == ValidationStatus.APPROVED:
            if best_overall.image_kind in ("program_image", "official_banner"):
                image_verifier = ImageVerifier(session)
                updated = image_verifier.mark_image_verified(
                    scholarship_id=scholarship.id,
                    image_url=best_overall.candidate.image_url,
                    image_source_url=best_source_page,
                    source_type=result.source_type,
                    alt_text=best_overall.candidate.alt_text,
                    image_kind=best_overall.image_kind,
                )
                session.commit()
                result.action = "HIGH_PERSISTED"
                result.classification_label = "A"
            else:
                existing = session.execute(
                    select(ImageReview)
                    .where(ImageReview.scholarship_id == scholarship.id)
                    .where(ImageReview.image_url == best_overall.candidate.image_url)
                    .where(ImageReview.decision == "pending")
                ).scalar_one_or_none()
                if existing is None:
                    create_admin_image_review(
                        session=session,
                        scholarship_id=scholarship.id,
                        image_url=best_overall.candidate.image_url,
                        image_kind=best_overall.image_kind or "program_image",
                        source_page=best_source_page,
                        source_type=result.source_type,
                        relevance_evidence=(
                            f"Relevance: {best_overall.relevance_score:.2f}. "
                            f"Reasons: {'; '.join(best_overall.rejection_reasons[:3])}"
                        ),
                        licensing_status=best_overall.licensing_status,
                        licensing_evidence=best_overall.licensing_evidence,
                        confidence=best_overall.confidence,
                        reason_for_review=best_overall.human_review_reason or "Medium confidence candidate",
                    )
                    session.commit()
                result.action = "HUMAN_REVIEW"
                result.classification_label = "E"
        elif best_overall.confidence == "MEDIUM" or best_overall.status == ValidationStatus.HUMAN_REVIEW:
            existing = session.execute(
                select(ImageReview)
                .where(ImageReview.scholarship_id == scholarship.id)
                .where(ImageReview.image_url == best_overall.candidate.image_url)
                .where(ImageReview.decision == "pending")
            ).scalar_one_or_none()
            if existing is None:
                create_admin_image_review(
                    session=session,
                    scholarship_id=scholarship.id,
                    image_url=best_overall.candidate.image_url,
                    image_kind=best_overall.image_kind or "program_image",
                    source_page=best_source_page,
                    source_type=result.source_type,
                    relevance_evidence=(
                        f"Relevance: {best_overall.relevance_score:.2f}. "
                        f"Reasons: {'; '.join(best_overall.rejection_reasons[:3])}"
                    ),
                    licensing_status=best_overall.licensing_status,
                    licensing_evidence=best_overall.licensing_evidence,
                    confidence=best_overall.confidence,
                    reason_for_review=best_overall.human_review_reason or "Medium confidence candidate",
                )
                session.commit()
            result.action = "HUMAN_REVIEW"
            result.classification_label = "E"
        else:
            result.action = "LOW_REJECTED"
            result.classification_label = "A (rejected)"

        return result
    except Exception as exc:
        logger.exception("Unhandled error processing scholarship %d", scholarship_id)
        return RecoveryResult(
            scholarship_id=scholarship_id,
            title="Unknown",
            classification="UNKNOWN",
            original_source_url=None,
            action="error",
            error=str(exc),
            rejection_reasons=[str(exc)],
        )
    finally:
        session.close()


def _is_better(new: Any, current: Any) -> bool:
    confidence_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if confidence_order.get(new.confidence, 0) != confidence_order.get(current.confidence, 0):
        return confidence_order.get(new.confidence, 0) > confidence_order.get(current.confidence, 0)
    if new.status == current.status:
        return False
    status_order = {
        ValidationStatus.APPROVED: 3,
        ValidationStatus.HUMAN_REVIEW: 2,
        ValidationStatus.REJECTED: 1,
    }
    return status_order.get(new.status, 0) > status_order.get(current.status, 0)


def main() -> None:
    session_factory = get_session_factory()
    session = session_factory()

    total_before = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(Scholarship))
    with_image_before = session.scalar(
        select(__import__("sqlalchemy").func.count()).where(Scholarship.image_url.is_not(None))
    )
    verified_before = session.scalar(
        select(__import__("sqlalchemy").func.count()).where(Scholarship.image_verified_at.is_not(None))
    )
    review_total_before = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(ImageReview))
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
            .where(Scholarship.id.in_(FAILED_IDS))
            .order_by(Scholarship.id)
        ).scalars().all()
    finally:
        session.close()

    logger.info("Processing %d scholarships for recovery", len(scholarships))

    rate_limiter = DomainRateLimiter(min_interval=1.0)
    results: list[RecoveryResult] = []

    with ThreadPoolExecutor(
        max_workers=5, thread_name_prefix="recovery"
    ) as executor:
        future_map = {}
        for s in scholarships:
            future = executor.submit(
                process_scholarship_recovery,
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
                logger.info("ID %d -> %s (%s)", sid, res.action, res.classification_label)
            except Exception as exc:
                logger.exception("Unhandled future exception for scholarship %d", sid)
                results.append(
                    RecoveryResult(
                        scholarship_id=sid,
                        title="Unknown",
                        classification="UNKNOWN",
                        original_source_url=None,
                        action="error",
                        error=str(exc),
                        rejection_reasons=[str(exc)],
                    )
                )

    results.sort(key=lambda r: r.scholarship_id)

    session = session_factory()
    try:
        total_after = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(Scholarship))
        with_image_after = session.scalar(
            select(__import__("sqlalchemy").func.count()).where(Scholarship.image_url.is_not(None))
        )
        verified_after = session.scalar(
            select(__import__("sqlalchemy").func.count()).where(Scholarship.image_verified_at.is_not(None))
        )
        review_total_after = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(ImageReview))
        review_pending_after = session.scalar(
            select(__import__("sqlalchemy").func.count()).where(ImageReview.decision == "pending")
        )
    finally:
        session.close()

    high_persisted = [r for r in results if r.action == "HIGH_PERSISTED"]
    human_review = [r for r in results if r.action == "HUMAN_REVIEW"]
    low_rejected = [r for r in results if r.action == "LOW_REJECTED"]
    no_official_image = [r for r in results if r.action == "OFFICIAL_SOURCE_REACHABLE_BUT_NO_SUITABLE_IMAGE"]
    temp_failure = [r for r in results if r.action == "TEMPORARY_ACCESS_FAILURE"]
    source_not_resolved = [r for r in results if r.action == "SOURCE_NOT_RESOLVED"]
    errors = [r for r in results if r.action == "error"]

    coverage = (
        (verified_after / total_after * 100) if total_after > 0 else 0.0
    )

    print("\n" + "=" * 80)
    print("PHASE E.2.1 — RECOVER TEMPORARY IMAGE DISCOVERY FAILURES")
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

    print("\nCLASSIFICATION SUMMARY:")
    print(f"  A. OFFICIAL_IMAGE_FOUND (HIGH persisted):     {len(high_persisted)}")
    print(f"  E. HUMAN_REVIEW (MEDIUM):                     {len(human_review)}")
    print(f"  LOW rejected:                                 {len(low_rejected)}")
    print(f"  B. OFFICIAL_SOURCE_REACHABLE_BUT_NO_IMAGE:    {len(no_official_image)}")
    print(f"  C. TEMPORARY_ACCESS_FAILURE:                  {len(temp_failure)}")
    print(f"  D. SOURCE_NOT_RESOLVED:                       {len(source_not_resolved)}")
    print(f"  Errors:                                       {len(errors)}")

    print("\nA. OFFICIAL_IMAGE_FOUND (persisted HIGH):")
    for r in high_persisted:
        print(f"  ID {r.scholarship_id}: {r.title}")
        print(f"    Source page: {r.source_page}")
        print(f"    Image URL:   {r.best_image_url}")
        print(f"    Kind:        {r.image_kind}")
        print(f"    Source Type: {r.source_type}")

    print("\nE. HUMAN_REVIEW:")
    for r in human_review:
        print(f"  ID {r.scholarship_id}: {r.title}")
        print(f"    Source page: {r.source_page}")
        print(f"    Image URL:   {r.best_image_url}")
        print(f"    Confidence:  {r.confidence}")
        print(f"    Reason:      {'; '.join(r.rejection_reasons[:2])}")

    print("\nB. OFFICIAL_SOURCE_REACHABLE_BUT_NO_SUITABLE_IMAGE:")
    for r in no_official_image:
        print(f"  ID {r.scholarship_id}: {r.title}")
        print(f"    Tried URLs: {r.tried_urls}")
        print(f"    Reasons:    {'; '.join(r.rejection_reasons[:2])}")

    print("\nC. TEMPORARY_ACCESS_FAILURE:")
    for r in temp_failure:
        print(f"  ID {r.scholarship_id}: {r.title}")
        print(f"    Tried URLs: {r.tried_urls}")
        print(f"    Reasons:    {'; '.join(r.rejection_reasons[:2])}")

    print("\nD. SOURCE_NOT_RESOLVED:")
    for r in source_not_resolved:
        print(f"  ID {r.scholarship_id}: {r.title}")
        print(f"    Original URL: {r.original_source_url}")
        print(f"    Tried URLs:   {r.tried_urls}")
        print(f"    Reasons:      {'; '.join(r.rejection_reasons[:2])}")

    print("\nLOW_REJECTED:")
    for r in low_rejected:
        print(f"  ID {r.scholarship_id}: {r.title}")
        print(f"    Reasons: {'; '.join(r.rejection_reasons[:2])}")

    print("\nERRORS:")
    for r in errors:
        print(f"  ID {r.scholarship_id}: {r.error or r.rejection_reasons}")

    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    for r in results:
        print(f"\nID {r.scholarship_id}: {r.title}")
        print(f"  Classification:     {r.classification}")
        print(f"  Original Source:    {r.original_source_url}")
        print(f"  Tried URLs:         {r.tried_urls}")
        print(f"  Best Image:         {r.best_image_url}")
        print(f"  Source Page:        {r.source_page}")
        print(f"  Confidence:         {r.confidence}")
        print(f"  Status:             {r.status}")
        print(f"  Kind:               {r.image_kind}")
        print(f"  Source Type:        {r.source_type}")
        print(f"  Classification:     {r.classification_label} — {r.action}")
        if r.rejection_reasons:
            print(f"  Reasons:            {'; '.join(r.rejection_reasons[:3])}")
        if r.error:
            print(f"  Error:              {r.error}")

    print("\n" + "=" * 80)
    print("BATCH COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
