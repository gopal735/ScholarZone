"""Dry-run pilot for evidence-driven image discovery and verification.

Selects 5 real scholarships from the existing database and runs the full
discovery + validation pipeline against their official_source_url.

IMPORTANT: This script does NOT write to the database. It produces a
dry-run report only.
"""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ..database import get_engine
from ..models import Scholarship
from ..services.image_discovery import ImageDiscoveryService
from ..services.image_validator import ImageValidator, ValidationStatus, determine_image_source_type
from ..services.scholarship_image_verifier import ImageSourceType, is_official_domain

logger = logging.getLogger(__name__)

PILOT_SCHOLARSHIP_IDS = [1, 2, 3, 5, 4]

PILOT_DISPLAY = {
    1: "Erasmus Mundus Joint Masters (EMJM)",
    2: "ICCR Scholarship (Suborno Jayanti Scheme)",
    3: "DAAD Scholarship",
    4: "Global Korea Scholarship (GKS)",
    5: "MEXT (Monbukagakusho) Scholarship",
}


@dataclass
class PilotReportEntry:
    scholarship_id: int
    scholarship_title: str
    official_source_url: str
    source_type: str | None
    candidates_found: int
    best_candidate_url: str | None
    best_candidate_source_page: str | None
    best_candidate_domain: str | None
    best_candidate_reachable: bool
    best_candidate_http_status: int | None
    best_candidate_content_type: str | None
    program_relevance: str
    licensing_status: str
    licensing_evidence: str | None
    confidence: str
    decision: str
    rejection_reasons: list[str]
    human_review_reason: str | None
    all_candidates_summary: list[dict[str, Any]]


def run_pilot_dry_run() -> list[PilotReportEntry]:
    """Run the dry-run pilot discovery/validation for 5 scholarships.

    Does NOT write to the database.
    """
    engine = get_engine()

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    entries: list[PilotReportEntry] = []

    try:
        for scholarship_id in PILOT_SCHOLARSHIP_IDS:
            scholarship = session.get(Scholarship, scholarship_id)
            if scholarship is None:
                logger.warning("Scholarship ID %d not found; skipping", scholarship_id)
                continue

            official_source_url = scholarship.official_source_url or ""
            source_domain = _extract_domain(official_source_url)
            source_type = determine_image_source_type(source_domain)

            logger.info(
                "Discovering images for scholarship ID %d (%s) from %s",
                scholarship_id, scholarship.title, official_source_url,
            )

            discovery = ImageDiscoveryService(timeout=30.0, max_candidates=50)
            candidates = discovery.discover_from_scholarship(official_source_url)
            logger.info("  Found %d candidate images", len(candidates))

            validator = ImageValidator(seen_images={}, timeout=30.0)
            results = validator.validate_candidates(
                candidates,
                scholarship_title=scholarship.title,
                official_source_url=official_source_url,
            )

            best = validator.find_best_result(results)

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
                    "is_duplicate": r.is_duplicate,
                    "relevance_score": r.relevance_score,
                    "confidence": r.confidence,
                    "status": r.status.value,
                    "rejection_reasons": r.rejection_reasons,
                })

            entry = PilotReportEntry(
                scholarship_id=scholarship_id,
                scholarship_title=scholarship.title,
                official_source_url=official_source_url,
                source_type=source_type.value if source_type else None,
                candidates_found=len(candidates),
                best_candidate_url=best.candidate.image_url if best else None,
                best_candidate_source_page=best.candidate.page_url if best else None,
                best_candidate_domain=_extract_domain(best.candidate.image_url) if best else None,
                best_candidate_reachable=best.is_reachable if best else False,
                best_candidate_http_status=best.http_status if best else None,
                best_candidate_content_type=best.content_type if best else None,
                program_relevance=_relevance_label(best) if best else "N/A",
                licensing_status=best.licensing_status if best else "licensing_unknown",
                licensing_evidence=best.licensing_evidence if best else None,
                confidence=best.confidence if best else "LOW",
                decision=best.status.value if best else "rejected",
                rejection_reasons=best.rejection_reasons if best else ["No candidates found"],
                human_review_reason=best.human_review_reason if best else None,
                all_candidates_summary=all_candidates,
            )
            entries.append(entry)

    finally:
        session.close()

    return entries


def run_pilot_json() -> str:
    """Run dry-run and return results as JSON string."""
    entries = run_pilot_dry_run()
    data = []
    for entry in entries:
        d = asdict(entry)
        d["timestamp"] = datetime.now(timezone.utc).isoformat()
        data.append(d)
    return json.dumps(data, indent=2, default=str)


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.lower() if parsed.netloc else None


def _relevance_label(best) -> str:
    if best is None:
        return "N/A"
    score = best.relevance_score
    if score >= 0.8:
        return "high"
    elif score >= 0.5:
        return "medium"
    elif score >= 0.3:
        return "low"
    return "none"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("=" * 70)
    print("PILOT DRY-RUN: Evidence-Driven Image Discovery & Validation")
    print("=" * 70)
    print()

    entries = run_pilot_dry_run()

    approved_count = sum(1 for e in entries if e.decision == "approved")
    review_count = sum(1 for e in entries if e.decision == "human_review")
    rejected_count = sum(1 for e in entries if e.decision == "rejected")

    total_candidates = sum(e.candidates_found for e in entries)

    for entry in entries:
        print(f"\n--- Scholarship ID {entry.scholarship_id}: {entry.scholarship_title} ---")
        print(f"  Source URL: {entry.official_source_url}")
        print(f"  Source Type: {entry.source_type}")
        print(f"  Candidates found: {entry.candidates_found}")
        if entry.best_candidate_url:
            print(f"  Best candidate: {entry.best_candidate_url}")
            print(f"  Best candidate domain: {entry.best_candidate_domain}")
            print(f"  Best candidate reachable: {entry.best_candidate_reachable} (HTTP {entry.best_candidate_http_status})")
            print(f"  Content type: {entry.best_candidate_content_type}")
            print(f"  Program relevance: {entry.program_relevance}")
            print(f"  Licensing: {entry.licensing_status}")
            if entry.licensing_evidence:
                print(f"  Licensing evidence: {entry.licensing_evidence}")
        print(f"  Confidence: {entry.confidence}")
        print(f"  Decision: {entry.decision.upper()}")
        if entry.rejection_reasons:
            print(f"  Rejection reasons: {entry.rejection_reasons}")
        if entry.human_review_reason:
            print(f"  Human review reason: {entry.human_review_reason}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Scholarships processed: {len(entries)}")
    print(f"  Total candidates discovered: {total_candidates}")
    print(f"  Approved (HIGH confidence): {approved_count}")
    print(f"  Human review (MEDIUM): {review_count}")
    print(f"  Rejected (LOW): {rejected_count}")
    print()

    if approved_count > 0:
        print("Approved images (safe to apply):")
        for e in entries:
            if e.decision == "approved":
                print(f"  ID {e.scholarship_id}: {e.best_candidate_url}")
    if review_count > 0:
        print("Human review needed:")
        for e in entries:
            if e.decision == "human_review":
                print(f"  ID {e.scholarship_id}: {e.best_candidate_url} — {e.human_review_reason}")
    if rejected_count > 0:
        print("Rejected (no suitable image):")
        for e in entries:
            if e.decision == "rejected":
                print(f"  ID {e.scholarship_id}: {e.rejection_reasons}")
