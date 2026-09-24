from __future__ import annotations

"""Append chunk 2: domain resolution tests."""

import pytest

from app.services.discovery_config import (
    ApprovedSourceData,
    StaticSourceRegistry,
)
from app.services.official_page_discovery import (
    DiscoveryConfidence,
    DomainResolver,
    PageRelevanceScorer,
    canonicalize_url,
)


@pytest.fixture
def registry():
    return StaticSourceRegistry([
        ApprovedSourceData("daad.de", "DAAD", "official_government", "Germany", 95, []),
        ApprovedSourceData("example.com", "Example", "official_program", "USA", 80, []),
    ])


class TestDomainResolver:
    def test_registry_exact_match(self, registry):
        resolver = DomainResolver(registry)
        result = resolver.resolve("https://www.daad.de/en/", "DAAD Scholarship", "DAAD")
        assert result.official_domain == "daad.de"
        assert result.is_official_domain is True
        assert result.trust_score == 95
        assert result.source_type == "official_government"
        assert result.confidence == DiscoveryConfidence.HIGH

    def test_registry_suffix_match(self, registry):
        resolver = DomainResolver(registry)
        result = resolver.resolve("https://sub.daad.de/page", "Test", None)
        assert result.official_domain == "daad.de"
        assert result.is_official_domain is True

    def test_no_url_returns_unverified(self, registry):
        resolver = DomainResolver(registry)
        result = resolver.resolve(None, "Test", None)
        assert result.official_domain is None
        assert result.is_official_domain is False
        assert result.confidence == DiscoveryConfidence.UNVERIFIED

    def test_unknown_domain_returns_unverified(self, registry):
        resolver = DomainResolver(registry)
        result = resolver.resolve("https://unknown.example.org/page", "Test", None)
        assert result.official_domain == "unknown.example.org"
        assert result.is_official_domain is False
        assert result.confidence == DiscoveryConfidence.UNVERIFIED

    def test_official_suffix_match(self, registry):
        resolver = DomainResolver(registry)
        result = resolver.resolve("https://www.university.edu/scholarships", "Test", None)
        assert result.is_official_domain is True
        assert result.trust_score == 70
        assert result.confidence == DiscoveryConfidence.MEDIUM

    def test_provider_name_fallback(self, registry):
        resolver = DomainResolver(registry)
        result = resolver.resolve("https://www.example.org/page", "Test", "DAAD")
        assert result.official_domain == "daad.de"
        assert result.is_official_domain is True
        assert result.confidence == DiscoveryConfidence.MEDIUM



"""Chunk 3: page relevance scoring tests."""

import pytest

from app.services.official_page_discovery import (
    OfficialPageCandidate,
    PageKind,
    PageRelevanceScorer,
)


class TestPageRelevanceScorer:
    def test_title_token_overlap_in_url(self):
        scorer = PageRelevanceScorer("DAAD Scholarship")
        score = scorer.score_url("https://daad.de/en/scholarships/daad-program")
        assert score > 0.2

    def test_title_token_overlap_in_text(self):
        scorer = PageRelevanceScorer("DAAD Scholarship")
        score = scorer.score_url(
            "https://daad.de/en/news",
            snippet="The DAAD Scholarship is now open for applications.",
        )
        assert score > 0.3

    def test_exact_title_bonus(self):
        scorer = PageRelevanceScorer("DAAD Scholarship")
        score = scorer.score_url(
            "https://daad.de/en/announcements",
            title="DAAD Scholarship",
            snippet="Details about the DAAD Scholarship program.",
        )
        assert score >= 0.5

    def test_non_trustworthy_path_penalty(self):
        scorer = PageRelevanceScorer("DAAD Scholarship")
        score = scorer.score_url("https://daad.de/login")
        assert score < 0.3

    def test_score_candidate(self):
        scorer = PageRelevanceScorer("DAAD Scholarship")
        from app.services.official_page_discovery import DiscoveryConfidence
        cand = OfficialPageCandidate(
            url="https://daad.de/en/scholarships/daad",
            normalized_url="https://daad.de/en/scholarships/daad",
            page_kind=PageKind.SCHOLARSHIP_PAGE,
            source_domain="daad.de",
            is_official_domain=True,
            trust_score=95,
            relevance_score=0.0,
            confidence=DiscoveryConfidence.MEDIUM,
            discovery_method="in_domain_title_match",
            title="DAAD Scholarship",
        )
        score = scorer.score_candidate(cand)
        assert score > 0.3



