"""Scholarship knowledge graph and relationship intelligence.

Builds a lightweight relational knowledge graph using existing DB infrastructure.
No heavy graph database required - uses SQLAlchemy models with normalized
entity nodes and typed edges.

Core entities/relations:
- scholarship -> provider
- scholarship -> country/region
- scholarship -> degree
- scholarship -> funding
- scholarship -> official source
- scholarship -> cycle/version
- scholarship -> alias/renamed identity
- scholarship -> related scholarship

Deterministic, no network calls, no AI/LLM required.
All metrics derived from existing persisted data.

Idempotent updates: duplicate edges are prevented by unique constraint.
Historical relationships remain auditable via created_at/updated_at.
Ambiguous relationships are flagged for REVIEW.
Provenance is attached to externally verified relationships.
Batch-friendly reads/writes. No N+1 queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models import KnowledgeEdge, KnowledgeNode, Scholarship
from .discovery_identity import normalize_provider, normalize_title, normalize_url
from .lifecycle_identity import (
    CYCLE_DISTINCT,
    CYCLE_NEW,
    CYCLE_RENAMED,
    CYCLE_SAME,
    IdentityResolution,
    _normalize_degree,
    _normalize_funding,
    _url_path,
    build_fingerprint,
    classify_lifecycle_state,
)
from .source_health_service import extract_domain

ENTITY_SCHOLARSHIP = "scholarship"
ENTITY_PROVIDER = "provider"
ENTITY_COUNTRY = "country"
ENTITY_DEGREE = "degree"
ENTITY_FUNDING = "funding"
ENTITY_SOURCE = "source"
ENTITY_UNIVERSITY = "university"
ENTITY_CYCLE = "cycle"
ENTITY_ALIAS = "alias"

RELATIONSHIP_PROVIDER = "scholarship_provider"
RELATIONSHIP_COUNTRY = "scholarship_country"
RELATIONSHIP_DEGREE = "scholarship_degree"
RELATIONSHIP_FUNDING = "scholarship_funding"
RELATIONSHIP_SOURCE = "scholarship_source"
RELATIONSHIP_UNIVERSITY = "scholarship_university"
RELATIONSHIP_CYCLE = "scholarship_cycle"
RELATIONSHIP_ALIAS = "scholarship_alias"
RELATIONSHIP_RELATED = "scholarship_related"
RELATIONSHIP_PREREQUISITE = "scholarship_prerequisite"

NODE_ENTITY_TYPES = frozenset({
    ENTITY_SCHOLARSHIP, ENTITY_PROVIDER, ENTITY_COUNTRY, ENTITY_DEGREE,
    ENTITY_FUNDING, ENTITY_SOURCE, ENTITY_UNIVERSITY, ENTITY_CYCLE, ENTITY_ALIAS,
})

RELATION_TYPES = frozenset({
    RELATIONSHIP_PROVIDER, RELATIONSHIP_COUNTRY, RELATIONSHIP_DEGREE,
    RELATIONSHIP_FUNDING, RELATIONSHIP_SOURCE, RELATIONSHIP_UNIVERSITY,
    RELATIONSHIP_CYCLE, RELATIONSHIP_ALIAS, RELATIONSHIP_RELATED,
    RELATIONSHIP_PREREQUISITE,
})

STATUS_VERIFIED = "verified"
STATUS_INFERRED = "inferred"
STATUS_REVIEW = "review"

EDGE_STATUSES = frozenset({STATUS_VERIFIED, STATUS_INFERRED, STATUS_REVIEW})


@dataclass(frozen=True)
class NodeRef:
    id: int
    entity_type: str
    normalized_value: str
    display_name: str | None


@dataclass(frozen=True)
class EdgeRef:
    id: int
    source_node_id: int
    target_node_id: int
    relation_type: str
    confidence: float
    status: str
    provenance: dict


@dataclass(frozen=True)
class GraphPath:
    nodes: list[NodeRef]
    edges: list[EdgeRef]
    path_type: str
    confidence: float


@dataclass
class RelationshipResult:
    edge_id: int | None
    created: bool
    status: str
    confidence: float
    message: str


@dataclass(frozen=True)
class AliasInfo:
    scholarship_id: int
    alias_title: str
    original_title: str
    similarity: float
    is_rename: bool


@dataclass(frozen=True)
class CycleInfo:
    scholarship_id: int
    cycle_year: int | None
    previous_cycle_id: int | None
    cycle_status: str
    normalized_value: str


@dataclass
class GraphStats:
    total_nodes: int
    total_edges: int
    nodes_by_type: dict[str, int] = field(default_factory=dict)
    edges_by_relation: dict[str, int] = field(default_factory=dict)
    edges_by_status: dict[str, int] = field(default_factory=dict)


def func_lower_like(column, value: str):
    from sqlalchemy import func
    return func.lower(column).like(f"%{value}%")


def _normalize_entity_value(entity_type: str, value: str | None) -> str:
    if not value:
        return ""
    v = value.strip()
    if not v:
        return ""
    if entity_type == ENTITY_COUNTRY:
        return v.lower()
    if entity_type == ENTITY_DEGREE:
        return _normalize_degree(v)
    if entity_type == ENTITY_FUNDING:
        return _normalize_funding(v)
    if entity_type == ENTITY_PROVIDER:
        return normalize_provider(v)
    if entity_type == ENTITY_SOURCE:
        return extract_domain(v) or v.lower()
    if entity_type == ENTITY_UNIVERSITY:
        return normalize_provider(v)
    if entity_type == ENTITY_CYCLE:
        return v.lower()
    if entity_type == ENTITY_ALIAS:
        return normalize_title(v)
    if entity_type == ENTITY_SCHOLARSHIP:
        return f"scholarship:{v}"
    return v.lower()


def get_or_create_node(
    session: Session,
    entity_type: str,
    value: str,
    display_name: str | None = None,
    metadata: dict | None = None,
) -> tuple[KnowledgeNode, bool]:
    """Get existing node or create new one. Idempotent."""
    if entity_type not in NODE_ENTITY_TYPES:
        raise ValueError(f"Unknown entity type: {entity_type}")

    normalized = _normalize_entity_value(entity_type, value)
    if not normalized:
        raise ValueError(f"Cannot normalize value for {entity_type}: {value!r}")

    existing = session.scalar(
        select(KnowledgeNode).where(
            and_(
                KnowledgeNode.entity_type == entity_type,
                KnowledgeNode.normalized_value == normalized,
            )
        )
    )

    if existing is not None:
        if display_name and not existing.display_name:
            existing.display_name = display_name
        if metadata:
            merged = dict(existing.metadata_json or {})
            merged.update(metadata)
            existing.metadata_json = merged
        return existing, False

    node = KnowledgeNode(
        entity_type=entity_type,
        normalized_value=normalized,
        display_name=display_name or value,
        metadata_json=metadata or {},
    )
    session.add(node)
    session.flush()
    return node, True


def get_node_by_id(session: Session, node_id: int) -> KnowledgeNode | None:
    return session.get(KnowledgeNode, node_id)


def find_node(
    session: Session,
    entity_type: str,
    value: str,
) -> KnowledgeNode | None:
    normalized = _normalize_entity_value(entity_type, value)
    if not normalized:
        return None
    return session.scalar(
        select(KnowledgeNode).where(
            and_(
                KnowledgeNode.entity_type == entity_type,
                KnowledgeNode.normalized_value == normalized,
            )
        )
    )


def create_edge(
    session: Session,
    source_node_id: int,
    target_node_id: int,
    relation_type: str,
    confidence: float = 1.0,
    status: str = STATUS_VERIFIED,
    provenance: dict | None = None,
) -> tuple[KnowledgeEdge, bool]:
    """Create edge if it doesn't exist. Idempotent."""
    if relation_type not in RELATION_TYPES:
        raise ValueError(f"Unknown relation type: {relation_type}")

    if status not in EDGE_STATUSES:
        raise ValueError(f"Unknown edge status: {status}")

    existing = session.scalar(
        select(KnowledgeEdge).where(
            and_(
                KnowledgeEdge.source_node_id == source_node_id,
                KnowledgeEdge.target_node_id == target_node_id,
                KnowledgeEdge.relation_type == relation_type,
            )
        )
    )

    if existing is not None:
        if existing.status != status:
            existing.status = status
        if confidence > existing.confidence:
            existing.confidence = confidence
        if provenance:
            merged = dict(existing.provenance or {})
            merged.update(provenance)
            existing.provenance = merged
        return existing, False

    edge = KnowledgeEdge(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relation_type=relation_type,
        confidence=confidence,
        status=status,
        provenance=provenance or {},
    )
    session.add(edge)
    session.flush()
    return edge, True


