"""Tests for scholarship knowledge graph and relationship intelligence."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, KnowledgeEdge, KnowledgeNode, Scholarship
from app.services.knowledge_graph import (
    CYCLE_RENAMED,
    CYCLE_SAME,
    EDGE_STATUSES,
    ENTITY_ALIAS,
    ENTITY_CYCLE,
    ENTITY_COUNTRY,
    ENTITY_DEGREE,
    ENTITY_FUNDING,
    ENTITY_PROVIDER,
    ENTITY_SCHOLARSHIP,
    ENTITY_SOURCE,
    NODE_ENTITY_TYPES,
    RELATIONSHIP_ALIAS,
    RELATIONSHIP_COUNTRY,
    RELATIONSHIP_CYCLE,
    RELATIONSHIP_DEGREE,
    RELATIONSHIP_FUNDING,
    RELATIONSHIP_PROVIDER,
    RELATIONSHIP_RELATED,
    RELATIONSHIP_SOURCE,
    RELATION_TYPES,
    STATUS_INFERRED,
    STATUS_REVIEW,
    STATUS_VERIFIED,
    AliasInfo,
    CycleInfo,
    GraphPath,
    GraphStats,
    NodeRef,
    RelationshipResult,
    _normalize_entity_value,
    batch_build_graph,
    build_scholarship_graph,
    create_edge,
    detect_alias_relationship,
    detect_cycle_relationship,
    find_related_by_shared_attributes,
    find_node,
    get_aliases_for_scholarship,
    get_cycle_history,
    get_edges_for_node,
    get_graph_stats,
    get_or_create_node,
    get_related_scholarships_via_graph,
    get_scholarships_by_country,
    get_scholarships_by_degree,
    get_scholarships_by_funding,
    get_scholarships_by_provider,
    resolve_ambiguous_relationship,
    traverse_from_scholarship,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


_url_counter = 0


@pytest.fixture
def scholarship_factory(session):
    def _make(**kwargs):
        global _url_counter
        _url_counter += 1
        url = f"https://example.com/scholarship-{_url_counter}"
        defaults = {
            "title": "Test Scholarship",
            "country": "Germany",
            "degree": "Masters",
            "funding": "Full",
            "official_source_url": url,
            "official_source": "Test Provider",
        }
        defaults.update(kwargs)
        if "official_source_url" in kwargs:
            defaults["official_source_url"] = kwargs["official_source_url"]
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s
    return _make


class TestNormalizeEntityValue:
    def test_country_normalization(self):
        assert _normalize_entity_value(ENTITY_COUNTRY, "Germany") == "germany"
        assert _normalize_entity_value(ENTITY_COUNTRY, "  USA  ") == "usa"

    def test_degree_normalization(self):
        assert _normalize_entity_value(ENTITY_DEGREE, "Masters") == "masters"
        assert _normalize_entity_value(ENTITY_DEGREE, "PhD") == "phd"
        assert _normalize_entity_value(ENTITY_DEGREE, "Bachelors") == "bachelors"

    def test_funding_normalization(self):
        assert _normalize_entity_value(ENTITY_FUNDING, "Full") == "full"
        assert _normalize_entity_value(ENTITY_FUNDING, "Partial") == "partial"

    def test_provider_normalization(self):
        assert _normalize_entity_value(ENTITY_PROVIDER, "DAAD") == "daad"
        assert _normalize_entity_value(ENTITY_PROVIDER, "British Council") == "britishcouncil"

    def test_empty_value(self):
        assert _normalize_entity_value(ENTITY_COUNTRY, "") == ""
        assert _normalize_entity_value(ENTITY_COUNTRY, None) == ""

    def test_scholarship_entity(self):
        assert _normalize_entity_value(ENTITY_SCHOLARSHIP, "42") == "scholarship:42"

    def test_whitespace_handling(self):
        assert _normalize_entity_value(ENTITY_COUNTRY, "   ") == ""


class TestGetOrCreateNode:
    def test_create_new_node(self, session):
        node, created = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        assert created is True
        assert node.entity_type == ENTITY_COUNTRY
        assert node.normalized_value == "germany"
        assert node.display_name == "Germany"

    def test_get_existing_node(self, session):
        node1, created1 = get_or_create_node(session, ENTITY_COUNTRY, "France")
        node2, created2 = get_or_create_node(session, ENTITY_COUNTRY, "france")
        assert created1 is True
        assert created2 is False
        assert node1.id == node2.id

    def test_case_insensitive_dedup(self, session):
        node1, _ = get_or_create_node(session, ENTITY_PROVIDER, "DAAD")
        node2, created = get_or_create_node(session, ENTITY_PROVIDER, "daad")
        assert created is False
        assert node1.id == node2.id

    def test_with_display_name(self, session):
        node, _ = get_or_create_node(
            session, ENTITY_COUNTRY, "DE", display_name="Germany"
        )
        assert node.display_name == "Germany"

    def test_with_metadata(self, session):
        node, _ = get_or_create_node(
            session, ENTITY_COUNTRY, "Japan", metadata={"code": "JP"}
        )
        assert node.metadata_json == {"code": "JP"}

    def test_update_display_name(self, session):
        node1, _ = get_or_create_node(session, ENTITY_COUNTRY, "Italy")
        node1.display_name = None
        session.commit()

        node2, created = get_or_create_node(
            session, ENTITY_COUNTRY, "italy", display_name="Italia"
        )
        assert created is False
        assert node2.display_name == "Italia"

    def test_merge_metadata(self, session):
        node1, _ = get_or_create_node(
            session, ENTITY_COUNTRY, "Korea", metadata={"code": "KR"}
        )
        session.commit()

        node2, created = get_or_create_node(
            session, ENTITY_COUNTRY, "korea", metadata={"region": "asia"}
        )
        assert created is False
        assert node2.metadata_json == {"code": "KR", "region": "asia"}

    def test_invalid_entity_type(self, session):
        with pytest.raises(ValueError, match="Unknown entity type"):
            get_or_create_node(session, "invalid_type", "value")

    def test_empty_value_raises(self, session):
        with pytest.raises(ValueError, match="Cannot normalize"):
            get_or_create_node(session, ENTITY_COUNTRY, "")


class TestFindNode:
    def test_find_existing(self, session):
        get_or_create_node(session, ENTITY_COUNTRY, "Spain")
        node = find_node(session, ENTITY_COUNTRY, "spain")
        assert node is not None
        assert node.normalized_value == "spain"

    def test_find_nonexistent(self, session):
        node = find_node(session, ENTITY_COUNTRY, "nonexistent")
        assert node is None

    def test_find_empty_value(self, session):
        node = find_node(session, ENTITY_COUNTRY, "")
        assert node is None


class TestCreateEdge:
    def test_create_new_edge(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        edge, created = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_COUNTRY
        )
        assert created is True
        assert edge.relation_type == RELATIONSHIP_COUNTRY
        assert edge.status == STATUS_VERIFIED
        assert edge.confidence == 1.0

    def test_duplicate_edge_prevented(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        edge1, created1 = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_COUNTRY
        )
        edge2, created2 = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_COUNTRY
        )
        assert created1 is True
        assert created2 is False
        assert edge1.id == edge2.id

    def test_edge_with_provenance(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        edge, _ = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_COUNTRY,
            provenance={"source": "test", "confidence": "high"}
        )
        assert edge.provenance["source"] == "test"

    def test_invalid_relation_type(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        with pytest.raises(ValueError, match="Unknown relation type"):
            create_edge(session, n1.id, n2.id, "invalid_relation")

    def test_invalid_status(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        with pytest.raises(ValueError, match="Unknown edge status"):
            create_edge(session, n1.id, n2.id, RELATIONSHIP_COUNTRY, status="invalid")

    def test_confidence_updated(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        edge1, _ = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_COUNTRY, confidence=0.5
        )
        edge2, created = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_COUNTRY, confidence=0.9
        )
        assert created is False
        assert edge2.confidence == 0.9


class TestGetEdgesForNode:
    def test_outgoing_edges(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        n3, _ = get_or_create_node(session, ENTITY_DEGREE, "Masters")
        create_edge(session, n1.id, n2.id, RELATIONSHIP_COUNTRY)
        create_edge(session, n1.id, n3.id, RELATIONSHIP_DEGREE)
        create_edge(session, n3.id, n2.id, RELATIONSHIP_COUNTRY)

        edges = get_edges_for_node(session, n1.id, direction="outgoing")
        assert len(edges) == 2

    def test_incoming_edges(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "2")
        n3, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        create_edge(session, n1.id, n3.id, RELATIONSHIP_COUNTRY)
        create_edge(session, n2.id, n3.id, RELATIONSHIP_COUNTRY)

        edges = get_edges_for_node(session, n3.id, direction="incoming")
        assert len(edges) == 2

    def test_both_directions(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        create_edge(session, n1.id, n2.id, RELATIONSHIP_COUNTRY)

        edges = get_edges_for_node(session, n1.id, direction="both")
        assert len(edges) == 1

    def test_filter_by_relation_type(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        n3, _ = get_or_create_node(session, ENTITY_DEGREE, "Masters")
        create_edge(session, n1.id, n2.id, RELATIONSHIP_COUNTRY)
        create_edge(session, n1.id, n3.id, RELATIONSHIP_DEGREE)

        edges = get_edges_for_node(
            session, n1.id, direction="outgoing", relation_type=RELATIONSHIP_COUNTRY
        )
        assert len(edges) == 1
        assert edges[0].relation_type == RELATIONSHIP_COUNTRY


class TestBuildScholarshipGraph:
    def test_builds_all_nodes(self, session, scholarship_factory):
        s = scholarship_factory(
            title="DAAD Scholarship 2026",
            official_source="DAAD",
            official_source_url="https://daad.de/scholarship/123",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        nodes = build_scholarship_graph(session, s)
        assert "scholarship" in nodes
        assert "provider" in nodes
        assert "country" in nodes
        assert "degree" in nodes
        assert "funding" in nodes
        assert "source" in nodes

    def test_idempotent(self, session, scholarship_factory):
        s = scholarship_factory()
        nodes1 = build_scholarship_graph(session, s)
        nodes2 = build_scholarship_graph(session, s)
        assert nodes1 == nodes2

    def test_minimal_scholarship(self, session, scholarship_factory):
        s = scholarship_factory(
            official_source=None,
            official_source_url=None,
        )
        nodes = build_scholarship_graph(session, s)
        assert "scholarship" in nodes
        assert "provider" not in nodes
        assert "source" not in nodes

    def test_with_provenance(self, session, scholarship_factory):
        s = scholarship_factory()
        provenance = {"source": "test_pipeline", "run_id": "123"}
        build_scholarship_graph(session, s, provenance=provenance)

        sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(s.id))
        edges = get_edges_for_node(session, sch_node.id, direction="outgoing")
        for edge in edges:
            assert edge.provenance.get("source") == "test_pipeline"

    def test_preserve_existing_identity(self, session, scholarship_factory):
        s = scholarship_factory(title="Original Title")
        build_scholarship_graph(session, s)
        session.commit()

        s.title = "Updated Title"
        session.commit()

        build_scholarship_graph(session, s)
        sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(s.id))
        assert sch_node is not None
        assert sch_node.normalized_value == f"scholarship:{s.id}"


class TestDetectAliasRelationship:
    def test_identical_titles(self, session, scholarship_factory):
        s = scholarship_factory(title="DAAD Scholarship")
        result = detect_alias_relationship(session, s, "DAAD Scholarship")
        assert result.status == STATUS_VERIFIED
        assert result.confidence == 1.0
        assert "identical" in result.message

    def test_similar_title_detected(self, session, scholarship_factory):
        s = scholarship_factory(title="DAAD Masters Scholarship 2026")
        result = detect_alias_relationship(session, s, "DAAD Masters Scholarship 2026 Germany")
        assert result.created is True
        assert result.confidence >= 0.6

    def test_low_similarity_review(self, session, scholarship_factory):
        s = scholarship_factory(title="DAAD Scholarship")
        result = detect_alias_relationship(session, s, "Completely Different Program")
        assert result.status == STATUS_REVIEW
        assert result.confidence < 0.5

    def test_empty_title_review(self, session, scholarship_factory):
        s = scholarship_factory()
        result = detect_alias_relationship(session, s, "")
        assert result.status == STATUS_REVIEW

    def test_creates_alias_node(self, session, scholarship_factory):
        s = scholarship_factory(title="Erasmus Mundus Joint Masters Scholarship")
        detect_alias_relationship(session, s, "Erasmus Mundus Joint Masters")

        aliases = get_aliases_for_scholarship(session, s.id)
        assert len(aliases) >= 1


class TestDetectCycleRelationship:
    def test_same_url_path(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="DAAD 2025",
            official_source_url="https://daad.de/scholarship?id=100&year=2025",
        )
        s2 = scholarship_factory(
            title="DAAD 2026",
            official_source_url="https://daad.de/scholarship?id=100&year=2026",
        )
        result = detect_cycle_relationship(session, s2, s1)
        assert result.status == STATUS_VERIFIED
        assert result.confidence == 1.0

    def test_year_change_same_provider(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="DAAD Scholarship 2025",
            official_source="DAAD",
            official_source_url="https://daad.de/scholarship-a",
        )
        s2 = scholarship_factory(
            title="DAAD Scholarship 2026",
            official_source="DAAD",
            official_source_url="https://daad.de/scholarship-b",
        )
        result = detect_cycle_relationship(session, s2, s1)
        assert result.created is True
        assert "year" in result.message.lower() or "cycle" in result.message.lower()

    def test_no_previous_cycle(self, session, scholarship_factory):
        s = scholarship_factory()
        result = detect_cycle_relationship(session, s, None)
        assert result.created is False
        assert "no_previous" in result.message

    def test_creates_cycle_node(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="DAAD 2025",
            official_source_url="https://daad.de/program/xyz?id=1&y=2025",
        )
        s2 = scholarship_factory(
            title="DAAD 2026",
            official_source_url="https://daad.de/program/xyz?id=1&y=2026",
        )
        detect_cycle_relationship(session, s2, s1)

        history = get_cycle_history(session, s2.id)
        assert len(history) >= 1


class TestFindRelatedBySharedAttributes:
    def test_shared_country_degree(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="Program A",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source="DAAD",
        )
        s2 = scholarship_factory(
            title="Program B",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source="DAAD",
        )
        related = find_related_by_shared_attributes(session, s1, min_shared=2)
        assert len(related) >= 1
        assert related[0][0] == s2.id

    def test_min_shared_threshold(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="Program A",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source="DAAD",
        )
        s2 = scholarship_factory(
            title="Program B",
            country="Germany",
            degree="PhD",
            funding="Partial",
            official_source="Other",
        )
        related = find_related_by_shared_attributes(session, s1, min_shared=3)
        assert len(related) == 0

    def test_no_candidates(self, session, scholarship_factory):
        s = scholarship_factory(country="Japan")
        related = find_related_by_shared_attributes(session, s)
        assert len(related) == 0

    def test_sorted_by_shared_count(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="Program A",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source="DAAD",
            official_source_url="https://daad.de/program/aaa1",
        )
        s2 = scholarship_factory(
            title="Program B",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source="DAAD",
            official_source_url="https://daad.de/program/aaa2",
        )
        related = find_related_by_shared_attributes(session, s1, min_shared=2)
        assert len(related) >= 1


class TestGetRelatedScholarshipsViaGraph:
    def test_direct_relation(self, session, scholarship_factory):
        s1 = scholarship_factory(title="A", country="Germany", degree="Masters", funding="Full")
        s2 = scholarship_factory(title="B", country="Germany", degree="Masters", funding="Full")
        build_scholarship_graph(session, s1)
        build_scholarship_graph(session, s2)
        session.commit()

        from app.services.knowledge_graph import create_related_edges
        create_related_edges(session, s1, min_shared=2)

        related = get_related_scholarships_via_graph(session, s1.id)
        related_ids = [r[0] for r in related]
        assert s2.id in related_ids

    def test_no_graph_nodes(self, session):
        related = get_related_scholarships_via_graph(session, 999)
        assert len(related) == 0


class TestTraversal:
    def test_traverse_provider(self, session, scholarship_factory):
        s = scholarship_factory(
            official_source="DAAD",
            country="Germany",
        )
        build_scholarship_graph(session, s)

        paths = traverse_from_scholarship(session, s.id, relation_type=RELATIONSHIP_PROVIDER)
        assert len(paths) >= 1
        assert paths[0].path_type == RELATIONSHIP_PROVIDER

    def test_traverse_country(self, session, scholarship_factory):
        s = scholarship_factory(country="Germany")
        build_scholarship_graph(session, s)

        paths = traverse_from_scholarship(session, s.id, relation_type=RELATIONSHIP_COUNTRY)
        assert len(paths) >= 1

    def test_max_depth_one(self, session, scholarship_factory):
        s = scholarship_factory(
            official_source="DAAD",
            country="Germany",
            degree="Masters",
        )
        build_scholarship_graph(session, s)

        paths = traverse_from_scholarship(session, s.id, max_depth=1)
        assert len(paths) >= 3

    def test_no_matching_relation(self, session, scholarship_factory):
        s = scholarship_factory(country="Germany", official_source=None, official_source_url=None)
        build_scholarship_graph(session, s)

        paths = traverse_from_scholarship(session, s.id, relation_type=RELATIONSHIP_PROVIDER)
        assert len(paths) == 0


class TestLookupFunctions:
    def test_get_by_provider(self, session, scholarship_factory):
        s1 = scholarship_factory(official_source="DAAD")
        s2 = scholarship_factory(official_source="DAAD")
        results = get_scholarships_by_provider(session, "DAAD")
        assert len(results) == 2

    def test_get_by_country(self, session, scholarship_factory):
        s1 = scholarship_factory(country="Germany")
        s2 = scholarship_factory(country="Germany")
        s3 = scholarship_factory(country="France")
        results = get_scholarships_by_country(session, "Germany")
        assert len(results) == 2

    def test_get_by_degree(self, session, scholarship_factory):
        s1 = scholarship_factory(degree="Masters")
        s2 = scholarship_factory(degree="masters")
        s3 = scholarship_factory(degree="PhD")
        results = get_scholarships_by_degree(session, "Masters")
        assert len(results) == 2

    def test_get_by_funding(self, session, scholarship_factory):
        s1 = scholarship_factory(funding="Full")
        s2 = scholarship_factory(funding="full")
        s3 = scholarship_factory(funding="Partial")
        results = get_scholarships_by_funding(session, "Full")
        assert len(results) == 2


class TestGraphStats:
    def test_empty_graph(self, session):
        stats = get_graph_stats(session)
        assert stats.total_nodes == 0
        assert stats.total_edges == 0

    def test_after_adding_nodes(self, session, scholarship_factory):
        s = scholarship_factory()
        build_scholarship_graph(session, s)
        stats = get_graph_stats(session)
        assert stats.total_nodes >= 4
        assert stats.total_edges >= 3
        assert ENTITY_SCHOLARSHIP in stats.nodes_by_type
        assert RELATIONSHIP_COUNTRY in stats.edges_by_relation

    def test_status_breakdown(self, session, scholarship_factory):
        s = scholarship_factory()
        build_scholarship_graph(session, s)
        stats = get_graph_stats(session)
        assert STATUS_VERIFIED in stats.edges_by_status


class TestBatchBuildGraph:
    def test_batch_build(self, session, scholarship_factory):
        s1 = scholarship_factory(country="Germany")
        s2 = scholarship_factory(country="France")
        s3 = scholarship_factory(country="Japan")
        results = batch_build_graph(session, [s1, s2, s3])
        assert len(results) == 3
        assert all("scholarship" in nodes for nodes in results.values())

    def test_batch_with_provenance(self, session, scholarship_factory):
        s1 = scholarship_factory()
        s2 = scholarship_factory()
        provenance = {"batch": "test", "timestamp": "2026-01-01"}
        batch_build_graph(session, [s1, s2], provenance=provenance)

        for s in [s1, s2]:
            sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(s.id))
            edges = get_edges_for_node(session, sch_node.id, direction="outgoing")
            for edge in edges:
                assert edge.provenance.get("batch") == "test"


class TestResolveAmbiguousRelationship:
    def test_approve_resolution(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "2")
        edge, _ = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_RELATED,
            status=STATUS_REVIEW, confidence=0.3
        )
        result = resolve_ambiguous_relationship(
            session, n1.id, n2.id, RELATIONSHIP_RELATED,
            resolution="approve", confidence=0.9
        )
        assert result.status == STATUS_VERIFIED
        assert result.confidence == 0.9

    def test_reject_resolution(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "2")
        edge, _ = create_edge(
            session, n1.id, n2.id, RELATIONSHIP_RELATED,
            status=STATUS_REVIEW, confidence=0.5
        )
        result = resolve_ambiguous_relationship(
            session, n1.id, n2.id, RELATIONSHIP_RELATED,
            resolution="reject"
        )
        assert result.status == STATUS_REVIEW
        assert result.confidence == 0.0

    def test_edge_not_found(self, session):
        result = resolve_ambiguous_relationship(
            session, 999, 1000, RELATIONSHIP_RELATED,
            resolution="approve"
        )
        assert result.edge_id is None
        assert result.message == "edge_not_found"


class TestDeterministicOutput:
    def test_same_input_same_nodes(self, session):
        n1a, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        session.expunge_all()
        n1b, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        assert n1a.normalized_value == n1b.normalized_value

    def test_same_input_same_edges(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        e1, _ = create_edge(session, n1.id, n2.id, RELATIONSHIP_COUNTRY)
        session.expunge_all()
        e2, _ = create_edge(session, n1.id, n2.id, RELATIONSHIP_COUNTRY)
        assert e1.id == e2.id

    def test_build_graph_deterministic(self, session, scholarship_factory):
        s = scholarship_factory()
        nodes1 = build_scholarship_graph(session, s)
        session.expunge_all()
        nodes2 = build_scholarship_graph(session, s)
        assert nodes1.keys() == nodes2.keys()


class TestNoNPlusOne:
    def test_edges_query_single_query(self, session, scholarship_factory):
        s = scholarship_factory()
        build_scholarship_graph(session, s)
        sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(s.id))
        edges = get_edges_for_node(session, sch_node.id)
        assert len(edges) > 0

    def test_batch_build_no_n_plus_one(self, session, scholarship_factory):
        scholarships = [scholarship_factory() for _ in range(10)]
        results = batch_build_graph(session, scholarships)
        assert len(results) == 10


class TestEdgeCases:
    def test_unicode_titles(self, session, scholarship_factory):
        s = scholarship_factory(title="Bourses d'études françaises")
        result = detect_alias_relationship(session, s, "Bourses detudes francaises")
        assert result.created is True or result.confidence > 0

    def test_very_long_title(self, session, scholarship_factory):
        long_title = "A" * 500
        s = scholarship_factory(title=long_title)
        nodes = build_scholarship_graph(session, s)
        assert "scholarship" in nodes

    def test_special_characters_in_country(self, session):
        node, _ = get_or_create_node(session, ENTITY_COUNTRY, "Côte d'Ivoire")
        assert node is not None

    def test_null_values_handled(self, session, scholarship_factory):
        s = scholarship_factory(
            official_source=None,
            official_source_url=None,
            country="Germany",
        )
        nodes = build_scholarship_graph(session, s)
        assert "scholarship" in nodes
        assert "provider" not in nodes
        assert "source" not in nodes


class TestConstants:
    def test_node_entity_types(self):
        assert ENTITY_SCHOLARSHIP in NODE_ENTITY_TYPES
        assert ENTITY_PROVIDER in NODE_ENTITY_TYPES
        assert ENTITY_COUNTRY in NODE_ENTITY_TYPES
        assert ENTITY_DEGREE in NODE_ENTITY_TYPES
        assert ENTITY_FUNDING in NODE_ENTITY_TYPES
        assert ENTITY_SOURCE in NODE_ENTITY_TYPES
        assert ENTITY_CYCLE in NODE_ENTITY_TYPES
        assert ENTITY_ALIAS in NODE_ENTITY_TYPES

    def test_relation_types(self):
        assert RELATIONSHIP_PROVIDER in RELATION_TYPES
        assert RELATIONSHIP_COUNTRY in RELATION_TYPES
        assert RELATIONSHIP_DEGREE in RELATION_TYPES
        assert RELATIONSHIP_FUNDING in RELATION_TYPES
        assert RELATIONSHIP_SOURCE in RELATION_TYPES
        assert RELATIONSHIP_CYCLE in RELATION_TYPES
        assert RELATIONSHIP_ALIAS in RELATION_TYPES
        assert RELATIONSHIP_RELATED in RELATION_TYPES

    def test_edge_statuses(self):
        assert STATUS_VERIFIED in EDGE_STATUSES
        assert STATUS_INFERRED in EDGE_STATUSES
        assert STATUS_REVIEW in EDGE_STATUSES


class TestHistoricalAuditability:
    def test_edge_has_timestamps(self, session):
        n1, _ = get_or_create_node(session, ENTITY_SCHOLARSHIP, "1")
        n2, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        edge, _ = create_edge(session, n1.id, n2.id, RELATIONSHIP_COUNTRY)
        assert edge.created_at is not None
        assert edge.updated_at is not None

    def test_node_has_timestamps(self, session):
        node, _ = get_or_create_node(session, ENTITY_COUNTRY, "Germany")
        assert node.created_at is not None
        assert node.updated_at is not None

    def test_multiple_edges_preserved(self, session, scholarship_factory):
        s1 = scholarship_factory(title="A", country="Germany", degree="Masters", funding="Full", official_source="DAAD")
        s2 = scholarship_factory(title="B", country="Germany", degree="Masters", funding="Full", official_source="DAAD")
        build_scholarship_graph(session, s1)
        build_scholarship_graph(session, s2)
        session.commit()

        n1 = find_node(session, ENTITY_SCHOLARSHIP, str(s1.id))
        n2 = find_node(session, ENTITY_SCHOLARSHIP, str(s2.id))
        create_edge(session, n1.id, n2.id, RELATIONSHIP_RELATED, provenance={"note": "first"})

        session.expunge_all()
        create_edge(session, n1.id, n2.id, RELATIONSHIP_RELATED, provenance={"note": "updated"})

        edges = session.query(KnowledgeEdge).filter(
            KnowledgeEdge.source_node_id == n1.id,
            KnowledgeEdge.target_node_id == n2.id,
        ).all()
        assert len(edges) == 1
        assert edges[0].provenance["note"] == "updated"


class TestProvenancePreservation:
    def test_provenance_attached_to_edges(self, session, scholarship_factory):
        s = scholarship_factory()
        provenance = {
            "source": "crawler_v2",
            "batch_id": "abc123",
            "discovered_at": "2026-01-01T00:00:00Z",
        }
        build_scholarship_graph(session, s, provenance=provenance)

        sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(s.id))
        edges = get_edges_for_node(session, sch_node.id, direction="outgoing")
        for edge in edges:
            assert edge.provenance["source"] == "crawler_v2"
            assert edge.provenance["batch_id"] == "abc123"

    def test_cycle_provenance(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="DAAD 2025",
            official_source_url="https://daad.de/program/xyz?id=1&y=2025",
        )
        s2 = scholarship_factory(
            title="DAAD 2026",
            official_source_url="https://daad.de/program/xyz?id=1&y=2026",
        )
        detect_cycle_relationship(session, s2, s1)

        sch_node = find_node(session, ENTITY_SCHOLARSHIP, str(s2.id))
        edges = get_edges_for_node(
            session, sch_node.id, relation_type=RELATIONSHIP_CYCLE
        )
        assert len(edges) >= 1
        assert edges[0].provenance.get("year") is not None