"""Chunk 4: discovery service tests with mocked fetcher."""

from unittest.mock import patch

import pytest

from app.services.discovery_config import (
    ApprovedSourceData,
    StaticSourceRegistry,
)
from app.services.official_page_discovery import (
    DiscoveryConfidence,
    DiscoveryOutcome,
    OfficialPageDiscoveryService,
    PageKind,
    canonicalize_url,
)
from app.services.image_discovery import PageFetchResult


@pytest.fixture
def registry():
    return StaticSourceRegistry([
        ApprovedSourceData("daad.de", "DAAD", "official_government", "Germany", 95, []),
    ])


class FakeDiscovery:
    """Deterministic ImageDiscoveryService stand-in."""

    def __init__(self, pages=None):
        self._pages = pages or {}
        self.fetch_calls = []

    def fetch_page(self, url):
        self.fetch_calls.append(url)
        canon = canonicalize_url(url)
        for key in (canon, url):
            if key in self._pages:
                content, status = self._pages[key]
                return PageFetchResult(url=canon, status_code=status, content=content)
        return PageFetchResult(url=canon, status_code=404, content=None, error="not found")


def _page(title_text="DAAD Scholarship", body="", links=None):
    title = title_text or "DAAD Scholarship"
    links_html = ""
    for link in links or []:
        links_html += "<a href=\"" + link + "\">" + link + "</a>"
    return (
        "<!DOCTYPE html><html><head><title>" + title + "</title>"
        '<meta name="description" content="Official ' + title + ' page">'
        "</head><body>" + body + links_html + "</body></html>"
    )


class TestOfficialPageDiscoveryService:
    def _service(self, pages, registry=None):
        fake = FakeDiscovery(pages)
        return OfficialPageDiscoveryService(
            discovery=fake,
            registry=registry or StaticSourceRegistry([
                ApprovedSourceData("daad.de", "DAAD", "official_government", "Germany", 95, []),
            ]),
            max_pages_per_scholarship=10,
            max_requests_per_scholarship=50,
        ), fake

    def test_discover_no_url(self):
        svc, _ = self._service({})
        result = svc.discover(1, "DAAD Scholarship", None, "DAAD")
        assert result.error == "no_official_source_url"
        assert result.candidates == []

    def test_discover_root_page(self):
        pages = {
            "https://daad.de/": (_page("DAAD", "Welcome to DAAD"), 200),
        }
        svc, fake = self._service(pages)
        result = svc.discover(1, "DAAD Scholarship", "https://daad.de/", "DAAD")
        assert result.is_official_domain is True
        assert result.official_domain == "daad.de"
        assert len(result.candidates) >= 1
        assert result.requests_made >= 1

    def test_discover_trusted_candidate(self):
        pages = {
            "https://daad.de/": (
                _page("DAAD", "Welcome", links=["https://daad.de/en/scholarships/daad-program"]),
                200,
            ),
            "https://daad.de/en/scholarships/daad-program": (
                _page("DAAD Scholarship", "The DAAD Scholarship is open"), 200,
            ),
        }
        svc, _ = self._service(pages)
        result = svc.discover(1, "DAAD Scholarship", "https://daad.de/", "DAAD")
        kinds = {c.page_kind for c in result.candidates}
        assert PageKind.ROOT_DOMAIN in kinds
        assert result.trusted_candidates, "expected at least one trusted candidate"
        assert any(c.is_trustworthy for c in result.trusted_candidates)

    def test_discover_bounded(self):
        pages = {"https://daad.de/": (_page("DAAD"), 200)}
        svc, _ = self._service(pages)
        result = svc.discover(1, "Test", "https://daad.de/", None)
        assert len(result.candidates) <= 10

    def test_discover_dedup(self):
        pages = {
            "https://daad.de/": (
                _page("DAAD", "Welcome", links=["https://daad.de/en/scholarships/"]),
                200,
            ),
            "https://daad.de/en/scholarships/": (_page("Scholarships"), 200),
        }
        svc, _ = self._service(pages)
        result = svc.discover(1, "Test", "https://daad.de/", None)
        urls = [c.normalized_url for c in result.candidates]
        assert len(urls) == len(set(urls)), "candidates must be deduplicated"



