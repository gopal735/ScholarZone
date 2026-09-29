"""Tests for the pre-insert gate rules added after a live deep crawl.

Every case in this file is a value or title that a real production discovery
round produced. The two records that run inserted are quoted verbatim, because
a rule invented from an imagined example tends not to survive contact with an
actual scraper's output.

The two that got through were:

    id 493  "Find your programme"          country=Austria
            degree="programmes from more than 77 esteemed institutions.
                    Do you want to take courses taught in English? At"
            official_source=None, is_verified=True

    id 492  "Study in Hungary - Application Timeline"
            degree="Programmes[/LINK]"
            deadline_display="for the first round of admission procedures is
                               usually in"
            official_source=None

Both passed a gate that only counted populated fields. The lesson recorded in
the module docstring - that field counting cannot tell a programme from a page
that mentions programmes - had not been carried through to the values
themselves.
"""

from __future__ import annotations

import pytest

from app.services.deadline_semantics import (
    DEADLINE_PRECISION_VALUES,
    coerce_deadline_precision,
)
from app.services.discovery_quality_gate import (
    DiscoveryVerdict,
    assess_candidate,
)

GOOD_FIELDS = {
    "description": "The DAAD Development-Related Postgraduate Programme funds study in Germany.",
    "eligibility": ["Open to graduates of developing countries"],
    "deadline": "15 January 2027",
    "provider": "DAAD",
    "degree": "Master",
}


# --- the exact junk that reached production ------------------------------


class TestLiveJunkIsNowRejected:
    def test_find_your_programme_is_rejected(self):
        verdict = assess_candidate(
            "Find your programme",
            "https://studyinaustria.at/study-in-austria/find-your-programme",
            {
                "description": "programmes from more than 77 esteemed institutions",
                "degree": "programmes from more than 77 esteemed institutions. Do you want to take courses taught in English? At",
                "provider": None,
            },
        )
        assert verdict.verdict is DiscoveryVerdict.REJECT, verdict.reasons

    def test_prose_in_degree_field_is_rejected(self):
        verdict = assess_candidate(
            "Study in Austria Programme",
            "https://studyinaustria.at/study-in-austria/programmes",
            {
                "description": "Study in Austria",
                "degree": "programmes from more than 77 esteemed institutions. Do you want to take courses taught in English? At",
                "provider": "OeAD",
            },
        )
        assert verdict.verdict is DiscoveryVerdict.REJECT, verdict.reasons

    def test_html_artifact_in_value_is_rejected(self):
        verdict = assess_candidate(
            "Study in Hungary - Application Timeline",
            "https://studyinhungary.hu/study-in-hungary/menu/studying-in-hungary/application-timeline.html",
            {
                "deadline": "for the first round of admission procedures is usually in",
                "degree": "Programmes[/LINK]",
                "provider": "Tempus Public Foundation",
            },
        )
        assert verdict.verdict is DiscoveryVerdict.REJECT, verdict.reasons

    def test_missing_provider_is_never_published(self):
        """The single check that would have caught both live records."""
        verdict = assess_candidate(
            "Some Programme Scholarship",
            "https://x.gov/scholarships/2026",
            {**GOOD_FIELDS, "provider": None, "official_source": None},
        )
        assert verdict.verdict is not DiscoveryVerdict.ACCEPT
        assert any("provider" in r for r in verdict.reasons)

    def test_application_timeline_title_is_rejected(self):
        verdict = assess_candidate(
            "Application Timeline",
            "https://x.gov/scholarships/2026/timeline",
            GOOD_FIELDS,
        )
        assert verdict.verdict is DiscoveryVerdict.REJECT

    def test_menu_path_is_rejected(self):
        verdict = assess_candidate(
            "Some Programme Scholarship",
            "https://x.gov/menu/scholarships/2026",
            GOOD_FIELDS,
        )
        assert verdict.verdict is DiscoveryVerdict.REJECT

    def test_template_extension_path_is_flagged(self):
        verdict = assess_candidate(
            "Some Programme Scholarship",
            "https://x.gov/scholarships/2026.html",
            GOOD_FIELDS,
        )
        assert any("template" in r for r in verdict.reasons)


# --- the rules must not reject real programmes --------------------------


