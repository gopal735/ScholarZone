"""Phase 8 read-only image dry run.

The script evaluates 50-100 scholarships through source resolution, image
discovery, and validation. It performs SELECT-only database access and writes
only JSON and Markdown reports.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_engine, get_session_factory, reset_database_connections
from app.models import Scholarship
from app.services.image_discovery import ImageCandidate, ImageDiscoveryService
from app.services.image_validator import (
    ImageValidator,
    ValidationStatus,
    determine_image_source_type,
)
from app.services.source_resolver import ResolvedSource, SourceResolverService


logger = logging.getLogger(__name__)
REPORT_DIR = BACKEND_DIR / "reports"
DEFAULT_DATABASE_PATH = BACKEND_DIR / "scholarzone.db"
DEFAULT_LIMIT = 50
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_CANDIDATES = 25
DEFAULT_RATE_LIMIT_SECONDS = 0.3


@dataclass
class ScholarshipContext:
    scholarship_id: int
    title: str
    country: str
    degree: str
    status: str
    official_source_url: str | None
    image_url: str | None


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
    licensing_status: str | None = None
    licensing_evidence: str | None = None
    expected_action: str | None = None
    duplicate_count: int = 0
    duplicate_urls: list[str] = field(default_factory=list)
    candidate_summaries: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    had_existing_image: bool = False


def _limit_arg(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if not 50 <= limit <= 100:
        raise argparse.ArgumentTypeError("limit must be between 50 and 100")
    return limit


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return _json_safe(value.value)
    return str(value)


def _database_url_kind(database_url: str) -> str:
    scheme = urlparse(database_url).scheme.lower()
    if scheme.startswith("sqlite"):
        return "sqlite"
    if scheme.startswith("postgresql"):
        return "postgresql"
    if scheme.startswith("mysql"):
        return "mysql"
    return scheme or "unknown"


def _session_factory(database_url: str | None):
    previous_url = os.environ.get("SCHOLARZONE_DATABASE_URL")
    if database_url:
        os.environ["SCHOLARZONE_DATABASE_URL"] = database_url
    try:
        reset_database_connections()
        return get_session_factory()
    finally:
        if database_url:
            if previous_url is None:
                os.environ.pop("SCHOLARZONE_DATABASE_URL", None)
            else:
                os.environ["SCHOLARZONE_DATABASE_URL"] = previous_url


def _default_database_url() -> str:
    configured = os.environ.get("SCHOLARZONE_DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"


def _load_contexts(session: Session, limit: int) -> list[ScholarshipContext]:
    rows = session.execute(
        select(Scholarship)
        .where(or_(Scholarship.image_url.is_(None), Scholarship.image_url == ""))
        .order_by(Scholarship.id)
        .limit(limit)
    ).scalars().all()
    return [
        ScholarshipContext(
            scholarship_id=row.id,
            title=row.title or "Unknown",
            country=row.country or "Unknown",
            degree=row.degree or "Unknown",
            status=row.status or "unknown",
            official_source_url=row.official_source_url,
            image_url=row.image_url,
        )
        for row in rows
    ]


def _snapshot(session: Session) -> dict[str, int]:
    return {
        "total_scholarships": int(session.scalar(select(func.count()).select_from(Scholarship)) or 0),
        "with_image_url": int(
            session.scalar(
                select(func.count()).where(
                    or_(Scholarship.image_url.is_not(None), Scholarship.image_url != "")
                )
            )
            or 0
        ),
        "max_scholarship_id": int(session.scalar(select(func.max(Scholarship.id))) or 0),
    }


def _source_type_for_url(url: str | None) -> str | None:
    if not url:
        return None
    domain = urlparse(url).netloc.lower()
    source_type = determine_image_source_type(domain)
    return source_type.value if source_type else None


def _candidate_summary(candidate: ImageCandidate, validation: Any | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "image_url": candidate.image_url,
        "page_url": candidate.page_url,
        "normalized_url": candidate.normalized_url,
        "discovery_method": candidate.discovery_method,
        "discovery_methods": list(candidate.discovery_methods),
        "fallback_level": candidate.fallback_level,
        "alt_text": candidate.alt_text,
        "width": candidate.width,
        "height": candidate.height,
        "source_attribute": candidate.source_attribute,
        "image_region": candidate.image_region,
        "html_context": candidate.html_context,
        "provenance": _json_safe(candidate.provenance),
        "evidence": list(candidate.evidence),
    }
    if validation is not None:
        summary.update(
            {
                "reachable": validation.is_reachable,
                "http_status": validation.http_status,
                "content_type": validation.content_type,
                "valid_image": validation.is_valid_image,
                "official_domain": validation.is_official_domain,
                "duplicate": validation.is_duplicate,
                "duplicate_of": validation.duplicate_of,
                "licensing_status": validation.licensing_status,
                "licensing_evidence": validation.licensing_evidence,
                "relevance_score": validation.relevance_score,
                "relevance_notes": list(validation.relevance_notes),
                "confidence": validation.confidence,
                "status": validation.status.value,
                "rejection_reasons": list(validation.rejection_reasons),
                "human_review_reason": validation.human_review_reason,
                "non_content_signals": [
                    {
                        "label": signal.label,
                        "weight": signal.weight,
                        "source": signal.source,
                    }
                    for signal in validation.non_content_signals
                ],
                "image_kind": validation.image_kind,
            }
        )
    return _json_safe(summary)


def _error_record(context: ScholarshipContext, stage: str, exc: Exception) -> DryRunRecord:
    return DryRunRecord(
        scholarship_id=context.scholarship_id,
        scholarship_title=context.title,
        country=context.country,
        degree=context.degree,
        status=context.status,
        official_source_url=context.official_source_url,
        had_existing_image=context.image_url not in (None, ""),
        resolved_source_url=None,
        source_resolution_type="error",
        source_resolution_confidence=0.0,
        source_resolution_reason=f"{stage} failed: {exc}",
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
        best_candidate_rejection_reasons=[f"{stage} failed: {exc}"],
        expected_action="error",
        error=str(exc),
    )


def _process_context(context: ScholarshipContext, timeout: float, max_candidates: int) -> DryRunRecord:
    official_source_url = (context.official_source_url or "").strip()
    try:
        resolver = SourceResolverService(timeout=timeout)
        resolved: ResolvedSource = resolver.resolve_source(official_source_url, context.title)
    except Exception as exc:
        return _error_record(context, "source resolution", exc)

    candidates: list[ImageCandidate] = []
    validation_results: list[Any] = []
    best = None
    error: str | None = None

    if resolved.resolved_url:
        try:
            discovery = ImageDiscoveryService(
                timeout=timeout,
                max_candidates=max_candidates,
            )
            candidates = discovery.discover_from_scholarship(resolved.resolved_url)
        except Exception as exc:
            error = f"image discovery failed: {exc}"
            logger.warning("Scholarship %d: %s", context.scholarship_id, error)

        if candidates:
            try:
                validator = ImageValidator(seen_images={}, timeout=timeout)
                validation_results = validator.validate_candidates(
                    candidates,
                    scholarship_title=context.title,
                    official_source_url=resolved.resolved_url,
                )
                best = validator.find_best_result(validation_results)
            except Exception as exc:
                error = f"image validation failed: {exc}"
                logger.warning("Scholarship %d: %s", context.scholarship_id, error)

    if best is None and validation_results:
        best = max(
            validation_results,
            key=lambda result: (
                result.status in {ValidationStatus.APPROVED, ValidationStatus.HUMAN_REVIEW},
                result.relevance_score,
            ),
        )

    validation_by_candidate = {id(validation.candidate): validation for validation in validation_results}
    candidate_summaries = [
        _candidate_summary(
            candidate,
            validation_by_candidate.get(id(candidate)),
        )
        for candidate in candidates
    ]

    duplicate_urls = [
        validation.candidate.image_url
        for validation in validation_results
        if validation.is_duplicate
    ]
    best_candidate = best.candidate if best else None
    best_source_type = _source_type_for_url(
        best_candidate.image_url if best_candidate else None
    )
    dimensions = None
    if best and best.width and best.height:
        dimensions = f"{best.width}x{best.height}"

    if best:
        rejection_reasons = list(best.rejection_reasons)
        human_review_reason = best.human_review_reason
        non_content_signals = [signal.label for signal in best.non_content_signals]
        confidence = best.confidence
        status = best.status.value
        reachable = best.is_reachable
        http_status = best.http_status
        content_type = best.content_type
        relevance = best.relevance_score
        licensing_status = best.licensing_status
        licensing_evidence = best.licensing_evidence
        image_kind = best.image_kind
        if status == ValidationStatus.APPROVED.value and confidence == "HIGH":
            expected_action = "auto_persist"
        elif status == ValidationStatus.HUMAN_REVIEW.value and confidence == "MEDIUM":
            expected_action = "human_review"
        else:
            expected_action = "rejected_low_confidence"
    else:
        rejection_reasons = ["No valid image candidate found"] if not candidates else []
        human_review_reason = None
        non_content_signals = []
        confidence = "LOW"
        status = "rejected"
        reachable = False
        http_status = None
        content_type = None
        relevance = 0.0
        licensing_status = "licensing_unknown"
        licensing_evidence = None
        image_kind = None
        expected_action = "rejected_low_confidence"

    if error and not rejection_reasons:
        rejection_reasons = [error]

    return DryRunRecord(
        scholarship_id=context.scholarship_id,
        scholarship_title=context.title,
        country=context.country,
        degree=context.degree,
        status=context.status,
        official_source_url=context.official_source_url,
        had_existing_image=context.image_url not in (None, ""),
        resolved_source_url=resolved.resolved_url,
        source_resolution_type=resolved.resolution_type.value,
        source_resolution_confidence=resolved.confidence,
        source_resolution_reason=resolved.reason,
        source_page_title=resolved.page_title,
        candidates_found=len(candidates),
        best_candidate_url=best_candidate.image_url if best_candidate else None,
        best_candidate_page=best_candidate.page_url if best_candidate else None,
        best_candidate_discovery_method=best_candidate.discovery_method if best_candidate else None,
        best_candidate_image_kind=image_kind,
        best_candidate_source_type=best_source_type,
        best_candidate_reachable=reachable,
        best_candidate_http_status=http_status,
        best_candidate_content_type=content_type,
        best_candidate_dimensions=dimensions,
        best_candidate_relevance=relevance,
        best_candidate_confidence=confidence,
        best_candidate_status=status,
        best_candidate_rejection_reasons=rejection_reasons,
        best_candidate_human_review_reason=human_review_reason,
        best_candidate_non_content_signals=non_content_signals,
        licensing_status=licensing_status,
        licensing_evidence=licensing_evidence,
        expected_action=expected_action,
        duplicate_count=len(duplicate_urls),
        duplicate_urls=duplicate_urls,
        candidate_summaries=candidate_summaries,
        error=error,
    )


def _record_outcome(record: DryRunRecord) -> str:
    if record.error:
        return "error"
    if record.expected_action == "auto_persist":
        return "accepted"
    if record.expected_action == "human_review":
        return "review"
    return "rejected"


def _counter(values: list[Any], default: str = "none") -> dict[str, int]:
    counts = Counter(str(value) if value not in (None, "") else default for value in values)
    return dict(sorted(counts.items()))


def _examples(records: list[DryRunRecord], outcome: str, limit: int = 5) -> list[dict[str, Any]]:
    selected = [record for record in records if _record_outcome(record) == outcome][:limit]
    return [
        {
            "scholarship_id": record.scholarship_id,
            "scholarship_title": record.scholarship_title,
            "confidence": record.best_candidate_confidence,
            "image_kind": record.best_candidate_image_kind,
            "reason": (
                record.best_candidate_rejection_reasons[0]
                if record.best_candidate_rejection_reasons
                else record.source_resolution_reason
            ),
        }
        for record in selected
    ]


def _build_summary(
    records: list[DryRunRecord],
    pre_snapshot: dict[str, int],
    post_snapshot: dict[str, int],
    sample_size: int,
) -> dict[str, Any]:
    outcomes = Counter(_record_outcome(record) for record in records)
    confidence_counts = _counter([record.best_candidate_confidence for record in records])
    status_counts = _counter([record.best_candidate_status for record in records])
    image_kind_counts = _counter([record.best_candidate_image_kind for record in records])
    discovery_method_counts = _counter(
        [record.best_candidate_discovery_method for record in records]
    )
    all_method_counts = Counter(
        candidate["discovery_method"]
        for record in records
        for candidate in record.candidate_summaries
    )
    reason_counts = Counter(
        reason
        for record in records
        for reason in (
            record.best_candidate_rejection_reasons
            + ([record.error] if record.error else [])
            + ([record.source_resolution_reason] if record.source_resolution_reason else [])
        )
    )
    duplicate_records = [
        record
        for record in records
        if record.duplicate_count
        or any(
            candidate.get("duplicate")
            for candidate in record.candidate_summaries
        )
    ]
    no_candidate_records = [record for record in records if record.candidates_found == 0]
    validator_duplicate_count = sum(record.duplicate_count for record in records)
    all_image_urls = [
        candidate["image_url"]
        for record in records
        for candidate in record.candidate_summaries
        if candidate.get("image_url")
    ]
    url_occurrences = Counter(all_image_urls)
    cross_record_duplicate_count = sum(count - 1 for count in url_occurrences.values() if count > 1)
    duplicate_count = validator_duplicate_count + cross_record_duplicate_count
    accepted = outcomes["accepted"]
    review = outcomes["review"]
    rejected = outcomes["rejected"] + outcomes["error"]
    sample_old_coverage = sum(1 for record in records if record.had_existing_image) / sample_size if sample_size else 0.0
    sample_new_coverage = accepted / sample_size if sample_size else 0.0
    old_coverage = pre_snapshot["with_image_url"] / pre_snapshot["total_scholarships"] if pre_snapshot["total_scholarships"] else 0.0
    projected_with_image = pre_snapshot["with_image_url"] + accepted
    new_coverage = projected_with_image / pre_snapshot["total_scholarships"] if pre_snapshot["total_scholarships"] else 0.0
    return {
        "sample_size": sample_size,
        "processed_records": len(records),
        "accepted_records": accepted,
        "human_review_records": review,
        "rejected_records": rejected,
        "outcome_counts": dict(sorted(outcomes.items())),
        "confidence_counts": confidence_counts,
        "status_counts": status_counts,
        "image_kind_counts": image_kind_counts,
        "best_discovery_method_counts": discovery_method_counts,
        "all_discovery_method_counts": dict(sorted(all_method_counts.items())),
        "reason_counts": dict(reason_counts.most_common()),
        "duplicate_candidate_count": duplicate_count,
        "validator_duplicate_candidate_count": validator_duplicate_count,
        "cross_record_duplicate_candidate_count": cross_record_duplicate_count,
        "records_with_duplicates": len(duplicate_records),
        "no_candidate_count": len(no_candidate_records),
        "no_candidate_scholarships": [
            {
                "scholarship_id": record.scholarship_id,
                "scholarship_title": record.scholarship_title,
            }
            for record in no_candidate_records
        ],
        "sample_old_coverage": sample_old_coverage,
        "sample_new_coverage": sample_new_coverage,
        "old_coverage": old_coverage,
        "new_coverage": new_coverage,
        "global_old_coverage": old_coverage,
        "global_projected_coverage": new_coverage,
        "global_coverage_delta": new_coverage - old_coverage,
        "coverage_delta": new_coverage - old_coverage,
        "projected_new_image_count": accepted,
        "projected_reviewable_count": accepted + review,
        "examples": {
            "accepted": _examples(records, "accepted"),
            "human_review": _examples(records, "review"),
            "rejected": _examples(records, "rejected"),
            "error": _examples(records, "error"),
        },
        "database_unchanged": pre_snapshot == post_snapshot,
    }


def _report_document(summary: dict[str, Any], pre_snapshot: dict[str, int], post_snapshot: dict[str, int], limitations: list[str]) -> str:
    def pct(value: float) -> str:
        return f"{value * 100:.1f}%"

    lines = [
        "# Phase 8 Image Dry Run",
        "",
        "## Database Safety",
        "",
        f"- Pre-run snapshot: `{json.dumps(pre_snapshot, sort_keys=True)}`",
        f"- Post-run snapshot: `{json.dumps(post_snapshot, sort_keys=True)}`",
        f"- Database unchanged: **{str(summary['database_unchanged']).lower()}**",
        "",
        "## Coverage",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Sample size | {summary['sample_size']} |",
        f"| Sample old coverage | {pct(summary['sample_old_coverage'])} |",
        f"| Sample projected coverage | {pct(summary['sample_new_coverage'])} |",
        f"| Global old coverage | {pct(summary['global_old_coverage'])} |",
        f"| Global projected coverage | {pct(summary['global_projected_coverage'])} |",
        f"| Global coverage delta | {pct(summary['global_coverage_delta'])} |",
        f"| Projected new images | {summary['projected_new_image_count']} |",
        f"| Projected reviewable records | {summary['projected_reviewable_count']} |",
        "",
        "## Outcomes",
        "",
        "| Outcome | Count |",
        "|---|---:|",
        f"| Accepted | {summary['accepted_records']} |",
        f"| Human review | {summary['human_review_records']} |",
        f"| Rejected or error | {summary['rejected_records']} |",
        "",
        "## Confidence",
        "",
        "| Confidence | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {key} | {value} |" for key, value in summary["confidence_counts"].items())
    lines.extend(["", "## Image Kinds", "", "| Image kind | Count |", "|---|---:|"])
    lines.extend(f"| {key} | {value} |" for key, value in summary["image_kind_counts"].items())
    lines.extend(["", "## Best Discovery Methods", "", "| Method | Count |", "|---|---:|"])
    lines.extend(f"| {key} | {value} |" for key, value in summary["best_discovery_method_counts"].items())
    lines.extend(["", "## All Discovery Methods", "", "| Method | Count |", "|---|---:|"])
    lines.extend(f"| {key} | {value} |" for key, value in summary["all_discovery_method_counts"].items())
    lines.extend(["", "## Reasons", "", "| Reason | Count |", "|---|---:|"])
    lines.extend(f"| {key} | {value} |" for key, value in summary["reason_counts"].items())
    lines.extend(
        [
            "",
            "## Examples",
            "",
        ]
    )
    for outcome in ("accepted", "human_review", "rejected", "error"):
        lines.append(f"### {outcome.replace('_', ' ').title()}")
        lines.append("")
        examples = summary["examples"][outcome]
        if not examples:
            lines.append("None.")
        else:
            lines.extend(["| ID | Title | Confidence | Image kind | Reason |", "|---:|---|---|---|---|"])
            for example in examples:
                reason = str(example["reason"]).replace("|", "\\|").replace("\n", " ")
                title = str(example["scholarship_title"]).replace("|", "\\|")
                lines.append(
                    f"| {example['scholarship_id']} | {title} | {example['confidence']} | {example['image_kind'] or 'none'} | {reason} |"
                )
        lines.append("")
    lines.extend(
        [
            "## Duplicates And Missing Candidates",
            "",
            f"- Duplicate candidate occurrences: {summary['duplicate_candidate_count']}",
            f"- Records with duplicates: {summary['records_with_duplicates']}",
            f"- Records with no candidates: {summary['no_candidate_count']}",
            "",
        ]
    )
    no_candidates = summary["no_candidate_scholarships"][:20]
    if no_candidates:
        lines.extend(["| ID | Title |", "|---:|---|"])
        lines.extend(
            f"| {item['scholarship_id']} | {str(item['scholarship_title']).replace('|', '\\|')} |"
            for item in no_candidates
        )
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in limitations)
    lines.append("")
    return "\n".join(lines)


def _write_reports(
    report_data: dict[str, Any],
    markdown: str,
    json_path: Path,
    markdown_path: Path,
) -> tuple[Path, Path]:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(_json_safe(report_data), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return json_path, markdown_path


def run_dry_run(
    limit: int = DEFAULT_LIMIT,
    timeout: float = DEFAULT_TIMEOUT,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
    database_url: str | None = None,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> dict[str, Any]:
    if not 50 <= limit <= 100:
        raise ValueError("limit must be between 50 and 100")

    run_started_at = datetime.now(timezone.utc)
    session_factory = _session_factory(database_url)
    session = session_factory()
    try:
        pre_snapshot = _snapshot(session)
        contexts = _load_contexts(session, limit)
    finally:
        session.close()

    records: list[DryRunRecord] = []
    for index, context in enumerate(contexts, start=1):
        records.append(_process_context(context, timeout, max_candidates))
        if index < len(contexts) and rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)
        if index % 10 == 0 or index == len(contexts):
            logger.info("Processed %d/%d scholarships", index, len(contexts))

    session = session_factory()
    try:
        post_snapshot = _snapshot(session)
    finally:
        session.close()

    summary = _build_summary(records, pre_snapshot, post_snapshot, len(contexts))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    resolved_json_path = json_path or REPORT_DIR / f"phase_8_image_dry_run_{timestamp}.json"
    resolved_markdown_path = markdown_path or REPORT_DIR / f"phase_8_image_dry_run_{timestamp}.md"
    limitations = [
        "The script performs SELECT-only database reads and never calls verification, review, or persistence services.",
        "The sample contains scholarships without an image URL, so sample old coverage is expected to be zero.",
        "HTTP results can vary with source availability, redirects, rate limits, and transient network failures.",
        "Validator duplicate state is scoped to each scholarship; the report separately counts duplicate signals observed in this run.",
        "Human-review and auto-persist outcomes are projections only; no database records are changed.",
    ]
    report_data = {
        "run": {
            "started_at": run_started_at.isoformat(),
            "limit_requested": limit,
            "limit_processed": len(contexts),
            "selection": "scholarships with null or empty image_url",
            "timeout_seconds": timeout,
            "max_candidates_per_scholarship": max_candidates,
            "database_url_kind": _database_url_kind(database_url or _default_database_url()),
        },
        "database": {
            "pre_run": pre_snapshot,
            "post_run": post_snapshot,
            "unchanged": pre_snapshot == post_snapshot,
        },
        "summary": summary,
        "records": [asdict(record) for record in records],
        "limitations": limitations,
        "json_path": str(resolved_json_path),
        "markdown_path": str(resolved_markdown_path),
    }
    markdown = _report_document(summary, pre_snapshot, post_snapshot, limitations)
    _write_reports(report_data, markdown, resolved_json_path, resolved_markdown_path)
    return report_data


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a read-only Phase 8 image dry run")
    parser.add_argument("--limit", type=_limit_arg, default=DEFAULT_LIMIT, help="Number of scholarships to evaluate (50-100)")
    parser.add_argument("--database-url", help="Database URL; omitted uses SCHOLARZONE_DATABASE_URL or the local SQLite file")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Per-request timeout in seconds")
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES, help="Maximum discovered candidates per scholarship")
    parser.add_argument("--rate-limit-seconds", type=float, default=DEFAULT_RATE_LIMIT_SECONDS, help="Delay between scholarships")
    parser.add_argument("--json-output", type=Path, help="JSON report path")
    parser.add_argument("--markdown-output", type=Path, help="Markdown report path")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    report = run_dry_run(
        limit=args.limit,
        timeout=args.timeout,
        max_candidates=max(1, args.max_candidates),
        rate_limit_seconds=max(0.0, args.rate_limit_seconds),
        database_url=args.database_url,
        json_path=args.json_output,
        markdown_path=args.markdown_output,
    )
    summary = report["summary"]
    print(
        "Phase 8 dry run: "
        f"sample={summary['sample_size']} "
        f"accepted={summary['accepted_records']} "
        f"review={summary['human_review_records']} "
        f"rejected={summary['rejected_records']} "
        f"db_unchanged={str(summary['database_unchanged']).lower()}"
    )
    print(f"JSON: {report['json_path']}")
    print(f"Markdown: {report['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
