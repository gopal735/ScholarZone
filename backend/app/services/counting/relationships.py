"""Relationship counting over the existing relational catalogue.

ScholarZone already stores relationships: ``knowledge_nodes`` and ``knowledge_edges``
are a typed, confidence-bearing graph, and the catalogue's own columns (country,
published funding string, published degree string, canonical taxonomy field) are
structured evidence. So this layer needs no graph database and no new tables.

The governing constraint is about *provenance*, not capability. A relationship is
only reported when it was derived from structured, published evidence, and the
evidence that produced it is published alongside the count. Two kinds are
distinguished and never merged:

``VERIFIED_EDGE``
    The relationship exists as a row in ``knowledge_edges`` with a verified status.
    These are real entity relationships ScholarZone has already established.

``PUBLISHED_FIELD_MATCH``
    Two records share an identical value in a structured column. Exact match on a
    published field, not name similarity and not an inference about who the funder
    really is. A shared funding *string* is evidence that two records describe
    funding the same way; it is not evidence that they share a legal funder, and
    :attr:`RelationshipCount.is_verified` says so.

What is deliberately absent: centrality, community detection, and any graph
algorithm. The relationship graph is sparse, and a centrality score computed over
three verified edges is a number that looks like insight and is not. Where the
graph is sparse this module reports the simple verified relationships instead,
which is what the architecture requires.

Field relationships additionally consult the Match taxonomy's own resolver, so
"related programme" means what the curated taxonomy says it means and never what
two strings happen to have in common.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .types import CountUniverse, RelationshipCount


#: Evidence classes, published with every relationship count.
EVIDENCE_VERIFIED_EDGE = "VERIFIED_EDGE"
EVIDENCE_PUBLISHED_MATCH = "PUBLISHED_FIELD_MATCH"

#: Relationships below this many members are not published. A "cluster" of one
#: scholarship tells a reader nothing, and listing every singleton would bury the
#: relationships that are actually informative.
MIN_MEMBERS_FOR_PUBLICATION = 2

#: How many groups to publish per relationship. Bounded so a wide-open country
#: facet cannot turn one request into a few hundred rows.
MAX_GROUPS_PER_RELATIONSHIP = 50


def relationship_counts(
    records: Sequence[object],
    *,
    universe: CountUniverse = CountUniverse.MATCH_ANALYSED,
    limit: int = MAX_GROUPS_PER_RELATIONSHIP,
) -> list[RelationshipCount]:
    """Counts over structured relationships, from one candidate set.

    Built from the same records every other count describes, so a relationship
    count and a summary count can never be about different populations.
    """
    groups: list[RelationshipCount] = []
    groups.extend(_group_by(records, "country", "Country", universe, limit))
    groups.extend(_group_by(records, "degree_levels", "Degree", universe, limit))
    groups.extend(_group_by(records, "funding_state", "Funding", universe, limit))
    # Only records the taxonomy actually resolved a field for. A record whose
    # programme is unresolvable is absent rather than grouped under a guess.
    groups.extend(
        RelationshipCount(
            relationship="same_field",
            entity_key=key,
            entity_label=label,
            count=count,
            evidence_source=EVIDENCE_PUBLISHED_MATCH,
            is_verified=False,
        )
        for key, label, count in _field_groups(records, limit)
    )
    return groups


def _group_by(
    records: Sequence[object],
    attribute: str,
    relationship: str,
    universe: CountUniverse,
    limit: int,
) -> list[RelationshipCount]:
    counts: dict[str, int] = {}
    for record in records:
        value = getattr(record, attribute, None)
        if value is None:
            continue
        key = value.value if hasattr(value, "value") else str(value)
        counts[key] = counts.get(key, 0) + 1

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [
        RelationshipCount(
            relationship=relationship,
            entity_key=key,
            entity_label=key.replace("_", " ").title(),
            count=count,
            evidence_source=EVIDENCE_PUBLISHED_MATCH,
            is_verified=False,
        )
        for key, count in ordered
        if count >= MIN_MEMBERS_FOR_PUBLICATION
    ]


def _field_groups(records: Sequence[object], limit: int):
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for record in records:
        key = getattr(record, "field", None)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        label = getattr(record, "field_label", None)
        if key not in labels and label:
            labels[key] = label

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [
        (key, labels.get(key, key.replace("_", " ").title()), count)
        for key, count in ordered
        if count >= MIN_MEMBERS_FOR_PUBLICATION
    ]


def related_fields(current_key: str) -> tuple[str, ...]:
    """Fields the curated taxonomy relates to ``current_key``.

    Reads the taxonomy's own ``close`` and ``related`` tuples. Both are curated
    editorial relationships declared in the taxonomy itself, which is what makes a
    proposed field evidence-based rather than a guess. String similarity is never
    used to suggest a field, and a key the taxonomy does not know returns nothing
    rather than a nearest match.
    """
    from ..matching.taxonomy import FIELDS_BY_KEY, relate_fields

    field = FIELDS_BY_KEY.get(current_key)
    if field is None:
        return ()

    # A field that resolves to something broader genuinely includes its parent, so
    # the relationship is checked rather than assumed.
    candidates = tuple(dict.fromkeys((*field.close, *field.related, *( (field.broad,) if field.broad else ()))))
    related: list[str] = []
    for candidate in candidates:
        if not candidate or candidate == current_key:
            continue
        relationship = relate_fields(current_key, candidate)
        if relationship.level in {"CLOSE_SPECIALIZATION", "RELATED_FIELD", "BROAD_FIELD"}:
            related.append(candidate)
    return tuple(related)


def related_field_labels(keys: Sequence[str]) -> dict[str, str]:
    """Display labels for taxonomy keys, resolved from the taxonomy itself."""
    from ..matching.taxonomy import FIELDS_BY_KEY

    return {key: FIELDS_BY_KEY[key].label for key in keys if key in FIELDS_BY_KEY}


def verified_graph_counts(session: Session, *, limit: int = MAX_GROUPS_PER_RELATIONSHIP):
    """Relationship counts from the existing knowledge graph.

    Only edges whose status is verified are counted. An edge in review or inferred
    is not reported as a relationship, because the graph already carries a status
    that says exactly that, and overriding it here would discard a decision
    ScholarZone made deliberately.

    Returns the counts plus a density report, so a reader can see how thin the
    graph is rather than being shown a confident answer derived from three edges.
    """
    from ..knowledge_graph import RELATION_TYPES, STATUS_VERIFIED
    from ...models import KnowledgeEdge, KnowledgeNode

    rows = session.execute(
        select(
            KnowledgeEdge.relation_type,
            func.count(KnowledgeEdge.id),
        )
        .where(KnowledgeEdge.status == STATUS_VERIFIED)
        .group_by(KnowledgeEdge.relation_type)
        .order_by(func.count(KnowledgeEdge.id).desc())
    ).all()

    total_nodes = session.scalar(select(func.count(KnowledgeNode.id))) or 0
    total_edges = (
        session.scalar(
            select(func.count(KnowledgeEdge.id)).where(
                KnowledgeEdge.status == STATUS_VERIFIED
            )
        )
        or 0
    )

    counts = [
        RelationshipCount(
            relationship=f"graph:{relation}",
            entity_key=relation,
            entity_label=relation.replace("_", " ").title(),
            count=int(count),
            evidence_source=EVIDENCE_VERIFIED_EDGE,
            is_verified=True,
        )
        for relation, count in rows[:limit]
    ]

    return counts, {
        "nodes": int(total_nodes),
        "verified_edges": int(total_edges),
        "declared_relation_types": sorted(RELATION_TYPES),
        "density": (
            "SPARSE"
            if total_edges < MIN_MEMBERS_FOR_PUBLICATION
            else "PARTIAL"
            if total_nodes and total_edges < total_nodes
            else "DENSE"
        ),
        "note": (
            "Counts use only edges already marked verified in the existing knowledge "
            "graph. No centrality or community analysis is computed: the graph is too "
            "sparse for such a measure to mean anything."
        ),
    }


__all__ = [
    "EVIDENCE_PUBLISHED_MATCH",
    "EVIDENCE_VERIFIED_EDGE",
    "MAX_GROUPS_PER_RELATIONSHIP",
    "MIN_MEMBERS_FOR_PUBLICATION",
    "relationship_counts",
    "related_field_labels",
    "related_fields",
    "verified_graph_counts",
]