class TestGenuineProgrammesStillPass:
    def test_well_formed_programme_is_accepted(self):
        verdict = assess_candidate(
            "DAAD Development-Related Postgraduate Programme",
            "https://www.daad.de/en/studying-in-germany/scholarships/",
            GOOD_FIELDS,
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT, verdict.reasons

    def test_home_economics_scholarship_still_accepted(self):
        """Regressed once: an unanchored 'home' rule killed this real award."""
        verdict = assess_candidate(
            "Home Economics Scholarship",
            "https://x.edu/scholarships/home-economics",
            GOOD_FIELDS,
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT, verdict.reasons

    def test_erasmus_programme_still_accepted(self):
        verdict = assess_candidate(
            "Erasmus Mundus Joint Masters Programme",
            "https://erasmus-plus.ec.europa.eu/programmes",
            GOOD_FIELDS,
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT, verdict.reasons

    def test_provider_supplied_via_official_source_key(self):
        fields = {k: v for k, v in GOOD_FIELDS.items() if k != "provider"}
        fields["official_source"] = "Chevening"
        verdict = assess_candidate(
            "Chevening Scholarship", "https://www.chevening.org/scholarships", fields
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT, verdict.reasons

    def test_long_description_is_fine(self):
        """Only short-label fields are length-checked; a real description is long."""
        fields = {**GOOD_FIELDS, "description": "A" * 3000}
        verdict = assess_candidate(
            "Some Programme Scholarship", "https://x.gov/scholarships/2026", fields
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT, verdict.reasons

    def test_bare_root_programme_still_accepted(self):
        """67 of 487 real records legitimately use a domain root."""
        verdict = assess_candidate(
            "DAAD Scholarship Database", "https://www.daad.de/", GOOD_FIELDS
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT, verdict.reasons

    def test_degree_vocabulary_variants_accepted(self):
        for degree in (
            "Bachelor's",
            "undergraduate",
            "PhD",
            "postdoctoral",
            "Graduate Diploma",
            "3-year course",
        ):
            verdict = assess_candidate(
                "Some Programme Scholarship",
                "https://x.gov/scholarships/2026",
                {**GOOD_FIELDS, "degree": degree},
            )
            assert verdict.verdict is DiscoveryVerdict.ACCEPT, f"{degree}: {verdict.reasons}"


# --- deadline precision coercion ----------------------------------------


class TestCoerceDeadlinePrecision:
    def test_the_live_failure_is_coerced(self):
        """`application_deadline` is 19 chars and killed every insert."""
        assert len("application_deadline") > 16
        assert coerce_deadline_precision("application_deadline") == "unknown"

    @pytest.mark.parametrize("value", sorted(DEADLINE_PRECISION_VALUES))
    def test_known_values_pass_through(self, value):
        assert coerce_deadline_precision(value) == value

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("EXACT", "exact"),
            ("  Month  ", "month"),
            ("rolling_deadline", "rolling"),
            ("varies_by_cycle", "varies"),
            (None, "unknown"),
            ("", "unknown"),
            ("", "unknown"),
        ],
    )
    def test_recognisable_fragments(self, raw, expected):
        assert coerce_deadline_precision(raw) == expected

    @pytest.mark.parametrize("raw", ["application_deadline", "zzz", "?", 12345, object()])
    def test_unrecognised_becomes_unknown_not_a_crash(self, raw):
        result = coerce_deadline_precision(raw)
        assert result == "unknown"
        assert len(result) <= 16

    def test_result_always_fits_the_column(self):
        """The invariant the crash violated: every result must fit String(16)."""
        for raw in ("application_deadline", "x" * 200, "exact", None, 12345):
            assert len(coerce_deadline_precision(raw)) <= 16


# --- quarantine backstop -------------------------------------------------


def _make_record(**kw):
    """A record that is a genuine programme unless a test says otherwise."""
    from app.models import Scholarship

    defaults = dict(
        degree="Master",
        funding="Full",
        official_source="Some University",
        official_source_url="https://x.gov/scholarships/2026",
        description="A real programme.",
        eligibility=["Open to all"],
        benefits=[],
        coverage=[],
        requirements=[],
        documents=[],
        application_method=[],
    )
    defaults.update(kw)
    return Scholarship(**defaults)


class TestQuarantineBackstop:
    """The post-hoc sweep must catch what the pre-insert gate now blocks.

    These two records reached production through the gate before it read values,
    and the backstop scored zero signals on both. They are reconstructed here
    field-for-field from what the API returned.
    """

    def test_application_timeline_menu_page_is_quarantined(self):
        from app.services.catalogue_quarantine import assess_record

        record = _make_record(
            id=492,
            title="Study in Hungary - Application Timeline",
            degree="Programmes[/LINK]",
            official_source=None,
            description=None,
            eligibility=[],
            deadline_display="for the first round of admission procedures is usually in",
            official_source_url=(
                "https://studyinhungary.hu/study-in-hungary/menu/studying-in-hungary/"
                "application-timeline.html"
            ),
        )
        verdict = assess_record(record)
        assert verdict.is_non_scholarship is True, verdict.reasons
        assert any("markup" in r for r in verdict.reasons)
        assert any("awarding body" in r for r in verdict.reasons)

    def test_find_your_programme_is_quarantined(self):
        from app.services.catalogue_quarantine import assess_record

        record = _make_record(
            id=493,
            title="Find your programme",
            degree=(
                "programmes from more than 77 esteemed institutions. Do you want "
                "to take courses taught in English? At"
            ),
            official_source=None,
            eligibility=[],
            description="programmes from more than 77 esteemed institutions",
            official_source_url="https://studyinaustria.at/study-in-austria/find-your-programme",
        )
        verdict = assess_record(record)
        assert verdict.is_non_scholarship is True, verdict.reasons
        assert any("search or listing" in r for r in verdict.reasons)
        assert any("awarding body" in r for r in verdict.reasons)


class TestCuratedCatalogueIsNotDestroyed:
    """Guards the mistake this refactor nearly shipped.

    Two rules proposed for the backstop looked reasonable and would have
    quarantined most of the catalogue when measured against the real records:

    * "short-label fields contain prose" flags `best_fit="Mid-career
      professionals with leadership potential"`, which is a correct value for a
      field the curated dataset fills descriptively. Measured: 304 of 489
      records, including DAAD, MEXT, Fulbright and Chevening.
    * "any field contains HTML markup" flags `selection_notes="...</p></div>"`,
      which is untidy stored data on Gates Cambridge, ANU, ETH Zurich and
      Fulbright - real programmes. Measured: 95 of 489 records.
    """

    def test_prose_in_curated_fields_is_not_corruption(self):
        from app.services.discovery_quality_gate import value_integrity_problems

        fields = {
            "best_fit": "Mid-career professionals with leadership potential",
            "duration": "12 months of full-time research",
            "program_type": "Postgraduate research programme",
        }
        assert value_integrity_problems(fields) == []

    def test_markup_in_prose_field_is_not_corruption(self):
        from app.services.discovery_quality_gate import value_integrity_problems

        fields = {"selection_notes": "interview in Feb.</p></div></div>"}
        assert value_integrity_problems(fields) == []

    def test_markup_in_structural_field_is_corruption(self):
        from app.services.discovery_quality_gate import value_integrity_problems

        assert value_integrity_problems({"degree": "Programmes[/LINK]"})
        assert value_integrity_problems({"title": "Home <b>Page</b>"})

    def test_template_extension_url_is_not_navigation(self):
        """JASSO's real scholarship page ends in `.html`.

        A site that never migrated to clean URLs is not evidence that a page is
        navigation, so the extension is not a shared signal.
        """
        from app.services.discovery_quality_gate import is_navigation_url

        assert not is_navigation_url(
            "https://www.jasso.go.jp/en/ryugaku/scholarship_j/shoreihi/about.html"
        )
        assert is_navigation_url("https://x.gov/menu/scholarships")
        assert is_navigation_url("https://x.gov/about")

    def test_a_real_record_with_prose_fields_survives(self):
        from app.services.catalogue_quarantine import assess_record

        record = _make_record(
            id=14,
            title="ETH Zurich Excellence Scholarship & Opportunity Programme",
            best_fit="Mid-career professionals with leadership potential",
            program_type="Postgraduate research",
            selection_notes="interview in Feb.</p></div></div>",
            official_source_url="https://ethz.ch/en/doctorate/",
        )
        assert assess_record(record).is_non_scholarship is False
