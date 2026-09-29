"""Tests for bounded deep discovery crawling.

The bug these guard against is a real one from this repository's history: the
approved-source registry stored bare domains while the seed URLs were written
with ``www.``, and the comparison used the raw netloc. DAAD, Chevening and
Campus France were therefore rejected as ``source_not_approved`` before any
request was made, so Germany, the UK and France produced no discovered records
at all - and nothing failed loudly, because a rejected candidate is a normal
outcome.
"""

from __future__ import annotations

from app.services.discovery_config import (
    _DEFAULT_SOURCES,
    _extract_domain,
    StaticSourceRegistry,
)
from app.services.discovery_crawler import (
    CrawlBudget,
    DeepCrawler,
    extract_links,
    is_same_site,
    link_relevance,
)


# --- host normalisation ---------------------------------------------------


class TestDomainExtraction:
    def test_www_prefix_is_stripped(self):
        assert _extract_domain("https://www.daad.de/en/") == "daad.de"

    def test_bare_domain_is_unchanged(self):
        assert _extract_domain("https://erasmus-plus.ec.europa.eu/") == (
            "erasmus-plus.ec.europa.eu"
        )

    def test_port_is_ignored(self):
        assert _extract_domain("https://example.gov:8443/x") == "example.gov"

    def test_empty_url(self):
        assert _extract_domain("") is None


class TestSeededUrlsAreApproved:
    """Every seed URL the scheduler builds must pass the approval check.

    This is the regression test for the silent three-country blackout. It
    iterates the real registry rather than a fixture, so adding a source with a
    bad pattern fails here instead of in production.
    """

    def test_every_seed_url_is_approved(self):
        registry = StaticSourceRegistry()
        unapproved = []
        for source in _DEFAULT_SOURCES:
            urls = source.discovery_url_patterns or [f"https://{source.domain}/"]
            for url in urls:
                if not registry.is_approved_site(url):
                    unapproved.append(url)
        assert unapproved == [], f"seed URLs rejected as not approved: {unapproved}"

    def test_known_www_seeds_are_approved(self):
        registry = StaticSourceRegistry()
        for url in (
            "https://www.daad.de/en/",
            "https://www.chevening.org/",
            "https://www.campusfrance.org/",
        ):
            assert registry.is_approved_site(url), url

    def test_unrelated_domain_is_not_approved(self):
        registry = StaticSourceRegistry()
        assert not registry.is_approved_site("https://evil.example/scholarship")

    def test_subdomain_of_approved_is_approved(self):
        registry = StaticSourceRegistry()
        assert registry.is_approved_site("https://apply.daad.de/scholarship")
        assert registry.is_approved_site("https://grants.gov.uk/apply")

    def test_subdomain_matching_is_not_a_suffix_confusion(self):
        """`notdaad.de` must not pass as a subdomain of `daad.de`."""
        registry = StaticSourceRegistry()
        assert not registry.is_approved_site("https://notdaad.de/x")


class TestSameSite:
    def test_identical_host(self):
        assert is_same_site("https://daad.de/a", "https://daad.de/")

    def test_www_equivalence(self):
        assert is_same_site("https://www.daad.de/a", "https://daad.de/")

    def test_subdomain_allowed(self):
        assert is_same_site("https://apply.daad.de/a", "https://daad.de/")

    def test_deep_subdomain_allowed(self):
        assert is_same_site("https://a.b.daad.de/x", "https://daad.de/")

    def test_different_domain_rejected(self):
        assert not is_same_site("https://other.gov/x", "https://daad.de/")

    def test_suffix_confusion_rejected(self):
        assert not is_same_site("https://evil-daad.de/x", "https://daad.de/")

    def test_external_social_rejected(self):
        assert not is_same_site("https://facebook.com/daad", "https://daad.de/")


# --- link relevance -------------------------------------------------------


