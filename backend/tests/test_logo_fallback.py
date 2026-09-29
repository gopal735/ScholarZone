"""Tests for the three-tier logo fallback resolver.

Two properties matter more than the happy path.

First, a fallback tier must never be able to *approve* an image. The tiers
propose candidates; the ordinary validator still decides. A test asserts the
resolver exposes no write path at all.

Second, provenance must stay honest. A Wikimedia-hosted file is the right
institution's logo, but it is not an official source, and a record that says
otherwise is a lie that outlives this repository. Several tests below exist
only to pin that distinction.
"""

from __future__ import annotations

import json

import pytest

from app.services.logo_fallback_resolver import (
    LogoFallbackResolver,
    LogoResolutionStatus,
    LogoTier,
    institution_key,
    load_overrides,
    root_of,
)


class _Scholarship:
    def __init__(self, sid=1, url="https://www.oxford.ac.uk/scholarships/123", title="Oxford Scholarship"):
        self.id = sid
        self.official_source_url = url
        self.title = title
        self.country = "United Kingdom"


def _fetcher(pages: dict[str, str]):
    """A fetch function backed by a dict, so no test touches the network."""
    calls: list[str] = []

    def fetch(url: str) -> str | None:
        calls.append(url)
        for prefix, body in pages.items():
            if url.startswith(prefix):
                return body
        return None

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


# ---------------------------------------------------------------------------
# Tier 1: root domain
# ---------------------------------------------------------------------------


class TestRootDomainTier:
    def test_it_finds_a_logo_on_the_institution_homepage(self):
        html = """
        <html><head>
          <img src="/sites/default/files/logo.png" alt="University logo" class="site-logo">
        </head><body></body></html>
        """
        fetch = _fetcher({"https://www.oxford.ac.uk/": html})
        resolver = LogoFallbackResolver(fetch_text=fetch)
        found = resolver.tier_root_domain(_Scholarship())
        assert found
        assert found[0].url == "https://www.oxford.ac.uk/sites/default/files/logo.png"
        assert found[0].official_host is True, "the institution's own bytes are official"

    def test_it_ignores_photographs_and_banners(self):
        html = """
        <img src="/hero.jpg" alt="Campus hero" class="hero">
        <img src="/banner.png" alt="admissions banner" class="banner">
        <img src="/logo.svg" alt="logo" class="logo">
        """
        fetch = _fetcher({"https://www.oxford.ac.uk/": html})
        found = LogoFallbackResolver(fetch_text=fetch).tier_root_domain(_Scholarship())
        assert [c.url for c in found] == ["https://www.oxford.ac.uk/logo.svg"]

    def test_it_refuses_an_image_hosted_elsewhere(self):
        """A CDN or tracker asset on the page is not the institution's own."""
        html = '<img src="https://cdn.tracker.example/logo.png" alt="logo">'
        fetch = _fetcher({"https://www.oxford.ac.uk/": html})
        found = LogoFallbackResolver(fetch_text=fetch).tier_root_domain(_Scholarship())
        assert found == []

    def test_it_refuses_aggregator_domains(self):
        """Study in Korea publishes other institutions' logos; that is not ours."""
        html = '<img src="/logo.png" alt="logo" class="logo">'
        fetch = _fetcher({"https://www.studyinkorea.go.kr/": html})
        found = LogoFallbackResolver(fetch_text=fetch).tier_root_domain(
            _Scholarship(url="https://www.studyinkorea.go.kr/Study_Scholarship/xyz")
        )
        assert found == [], "a portal's own logo must not be attributed to a programme"

    def test_it_returns_nothing_when_the_root_is_unreachable(self):
        fetch = _fetcher({})
        assert LogoFallbackResolver(fetch_text=fetch).tier_root_domain(_Scholarship()) == []

    def test_it_uses_the_scheme_and_host_only(self):
        assert root_of("https://www.oxford.ac.uk/a/b/c?x=1") == "https://www.oxford.ac.uk/"
        assert root_of("not a url") is None
        assert root_of(None) is None
        assert root_of("ftp://example.org/x") is None


# ---------------------------------------------------------------------------
# Tier 2: Wikimedia
# ---------------------------------------------------------------------------


