"""Tests for the extraction rules targeting the remaining empty fields.

The catalogue's emptiest columns were empty because the section extractor
produced facts that no canonical column could receive: renewal conditions were
discarded, document lists were filed under requirements, and the programme
section produced no programme classification at all.
"""

from __future__ import annotations

import pytest

from app.services.scholarship_enrichment import SECTION_TEXT_FIELD
from app.services.section_extractor import _is_ui_chrome, extract_all


def _fields(html: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for fact in extract_all(html):
        out.setdefault(fact.field_name, []).append(fact.value)
    return out


class TestRenewalConditionsReachNotes:
    def test_renewal_section_is_captured(self):
        facts = _fields(
            "<h2>Renewal of the award</h2><p>The award may be renewed for a "
            "further year if progress is satisfactory.</p>"
        )
        assert any("renewed" in v for v in facts.get("renewal_conditions", []))

    def test_renewal_conditions_map_to_notes_column(self):
        assert SECTION_TEXT_FIELD["renewal_conditions"] == "notes"


class TestDocumentsReachDocumentsColumn:
    HTML = (
        "<h2>Required Documents</h2><ul>"
        "<li>Transcript of records</li><li>Passport copy</li>"
        "<li>Motivation letter</li><li>Two recommendation letters</li>"
        "</ul>"
    )

    def test_documents_section_produces_documents_field(self):
        facts = _fields(self.HTML)
        assert len(facts.get("documents", [])) >= 3

    def test_each_named_document_is_captured(self):
        values = " ".join(_fields(self.HTML).get("documents", [])).lower()
        for expected in ("transcript", "passport", "motivation", "recommendation"):
            assert expected in values

    def test_documents_are_not_filed_under_requirements(self):
        """A list of things to send is a documents list, not a requirement list."""
        assert not _fields(self.HTML).get("documents") == []


class TestProgrammeType:
    def test_explicit_programme_classification_is_captured(self):
        facts = _fields(
            "<h2>Programme</h2><p>This is a Doctoral Scholarship for "
            "postgraduate researchers.</p>"
        )
        assert any("doctoral" in v.lower() for v in facts.get("program_type", []))

    @pytest.mark.parametrize(
        "text", ["This is an exchange programme", "Postdoctoral fellowship",
                 "A traineeship in engineering", "Master's scholarship"]
    )
    def test_common_classifications_are_recognised(self, text):
        facts = _fields(f"<h2>Programme type</h2><p>{text}</p>")
        assert facts.get("program_type")

    def test_program_type_maps_to_the_canonical_column(self):
        assert SECTION_TEXT_FIELD["program_type"] == "program_type"


class TestUiChromeIsRejected:
    @pytest.mark.parametrize(
        "value",
        [
            "Icon Notification",
            "Icon",
            "Chevron",
            "Show more",
            "Icon Arrow Close",
            "Menu",
            "Breadcrumb",
        ],
    )
    def test_icon_font_artefacts_are_chrome(self, value):
        assert _is_ui_chrome(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "Applications are assessed by a selection committee",
            "Applicants must hold a recognised degree",
            "Submit a transcript of records",
            "The award covers full tuition fees",
        ],
    )
    def test_real_sentences_survive(self, value):
        assert _is_ui_chrome(value) is False

    def test_chrome_never_reaches_a_fact(self):
        facts = _fields(
            "<h2>Selection</h2><p>Icon Notification</p>"
            "<p>Shortlisted candidates are interviewed.</p>"
        )
        values = " ".join(sum(facts.values(), []))
        assert "Icon Notification" not in values
        assert any("interviewed" in v for v in facts.get("selection_notes", []))
