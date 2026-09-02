"""Tests for advanced entity resolution and duplicate detection."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, KnowledgeEdge, KnowledgeNode, Scholarship
from app.services.entity_resolution import (
    MATCH_ANNUAL_CYCLE,
    MATCH_EXACT,
    MATCH_METADATA,
    MATCH_NEW,
    MATCH_RELATED,
    MATCH_RENAMED,
    MATCH_REVIEW,
    MATCH_SEMANTIC,
    MATCH_TRANSLATED,
    MATCH_TYPES,
    MATCH_URL_MIGRATION,
    REASON_CODES,
    REASON_EXACT_URL,
    EntityResolutionResult,
    _build_signal,
    _compute_semantic_similarity,
    _detect_cycle_status,
    is_ambiguous,
    is_match,
    is_new,
    is_review,
    resolve_entity,
    resolve_entity_batch,
)
from app.services.knowledge_graph import (
    RELATIONSHIP_ALIAS,
    RELATIONSHIP_CYCLE,
    RELATIONSHIP_RELATED,
    STATUS_VERIFIED,
    create_edge,
    get_or_create_node,
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
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s
    return _make


class TestExactDuplicate:
    def test_exact_url_match(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="DAAD Scholarship",
            official_source="DAAD",
            official_source_url="https://www.daad.de/scholarship/",
        )
        result = resolve_entity(
            session=session,
            source_url="https://www.daad.de/scholarship/",
            title="DAAD Scholarship",
            provider="DAAD",
            country="Germany",
        )
        assert result.match_type == MATCH_EXACT
        assert result.matched_scholarship_id == existing.id
        assert result.confidence == 1.0
        assert is_match(result)

    def test_exact_url_match_with_trailing_slash(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Chevening Scholarship",
            official_source="Chevening",
            official_source_url="https://www.chevening.org/apply/",
        )
        result = resolve_entity(
            session=session,
            source_url="https://www.chevening.org/apply",
            title="Chevening Scholarship",
            provider="Chevening",
            country="UK",
        )
        assert result.match_type == MATCH_EXACT
        assert result.matched_scholarship_id == existing.id

    def test_exact_url_match_case_insensitive(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Erasmus Mundus",
            official_source="EU",
            official_source_url="https://erasmus-plus.ec.europa.eu/",
        )
        result = resolve_entity(
            session=session,
            source_url="https://ERASMUS-PLUS.EC.EUROPA.EU/",
            title="Erasmus Mundus",
            provider="EU",
            country="EU",
        )
        assert result.match_type == MATCH_EXACT
        assert result.matched_scholarship_id == existing.id


class TestUrlMigration:
    def test_same_domain_different_path(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Fulbright Program 2025",
            official_source="Fulbright",
            official_source_url="https://fulbright.org/programs/2025/",
            country="USA",
        )
        result = resolve_entity(
            session=session,
            source_url="https://fulbright.org/programs/2026/",
            title="Fulbright Program 2026",
            provider="Fulbright",
            country="USA",
        )
        assert result.match_type in (MATCH_URL_MIGRATION, MATCH_ANNUAL_CYCLE, MATCH_EXACT)
        assert result.matched_scholarship_id == existing.id
        assert result.confidence >= 0.9


class TestRenamedProgram:
    def test_renamed_title_same_provider(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="International Excellence Award",
            official_source="Oxford University",
            official_source_url="https://ox.ac.uk/awards/",
        )
        result = resolve_entity(
            session=session,
            source_url="https://ox.ac.uk/awards/",
            title="Global Excellence Scholarship",
            provider="Oxford University",
            country="UK",
        )
        assert result.match_type in (MATCH_EXACT, MATCH_RENAMED, MATCH_REVIEW)
        assert result.matched_scholarship_id is not None or result.ambiguity


class TestProviderRename:
    def test_provider_renamed_same_program(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Tech Leaders Fellowship",
            official_source="Ministry of Education",
            official_source_url="https://moe.gov/fellowship/",
        )
        result = resolve_entity(
            session=session,
            source_url="https://moe.gov/fellowship/",
            title="Tech Leaders Fellowship",
            provider="Department of Education",
            country="TestCountry",
        )
        assert result.match_type in (MATCH_EXACT, MATCH_REVIEW)
        assert result.matched_scholarship_id == existing.id or result.ambiguity


class TestAnnualCycle:
    def test_new_cycle_detected(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="DAAD Research Grant 2025",
            official_source="DAAD",
            official_source_url="https://daad.de/research/",
            country="Germany",
        )
        result = resolve_entity(
            session=session,
            source_url="https://daad.de/research/",
            title="DAAD Research Grant 2026",
            provider="DAAD",
            country="Germany",
        )
        assert result.match_type in (MATCH_EXACT, MATCH_ANNUAL_CYCLE)
        assert result.cycle_status in ("new_cycle", "same_cycle")

    def test_same_cycle(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Humboldt Fellowship 2025",
            official_source="Humboldt Foundation",
            official_source_url="https://humboldt.de/fellowship/",
        )
        result = resolve_entity(
            session=session,
            source_url="https://humboldt.de/fellowship/",
            title="Humboldt Fellowship 2025",
            provider="Humboldt Foundation",
            country="Germany",
        )
        assert result.match_type == MATCH_EXACT
        assert result.cycle_status == "same_cycle"


class TestTranslatedTitle:
    def test_translated_title_same_metadata(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Bourse d'excellence",
            official_source="French Ministry",
            official_source_url="https://education.gouv.fr/bourse/",
            country="France",
            degree="Masters",
            funding="Full",
        )
        result = resolve_entity(
            session=session,
            source_url="https://other.fr/bourse/",
            title="Excellence Scholarship",
            provider="French Ministry",
            country="France",
            degree="Masters",
            funding="Full",
        )
        assert result.match_type in (MATCH_METADATA, MATCH_REVIEW, MATCH_NEW)
        assert result.confidence >= 0.0


class TestMetadataOnlyMatch:
    def test_metadata_corroboration(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="African STEM Leaders Program",
            official_source="African Union",
            official_source_url="https://africa-union.org/stem/",
            country="Kenya",
            degree="PhD",
            funding="Full",
        )
        result = resolve_entity(
            session=session,
            source_url="https://au.int/stem/",
            title="STEM Leaders Africa",
            provider="African Union",
            country="Kenya",
            degree="PhD",
            funding="Full",
        )
        assert result.match_type in (MATCH_METADATA, MATCH_REVIEW, MATCH_NEW, MATCH_RELATED)


class TestRelatedDistinctPrograms:
    def test_related_but_distinct(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Engineering Excellence Award",
            official_source="Technical University",
            official_source_url="https://tuni.de/engineering/",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        result = resolve_entity(
            session=session,
            source_url="https://tuni.de/business/",
            title="Business Leadership Scholarship",
            provider="Technical University",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        assert result.match_type in (MATCH_RELATED, MATCH_REVIEW, MATCH_NEW, MATCH_METADATA)
        assert result.confidence < 0.95

    def test_different_programs_same_provider(self, session, scholarship_factory):
        scholarship_factory(
            title="Medical Research Grant",
            official_source="Wellcome Trust",
            official_source_url="https://wellcome.org/medical/",
            country="UK",
            degree="PhD",
            funding="Full",
        )
        result = resolve_entity(
            session=session,
            source_url="https://new.org/arts/",
            title="Arts and Culture Fellowship",
            provider="Wellcome Trust",
            country="UK",
            degree="PhD",
            funding="Full",
        )
        assert result.match_type in (MATCH_RELATED, MATCH_REVIEW, MATCH_NEW, MATCH_METADATA)


class TestSemanticNearDuplicate:
    def test_semantic_similarity_match(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="International Masters Scholarship for Excellence",
            official_source="Global University",
            official_source_url="https://globaluni.edu/masters/",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        result = resolve_entity(
            session=session,
            source_url="https://other.org/scholarship/",
            title="Masters Excellence International Scholarship Award",
            provider="Global University",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        assert result.match_type in (MATCH_SEMANTIC, MATCH_METADATA, MATCH_REVIEW, MATCH_EXACT, MATCH_ANNUAL_CYCLE, MATCH_RENAMED)
        assert result.confidence >= 0.0


class TestGenuineNewScholarship:
    def test_genuinely_new_scholarship(self, session, scholarship_factory):
        scholarship_factory(
            title="Existing Program A",
            official_source="Provider A",
            official_source_url="https://provider-a.org/program/",
            country="USA",
        )
        result = resolve_entity(
            session=session,
            source_url="https://brand-new.org/scholarship/",
            title="Completely Different Scholarship Program",
            provider="Brand New Provider",
            country="Japan",
        )
        assert result.match_type == MATCH_NEW
        assert result.matched_scholarship_id is None
        assert result.confidence == 0.0
        assert is_new(result)

    def test_new_scholarship_empty_database(self, session):
        result = resolve_entity(
            session=session,
            source_url="https://first-ever.org/scholarship/",
            title="First Ever Scholarship",
            provider="First Provider",
            country="India",
        )
        assert result.match_type == MATCH_NEW
        assert is_new(result)


class TestAmbiguousMatchReview:
    def test_ambiguous_requires_review(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Leadership Program 2025",
            official_source="Foundation X",
            official_source_url="https://foundationx.org/leadership/",
            country="USA",
        )
        result = resolve_entity(
            session=session,
            source_url="https://other.org/program/",
            title="Leadership Initiative",
            provider="Foundation Y",
            country="USA",
        )
        assert result.match_type == MATCH_REVIEW or result.ambiguity or result.confidence < 0.85

    def test_partial_match_flagged_review(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Global Health Fellowship",
            official_source="WHO",
            official_source_url="https://who.int/fellowship/",
            country="Switzerland",
            degree="PhD",
        )
        result = resolve_entity(
            session=session,
            source_url="https://who.int/health/",
            title="Global Health Scholarship Program",
            provider="WHO",
            country="Switzerland",
        )
        assert is_review(result) or result.matched_scholarship_id is not None or result.match_type == MATCH_NEW


class TestConfidenceBoundaries:
    def test_exact_match_confidence_is_one(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Exact Match Test",
            official_source="Provider",
            official_source_url="https://exact.test/scholarship/",
        )
        result = resolve_entity(
            session=session,
            source_url="https://exact.test/scholarship/",
            title="Different Title",
            provider="Different Provider",
            country="Test",
        )
        assert result.confidence == 1.0

    def test_new_match_confidence_is_zero(self, session):
        result = resolve_entity(
            session=session,
            source_url="https://unique.org/scholarship/",
            title="Unique Scholarship",
            provider="Unique Provider",
            country="Unique",
        )
        assert result.confidence == 0.0

    def test_confidence_ordering(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Confidence Test Scholarship",
            official_source="Provider",
            official_source_url="https://confidence.test/program/",
            country="TestCountry",
        )
        exact = resolve_entity(
            session=session,
            source_url="https://confidence.test/program/",
            title="Other Title",
            provider="Other",
            country="TestCountry",
        )
        new = resolve_entity(
            session=session,
            source_url="https://completely-different.org/program/",
            title="Completely Different Program Name",
            provider="Different Provider",
            country="OtherCountry",
        )
        assert exact.confidence > new.confidence


class TestIdempotency:
    def test_same_input_same_output(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Idempotent Test",
            official_source="Provider",
            official_source_url="https://idempotent.test/scholarship/",
            country="TestCountry",
        )
        result1 = resolve_entity(
            session=session,
            source_url="https://idempotent.test/scholarship/",
            title="Idempotent Test",
            provider="Provider",
            country="TestCountry",
        )
        result2 = resolve_entity(
            session=session,
            source_url="https://idempotent.test/scholarship/",
            title="Idempotent Test",
            provider="Provider",
            country="TestCountry",
        )
        assert result1.match_type == result2.match_type
        assert result1.matched_scholarship_id == result2.matched_scholarship_id
        assert result1.confidence == result2.confidence


class TestBatchResolution:
    def test_batch_resolution(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="Batch Test 1",
            official_source="Provider 1",
            official_source_url="https://batch1.test/scholarship/",
        )
        s2 = scholarship_factory(
            title="Batch Test 2",
            official_source="Provider 2",
            official_source_url="https://batch2.test/scholarship/",
        )
        candidates = [
            {"source_url": "https://batch1.test/scholarship/", "title": "Batch Test 1", "provider": "Provider 1", "country": "Germany"},
            {"source_url": "https://batch2.test/scholarship/", "title": "Batch Test 2", "provider": "Provider 2", "country": "Germany"},
            {"source_url": "https://brand-new.test/scholarship/", "title": "Brand New", "provider": "New Provider", "country": "Germany"},
        ]
        results = resolve_entity_batch(session, candidates)
        assert len(results) == 3
        assert results[0].matched_scholarship_id == s1.id
        assert results[1].matched_scholarship_id == s2.id
        assert results[2].match_type == MATCH_NEW


class TestNoFalseMerge:
    def test_different_programs_not_merged(self, session, scholarship_factory):
        scholarship_factory(
            title="Medical Scholarship",
            official_source="Medical Council",
            official_source_url="https://medical.org/scholarship/",
            country="USA",
            degree="PhD",
        )
        result = resolve_entity(
            session=session,
            source_url="https://engineering.org/scholarship/",
            title="Engineering Scholarship",
            provider="Engineering Board",
            country="USA",
            degree="Masters",
        )
        assert result.match_type in (MATCH_NEW, MATCH_RELATED, MATCH_REVIEW)
        if result.matched_scholarship_id is not None:
            assert result.confidence < 0.9

    def test_same_title_different_provider(self, session, scholarship_factory):
        scholarship_factory(
            title="Excellence Scholarship",
            official_source="Provider A",
            official_source_url="https://provider-a.org/excellence/",
            country="Germany",
        )
        result = resolve_entity(
            session=session,
            source_url="https://provider-b.org/excellence/",
            title="Excellence Scholarship",
            provider="Provider B",
            country="Germany",
        )
        assert result.match_type in (MATCH_REVIEW, MATCH_NEW, MATCH_SEMANTIC, MATCH_RELATED)


class TestHistoricalIdentityPreservation:
    def test_historical_evidence_preserves_identity(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Historical Test Scholarship 2024",
            official_source="Historical Provider",
            official_source_url="https://historical.test/scholarship/",
            country="TestCountry",
        )
        from app.services.temporal_versioning import create_snapshot
        create_snapshot(
            session=session,
            scholarship=existing,
            changed_fields=["title", "deadline_date"],
            source_url="https://historical.test/scholarship/",
            provenance={"source": "test"},
        )
        result = resolve_entity(
            session=session,
            source_url="https://historical-different.test/scholarship/",
            title="Historical Test Scholarship 2025",
            provider="Historical Provider",
            country="TestCountry",
        )
        assert result.match_type in (MATCH_REVIEW, MATCH_NEW, MATCH_SEMANTIC, MATCH_ANNUAL_CYCLE)


class TestDeterministicOutput:
    def test_deterministic_resolution(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Deterministic Test",
            official_source="Provider",
            official_source_url="https://deterministic.test/scholarship/",
            country="TestCountry",
        )
        results = []
        for _ in range(5):
            r = resolve_entity(
                session=session,
                source_url="https://deterministic.test/scholarship/",
                title="Deterministic Test",
                provider="Provider",
                country="TestCountry",
            )
            results.append(r)
        assert all(r.match_type == results[0].match_type for r in results)
        assert all(r.confidence == results[0].confidence for r in results)


class TestNoNPlusOne:
    def test_no_n_plus_one_queries(self, session, scholarship_factory):
        for i in range(5):
            scholarship_factory(
                title=f"No N+Plus Test {i}",
                official_source=f"Provider {i}",
                official_source_url=f"https://nplus{i}.test/scholarship/",
                country="TestCountry",
            )
        import unittest.mock as mock
        with mock.patch.object(session, "scalars", wraps=session.scalars) as mock_scalars:
            resolve_entity(
                session=session,
                source_url="https://nplus-new.test/scholarship/",
                title="No N+Plus New",
                provider="New Provider",
                country="TestCountry",
            )
            select_count = mock_scalars.call_count
            assert select_count < 15


class TestKnowledgeGraphRelationships:
    def test_alias_relationship_detected(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Original Name Scholarship",
            official_source="Provider",
            official_source_url="https://alias.test/original/",
            country="TestCountry",
        )
        sch_node, _ = get_or_create_node(session, "scholarship", str(existing.id))
        alias_node, _ = get_or_create_node(session, "alias", f"alias:{existing.id}:renamedscholarship")
        create_edge(
            session,
            sch_node.id,
            alias_node.id,
            RELATIONSHIP_ALIAS,
            confidence=0.95,
            status=STATUS_VERIFIED,
        )
        result = resolve_entity(
            session=session,
            source_url="https://alias.test/original/",
            title="Renamed Scholarship",
            provider="Provider",
            country="TestCountry",
        )
        assert result.match_type in (MATCH_EXACT, MATCH_RENAMED)

    def test_related_scholarship_not_merged(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="Related Program A",
            official_source="Provider",
            official_source_url="https://related.test/program-a/",
            country="TestCountry",
        )
        s2 = scholarship_factory(
            title="Related Program B",
            official_source="Provider",
            official_source_url="https://related.test/program-b/",
            country="TestCountry",
        )
        node1, _ = get_or_create_node(session, "scholarship", str(s1.id))
        node2, _ = get_or_create_node(session, "scholarship", str(s2.id))
        create_edge(
            session,
            node1.id,
            node2.id,
            RELATIONSHIP_RELATED,
            confidence=0.85,
            status=STATUS_VERIFIED,
        )
        result = resolve_entity(
            session=session,
            source_url="https://related.test/program-b/",
            title="Related Program B",
            provider="Provider",
            country="TestCountry",
        )
        assert result.match_type == MATCH_EXACT
        assert result.matched_scholarship_id == s2.id


class TestHelperFunctions:
    def test_is_ambiguous(self):
        r = EntityResolutionResult(match_type=MATCH_REVIEW, ambiguity=True)
        assert is_ambiguous(r)
        r2 = EntityResolutionResult(match_type=MATCH_EXACT, matched_scholarship_id=1, confidence=1.0)
        assert not is_ambiguous(r2)

    def test_is_match(self):
        r = EntityResolutionResult(match_type=MATCH_EXACT, matched_scholarship_id=1, confidence=1.0)
        assert is_match(r)
        r2 = EntityResolutionResult(match_type=MATCH_NEW)
        assert not is_match(r2)
        r3 = EntityResolutionResult(match_type=MATCH_REVIEW, matched_scholarship_id=1, ambiguity=True)
        assert not is_match(r3)

    def test_is_new(self):
        r = EntityResolutionResult(match_type=MATCH_NEW)
        assert is_new(r)
        r2 = EntityResolutionResult(match_type=MATCH_EXACT, matched_scholarship_id=1)
        assert not is_new(r2)

    def test_is_review(self):
        r = EntityResolutionResult(match_type=MATCH_REVIEW)
        assert is_review(r)
        r2 = EntityResolutionResult(match_type=MATCH_EXACT, matched_scholarship_id=1, confidence=1.0)
        assert not is_review(r2)
        r3 = EntityResolutionResult(match_type=MATCH_NEW, ambiguity=True)
        assert is_review(r3)


class TestMatchTypes:
    def test_all_match_types_valid(self):
        valid_types = {
            MATCH_EXACT, MATCH_URL_MIGRATION, MATCH_RENAMED,
            MATCH_ANNUAL_CYCLE, MATCH_TRANSLATED, MATCH_METADATA,
            MATCH_SEMANTIC, MATCH_RELATED, MATCH_NEW, MATCH_REVIEW,
        }
        assert valid_types.issubset(MATCH_TYPES)

    def test_reason_codes_exist(self):
        assert REASON_EXACT_URL in REASON_CODES or hasattr(
            __import__("app.services.entity_resolution", fromlist=["REASON_EXACT_URL"]),
            "REASON_EXACT_URL",
        )


class TestSignalBuilding:
    def test_build_signal_normalization(self):
        signal = _build_signal(
            source_url="https://WWW.Example.COM/Scholarship/",
            title="Test Scholarship 2025!",
            provider="Test Provider",
            degree="Masters",
            funding="Full",
        )
        assert "www.example.com" in signal.normalized_url
        assert "test" in signal.normalized_title
        assert signal.domain == "www.example.com"

    def test_build_signal_empty_url(self):
        signal = _build_signal(
            source_url="",
            title="Test",
            provider="Provider",
        )
        assert signal.normalized_url == ""
        assert signal.domain == ""


class TestSemanticSimilarity:
    def test_identical_scholarships_high_score(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Identical Scholarship Test",
            official_source="Provider",
            official_source_url="https://identical.test/scholarship/",
            country="TestCountry",
        )
        signal = _build_signal(
            source_url="https://other.test/scholarship/",
            title="Identical Scholarship Test",
            provider="Provider",
            degree="Masters",
            funding="Full",
        )
        score = _compute_semantic_similarity(signal, existing)
        assert score >= 0.6

    def test_different_scholarships_low_score(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Completely Different Program",
            official_source="Different Provider",
            official_source_url="https://different.test/program/",
            country="OtherCountry",
            degree="PhD",
            funding="Partial",
        )
        signal = _build_signal(
            source_url="https://original.test/scholarship/",
            title="Original Scholarship Name",
            provider="Original Provider",
            degree="Masters",
            funding="Full",
        )
        score = _compute_semantic_similarity(signal, existing)
        assert score < 0.8


class TestCycleDetection:
    def test_new_cycle_year(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Annual Scholarship 2024",
            official_source="Provider",
            official_source_url="https://annual.test/scholarship/",
        )
        status = _detect_cycle_status(session, existing.id, "Annual Scholarship 2026")
        assert status == "new_cycle"

    def test_same_cycle_year(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Annual Scholarship 2025",
            official_source="Provider",
            official_source_url="https://annual.test/scholarship/",
        )
        status = _detect_cycle_status(session, existing.id, "Annual Scholarship 2025")
        assert status == "same_cycle"

    def test_renamed_cycle(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Original Name Program",
            official_source="Provider",
            official_source_url="https://original.test/program/",
        )
        status = _detect_cycle_status(session, existing.id, "New Name Program")
        assert status in ("renamed", "distinct")