class TestLinkRelevance:
    def test_scholarship_in_path_scores(self):
        assert link_relevance("https://x.gov/scholarships/2026") > 0

    def test_anchor_only_scores(self):
        assert link_relevance("https://x.gov/page?id=3", "Grants and scholarships") > 0

    def test_generic_about_page_not_followed(self):
        assert link_relevance("https://x.gov/about", "About us") == 0

    def test_login_is_vetoed_despite_programme_vocabulary(self):
        assert link_relevance("https://x.gov/login?next=scholarship", "Login") == 0

    def test_privacy_is_vetoed(self):
        assert link_relevance("https://x.gov/privacy", "Privacy policy") == 0

    def test_external_host_social_vetoed(self):
        assert link_relevance("https://facebook.com/scholarship", "Scholarship") == 0

    def test_apply_now_anchor_vetoed(self):
        assert link_relevance("https://x.gov/scholarships", "Apply now") == 0

    def test_path_match_outranks_anchor_match(self):
        strong = link_relevance("https://x.gov/scholarships", "Details")
        weak = link_relevance("https://x.gov/page", "Scholarships")
        assert strong > weak


class TestExtractLinks:
    HTML = """
    <html><body>
      <a href="/scholarships/2026">Scholarships 2026</a>
      <a href="/about">About us</a>
      <a href="mailto:x@y.gov">Email</a>
      <a href="#top">Top</a>
      <a href="https://other.gov/scholarship">Other site</a>
      <a href="/grants">Grants</a>
      <a href="/scholarships/2026">Duplicate</a>
    </body></html>
    """

    def test_extracts_only_relevant_same_site_links(self):
        links = extract_links(self.HTML, "https://x.gov/", limit=50)
        assert "https://x.gov/scholarships/2026" in links
        assert "https://x.gov/grants" in links
        assert not any("/about" in link for link in links)
        assert not any("other.gov" in link for link in links)
        assert not any(link.startswith("mailto") for link in links)

    def test_equal_relevance_is_ordered_deterministically(self):
        """A score tie must break the same way on every run.

        Otherwise two runs over the same page can visit different pages, and a
        budget that truncates turns that into records that appear on one run
        and not the next. Both links here score 5, so ordering is decided by
        the URL sort key rather than by link order in the HTML.
        """
        links = extract_links(self.HTML, "https://x.gov/", limit=50)
        tied = [u for u in links if u in ("https://x.gov/grants", "https://x.gov/scholarships/2026")]
        assert tied == sorted(tied)

    def test_deduplicates_repeated_hrefs(self):
        links = extract_links(self.HTML, "https://x.gov/", limit=50)
        assert len(links) == len(set(links))

    def test_limit_is_respected(self):
        links = extract_links(self.HTML, "https://x.gov/", limit=1)
        assert len(links) == 1

    def test_url_filter_excludes(self):
        links = extract_links(
            self.HTML, "https://x.gov/", limit=50, url_filter=lambda u: "grants" not in u
        )
        assert not any("grants" in link for link in links)

    def test_malformed_html_does_not_raise(self):
        assert extract_links("<html><a href=", "https://x.gov/", limit=5) == []

    def test_empty_content(self):
        assert extract_links("", "https://x.gov/", limit=5) == []


class TestCrawlBudget:
    def test_defaults_are_bounded(self):
        budget = CrawlBudget()
        assert budget.max_depth >= 1
        assert budget.max_pages_per_seed >= 2
        assert budget.max_total_pages >= budget.max_pages_per_seed
        assert set(budget.as_dict()) == {
            "max_depth",
            "max_pages_per_seed",
            "max_total_pages",
        }


