"""Phase E — 10-record LIVE WEB image dry run.

Read-only pipeline: source resolution -> image discovery -> validation ->
confidence classification. Zero database writes.

Selects 10 scholarships with NULL/empty image_url, inspects their official
pages through the existing pipeline, and prints a detailed report table.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend')

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_engine, get_session_factory
from app.models import Scholarship
from app.services.image_discovery import ImageDiscoveryService, ImageCandidate
from app.services.image_validator import (
    ImageValidator,
    ValidationStatus,
    determine_image_source_type,
    extract_domain,
)
from app.services.source_resolver import ResolvedSource, SourceResolverService

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = BACKEND_DIR / "reports"
DEFAULT_DB_PATH = BACKEND_DIR / "scholarzone.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class DryRunRecord:
    scholarship_id: int
    scholarship_title: str
    country: str
    degree: str
    status: str
    official_source_url: str | None
    resolved_source_url: str | None
    source_resolution_type: str
    source_resolution_confidence: float
    source_resolution_reason: str
    source_page_title: str | None
    candidates_found: int
    best_candidate_url: str | None
    best_candidate_page: str | None
    best_candidate_discovery_method: str | None
    best_candidate_image_kind: str | None
    best_candidate_source_type: str | None
    best_candidate_reachable: bool
    best_candidate_http_status: int | None
    best_candidate_content_type: str | None
    best_candidate_dimensions: str | None
    best_candidate_relevance: float
    best_candidate_confidence: str
    best_candidate_status: str
    best_candidate_rejection_reasons: list[str] = field(default_factory=list)
    best_candidate_human_review_reason: str | None = None
    best_candidate_non_content_signals: list[str] = field(default_factory=list)
    expected_action: str | None = None
    error: str | None = None


def _connect_production_db() -> sessionmaker:
    db_url = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    engine = get_engine()
    return sessionmaker(bind=engine)


def _load_scholarships_without_images(session: Session, limit: int = 10) -> list[Scholarship]:
    rows = session.execute(
        select(Scholarship)
        .where(Scholarship.image_url.is_(None))
        .order_by(Scholarship.id)
        .limit(limit)
    ).scalars().all()
    return list(rows)


def _process_scholarship(scholarship: Scholarship, timeout: float = 30.0) -> DryRunRecord:
    official_source_url = (scholarship.official_source_url or "").strip()

    resolver = SourceResolverService(timeout=timeout)
    try:
        resolved: ResolvedSource = resolver.resolve_source(official_source_url, scholarship.title)
    except Exception as exc:
        return DryRunRecord(
            scholarship_id=scholarship.id,
            scholarship_title=scholarship.title,
            country=scholarship.country,
            degree=scholarship.degree,
            status=scholarship.status,
            official_source_url=official_source_url or None,
            resolved_source_url=None,
            source_resolution_type="error",
            source_resolution_confidence=0.0,
            source_resolution_reason=f"Source resolution failed: {exc}",
            source_page_title=None,
            candidates_found=0,
            best_candidate_url=None,
            best_candidate_page=None,
            best_candidate_discovery_method=None,
            best_candidate_image_kind=None,
            best_candidate_source_type=None,
            best_candidate_reachable=False,
            best_candidate_http_status=None,
            best_candidate_content_type=None,
            best_candidate_dimensions=None,
            best_candidate_relevance=0.0,
            best_candidate_confidence="LOW",
            best_candidate_status="rejected",
            best_candidate_rejection_reasons=[f"Source resolution error: {exc}"],
            expected_action="none",
            error=str(exc),
        )

    candidates: list[ImageCandidate] = []
    results: list[Any] = []
    best = None
    source_type = None

    if resolved.resolved_url:
        try:
            discovery = ImageDiscoveryService(timeout=timeout, max_candidates=25)
            candidates = discovery.discover_from_scholarship(resolved.resolved_url)
        except Exception as exc:
            logger.warning("Scholarship %d: discovery failed: %s", scholarship.id, exc)

        if candidates:
            try:
                validator = ImageValidator(seen_images={}, timeout=timeout)
                results = validator.validate_candidates(
                    candidates,
                    scholarship_title=scholarship.title,
                    official_source_url=resolved.resolved_url,
                )
                best = validator.find_best_result(results)
            except Exception as exc:
                logger.warning("Scholarship %d: validation failed: %s", scholarship.id, exc)

    if best:
        domain = extract_domain(best.candidate.image_url)
        source_type = determine_image_source_type(domain)
        source_type = source_type.value if source_type else None

    dims = None
    if best and best.width and best.height:
        dims = f"{best.width}x{best.height}"

    rejection_reasons = []
    hr_reason = None
    non_content_labels = []
    if best:
        rejection_reasons = best.rejection_reasons[:5]
        hr_reason = best.human_review_reason
        non_content_labels = [s.label for s in best.non_content_signals[:5]]

    expected_action = "none"
    if best is None:
        expected_action = "rejected_low_confidence"
    else:
        if best.status == ValidationStatus.APPROVED and best.confidence == "HIGH":
            expected_action = "auto_persist"
        elif best.status == ValidationStatus.HUMAN_REVIEW and best.confidence == "MEDIUM":
            expected_action = "human_review"
        else:
            expected_action = "rejected_low_confidence"

    return DryRunRecord(
        scholarship_id=scholarship.id,
        scholarship_title=scholarship.title,
        country=scholarship.country,
        degree=scholarship.degree,
        status=scholarship.status,
        official_source_url=official_source_url or None,
        resolved_source_url=resolved.resolved_url,
        source_resolution_type=resolved.resolution_type.value,
        source_resolution_confidence=resolved.confidence,
        source_resolution_reason=resolved.reason,
        source_page_title=resolved.page_title,
        candidates_found=len(candidates),
        best_candidate_url=best.candidate.image_url if best else None,
        best_candidate_page=best.candidate.page_url if best else None,
        best_candidate_discovery_method=best.candidate.discovery_method if best else None,
        best_candidate_image_kind=best.image_kind if best else None,
        best_candidate_source_type=source_type,
        best_candidate_reachable=best.is_reachable if best else False,
        best_candidate_http_status=best.http_status if best else None,
        best_candidate_content_type=best.content_type if best else None,
        best_candidate_dimensions=dims,
        best_candidate_relevance=best.relevance_score if best else 0.0,
        best_candidate_confidence=best.confidence if best else "LOW",
        best_candidate_status=best.status.value if best else "rejected",
        best_candidate_rejection_reasons=rejection_reasons,
        best_candidate_human_review_reason=hr_reason,
        best_candidate_non_content_signals=non_content_labels,
        expected_action=expected_action,
        error=None,
    )


def _print_table(records: list[DryRunRecord]) -> None:
    headers = [
        "ID",
        "Title",
        "Official source",
        "Resolved URL",
        "Candidates",
        "Best image kind",
        "Source type",
        "Confidence",
        "Status",
        "Expected action",
        "Reason / rejection",
    ]

    rows = []
    for r in records:
        title = r.scholarship_title[:35].ljust(35)
        official = (r.official_source_url or "")[:30].ljust(30)
        resolved = (r.resolved_source_url or "")[:35].ljust(35)
        kind = (r.best_candidate_image_kind or "none").ljust(18)
        stype = (r.best_candidate_source_type or "none").ljust(22)
        confidence = r.best_candidate_confidence.ljust(10)
        status = r.best_candidate_status.ljust(14)
        action = (r.expected_action or "none").ljust(18)
        reason = ""
        if r.error:
            reason = f"ERROR: {r.error[:40]}"
        elif r.best_candidate_rejection_reasons:
            reason = r.best_candidate_rejection_reasons[0][:50]
        elif r.best_candidate_human_review_reason:
            reason = r.best_candidate_human_review_reason[:50]
        else:
            reason = r.source_resolution_reason[:50]
        rows.append([
            str(r.scholarship_id),
            title,
            official,
            resolved,
            str(r.candidates_found),
            kind,
            stype,
            confidence,
            status,
            action,
            reason,
        ])

    col_widths = [max(len(h), max((len(str(row[i])) for row in rows), default=0)) for i, h in enumerate(headers)]

    def fmt_row(cells):
        return " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(cells))

    print()
    print("=" * 180)
    print("PHASE E — IMAGE COVERAGE DRY RUN (10 scholarships, NO DB WRITES)")
    print("=" * 180)
    print(fmt_row(headers))
    print("-" * 180)
    for row in rows:
        print(fmt_row(row))
    print("=" * 180)


def _print_summary(records: list[DryRunRecord]) -> None:
    total = len(records)
    high = sum(1 for r in records if r.best_candidate_confidence == "HIGH" and r.best_candidate_status == "approved")
    medium = sum(1 for r in records if r.best_candidate_confidence == "MEDIUM" and r.best_candidate_status == "human_review")
    low = sum(1 for r in records if r.best_candidate_status == "rejected")
    errors = sum(1 for r in records if r.error is not None)
    no_candidates = sum(1 for r in records if r.candidates_found == 0)
    with_candidate = sum(1 for r in records if r.best_candidate_url)
    reachable = sum(1 for r in records if r.best_candidate_reachable)

    program_image = sum(1 for r in records if r.best_candidate_image_kind == "program_image")
    official_banner = sum(1 for r in records if r.best_candidate_image_kind == "official_banner")
    official_logo = sum(1 for r in records if r.best_candidate_image_kind == "official_logo")

    print()
    print("SUMMARY")
    print("-" * 80)
    print(f"Total processed            : {total}")
    print(f"Errors / failed resolution : {errors}")
    print(f"No candidates discovered   : {no_candidates}")
    print(f"With at least one candidate: {with_candidate}")
    print(f"Reachable best candidate   : {reachable}")
    print()
    print("Best candidate image kind:")
    print(f"  program_image            : {program_image}")
    print(f"  official_banner          : {official_banner}")
    print(f"  official_logo            : {official_logo}")
    print()
    print("Validation outcome:")
    print(f"  HIGH (auto-persist)      : {high}")
    print(f"  MEDIUM (human review)    : {medium}")
    print(f"  LOW (rejected)           : {low}")
    print()
    expected_increase = high + medium
    print(f"Expected coverage increase (HIGH + MEDIUM) : {expected_increase}/{total} => +{expected_increase/total*100:.1f} pp")
    print("=" * 80)


def _write_report(records: list[DryRunRecord]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    json_path = REPORT_DIR / f"phase_e_dry_run_10_{ts}.json"
    csv_path = REPORT_DIR / f"phase_e_dry_run_10_{ts}.csv"

    data = []
    for r in records:
        d = {
            "scholarship_id": r.scholarship_id,
            "scholarship_title": r.scholarship_title,
            "country": r.country,
            "degree": r.degree,
            "status": r.status,
            "official_source_url": r.official_source_url,
            "resolved_source_url": r.resolved_source_url,
            "source_resolution_type": r.source_resolution_type,
            "source_resolution_confidence": r.source_resolution_confidence,
            "source_resolution_reason": r.source_resolution_reason,
            "source_page_title": r.source_page_title,
            "candidates_found": r.candidates_found,
            "best_candidate_url": r.best_candidate_url,
            "best_candidate_page": r.best_candidate_page,
            "best_candidate_discovery_method": r.best_candidate_discovery_method,
            "best_candidate_image_kind": r.best_candidate_image_kind,
            "best_candidate_source_type": r.best_candidate_source_type,
            "best_candidate_reachable": r.best_candidate_reachable,
            "best_candidate_http_status": r.best_candidate_http_status,
            "best_candidate_content_type": r.best_candidate_content_type,
            "best_candidate_dimensions": r.best_candidate_dimensions,
            "best_candidate_relevance": r.best_candidate_relevance,
            "best_candidate_confidence": r.best_candidate_confidence,
            "best_candidate_status": r.best_candidate_status,
            "best_candidate_rejection_reasons": r.best_candidate_rejection_reasons,
            "best_candidate_human_review_reason": r.best_candidate_human_review_reason,
            "best_candidate_non_content_signals": r.best_candidate_non_content_signals,
            "expected_action": r.expected_action,
            "error": r.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        data.append(d)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    fieldnames = [
        "scholarship_id",
        "scholarship_title",
        "country",
        "degree",
        "status",
        "official_source_url",
        "resolved_source_url",
        "source_resolution_type",
        "source_resolution_confidence",
        "source_resolution_reason",
        "source_page_title",
        "candidates_found",
        "best_candidate_url",
        "best_candidate_page",
        "best_candidate_discovery_method",
        "best_candidate_image_kind",
        "best_candidate_source_type",
        "best_candidate_reachable",
        "best_candidate_http_status",
        "best_candidate_content_type",
        "best_candidate_dimensions",
        "best_candidate_relevance",
        "best_candidate_confidence",
        "best_candidate_status",
        "best_candidate_rejection_reasons",
        "best_candidate_human_review_reason",
        "best_candidate_non_content_signals",
        "expected_action",
        "error",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = {
                "scholarship_id": r.scholarship_id,
                "scholarship_title": r.scholarship_title,
                "country": r.country,
                "degree": r.degree,
                "status": r.status,
                "official_source_url": r.official_source_url,
                "resolved_source_url": r.resolved_source_url,
                "source_resolution_type": r.source_resolution_type,
                "source_resolution_confidence": r.source_resolution_confidence,
                "source_resolution_reason": r.source_resolution_reason,
                "source_page_title": r.source_page_title,
                "candidates_found": r.candidates_found,
                "best_candidate_url": r.best_candidate_url,
                "best_candidate_page": r.best_candidate_page,
                "best_candidate_discovery_method": r.best_candidate_discovery_method,
                "best_candidate_image_kind": r.best_candidate_image_kind,
                "best_candidate_source_type": r.best_candidate_source_type,
                "best_candidate_reachable": r.best_candidate_reachable,
                "best_candidate_http_status": r.best_candidate_http_status,
                "best_candidate_content_type": r.best_candidate_content_type,
                "best_candidate_dimensions": r.best_candidate_dimensions,
                "best_candidate_relevance": r.best_candidate_relevance,
                "best_candidate_confidence": r.best_candidate_confidence,
                "best_candidate_status": r.best_candidate_status,
                "best_candidate_rejection_reasons": "; ".join(r.best_candidate_rejection_reasons or []),
                "best_candidate_human_review_reason": r.best_candidate_human_review_reason,
                "best_candidate_non_content_signals": "; ".join(r.best_candidate_non_content_signals or []),
                "expected_action": r.expected_action,
                "error": r.error,
            }
            writer.writerow(row)

    logger.info("JSON report: %s", json_path)
    logger.info("CSV report:  %s", csv_path)
    return json_path, csv_path


def main() -> None:
    SessionLocal = _connect_production_db()
    session = SessionLocal()
    try:
        scholarships = _load_scholarships_without_images(session, limit=10)
    finally:
        session.close()

    if not scholarships:
        logger.info("No scholarships found with NULL image_url.")
        return

    logger.info("Loaded %d scholarships for Phase E dry run", len(scholarships))

    records: list[DryRunRecord] = []
    for idx, scholarship in enumerate(scholarships, 1):
        logger.info("Processing %d/%d: ID %d — %s", idx, len(scholarships), scholarship.id, scholarship.title[:60])
        try:
            record = _process_scholarship(scholarship)
            records.append(record)
            logger.info(
                "  -> %s | kind=%s | confidence=%s | status=%s",
                record.expected_action,
                record.best_candidate_image_kind,
                record.best_candidate_confidence,
                record.best_candidate_status,
            )
        except Exception as exc:
            logger.exception("Failed to process scholarship %d", scholarship.id)
            records.append(DryRunRecord(
                scholarship_id=scholarship.id,
                scholarship_title=scholarship.title,
                country=scholarship.country,
                degree=scholarship.degree,
                status=scholarship.status,
                official_source_url=scholarship.official_source_url,
                resolved_source_url=None,
                source_resolution_type="error",
                source_resolution_confidence=0.0,
                source_resolution_reason=f"Pipeline error: {exc}",
                source_page_title=None,
                candidates_found=0,
                best_candidate_url=None,
                best_candidate_page=None,
                best_candidate_discovery_method=None,
                best_candidate_image_kind=None,
                best_candidate_source_type=None,
                best_candidate_reachable=False,
                best_candidate_http_status=None,
                best_candidate_content_type=None,
                best_candidate_dimensions=None,
                best_candidate_relevance=0.0,
                best_candidate_confidence="LOW",
                best_candidate_status="rejected",
                best_candidate_rejection_reasons=[f"Pipeline error: {exc}"],
                expected_action="none",
                error=str(exc),
            ))
        time.sleep(0.3)

    _print_table(records)
    _print_summary(records)
    json_path, csv_path = _write_report(records)

    print()
    print("Reports saved:")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print()
    print("NO DATABASE WRITES WERE MADE.")


if __name__ == "__main__":
    main()
