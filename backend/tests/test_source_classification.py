"""Regression tests for authoritative-source classification.

These lock in the fix for a real measurement: 261 of 489 catalogue records
(53%) were misclassified as third party, which blocked official-source
enrichment for every one of them.
"""

from __future__ import annotations

import pytest

from app.services.scholarship_evidence import (
    SourceType,
    _normalize_host,
    _registrable,
    classify_source,
    is_authoritative_source,
)


class TestHostNormalisation:
    def test_strips_www(self):
        assert _normalize_host("www.kth.se") == "kth.se"

    def test_strips_www2(self):
        assert _normalize_host("www2.daad.de") == "daad.de"

    def test_strips_language_prefix(self):
        assert _normalize_host("en.unito.it") == "unito.it"

    def test_strips_locale_prefix(self):
        assert _normalize_host("de.kth.se") == "kth.se"

    def test_strips_port(self):
        assert _normalize_host("kth.se:8443") == "kth.se"

    def test_leaves_bare_domain(self):
        assert _normalize_host("kth.se") == "kth.se"


class TestRegistrable:
    def test_simple_domain(self):
        assert _registrable("kth.se") == "kth.se"

    def test_subdomain(self):
        assert _registrable("future.utoronto.ca") == "utoronto.ca"

    def test_multi_part_public_suffix(self):
        assert _registrable("www.temasek.com.sg") == "temasek.com.sg"
        assert _registrable("www.education.govt.nz") == "education.govt.nz"
        assert _registrable("www.daad.de") == "daad.de"

    def test_deep_subdomain(self):
        assert _registrable("en.unimib.it") == "unimib.it"


class TestClassification:
    @pytest.mark.parametrize(
        "url",
        [
            "https://ethz.ch/students/en/",
            "https://www.epfl.ch/education/",
            "https://www.kth.se/en/",
            "https://www.tudelft.nl/en/",
            "https://www.uu.nl/en/",
            "https://www.rug.nl/en/",
            "https://you.ubc.ca/",
            "https://futurestudents.yorku.ca/",
            "https://unipd.it/en/",
            "https://www.unige.ch/",
        ],
    )
    def test_universities_are_official(self, url):
        assert is_authoritative_source(classify_source(url))

    @pytest.mark.parametrize(
        "url",
        [
            "https://erasmus-plus.ec.europa.eu/",
            "https://www2.daad.de/",
            "https://www.campusfrance.org/",
            "https://www.snf.ch/",
            "https://www.humboldt-foundation.de/",
            "https://www.studyinnl.org/",
            "https://www.sciencespo.fr/",
            "https://www.ethz.ch/",
        ],
    )
    def test_programme_operators_are_official(self, url):
        assert is_authoritative_source(classify_source(url))

    @pytest.mark.parametrize(
        "url",
        [
            "https://exchanges.state.gov/",
            "https://www.education.govt.nz/",
            "https://www.nsf.gov/",
            "https://frq.gouv.qc.ca/",
        ],
    )
    def test_government_is_official(self, url):
        st = classify_source(url)
        assert st == SourceType.OFFICIAL_GOVERNMENT
        assert is_authoritative_source(st)

    def test_named_programme_host_stays_programme(self):
        """jasso.go.jp is a curated programme host, so it outranks the .go.jp rule."""
        assert (
            classify_source("https://www.jasso.go.jp/en/")
            == SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM
        )

    def test_www2_daad_matches_programme(self):
        assert classify_source("https://www2.daad.de/x") == SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM

    def test_application_portal_wins_over_parent_domain(self):
        assert (
            classify_source("https://apply.daad.de/portal")
            == SourceType.OFFICIAL_APPLICATION_PORTAL
        )

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.scholarshipdb.net/x",
            "https://www.scholars4dev.com/x",
            "https://www.grammarvine.com/",
            "http://example.com/",
        ],
    )
    def test_aggregators_stay_third_party(self, url):
        assert classify_source(url) == SourceType.THIRD_PARTY

    def test_empty_is_third_party(self):
        assert classify_source("") == SourceType.THIRD_PARTY
        assert classify_source("https://") == SourceType.THIRD_PARTY

    def test_known_programme_host_still_exact(self):
        assert (
            classify_source("https://www.campusfrance.org/en/")
            == SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM
        )


class TestRegistryAgreement:
    """The evidence layer must never outrank the ApprovedSource registry.

    A real cross-check found discovery_config.py classifying scholars4dev.com as
    an "aggregator" while the evidence layer treated it as an official
    scholarship programme, which would have let directory content be stored as
    official fact.
    """

    def test_no_aggregator_is_treated_as_official(self):
        from app.services.discovery_config import _DEFAULT_SOURCES

        for source in _DEFAULT_SOURCES:
            if source.source_type != "aggregator":
                continue
            for variant in (f"https://{source.domain}/", f"https://www.{source.domain}/"):
                assert (
                    classify_source(variant) == SourceType.THIRD_PARTY
                ), f"aggregator {source.domain} must not classify as official"

    def test_every_official_registry_source_is_authoritative(self):
        from app.services.discovery_config import _DEFAULT_SOURCES

        for source in _DEFAULT_SOURCES:
            if source.source_type == "aggregator":
                continue
            assert is_authoritative_source(
                classify_source(f"https://www.{source.domain}/")
            ), f"official registry source {source.domain} must classify as authoritative"
