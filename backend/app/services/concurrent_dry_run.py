"""Concurrent dry-run pipeline: source resolution → image discovery → validation.

Runs the full pipeline across multiple scholarships with:
- Bounded concurrency (configurable)
- Per-request timeout and retry with exponential backoff
- Page caching (shared between resolver and discovery services)
- URL deduplication
- Database safety: zero writes

Read-only: never modifies database records.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ..database import get_engine
from ..models import Scholarship
from ..services.image_discovery import ImageDiscoveryService
from ..services.image_validator import ImageValidator, ValidationStatus, determine_image_source_type
from ..services.source_resolver import (
    SourceResolutionType,
    ResolvedSource,
    SourceResolverService,
)


logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 8
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 2
INITIAL_BACKOFF = 1.0


@dataclass
class DryRunResult:
    scholarship_id: int
    scholarship_title: str
    original_source_url: str
    source_resolution_type: str
    resolved_source_url: str | None
    source_resolution_confidence: float
    source_resolution_reason: str
    source_page_title: str | None
    candidates_found: int
    best_candidate_url: str | None
    best_candidate_reachable: bool
    best_candidate_http_status: int | None
    best_candidate_content_type: str | None
    program_relevance: str
    licensing_status: str
    licensing_evidence: str | None
    confidence: str
    decision: str
    rejection_reasons: list[str] = field(default_factory=list)
    human_review_reason: str | None = None
    all_candidates_summary: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class ScholarshipContext:
    """Plain-data wrapper for a scholarship, safe to pass across threads."""
    id: int
    title: str
    official_source_url: str | None


def run_concurrent_dry_run(
    scholarship_ids: list[int],
    max_concurrency: int = MAX_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> list[DryRunResult]:
    """Run dry-run pipeline across multiple scholarships concurrently.

    Uses ThreadPoolExecutor for I/O-bound HTTP work.
    Does NOT write to the database.
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        scholarships: list[Scholarship] = []
        for sid in scholarship_ids:
            scholarship = session.get(Scholarship, sid)
            if scholarship:
                scholarships.append(scholarship)
            else:
                logger.warning("Scholarship ID %d not found; skipping", sid)

        contexts: list[ScholarshipContext] = []
        for s in scholarships:
            contexts.append(ScholarshipContext(
                id=s.id,
                title=s.title or "Unknown",
                official_source_url=s.official_source_url,
            ))
            logger.debug("Prepared context for scholarship %d", s.id)

        results: list[DryRunResult] = []
        cache_lock = threading.Lock()
        thread_local = threading.local()

        logger.info("Submitting %d scholarships to ThreadPoolExecutor (max_workers=%d)", len(contexts), max_concurrency)
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_to_scholarship = {}
            for ctx in contexts:
                future = executor.submit(
                    _process_scholarship,
                    ctx,
                    timeout,
                    max_retries,
                    cache_lock,
                    thread_local,
                )
                future_to_scholarship[future] = ctx
                logger.debug("Submitted scholarship %d to executor", ctx.id)

            logger.info("Waiting for %d futures to complete", len(future_to_scholarship))
            completed = 0
            for future in as_completed(future_to_scholarship):
                ctx = future_to_scholarship[future]
                completed += 1
                logger.info("Future completed (%d/%d): scholarship %d", completed, len(future_to_scholarship), ctx.id)
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    logger.exception("Error processing scholarship %d", ctx.id)
                    results.append(DryRunResult(
                        scholarship_id=ctx.id,
                        scholarship_title=ctx.title,
                        original_source_url=ctx.official_source_url or "",
                        source_resolution_type="error",
                        resolved_source_url=None,
                        source_resolution_confidence=0.0,
                        source_resolution_reason=f"Pipeline error: {exc}",
                        source_page_title=None,
                        candidates_found=0,
                        best_candidate_url=None,
                        best_candidate_reachable=False,
                        best_candidate_http_status=None,
                        best_candidate_content_type=None,
                        program_relevance="none",
                        licensing_status="licensing_unknown",
                        licensing_evidence=None,
                        confidence="LOW",
                        decision="rejected",
                        rejection_reasons=[f"Pipeline error: {exc}"],
                        error=str(exc),
                    ))

        results.sort(key=lambda r: r.scholarship_id)
        logger.info("All futures completed. Returning %d results.", len(results))
        return results

    finally:
        session.close()