def get_edges_for_node(
    session: Session,
    node_id: int,
    direction: str = "both",
    relation_type: str | None = None,
) -> list[KnowledgeEdge]:
    """Get edges for a node. No N+1 - single query."""
    conditions = []
    if direction in ("outgoing", "both"):
        conditions.append(KnowledgeEdge.source_node_id == node_id)
    if direction in ("incoming", "both"):
        conditions.append(KnowledgeEdge.target_node_id == node_id)

    query = select(KnowledgeEdge).where(or_(*conditions))

    if relation_type:
        query = query.where(KnowledgeEdge.relation_type == relation_type)

    return list(session.scalars(query).all())


def get_related_scholarships_via_graph(
    session: Session,
    scholarship_id: int,
    max_depth: int = 2,
) -> list[tuple[int, str, float]]:
    """Find related scholarships via graph traversal."""
    source_node = find_node(session, ENTITY_SCHOLARSHIP, str(scholarship_id))
    if source_node is None:
        return []

    visited: dict[int, tuple[int, str, float]] = {}
    frontier = [(source_node.id, 0, 1.0)]

    while frontier:
        current_id, depth, path_confidence = frontier.pop(0)
        if depth >= max_depth:
            continue

        edges = get_edges_for_node(session, current_id, direction="both")

        for edge in edges:
            if edge.status == STATUS_REVIEW:
                continue

            neighbor_id = (
                edge.target_node_id
                if edge.source_node_id == current_id
                else edge.source_node_id
            )

            neighbor_node = get_node_by_id(session, neighbor_id)
            if neighbor_node is None:
                continue

            new_confidence = path_confidence * edge.confidence

            if neighbor_node.entity_type == ENTITY_SCHOLARSHIP:
                sid = int(neighbor_node.normalized_value.split(":")[-1])
                if sid != scholarship_id and sid not in visited:
                    relation = edge.relation_type
                    visited[sid] = (sid, relation, new_confidence)
            else:
                if depth + 1 < max_depth:
                    frontier.append((neighbor_id, depth + 1, new_confidence))

    return list(visited.values())