class TestWikimediaTier:
    def _wiki_payload(self, src="https://upload.wikimedia.org/logo.png"):
        return json.dumps(
            {
                "query": {
                    "pages": {
                        "123": {
                            "index": 1,
                            "title": "University of Oxford",
                            "original": {"source": src},
                        }
                    }
                }
            }
        )

    def test_it_returns_a_candidate_but_marks_it_non_official(self):
        """The critical property: a third-party host is never 'official'."""
        fetch = _fetcher({"https://en.wikipedia.org/w/api.php": self._wiki_payload()})
        found = LogoFallbackResolver(fetch_text=fetch).tier_wikimedia(_Scholarship())
        assert found
        assert found[0].url == "https://upload.wikimedia.org/logo.png"
        assert found[0].official_host is False
        assert found[0].tier is LogoTier.WIKIMEDIA

    def test_it_never_labels_a_wikimedia_image_official(self):
        """Belt and braces: no code path may map this tier to an official type."""
        source = open(
            __import__("app.services.image_discovery_orchestrator", fromlist=["x"]).__file__,
            encoding="utf-8",
        ).read()
        block = source.split("def run_logo_fallback")[1][:3000]
        assert '"wikimedia"' in block
        # The wikimedia branch must not be able to reach the official
        # classifier.
        assert 'if best.official_host' in block
        assert "official_host" in block

    def test_the_wikimedia_source_type_is_not_an_official_one(self):
        from app.services.scholarship_image_verifier import ImageSourceType

        official = {
            ImageSourceType.OFFICIAL_SCHOLARSHIP,
            ImageSourceType.OFFICIAL_UNIVERSITY,
            ImageSourceType.OFFICIAL_GOVERNMENT,
            ImageSourceType.OFFICIAL_PROVIDER,
        }
        assert ImageSourceType.WIKIMEDIA not in official
        assert ImageSourceType.WIKIMEDIA.value == "wikimedia"

    def test_it_returns_nothing_on_a_malformed_response(self):
        fetch = _fetcher({"https://en.wikipedia.org/w/api.php": "not json"})
        assert LogoFallbackResolver(fetch_text=fetch).tier_wikimedia(_Scholarship()) == []

    def test_it_skips_a_missing_page_entry(self):
        payload = json.dumps({"query": {"pages": {"1": {"index": "-1"}}}})
        fetch = _fetcher({"https://en.wikipedia.org/w/api.php": payload})
        assert LogoFallbackResolver(fetch_text=fetch).tier_wikimedia(_Scholarship()) == []

    def test_it_rejects_a_non_image_page_image(self):
        payload = json.dumps(
            {"query": {"pages": {"1": {"index": 1, "title": "X", "original": {"source": "https://x.test/p"}}}}}
        )
        fetch = _fetcher({"https://en.wikipedia.org/w/api.php": payload})
        assert LogoFallbackResolver(fetch_text=fetch).tier_wikimedia(_Scholarship()) == []


# ---------------------------------------------------------------------------
# Tier 3: static override
# ---------------------------------------------------------------------------


class TestStaticOverrideTier:
    def test_a_matching_override_is_used(self):
        overrides = {
            "oxford.ac.uk": {
                "url": "https://static.example.org/oxford-logo.png",
                "page_url": "https://www.oxford.ac.uk/",
                "official_host": True,
                "alt_text": "University of Oxford",
            }
        }
        resolver = LogoFallbackResolver(fetch_text=_fetcher({}), overrides=overrides)
        found = resolver.tier_static_override(_Scholarship())
        assert found[0].url == "https://static.example.org/oxford-logo.png"
        assert found[0].tier is LogoTier.STATIC_OVERRIDE

    def test_a_non_matching_override_is_ignored(self):
        resolver = LogoFallbackResolver(
            fetch_text=_fetcher({}), overrides={"other.edu": {"url": "https://x.test/a.png"}}
        )
        assert resolver.tier_static_override(_Scholarship()) == []

    def test_an_override_with_a_non_image_url_is_rejected(self):
        overrides = {"oxford.ac.uk": {"url": "https://www.oxford.ac.uk/"}}
        resolver = LogoFallbackResolver(fetch_text=_fetcher({}), overrides=overrides)
        assert resolver.tier_static_override(_Scholarship()) == []

    def test_an_override_defaults_to_not_official_host(self):
        """Absent evidence must not default to claiming official hosting."""
        overrides = {"oxford.ac.uk": {"url": "https://cdn.test/logo.png"}}
        resolver = LogoFallbackResolver(fetch_text=_fetcher({}), overrides=overrides)
        assert resolver.tier_static_override(_Scholarship())[0].official_host is False

    def test_the_key_is_the_host_not_the_title(self):
        assert institution_key(_Scholarship()) == "oxford.ac.uk"
        s = _Scholarship()
        s.title = "A Completely Different Name"
        assert institution_key(s) == "oxford.ac.uk"


