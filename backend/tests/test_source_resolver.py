"""Tests for source URL resolution and classification.

Covers:
- Root-domain classification
- Exact program page classification
- Source resolution via link extraction
- Keyword-based link scoring
- Page caching
- Title tokenization
- Edge cases (empty, malformed URLs)
"""

import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-test-src-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.models import Base, Scholarship  # noqa: E402
from app.services.source_resolver import (  # noqa: E402
    SourceResolverService,
    SourceResolutionType,
    ResolvedSource,
    _classify_url,
    _extract_domain,
    _normalize_url,
    _tokenize_title,
)


class TestClassifyUrl:
    def test_root_domain_detected(self):
        result = _classify_url("https://www.daad.de")
        assert result == SourceResolutionType.ROOT_DOMAIN

    def test_exact_program_page(self):
        result = _classify_url("https://www.daad.de/en/scholarships/test-program")
        assert result == SourceResolutionType.EXACT_PROGRAM_PAGE

    def test_single_path_segment_is_application_page(self):
        result = _classify_url("https://www.university.edu/scholarships")
        assert result == SourceResolutionType.OFFICIAL_APPLICATION_PAGE

    def test_empty_url_is_invalid(self):
        result = _classify_url("")
        assert result == SourceResolutionType.INVALID

    def test_malformed_url_treated_as_root_domain(self):
        result = _classify_url("not-a-url")
        assert result == SourceResolutionType.ROOT_DOMAIN

    def test_normalize_adds_scheme(self):
        assert _normalize_url("www.example.com") == "https://www.example.com"
        assert _normalize_url("http://www.example.com") == "http://www.example.com"

    def test_extract_domain(self):
        assert _extract_domain("https://www.daad.de/page") == "www.daad.de"
        assert _extract_domain("https://example.com") == "example.com"
        assert _extract_domain("") is None


class TestSourceResolver:
    def test_already_program_page(self):
        resolver = SourceResolverService()
        result = resolver.resolve_source(
            "https://www.daad.de/en/scholarships/test-program",
            "DAAD Scholarship",
        )
        assert result.resolution_type == SourceResolutionType.EXACT_PROGRAM_PAGE
        assert result.confidence >= 0.9
        assert result.resolved_url is not None

    def test_empty_url_returns_invalid(self):
        resolver = SourceResolverService()
        result = resolver.resolve_source("", "Test")
        assert result.resolution_type == SourceResolutionType.INVALID
        assert result.confidence == 0.0
        assert result.resolved_url is None

    def test_root_domain_with_links(self):
        html = """
        <html><head><title>Study in Korea</title></head>
        <body>
            <a href="/en/plan/scholarship/gks">Global Korea Scholarship</a>
            <a href="/other/page">Other Page</a>
            <a href="/en/scholarships/list">Scholarships List</a>
        </body></html>
        """
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html
        mock_response.url = "https://studyinkorea.go.kr"

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://studyinkorea.go.kr",
                "Global Korea Scholarship",
            )

        assert result.resolution_type in (
            SourceResolutionType.EXACT_PROGRAM_PAGE,
            SourceResolutionType.OFFICIAL_APPLICATION_PAGE,
        )
        assert result.resolved_url is not None
        assert result.confidence > 0.4

    def test_root_domain_no_relevant_links(self):
        html = """
        <html><head><title>Home</title></head>
        <body>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
        </body></html>
        """
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://example-university.edu",
                "Test Scholarship",
            )

        assert result.resolution_type == SourceResolutionType.ROOT_DOMAIN
        assert result.resolved_url is None

    def test_inaccessible_domain(self):
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://www.daad.de",
                "DAAD Scholarship",
            )

        assert result.resolution_type == SourceResolutionType.INACCESSIBLE
        assert result.resolved_url is None

    def test_page_caching(self):
        resolver = SourceResolverService()

        call_count = [0]
        original_get = __import__("httpx").get

        def mock_get(url, **kwargs):
            call_count[0] += 1
            response = MagicMock()
            response.status_code = 200
            response.headers = {"content-type": "text/html"}
            response.text = "<html><body><a href='/scholarships'>Scholarships</a></body></html>"
            return response

        with patch("app.services.source_resolver.httpx.get", side_effect=mock_get):
            resolver.resolve_source("https://studyinkorea.go.kr", "GKS")
            resolver.resolve_source("https://studyinkorea.go.kr", "GKS")

        assert call_count[0] == 1