def build_scholarship_graph(
    session: Session,
    scholarship: Scholarship,
    provenance: dict | None = None,
) -> dict[str, int]:
    """Build graph nodes and edges for a scholarship. Idempotent."""
    created_nodes: dict[str, int] = {}

    sch_node, _ = get_or_create_node(
        session,
        ENTITY_SCHOLARSHIP,
        str(scholarship.id),
        display_name=scholarship.title,
        metadata={"scholarship_id": scholarship.id, "title": scholarship.title},
    )
    created_nodes["scholarship"] = sch_node.id

    if scholarship.official_source:
        prov_node, _ = get_or_create_node(
            session,
            ENTITY_PROVIDER,
            scholarship.official_source,
            display_name=scholarship.official_source,
        )
        created_nodes["provider"] = prov_node.id
        create_edge(
            session,
            sch_node.id,
            prov_node.id,
            RELATIONSHIP_PROVIDER,
            confidence=1.0,
            status=STATUS_VERIFIED,
            provenance=provenance,
        )

    if scholarship.country:
        country_node, _ = get_or_create_node(
            session,
            ENTITY_COUNTRY,
            scholarship.country,
            display_name=scholarship.country,
        )
        created_nodes["country"] = country_node.id
        create_edge(
            session,
            sch_node.id,
            country_node.id,
            RELATIONSHIP_COUNTRY,
            confidence=1.0,
            status=STATUS_VERIFIED,
            provenance=provenance,
        )

    if scholarship.degree:
        degree_node, _ = get_or_create_node(
            session,
            ENTITY_DEGREE,
            scholarship.degree,
            display_name=scholarship.degree,
        )
        created_nodes["degree"] = degree_node.id
        create_edge(
            session,
            sch_node.id,
            degree_node.id,
            RELATIONSHIP_DEGREE,
            confidence=1.0,
            status=STATUS_VERIFIED,
            provenance=provenance,
        )

    if scholarship.funding:
        funding_node, _ = get_or_create_node(
            session,
            ENTITY_FUNDING,
            scholarship.funding,
            display_name=scholarship.funding,
        )
        created_nodes["funding"] = funding_node.id
        create_edge(
            session,
            sch_node.id,
            funding_node.id,
            RELATIONSHIP_FUNDING,
            confidence=1.0,
            status=STATUS_VERIFIED,
            provenance=provenance,
        )

    if scholarship.official_source_url:
        source_node, _ = get_or_create_node(
            session,
            ENTITY_SOURCE,
            scholarship.official_source_url,
            display_name=extract_domain(scholarship.official_source_url),
            metadata={"url": scholarship.official_source_url},
        )
        created_nodes["source"] = source_node.id
        create_edge(
            session,
            sch_node.id,
            source_node.id,
            RELATIONSHIP_SOURCE,
            confidence=1.0,
            status=STATUS_VERIFIED,
            provenance=provenance,
        )

    return created_nodes


