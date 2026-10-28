"""Web search-based image discovery for scholarships.

Uses DuckDuckGo HTML search to find official images for scholarships.
Then validates candidates through the existing ImageValidator pipeline.

Zero database writes.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import get_engine
from app.models import Scholarship
from app.services.image_discovery import ImageCandidate
from app.services.image_validator import (
    ImageValidator,
    ValidationStatus,
    determine_image_source_type,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPORT_DIR = BACKEND_DIR / "reports"
DEFAULT_DB_PATH = BACKEND_DIR / "scholarzone.db"

MAX_CONCURRENCY = 8
DEFAULT_TIMEOUT = 15.0

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
DDG_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


@dataclass
class WebSearchResult:
    scholarship_id: int
    scholarship_title: str
    country: str
    degree: str
    status: str
    source_type: str | None
    official_source_url: str | None
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
    web_search_query: str | None = None
    web_pages_fetched: int = 0


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
        domain = urlparse(image_url).netloc.lower()
    elif source_url:
        domain = urlparse(source_url).netloc.lower()
    if not domain:
        return None
    result = determine_image_source_type(domain)
    return result.value if result else None


def _web_search_images(query: str, max_results: int = 5) -> list[str]:
    """Search DuckDuckGo HTML for URLs related to the query.
    Returns list of page URLs.
    """
    results = []
    try:
        session = requests.Session()
        session.headers.update(DDG_HEADERS)
        
        params = {"q": query, "b": "", "kl": "us-en"}
        response = session.get(DDG_SEARCH_URL, params=params, timeout=15)
        if response.status_code != 200:
            return results
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        for result in soup.select(".result__a")[:max_results]:
            href = result.get("href", "")
            if href:
                if "uddg=" in href:
                    from urllib.parse import unquote, urlparse, parse_qs
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    if "uddg" in qs:
                        actual_url = unquote(qs["uddg"][0])
                        results.append(actual_url)
                elif href.startswith("http"):
                    results.append(href)
    except Exception as exc:
        logger.debug("Web search failed for query '%s': %s", query, exc)
    
    return results


def _fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int | None, str | None, str | None]:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=timeout,
        )
        if response.status_code == 200:
            ct = response.headers.get("content-type", "")
            if "text/html" in ct or "application/xhtml" in ct:
                return 200, response.text, None
            return 200, None, f"Non-HTML content-type: {ct}"
        return response.status_code, None, f"HTTP {response.status_code}"
    except Exception as exc:
        return None, None, str(exc)


def _extract_images_from_html(content: str, page_url: str) -> list[ImageCandidate]:
    candidates = []
    if not content:
        return candidates
    
    soup = BeautifulSoup(content, "html.parser")
    
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        img_url = urljoin(page_url, og_image["content"].strip())
        candidates.append(ImageCandidate(
            image_url=img_url, page_url=page_url, discovery_method="og:image"
        ))
    
    twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter_image and twitter_image.get("content"):
        img_url = urljoin(page_url, twitter_image["content"].strip())
        candidates.append(ImageCandidate(
            image_url=img_url, page_url=page_url, discovery_method="twitter:image"
        ))
    
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src or src.startswith("data:"):
            continue
        img_url = urljoin(page_url, src.strip())
        alt = img.get("alt")
        width = img.get("width")
        height = img.get("height")
        candidates.append(ImageCandidate(
            image_url=img_url, page_url=page_url, discovery_method="html-img",
            alt_text=alt, width=_to_int(width), height=_to_int(height),
        ))
    
    return candidates


def _to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _process_single_web_search(ctx: ScholarshipContext, timeout: float) -> WebSearchResult:
    official_source_url = (ctx.official_source_url or "").strip()
    all_candidates: list[ImageCandidate] = []
    web_search_query = None
    web_pages_fetched = 0
    
    # Build search query
    domain_hint = ""
    if official_source_url:
        parsed = urlparse(official_source_url)
        domain_hint = f" site:{parsed.netloc}"
    
    title_terms = " ".join([w for w in ctx.title.split() if len(w) > 3][:5])
    query = f"{title_terms} scholarship{domain_hint}"
    web_search_query = query
    
    # Search for pages
    web_urls = _web_search_images(query, max_results=5)
    
    # Fetch pages and extract images
    for page_url in web_urls[:3]:
        status, content, error = _fetch_page(page_url, timeout)
        if content:
            page_candidates = _extract_images_from_html(content, page_url)
            all_candidates.extend(page_candidates)
            web_pages_fetched += 1
    
    # Deduplicate
    seen_urls = set()
    unique_candidates = []
    for c in all_candidates:
        if c.image_url not in seen_urls:
            seen_urls.add(c.image_url)
            unique_candidates.append(c)
    all_candidates = unique_candidates[:30]
    
    # Validate
    best_candidate = None
    source_type = None
    program_relevance = "none"
    licensing_status = "licensing_unknown"
    licensing_evidence = None
    confidence = "LOW"
    decision = "rejected"
    rejection_reasons = []
    hr_reason = None
    
    if all_candidates:
        try:
            validator = ImageValidator(seen_images={}, timeout=timeout)
            results = validator.validate_candidates(
                all_candidates,
                scholarship_title=ctx.title,
                official_source_url=official_source_url,
            )
            best_candidate = validator.find_best_result(results)
            
            if best_candidate:
                source_type = _classify_source_type(
                    best_candidate.candidate.image_url,
                    official_source_url,
                )
                program_relevance = _relevance_label(best_candidate)
                licensing_status = best_candidate.licensing_status
                licensing_evidence = best_candidate.licensing_evidence
                confidence = best_candidate.confidence
                decision = best_candidate.status.value
                rejection_reasons = best_candidate.rejection_reasons
                hr_reason = best_candidate.human_review_reason
        except Exception as exc:
            logger.warning("Scholarship %d: validation failed: %s", ctx.id, exc)
    
    if not all_candidates:
        rejection_reasons = ["No valid image candidate found"]
    
    if ctx.id % 50 == 0:
        logger.info("Web search %d [%s]: decision=%s confidence=%s candidates=%d",
                    ctx.id, ctx.title[:40], decision, confidence, len(all_candidates))
    
    return WebSearchResult(
        scholarship_id=ctx.id,
        scholarship_title=ctx.title,
        country=ctx.country,
        degree=ctx.degree,
        status=ctx.status,
        source_type=source_type,
        official_source_url=official_source_url or None,
        candidates_found=len(all_candidates),
        best_candidate_url=best_candidate.candidate.image_url if best_candidate else None,
        best_candidate_reachable=best_candidate.is_reachable if best_candidate else False,
        best_candidate_http_status=best_candidate.http_status if best_candidate else None,
        best_candidate_content_type=best_candidate.content_type if best_candidate else None,
        program_relevance=program_relevance,
        licensing_status=licensing_status,
        licensing_evidence=licensing_evidence,
        confidence=confidence,
        decision=decision,
        rejection_reasons=rejection_reasons,
        human_review_reason=hr_reason,
        non_content_signals=[s.label for s in best_candidate.non_content_signals] if best_candidate else [],
        web_search_query=web_search_query,
        web_pages_fetched=web_pages_fetched,
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


def run_web_search(
    max_concurrency: int = MAX_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    scholarship_ids: list[int] | None = None,
) -> list[WebSearchResult]:
    Session = _connect_production_db()
    all_contexts = _load_all_scholarships(Session)
    logger.info("Loaded %d scholarships for web search", len(all_contexts))
    
    if scholarship_ids:
        contexts = [c for c in all_contexts if c.id in scholarship_ids]
        logger.info("Filtered to %d specified scholarships", len(contexts))
    else:
        contexts = all_contexts
    
    results: list[WebSearchResult] = []

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        future_to_ctx = {}
        for ctx in contexts:
            future = executor.submit(_process_single_web_search, ctx, timeout)
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
                results.append(WebSearchResult(
                    scholarship_id=ctx.id,
                    scholarship_title=ctx.title,
                    country=ctx.country,
                    degree=ctx.degree,
                    status=ctx.status,
                    source_type=None,
                    official_source_url=ctx.official_source_url,
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
                    web_search_query=None,
                    web_pages_fetched=0,
                ))
            if completed % 50 == 0 or completed == len(contexts):
                logger.info("Progress: %d/%d completed", completed, len(contexts))

    results.sort(key=lambda r: r.scholarship_id)
    return results


def _write_report(results: list[WebSearchResult], label: str = "") -> tuple[Path, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    suffix = f"_{label}" if label else ""
    json_path = REPORT_DIR / f"web_search_dry_run{suffix}_{ts}.json"
    csv_path = REPORT_DIR / f"web_search_dry_run{suffix}_{ts}.csv"

    data = []
    for r in results:
        d = asdict(r)
        d["timestamp"] = datetime.now(timezone.utc).isoformat()
        data.append(d)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    fieldnames = [
        "scholarship_id", "scholarship_title", "country", "degree", "status",
        "source_type", "official_source_url", "candidates_found",
        "best_candidate_url", "best_candidate_reachable",
        "best_candidate_http_status", "best_candidate_content_type",
        "program_relevance", "licensing_status", "licensing_evidence",
        "confidence", "decision", "rejection_reasons",
        "human_review_reason", "non_content_signals", "error",
        "web_search_query", "web_pages_fetched",
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


def _print_summary(results: list[WebSearchResult]) -> None:
    total = len(results)
    approved = sum(1 for r in results if r.decision == "approved")
    human_review = sum(1 for r in results if r.decision == "human_review")
    rejected = sum(1 for r in results if r.decision == "rejected")
    errors = sum(1 for r in results if r.error is not None)
    
    pages_fetched = sum(r.web_pages_fetched for r in results)

    source_type_counts: Counter = Counter()
    for r in results:
        if r.source_type:
            source_type_counts[r.source_type] += 1

    with_image = sum(1 for r in results if r.best_candidate_url)
    reachable = sum(1 for r in results if r.best_candidate_reachable)

    print("\n" + "=" * 80)
    print("WEB SEARCH IMAGE DRY-RUN SUMMARY")
    print("=" * 80)
    print(f"Total scholarships processed : {total}")
    print(f"APPROVED                     : {approved} ({approved/total*100:.1f}%)")
    print(f"HUMAN_REVIEW                 : {human_review} ({human_review/total*100:.1f}%)")
    print(f"REJECTED                     : {rejected} ({rejected/total*100:.1f}%)")
    print(f"Pipeline errors              : {errors}")
    print(f"With discovered image        : {with_image} ({with_image/total*100:.1f}%)")
    print(f"Reachable images             : {reachable} ({reachable/total*100:.1f}%)")
    print(f"Web pages fetched            : {pages_fetched}")
    print()
    print("Source type distribution (best candidate domain):")
    for st, count in sorted(source_type_counts.items()):
        print(f"  {st:35s} : {count}")
    print()
    print("Decision distribution:")
    dec_counts: Counter = Counter(r.decision for r in results)
    for dec, count in sorted(dec_counts.items()):
        print(f"  {dec:35s} : {count}")
    print("=" * 80)


def main() -> None:
    import argparse

    global REPORT_DIR
    parser = argparse.ArgumentParser(description="Web search image dry-run for all scholarships")
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY,
                        help="Max parallel workers")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="HTTP request timeout in seconds")
    parser.add_argument("--output-dir", type=str, default="reports",
                        help="Output directory for reports")
    parser.add_argument("--ids", type=int, nargs="*", default=None,
                        help="Specific scholarship IDs to process")
    args = parser.parse_args()

    REPORT_DIR = Path(args.output_dir)
    REPORT_DIR.mkdir(exist_ok=True)

    logger.info("Starting web search dry-run (concurrency=%d, timeout=%.1fs)",
                args.concurrency, args.timeout)
    results = run_web_search(
        max_concurrency=args.concurrency,
        timeout=args.timeout,
        scholarship_ids=args.ids,
    )
    json_path, csv_path = _write_report(results)
    _print_summary(results)

    approved = [r for r in results if r.decision == "approved"]
    human_review = [r for r in results if r.decision == "human_review"]

    if approved:
        print("\nAPPROVED scholarships:")
        for r in approved:
            print(f"  ID {r.scholarship_id}: {r.scholarship_title[:50]} | {r.source_type} | {r.best_candidate_url}")

    if human_review:
        print("\nHUMAN_REVIEW scholarships:")
        for r in human_review:
            print(f"  ID {r.scholarship_id}: {r.scholarship_title[:50]} | {r.human_review_reason}")

    print(f"\nReports saved to: {json_path.parent}")
    print("NO DATABASE WRITES WERE MADE.")


if __name__ == "__main__":
    main()