class TestTitleTokenization:
    def test_tokenize_removes_stopwords(self):
        tokens = _tokenize_title("Erasmus Mundus Joint Masters Scholarship")
        assert "erasmus" in tokens
        assert "mundus" in tokens
        assert "joint" in tokens
        assert "masters" in tokens
        assert "scholarship" in tokens
        assert "and" not in tokens
        assert "for" not in tokens

    def test_tokenize_short_words_filtered(self):
        tokens = _tokenize_title("PhD in CS")
        assert len(tokens) == 0 or "phd" not in tokens

    def test_tokenize_empty(self):
        assert _tokenize_title("") == []
        assert _tokenize_title(None) == []


class TestWeakPagePenalties:
    """Regression tests: weak pages must be penalized and exact pages must score higher."""

    def test_exact_scholarship_page_gets_high_confidence(self):
        html = """
        <html><head><title>Global Korea Scholarship Program</title></head>
        <body>
            <a href="/en/plan/scholarship/gks">Global Korea Scholarship</a>
            <a href="/en/plan/scholarship/gks/application">Application Guidelines</a>
        </body></html>
        """
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html
        mock_response.url = "https://studyinkorea.go.kr"

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://studyinkorea.go.kr",
                "Global Korea Scholarship",
            )

        assert result.resolution_type == SourceResolutionType.EXACT_PROGRAM_PAGE
        assert result.confidence >= 0.5
        assert result.resolved_url is not None

    def test_notification_list_is_penalized(self):
        html = """
        <html><head><title>Scholarship Notifications</title></head>
        <body>
            <a href="/en/notifications/list">Notification List</a>
            <a href="/en/scholarship/gks">Global Korea Scholarship</a>
        </body></html>
        """
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html
        mock_response.url = "https://studyinkorea.go.kr"

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://studyinkorea.go.kr",
                "Global Korea Scholarship",
            )

        assert result.resolved_url is not None
        assert "scholarship/gks" in result.resolved_url
        assert result.confidence > 0.3

    def test_root_domain_with_only_homepage_links_low_confidence(self):
        html = """
        <html><head><title>DAAD Home</title></head>
        <body>
            <a href="/about">About Us</a>
            <a href="/contact">Contact</a>
            <a href="/impressum">Imprint</a>
        </body></html>
        """
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://www.daad.de",
                "DAAD Scholarship",
            )

        assert result.resolved_url is None
        assert result.confidence <= 0.15

    def test_news_announcement_page_penalized(self):
        html = """
        <html><head><title>DAAD News</title></head>
        <body>
            <a href="/en/news/2024-scholarship">News Article</a>
            <a href="/en/scholarships/daad-program">DAAD Program</a>
            <a href="/en/news/archive">News Archive</a>
        </body></html>
        """
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://www.daad.de",
                "DAAD Scholarship Program",
            )

        assert result.resolved_url is not None
        assert "scholarships/daad-program" in result.resolved_url
        news_score = dict(result.alternatives).get("https://www.daad.de/en/news/2024-scholarship", 0)
        program_score = next(s for u, s in result.alternatives if "daad-program" in u)
        assert program_score > news_score

    def test_sitemap_and_search_pages_ignored(self):
        html = """
        <html><head><title>Site Map</title></head>
        <body>
            <a href="/sitemap.html">Sitemap</a>
            <a href="/search?q=scholarship">Search</a>
            <a href="/about">About</a>
        </body></html>
        """
        resolver = SourceResolverService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        with patch("app.services.source_resolver.httpx.get", return_value=mock_response):
            result = resolver.resolve_source(
                "https://www.university.edu",
                "Test Scholarship",
            )

        assert len([c for c in result.alternatives if c[0] is not None]) <= 0