def detect_alias_relationship(
    session: Session,
    scholarship: Scholarship,
    candidate_title: str,
) -> RelationshipResult:
    """Detect if candidate_title is an alias/rename of existing scholarship."""
    norm_candidate = normalize_title(candidate_title)
    norm_existing = normalize_title(scholarship.title)

    if not norm_candidate or not norm_existing:
        return RelationshipResult(
            edge_id=None,
            created=False,
            status=STATUS_REVIEW,
            confidence=0.0,
            message="cannot_normalize_titles",
        )

    if norm_candidate == norm_existing:
        return RelationshipResult(
            edge_id=None,
            created=False,
            status=STATUS_VERIFIED,
            confidence=1.0,
            message="identical_titles",
        )

    from .discovery_identity import _containment_score
    similarity = _containment_score(norm_candidate, norm_existing)

    if similarity < 0.5:
        return RelationshipResult(
            edge_id=None,
            created=False,
            status=STATUS_REVIEW,
            confidence=similarity,
            message=f"low_similarity:{similarity:.2f}",
        )

    source_node, _ = get_or_create_node(
        session,
        ENTITY_SCHOLARSHIP,
        str(scholarship.id),
        display_name=scholarship.title,
    )

    alias_value = f"alias:{scholarship.id}:{norm_candidate}"
    alias_node, _ = get_or_create_node(
        session,
        ENTITY_ALIAS,
        alias_value,
        display_name=candidate_title,
        metadata={"original_scholarship_id": scholarship.id, "similarity": similarity},
    )

    is_rename = similarity >= 0.6
    status = STATUS_VERIFIED if is_rename else STATUS_REVIEW

    edge, created = create_edge(
        session,
        source_node.id,
        alias_node.id,
        RELATIONSHIP_ALIAS,
        confidence=similarity,
        status=status,
        provenance={"similarity": similarity, "is_rename": is_rename},
    )

    return RelationshipResult(
        edge_id=edge.id,
        created=created,
        status=status,
        confidence=similarity,
        message=f"alias_detected:similarity={similarity:.2f}",
    )


