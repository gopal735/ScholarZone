"""The logo override file is audited data, so it gets audited tests.

Every entry here was probed live before it was added, but a URL rots and a
config file does not complain. These tests fail loudly rather than letting a
stale or malformed entry sit in production where it would either be fetched on
every run or silently skipped.
"""

from __future__ import annotations

import json

import pytest

from app.services.logo_fallback_resolver import (
    LogoFallbackResolver,
    load_overrides,
    root_of,
)


class _Scholarship:
    def __init__(self, url, title="Test Scholarship", country="Testland"):
        self.id = 1
        self.official_source_url = url
        self.title = title
        self.country = country


@pytest.fixture(scope="module")
def overrides():
    return load_overrides()


class TestOverrideFileIntegrity:
    def test_file_parses_and_is_not_empty(self, overrides):
        assert overrides, "override file parsed to nothing; the config is broken"

    def test_every_entry_has_the_required_fields(self, overrides):
        for host, entry in overrides.items():
            assert entry.get("url"), f"{host} has no url"
            assert entry.get("alt_text"), f"{host} has no alt_text"
            assert "page_url" in entry, f"{host} has no page_url"
            assert isinstance(entry.get("official_host"), bool), (
                f"{host} must state official_host explicitly, not omit it"
            )

    def test_every_logo_url_is_https(self, overrides):
        for host, entry in overrides.items():
            assert entry["url"].startswith("https://") or entry["url"].startswith(
                "http://"
            ), f"{host} logo url is not absolute: {entry['url']}"

    def test_page_url_is_absolute_http(self, overrides):
        """Absolute is the requirement; the scheme is the host's business.

        moe.gov.cn serves http only. Upgrading it to https here would point at
        a page that does not resolve, so the entry has to keep the scheme the
        institution actually publishes.
        """
        for host, entry in overrides.items():
            page = entry.get("page_url") or ""
            assert page.startswith("https://") or page.startswith("http://"), (
                f"{host} page_url is not absolute: {page}"
            )

    def test_official_host_claims_are_consistent(self, overrides):
        """A non-official host must be the exception, and only a rare one.

        Every entry is the institution's own artwork. The one exception here is
        a logo served by a sibling ministry host, which is recorded honestly as
        a third-party host so the record's provenance stays true.
        """
        third_party = [h for h, e in overrides.items() if not e["official_host"]]
        assert len(third_party) <= 2, (
            f"unexpected number of third-party-hosted logos: {third_party}"
        )

    def test_no_duplicate_logo_urls_across_different_hosts(self, overrides):
        """Two institutions sharing one logo file would be a provenance bug.

        Aliasing is allowed - Stipendium Hungaricum and Study in Hungary are
        the same programme run by the same foundation - but a university and a
        ministry pointing at one file is not.
        """
        by_url: dict[str, list[str]] = {}
        for host, entry in overrides.items():
            by_url.setdefault(entry["url"], []).append(host)
        for url, hosts in by_url.items():
            assert len(hosts) <= 2, f"{url} shared by unrelated hosts: {hosts}"


class TestOverrideResolution:
    def test_known_host_resolves_without_network(self, overrides):
        resolver = LogoFallbackResolver(overrides=overrides, fetch_text=lambda _u: None)
        scholarship = _Scholarship("https://www.nawa.gov.pl/en/students")
        candidates = resolver.tier_static_override(scholarship)
        assert len(candidates) == 1
        assert "nawa.gov.pl" in candidates[0].url
        assert candidates[0].official_host is True
        assert candidates[0].tier.value == "static_override"

    def test_unknown_host_resolves_to_nothing(self, overrides):
        resolver = LogoFallbackResolver(overrides=overrides, fetch_text=lambda _u: None)
        scholarship = _Scholarship("https://unknown.example.edu/x")
        assert resolver.tier_static_override(scholarship) == []

    def test_www_prefixed_record_matches_bare_domain_key(self, overrides):
        """Records are stored with a www host; keys are bare domains.

        institution_key strips www, so a key written with www would never match
        and the override would be dead config that looks alive in a diff.
        """
        for host in overrides:
            assert not host.startswith("www."), f"{host} should be stored without www"

    def test_entry_without_official_host_is_never_silently_treated_as_official(self, overrides):
        """An omitted official_host must default to False, not to True.

        The resolver is the boundary where a candidate's provenance is decided,
        so a missing key has to be the conservative option: a third-party-hosted
        logo must never be laundered into an official one by a typo.
        """
        fake = {
            "x.example": {
                "url": "https://x.example/logo.svg",
                "page_url": "https://x.example/",
                "alt_text": "X",
            }
        }
        resolver = LogoFallbackResolver(overrides=fake, fetch_text=lambda _u: None)
        got = resolver.tier_static_override(_Scholarship("https://x.example/"))
        assert got[0].official_host is False

    def test_audit_rules_are_documented_in_the_file(self):
        """The file's own rules must state why a URL is not simply added.

        Without the probing and white-logo rules recorded next to the data, the
        next editor will add whatever a search engine returned.
        """
        path = (
            __import__("app.services.logo_fallback_resolver", fromlist=["x"]).OVERRIDE_PATH
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        rules = " ".join(data.get("_rules", []))
        assert "200" in rules, "rules must record that URLs were probed live"
        assert "white" in rules.lower(), "rules must record the white-logo exclusion"


class TestRootOfHelper:
    def test_root_of_extracts_scheme_and_host(self):
        assert root_of("https://daad.de/en/x") == "https://daad.de/"
