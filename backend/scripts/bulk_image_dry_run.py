"""Bulk image dry-run processor for all 303 existing scholarships.

Read-only pipeline: source resolution -> image discovery -> validation ->
source-type classification. Zero database writes.

Outputs a complete dry-run report (JSON + CSV) for all scholarships.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import get_engine
from app.models import Scholarship
from app.services.image_discovery import ImageDiscoveryService
from app.services.image_validator import (
    ImageValidator,
    ValidationStatus,
    determine_image_source_type,
)
from app.services.source_resolver import (
    ResolvedSource,
    SourceResolutionType,
    SourceResolverService,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPORT_DIR = BACKEND_DIR / "reports"
DEFAULT_DB_PATH = BACKEND_DIR / "scholarzone.db"

MAX_CONCURRENCY = 8
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 2
INITIAL_BACKOFF = 1.0


@dataclass
class BulkDryRunResult:
    scholarship_id: int
    scholarship_title: str
    country: str
    degree: str
    status: str
    source_type: str | None
    official_source_url: str | None
    resolved_source_url: str | None
    source_resolution_type: str
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
    non_content_signals: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ScholarshipContext:
    id: int
    title: str
    country: str
    degree: str
    status: str
    official_source_url: str | None


def _connect_production_db() -> sessionmaker:
    db_url = os.getenv("SCHOLARZONE_DATABASE_URL")
    if not db_url:
        db_url = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    engine = get_engine()
    return sessionmaker(bind=engine)


def _load_all_scholarships(Session) -> list[ScholarshipContext]:
    session = Session()
    try:
        rows = session.execute(
            select(
                Scholarship.id,
                Scholarship.title,
                Scholarship.country,
                Scholarship.degree,
                Scholarship.status,
                Scholarship.official_source_url,
            )
        ).all()
        return [
            ScholarshipContext(
                id=r.id,
                title=r.title or "Unknown",
                country=r.country or "Unknown",
                degree=r.degree or "Unknown",
                status=r.status or "open",
                official_source_url=r.official_source_url,
            )
            for r in rows
        ]
    finally:
        session.close()


def _classify_source_type(image_url: str | None, source_url: str | None) -> str | None:
    domain = None
    if image_url:
        from urllib.parse import urlparse
        domain = urlparse(image_url).netloc.lower()
    elif source_url:
        from urllib.parse import urlparse
        domain = urlparse(source_url).netloc.lower()
    if not domain:
        return None
    result = determine_image_source_type(domain)
    return result.value if result else None


def _retry_with_backoff(func, *args, max_retries: int = MAX_RETRIES,
                         timeout: float = DEFAULT_TIMEOUT, **kwargs):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
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
                time.sleep(backoff)
    raise last_exc


def _process_single(ctx: ScholarshipContext, timeout: float) -> BulkDryRunResult:
    official_source_url = (ctx.official_source_url or "").strip()

    try:
        resolver = SourceResolverService(timeout=timeout)
        resolved: ResolvedSource = _retry_with_backoff(
            resolver.resolve_source, official_source_url, ctx.title
        )
    except Exception as exc:
        return BulkDryRunResult(
            scholarship_id=ctx.id,
            scholarship_title=ctx.title,
            country=ctx.country,
            degree=ctx.degree,
            status=ctx.status,
            source_type=None,
            official_source_url=official_source_url or None,
            resolved_source_url=None,
            source_resolution_type="error",
            source_resolution_confidence=0.0,
            source_resolution_reason=f"Source resolution failed: {exc}",
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
            rejection_reasons=[f"Source resolution error: {exc}"],
            error=str(exc),
        )

    candidates = []
    results: list[Any] = []
    best_candidate = None
    source_type = None

    if resolved.resolved_url:
        try:
            discovery = ImageDiscoveryService(timeout=timeout, max_candidates=50)
            candidates = _retry_with_backoff(
                discovery.discover_from_scholarship,
                resolved.resolved_url,
            )
        except Exception as exc:
            logger.warning("Scholarship %d: discovery failed: %s", ctx.id, exc)

        if candidates:
            try:
                validator = ImageValidator(seen_images={}, timeout=timeout)
                results = validator.validate_candidates(
                    candidates,
                    scholarship_title=ctx.title,
                    official_source_url=resolved.resolved_url,
                )
                best_candidate = validator.find_best_result(results)
            except Exception as exc:
                logger.warning("Scholarship %d: validation failed: %s", ctx.id, exc)

    if best_candidate:
        source_type = _classify_source_type(
            best_candidate.candidate.image_url,
            resolved.resolved_url,
        )

    non_content_labels = []
    if best_candidate:
        non_content_labels = [s.label for s in best_candidate.non_content_signals]

    if best_candidate is None:
        decision = "rejected"
        confidence = "LOW"
        rejection_reasons = ["No valid image candidate found"] if not candidates else [
            r.rejection_reasons[0] if r.rejection_reasons else "Rejected"
            for r in results if r.status == ValidationStatus.REJECTED
        ]
        if not rejection_reasons:
            rejection_reasons = ["No candidates found"]
        program_relevance = "none"
        licensing_status = "licensing_unknown"
        licensing_evidence = None
        best_reachable = False
        best_http = None
        best_ct = None
        hr_reason = None
    else:
        decision = best_candidate.status.value
        confidence = best_candidate.confidence
        rejection_reasons = best_candidate.rejection_reasons
        hr_reason = best_candidate.human_review_reason
        program_relevance = _relevance_label(best_candidate)
        licensing_status = best_candidate.licensing_status
        licensing_evidence = best_candidate.licensing_evidence
        best_reachable = best_candidate.is_reachable
        best_http = best_candidate.http_status
        best_ct = best_candidate.content_type

    logger.info(
        "Scholarship %d [%s]: decision=%s confidence=%s source_type=%s candidates=%d",
        ctx.id, ctx.title[:40], decision, confidence, source_type, len(candidates),
    )

    return BulkDryRunResult(
        scholarship_id=ctx.id,
        scholarship_title=ctx.title,
        country=ctx.country,
        degree=ctx.degree,
        status=ctx.status,
        source_type=source_type,
        official_source_url=official_source_url or None,
        resolved_source_url=resolved.resolved_url,
        source_resolution_type=resolved.resolution_type.value,
        source_resolution_confidence=resolved.confidence,
        source_resolution_reason=resolved.reason,
        source_page_title=resolved.page_title,
        candidates_found=len(candidates),
        best_candidate_url=best_candidate.candidate.image_url if best_candidate else None,
        best_candidate_reachable=best_reachable,
        best_candidate_http_status=best_http,
        best_candidate_content_type=best_ct,
        program_relevance=program_relevance,
        licensing_status=licensing_status,
        licensing_evidence=licensing_evidence,
        confidence=confidence,
        decision=decision,
        rejection_reasons=rejection_reasons,
        human_review_reason=hr_reason,
        non_content_signals=non_content_labels,
        error=None,
    )


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


def run_bulk_dry_run(
    max_concurrency: int = MAX_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[BulkDryRunResult]:
    Session = _connect_production_db()
    contexts = _load_all_scholarships(Session)
    logger.info("Loaded %d scholarships for bulk dry-run", len(contexts))

    results: list[BulkDryRunResult] = []
    cache_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        future_to_ctx = {}
        for ctx in contexts:
            future = executor.submit(_process_single, ctx, timeout)
            future_to_ctx[future] = ctx

        completed = 0
        for future in as_completed(future_to_ctx):
            ctx = future_to_ctx[future]
            completed += 1
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                logger.exception("Error processing scholarship %d", ctx.id)
                results.append(BulkDryRunResult(
                    scholarship_id=ctx.id,
                    scholarship_title=ctx.title,
                    country=ctx.country,
                    degree=ctx.degree,
                    status=ctx.status,
                    source_type=None,
                    official_source_url=ctx.official_source_url,
                    resolved_source_url=None,
                    source_resolution_type="error",
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
            if completed % 50 == 0 or completed == len(contexts):
                logger.info("Progress: %d/%d completed", completed, len(contexts))

    results.sort(key=lambda r: r.scholarship_id)
    return results


def _write_report(results: list[BulkDryRunResult]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    json_path = REPORT_DIR / f"bulk_image_dry_run_{ts}.json"
    csv_path = REPORT_DIR / f"bulk_image_dry_run_{ts}.csv"

    data = []
    for r in results:
        d = asdict(r)
        d["timestamp"] = datetime.now(timezone.utc).isoformat()
        data.append(d)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    fieldnames = [
        "scholarship_id", "scholarship_title", "country", "degree", "status",
        "source_type", "official_source_url", "resolved_source_url",
        "source_resolution_type", "source_resolution_confidence",
        "candidates_found", "best_candidate_url",
        "best_candidate_reachable", "best_candidate_http_status",
        "best_candidate_content_type", "program_relevance",
        "licensing_status", "licensing_evidence",
        "confidence", "decision", "rejection_reasons",
        "human_review_reason", "non_content_signals", "error",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row["rejection_reasons"] = "; ".join(row["rejection_reasons"] or [])
            row["non_content_signals"] = "; ".join(row["non_content_signals"] or [])
            writer.writerow(row)

    logger.info("JSON report: %s", json_path)
    logger.info("CSV report:  %s", csv_path)
    return json_path, csv_path


def _print_summary(results: list[BulkDryRunResult]) -> None:
    total = len(results)
    approved = sum(1 for r in results if r.decision == "approved")
    human_review = sum(1 for r in results if r.decision == "human_review")
    rejected = sum(1 for r in results if r.decision == "rejected")
    errors = sum(1 for r in results if r.error is not None)

    source_type_counts: Counter = Counter()
    for r in results:
        if r.source_type:
            source_type_counts[r.source_type] += 1

    with_image = sum(1 for r in results if r.best_candidate_url)
    reachable = sum(1 for r in results if r.best_candidate_reachable)

    print("\n" + "=" * 80)
    print("BULK IMAGE DRY-RUN SUMMARY")
    print("=" * 80)
    print(f"Total scholarships processed : {total}")
    print(f"APPROVED                     : {approved} ({approved/total*100:.1f}%)")
    print(f"HUMAN_REVIEW                 : {human_review} ({human_review/total*100:.1f}%)")
    print(f"REJECTED                     : {rejected} ({rejected/total*100:.1f}%)")
    print(f"Pipeline errors              : {errors}")
    print(f"With discovered image        : {with_image} ({with_image/total*100:.1f}%)")
    print(f"Reachable images             : {reachable} ({reachable/total*100:.1f}%)")
    print()
    print("Source type distribution (best candidate domain):")
    for st, count in sorted(source_type_counts.items()):
        print(f"  {st:35s} : {count}")
    print()
    print("Resolution type distribution:")
    res_counts: Counter = Counter(r.source_resolution_type for r in results)
    for rt, count in sorted(res_counts.items()):
        print(f"  {rt:35s} : {count}")
    print()
    print("Licensing status distribution:")
    lic_counts: Counter = Counter(r.licensing_status for r in results)
    for ls, count in sorted(lic_counts.items()):
        print(f"  {ls:35s} : {count}")
    print("=" * 80)


def main() -> None:
    import argparse

    global REPORT_DIR
    parser = argparse.ArgumentParser(description="Bulk image dry-run for all scholarships")
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY,
                        help="Max parallel workers")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="HTTP request timeout in seconds")
    parser.add_argument("--output-dir", type=str, default="reports",
                        help="Output directory for reports")
    args = parser.parse_args()

    global REPORT_DIR
    REPORT_DIR = Path(args.output_dir)
    REPORT_DIR.mkdir(exist_ok=True)

    logger.info("Starting bulk image dry-run (concurrency=%d, timeout=%.1fs)",
                args.concurrency, args.timeout)
    results = run_bulk_dry_run(
        max_concurrency=args.concurrency,
        timeout=args.timeout,
    )
    json_path, csv_path = _write_report(results)
    _print_summary(results)

    approved = [r for r in results if r.decision == "approved"]
    human_review = [r for r in results if r.decision == "human_review"]
    rejected = [r for r in results if r.decision == "rejected"]

    if approved:
        print("\nAPPROVED scholarships (sample):")
        for r in approved[:10]:
            print(f"  ID {r.scholarship_id}: {r.scholarship_title[:50]} | {r.source_type} | {r.best_candidate_url}")
        if len(approved) > 10:
            print(f"  ... and {len(approved) - 10} more")

    if human_review:
        print("\nHUMAN_REVIEW scholarships (sample):")
        for r in human_review[:10]:
            print(f"  ID {r.scholarship_id}: {r.scholarship_title[:50]} | {r.source_type} | {r.human_review_reason}")
        if len(human_review) > 10:
            print(f"  ... and {len(human_review) - 10} more")

    print(f"\nReports saved to: {json_path.parent}")
    print("NO DATABASE WRITES WERE MADE.")


if __name__ == "__main__":
    main()