def detect_cycle_relationship(
    session: Session,
    scholarship: Scholarship,
    previous_scholarship: Scholarship | None = None,
) -> RelationshipResult:
    """Detect cycle/version relationship between scholarships."""
    fp_current = build_fingerprint(
        title=scholarship.title,
        provider=scholarship.official_source,
        official_source_url=scholarship.official_source_url,
        degree=scholarship.degree,
        funding=scholarship.funding,
        country=scholarship.country,
    )

    current_year = fp_current.year_hint

    if previous_scholarship is None:
        return RelationshipResult(
            edge_id=None,
            created=False,
            status=STATUS_VERIFIED,
            confidence=1.0,
            message="no_previous_cycle",
        )

    fp_previous = build_fingerprint(
        title=previous_scholarship.title,
        provider=previous_scholarship.official_source,
        official_source_url=previous_scholarship.official_source_url,
        degree=previous_scholarship.degree,
        funding=previous_scholarship.funding,
        country=previous_scholarship.country,
    )

    previous_year = fp_previous.year_hint

    if fp_current.domain and fp_previous.domain and fp_current.domain == fp_previous.domain:
        if fp_current.url_path and fp_previous.url_path and fp_current.url_path == fp_previous.url_path:
            source_node, _ = get_or_create_node(
                session,
                ENTITY_SCHOLARSHIP,
                str(scholarship.id),
                display_name=scholarship.title,
            )
            target_node, _ = get_or_create_node(
                session,
                ENTITY_SCHOLARSHIP,
                str(previous_scholarship.id),
                display_name=previous_scholarship.title,
            )

            cycle_value = f"cycle:{fp_current.domain}:{fp_current.url_path}"
            cycle_node, _ = get_or_create_node(
                session,
                ENTITY_CYCLE,
                cycle_value,
                display_name=f"Cycle: {fp_current.domain}",
                metadata={"domain": fp_current.domain, "path": fp_current.url_path},
            )

            edge1, _ = create_edge(
                session,
                source_node.id,
                cycle_node.id,
                RELATIONSHIP_CYCLE,
                confidence=1.0,
                status=STATUS_VERIFIED,
                provenance={"year": current_year, "cycle_type": "same_path"},
            )
            create_edge(
                session,
                target_node.id,
                cycle_node.id,
                RELATIONSHIP_CYCLE,
                confidence=1.0,
                status=STATUS_VERIFIED,
                provenance={"year": previous_year, "cycle_type": "same_path"},
            )

            return RelationshipResult(
                edge_id=edge1.id,
                created=True,
                status=STATUS_VERIFIED,
                confidence=1.0,
                message=f"cycle_detected:domain={fp_current.domain}",
            )

    if current_year and previous_year and current_year != previous_year:
        if fp_current.provider and fp_previous.provider and fp_current.provider == fp_previous.provider:
            source_node, _ = get_or_create_node(
                session,
                ENTITY_SCHOLARSHIP,
                str(scholarship.id),
                display_name=scholarship.title,
            )
            target_node, _ = get_or_create_node(
                session,
                ENTITY_SCHOLARSHIP,
                str(previous_scholarship.id),
                display_name=previous_scholarship.title,
            )

            edge, created = create_edge(
                session,
                source_node.id,
                target_node.id,
                RELATIONSHIP_RELATED,
                confidence=0.8,
                status=STATUS_VERIFIED,
                provenance={
                    "relation": "cycle_year_change",
                    "current_year": current_year,
                    "previous_year": previous_year,
                },
            )

            return RelationshipResult(
                edge_id=edge.id,
                created=created,
                status=STATUS_VERIFIED,
                confidence=0.8,
                message=f"cycle_year_change:{previous_year}->{current_year}",
            )

    return RelationshipResult(
        edge_id=None,
        created=False,
        status=STATUS_REVIEW,
        confidence=0.0,
        message="no_cycle_detected",
    )