"""Chunk 5: announcement/news/press discovery and wrong-page rejection."""

from app.services.discovery_config import (
    ApprovedSourceData,
    StaticSourceRegistry,
)
from app.services.official_page_discovery import (
    OfficialPageDiscoveryService,
    PageKind,
    canonicalize_url,
)
from app.services.image_discovery import PageFetchResult


class FakeDiscovery:
    """Deterministic ImageDiscoveryService stand-in."""

    def __init__(self, pages=None):
        self._pages = pages or {}
        self.fetch_calls = []

    def fetch_page(self, url):
        self.fetch_calls.append(url)
        canon = canonicalize_url(url)
        for key in (canon, url):
            if key in self._pages:
                content, status = self._pages[key]
                return PageFetchResult(url=canon, status_code=status, content=content)
        return PageFetchResult(url=canon, status_code=404, content=None, error="not found")


def _page(title_text="DAAD Scholarship", body="", links=None):
    title = title_text or "DAAD Scholarship"
    links_html = ""
    for link in links or []:
        links_html += "<a href=\"" + link + "\">" + link + "</a>"
    return (
        "<!DOCTYPE html><html><head><title>" + title + "</title>"
        '<meta name="description" content="Official ' + title + ' page">'
        "</head><body>" + body + links_html + "</body></html>"
    )


class TestAnnouncementNewsPressDiscovery:
    def _service(self, pages):
        fake = FakeDiscovery(pages)
        return OfficialPageDiscoveryService(
            discovery=fake,
            registry=StaticSourceRegistry([
                ApprovedSourceData("daad.de", "DAAD", "official_government", "Germany", 95, []),
            ]),
            max_pages_per_scholarship=10,
            max_requests_per_scholarship=50,
        ), fake

    def test_announcement_page_discovered(self):
        pages = {
            "https://daad.de/": (
                _page("DAAD", "Welcome", links=["https://daad.de/en/announcements/daad-2026"]),
                200,
            ),
            "https://daad.de/en/announcements/daad-2026": (
                _page("DAAD Announcement", "The DAAD Scholarship announcement is now published."), 200,
            ),
        }
        svc, _ = self._service(pages)
        result = svc.discover(1, "DAAD Scholarship", "https://daad.de/", "DAAD")
        kinds = {c.page_kind for c in result.candidates}
        assert PageKind.ANNOUNCEMENT in kinds or PageKind.NEWS in kinds

    def test_news_page_discovered(self):
        pages = {
            "https://daad.de/": (
                _page("DAAD", "Welcome", links=["https://daad.de/en/news/daad-story"]),
                200,
            ),
            "https://daad.de/en/news/daad-story": (
                _page("DAAD News", "A news story about the DAAD Scholarship."), 200,
            ),
        }
        svc, _ = self._service(pages)
        result = svc.discover(1, "DAAD Scholarship", "https://daad.de/", "DAAD")
        assert any(c.page_kind in (PageKind.NEWS, PageKind.PRESS) for c in result.candidates)

    def test_press_page_discovered(self):
        pages = {
            "https://daad.de/": (
                _page("DAAD", "Welcome", links=["https://daad.de/en/press/daad-release"]),
                200,
            ),
            "https://daad.de/en/press/daad-release": (
                _page("DAAD Press", "A press release about the DAAD Scholarship."), 200,
            ),
        }
        svc, _ = self._service(pages)
        result = svc.discover(1, "DAAD Scholarship", "https://daad.de/", "DAAD")
        assert any(c.page_kind == PageKind.PRESS for c in result.candidates)

    def test_third_party_page_not_trusted(self):
        pages = {
            "https://daad.de/": (
                _page("DAAD", "Welcome", links=["https://third-party.example.com/scholarship"]),
                200,
            ),
            "https://third-party.example.com/scholarship": (
                _page("Third Party", "A third-party page about the DAAD Scholarship."), 200,
            ),
        }
        svc, _ = self._service(pages)
        result = svc.discover(1, "DAAD Scholarship", "https://daad.de/", "DAAD")
        # Third-party pages should not be marked as official domain.
        for c in result.candidates:
            if "third-party.example.com" in c.url:
                assert c.is_official_domain is False

    def test_non_trustworthy_path_not_trusted(self):
        pages = {
            "https://daad.de/": (
                _page("DAAD", "Welcome", links=["https://daad.de/login"]),
                200,
            ),
            "https://daad.de/login": (
                _page("Login", "Please log in to access the DAAD Scholarship."), 200,
            ),
        }
        svc, _ = self._service(pages)
        result = svc.discover(1, "DAAD Scholarship", "https://daad.de/", "DAAD")
        for c in result.candidates:
            if c.normalized_url == "https://daad.de/login":
                assert c.is_trustworthy is False