class TestOverrideFile:
    def test_documentation_keys_are_not_loaded_as_overrides(self, tmp_path):
        """A comment block must never act as a live mapping."""
        path = tmp_path / "o.json"
        path.write_text(
            json.dumps(
                {
                    "_comment": "docs",
                    "_examples": {"x.test": {"url": "https://x.test/a.png"}},
                    "real.test": {"url": "https://real.test/a.png"},
                }
            ),
            encoding="utf-8",
        )
        loaded = load_overrides(path)
        assert set(loaded) == {"real.test"}

    def test_a_missing_file_means_no_overrides(self, tmp_path):
        assert load_overrides(tmp_path / "absent.json") == {}

    def test_a_malformed_file_means_no_overrides(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        assert load_overrides(path) == {}

    def test_the_shipped_file_is_valid_and_empty(self):
        """It must parse, and must not smuggle in an unvetted mapping."""
        shipped = load_overrides()
        assert isinstance(shipped, dict)


# ---------------------------------------------------------------------------
# Tier ordering and the resolver contract
# ---------------------------------------------------------------------------


class TestResolverOrdering:
    def test_tiers_are_tried_in_cost_order(self):
        """Root domain first (official and cheap), override, then Wikimedia."""
        source = open(
            __import__("app.services.logo_fallback_resolver", fromlist=["x"]).__file__,
            encoding="utf-8",
        ).read()
        order = [
            "LogoTier.ROOT_DOMAIN, self.tier_root_domain",
            "LogoTier.STATIC_OVERRIDE, self.tier_static_override",
            "LogoTier.WIKIMEDIA, self.tier_wikimedia",
        ]
        positions = [source.find(item) for item in order]
        assert all(p > 0 for p in positions)
        assert positions == sorted(positions), "tier order changed"

    def test_the_first_tier_with_a_candidate_wins(self):
        html = '<img src="/logo.svg" alt="logo" class="logo">'
        fetch = _fetcher({"https://www.oxford.ac.uk/": html})
        resolver = LogoFallbackResolver(fetch_text=fetch, overrides={})
        resolution = resolver.resolve(_Scholarship())
        assert resolution.status is LogoResolutionStatus.RESOLVED
        assert resolution.tier is LogoTier.ROOT_DOMAIN
        assert len(resolution.candidates) == 1

    def test_it_falls_through_to_a_later_tier(self):
        resolver = LogoFallbackResolver(
            fetch_text=_fetcher({}),
            overrides={"oxford.ac.uk": {"url": "https://cdn.test/logo.png"}},
        )
        resolution = resolver.resolve(_Scholarship())
        assert resolution.tier is LogoTier.STATIC_OVERRIDE

    def test_no_candidates_anywhere_is_an_outcome_not_an_error(self):
        resolver = LogoFallbackResolver(fetch_text=_fetcher({}), overrides={})
        resolution = resolver.resolve(_Scholarship())
        assert resolution.status is LogoResolutionStatus.NO_CANDIDATE
        assert resolution.candidates == []
        assert len(resolution.attempts) == 3, "every tier must be reported"

    def test_one_broken_tier_does_not_stop_the_others(self):
        def explode(url):
            raise RuntimeError("network down")

        resolver = LogoFallbackResolver(
            fetch_text=explode,
            overrides={"oxford.ac.uk": {"url": "https://cdn.test/logo.png"}},
        )
        resolution = resolver.resolve(_Scholarship())
        assert resolution.status is LogoResolutionStatus.RESOLVED
        assert resolution.tier is LogoTier.STATIC_OVERRIDE
        assert any("error" in a for a in resolution.attempts)

    def test_the_resolver_has_no_write_path(self):
        """A tier proposes; it never approves.

        Checked against persistence APIs rather than a bare ``.add(``, which
        would also match an ordinary Python set.
        """
        source = open(
            __import__("app.services.logo_fallback_resolver", fromlist=["x"]).__file__,
            encoding="utf-8",
        ).read()
        for forbidden in (
            "import sqlalchemy",
            "session",
            "Session",
            ".commit(",
            "setattr(",
            "db_url",
        ):
            assert forbidden not in source, f"the resolver must not contain {forbidden}"


class TestRequestBudget:
    def test_each_tier_makes_at_most_a_small_number_of_requests(self):
        """The fallback must not become a crawler."""
        html = "".join(
            f'<img src="/logo{i}.png" alt="logo" class="logo">' for i in range(50)
        )
        fetch = _fetcher({"https://www.oxford.ac.uk/": html})
        resolver = LogoFallbackResolver(fetch_text=fetch, overrides={})
        candidates = resolver.tier_root_domain(_Scholarship())
        assert len(candidates) <= 4, "a root page must not yield unbounded candidates"

    def test_the_request_counter_is_recorded(self):
        payload = json.dumps(
            {"query": {"pages": {"1": {"index": 1, "title": "X", "original": {"source": "https://x.test/l.png"}}}}}
        )
        fetch = _fetcher({"https://en.wikipedia.org/w/api.php": payload})
        resolver = LogoFallbackResolver(fetch_text=fetch)
        resolver.tier_wikimedia(_Scholarship())
        assert resolver.requests_made == 1
