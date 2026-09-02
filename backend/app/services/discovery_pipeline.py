"""Core discovery pipeline for new scholarship candidates."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..database import get_session_factory
from ..models import ApprovedSource, DiscoveryCandidate, Scholarship
from .discovery_config import (
    SourceRegistry,
    StaticSourceRegistry,
    seed_approved_sources,
)
from .discovery_identity import (
    MatchResult,
    compute_discovery_hash,
    normalize_title,
    normalize_url,
    resolve_identity,
)
from .official_source_fetcher import OfficialSourceFetchResult, fetch_official_source
from .scholarship_evidence import (
    EvidenceCollection,
    SourceType,
    classify_source,
    collect_evidence,
)
from .scholarship_extractor import ScholarshipExtractionResult, extract_scholarship_information
from .telemetry import PipelineStages, record_event
from .verification_confidence import VerificationAssessment, assess_confidence

logger = logging.getLogger(__name__)


class DiscoveryError(Exception):
    pass


class SourceNotApprovedError(DiscoveryError):
    pass


@dataclass(frozen=True)
class DiscoveryResult:
    candidate_id: int
    status: str
    match_type: str
    matched_scholarship_id: int | None = None
    confidence: float = 0.0
    review_reason: str | None = None


@dataclass
class DiscoveryBatch:
    source_urls: list[str]
    discovered: list[DiscoveryResult] = field(default_factory=list)
    duplicates: int = 0
    rejected: int = 0
    errors: int = 0


class DiscoveryPipeline:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        registry: SourceRegistry | None = None,
        now_fn=None,
    ) -> None:
        self.session_factory = session_factory or get_session_factory()
        self.registry = registry or StaticSourceRegistry()
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def _new_session(self) -> Session:
        return self.session_factory()

    def discover_from_url(self, source_url: str) -> DiscoveryResult:
        session = self._new_session()
        try:
            discovery_start = time.monotonic()
            result = self._discover_single(session, source_url)
            discovery_duration_ms = (time.monotonic() - discovery_start) * 1000.0
            record_event(
                stage=PipelineStages.DISCOVERY,
                metric_type="success" if result.status not in ("error", "rejected") else "failure",
                duration_ms=discovery_duration_ms,
                source=source_url,
                success=result.status not in ("error", "rejected"),
                metadata={"match_type": result.match_type, "candidate_id": result.candidate_id},
            )
            return result
        finally:
            session.close()

    def discover_batch(self, source_urls: list[str]) -> DiscoveryBatch:
        batch = DiscoveryBatch(source_urls=source_urls)
        session = self._new_session()
        try:
            seed_approved_sources(session)
            session.commit()
        except Exception:
            session.rollback()

        batch_start = time.monotonic()
        for url in source_urls:
            try:
                result = self.discover_from_url(url)
                batch.discovered.append(result)
                if result.match_type in ("exact_url", "exact_candidate", "near_duplicate", "alias"):
                    batch.duplicates += 1
                elif result.status == "rejected":
                    batch.rejected += 1
            except DiscoveryError:
                batch.rejected += 1
            except Exception:
                logger.exception("Discovery failed for %s", url)
                batch.errors += 1

        batch_duration_ms = (time.monotonic() - batch_start) * 1000.0
        record_event(
            stage=PipelineStages.DISCOVERY,
            metric_type="success",
            duration_ms=batch_duration_ms,
            success=True,
            metadata={
                "batch_size": len(source_urls),
                "discovered": len(batch.discovered),
                "duplicates": batch.duplicates,
                "rejected": batch.rejected,
                "errors": batch.errors,
            },
        )

        return batch

    def _discover_single(self, session: Session, source_url: str) -> DiscoveryResult:
        normalized_url = normalize_url(source_url)
        if not normalized_url:
            return self._create_rejected_candidate(session, source_url, "invalid_url", "Invalid or empty source URL")

        if not self.registry.is_approved(normalized_url):
            return self._create_rejected_candidate(
                session, source_url, "source_not_approved",
                f"Source domain not in approved registry: {normalized_url}"
            )

        fetch_result = fetch_official_source(normalized_url)
        if not fetch_result.success:
            return self._create_error_candidate(session, source_url, normalized_url, fetch_result)

        extraction = extract_scholarship_information(fetch_result.content or "", normalized_url)
        title = extraction.scholarship_name
        provider = extraction.provider
        country = _infer_country(session, normalized_url, extraction)

        match = resolve_identity(session, normalized_url, title, provider, country)

        discovery_hash = compute_discovery_hash(normalized_url, title, provider)

        if match.is_match and match.matched_id is not None:
            return self._handle_match(session, source_url, normalized_url, title, provider, country, match, discovery_hash, extraction)

        return self._evaluate_new_candidate(
            session, source_url, normalized_url, title, provider, country,
            discovery_hash, extraction, fetch_result,
        )

    def _handle_match(
        self,
        session: Session,
        source_url: str,
        normalized_url: str,
        title: str | None,
        provider: str | None,
        country: str | None,
        match: MatchResult,
        discovery_hash: str,
        extraction: ScholarshipExtractionResult,
    ) -> DiscoveryResult:
        existing = session.scalar(
            select(DiscoveryCandidate).where(DiscoveryCandidate.discovery_hash == discovery_hash)
        )

        if existing is not None:
            return DiscoveryResult(
                candidate_id=existing.id,
                status=existing.status,
                match_type=match.match_type,
                matched_scholarship_id=match.matched_id,
                confidence=match.confidence,
            )

        candidate = DiscoveryCandidate(
            source_url=source_url,
            normalized_url=normalized_url,
            title=title,
            provider=provider,
            country=country,
            degree=extraction.degree_level,
            funding=None,
            official_source=provider,
            official_source_url=normalized_url,
            status="duplicate",
            match_status="matched",
            matched_scholarship_id=match.matched_id,
            extracted_fields=extraction.model_dump(mode="json"),
            discovery_hash=discovery_hash,
            discovery_source=self.registry.get_source_type(normalized_url) or "unknown",
            confidence="high" if match.confidence >= 0.9 else "medium",
            review_reason=f"Matched via {match.match_type}",
            fetched_at=self.now_fn(),
            resolved_at=self.now_fn(),
        )
        session.add(candidate)
        session.commit()

        return DiscoveryResult(
            candidate_id=candidate.id,
            status="duplicate",
            match_type=match.match_type,
            matched_scholarship_id=match.matched_id,
            confidence=match.confidence,
        )

    def _evaluate_new_candidate(
        self,
        session: Session,
        source_url: str,
        normalized_url: str,
        title: str | None,
        provider: str | None,
        country: str | None,
        discovery_hash: str,
        extraction: ScholarshipExtractionResult,
        fetch_result: OfficialSourceFetchResult,
    ) -> DiscoveryResult:
        existing = session.scalar(
            select(DiscoveryCandidate).where(DiscoveryCandidate.discovery_hash == discovery_hash)
        )
        if existing is not None:
            return DiscoveryResult(
                candidate_id=existing.id,
                status=existing.status,
                match_type="exact_candidate",
                matched_scholarship_id=existing.matched_scholarship_id,
                confidence=1.0,
            )

        evidence = collect_evidence(
            scholarship_id=0,
            source_url=normalized_url,
            source_content=fetch_result.content or "",
            extraction_result=extraction,
            changeset=None,
        )

        source_type = classify_source(normalized_url)
        confidence = assess_confidence(
            scholarship_id=0,
            evidence_items=evidence.items,
        )

        trust_score = self.registry.get_trust_score(normalized_url)

        is_official = source_type in (
            SourceType.OFFICIAL_GOVERNMENT,
            SourceType.OFFICIAL_UNIVERSITY,
            SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            SourceType.OFFICIAL_APPLICATION_PORTAL,
        )

        has_sufficient_evidence = evidence.has_any_evidence and len(evidence.high_confidence_items) >= 2

        overall_confidence = _compute_overall_confidence(confidence)

        review_reason: str | None = None
        status = "pending"

        if not title or len(title.strip()) < 5:
            status = "review"
            review_reason = "Insufficient title information"
        elif not is_official:
            status = "review"
            review_reason = f"Non-official source type: {source_type.value}"
        elif not has_sufficient_evidence:
            status = "review"
            review_reason = "Insufficient evidence for auto-approval"
        elif trust_score < 50:
            status = "review"
            review_reason = f"Low trust score: {trust_score}"
        elif confidence.has_conflicts:
            status = "review"
            review_reason = "Conflicting evidence detected"

        candidate = DiscoveryCandidate(
            source_url=source_url,
            normalized_url=normalized_url,
            title=title,
            provider=provider,
            country=country,
            degree=extraction.degree_level,
            funding=None,
            official_source=provider,
            official_source_url=normalized_url,
            status=status,
            match_status="unmatched",
            extracted_fields=extraction.model_dump(mode="json"),
            discovery_hash=discovery_hash,
            discovery_source=source_type.value,
            confidence=overall_confidence,
            evidence_summary={
                "high_confidence_count": len(evidence.high_confidence_items),
                "low_confidence_count": len(evidence.low_confidence_items),
                "missing_count": len(evidence.missing_items),
                "has_conflicts": confidence.has_conflicts,
            },
            review_reason=review_reason,
            fetched_at=self.now_fn(),
            resolved_at=self.now_fn() if status != "pending" else None,
        )
        session.add(candidate)
        session.commit()

        return DiscoveryResult(
            candidate_id=candidate.id,
            status=status,
            match_type="unmatched",
            confidence=match_confidence(trust_score, evidence),
            review_reason=review_reason,
        )

    def _create_rejected_candidate(
        self, session: Session, source_url: str, reason: str, review_reason: str
    ) -> DiscoveryResult:
        normalized_url = normalize_url(source_url)
        discovery_hash = compute_discovery_hash(normalized_url, None, None)
        existing = session.scalar(
            select(DiscoveryCandidate).where(DiscoveryCandidate.discovery_hash == discovery_hash)
        )
        if existing is not None:
            return DiscoveryResult(
                candidate_id=existing.id,
                status=existing.status,
                match_type="rejected",
                review_reason=review_reason,
            )

        candidate = DiscoveryCandidate(
            source_url=source_url,
            normalized_url=normalized_url or source_url,
            status="rejected",
            match_status="rejected",
            discovery_hash=discovery_hash,
            discovery_source="rejected",
            review_reason=review_reason,
            fetched_at=self.now_fn(),
            resolved_at=self.now_fn(),
        )
        session.add(candidate)
        session.commit()
        return DiscoveryResult(
            candidate_id=candidate.id,
            status="rejected",
            match_type="rejected",
            review_reason=review_reason,
        )

    def _create_error_candidate(
        self, session: Session, source_url: str, normalized_url: str, fetch_result: OfficialSourceFetchResult
    ) -> DiscoveryResult:
        discovery_hash = compute_discovery_hash(normalized_url, None, None)
        candidate = DiscoveryCandidate(
            source_url=source_url,
            normalized_url=normalized_url,
            status="error",
            match_status="error",
            discovery_hash=discovery_hash,
            discovery_source="error",
            last_error=fetch_result.error_type or "unknown",
            review_reason=f"Fetch failed: {fetch_result.error_reason}",
            retry_count=1,
        )
        session.add(candidate)
        session.commit()
        return DiscoveryResult(
            candidate_id=candidate.id,
            status="error",
            match_type="error",
            review_reason=f"Fetch failed: {fetch_result.error_reason}",
        )

    def approve_candidate(self, candidate_id: int) -> int | None:
        session = self._new_session()
        try:
            candidate = session.get(DiscoveryCandidate, candidate_id)
            if candidate is None:
                return None
            if candidate.status not in ("pending", "review"):
                raise DiscoveryError(f"Cannot approve candidate in status: {candidate.status}")

            if candidate.matched_scholarship_id is not None:
                candidate.status = "duplicate"
                candidate.resolved_at = self.now_fn()
                session.commit()
                return None

            scholarship = Scholarship(
                title=candidate.title or "Unknown Scholarship",
                country=candidate.country or "Unknown",
                degree=candidate.degree or "Unknown",
                funding=candidate.funding or "Unknown",
                official_source=candidate.official_source,
                official_source_url=candidate.normalized_url,
                application_link=candidate.normalized_url,
                is_verified=True,
                last_verified_date=self.now_fn(),
                last_verified_at=self.now_fn(),
                verification_status="active",
                region=candidate.extracted_fields.get("region"),
                duration=candidate.extracted_fields.get("duration"),
                deadline_display=candidate.extracted_fields.get("deadline"),
                eligibility=candidate.extracted_fields.get("eligibility", []),
                benefits=candidate.extracted_fields.get("coverage", []),
                requirements=candidate.extracted_fields.get("requirements", []),
                documents=candidate.extracted_fields.get("documents", []),
                application_method=candidate.extracted_fields.get("application_method", []),
            )
            session.add(scholarship)
            session.flush()

            candidate.status = "approved"
            candidate.match_status = "resolved"
            candidate.matched_scholarship_id = scholarship.id
            candidate.resolved_at = self.now_fn()
            session.commit()
            return scholarship.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def reject_candidate(self, candidate_id: int, reason: str) -> bool:
        session = self._new_session()
        try:
            candidate = session.get(DiscoveryCandidate, candidate_id)
            if candidate is None:
                return False
            candidate.status = "rejected"
            candidate.review_reason = reason
            candidate.resolved_at = self.now_fn()
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_pending_candidates(self, limit: int = 50) -> list[DiscoveryCandidate]:
        session = self._new_session()
        try:
            return list(
                session.scalars(
                    select(DiscoveryCandidate)
                    .where(DiscoveryCandidate.status.in_(("pending", "review")))
                    .order_by(DiscoveryCandidate.created_at.asc())
                    .limit(limit)
                ).all()
            )
        finally:
            session.close()

    def get_candidate_by_id(self, candidate_id: int) -> DiscoveryCandidate | None:
        session = self._new_session()
        try:
            return session.get(DiscoveryCandidate, candidate_id)
        finally:
            session.close()


def _compute_overall_confidence(assessment: VerificationAssessment) -> str:
    if assessment.has_conflicts:
        return "conflict"
    if not assessment.field_results:
        return "low"
    verified = len(assessment.verified_fields)
    total = len(assessment.field_results)
    if total == 0:
        return "low"
    ratio = verified / total
    if ratio >= 0.7:
        return "high"
    if ratio >= 0.4:
        return "medium"
    return "low"


def _infer_country(session: Session, normalized_url: str, extraction: ScholarshipExtractionResult) -> str | None:
    url_lower = normalized_url.lower()
    country_hints = {
        "germany": "Germany", "deutschland": "Germany", "daad": "Germany",
        "france": "France", "campusfrance": "France",
        "uk": "United Kingdom", "united kingdom": "United Kingdom", "chevening": "United Kingdom", "gov.uk": "United Kingdom",
        "switzerland": "Switzerland", "swiss": "Switzerland",
        "netherlands": "Netherlands", "nuffic": "Netherlands", "holland": "Netherlands",
        "sweden": "Sweden", "studyinsweden": "Sweden",
        "austria": "Austria", "studyinaustria": "Austria",
        "belgium": "Belgium", "studyinbelgium": "Belgium",
        "usa": "United States", "united states": "United States", "educationusa": "United States", "fulbright": "United States",
        "australia": "Australia", "australia.gov": "Australia",
        "canada": "Canada", "gc.ca": "Canada",
        "japan": "Japan", "studyinjapan": "Japan",
        "korea": "South Korea", "korea.kr": "South Korea",
        "china": "China", "csc.edu": "China",
        "singapore": "Singapore", "moe.gov.sg": "Singapore",
        "india": "India",
        "erasmus": "EU (multiple)",
    }
    for hint, country in country_hints.items():
        if hint in url_lower:
            return country

    rows = session.scalars(select(ApprovedSource)).all()
    for row in rows:
        if row.domain and row.domain in url_lower:
            return row.country

    return None


def match_confidence(trust_score: int, evidence: EvidenceCollection) -> float:
    base = trust_score / 100.0
    evidence_ratio = 0.0
    total_items = len(evidence.items)
    if total_items > 0:
        evidence_ratio = len(evidence.high_confidence_items) / total_items
    if evidence.has_any_evidence and len(evidence.identity_conflict_items) > 0:
        return 0.0
    return min(1.0, (base * 0.5) + (evidence_ratio * 0.5))