def find_related_by_shared_attributes(
    session: Session,
    scholarship: Scholarship,
    min_shared: int = 2,
) -> list[tuple[int, int, list[str]]]:
    """Find scholarships sharing multiple attributes."""
    if not scholarship.country:
        return []

    candidates = session.scalars(
        select(Scholarship).where(
            and_(
                Scholarship.id != scholarship.id,
                Scholarship.country == scholarship.country,
            )
        )
    ).all()

    related: list[tuple[int, int, list[str]]] = []

    for candidate in candidates:
        shared: list[str] = []
        shared_count = 0

        if (
            scholarship.degree and candidate.degree
            and _normalize_degree(scholarship.degree) == _normalize_degree(candidate.degree)
        ):
            shared.append("degree")
            shared_count += 1

        if (
            scholarship.funding and candidate.funding
            and _normalize_funding(scholarship.funding) == _normalize_funding(candidate.funding)
        ):
            shared.append("funding")
            shared_count += 1

        if (
            scholarship.official_source and candidate.official_source
            and normalize_provider(scholarship.official_source)
            == normalize_provider(candidate.official_source)
        ):
            shared.append("provider")
            shared_count += 1

        if (
            scholarship.official_source_url and candidate.official_source_url
            and extract_domain(scholarship.official_source_url)
            == extract_domain(candidate.official_source_url)
        ):
            shared.append("source_domain")
            shared_count += 1

        if shared_count >= min_shared:
            related.append((candidate.id, shared_count, shared))

    related.sort(key=lambda x: (-x[1], x[0]))
    return related


def create_related_edges(
    session: Session,
    scholarship: Scholarship,
    min_shared: int = 2,
    provenance: dict | None = None,
) -> list[RelationshipResult]:
    """Create edges to related scholarships based on shared attributes."""
    related = find_related_by_shared_attributes(session, scholarship, min_shared)
    results: list[RelationshipResult] = []

    source_node, _ = get_or_create_node(
        session,
        ENTITY_SCHOLARSHIP,
        str(scholarship.id),
        display_name=scholarship.title,
    )

    for related_id, shared_count, shared_attrs in related:
        target_node, _ = get_or_create_node(
            session,
            ENTITY_SCHOLARSHIP,
            str(related_id),
        )

        confidence = min(0.95, 0.5 + (shared_count * 0.15))
        status = STATUS_VERIFIED if shared_count >= min_shared else STATUS_REVIEW

        edge, created = create_edge(
            session,
            source_node.id,
            target_node.id,
            RELATIONSHIP_RELATED,
            confidence=confidence,
            status=status,
            provenance={
                "shared_attributes": shared_attrs,
                "shared_count": shared_count,
                **(provenance or {}),
            },
        )

        results.append(RelationshipResult(
            edge_id=edge.id,
            created=created,
            status=status,
            confidence=confidence,
            message=f"related:shared={shared_attrs}",
        ))

    return results


def get_scholarships_by_provider(
    session: Session,
    provider: str,
) -> list[Scholarship]:
    """Get all scholarships from a provider."""
    norm_provider = normalize_provider(provider)
    if not norm_provider:
        return []

    return list(session.scalars(
        select(Scholarship).where(
            func_lower_like(Scholarship.official_source, norm_provider)
        )
    ).all())


def get_scholarships_by_country(
    session: Session,
    country: str,
) -> list[Scholarship]:
    """Get all scholarships for a country."""
    return list(session.scalars(
        select(Scholarship).where(
            Scholarship.country == country
        )
    ).all())