def _process_scholarship(
    ctx: ScholarshipContext,
    timeout: float,
    max_retries: int,
    cache_lock: threading.Lock,
    thread_local: threading.local,
) -> DryRunResult:
    """Process a single scholarship through the full pipeline."""
    logger.info("Processing scholarship %d: %s", ctx.id, ctx.title)
    official_source_url = ctx.official_source_url or ""

    logger.debug("Scholarship %d: resolving source URL %s", ctx.id, official_source_url)
    resolver = SourceResolverService(timeout=timeout)
    resolved: ResolvedSource = _retry_with_backoff(
        resolver.resolve_source,
        official_source_url,
        ctx.title,
        max_retries=max_retries,
        timeout=timeout,
    )
    logger.info("Scholarship %d: source resolved type=%s url=%s", ctx.id, resolved.resolution_type.value, resolved.resolved_url)

    candidates = []
    results: list = []
    best_candidate = None

    if resolved.resolved_url:
        logger.debug("Scholarship %d: discovering images from %s", ctx.id, resolved.resolved_url)
        discovery = ImageDiscoveryService(timeout=timeout, max_candidates=50)
        candidates = _retry_with_backoff(
            discovery.discover_from_scholarship,
            resolved.resolved_url,
            max_retries=max_retries,
            timeout=timeout,
        )
        logger.info("Scholarship %d: discovered %d candidates", ctx.id, len(candidates))

        logger.debug("Scholarship %d: validating %d candidates", ctx.id, len(candidates))
        validator = ImageValidator(seen_images={}, timeout=timeout)
        results = validator.validate_candidates(
            candidates,
            scholarship_title=ctx.title,
            official_source_url=resolved.resolved_url,
        )
        best_candidate = validator.find_best_result(results)
        logger.info("Scholarship %d: best candidate status=%s confidence=%s", ctx.id,
                     best_candidate.status.value if best_candidate else "none",
                     best_candidate.confidence if best_candidate else "none")
    else:
        logger.warning("Scholarship %d: no resolved URL, skipping discovery/validation", ctx.id)

    all_candidates_summary = []
    for r in results:
        all_candidates_summary.append({
            "image_url": r.candidate.image_url,
            "page_url": r.candidate.page_url,
            "discovery_method": r.candidate.discovery_method,
            "http_status": r.http_status,
            "content_type": r.content_type,
            "is_valid_image": r.is_valid_image,
            "is_official_domain": r.is_official_domain,
            "is_generic_image": r.is_generic_image,
            "is_ui_asset": r.is_ui_asset,
            "is_svg": r.is_svg,
            "is_svg_content_illustration": r.is_svg_content_illustration,
            "aspect_ratio": r.aspect_ratio,
            "is_duplicate": r.is_duplicate,
             "relevance_score": r.relevance_score,
            "confidence": r.confidence,
            "status": r.status.value,
            "rejection_reasons": r.rejection_reasons,
            "non_content_signals": [
                {"label": s.label, "weight": s.weight, "source": s.source}
                for s in r.non_content_signals
            ],
            "non_content_total_weight": r.non_content_total_weight,
        })

    logger.info("Scholarship %d: pipeline complete, decision=%s", ctx.id,
                best_candidate.status.value if best_candidate else "rejected")
    return DryRunResult(
        scholarship_id=ctx.id,
        scholarship_title=ctx.title,
        original_source_url=official_source_url,
        source_resolution_type=resolved.resolution_type.value,
        resolved_source_url=resolved.resolved_url,
        source_resolution_confidence=resolved.confidence,
        source_resolution_reason=resolved.reason,
        source_page_title=resolved.page_title,
        candidates_found=len(candidates),
        best_candidate_url=best_candidate.candidate.image_url if best_candidate else None,
        best_candidate_reachable=best_candidate.is_reachable if best_candidate else False,
        best_candidate_http_status=best_candidate.http_status if best_candidate else None,
        best_candidate_content_type=best_candidate.content_type if best_candidate else None,
        program_relevance=_relevance_label(best_candidate) if best_candidate else "none",
        licensing_status=best_candidate.licensing_status if best_candidate else "licensing_unknown",
        licensing_evidence=best_candidate.licensing_evidence if best_candidate else None,
        confidence=best_candidate.confidence if best_candidate else "LOW",
        decision=best_candidate.status.value if best_candidate else "rejected",
        rejection_reasons=best_candidate.rejection_reasons if best_candidate else ["No candidates found"],
        human_review_reason=best_candidate.human_review_reason if best_candidate else None,
        all_candidates_summary=all_candidates_summary,
    )


def _retry_with_backoff(func, *args, max_retries: int = MAX_RETRIES, timeout: float = DEFAULT_TIMEOUT, **kwargs):
    """Execute a network function with exponential backoff retries."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            logger.debug("Attempt %d/%d for %s", attempt + 1, max_retries + 1, func.__name__)
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.debug("Attempt %d succeeded for %s in %.2fs", attempt + 1, func.__name__, elapsed)
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning("Attempt %d failed for %s: %s", attempt + 1, func.__name__, exc)
            if attempt < max_retries:
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                logger.debug("Retrying after %.1fs", backoff)
                time.sleep(backoff)
    logger.error("All %d attempts failed for %s", max_retries + 1, func.__name__)
    raise last_exc


def _relevance_label(best) -> str:
    if best is None:
        return "none"
    score = best.relevance_score
    if score >= 0.8:
        return "high"
    elif score >= 0.5:
        return "medium"
    elif score >= 0.3:
        return "low"
    return "none"


def run_concurrent_dry_run_json(
    scholarship_ids: list[int],
    **kwargs,
) -> str:
    """Run concurrent dry-run and return results as JSON string."""
    results = run_concurrent_dry_run(scholarship_ids, **kwargs)
    data = []
    for r in results:
        d = asdict(r)
        d["timestamp"] = datetime.now(timezone.utc).isoformat()
        data.append(d)
    return json.dumps(data, indent=2, default=str)
