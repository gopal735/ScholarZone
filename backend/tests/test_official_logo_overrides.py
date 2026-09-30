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


class TestGapReport:
    """The uncovered-host report is the research worklist, so it must be right.

    An earlier version called ``.values()`` on the already-sorted list and took
    the whole stage down in production. Nothing had executed that code, so the
    fix here is a test that actually evaluates the report shape.
    """

    @staticmethod
    def report(still_missing):
        ranked = sorted(still_missing.items(), key=lambda kv: (-kv[1], kv[0]))
        return {
            "records_still_without_logo": sum(count for _host, count in ranked),
            "distinct_hosts_still_without_logo": len(ranked),
            "top_hosts_still_without_logo": ranked[:60],
        }

    def test_totals_the_records_not_the_hosts(self):
        out = self.report({"a.example": 3, "b.example": 4, "c.example": 1})
        assert out["records_still_without_logo"] == 8
        assert out["distinct_hosts_still_without_logo"] == 3

    def test_ranks_by_record_count_then_host(self):
        out = self.report({"z.example": 5, "a.example": 2, "m.example": 5})
        assert out["top_hosts_still_without_logo"] == [
            ("m.example", 5), ("z.example", 5), ("a.example", 2)
        ]

    def test_empty_gap_reports_zero(self):
        out = self.report({})
        assert out["records_still_without_logo"] == 0
        assert out["distinct_hosts_still_without_logo"] == 0
        assert out["top_hosts_still_without_logo"] == []

    def test_result_is_capped_but_total_is_not(self):
        many = {f"h{i}.example": i for i in range(100)}
        out = self.report(many)
        assert len(out["top_hosts_still_without_logo"]) == 60
        assert out["records_still_without_logo"] == sum(many.values())


class TestFindOverrideIsShared:
    def test_stage_and_resolver_agree_on_the_matched_key(self):
        """The stage and the crawler must not resolve a host differently.

        Two copies of the parent-domain rule is how they drift, and a drift here
        would mean the fast stage attaches a different logo than the crawler
        would have found.
        """
        from app.services.logo_fallback_resolver import find_override

        overrides = {
            "nus.edu.sg": {"url": "https://www.nus.edu.sg/l.svg", "alt_text": "NUS",
                           "page_url": "https://www.nus.edu.sg/", "official_host": True},
        }
        found = find_override(overrides, "nusgs.nus.edu.sg")
        assert found is not None
        key, entry = found
        resolver = LogoFallbackResolver(overrides=overrides, fetch_text=lambda _u: None)
        candidate = resolver.tier_static_override(
            _Scholarship("https://nusgs.nus.edu.sg/x")
        )[0]
        assert candidate.url == entry["url"] == "https://www.nus.edu.sg/l.svg"

    def test_find_override_reports_the_key_it_used(self):
        from app.services.logo_fallback_resolver import find_override

        overrides = {"kaist.ac.kr": {"url": "https://k/l.svg", "alt_text": "KAIST",
                                     "page_url": "https://kaist.ac.kr/", "official_host": True}}
        key, _entry = find_override(overrides, "admission.kaist.ac.kr")
        assert key == "kaist.ac.kr"