def get_scholarships_by_degree(
    session: Session,
    degree: str,
) -> list[Scholarship]:
    """Get all scholarships for a degree level."""
    norm_degree = _normalize_degree(degree)
    if not norm_degree:
        return []

    all_scholarships = session.scalars(select(Scholarship)).all()
    return [s for s in all_scholarships if _normalize_degree(s.degree) == norm_degree]


def get_scholarships_by_funding(
    session: Session,
    funding: str,
) -> list[Scholarship]:
    """Get all scholarships for a funding type."""
    norm_funding = _normalize_funding(funding)
    if not norm_funding:
        return []

    all_scholarships = session.scalars(select(Scholarship)).all()
    return [s for s in all_scholarships if _normalize_funding(s.funding) == norm_funding]


def get_graph_stats(session: Session) -> GraphStats:
    """Get graph statistics."""
    from sqlalchemy import func

    total_nodes = session.scalar(select(func.count(KnowledgeNode.id))) or 0
    total_edges = session.scalar(select(func.count(KnowledgeEdge.id))) or 0

    nodes_by_type: dict[str, int] = {}
    rows = session.execute(
        select(KnowledgeNode.entity_type, func.count(KnowledgeNode.id))
        .group_by(KnowledgeNode.entity_type)
    ).all()
    for entity_type, count in rows:
        nodes_by_type[entity_type] = count

    edges_by_relation: dict[str, int] = {}
    rows = session.execute(
        select(KnowledgeEdge.relation_type, func.count(KnowledgeEdge.id))
        .group_by(KnowledgeEdge.relation_type)
    ).all()
    for relation_type, count in rows:
        edges_by_relation[relation_type] = count

    edges_by_status: dict[str, int] = {}
    rows = session.execute(
        select(KnowledgeEdge.status, func.count(KnowledgeEdge.id))
        .group_by(KnowledgeEdge.status)
    ).all()
    for status, count in rows:
        edges_by_status[status] = count

    return GraphStats(
        total_nodes=total_nodes,
        total_edges=total_edges,
        nodes_by_type=nodes_by_type,
        edges_by_relation=edges_by_relation,
        edges_by_status=edges_by_status,
    )


def batch_build_graph(
    session: Session,
    scholarships: list[Scholarship],
    provenance: dict | None = None,
) -> dict[int, dict[str, int]]:
    """Build graph for multiple scholarships. Batch-friendly."""
    results: dict[int, dict[str, int]] = {}
    for scholarship in scholarships:
        nodes = build_scholarship_graph(session, scholarship, provenance)
        results[scholarship.id] = nodes
    return results


def resolve_ambiguous_relationship(
    session: Session,
    source_id: int,
    target_id: int,
    relation_type: str,
    resolution: str,
    confidence: float | None = None,
) -> RelationshipResult:
    """Resolve an ambiguous relationship."""
    edge = session.scalar(
        select(KnowledgeEdge).where(
            and_(
                KnowledgeEdge.source_node_id == source_id,
                KnowledgeEdge.target_node_id == target_id,
                KnowledgeEdge.relation_type == relation_type,
            )
        )
    )

    if edge is None:
        return RelationshipResult(
            edge_id=None,
            created=False,
            status=STATUS_REVIEW,
            confidence=0.0,
            message="edge_not_found",
        )

    if resolution == "approve":
        edge.status = STATUS_VERIFIED
        if confidence is not None:
            edge.confidence = confidence
        return RelationshipResult(
            edge_id=edge.id,
            created=False,
            status=STATUS_VERIFIED,
            confidence=edge.confidence,
            message="approved",
        )
    elif resolution == "reject":
        edge.status = STATUS_REVIEW
        edge.confidence = 0.0
        return RelationshipResult(
            edge_id=edge.id,
            created=False,
            status=STATUS_REVIEW,
            confidence=0.0,
            message="rejected",
        )
    else:
        return RelationshipResult(
            edge_id=edge.id,
            created=False,
            status=edge.status,
            confidence=edge.confidence,
            message="no_change",
        )


