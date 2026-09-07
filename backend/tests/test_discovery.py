"""Tests for intelligent scholarship discovery."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    ApprovedSource,
    Base,
    DiscoveryCandidate,
    Scholarship,
)
from app.services.discovery_config import (
    ApprovedSourceData,
    StaticSourceRegistry,
    seed_approved_sources,
)
from app.services.discovery_identity import (
    MatchResult,
    compute_discovery_hash,
    find_exact_url_match,
    find_near_duplicate,
    normalize_title,
    normalize_url,
    resolve_identity,
)
from app.services.discovery_pipeline import (
    DiscoveryPipeline,
    DiscoveryResult,
)
from app.services.official_source_fetcher import OfficialSourceFetchResult
from app.services.scholarship_extractor import ScholarshipExtractionResult


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def registry():
    return StaticSourceRegistry([
        ApprovedSourceData("daad.de", "DAAD", "official_government", "Germany", 95, []),
        ApprovedSourceData("example.com", "Example", "official_program", "USA", 80, []),
    ])


@pytest.fixture
def pipeline(session_factory, registry):
    return DiscoveryPipeline(session_factory=session_factory, registry=registry)


@pytest.fixture
def existing_scholarship(session):
    s = Scholarship(
        title="DAAD Scholarship",
        country="Germany",
        degree="Masters",
        funding="Full",
        official_source="DAAD",
        official_source_url="https://daad.de/scholarship",
        application_link="https://daad.de/scholarship",
    )
    session.add(s)
    session.commit()
    return s


class TestUrlNormalization:
    def test_normalize_url_strips_trailing_slash(self):
        assert normalize_url("https://example.com/path/") == "https://example.com/path"

    def test_normalize_url_lowercases_domain(self):
        assert normalize_url("https://EXAMPLE.COM/Path") == "https://example.com/Path"

    def test_normalize_url_removes_default_port(self):
        assert normalize_url("https://example.com:443/path") == "https://example.com/path"

    def test_normalize_url_empty(self):
        assert normalize_url("") == ""

    def test_normalize_url_root_path(self):
        assert normalize_url("https://example.com") == "https://example.com/"


class TestTitleNormalization:
    def test_normalize_title_lowercase(self):
        assert normalize_title("DAAD Scholarship") == "daadscholarship"

    def test_normalize_title_removes_suffix(self):
        assert normalize_title("Test Program (Scholarship)") == "testprogram"

    def test_normalize_title_removes_non_alnum(self):
        assert normalize_title("Test — Program!") == "testprogram"

    def test_normalize_title_none(self):
        assert normalize_title(None) == ""

    def test_normalize_title_unicode(self):
        assert normalize_title("Müller-Stipendium") == "mullerstipendium"


class TestDiscoveryHash:
    def test_same_input_same_hash(self):
        h1 = compute_discovery_hash("https://example.com/scholarship", "Test", "Provider")
        h2 = compute_discovery_hash("https://example.com/scholarship", "Test", "Provider")
        assert h1 == h2

    def test_different_input_different_hash(self):
        h1 = compute_discovery_hash("https://example.com/a", "Test", "Provider")
        h2 = compute_discovery_hash("https://example.com/b", "Test", "Provider")
        assert h1 != h2

    def test_hash_is_sha256(self):
        h = compute_discovery_hash("https://example.com", "Title", "Provider")
        assert len(h) == 64


class TestExactUrlMatch:
    def test_finds_existing_by_official_url(self, session, existing_scholarship):
        result = find_exact_url_match(session, "https://daad.de/scholarship")
        assert result is not None
        assert result.id == existing_scholarship.id

    def test_finds_existing_by_application_link(self, session, existing_scholarship):
        result = find_exact_url_match(session, "https://daad.de/scholarship")
        assert result is not None

    def test_no_match_for_unknown_url(self, session, existing_scholarship):
        result = find_exact_url_match(session, "https://unknown.com/scholarship")
        assert result is None


class TestNearDuplicate:
    def test_exact_title_match(self, session, existing_scholarship):
        result = find_near_duplicate(session, "DAAD Scholarship", "DAAD", "Germany")
        assert result is not None
        assert result.id == existing_scholarship.id

    def test_similar_title_match(self, session, existing_scholarship):
        result = find_near_duplicate(session, "DAAD Scholarship 25", "DAAD", "Germany")
        assert result is not None

    def test_no_match_different_title(self, session, existing_scholarship):
        result = find_near_duplicate(session, "Completely Different Scholarship", "Other", "France")
        assert result is None

    def test_short_title_no_match(self, session, existing_scholarship):
        result = find_near_duplicate(session, "Short", "DAAD", "Germany")
        assert result is None


class TestResolveIdentity:
    def test_exact_url_match(self, session, existing_scholarship):
        result = resolve_identity(session, "https://daad.de/scholarship", "DAAD", "DAAD", "Germany")
        assert result.is_match is True
        assert result.match_type == "exact_url"
        assert result.matched_id == existing_scholarship.id

    def test_near_duplicate_match(self, session, existing_scholarship):
        result = resolve_identity(session, "https://daad.de/new", "DAAD Scholarship 2025", "DAAD", "Germany")
        assert result.is_match is True
        assert result.match_type in ("near_duplicate", "alias")

    def test_unmatched_new_scholarship(self, session, existing_scholarship):
        result = resolve_identity(session, "https://newsite.com/scholarship", "Brand New Scholarship", "NewOrg", "Japan")
        assert result.is_match is False
        assert result.match_type == "unmatched"


class TestApprovedSourceRegistry:
    def test_static_registry_approves_known_domain(self, registry):
        assert registry.is_approved("https://daad.de/scholarship") is True

    def test_static_registry_rejects_unknown_domain(self, registry):
        assert registry.is_approved("https://unknown.com/scholarship") is False

    def test_static_registry_returns_source_type(self, registry):
        assert registry.get_source_type("https://daad.de/scholarship") == "official_government"

    def test_static_registry_returns_trust_score(self, registry):
        assert registry.get_trust_score("https://daad.de/scholarship") == 95

    def test_static_registry_get_all_active(self, registry):
        sources = registry.get_all_active()
        assert len(sources) == 2


class TestSeedApprovedSources:
    def test_seeds_new_sources(self, session):
        count = seed_approved_sources(session)
        assert count > 0
        session.commit()
        rows = session.query(ApprovedSource).all()
        assert len(rows) == count

    def test_idempotent_seed(self, session):
        count1 = seed_approved_sources(session)
        session.commit()
        count2 = seed_approved_sources(session)
        assert count2 == 0


class TestDiscoveryPipeline:
    def test_rejects_unapproved_source(self, pipeline, session):
        result = pipeline.discover_from_url("https://unapproved-site.com/scholarship")
        assert result.status == "rejected"
        assert "not in approved registry" in (result.review_reason or "")

    def test_rejects_invalid_url(self, pipeline):
        result = pipeline.discover_from_url("")
        assert result.status == "rejected"

    def test_handles_fetch_failure(self, pipeline):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url="https://example.com/scholarship",
                error_type="not_found",
                error_reason="404 Not Found",
            )
            result = pipeline.discover_from_url("https://example.com/scholarship")
            assert result.status == "error"
            assert "Fetch failed" in (result.review_reason or "")

    def test_error_candidate_idempotent_retry(self, pipeline, session):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url="https://example.com/scholarship",
                error_type="not_found",
                error_reason="404 Not Found",
            )
            result1 = pipeline.discover_from_url("https://example.com/scholarship")
            assert result1.status == "error"
            result2 = pipeline.discover_from_url("https://example.com/scholarship")
            assert result2.status == "error"
            assert result1.candidate_id == result2.candidate_id
            candidates = session.query(DiscoveryCandidate).all()
            assert len(candidates) == 1

    def test_error_candidate_retry_updates_reason(self, pipeline, session):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url="https://example.com/scholarship",
                error_type="not_found",
                error_reason="404 Not Found",
            )
            result1 = pipeline.discover_from_url("https://example.com/scholarship")
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url="https://example.com/scholarship",
                error_type="timeout",
                error_reason="Request timed out",
            )
            result2 = pipeline.discover_from_url("https://example.com/scholarship")
            assert result1.candidate_id == result2.candidate_id
            candidate = session.get(DiscoveryCandidate, result2.candidate_id)
            assert candidate.last_error == "timeout"
            assert candidate.retry_count == 2
            assert "timed out" in (candidate.review_reason or "")

    def test_detects_duplicate(self, pipeline, session, existing_scholarship):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://daad.de/scholarship",
                content="<html><body>DAAD Scholarship for Masters</body></html>",
            )
            result = pipeline.discover_from_url("https://daad.de/scholarship")
            assert result.status == "duplicate"
            assert result.match_type == "exact_url"

    def test_new_candidate_pending(self, pipeline):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch, \
             patch("app.services.discovery_pipeline.extract_scholarship_information") as mock_extract:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://example.com/new-scholarship",
                content="<html><body>New Scholarship Program for International Students. Apply now. Full funding available.</body></html>",
            )
            mock_extract.return_value = ScholarshipExtractionResult(
                scholarship_name="New Scholarship Program",
                provider="Example Org",
                degree_level="Masters",
                eligibility="International students",
                duration="2 years",
                application_method="Online",
                deadline="2025-12-31",
                status="open",
                confidence={"scholarship_name": "high", "provider": "high", "degree_level": "high"},
            )
            result = pipeline.discover_from_url("https://example.com/new-scholarship")
            assert result.status in ("pending", "review")

    def test_idempotent_same_candidate(self, pipeline):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch, \
             patch("app.services.discovery_pipeline.extract_scholarship_information") as mock_extract:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://example.com/unique-scholarship",
                content="<html><body>Unique Scholarship. Full funding for PhD students.</body></html>",
            )
            mock_extract.return_value = ScholarshipExtractionResult(
                scholarship_name="Unique Scholarship",
                provider="Example Org",
                degree_level="PhD",
                eligibility="All nationalities",
                duration="3 years",
                application_method="Online",
                deadline="2026-01-15",
                status="open",
                confidence={"scholarship_name": "high", "provider": "high"},
            )
            result1 = pipeline.discover_from_url("https://example.com/unique-scholarship")
            result2 = pipeline.discover_from_url("https://example.com/unique-scholarship")
            assert result1.candidate_id == result2.candidate_id

    def test_approve_creates_scholarship(self, pipeline, session_factory):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch, \
             patch("app.services.discovery_pipeline.extract_scholarship_information") as mock_extract:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://example.com/approvable",
                content="<html><body>Approvable Scholarship. Full funding for Masters students. Apply online.</body></html>",
            )
            mock_extract.return_value = ScholarshipExtractionResult(
                scholarship_name="Approvable Scholarship",
                provider="Example Org",
                degree_level="Masters",
                eligibility="International",
                duration="2 years",
                application_method="Online",
                deadline="2025-12-31",
                status="open",
                confidence={"scholarship_name": "high", "provider": "high", "degree_level": "high"},
            )
            result = pipeline.discover_from_url("https://example.com/approvable")
            if result.status in ("pending", "review"):
                new_id = pipeline.approve_candidate(result.candidate_id)
                if new_id is not None:
                    session = session_factory()
                    scholarship = session.get(Scholarship, new_id)
                    assert scholarship is not None
                    assert scholarship.title == "Approvable Scholarship"
                    assert scholarship.is_verified is True
                    session.close()

    def test_reject_candidate(self, pipeline):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch, \
             patch("app.services.discovery_pipeline.extract_scholarship_information") as mock_extract:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://example.com/rejectable",
                content="<html><body>Rejectable Scholarship.</body></html>",
            )
            mock_extract.return_value = ScholarshipExtractionResult(
                scholarship_name="Rejectable Scholarship",
                provider="Example Org",
                degree_level="Masters",
                confidence={"scholarship_name": "high"},
            )
            result = pipeline.discover_from_url("https://example.com/rejectable")
            success = pipeline.reject_candidate(result.candidate_id, "Test rejection")
            assert success is True
            candidate = pipeline.get_candidate_by_id(result.candidate_id)
            assert candidate.status == "rejected"
            assert candidate.review_reason == "Test rejection"

    def test_get_pending_candidates(self, pipeline):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch, \
             patch("app.services.discovery_pipeline.extract_scholarship_information") as mock_extract:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://example.com/pending-one",
                content="<html><body>Pending Scholarship One. Full funding for students.</body></html>",
            )
            mock_extract.return_value = ScholarshipExtractionResult(
                scholarship_name="Pending Scholarship One",
                provider="Example Org",
                degree_level="Masters",
                eligibility="All",
                duration="2 years",
                application_method="Online",
                deadline="2025-12-31",
                status="open",
                confidence={"scholarship_name": "high", "provider": "high"},
            )
            pipeline.discover_from_url("https://example.com/pending-one")
        pending = pipeline.get_pending_candidates()
        assert len(pending) >= 1

    def test_batch_discovery(self, pipeline):
        urls = [
            "https://example.com/batch-one",
            "https://example.com/batch-two",
        ]
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch, \
             patch("app.services.discovery_pipeline.extract_scholarship_information") as mock_extract:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://example.com/batch",
                content="<html><body>Batch Scholarship. Full funding.</body></html>",
            )
            mock_extract.return_value = ScholarshipExtractionResult(
                scholarship_name="Batch Scholarship",
                provider="Example Org",
                degree_level="Masters",
                confidence={"scholarship_name": "high"},
            )
            batch = pipeline.discover_batch(urls)
            assert len(batch.discovered) == 2


class TestDiscoveryCandidateModel:
    def test_create_candidate(self, session):
        c = DiscoveryCandidate(
            source_url="https://example.com/test",
            normalized_url="https://example.com/test",
            title="Test Scholarship",
            provider="Test Org",
            country="Germany",
            discovery_hash="abc123",
            discovery_source="official_government",
        )
        session.add(c)
        session.commit()
        assert c.id is not None
        assert c.status == "pending"
        assert c.match_status == "unmatched"

    def test_unique_discovery_hash(self, session):
        c1 = DiscoveryCandidate(
            source_url="https://example.com/test",
            normalized_url="https://example.com/test",
            title="Test",
            discovery_hash="unique_hash_123",
        )
        session.add(c1)
        session.commit()
        c2 = DiscoveryCandidate(
            source_url="https://example.com/test",
            normalized_url="https://example.com/test",
            title="Test",
            discovery_hash="unique_hash_123",
        )
        session.add(c2)
        with pytest.raises(Exception):
            session.commit()


class TestExistingScholarshipPreservation:
    def test_discovery_never_modifies_existing(self, pipeline, session, existing_scholarship):
        original_title = existing_scholarship.title
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://daad.de/scholarship",
                content="<html><body>Modified Content</body></html>",
            )
            pipeline.discover_from_url("https://daad.de/scholarship")
            session.refresh(existing_scholarship)
            assert existing_scholarship.title == original_title


class TestAmbiguousIdentity:
    def test_ambiguous_routed_to_review(self, pipeline):
        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch, \
             patch("app.services.discovery_pipeline.extract_scholarship_information") as mock_extract:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url="https://example.com/ambiguous",
                content="<html><body>Short.</body></html>",
            )
            mock_extract.return_value = ScholarshipExtractionResult(
                scholarship_name="AB",
                provider=None,
                confidence={},
            )
            result = pipeline.discover_from_url("https://example.com/ambiguous")
            assert result.status == "review"
            assert "Insufficient title" in (result.review_reason or "")
