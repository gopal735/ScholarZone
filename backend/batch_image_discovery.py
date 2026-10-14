"""Batch image discovery for all scholarships without images.

Processes scholarships incrementally through:
1. Source resolution (using existing SourceResolverService)
2. Image discovery (using existing ImageDiscoveryService)  
3. Image validation (using existing ImageValidator)

Results are saved incrementally to a JSON file for recovery.
Manual web research is attempted for scholarships where automated discovery fails.

Does NOT write to the database.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend')

from app.database import get_engine, init_database
from app.models import Scholarship
from app.services.image_discovery import ImageDiscoveryService
from app.services.image_validator import ImageValidator, ValidationStatus, determine_image_source_type
from app.services.scholarship_image_verifier import ImageSourceType, is_official_domain, extract_domain
from app.services.source_resolver import SourceResolverService

OUTPUT_FILE = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_results.json')
PROGRESS_FILE = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_progress.json')
BATCH_SIZE = 20
MAX_WORKERS = 4

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_progress() -> set:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def save_progress(processed_ids: set):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(processed_ids), f)


def load_results() -> list:
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_results(results: list):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str, ensure_ascii=False)


def process_scholarship(scholarship_id: int, timeout: float = 30.0) -> dict:
    """Process a single scholarship through the discovery pipeline."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        scholarship = session.get(Scholarship, scholarship_id)
        if not scholarship:
            return {
                "scholarship_id": scholarship_id,
                "error": "Not found",
                "decision": "rejected",
                "confidence": "LOW"
            }
        
        official_source_url = scholarship.official_source_url or ""
        source_domain = extract_domain(official_source_url)
        source_type = determine_image_source_type(source_domain)
        
        logger.info(f"Processing ID {scholarship_id}: {scholarship.title[:50]}...")
        
        # Step 1: Resolve source
        resolver = SourceResolverService(timeout=timeout)
        resolved = resolver.resolve_source(official_source_url, scholarship.title)
        
        candidates = []
        results = []
        best_candidate = None
        
        # Step 2: Discover images
        if resolved.resolved_url:
            discovery = ImageDiscoveryService(timeout=timeout, max_candidates=50)
            candidates = discovery.discover_from_scholarship(resolved.resolved_url)
            
            # Step 3: Validate candidates
            validator = ImageValidator(seen_images={}, timeout=timeout)
            results = validator.validate_candidates(
                candidates,
                scholarship_title=scholarship.title,
                official_source_url=resolved.resolved_url,
            )
            best_candidate = validator.find_best_result(results)
        
        # Build result
        all_candidates = []
        for r in results:
            all_candidates.append({
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
                "aspect_ratio": r.aspect_ratio,
                "is_duplicate": r.is_duplicate,
                "relevance_score": r.relevance_score,
                "confidence": r.confidence,
                "status": r.status.value,
                "rejection_reasons": r.rejection_reasons,
                "human_review_reason": r.human_review_reason,
                "licensing_status": r.licensing_status,
                "non_content_total_weight": r.non_content_total_weight,
            })
        
        decision = best_candidate.status.value if best_candidate else "rejected"
        confidence = best_candidate.confidence if best_candidate else "LOW"
        
        return {
            "scholarship_id": scholarship_id,
            "scholarship_title": scholarship.title,
            "country": scholarship.country,
            "degree": scholarship.degree,
            "funding": scholarship.funding,
            "official_source": scholarship.official_source,
            "official_source_url": official_source_url,
            "source_type": source_type.value if source_type else None,
            "source_resolution_type": resolved.resolution_type.value,
            "resolved_source_url": resolved.resolved_url,
            "source_resolution_confidence": resolved.confidence,
            "candidates_found": len(candidates),
            "best_candidate_url": best_candidate.candidate.image_url if best_candidate else None,
            "best_candidate_page": best_candidate.candidate.page_url if best_candidate else None,
            "best_candidate_reachable": best_candidate.is_reachable if best_candidate else False,
            "best_candidate_http_status": best_candidate.http_status if best_candidate else None,
            "best_candidate_content_type": best_candidate.content_type if best_candidate else None,
            "best_candidate_dimensions": {
                "width": best_candidate.width if best_candidate else None,
                "height": best_candidate.height if best_candidate else None,
            },
            "program_relevance": _relevance_label(best_candidate) if best_candidate else "none",
            "licensing_status": best_candidate.licensing_status if best_candidate else "licensing_unknown",
            "licensing_evidence": best_candidate.licensing_evidence if best_candidate else None,
            "confidence": confidence,
            "decision": decision,
            "rejection_reasons": best_candidate.rejection_reasons if best_candidate else ["No candidates found"],
            "human_review_reason": best_candidate.human_review_reason if best_candidate else None,
            "all_candidates": all_candidates,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error(f"Error processing ID {scholarship_id}: {exc}")
        return {
            "scholarship_id": scholarship_id,
            "error": str(exc),
            "decision": "rejected",
            "confidence": "LOW",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        session.close()


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


def run_batch(scholarship_ids: list[int], start_index: int = 0):
    """Process a batch of scholarships and save results."""
    processed = load_progress()
    results = load_results()
    
    # Filter out already processed
    to_process = [sid for sid in scholarship_ids if sid not in processed]
    
    if not to_process:
        logger.info("All scholarships already processed!")
        return results
    
    logger.info(f"Processing {len(to_process)} scholarships (batch starting at {start_index})...")
    logger.info(f"Already processed: {len(processed)}")
    
    batch = to_process[:BATCH_SIZE]
    
    for i, sid in enumerate(batch):
        logger.info(f"--- Processing {i+1}/{len(batch)} (ID {sid}) ---")
        result = process_scholarship(sid)
        results.append(result)
        processed.add(sid)
        
        # Save incrementally
        save_results(results)
        save_progress(processed)
        
        # Log summary
        decision = result.get('decision', 'unknown')
        confidence = result.get('confidence', 'unknown')
        best_url = result.get('best_candidate_url')
        logger.info(f"  -> {decision.upper()} ({confidence}): {best_url[:60] if best_url else 'None'}")
        
        time.sleep(0.5)  # Rate limiting
    
    logger.info(f"Batch complete. Total processed: {len(processed)}/{len(scholarship_ids)}")
    return results


def run_all():
    """Run discovery on all scholarships without images."""
    init_database()
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        result = session.execute(
            select(Scholarship.id).where(Scholarship.image_url.is_(None)).order_by(Scholarship.id)
        )
        scholarship_ids = [row[0] for row in result.fetchall()]
    finally:
        session.close()
    
    logger.info(f"Found {len(scholarship_ids)} scholarships without images")
    
    # Process in batches
    for i in range(0, len(scholarship_ids), BATCH_SIZE):
        batch_ids = scholarship_ids[i:i + BATCH_SIZE]
        run_batch(batch_ids, start_index=i)
        
        if i + BATCH_SIZE < len(scholarship_ids):
            logger.info(f"Pausing before next batch...")
            time.sleep(2)
    
    return load_results()


def generate_dry_run_report(results: list) -> str:
    """Generate dry-run statistics report."""
    total = len(results)
    approved = sum(1 for r in results if r.get('decision') == 'approved')
    review = sum(1 for r in results if r.get('decision') == 'human_review')
    rejected = sum(1 for r in results if r.get('decision') == 'rejected')
    no_candidates = sum(1 for r in results if r.get('candidates_found', 0) == 0)
    
    # Source type breakdown
    uni = sum(1 for r in results if r.get('source_type') == 'official_university')
    gov = sum(1 for r in results if r.get('source_type') == 'official_government')
    provider = sum(1 for r in results if r.get('source_type') == 'official_provider')
    scholarship = sum(1 for r in results if r.get('source_type') == 'official_scholarship')
    
    # Top domains
    domains = {}
    for r in results:
        url = r.get('best_candidate_url')
        if url:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            domains[domain] = domains.get(domain, 0) + 1
    top_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Duplicates
    urls = [r.get('best_candidate_url') for r in results if r.get('best_candidate_url')]
    seen = set()
    duplicates = []
    for url in urls:
        if url in seen:
            duplicates.append(url)
        seen.add(url)
    
    report = f"""
DRY-RUN REPORT
==============
Total scholarships: {total}
  University scholarships: {uni}
  Government scholarships: {gov}
  Provider scholarships: {provider}
  Official scholarship programs: {scholarship}

Images found: {sum(1 for r in results if r.get('best_candidate_url'))}
  HIGH confidence (APPROVED): {approved}
  MEDIUM confidence (HUMAN_REVIEW): {review}
  LOW confidence (REJECTED): {rejected}
  No candidates found: {no_candidates}

Top source domains:
"""
    for domain, count in top_domains:
        report += f"  {domain}: {count}\n"
    
    report += f"""
Duplicate images: {len(duplicates)}
"""
    
    return report


if __name__ == "__main__":
    logger.info("Starting batch image discovery...")
    results = run_all()
    report = generate_dry_run_report(results)
    logger.info(report)
    
    # Save final report
    report_file = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_report.txt')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"Report saved to {report_file}")