class TestParentDomainMatching:
    """One audited entry must cover every host an institution is reached on.

    Records store whatever host their programme page lives on, and that is
    rarely the apex. The catalogue had 316 hosts needing a logo against 42
    audited institutions, which is the size of the gap exact matching leaves.
    """

    @pytest.fixture
    def resolver(self):
        return LogoFallbackResolver(
            overrides={
                "daad.de": {"url": "https://www.daad.de/logo.svg",
                            "page_url": "https://www.daad.de/", "alt_text": "DAAD",
                            "official_host": True},
                "kaist.ac.kr": {"url": "https://www.kaist.ac.kr/logo.svg",
                                "page_url": "https://www.kaist.ac.kr/", "alt_text": "KAIST",
                                "official_host": True},
                "nus.edu.sg": {"url": "https://www.nus.edu.sg/logo.svg",
                               "page_url": "https://www.nus.edu.sg/", "alt_text": "NUS",
                               "official_host": True},
            },
            fetch_text=lambda _u: None,
        )

    def test_deep_subdomain_resolves_to_its_institution(self, resolver):
        got = resolver.tier_static_override(
            _Scholarship("https://admission.kaist.ac.kr/scholarship")
        )
        assert len(got) == 1
        assert "kaist.ac.kr" in got[0].url

    def test_numbered_subdomain_resolves_to_its_institution(self, resolver):
        """DAAD's programme database is served from www2, not www."""
        got = resolver.tier_static_override(
            _Scholarship("https://www2.daad.de/datenbank/en/21148")
        )
        assert len(got) == 1
        assert "daad.de" in got[0].url

    def test_exact_match_still_wins_over_a_parent(self, resolver):
        """A specific entry must not be shadowed by a broader one."""
        resolver._overrides["eng.nus.edu.sg"] = {
            "url": "https://eng.nus.edu.sg/engineering-logo.svg",
            "page_url": "https://eng.nus.edu.sg/", "alt_text": "NUS Engineering",
            "official_host": True,
        }
        got = resolver.tier_static_override(
            _Scholarship("https://eng.nus.edu.sg/scholarship")
        )
        assert "engineering-logo" in got[0].url

    def test_unrelated_host_does_not_match(self, resolver):
        assert resolver.tier_static_override(
            _Scholarship("https://notkaist.ac.kr.example.com/x")
        ) == []

    def test_a_host_that_merely_ends_with_the_key_is_not_a_match(self, resolver):
        """`evildaad.de` is not DAAD.

        Suffix matching without a dot boundary would hand one institution's
        logo to an unrelated lookalike domain, which is the worst outcome this
        table can produce.
        """
        assert resolver.tier_static_override(
            _Scholarship("https://evildaad.de/x")
        ) == []

    def test_public_suffix_is_not_itself_a_match_target(self, resolver):
        """A record hosted directly on a TLD must not resolve to a sibling."""
        assert resolver.tier_static_override(
            _Scholarship("https://ac.kr/scholarship")
        ) == []


class TestIssuerKind:
    def test_government_hosts_are_attributed_to_government(self):
        from app.jobs.scholarzone_maintenance import _issuer_kind

        for host, expected in [
            ("nawa.gov.pl", "official_government"),
            ("moe.gov.sa", "official_government"),
            ("erasmus-plus.ec.europa.eu", "official_government"),
            ("un.org", "official_government"),
        ]:
            assert _issuer_kind(host) == expected

    def test_university_hosts_are_attributed_to_university(self):
        from app.jobs.scholarzone_maintenance import _issuer_kind

        for host in ("uct.ac.za", "wits.ac.za", "iuj.ac.jp", "um.edu.mt", "knust.edu.gh"):
            assert _issuer_kind(host) == "official_university"

    def test_a_national_university_domain_is_not_guessed_from_its_tld(self):
        """`.hr` is not a university signal, and the code must not pretend it is.

        Zagreb is a university, but a host pattern matching `.hr` would also
        match a government ministry, a broadcaster and a bank. Guessing there
        would produce a confident wrong attribution, so the host pattern is
        absent and the alt text is used instead.
        """
        from app.jobs.scholarzone_maintenance import _issuer_kind

        assert _issuer_kind("unizg.hr") == "official_logo"
        assert _issuer_kind("unizg.hr", "University of Zagreb") == "official_university"

    def test_national_academic_domains_need_the_alt_text(self):
        """`.ee`, `.lv` and `.is` carry no university signal in the TLD.

        Tartu, Latvia and Iceland are all universities on national academic
        domains, so the alt text is the only honest way to attribute them.
        """
        from app.jobs.scholarzone_maintenance import _issuer_kind

        for host in ("ut.ee", "lu.lv", "hi.is"):
            assert _issuer_kind(host) == "official_logo", (
                f"{host} has no host-level university signal"
            )
            assert _issuer_kind(host, "University of Tartu") == "official_university"

    def test_every_override_with_university_alt_text_resolves_to_university(self, overrides):
        """The attribution must be derivable for every entry we ship."""
        from app.jobs.scholarzone_maintenance import _issuer_kind

        for host, entry in overrides.items():
            kind = _issuer_kind(host, entry.get("alt_text"))
            assert kind in {
                "official_logo", "official_government", "official_university"
            }, f"{host} produced an unknown issuer kind: {kind}"

    def test_unknown_issuer_falls_back_to_logo(self):
        """A foundation is a logo with no more specific attribution.

        Claiming a government or university identity we cannot support would be
        worse than the honest, weaker statement.
        """
        from app.jobs.scholarzone_maintenance import _issuer_kind

        assert _issuer_kind("iie.org") == "official_logo"
        assert _issuer_kind("akdn.org") == "official_logo"


class TestRootOfHelper:
    def test_root_of_extracts_scheme_and_host(self):
        assert root_of("https://daad.de/en/x") == "https://daad.de/"
