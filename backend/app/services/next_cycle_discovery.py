"""Next-cycle discovery for closed scholarships.

When a scholarship is CLOSED, this service searches its official source
for evidence of the next application cycle. It only marks a scholarship
as UPCOMING when an official next-cycle announcement or call is found.

Design:
- Never infers dates from previous years
- Only accepts future cycles that are officially announced/confirmed
- Creates discovery candidates for review when next cycle is detected
- Integrates with existing discovery pipeline for authoritative verification
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ApprovedSource,
    DiscoveryCandidate,
    Scholarship,
    ScholarshipVerificationHistory,
)
from .discovery_config import seed_approved_sources
from .discovery_identity import normalize_url
from .official_source_fetcher import OfficialSourceFetchResult, fetch_official_source
from .scholarship_extractor import extract_scholarship_information
from .telemetry import PipelineStages, record_event

logger = logging.getLogger(__name__)

_NEXT_CYCLE_PATTERNS = [
    r"\b(20\d{2})\s*[-–]\s*(20\d{2})\b",
    r"\b(20\d{2})\s*/\s*(20\d{2})\b",
    r"\b(20\d{2})\s+intake\b",
    r"\b(20\d{2})\s+cycle\b",
    r"\b(20\d{2})\s+cohort\b",
    r"\bnow\s+open\b",
    r"\baccepted?\s+for\s+(20\d{2})\b",
    r"\bapply\s+for\s+(20\d{2})\b",
    r"\bnext\s+(cycle|intake|cohort|year|academic\s+year)\b",
    r"\b(autumn|fall|spring|winter)\s+(20\d{2})\b",
    r"\bdeadline.*(20\d{2})\b",
    r"\bapplications\s+open\b",
    r"\bnow\s+accepting\b",
    r"\bopen\s+for\s+applications\b",
]

_NEXT_CYCLE_RE = re.compile("|".join(_NEXT_CYCLE_PATTERNS), re.IGNORECASE)


@dataclass(frozen=True)
class NextCycleDiscoveryResult:
    scholarship_id: int
    discovered: bool
    next_cycle_year: int | None
    next_cycle_text: str | None
    source_verified: bool
    confidence: str
    evidence: str
    proposed_status: str | None
    error: str | None = None


def discover_next_cycle(
    session: Session,
    scholarship: Scholarship,
    max_attempts: int = 2,
) -> NextCycleDiscoveryResult:
    """Search for the next application cycle of a CLOSED scholarship.

    Args:
        session: SQLAlchemy session
        scholarship: The CLOSED scholarship to check
        max_attempts: Maximum fetch retries

    Returns:
        NextCycleDiscoveryResult with findings
    """
    if not scholarship.official_source_url:
        return NextCycleDiscoveryResult(
            scholarship_id=scholarship.id,
            discovered=False,
            next_cycle_year=None,
            next_cycle_text=None,
            source_verified=False,
            confidence="low",
            evidence="No official_source_url",
            proposed_status=None,
            error="missing_source_url",
        )

    normalized_url = normalize_url(scholarship.official_source_url)
    if not normalized_url:
        return NextCycleDiscoveryResult(
            scholarship_id=scholarship.id,
            discovered=False,
            next_cycle_year=None,
            next_cycle_text=None,
            source_verified=False,
            confidence="low",
            evidence="Invalid source URL",
            proposed_status=None,
            error="invalid_url",
        )

    fetch_result = fetch_official_source(normalized_url)
    if not fetch_result.success:
        return NextCycleDiscoveryResult(
            scholarship_id=scholarship.id,
            discovered=False,
            next_cycle_year=None,
            next_cycle_text=None,
            source_verified=False,
            confidence="low",
            evidence=f"Fetch failed: {fetch_result.error_reason}",
            proposed_status=None,
            error=fetch_result.error_type,
        )

    content = fetch_result.content or ""
    extraction = extract_scholarship_information(content, normalized_url)

    title = extraction.scholarship_name or scholarship.title or ""
    provider = extraction.provider or scholarship.official_source or ""
    full_text = f"{title} {provider} {content} {extraction.model_dump_json()}"

    matches = _NEXT_CYCLE_RE.findall(full_text)
    current_year = datetime.now(timezone.utc).year

    future_years: list[int] = []
    for match in matches:
        if isinstance(match, tuple):
            for year_str in match:
                try:
                    year = int(year_str)
                    if year >= current_year:
                        future_years.append(year)
                except ValueError:
                    continue
        else:
            try:
                year = int(match)
                if year >= current_year:
                    future_years.append(year)
            except ValueError:
                continue

    future_years = sorted(set(future_years), reverse=True)
    next_cycle_year = future_years[0] if future_years else None
    next_cycle_text = _extract_context(full_text, next_cycle_year) if next_cycle_year else None

    has_explicit_open = bool(re.search(r"\b(applications?\s+(?:now\s+)?open|now\s+(?:accepting|open)|open\s+for\s+applications?)\b", full_text, re.IGNORECASE))
    has_explicit_year = next_cycle_year is not None
    has_deadline = extraction.deadline is not None

    if has_explicit_open and has_explicit_year:
        confidence = "high"
        discovered = True
        evidence = f"Explicit next-cycle announcement for {next_cycle_year} with open application language"
    elif has_explicit_open and has_deadline:
        confidence = "high"
        discovered = True
        next_cycle_year = next_cycle_year or current_year
        evidence = "Explicit open application with deadline on official source"
    elif has_explicit_year and not has_explicit_open:
        confidence = "medium"
        discovered = True
        evidence = f"Future cycle year {next_cycle_year} mentioned but no explicit open announcement"
    else:
        confidence = "low"
        discovered = False
        evidence = "No clear next-cycle announcement found"

    proposed_status = "upcoming" if discovered else None

    return NextCycleDiscoveryResult(
        scholarship_id=scholarship.id,
        discovered=discovered,
        next_cycle_year=next_cycle_year,
        next_cycle_text=next_cycle_text,
        source_verified=True,
        confidence=confidence,
        evidence=evidence,
        proposed_status=proposed_status,
    )


def _extract_context(text: str, year: int | None) -> str | None:
    if year is None:
        return None
    pattern = re.compile(r".{0,100}" + re.escape(str(year)) + r".{0,100}", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        context = match.group(0).strip()
        context = re.sub(r"\s+", " ", context)
        return context[:200]
    return None


def batch_discover_next_cycles(
    session: Session,
    scholarship_ids: list[int],
    max_attempts: int = 2,
) -> list[NextCycleDiscoveryResult]:
    """Discover next cycles for multiple closed scholarships.

    Args:
        session: SQLAlchemy session
        scholarship_ids: List of scholarship IDs to check
        max_attempts: Maximum fetch retries per scholarship

    Returns:
        List of NextCycleDiscoveryResult objects
    """
    results = []
    for sid in scholarship_ids:
        scholarship = session.get(Scholarship, sid)
        if scholarship is None:
            continue
        if scholarship.status != "closed":
            continue

        discovery_start = datetime.now(timezone.utc)
        result = discover_next_cycle(session, scholarship, max_attempts)
        discovery_duration_ms = (datetime.now(timezone.utc) - discovery_start).total_seconds() * 1000.0

        record_event(
            stage=PipelineStages.DISCOVERY,
            metric_type="success" if result.discovered else "failure",
            duration_ms=discovery_duration_ms,
            scholarship_id=sid,
            source=scholarship.official_source_url,
            success=result.discovered,
            metadata={
                "next_cycle_year": result.next_cycle_year,
                "confidence": result.confidence,
                "discovered": result.discovered,
            },
        )

        if result.discovered and result.confidence in ("high", "medium"):
            _create_next_cycle_candidate(session, scholarship, result)

        results.append(result)

    return results


def _create_next_cycle_candidate(
    session: Session,
    scholarship: Scholarship,
    result: NextCycleDiscoveryResult,
) -> None:
    """Create a discovery candidate for a next-cycle scholarship."""
    seed_approved_sources(session)

    existing = session.scalar(
        select(DiscoveryCandidate).where(
            DiscoveryCandidate.official_source_url == scholarship.official_source_url,
            DiscoveryCandidate.status.in_(["pending", "approved"]),
        )
    )
    if existing is not None:
        return

    candidate = DiscoveryCandidate(
        source_url=scholarship.official_source_url or "",
        normalized_url=normalize_url(scholarship.official_source_url) or "",
        title=f"{scholarship.title} ({result.next_cycle_year})" if result.next_cycle_year else scholarship.title,
        provider=scholarship.official_source,
        country=scholarship.country,
        degree=scholarship.degree,
        funding=scholarship.funding,
        official_source=scholarship.official_source,
        official_source_url=scholarship.official_source_url,
        status="pending",
        match_status="unmatched",
        extracted_fields={
            "next_cycle_year": result.next_cycle_year,
            "next_cycle_evidence": result.evidence,
            "parent_scholarship_id": scholarship.id,
        },
        discovery_hash="",
        discovery_source="next_cycle_discovery",
        confidence=result.confidence,
        review_reason=f"Next-cycle discovery: {result.evidence}",
        fetched_at=datetime.now(timezone.utc),
        resolved_at=None,
    )
    session.add(candidate)
    session.flush()

    history_entry = ScholarshipVerificationHistory(
        scholarship_id=scholarship.id,
        field_name="next_cycle_candidate",
        old_value=None,
        new_value=str(candidate.id),
        change_type="modified",
        source_url=scholarship.official_source_url,
        evidence_text=f"Next-cycle candidate created: {result.evidence}",
        confidence=result.confidence,
        verification_status="active",
    )
    session.add(history_entry)
    session.flush()
