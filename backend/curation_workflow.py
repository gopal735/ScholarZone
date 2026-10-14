"""Read-only official image curation workflow.

Identifies scholarships with no trustworthy automated image, discovers
candidate images from official domains, validates them using the existing
ImageValidator, and produces a curation report.

NO database writes. NO Playwright. NO new image engine.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_engine, init_database  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.image_discovery import ImageDiscoveryService, ImageCandidate  # noqa: E402
from app.services.image_validator import ImageValidator, ValidationStatus, determine_image_source_type  # noqa: E402
from app.services.source_resolver import SourceResolverService  # noqa: E402
from sqlalchemy import select  # noqa: E402


# ---------------------------------------------------------------------------
# Curation data model
# ---------------------------------------------------------------------------
@dataclass
class CurationResult:
    scholarship_id: int
    scholarship_name: str
    type: str  # UNIVERSITY | GOVERNMENT | PROVIDER
    official_page: str
    candidate_image_url: str | None
    validation_result: str
    confidence: str
    decision: str  # APPROVED | HUMAN_REVIEW | REJECTED
    reason: str
    relevance_score: float | None = None
    non_content_weight: float | None = None
    image_domain: str | None = None
    discovery_method: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    width: int | None = None
    height: int | None = None
    licensing_status: str | None = None
    licensing_evidence: str | None = None
    processing_time_ms: float | None = None


# ---------------------------------------------------------------------------
# Priority selection — top 20 most prestigious / highest-visibility programs
# ---------------------------------------------------------------------------
TOP_20_IDS = [
    80,   # Rhodes Scholarship (Global Constituency) — University of Oxford
    68,   # Gates Cambridge Scholarship
    62,   # Knight-Hennessy Scholars — Stanford University
    125,  # Harvard University Financial Aid (International)
    126,  # Yale University Need-Based Financial Aid (International)
    127,  # Princeton University Financial Aid (International)
    128,  # Brown University Financial Aid (International)
    129,  # Dartmouth College Financial Aid (International)
    63,   # Michigan State University International Merit Scholarships
    122,  # Karsh International Scholars Program — Duke University
    54,   # University of Miami Stamps Scholarship
    65,   # Clarendon Fund Scholarship — University of Oxford
    66,   # Weidenfeld-Hoffmann Scholarships and Leadership Programme
    83,   # McCall MacBain Scholarships at McGill University
    82,   # Pierre Elliott Trudeau Foundation Doctoral Scholarship
    47,   # Melbourne International Undergraduate Scholarship
    102,  # NUS Research Scholarship
    208,  # Seoul National University (SNU) President Fellowship Program
    94,   # INSEAD MBA / Master in Management / Master in Finance Scholarships
    14,   # ETH Zurich Excellence Scholarship & Opportunity Programme (ESOP)
]


def classify_scholarship_type(source_type_str: str | None, official_source_url: str | None) -> str:
    """Map ImageSourceType / domain to curation type label."""
    if source_type_str:
        mapping = {
            "official_university": "UNIVERSITY",
            "official_government": "GOVERNMENT",
            "official_scholarship": "PROVIDER",
            "official_provider": "PROVIDER",
        }
        if source_type_str in mapping:
            return mapping[source_type_str]

    # Fallback: classify by domain suffix
    if official_source_url:
        domain = urlparse(official_source_url).netloc.lower()
        if domain.endswith(".edu") or ".ac." in domain:
            return "UNIVERSITY"
        if domain.endswith(".gov") or domain.endswith(".gov.uk") or ".go." in domain:
            return "GOVERNMENT"
    return "PROVIDER"


def curate_scholarship(scholarship: Scholarship) -> CurationResult:
    """Run read-only curation for a single scholarship."""
    start = time.perf_counter()
    official_url = scholarship.official_source_url or ""

    # 1. Classify type
    source_type = determine_image_source_type(
        urlparse(official_url).netloc.lower() if official_url else None
    )
    source_type_str = source_type.value if source_type else None
    provider_type = classify_scholarship_type(source_type_str, official_url)

    # 2. Resolve best official page
    resolver = SourceResolverService(timeout=20.0, max_routes=10)
    resolved = resolver.resolve_source(official_url, scholarship.title)
    best_page = resolved.resolved_url or official_url

    # 3. Discover candidates from the official page
    discovery = ImageDiscoveryService(timeout=30.0, max_candidates=30)
    candidates = discovery.discover_from_scholarship(best_page)

    # 4. Validate candidates
    validator = ImageValidator(timeout=30.0)
    validation_results = validator.validate_candidates(
        candidates,
        scholarship_title=scholarship.title,
        official_source_url=official_url,
    )

    # 5. Pick best result
    best_result = validator.find_best_result(validation_results)

    # If no approved/human_review, show the best rejected candidate for transparency
    best_rejected = None
    if best_result is None and validation_results:
        rejected = [r for r in validation_results if r.status == ValidationStatus.REJECTED]
        if rejected:
            best_rejected = max(rejected, key=lambda r: r.relevance_score)

    elapsed_ms = (time.perf_counter() - start) * 1000.0

    if best_result is None:
        candidate_url = None
        validation_result = "no_valid_candidates"
        confidence = "LOW"
        decision = "REJECTED"
        if best_rejected:
            candidate_url = best_rejected.candidate.image_url
            validation_result = "rejected"
            confidence = best_rejected.confidence
            reason = "; ".join(best_rejected.rejection_reasons[:3]) if best_rejected.rejection_reasons else "Failed validation checks"
            relevance_score = round(best_rejected.relevance_score, 4)
            non_content_weight = round(best_rejected.non_content_total_weight, 4)
            image_domain = best_rejected.image_domain
            discovery_method = best_rejected.candidate.discovery_method
            http_status = best_rejected.http_status
            content_type = best_rejected.content_type
            width = best_rejected.width
            height = best_rejected.height
            licensing_status = best_rejected.licensing_status
            licensing_evidence = best_rejected.licensing_evidence
        else:
            reason = "No image candidates discovered from official page"
            relevance_score = None
            non_content_weight = None
            image_domain = None
            discovery_method = None
            http_status = None
            content_type = None
            width = None
            height = None
            licensing_status = None
            licensing_evidence = None

        return CurationResult(
            scholarship_id=scholarship.id,
            scholarship_name=scholarship.title,
            type=provider_type,
            official_page=best_page,
            candidate_image_url=candidate_url,
            validation_result=validation_result,
            confidence=confidence,
            decision=decision,
            reason=reason,
            relevance_score=relevance_score,
            non_content_weight=non_content_weight,
            image_domain=image_domain,
            discovery_method=discovery_method,
            http_status=http_status,
            content_type=content_type,
            width=width,
            height=height,
            licensing_status=licensing_status,
            licensing_evidence=licensing_evidence,
            processing_time_ms=round(elapsed_ms, 1),
        )

    status = best_result.status.value
    confidence = best_result.confidence
    candidate = best_result.candidate

    # Build human-readable reason
    if status == "approved":
        reason = "High relevance, official domain, reachable, no non-content signals, licensing inferred"
    elif status == "human_review":
        if best_result.human_review_reason:
            reason = best_result.human_review_reason
        else:
            reason = f"Moderate relevance ({best_result.relevance_score:.2f}) or unknown licensing — needs human review"
    else:
        if best_result.rejection_reasons:
            reason = "; ".join(best_result.rejection_reasons[:3])
        else:
            reason = "Failed validation checks"

    return CurationResult(
        scholarship_id=scholarship.id,
        scholarship_name=scholarship.title,
        type=provider_type,
        official_page=best_page,
        candidate_image_url=candidate.image_url if status != "rejected" else candidate.image_url,
        validation_result=status,
        confidence=confidence,
        decision=status.upper(),
        reason=reason,
        relevance_score=round(best_result.relevance_score, 4),
        non_content_weight=round(best_result.non_content_total_weight, 4),
        image_domain=best_result.image_domain,
        discovery_method=candidate.discovery_method,
        http_status=best_result.http_status,
        content_type=best_result.content_type,
        width=best_result.width,
        height=best_result.height,
        licensing_status=best_result.licensing_status,
        licensing_evidence=best_result.licensing_evidence,
        processing_time_ms=round(elapsed_ms, 1),
    )


def run_curation() -> list[CurationResult]:
    """Execute curation on the top 20 scholarships."""
    # Use direct engine to avoid test-isolation enforcement
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = BACKEND_DIR / "scholarzone.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        stmt = (
            select(Scholarship)
            .where(Scholarship.id.in_(TOP_20_IDS))
            .order_by(Scholarship.id)
        )
        scholarships = session.scalars(stmt).all()
    finally:
        session.close()
        engine.dispose()

    results: list[CurationResult] = []
    for scholarship in scholarships:
        print(f"[{scholarship.id}] Curating: {scholarship.title[:60]}...")
        result = curate_scholarship(scholarship)
        results.append(result)
        print(f"    -> {result.decision} | confidence={result.confidence} | time={result.processing_time_ms}ms")

    return results


def write_report(results: list[CurationResult]) -> None:
    """Write curation report as JSON and CSV."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_dir = BACKEND_DIR / "reports"
    report_dir.mkdir(exist_ok=True)

    json_path = report_dir / f"curation_report_{timestamp}.json"
    csv_path = report_dir / f"curation_report_{timestamp}.csv"

    # JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False, default=str)

    # CSV
    fieldnames = [
        "scholarship_id",
        "scholarship_name",
        "type",
        "official_page",
        "candidate_image_url",
        "validation_result",
        "confidence",
        "decision",
        "reason",
        "relevance_score",
        "non_content_weight",
        "image_domain",
        "discovery_method",
        "http_status",
        "content_type",
        "width",
        "height",
        "licensing_status",
        "licensing_evidence",
        "processing_time_ms",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    print(f"\nReports written:")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")


def print_summary(results: list[CurationResult]) -> None:
    approved = [r for r in results if r.decision == "APPROVED"]
    human_review = [r for r in results if r.decision == "HUMAN_REVIEW"]
    rejected = [r for r in results if r.decision == "REJECTED"]

    print("\n" + "=" * 70)
    print("CURATION SUMMARY")
    print("=" * 70)
    print(f"Total scholarships curated: {len(results)}")
    print(f"  APPROVED:      {len(approved)}")
    print(f"  HUMAN_REVIEW:  {len(human_review)}")
    print(f"  REJECTED:      {len(rejected)}")
    print()

    # Group by type
    by_type: dict[str, list[CurationResult]] = {}
    for r in results:
        by_type.setdefault(r.type, []).append(r)

    for t in ["UNIVERSITY", "GOVERNMENT", "PROVIDER"]:
        group = by_type.get(t, [])
        if not group:
            continue
        approved_t = sum(1 for r in group if r.decision == "APPROVED")
        print(f"--- {t} ({len(group)}) ---")
        for r in group:
            status_icon = "A" if r.decision == "APPROVED" else ("H" if r.decision == "HUMAN_REVIEW" else "R")
            print(f"  [{status_icon}] #{r.scholarship_id} {r.scholarship_name[:50]}")
            print(f"       Page: {r.official_page[:80]}")
            if r.candidate_image_url:
                print(f"       Image: {r.candidate_image_url[:80]}")
            print(f"       Decision: {r.decision} | Confidence: {r.confidence}")
            if r.relevance_score is not None:
                print(f"       Relevance: {r.relevance_score} | Non-content weight: {r.non_content_weight}")
            print(f"       Reason: {r.reason[:120]}")
            print()


if __name__ == "__main__":
    print("=" * 70)
    print("OFFICIAL IMAGE CURATION WORKFLOW — READ-ONLY")
    print("=" * 70)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target: {len(TOP_20_IDS)} highest-priority scholarships")
    print(f"Database: {BACKEND_DIR / 'scholarzone.db'}")
    print("=" * 70)
    print()

    results = run_curation()
    write_report(results)
    print_summary(results)

    print("\nCuration complete. No database modifications were made.")
