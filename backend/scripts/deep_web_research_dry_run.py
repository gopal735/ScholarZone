"""Fast deep research image discovery for all 303 scholarships.

Optimized pipeline:
1. Original source resolution + image discovery
2. Common paths only for 0-candidate scholarships
3. Text-based search on already-fetched pages

Zero database writes.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import get_engine
from app.models import Scholarship
from app.services.image_discovery import ImageCandidate, ImageDiscoveryService
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
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPORT_DIR = BACKEND_DIR / "reports"
DEFAULT_DB_PATH = BACKEND_DIR / "scholarzone.db"

MAX_CONCURRENCY = 12
DEFAULT_TIMEOUT = 15.0
MAX_RETRIES = 1
INITIAL_BACKOFF = 0.5

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Reduced common paths for speed
COMMON_MEDIA_PATHS = [
    "/news", "/press", "/media", "/photos", "/gallery",
]

SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
]


@dataclass
class DeepResearchResult:
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
    discovery_strategies: list[str] = field(default_factory=list)
    sitemap_discovered: bool = False
    additional_pages_crawled: int = 0


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


def _retry_with_backoff(func, *args, max_retries: int = MAX_RETRIES,
                         timeout: float = DEFAULT_TIMEOUT, **kwargs):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            return result
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                time.sleep(backoff)
    raise last_exc


def _fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[int | None, str | None, str | None]:
    """Fetch a page, returning (status, content, error)."""
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=timeout,
            follow_redirects=True,
        )
        if response.status_code == 200:
            ct = response.headers.get("content-type", "")
            if "text/html" in ct or "application/xhtml" in ct:
                return 200, response.text, None
            return 200, None, f"Non-HTML content-type: {ct}"
        return response.status_code, None, f"HTTP {response.status_code}"
    except Exception as exc:
        return None, None, str(exc)


def _try_sitemap_discovery(base_url: str, timeout: float = DEFAULT_TIMEOUT) -> list[str]:
    """Try to discover URLs from sitemaps."""
    discovered = []
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    base_scheme = parsed_base.scheme or "https"
    
    for sitemap_path in SITEMAP_PATHS:
        sitemap_url = f"{base_scheme}://{base_domain}{sitemap_path}"
        status, content, error = _fetch_page(sitemap_url, timeout)
        if content:
            try:
                soup = BeautifulSoup(content, "xml")
                urls = []
                for loc in soup.find_all("loc"):
                    if loc.text:
                        urls.append(loc.text.strip())
                discovered.extend(urls[:10])
                if discovered:
                    break
            except Exception:
                continue
    
    same_domain = []
    for url in discovered:
        parsed = urlparse(url)
        if parsed.netloc == base_domain:
            same_domain.append(url)
    
    return same_domain[:8]


def _try_common_paths(base_url: str, timeout: float = DEFAULT_TIMEOUT) -> list[str]:
    """Try common media/news/press paths on the official domain."""
    discovered = []
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    base_scheme = parsed_base.scheme or "https"
    
    for path in COMMON_MEDIA_PATHS:
        test_url = f"{base_scheme}://{base_domain}{path}"
        status, content, error = _fetch_page(test_url, timeout)
        if content and status == 200:
            discovered.append(test_url)
            if len(discovered) >= 4:
                break
    
    return discovered


def _search_page_for_scholarship(page_content: str, scholarship_title: str, base_url: str) -> list[str]:
    """Search page text for scholarship name and extract nearby image URLs."""
    images = []
    if not page_content or not scholarship_title:
        return images
    
    soup = BeautifulSoup(page_content, "html.parser")
    title_words = [w.lower() for w in scholarship_title.split() if len(w) > 3]
    
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    
    page_text = soup.get_text(separator=" ", strip=True).lower()
    match_count = sum(1 for w in title_words if w in page_text)
    if match_count < 2:
        return images
    
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src or src.startswith("data:"):
            continue
        full_url = urljoin(base_url, src.strip())
        parsed = urlparse(full_url)
        if parsed.scheme.startswith("http"):
            images.append(full_url)
    
    for tag in soup.find_all(style=True):
        style = tag.get("style", "")
        urls = re.findall(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
        for u in urls:
            if not u.startswith("data:"):
                full_url = urljoin(base_url, u.strip())
                parsed = urlparse(full_url)
                if parsed.scheme.startswith("http"):
                    images.append(full_url)
    
    return list(set(images))


def _extract_images_from_html(content: str, page_url: str) -> list[ImageCandidate]:
    """Extract image candidates from HTML content."""
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
    
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    for key in ("image", "photo"):
                        val = item.get(key)
                        if isinstance(val, str) and val:
                            img_url = urljoin(page_url, val.strip())
                            candidates.append(ImageCandidate(
                                image_url=img_url, page_url=page_url, discovery_method="json-ld"
                            ))
                        elif isinstance(val, list):
                            for sub in val:
                                if isinstance(sub, str) and sub:
                                    img_url = urljoin(page_url, sub.strip())
                                    candidates.append(ImageCandidate(
                                        image_url=img_url, page_url=page_url, discovery_method="json-ld"
                                    ))
        except Exception:
            continue
    
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


def _process_single_deep_research(ctx: ScholarshipContext, timeout: float) -> DeepResearchResult:
    """Process a single scholarship with deep research strategies."""
    official_source_url = (ctx.official_source_url or "").strip()
    strategies_used = []
    sitemap_discovered = False
    additional_pages = 0
    all_candidates: list[ImageCandidate] = []
    
    try:
        resolver = SourceResolverService(timeout=timeout)
        resolved: ResolvedSource = _retry_with_backoff(
            resolver.resolve_source, official_source_url, ctx.title
        )
        strategies_used.append("source_resolution")
        
        if resolved.resolution_type == SourceResolutionType.INACCESSIBLE:
            if official_source_url:
                status, content, error = _fetch_page(official_source_url, timeout)
                if content:
                    resolved = ResolvedSource(
                        original_url=official_source_url,
                        resolved_url=official_source_url,
                        resolution_type=SourceResolutionType.EXACT_PROGRAM_PAGE,
                        confidence=0.8,
                        reason="Direct fetch succeeded after resolver failed",
                    )
                    strategies_used.append("direct_fetch_retry")
        
    except Exception as exc:
        resolved = ResolvedSource(
            original_url=official_source_url,
            resolved_url=None,
            resolution_type=SourceResolutionType.INACCESSIBLE,
            confidence=0.0,
            reason=f"Source resolution failed: {exc}",
        )
    
    # Strategy 1: Original image discovery
    original_candidates = []
    if resolved.resolved_url:
        try:
            discovery = ImageDiscoveryService(timeout=timeout, max_candidates=50)
            original_candidates = _retry_with_backoff(
                discovery.discover_from_scholarship,
                resolved.resolved_url,
            )
            all_candidates.extend(original_candidates)
            strategies_used.append("original_discovery")
        except Exception as exc:
            logger.debug("Scholarship %d: original discovery failed: %s", ctx.id, exc)
    
    # Strategy 2: Common paths (only if original found 0 candidates)
    if len(original_candidates) == 0 and (resolved.resolved_url or official_source_url):
        base_url = resolved.resolved_url or official_source_url
        if base_url:
            try:
                common_urls = _try_common_paths(base_url, timeout)
                if common_urls:
                    strategies_used.append("common_paths")
                    
                    for common_url in common_urls[:4]:
                        status, content, error = _fetch_page(common_url, timeout)
                        if content:
                            page_candidates = _extract_images_from_html(content, common_url)
                            all_candidates.extend(page_candidates)
                            additional_pages += 1
                            
                            name_images = _search_page_for_scholarship(content, ctx.title, common_url)
                            for img_url in name_images:
                                all_candidates.append(ImageCandidate(
                                    image_url=img_url, page_url=common_url, discovery_method="text-search"
                                ))
            except Exception as exc:
                logger.debug("Scholarship %d: common paths failed: %s", ctx.id, exc)
    
    # Strategy 3: Sitemap discovery (only if still 0 candidates)
    if len(all_candidates) == 0 and (resolved.resolved_url or official_source_url):
        base_url = resolved.resolved_url or official_source_url
        if base_url:
            try:
                sitemap_urls = _try_sitemap_discovery(base_url, timeout)
                if sitemap_urls:
                    sitemap_discovered = True
                    strategies_used.append("sitemap_discovery")
                    
                    for sitemap_url in sitemap_urls[:6]:
                        status, content, error = _fetch_page(sitemap_url, timeout)
                        if content:
                            page_candidates = _extract_images_from_html(content, sitemap_url)
                            all_candidates.extend(page_candidates)
                            additional_pages += 1
            except Exception as exc:
                logger.debug("Scholarship %d: sitemap discovery failed: %s", ctx.id, exc)
    
    # Deduplicate candidates
    seen_urls = set()
    unique_candidates = []
    for c in all_candidates:
        if c.image_url not in seen_urls:
            seen_urls.add(c.image_url)
            unique_candidates.append(c)
    all_candidates = unique_candidates[:50]
    
    # Validate candidates
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
                official_source_url=resolved.resolved_url or official_source_url,
            )
            best_candidate = validator.find_best_result(results)
            
            if best_candidate:
                source_type = _classify_source_type(
                    best_candidate.candidate.image_url,
                    resolved.resolved_url,
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
    
    if ctx.id % 25 == 0:
        logger.info("Scholarship %d [%s]: decision=%s confidence=%s candidates=%d strategies=%s",
                    ctx.id, ctx.title[:40], decision, confidence, len(all_candidates),
                    "+".join(strategies_used) if strategies_used else "none")
    
    return DeepResearchResult(
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
        discovery_strategies=strategies_used,
        sitemap_discovered=sitemap_discovered,
        additional_pages_crawled=additional_pages,
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


def run_deep_research(
    max_concurrency: int = MAX_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
    scholarship_ids: list[int] | None = None,
) -> list[DeepResearchResult]:
    Session = _connect_production_db()
    all_contexts = _load_all_scholarships(Session)
    logger.info("Loaded %d scholarships for deep research", len(all_contexts))
    
    if scholarship_ids:
        contexts = [c for c in all_contexts if c.id in scholarship_ids]
        logger.info("Filtered to %d specified scholarships", len(contexts))
    else:
        contexts = all_contexts
    
    results: list[DeepResearchResult] = []

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        future_to_ctx = {}
        for ctx in contexts:
            future = executor.submit(_process_single_deep_research, ctx, timeout)
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
                results.append(DeepResearchResult(
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


def _write_report(results: list[DeepResearchResult], label: str = "") -> tuple[Path, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    suffix = f"_{label}" if label else ""
    json_path = REPORT_DIR / f"deep_research_dry_run{suffix}_{ts}.json"
    csv_path = REPORT_DIR / f"deep_research_dry_run{suffix}_{ts}.csv"

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
        "discovery_strategies", "sitemap_discovered", "additional_pages_crawled",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row["rejection_reasons"] = "; ".join(row["rejection_reasons"] or [])
            row["non_content_signals"] = "; ".join(row["non_content_signals"] or [])
            row["discovery_strategies"] = "; ".join(row["discovery_strategies"] or [])
            writer.writerow(row)

    logger.info("JSON report: %s", json_path)
    logger.info("CSV report:  %s", csv_path)
    return json_path, csv_path


def _print_summary(results: list[DeepResearchResult]) -> None:
    total = len(results)
    approved = sum(1 for r in results if r.decision == "approved")
    human_review = sum(1 for r in results if r.decision == "human_review")
    rejected = sum(1 for r in results if r.decision == "rejected")
    errors = sum(1 for r in results if r.error is not None)
    
    sitemaps = sum(1 for r in results if r.sitemap_discovered)
    additional_crawled = sum(r.additional_pages_crawled for r in results)

    source_type_counts: Counter = Counter()
    for r in results:
        if r.source_type:
            source_type_counts[r.source_type] += 1

    with_image = sum(1 for r in results if r.best_candidate_url)
    reachable = sum(1 for r in results if r.best_candidate_reachable)

    print("\n" + "=" * 80)
    print("DEEP RESEARCH IMAGE DRY-RUN SUMMARY")
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
    print("Deep research metrics:")
    print(f"  Sitemaps discovered        : {sitemaps}")
    print(f"  Additional pages crawled   : {additional_crawled}")
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
    parser = argparse.ArgumentParser(description="Deep research image dry-run for all scholarships")
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

    logger.info("Starting deep research dry-run (concurrency=%d, timeout=%.1fs)",
                args.concurrency, args.timeout)
    results = run_deep_research(
        max_concurrency=args.concurrency,
        timeout=args.timeout,
        scholarship_ids=args.ids,
    )
    json_path, csv_path = _write_report(results)
    _print_summary(results)

    approved = [r for r in results if r.decision == "approved"]
    human_review = [r for r in results if r.decision == "human_review"]
    rejected = [r for r in results if r.decision == "rejected"]

    if approved:
        print("\nAPPROVED scholarships:")
        for r in approved:
            print(f"  ID {r.scholarship_id}: {r.scholarship_title[:50]} | {r.source_type} | {r.best_candidate_url}")
            print(f"    Strategies: {', '.join(r.discovery_strategies)}")

    if human_review:
        print("\nHUMAN_REVIEW scholarships:")
        for r in human_review:
            print(f"  ID {r.scholarship_id}: {r.scholarship_title[:50]} | {r.human_review_reason}")
            print(f"    Strategies: {', '.join(r.discovery_strategies)}")

    print(f"\nReports saved to: {json_path.parent}")
    print("NO DATABASE WRITES WERE MADE.")


if __name__ == "__main__":
    main()
