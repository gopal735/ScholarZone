"""Tests for section-aware extraction and the fragment-guard correction."""

from __future__ import annotations

import pytest

from app.services.scholarship_extractor import _is_usable_detail_value
from app.services.section_extractor import (
    ExtractedFact,
    classify_section,
    extract_all,
    extract_jsonld,
    extract_sections,
    split_sections,
)


class TestFragmentGuardCorrection:
    """A real defect: the guard rejected every sentence starting with a
    function word, which silently suppressed legitimate official prose."""

    @pytest.mark.parametrize(
        "value",
        [
            "A graduate scholarship for students from developing countries.",
            "The award covers full tuition for the duration of the programme.",
            "In 2024 the programme expanded to include doctoral candidates.",
            "It is open to applicants from all participating countries.",
            "An allowance of 500 EUR is paid monthly.",
        ],
    )
    def test_legitimate_sentences_are_accepted(self, value):
        assert _is_usable_detail_value(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "of Excellence at KAIST",
            "and the following supporting documents",
            "which must be submitted with the application",
            "including travel and accommodation costs",
        ],
    )
    def test_mid_sentence_fragments_are_still_rejected(self, value):
        assert _is_usable_detail_value(value) is False

    def test_capitalised_connective_is_a_real_sentence(self):
        """Mid-sentence captures preserve casing, so a capitalised start is real."""
        assert _is_usable_detail_value("With respect to eligibility, applicants must") is True


class TestSectionSplitting:
    def test_splits_at_headings(self):
        html = "<body><h2>Benefits</h2><p>Stipend provided</p><h2>Eligibility</h2><p>Bachelor degree</p></body>"
        sections = split_sections(html)
        headings = [s.heading for s in sections]
        assert "Benefits" in headings
        assert "Eligibility" in headings

    def test_keeps_intro_before_first_heading(self):
        html = "<body><p>Intro text</p><h2>Benefits</h2><p>Stipend</p></body>"
        sections = split_sections(html)
        assert sections[0].heading == "page"
        assert "Intro text" in sections[0].text

    def test_strips_navigation_and_scripts(self):
        html = "<body><nav>Home About Contact</nav><h2>Benefits</h2><p>Stipend</p><script>var x=1</script></body>"
        text = " ".join(s.text for s in split_sections(html))
        assert "Home About Contact" not in text
        assert "var x" not in text

    def test_malformed_markup_does_not_raise(self):
        assert extract_sections("<body><h2>Unclosed") is not None


class TestSectionClassification:
    @pytest.mark.parametrize(
        "heading,topic",
        [
            ("Scholarship Benefits", "funding"),
            ("Eligibility Criteria", "eligibility"),
            ("How to apply", "application"),
            ("Required Documents", "documents"),
            ("Selection Process", "selection"),
            ("Programme Structure", "programme"),
            ("Renewal Conditions", "renewal"),
        ],
    )
    def test_maps_headings_to_topics(self, heading, topic):
        assert classify_section(heading) == topic

    def test_language_heading_beats_requirements(self):
        """'English Requirements' is about language, not eligibility."""
        assert classify_section("English Requirements") == "language"

    def test_ielts_mention_resolves_to_language(self):
        assert classify_section("Minimum IELTS score") == "language"

    def test_unknown_heading_is_none(self):
        assert classify_section("Contact Details") is None


class TestFactExtraction:
    HTML = (
        "<html><body>"
        "<h2>Scholarship Benefits</h2>"
        "<p>Living stipend: 800 EUR per month</p>"
        "<p>Full tuition fees are covered for the duration of the award.</p>"
        "<h2>Eligibility Criteria</h2>"
        "<ul><li>Applicants must hold a Bachelor degree</li>"
        "<li>Nationality: citizens of eligible countries</li></ul>"
        "<h2>How to apply</h2>"
        "<p>Deadline: 15 March 2027</p>"
        "<p>Apply through the official online portal.</p>"
        "<h2>English Requirements</h2>"
        "<p>IELTS 6.5 minimum is required.</p>"
        "</body></html>"
    )

    def _by_field(self):
        facts = {}
        for f in extract_sections(self.HTML):
            facts.setdefault(f.field_name, []).append(f)
        return facts

    def test_reads_labelled_rows(self):
        facts = self._by_field()
        assert any("800 EUR" in f.value for f in facts.get("coverage", []))

    def test_reads_prose_facts(self):
        facts = self._by_field()
        assert any("Full tuition" in f.value for f in facts.get("coverage", []))

    def test_reads_bullet_lists(self):
        facts = self._by_field()
        assert any("Bachelor degree" in f.value for f in facts.get("eligibility", []))

    def test_reads_language_section(self):
        facts = self._by_field()
        assert any("IELTS" in f.value for f in facts.get("english_requirement", []))

    def test_reads_deadline(self):
        facts = self._by_field()
        assert any("15 March 2027" in f.value for f in facts.get("application_period", []))

    def test_collects_multiple_facts_per_field_per_section(self):
        """A funding section states stipend, tuition and travel separately."""
        coverage = self._by_field().get("coverage", [])
        values = {f.value for f in coverage}
        assert len(values) >= 2, "only the first matching line was kept"

    def test_every_fact_carries_context(self):
        for fact in extract_sections(self.HTML):
            assert fact.section, "fact lost its section heading"
            assert fact.evidence, "fact lost its evidence"
            assert fact.structure in ("label_value", "bullet", "prose", "json_ld")

    def test_navigation_is_never_a_fact(self):
        for fact in extract_sections(self.HTML):
            assert "Home About Contact" not in fact.value


class TestJsonLd:
    HTML = (
        '<html><body><script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"EducationalOrganization",'
        '"description":"A graduate scholarship for students from developing countries."}'
        "</script></body></html>"
    )

    def test_extracts_description(self):
        facts = extract_jsonld(self.HTML)
        assert len(facts) == 1
        assert facts[0].field_name == "description"
        assert facts[0].confidence == "high"

    def test_invalid_json_is_ignored(self):
        facts = extract_jsonld('<script type="application/ld+json">{not json}</script>')
        assert facts == []

    def test_graph_shape_is_walked(self):
        html = (
            '<script type="application/ld+json">'
            '{"@graph":[{"description":"Nested description here."}]}'
            "</script>"
        )
        assert any(f.field_name == "description" for f in extract_jsonld(html))


class TestExtractAll:
    def test_deduplicates_field_and_value(self):
        html = (
            "<h2>Benefits</h2><p>Stipend: 500 EUR</p>"
            "<h2>More</h2><p>Stipend: 500 EUR</p>"
        )
        seen = [(f.field_name, f.value) for f in extract_all(html)]
        assert len(seen) == len(set(seen))

    def test_empty_html_is_safe(self):
        assert extract_all("") == []
        assert extract_all("<html></html>") == []
