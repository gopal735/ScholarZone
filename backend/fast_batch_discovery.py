"""High-concurrency batch image discovery for all scholarships.

Uses ThreadPoolExecutor to process multiple scholarships in parallel.
Saves results incrementally.
"""

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

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
MAX_WORKERS = 16
TIMEOUT = 30.0

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

progress_lock = Lock()
results_lock = Lock()


def load_progress() -> set:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def save_progress(processed_ids: set):
    with progress_lock:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(processed_ids), f)


def load_results() -> list:
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_result(result: dict):
    with results_lock:
        results = load_results()
        # Update existing or append new
        for i, r in enumerate(results):
            if r.get('scholarship_id') == result.get('scholarship_id'):
                results[i] = result
                break
        else:
            results.append(result)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)


def process_scholarship(scholarship_id: int) -> dict:
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
        
        logger.info(f"ID {scholarship_id}: {scholarship.title[:50]}")
        
        # Step 1: Resolve source
        resolver = SourceResolverService(timeout=TIMEOUT)
        resolved = resolver.resolve_source(official_source_url, scholarship.title)
        
        candidates = []
        results = []
        best_candidate = None
        
        # Step 2: Discover images
        if resolved.resolved_url:
            discovery = ImageDiscoveryService(timeout=TIMEOUT, max_candidates=50)
            candidates = discovery.discover_from_scholarship(resolved.resolved_url)
            
            # Step 3: Validate candidates
            validator = ImageValidator(seen_images={}, timeout=TIMEOUT)
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
                "relevance_score": r.relevance_score,
                "confidence": r.confidence,
                "status": r.status.value,
                "rejection_reasons": r.rejection_reasons,
                "human_review_reason": r.human_review_reason,
                "non_content_total_weight": r.non_content_total_weight,
            })
        
        decision = best_candidate.status.value if best_candidate else "rejected"
        confidence = best_candidate.confidence if best_candidate else "LOW"
        
        result = {
            "scholarship_id": scholarship_id,
            "scholarship_title": scholarship.title,
            "country": scholarship.country,
            "official_source_url": official_source_url,
            "source_type": source_type.value if source_type else None,
            "source_resolution_type": resolved.resolution_type.value,
            "resolved_source_url": resolved.resolved_url,
            "candidates_found": len(candidates),
            "best_candidate_url": best_candidate.candidate.image_url if best_candidate else None,
            "best_candidate_page": best_candidate.candidate.page_url if best_candidate else None,
            "best_candidate_reachable": best_candidate.is_reachable if best_candidate else False,
            "best_candidate_http_status": best_candidate.http_status if best_candidate else None,
            "best_candidate_content_type": best_candidate.content_type if best_candidate else None,
            "program_relevance": _relevance_label(best_candidate) if best_candidate else "none",
            "licensing_status": best_candidate.licensing_status if best_candidate else "licensing_unknown",
            "confidence": confidence,
            "decision": decision,
            "rejection_reasons": best_candidate.rejection_reasons if best_candidate else ["No candidates found"],
            "human_review_reason": best_candidate.human_review_reason if best_candidate else None,
            "all_candidates": all_candidates,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        
        save_result(result)
        return result
        
    except Exception as exc:
        logger.error(f"Error processing ID {scholarship_id}: {exc}")
        result = {
            "scholarship_id": scholarship_id,
            "error": str(exc),
            "decision": "rejected",
            "confidence": "LOW",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        save_result(result)
        return result
    finally:
        session.close()


def _relevance_label(best):
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


def run_concurrent(scholarship_ids: list[int]):
    """Run discovery on multiple scholarships concurrently."""
    logger.info(f"Starting concurrent processing of {len(scholarship_ids)} scholarships with {MAX_WORKERS} workers")
    
    completed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_id = {
            executor.submit(process_scholarship, sid): sid
            for sid in scholarship_ids
        }
        
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            try:
                result = future.result()
                completed += 1
                decision = result.get('decision', 'unknown')
                confidence = result.get('confidence', 'unknown')
                best_url = result.get('best_candidate_url')
                logger.info(f"Completed {completed}/{len(scholarship_ids)}: ID {sid} -> {decision.upper()} ({confidence})")
            except Exception as exc:
                logger.error(f"Future failed for ID {sid}: {exc}")
                completed += 1
    
    logger.info(f"All {completed} futures completed")
    return load_results()


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
    
    # Filter out already processed
    processed = load_progress()
    to_process = [sid for sid in scholarship_ids if sid not in processed]
    logger.info(f"Already processed: {len(processed)}, Remaining: {len(to_process)}")
    
    if to_process:
        run_concurrent(to_process)
    
    return load_results()


if __name__ == "__main__":
    results = run_all()
    
    approved = sum(1 for r in results if r.get('decision') == 'approved')
    review = sum(1 for r in results if r.get('decision') == 'human_review')
    rejected = sum(1 for r in results if r.get('decision') == 'rejected')
    
    print(f"\n{'='*70}")
    print(f"BATCH DISCOVERY COMPLETE")
    print(f"{'='*70}")
    print(f"Total processed: {len(results)}")
    print(f"  APPROVED (HIGH): {approved}")
    print(f"  HUMAN_REVIEW (MEDIUM): {review}")
    print(f"  REJECTED (LOW): {rejected}")
    print(f"{'='*70}")
