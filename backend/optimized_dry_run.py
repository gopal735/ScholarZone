"""Optimized dry-run for production-scale autonomous image discovery.

Processes a specific set of scholarship IDs with:
- Tier-by-tier discovery with early-stop
- Bounded concurrency (ThreadPoolExecutor)
- Per-request and per-scholarship timeouts
- Retry only transient failures (timeout/5xx)
- Fail-fast per scholarship
- No database writes

Read-only: never modifies database records.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import get_engine
from app.models import Scholarship
from app.services.image_discovery import ImageDiscoveryService, ImageCandidate
from app.services.image_validator import ImageValidator, ValidationStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
)
logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 4
PER_REQUEST_TIMEOUT = 20.0
PER_SCHOLARSHIP_TIMEOUT = 90.0
MAX_RETRIES = 2
TARGET_IDS = [26, 28, 30, 31, 32, 33, 34, 35, 36, 37]


@dataclass
class DryRunMetrics:
    scholarship_id: int
    title: str
    official_source_url: str | None
    classification: str = ""
    candidates_found: int = 0
    requests_made: int = 0
    timeout_count: int = 0
    blocked_403_count: int = 0
    transient_5xx_count: int = 0
    runtime_seconds: float = 0.0
    tiers_exhausted: list[str] = field(default_factory=list)
    best_candidate_url: str | None = None
    best_candidate_page_url: str | None = None
    best_candidate_method: str | None = None
    confidence: str | None = None
    image_kind: str | None = None
    status: str | None = None
    rejection_reasons: list[str] = field(default_factory=list)
    human_review_reason: str | None = None
    early_stop_reason: str | None = None
    error: str | None = None
    all_candidates: list[dict[str, Any]] = field(default_factory=list)
    network_retry_result: str | None = None
    is_temporarily_unavailable: bool = False
    is_genuinely_missing: bool = False
    retry_count: int = 0
    last_attempt_at: str | None = None
    next_retry_at: str | None = None
    failure_reason: str | None = None


def classify_scholarship(scholarship: Scholarship) -> str:
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


def _should_early_stop(validation, candidates_so_far: int) -> tuple[bool, str | None]:
    """Determine if discovery should stop early based on validation result."""
    if not validation:
        return False, None

    if validation.confidence == "HIGH" and validation.image_kind == "program_image":
        return True, "HIGH-confidence PROGRAM_IMAGE found"

    if validation.confidence == "HIGH" and validation.image_kind == "official_banner":
        return True, "HIGH-confidence OFFICIAL_BANNER found"

    if validation.confidence == "MEDIUM" and validation.image_kind == "program_image" and candidates_so_far >= 3:
        return True, "MEDIUM-confidence PROGRAM_IMAGE with sufficient candidates"

    return False, None


def _process_scholarship(scholarship_id: int) -> DryRunMetrics:
    """Process a single scholarship through optimized discovery pipeline."""
    start_time = time.time()
    metrics = DryRunMetrics(
        scholarship_id=scholarship_id,
        title="",
        official_source_url=None,
    )

    try:
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()

        scholarship = session.get(Scholarship, scholarship_id)
        if scholarship is None:
            metrics.error = f"Scholarship ID {scholarship_id} not found"
            return metrics

        metrics.title = scholarship.title
        metrics.official_source_url = scholarship.official_source_url
        metrics.classification = classify_scholarship(scholarship)

        session.close()

        if not scholarship.official_source_url:
            metrics.error = "No official_source_url"
            metrics.runtime_seconds = time.time() - start_time
            return metrics

        official_source_url = scholarship.official_source_url
        discovery = ImageDiscoveryService(
            timeout=PER_REQUEST_TIMEOUT,
            max_candidates=50,
            max_retries=MAX_RETRIES,
            scholarship_timeout=PER_SCHOLARSHIP_TIMEOUT,
        )
        validator = ImageValidator(timeout=PER_REQUEST_TIMEOUT)

        best_candidate = None
        best_validation = None
        all_candidates_summary = []
        candidates_so_far = 0

        for tier_name, added in discovery.discover_tier_by_tier(official_source_url):
            metrics.tiers_exhausted.append(tier_name)
            candidates_so_far += added

            if added > 0:
                candidates = discovery._candidates
                candidates_for_validation = [c for c in candidates if c.image_url.startswith("http")]
                if candidates_for_validation:
                    priority = {
                        "og:image": 0,
                        "twitter:image": 1,
                        "json-ld": 2,
                        "link-image-src": 3,
                        "html-img": 4,
                        "common-asset": 5,
                        "link-rel-icon": 6,
                    }
                    candidates_for_validation.sort(
                        key=lambda c: (
                            priority.get(c.discovery_method, 99),
                            -c.fallback_level,
                            -(len(c.alt_text or "")),
                        )
                    )
                    candidate = candidates_for_validation[0]
                    validation = validator.validate_candidate(
                        candidate,
                        scholarship_title=scholarship.title,
                        official_source_url=official_source_url,
                    )

                    all_candidates_summary.append({
                        "image_url": candidate.image_url,
                        "page_url": candidate.page_url,
                        "discovery_method": candidate.discovery_method,
                        "fallback_level": candidate.fallback_level,
                        "http_status": validation.http_status,
                        "content_type": validation.content_type,
                        "is_valid_image": validation.is_valid_image,
                        "is_official_domain": validation.is_official_domain,
                        "is_generic_image": validation.is_generic_image,
                        "is_ui_asset": validation.is_ui_asset,
                        "relevance_score": validation.relevance_score,
                        "confidence": validation.confidence,
                        "status": validation.status.value,
                        "image_kind": validation.image_kind,
                        "rejection_reasons": validation.rejection_reasons[:3],
                    })

                    if best_candidate is None:
                        best_candidate = candidate
                        best_validation = validation

                    stop, reason = _should_early_stop(validation, candidates_so_far)
                    if stop:
                        metrics.early_stop_reason = reason
                        break

            if discovery._is_timed_out():
                metrics.early_stop_reason = "Per-scholarship timeout exceeded"
                break

        metrics.candidates_found = len(discovery._candidates)
        metrics.requests_made = discovery._requests_made
        metrics.timeout_count = discovery._timeout_count
        metrics.blocked_403_count = discovery._blocked_count
        metrics.transient_5xx_count = discovery._transient_error_count
        metrics.runtime_seconds = round(time.time() - start_time, 2)
        metrics.all_candidates = all_candidates_summary

        if best_validation:
            metrics.best_candidate_url = best_candidate.image_url
            metrics.best_candidate_page_url = best_candidate.page_url
            metrics.best_candidate_method = best_candidate.discovery_method
            metrics.confidence = best_validation.confidence
            metrics.image_kind = best_validation.image_kind
            metrics.status = best_validation.status.value
            metrics.rejection_reasons = best_validation.rejection_reasons[:5]
            metrics.human_review_reason = best_validation.human_review_reason
            metrics.retry_count = best_validation.retry_count
            metrics.last_attempt_at = best_validation.last_attempt_at.isoformat() if best_validation.last_attempt_at else None
            metrics.next_retry_at = best_validation.next_retry_at.isoformat() if best_validation.next_retry_at else None
            metrics.failure_reason = best_validation.failure_reason
            if best_validation.status.value == "temp_unavailable":
                metrics.is_temporarily_unavailable = True
                metrics.network_retry_result = "exhausted_retries"
            elif best_validation.status.value == "genuinely_missing":
                metrics.is_genuinely_missing = True
                metrics.network_retry_result = "not_found"
            elif best_validation.is_reachable:
                metrics.network_retry_result = "success"
            else:
                metrics.network_retry_result = f"http_{best_validation.http_status}"
        else:
            metrics.status = "rejected"
            metrics.confidence = "LOW"
            if not metrics.rejection_reasons:
                metrics.rejection_reasons.append("No valid candidates found")

    except Exception as exc:
        logger.exception("Error processing scholarship %d", scholarship_id)
        metrics.error = str(exc)
        metrics.runtime_seconds = round(time.time() - start_time, 2)

    return metrics


def run_optimized_dry_run(ids: list[int], max_concurrency: int = MAX_CONCURRENCY) -> list[DryRunMetrics]:
    """Run optimized dry-run on specific scholarship IDs with bounded concurrency."""
    results: list[DryRunMetrics] = []
    cache_lock = threading.Lock()

    logger.info(
        "Submitting %d scholarships to ThreadPoolExecutor (max_workers=%d)",
        len(ids),
        max_concurrency,
    )

    with ThreadPoolExecutor(max_workers=max_concurrency, thread_name_prefix="dryrun") as executor:
        future_to_id = {}
        for sid in ids:
            future = executor.submit(_process_scholarship, sid)
            future_to_id[future] = sid

        completed = 0
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            completed += 1
            try:
                result = future.result()
                results.append(result)
                logger.info(
                    "Completed (%d/%d): ID %d -> status=%s confidence=%s candidates=%d time=%.2fs",
                    completed,
                    len(ids),
                    sid,
                    result.status,
                    result.confidence,
                    result.candidates_found,
                    result.runtime_seconds,
                )
            except Exception as exc:
                logger.exception("Unhandled error processing scholarship %d", sid)
                results.append(DryRunMetrics(
                    scholarship_id=sid,
                    title="",
                    official_source_url=None,
                    error=str(exc),
                    runtime_seconds=round(time.time() - start_time, 2),
                ))

    results.sort(key=lambda r: r.scholarship_id)
    return results


def print_report(results: list[DryRunMetrics]) -> None:
    """Print detailed dry-run report."""
    print("\n" + "=" * 100)
    print("OPTIMIZED DRY-RUN REPORT — 10 SCHOLARSHIPS")
    print("=" * 100)

    for r in results:
        print(f"\n--- ID {r.scholarship_id}: {r.title or 'Unknown'} ---")
        print(f"  Classification:      {r.classification}")
        print(f"  Official Source:     {r.official_source_url}")
        print(f"  Candidates Found:    {r.candidates_found}")
        print(f"  Requests Made:       {r.requests_made}")
        print(f"  Runtime:             {r.runtime_seconds:.2f}s")
        print(f"  Timeouts:            {r.timeout_count}")
        print(f"  Blocked (403):       {r.blocked_403_count}")
        print(f"  Transient 5xx:       {r.transient_5xx_count}")
        print(f"  Tiers Exhausted:     {', '.join(r.tiers_exhausted) or 'none'}")
        if r.early_stop_reason:
            print(f"  Early Stop:          {r.early_stop_reason}")
        print(f"  Best Image URL:      {r.best_candidate_url}")
        print(f"  Best Page URL:       {r.best_candidate_page_url}")
        print(f"  Discovery Method:    {r.best_candidate_method}")
        print(f"  Confidence:          {r.confidence}")
        print(f"  Image Kind:          {r.image_kind}")
        print(f"  Status:              {r.status}")
        if r.is_temporarily_unavailable:
            print(f"  Network Result:      TEMPORARILY UNAVAILABLE (retries exhausted)")
        elif r.is_genuinely_missing:
            print(f"  Network Result:      GENUINELY MISSING (HTTP 404/410)")
        elif r.network_retry_result:
            print(f"  Network Result:      {r.network_retry_result}")
        if r.failure_reason:
            print(f"  Failure Reason:      {r.failure_reason}")
        if r.retry_count:
            print(f"  Retry Count:         {r.retry_count}")
        if r.last_attempt_at:
            print(f"  Last Attempt:        {r.last_attempt_at}")
        if r.next_retry_at:
            print(f"  Next Retry At:       {r.next_retry_at}")
        if r.rejection_reasons:
            print(f"  Rejection Reasons:   {'; '.join(r.rejection_reasons[:3])}")
        if r.human_review_reason:
            print(f"  Human Review Reason: {r.human_review_reason}")
        if r.error:
            print(f"  ERROR:               {r.error}")
        if r.all_candidates:
            print(f"  Top Candidates:")
            for c in r.all_candidates[:5]:
                print(f"    - {c['image_url'][:80]} | {c['discovery_method']} | {c['confidence']} | {c['status']}")

    print("\n" + "-" * 100)
    print("AGGREGATE STATISTICS")
    print("-" * 100)
    total_runtime = sum(r.runtime_seconds for r in results)
    total_requests = sum(r.requests_made for r in results)
    total_candidates = sum(r.candidates_found for r in results)
    total_timeouts = sum(r.timeout_count for r in results)
    total_blocked = sum(r.blocked_403_count for r in results)
    total_5xx = sum(r.transient_5xx_count for r in results)
    early_stops = sum(1 for r in results if r.early_stop_reason)
    errors = sum(1 for r in results if r.error)
    null_results = sum(1 for r in results if r.status == "rejected" and not r.best_candidate_url)

    print(f"Total Runtime:         {total_runtime:.2f}s")
    print(f"Total Requests:        {total_requests}")
    print(f"Total Candidates:      {total_candidates}")
    print(f"Total Timeouts:        {total_timeouts}")
    print(f"Total Blocked (403):   {total_blocked}")
    print(f"Total Transient 5xx:   {total_5xx}")
    print(f"Early Stops:           {early_stops}")
    print(f"Errors:                {errors}")
    print(f"NULL/Rejected:         {null_results}")

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status or "unknown"] = status_counts.get(r.status or "unknown", 0) + 1
    print(f"Status Breakdown:      {status_counts}")

    kind_counts: dict[str, int] = {}
    for r in results:
        if r.image_kind:
            kind_counts[r.image_kind] = kind_counts.get(r.image_kind, 0) + 1
    print(f"Image Kind Breakdown:  {kind_counts}")

    human_review_count = sum(1 for r in results if r.status == "human_review")
    high_confidence_count = sum(1 for r in results if r.confidence == "HIGH")
    temp_unavail_count = sum(1 for r in results if r.is_temporarily_unavailable)
    genuine_missing_count = sum(1 for r in results if r.is_genuinely_missing)
    print(f"HUMAN_REVIEW count:    {human_review_count}")
    print(f"HIGH-confidence count: {high_confidence_count}")
    print(f"Temp Unavailable:      {temp_unavail_count}")
    print(f"Genuinely Missing:     {genuine_missing_count}")

    blockers = []
    for r in results:
        if r.status == "rejected" and not r.is_temporarily_unavailable and not r.is_genuinely_missing:
            blockers.append(f"ID {r.scholarship_id}: {'; '.join(r.rejection_reasons[:2]) or 'no_candidate'}")
    if blockers:
        print(f"Remaining Blockers ({len(blockers)}):")
        for b in blockers:
            print(f"  - {b}")
    print("=" * 100)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    logger.info("Starting optimized dry-run for IDs: %s", TARGET_IDS)

    results = run_optimized_dry_run(TARGET_IDS, max_concurrency=MAX_CONCURRENCY)
    print_report(results)

    output_path = "optimized_dry_run_results.json"
    data = []
    for r in results:
        d = {
            "scholarship_id": r.scholarship_id,
            "title": r.title,
            "official_source_url": r.official_source_url,
            "classification": r.classification,
            "candidates_found": r.candidates_found,
            "requests_made": r.requests_made,
            "timeout_count": r.timeout_count,
            "blocked_403_count": r.blocked_403_count,
            "transient_5xx_count": r.transient_5xx_count,
            "runtime_seconds": r.runtime_seconds,
            "tiers_exhausted": r.tiers_exhausted,
            "best_candidate_url": r.best_candidate_url,
            "best_candidate_page_url": r.best_candidate_page_url,
            "best_candidate_method": r.best_candidate_method,
            "confidence": r.confidence,
            "image_kind": r.image_kind,
            "status": r.status,
            "rejection_reasons": r.rejection_reasons,
            "human_review_reason": r.human_review_reason,
            "early_stop_reason": r.early_stop_reason,
            "error": r.error,
            "all_candidates": r.all_candidates,
            "network_retry_result": r.network_retry_result,
            "is_temporarily_unavailable": r.is_temporarily_unavailable,
            "is_genuinely_missing": r.is_genuinely_missing,
            "retry_count": r.retry_count,
            "last_attempt_at": r.last_attempt_at,
            "next_retry_at": r.next_retry_at,
            "failure_reason": r.failure_reason,
        }
        data.append(d)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info("Results saved to %s", output_path)
    return results


if __name__ == "__main__":
    main()
