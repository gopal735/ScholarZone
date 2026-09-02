"""Advanced entity resolution and duplicate detection for scholarships.

Provides a staged, explainable resolution pipeline that distinguishes:
- exact duplicate
- renamed/rebranded program
- annual/new cycle
- translated title
- provider migration
- same scholarship with changed URL
- related but distinct program
- genuinely new scholarship

Resolution is deterministic-first, semantic-similarity-last, and always
produces an explainable EntityResolutionResult. It never directly modifies
Scholarship data — it only recommends MATCH / NEW / REVIEW.

Staged pipeline:
1. Exact canonical URL/domain/path
2. Stable provider/program identifiers
3. Normalized title + provider
4. Degree/funding/country metadata
5. Knowledge-graph relationships
6. Historical identity/version evidence
7. Semantic similarity (fallback only)
8. Ambiguous -> REVIEW
9. No reliable match -> NEW
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..models import DiscoveryCandidate, KnowledgeEdge, KnowledgeNode, Scholarship
from .discovery_identity import (
    _containment_score,
    compute_discovery_hash,
    normalize_provider,
    normalize_title,
    normalize_url,
)
from .knowledge_graph import (
    RELATIONSHIP_ALIAS,
    RELATIONSHIP_CYCLE,
    RELATIONSHIP_RELATED,
    STATUS_REVIEW,
    STATUS_VERIFIED,
    find_node,
    get_edges_for_node,
)
from .lifecycle_identity import (
    _normalize_degree,
    _normalize_funding,
    _url_path,
    build_fingerprint,
)
from .source_health_service import extract_domain

if TYPE_CHECKING:
    pass


MATCH_EXACT = "exact_duplicate"
MATCH_URL_MIGRATION = "url_migration"
MATCH_RENAMED = "renamed_program"
MATCH_PROVIDER_RENAME = "provider_rename"
MATCH_ANNUAL_CYCLE = "annual_cycle"
MATCH_TRANSLATED = "translated_title"
MATCH_METADATA = "metadata_only_match"
MATCH_SEMANTIC = "semantic_near_duplicate"
MATCH_RELATED = "related_distinct"
MATCH_NEW = "new_scholarship"
MATCH_REVIEW = "review_ambiguous"

MATCH_TYPES = frozenset({
    MATCH_EXACT, MATCH_URL_MIGRATION, MATCH_RENAMED, MATCH_PROVIDER_RENAME,
    MATCH_ANNUAL_CYCLE, MATCH_TRANSLATED, MATCH_METADATA, MATCH_SEMANTIC,
    MATCH_RELATED, MATCH_NEW, MATCH_REVIEW,
})

REASON_EXACT_URL = "exact_url_match"
REASON_CANONICAL_PATH = "canonical_domain_path_match"
REASON_DISCOVERY_HASH = "discovery_hash_match"
REASON_TITLE_PROVIDER = "title_provider_match"
REASON_METADATA = "metadata_corroboration"
REASON_GRAPH_ALIAS = "knowledge_graph_alias"
REASON_GRAPH_CYCLE = "knowledge_graph_cycle"
REASON_GRAPH_RELATED = "knowledge_graph_related"
REASON_HISTORICAL = "historical_identity_evidence"
REASON_SEMANTIC = "semantic_similarity"
REASON_PROVIDER_MIGRATION = "provider_url_migration"
REASON_TRANSLATED = "translated_title_match"
REASON_AMBIGUOUS = "ambiguous_signals"
REASON_NO_MATCH = "no_match_found"

REASON_CODES = frozenset({
    REASON_EXACT_URL, REASON_CANONICAL_PATH, REASON_DISCOVERY_HASH,
    REASON_TITLE_PROVIDER, REASON_METADATA, REASON_GRAPH_ALIAS,
    REASON_GRAPH_CYCLE, REASON_GRAPH_RELATED, REASON_HISTORICAL,
    REASON_SEMANTIC, REASON_PROVIDER_MIGRATION, REASON_TRANSLATED,
    REASON_AMBIGUOUS, REASON_NO_MATCH,
})


@dataclass(frozen=True)
class EntityResolutionResult:
    match_type: str
    matched_scholarship_id: int | None = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    ambiguity: bool = False
    related_ids: list[int] = field(default_factory=list)
    cycle_status: str = "same_cycle"
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _IdentitySignal:
    normalized_url: str
    normalized_title: str
    normalized_provider: str
    normalized_degree: str
    normalized_funding: str
    domain: str
    url_path: str
    discovery_hash: str
    title_length: int
    provider_length: int


def _build_signal(
    source_url: str | None,
    title: str | None,
    provider: str | None,
    degree: str | None = None,
    funding: str | None = None,
) -> _IdentitySignal:
    norm_url = normalize_url(source_url or "")
    norm_title = normalize_title(title)
    norm_provider = normalize_provider(provider)
    norm_degree = _normalize_degree(degree)
    norm_funding = _normalize_funding(funding)
    domain = extract_domain(source_url) or ""
    path = _url_path(source_url)
    dh = compute_discovery_hash(source_url or "", title, provider)
    return _IdentitySignal(
        normalized_url=norm_url,
        normalized_title=norm_title,
        normalized_provider=norm_provider,
        normalized_degree=norm_degree,
        normalized_funding=norm_funding,
        domain=domain,
        url_path=path,
        discovery_hash=dh,
        title_length=len(norm_title),
        provider_length=len(norm_provider),
    )


def _build_signal_for_scholarship(s: Scholarship) -> _IdentitySignal:
    return _build_signal(
        source_url=s.official_source_url or s.application_link,
        title=s.title,
        provider=s.official_source,
        degree=s.degree,
        funding=s.funding,
    )


def _url_variants(url: str) -> list[str]:
    if not url:
        return []
    variants = [url]
    if not url.endswith("/"):
        variants.append(f"{url}/")
    else:
        variants.append(url.rstrip("/"))
    return variants


def _check_exact_url_match(
    session: Session,
    signal: _IdentitySignal,
    source_url: str,
) -> tuple[int, float, str] | None:
    if not signal.normalized_url:
        return None
    variants = _url_variants(signal.normalized_url)
    existing = session.scalar(
        select(Scholarship).where(
            or_(
                func.lower(Scholarship.official_source_url).in_(variants),
                func.lower(Scholarship.application_link).in_(variants),
                func.lower(Scholarship.catalogue_url).in_(variants),
                func.lower(Scholarship.official_updates_url).in_(variants),
            )
        )
    )
    if existing is not None:
        return (existing.id, 1.0, REASON_EXACT_URL)
    return None


def _check_canonical_path_match(
    session: Session,
    signal: _IdentitySignal,
) -> tuple[int, float, str] | None:
    if not signal.domain or not signal.url_path:
        return None
    candidates = session.scalars(
        select(Scholarship).where(
            or_(
                func.lower(Scholarship.official_source_url).like(f"%{signal.domain}%"),
                func.lower(Scholarship.catalogue_url).like(f"%{signal.domain}%"),
                func.lower(Scholarship.application_link).like(f"%{signal.domain}%"),
            )
        )
    ).all()
    for s in candidates:
        s_domain = extract_domain(s.official_source_url) or extract_domain(s.catalogue_url) or ""
        if s_domain == signal.domain:
            s_path = _url_path(s.official_source_url) or _url_path(s.catalogue_url) or ""
            if s_path == signal.url_path:
                return (s.id, 0.95, REASON_CANONICAL_PATH)
    return None


def _check_discovery_hash_match(
    session: Session,
    signal: _IdentitySignal,
) -> tuple[int, float, str] | None:
    if not signal.discovery_hash:
        return None
    candidate = session.scalar(
        select(DiscoveryCandidate).where(
            DiscoveryCandidate.discovery_hash == signal.discovery_hash,
            DiscoveryCandidate.status.in_(["pending", "approved", "duplicate"]),
        )
    )
    if candidate is not None and candidate.matched_scholarship_id is not None:
        return (candidate.matched_scholarship_id, 1.0, REASON_DISCOVERY_HASH)
    existing = session.scalar(
        select(Scholarship).where(
            Scholarship.official_source_url == signal.normalized_url
        )
    )
    if existing is not None:
        return (existing.id, 1.0, REASON_DISCOVERY_HASH)
    return None


def _check_title_provider_match(
    session: Session,
    signal: _IdentitySignal,
    country: str | None,
) -> tuple[int, float, str, list[str]] | None:
    if signal.title_length < 6:
        return None
    candidates = session.scalars(
        select(Scholarship).where(
            Scholarship.country == country if country else Scholarship.country.is_(None)
        )
    ).all()
    best_id: int | None = None
    best_score: float = 0.0
    best_evidence: list[str] = []
    for s in candidates:
        s_title = normalize_title(s.title)
        if not s_title:
            continue
        title_containment = _containment_score(signal.normalized_title, s_title)
        provider_match = False
        if signal.provider_length > 4:
            s_provider = normalize_provider(s.official_source)
            if s_provider:
                provider_match = (
                    signal.normalized_provider == s_provider
                    or _containment_score(signal.normalized_provider, s_provider) >= 0.9
                )
        if s_title == signal.normalized_title and provider_match:
            return (s.id, 0.92, REASON_TITLE_PROVIDER, ["exact_normalized_title_match", "provider_match"])
        if title_containment >= 0.85 and provider_match:
            if title_containment > best_score:
                best_score = title_containment
                best_id = s.id
                best_evidence = [f"title_containment={title_containment:.2f}", "provider_match"]
        if signal.provider_length > 4:
            s_provider = normalize_provider(s.official_source)
            if s_provider:
                if provider_match and title_containment >= 0.5:
                    combined_score = 0.7 + (title_containment * 0.2)
                    if combined_score > best_score:
                        best_score = combined_score
                        best_id = s.id
                        best_evidence = [
                            "provider_match",
                            f"title_overlap={title_containment:.2f}",
                        ]
    if best_id is not None and best_score >= 0.7:
        return (best_id, min(best_score, 0.92), REASON_TITLE_PROVIDER, best_evidence)
    return None


def _check_metadata_match(
    session: Session,
    signal: _IdentitySignal,
    country: str | None,
    degree: str | None,
    funding: str | None,
) -> tuple[int, float, str, list[str]] | None:
    if not country:
        return None
    candidates = session.scalars(
        select(Scholarship).where(Scholarship.country == country)
    ).all()
    best_id: int | None = None
    best_score: float = 0.0
    best_evidence: list[str] = []
    for s in candidates:
        s_signal = _build_signal_for_scholarship(s)
        matches: list[str] = []
        score = 0.0
        if signal.normalized_degree and s_signal.normalized_degree:
            if signal.normalized_degree == s_signal.normalized_degree:
                matches.append("degree")
                score += 0.2
        if signal.normalized_funding and s_signal.normalized_funding:
            if signal.normalized_funding == s_signal.normalized_funding:
                matches.append("funding")
                score += 0.15
        if signal.domain and s_signal.domain and signal.domain == s_signal.domain:
            matches.append("domain")
            score += 0.2
        if signal.title_length >= 6 and s_signal.title_length >= 6:
            title_sim = _containment_score(signal.normalized_title, s_signal.normalized_title)
            if title_sim >= 0.6:
                matches.append(f"title_sim={title_sim:.2f}")
                score += title_sim * 0.3
        if signal.provider_length > 4 and s_signal.provider_length > 4:
            prov_sim = _containment_score(signal.normalized_provider, s_signal.normalized_provider)
            if prov_sim >= 0.8:
                matches.append(f"provider_sim={prov_sim:.2f}")
                score += prov_sim * 0.15
        if len(matches) >= 3 and score > best_score:
            best_score = score
            best_id = s.id
            best_evidence = matches
    if best_id is not None and best_score >= 0.6:
        return (best_id, min(best_score, 0.85), REASON_METADATA, best_evidence)
    return None


def _check_graph_relationships(
    session: Session,
    signal: _IdentitySignal,
) -> tuple[int, float, str, list[str]] | None:
    if not signal.domain:
        return None
    candidates = session.scalars(
        select(Scholarship).where(
            or_(
                func.lower(Scholarship.official_source_url).like(f"%{signal.domain}%"),
                func.lower(Scholarship.catalogue_url).like(f"%{signal.domain}%"),
            )
        )
    ).all()
    for s in candidates:
        s_node = find_node(session, "scholarship", str(s.id))
        if s_node is None:
            continue
        edges = get_edges_for_node(session, s_node.id, direction="both")
        for edge in edges:
            if edge.status == STATUS_REVIEW:
                continue
            if edge.relation_type == RELATIONSHIP_ALIAS and edge.status == STATUS_VERIFIED:
                return (s.id, edge.confidence, REASON_GRAPH_ALIAS, [f"alias_edge_confidence={edge.confidence:.2f}"])
            if edge.relation_type == RELATIONSHIP_CYCLE and edge.status == STATUS_VERIFIED:
                return (s.id, 0.9, REASON_GRAPH_CYCLE, [f"cycle_edge"])
            if edge.relation_type == RELATIONSHIP_RELATED and edge.status == STATUS_VERIFIED:
                if edge.confidence >= 0.7:
                    return (s.id, edge.confidence * 0.8, REASON_GRAPH_RELATED, [f"related_edge_confidence={edge.confidence:.2f}"])
    return None


def _check_historical_identity(
    session: Session,
    signal: _IdentitySignal,
    country: str | None,
) -> tuple[int, float, str, list[str]] | None:
    if signal.title_length < 8:
        return None
    from .temporal_versioning import get_version_history
    candidates = session.scalars(
        select(Scholarship).where(
            Scholarship.country == country if country else Scholarship.country.is_(None)
        )
    ).all()
    for s in candidates:
        s_title = normalize_title(s.title)
        if not s_title:
            continue
        title_sim = _containment_score(signal.normalized_title, s_title)
        if title_sim < 0.7:
            continue
        try:
            history = get_version_history(session, s.id, limit=5)
        except Exception:
            history = []
        if history and title_sim >= 0.7:
            return (
                s.id,
                min(0.75, title_sim * 0.8),
                REASON_HISTORICAL,
                [f"historical_title_sim={title_sim:.2f}", f"versions={len(history)}"],
            )
    return None


def _compute_semantic_similarity(
    signal: _IdentitySignal,
    s: Scholarship,
) -> float:
    s_signal = _build_signal_for_scholarship(s)
    if signal.title_length < 6 or s_signal.title_length < 6:
        return 0.0
    title_sim = _containment_score(signal.normalized_title, s_signal.normalized_title)
    provider_sim = 0.0
    if signal.provider_length > 4 and s_signal.provider_length > 4:
        provider_sim = _containment_score(signal.normalized_provider, s_signal.normalized_provider)
    domain_match = 1.0 if (signal.domain and s_signal.domain and signal.domain == s_signal.domain) else 0.0
    degree_match = 1.0 if (signal.normalized_degree and s_signal.normalized_degree and signal.normalized_degree == s_signal.normalized_degree) else 0.0
    funding_match = 1.0 if (signal.normalized_funding and s_signal.normalized_funding and signal.normalized_funding == s_signal.normalized_funding) else 0.0
    weighted = (
        title_sim * 0.45 +
        provider_sim * 0.25 +
        domain_match * 0.15 +
        degree_match * 0.10 +
        funding_match * 0.05
    )
    return weighted


def _check_semantic_similarity(
    session: Session,
    signal: _IdentitySignal,
    country: str | None,
) -> tuple[int, float, str, list[str]] | None:
    if signal.title_length < 8:
        return None
    candidates = session.scalars(
        select(Scholarship).where(
            Scholarship.country == country if country else Scholarship.country.is_(None)
        )
    ).all()
    best_id: int | None = None
    best_score: float = 0.0
    for s in candidates:
        score = _compute_semantic_similarity(signal, s)
        if score > best_score:
            best_score = score
            best_id = s.id
    if best_id is not None and best_score >= 0.8:
        return (best_id, best_score, REASON_SEMANTIC, [f"semantic_score={best_score:.2f}"])
    if best_id is not None and best_score >= 0.65:
        return (best_id, best_score, REASON_AMBIGUOUS, [f"semantic_score={best_score:.2f}"])
    return None


def _detect_cycle_status(
    session: Session,
    matched_id: int,
    title: str | None,
) -> str:
    import re
    existing = session.get(Scholarship, matched_id)
    if existing is None:
        return "same_cycle"
    _YEAR_RE = re.compile(r"\b(20\d{2})\b")
    new_years = [int(m) for m in _YEAR_RE.findall(title or "")]
    existing_years = [int(m) for m in _YEAR_RE.findall(existing.title or "")]
    if new_years and existing_years:
        if max(new_years) > max(existing_years):
            return "new_cycle"
        if min(new_years) > min(existing_years):
            return "new_cycle"
    norm_new = normalize_title(title)
    norm_existing = normalize_title(existing.title)
    if norm_new and norm_existing and norm_new != norm_existing:
        sim = _containment_score(norm_new, norm_existing)
        if sim >= 0.6:
            return "renamed"
        return "distinct"
    return "same_cycle"


def resolve_entity(
    session: Session,
    source_url: str | None,
    title: str | None,
    provider: str | None,
    country: str | None = None,
    degree: str | None = None,
    funding: str | None = None,
) -> EntityResolutionResult:
    signal = _build_signal(source_url, title, provider, degree, funding)
    url_to_check = source_url or ""
    result = _check_exact_url_match(session, signal, url_to_check)
    if result is not None:
        matched_id, confidence, reason = result
        cycle = _detect_cycle_status(session, matched_id, title)
        return EntityResolutionResult(
            match_type=MATCH_EXACT,
            matched_scholarship_id=matched_id,
            confidence=confidence,
            evidence=[f"exact_url_match"],
            reason_codes=[reason],
            cycle_status=cycle,
        )
    result = _check_canonical_path_match(session, signal)
    if result is not None:
        matched_id, confidence, reason = result
        cycle = _detect_cycle_status(session, matched_id, title)
        return EntityResolutionResult(
            match_type=MATCH_URL_MIGRATION if cycle != "same_cycle" else MATCH_EXACT,
            matched_scholarship_id=matched_id,
            confidence=confidence,
            evidence=[f"domain={signal.domain}", f"path={signal.url_path}"],
            reason_codes=[reason],
            cycle_status=cycle,
        )
    result = _check_discovery_hash_match(session, signal)
    if result is not None:
        matched_id, confidence, reason = result
        cycle = _detect_cycle_status(session, matched_id, title)
        return EntityResolutionResult(
            match_type=MATCH_EXACT,
            matched_scholarship_id=matched_id,
            confidence=confidence,
            evidence=["discovery_hash_match"],
            reason_codes=[reason],
            cycle_status=cycle,
        )
    tp_result = _check_title_provider_match(session, signal, country)
    if tp_result is not None:
        matched_id, confidence, reason, evidence = tp_result
        cycle = _detect_cycle_status(session, matched_id, title)
        if cycle == "new_cycle":
            match_type = MATCH_ANNUAL_CYCLE
        elif cycle == "renamed":
            match_type = MATCH_RENAMED
        else:
            match_type = MATCH_EXACT if confidence >= 0.9 else MATCH_REVIEW
        return EntityResolutionResult(
            match_type=match_type,
            matched_scholarship_id=matched_id if match_type != MATCH_REVIEW else None,
            confidence=confidence,
            evidence=evidence,
            reason_codes=[reason],
            ambiguity=(match_type == MATCH_REVIEW),
            cycle_status=cycle,
        )
    meta_result = _check_metadata_match(session, signal, country, degree, funding)
    if meta_result is not None:
        matched_id, confidence, reason, evidence = meta_result
        cycle = _detect_cycle_status(session, matched_id, title)
        return EntityResolutionResult(
            match_type=MATCH_METADATA,
            matched_scholarship_id=matched_id,
            confidence=confidence,
            evidence=evidence,
            reason_codes=[reason],
            cycle_status=cycle,
            notes=["metadata_corroboration_match"],
        )
    graph_result = _check_graph_relationships(session, signal)
    if graph_result is not None:
        matched_id, confidence, reason, evidence = graph_result
        cycle = _detect_cycle_status(session, matched_id, title)
        if reason == REASON_GRAPH_ALIAS:
            match_type = MATCH_RENAMED
        elif reason == REASON_GRAPH_CYCLE:
            match_type = MATCH_ANNUAL_CYCLE
        else:
            match_type = MATCH_RELATED
        return EntityResolutionResult(
            match_type=match_type,
            matched_scholarship_id=matched_id if match_type != MATCH_RELATED else None,
            confidence=confidence,
            evidence=evidence,
            reason_codes=[reason],
            related_ids=[matched_id] if match_type == MATCH_RELATED else [],
            cycle_status=cycle,
        )
    hist_result = _check_historical_identity(session, signal, country)
    if hist_result is not None:
        matched_id, confidence, reason, evidence = hist_result
        cycle = _detect_cycle_status(session, matched_id, title)
        return EntityResolutionResult(
            match_type=MATCH_REVIEW,
            matched_scholarship_id=None,
            confidence=confidence,
            evidence=evidence,
            reason_codes=[reason],
            ambiguity=True,
            related_ids=[matched_id],
            cycle_status=cycle,
            notes=["historical_evidence_requires_review"],
        )
    semantic_result = _check_semantic_similarity(session, signal, country)
    if semantic_result is not None:
        matched_id, confidence, reason, evidence = semantic_result
        if reason == REASON_AMBIGUOUS:
            return EntityResolutionResult(
                match_type=MATCH_REVIEW,
                matched_scholarship_id=None,
                confidence=confidence,
                evidence=evidence,
                reason_codes=[reason],
                ambiguity=True,
                related_ids=[matched_id],
                notes=["semantic_ambiguity_requires_review"],
            )
        cycle = _detect_cycle_status(session, matched_id, title)
        return EntityResolutionResult(
            match_type=MATCH_SEMANTIC,
            matched_scholarship_id=matched_id,
            confidence=confidence,
            evidence=evidence,
            reason_codes=[reason],
            cycle_status=cycle,
        )
    return EntityResolutionResult(
        match_type=MATCH_NEW,
        matched_scholarship_id=None,
        confidence=0.0,
        evidence=[],
        reason_codes=[REASON_NO_MATCH],
        notes=["no_matching_entity_found"],
    )


def resolve_entity_batch(
    session: Session,
    candidates: list[dict],
) -> list[EntityResolutionResult]:
    return [
        resolve_entity(
            session=session,
            source_url=c.get("source_url"),
            title=c.get("title"),
            provider=c.get("provider"),
            country=c.get("country"),
            degree=c.get("degree"),
            funding=c.get("funding"),
        )
        for c in candidates
    ]


def is_ambiguous(result: EntityResolutionResult) -> bool:
    return result.ambiguity


def is_match(result: EntityResolutionResult) -> bool:
    return result.matched_scholarship_id is not None and not result.ambiguity


def is_new(result: EntityResolutionResult) -> bool:
    return result.match_type == MATCH_NEW


def is_review(result: EntityResolutionResult) -> bool:
    return result.match_type == MATCH_REVIEW or result.ambiguity


def get_match_type(result: EntityResolutionResult) -> str:
    return result.match_type