def get_aliases_for_scholarship(
    session: Session,
    scholarship_id: int,
) -> list[AliasInfo]:
    """Get all aliases for a scholarship."""
    sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(scholarship_id))
    if sch_node is None:
        return []

    edges = get_edges_for_node(
        session,
        sch_node.id,
        direction="outgoing",
        relation_type=RELATIONSHIP_ALIAS,
    )

    aliases: list[AliasInfo] = []
    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        return []

    for edge in edges:
        alias_node = get_node_by_id(session, edge.target_node_id)
        if alias_node is None:
            continue

        similarity = edge.confidence
        is_rename = similarity >= 0.6

        aliases.append(AliasInfo(
            scholarship_id=scholarship_id,
            alias_title=alias_node.display_name or alias_node.normalized_value,
            original_title=scholarship.title,
            similarity=similarity,
            is_rename=is_rename,
        ))

    return aliases


def get_cycle_history(
    session: Session,
    scholarship_id: int,
) -> list[CycleInfo]:
    """Get cycle history for a scholarship."""
    sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(scholarship_id))
    if sch_node is None:
        return []

    edges = get_edges_for_node(
        session,
        sch_node.id,
        direction="outgoing",
        relation_type=RELATIONSHIP_CYCLE,
    )

    cycles: list[CycleInfo] = []
    for edge in edges:
        cycle_node = get_node_by_id(session, edge.target_node_id)
        if cycle_node is None:
            continue

        year = edge.provenance.get("year") if edge.provenance else None
        cycles.append(CycleInfo(
            scholarship_id=scholarship_id,
            cycle_year=year,
            previous_cycle_id=None,
            cycle_status=edge.status,
            normalized_value=cycle_node.normalized_value,
        ))

    return cycles


def traverse_from_scholarship(
    session: Session,
    scholarship_id: int,
    relation_type: str | None = None,
    max_depth: int = 1,
) -> list[GraphPath]:
    """Traverse graph from a scholarship node."""
    source_node = find_node(session, ENTITY_SCHOLARSHIP, str(scholarship_id))
    if source_node is None:
        return []

    paths: list[GraphPath] = []
    visited_nodes: set[int] = {source_node.id}

    def _traverse(
        current_id: int,
        depth: int,
        path_nodes: list[NodeRef],
        path_edges: list[EdgeRef],
        path_confidence: float,
    ) -> None:
        if depth >= max_depth:
            return

        edges = get_edges_for_node(session, current_id, direction="outgoing")
        for edge in edges:
            if relation_type and edge.relation_type != relation_type:
                continue
            if edge.status == STATUS_REVIEW:
                continue

            neighbor_id = edge.target_node_id
            if neighbor_id in visited_nodes:
                continue

            neighbor_node = get_node_by_id(session, neighbor_id)
            if neighbor_node is None:
                continue

            new_confidence = path_confidence * edge.confidence
            new_path_nodes = path_nodes + [NodeRef(
                id=neighbor_node.id,
                entity_type=neighbor_node.entity_type,
                normalized_value=neighbor_node.normalized_value,
                display_name=neighbor_node.display_name,
            )]
            new_path_edges = path_edges + [EdgeRef(
                id=edge.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                relation_type=edge.relation_type,
                confidence=edge.confidence,
                status=edge.status,
                provenance=dict(edge.provenance or {}),
            )]

            paths.append(GraphPath(
                nodes=new_path_nodes,
                edges=new_path_edges,
                path_type=edge.relation_type,
                confidence=new_confidence,
            ))

            visited_nodes.add(neighbor_id)
            _traverse(neighbor_id, depth + 1, new_path_nodes, new_path_edges, new_confidence)
            visited_nodes.discard(neighbor_id)

    _traverse(source_node.id, 0, [], [], 1.0)
    return paths