"""Chunk 6: orchestrator tests."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.discovery_config import seed_approved_sources
from app.services.image_discovery_orchestrator import (
    ImageDiscoveryOrchestrator,
    OrchestratorRunResult,
    TrustworthyImageStatus,
)
from app.services.official_page_discovery import (
    OfficialPageCandidate,
    OfficialPageDiscoveryService,
    PageKind,
)


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
def seeded_sources(session):
    seed_approved_sources(session)
    session.commit()


def _scholarship(session, title="DAAD Scholarship", url="https://daad.de/en/scholarships/daad", image_url=None, verified_at=None):
    s = Scholarship(
        title=title,
        country="Germany",
        degree="Masters",
        funding="Full",
        official_source="DAAD",
        official_source_url=url,
        application_link=url,
        image_url=image_url,
        image_verified_at=verified_at,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s




class _MockFetch:
    def __init__(self, content):
        self.content = content
        self.error = None
        self.status_code = 200
        self.url = "https://daad.de/"


class _MockValidation:
    def __init__(self, image_url, domain, is_valid, status, image_kind=None):
        self.candidate = type("C", (), {"image_url": image_url, "page_url": "https://daad.de/", "alt_text": "DAAD Scholarship", "html_context": None, "discovery_method": "root_domain_fetch"})()
        self.is_reachable = True
        self.http_status = 200
        self.content_type = "image/jpeg"
        self.is_valid_image = is_valid
        self.is_official_domain = True
        self.image_domain = domain
        self.source_domain = "daad.de"
        self.width = 100
        self.height = 100
        self.is_generic_image = False
        self.is_ui_asset = False
        self.is_svg = False
        self.aspect_ratio = 1.0
        self.is_duplicate = False
        self.duplicate_of = None
        self.licensing_status = "unknown"
        self.relevance_score = 0.8
        self.confidence = "HIGH"
        self.status = type("S", (), {"value": status})()
        self.rejection_reasons = []
        self.human_review_reason = None
        self.checked_at = None
        self.file_size_bytes = 1000
        self.image_analysis = None
        self.result_id = "mock"
        self.retry_count = 0
        self.failure_reason = None
        self.image_kind = image_kind


class TestOrchestrator:

    def test_no_trustworthy_image(self, session, seeded_sources):
        svc = OfficialPageDiscoveryService(
            discovery=_FakeDiscovery({}),
        )
        orch = ImageDiscoveryOrchestrator(
            session_factory=session_factory,
            page_discovery_service=svc,
            dry_run=True,
        )
        result = orch.run(
            scholarship_id=1,
            scholarship_title="DAAD Scholarship",
            official_source_url="https://daad.de/",
            official_source_name="DAAD",
            session=session,
        )
        assert isinstance(result, OrchestratorRunResult)
        assert result.status == TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE

    def test_dry_run_does_not_persist(self, session, seeded_sources):
        s = _scholarship(session, image_url="https://old.example.com/old.jpg")
        svc = OfficialPageDiscoveryService(
            discovery=_FakeDiscoveryWithImage(),
        )
        orch = ImageDiscoveryOrchestrator(
            session_factory=session_factory,
            page_discovery_service=svc,
            dry_run=True,
        )
        with patch("app.services.image_discovery.ImageDiscoveryService") as MockDisc,             patch("app.services.image_validator.ImageValidator") as MockVal:
            MockDisc.return_value.fetch_page.return_value = _MockFetch(
                '<html><body><img src="https://daad.de/img/daad.jpg" alt="DAAD Scholarship"></body></html>'
            )
            MockVal.return_value.validate_candidates.return_value = [
                _MockValidation("https://daad.de/img/daad.jpg", "daad.de", True, "approved"),
            ]
            result = orch.run(
                scholarship_id=s.id,
                scholarship_title="DAAD Scholarship",
                official_source_url="https://daad.de/",
                official_source_name="DAAD",
                session=session,
            )
        assert result.persisted is False
        # Existing image must be untouched.
        session.refresh(s)
        assert s.image_url == "https://old.example.com/old.jpg"

    def test_idempotent_dry_run(self, session, seeded_sources):
        s = _scholarship(session, image_url=None)
        svc = OfficialPageDiscoveryService(
            discovery=_FakeDiscoveryWithImage(),
        )
        orch = ImageDiscoveryOrchestrator(
            session_factory=session_factory,
            page_discovery_service=svc,
            dry_run=True,
        )
        with patch("app.services.image_discovery.ImageDiscoveryService") as MockDisc,             patch("app.services.image_validator.ImageValidator") as MockVal:
            MockDisc.return_value.fetch_page.return_value = _MockFetch(
                '<html><body><img src="https://daad.de/img/daad.jpg" alt="DAAD Scholarship"></body></html>'
            )
            MockVal.return_value.validate_candidates.return_value = [
                _MockValidation("https://daad.de/img/daad.jpg", "daad.de", True, "approved"),
            ]
            r1 = orch.run(s.id, "DAAD Scholarship", "https://daad.de/", "DAAD", session=session)
            r2 = orch.run(s.id, "DAAD Scholarship", "https://daad.de/", "DAAD", session=session)
        assert r1.status == r2.status
        assert len(r1.image_results) == len(r2.image_results)


class _FakeDiscovery:
    def __init__(self, pages):
        self._pages = pages

    def fetch_page(self, url):
        from app.services.image_discovery import PageFetchResult
        return PageFetchResult(url=url, status_code=404, content=None, error="not found")

    def discover(self, scholarship_id, title, url, name):
        from app.services.official_page_discovery import DiscoveryOutcome
        return DiscoveryOutcome(
            scholarship_id=scholarship_id,
            scholarship_title=title or "",
            official_source_url=url,
            official_domain=None,
            is_official_domain=False,
        )


class _FakeDiscoveryWithImage:
    def fetch_page(self, url):
        from app.services.image_discovery import PageFetchResult
        if url == "https://daad.de/":
            return PageFetchResult(
                url=url,
                status_code=200,
                content='<html><body><img src="https://daad.de/img/daad.jpg" alt="DAAD Scholarship"></body></html>',
            )
        return PageFetchResult(url=url, status_code=404, content=None, error="not found")

    def discover(self, scholarship_id, title, url, name):
        from app.services.official_page_discovery import (
            DiscoveryOutcome,
            OfficialPageCandidate,
        )
        cand = OfficialPageCandidate(
            url="https://daad.de/",
            normalized_url="https://daad.de/",
            page_kind=PageKind.ROOT_DOMAIN,
            source_domain="daad.de",
            is_official_domain=True,
            trust_score=95,
            relevance_score=0.8,
            discovery_method="root_domain_fetch",
            title="DAAD",
            is_trustworthy=True,
        )
        return DiscoveryOutcome(
            scholarship_id=scholarship_id,
            scholarship_title=title or "",
            official_source_url=url,
            official_domain="daad.de",
            is_official_domain=True,
            candidates=[cand],
            trusted_candidates=[cand],
        )


