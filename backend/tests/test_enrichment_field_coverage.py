"""Tests for the fields the enrichment engine previously could never write.

The catalogue's emptiest columns were not empty because the official pages
lacked the information. They were empty because no code path ever wrote them:
documents had a classifier but no field mapping, deadline_date was parsed for
status but never persisted, and the three URL columns could not be filled by a
text extractor at all.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.scholarship_enrichment import (
    WRITABLE_FIELDS,
    _COUNTRY_REGION,
    _link_proposals_from_sections,
    parse_deadline_date,
)


class TestPreviouslyUnwritableFields:
    @pytest.mark.parametrize(
        "field",
        [
            "documents",
            "deadline_date",
            "region",
            "eligibility_summary",
            "application_link",
            "catalogue_url",
            "official_updates_url",
        ],
    )
    def test_field_is_now_writable(self, field):
        assert field in WRITABLE_FIELDS


class TestDocumentsMapping:
    def test_documents_section_maps_to_documents_column(self):
        from app.services.scholarship_enrichment import SECTION_LIST_FIELD

        assert SECTION_LIST_FIELD["documents"] == "documents"


class TestDeadlineParsing:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("15 March 2027", date(2027, 3, 15)),
            ("March 15, 2027", date(2027, 3, 15)),
            ("2027-03-15", date(2027, 3, 15)),
            ("Deadline: 31 December 2026", date(2026, 12, 31)),
            ("15/03/2027", date(2027, 3, 15)),
        ],
    )
    def test_parses_unambiguous_dates(self, text, expected):
        assert parse_deadline_date(text) == expected

    def test_month_level_deadline_uses_last_day_of_month(self):
        assert parse_deadline_date("applications close in March 2027") == date(2027, 3, 31)

    @pytest.mark.parametrize(
        "text", ["", "sometime next year", "rolling deadline", "TBA", "see website"]
    )
    def test_unparseable_text_returns_none_rather_than_guessing(self, text):
        """A wrong deadline drives status and notifications; guessing is worse."""
        assert parse_deadline_date(text) is None

    def test_impossible_date_is_rejected(self):
        assert parse_deadline_date("31 February 2027") is None

    def test_ambiguous_numeric_is_read_as_day_first(self):
        """European official sites publish DD/MM/YYYY."""
        assert parse_deadline_date("05/06/2027") == date(2027, 6, 5)


class TestLinkExtraction:
    HTML = (
        '<a href="/how-to-apply">How to apply</a>'
        '<a href="/news/2027-call">Latest news</a>'
        '<a href="/scholarships/list">All scholarships</a>'
    )

    def test_finds_application_portal(self):
        proposals = _link_proposals_from_sections(
            self.HTML, "https://x.org/p", "https://x.org/p"
        )
        assert proposals["application_link"]["value"] == "https://x.org/how-to-apply"

    def test_finds_updates_page(self):
        proposals = _link_proposals_from_sections(
            self.HTML, "https://x.org/p", "https://x.org/p"
        )
        assert proposals["official_updates_url"]["value"] == "https://x.org/news/2027-call"

    def test_finds_catalogue_page(self):
        proposals = _link_proposals_from_sections(
            self.HTML, "https://x.org/p", "https://x.org/p"
        )
        assert proposals["catalogue_url"]["value"] == "https://x.org/scholarships/list"

    def test_relative_links_are_resolved_against_the_page(self):
        proposals = _link_proposals_from_sections(
            '<a href="apply.html">Apply</a>', "https://x.org/a/b", "https://x.org/a/b"
        )
        assert proposals["application_link"]["value"] == "https://x.org/a/apply.html"

    @pytest.mark.parametrize(
        "html",
        [
            '<a href="javascript:void(0)">Apply</a>',
            '<a href="mailto:info@x.org">Apply</a>',
            '<a href="#apply">Apply</a>',
            "<p>No links here at all</p>",
        ],
    )
    def test_non_navigational_hrefs_are_ignored(self, html):
        proposals = _link_proposals_from_sections(html, "https://x.org/p", "https://x.org/p")
        assert "application_link" not in proposals

    def test_link_back_to_the_same_page_is_not_offered(self):
        html = '<a href="/how-to-apply">Apply</a>'
        proposals = _link_proposals_from_sections(
            html, "https://x.org/how-to-apply", "https://x.org/how-to-apply"
        )
        assert "application_link" not in proposals


class TestRegionMapping:
    def test_known_countries_map_to_a_region(self):
        assert _COUNTRY_REGION["germany"] == "Europe"
        assert _COUNTRY_REGION["canada"] == "North America"
        assert _COUNTRY_REGION["japan"] == "Asia"
        assert _COUNTRY_REGION["south africa"] == "Africa"

    def test_unknown_country_is_absent(self):
        """No guess: an unrecognised country yields no region."""
        assert "atlantis" not in _COUNTRY_REGION