class TestDeepCrawlerPlan:
    """`plan` must be bounded and resilient without network access.

    The crawler's page reads go through `fetch_official_source`, which is
    patched to return a small site so these tests stay offline and fast. The
    assertions that matter are the bounds: an unbounded crawler is the failure
    mode this module exists to prevent.
    """

    def _patch_fetcher(self, monkeypatch, pages: dict[str, str]):
        from app.services import discovery_crawler

        class _Result:
            def __init__(self, content):
                self.success = bool(content)
                self.content = content
                self.content_type = "text/html"

        def fake_fetch(url):
            return _Result(pages.get(url, ""))

        monkeypatch.setattr(discovery_crawler, "fetch_official_source", fake_fetch, raising=False)
        # The crawler imports the fetcher inside the method, so patch the
        # source module attribute instead.
        from app.services import official_source_fetcher

        monkeypatch.setattr(official_source_fetcher, "fetch_official_source", fake_fetch)

    def test_seed_is_visited_first(self, monkeypatch):
        self._patch_fetcher(monkeypatch, {"https://x.gov/": ""})
        crawler = DeepCrawler(CrawlBudget(max_depth=2, max_pages_per_seed=5))
        assert crawler.plan("https://x.gov/") == ["https://x.gov/"]

    def test_follows_relevant_links(self, monkeypatch):
        self._patch_fetcher(
            monkeypatch,
            {
                "https://x.gov/": '<a href="/scholarships/2026">Scholarships</a>',
                "https://x.gov/scholarships/2026": "<p>Programme</p>",
            },
        )
        crawler = DeepCrawler(CrawlBudget(max_depth=1, max_pages_per_seed=5))
        plan = crawler.plan("https://x.gov/")
        assert plan == ["https://x.gov/", "https://x.gov/scholarships/2026"]

    def test_respects_max_depth(self, monkeypatch):
        self._patch_fetcher(
            monkeypatch,
            {
                "https://x.gov/": '<a href="/a">Scholarships</a>',
                "https://x.gov/a": '<a href="/b">Scholarships</a>',
                "https://x.gov/b": '<a href="/c">Scholarships</a>',
            },
        )
        crawler = DeepCrawler(CrawlBudget(max_depth=1, max_pages_per_seed=10))
        plan = crawler.plan("https://x.gov/")
        assert "https://x.gov/b" not in plan
        assert "https://x.gov/a" in plan

    def test_respects_max_pages_per_seed(self, monkeypatch):
        links = "".join(f'<a href="/p{i}">Scholarships</a>' for i in range(30))
        self._patch_fetcher(monkeypatch, {"https://x.gov/": links})
        crawler = DeepCrawler(CrawlBudget(max_depth=2, max_pages_per_seed=4))
        assert len(crawler.plan("https://x.gov/")) <= 4

    def test_url_filter_is_applied(self, monkeypatch):
        self._patch_fetcher(
            monkeypatch,
            {
                "https://x.gov/": (
                    '<a href="/scholarships">Scholarships</a>'
                    '<a href="/grants">Grants</a>'
                ),
            },
        )
        crawler = DeepCrawler(
            CrawlBudget(max_depth=1, max_pages_per_seed=10),
            url_filter=lambda u: "scholarships" in u,
        )
        plan = crawler.plan("https://x.gov/")
        assert not any("grants" in link for link in plan)

    def test_fetch_failure_does_not_abort_the_crawl(self, monkeypatch):
        """A single unreachable page must not lose the rest of the crawl."""
        from app.services import official_source_fetcher

        class _Result:
            def __init__(self, content, success=True):
                self.success = success
                self.content = content
                self.content_type = "text/html"

        def fake_fetch(url):
            if url == "https://x.gov/":
                return _Result('<a href="/scholarships">Scholarships</a>')
            return _Result("", success=False)

        monkeypatch.setattr(official_source_fetcher, "fetch_official_source", fake_fetch)
        crawler = DeepCrawler(CrawlBudget(max_depth=1, max_pages_per_seed=5))
        assert crawler.plan("https://x.gov/") == [
            "https://x.gov/",
            "https://x.gov/scholarships",
        ]

    def test_unfollowable_seed_returns_empty(self, monkeypatch):
        self._patch_fetcher(monkeypatch, {})
        assert DeepCrawler(CrawlBudget()).plan("mailto:x@y.gov") == []

    def test_fragment_deduplication(self, monkeypatch):
        self._patch_fetcher(
            monkeypatch,
            {
                "https://x.gov/": (
                    '<a href="/scholarships#a">Scholarships</a>'
                    '<a href="/scholarships#b">Scholarships</a>'
                ),
            },
        )
        crawler = DeepCrawler(CrawlBudget(max_depth=1, max_pages_per_seed=10))
        plan = crawler.plan("https://x.gov/")
        assert plan.count("https://x.gov/scholarships") == 1
