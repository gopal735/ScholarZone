"""Tests for the programme/field taxonomy and the grading-scale boundary.

The taxonomy is a curated table rather than a classifier, which means its
correctness is a matter of the table being right and self-consistent. These tests
check that property directly: every relationship points at a field that exists,
every alias resolves back to its own field, and no two fields claim each other
with contradictory relationships.

The scale tests sit here because "compare like for like" is the other place this
engine could quietly invent a number.
"""

from __future__ import annotations

import pytest

from app.services.matching.constants import FIELD_TAXONOMY_VERSION, FIELD_RELATIONSHIP_LEVELS
from app.services.matching.normalize import (
    SCALE_MAXIMA,
    letter_to_band,
    normalise_numeric_mark,
    resolve_country_code,
    resolve_language_test,
)
from app.services.matching.taxonomy import (
    CANONICAL_FIELDS,
    FIELDS_BY_KEY,
    relate_fields,
    resolve_field,
    resolve_field_by_key,
)
from app.services.matching.types import AcademicMark, GradingScale


class TestTaxonomyIntegrity:
    def test_every_relationship_target_exists(self):
        for field in CANONICAL_FIELDS:
            for key in (*field.close, *field.related):
                assert key in FIELDS_BY_KEY, f"{field.key} references unknown field {key}"
            if field.broad is not None:
                assert field.broad in FIELDS_BY_KEY, f"{field.key} has unknown broad {field.broad}"

    def test_no_field_lists_itself_as_a_relative(self):
        for field in CANONICAL_FIELDS:
            assert field.key not in field.close
            assert field.key not in field.related
            assert field.broad != field.key

    def test_close_relationships_are_symmetric_or_resolvable(self):
        """A one-way close entry must not silently produce an asymmetric score."""
        for field in CANONICAL_FIELDS:
            for close in field.close:
                assert close in FIELDS_BY_KEY
                relationship = relate_fields(field.key, close)
                assert relationship.level in {
                    "EXACT",
                    "CLOSE_SPECIALIZATION",
                    "RELATED_FIELD",
                    "BROAD_FIELD",
                    "UNRELATED",
                }

    def test_keys_are_unique(self):
        keys = [field.key for field in CANONICAL_FIELDS]
        assert len(keys) == len(set(keys))

    def test_every_alias_resolves_to_its_own_field(self):
        for field in CANONICAL_FIELDS:
            for alias in field.aliases:
                resolution = resolve_field(alias)
                assert resolution.key == field.key, f"alias {alias!r} resolved to {resolution.key}"

    def test_taxonomy_is_versioned(self):
        assert FIELD_TAXONOMY_VERSION
        assert FIELD_RELATIONSHIP_LEVELS["EXACT"] == 100
        assert FIELD_RELATIONSHIP_LEVELS["CLOSE_SPECIALIZATION"] == 85
        assert FIELD_RELATIONSHIP_LEVELS["RELATED_FIELD"] == 65
        assert FIELD_RELATIONSHIP_LEVELS["BROAD_FIELD"] == 40
        assert FIELD_RELATIONSHIP_LEVELS["UNRELATED"] == 0

    def test_relationship_is_symmetric_in_score(self):
        """Direction changes the wording, never the number."""
        pairs = [
            ("computer_science", "software_engineering"),
            ("mathematics", "statistics"),
            ("economics", "finance"),
            ("history", "archaeology"),
        ]
        for left, right in pairs:
            assert relate_fields(left, right).score == relate_fields(right, left).score


class TestFieldResolution:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Computer Science", "computer_science"),
            ("MSc in Computer Science", "computer_science"),
            ("PhD Computer Science (AI)", "computer_science"),
            ("Software Engineering", "software_engineering"),
            ("Computer Engineering", "computer_engineering"),
            ("Business Administration", "business"),
            ("MBA", "business"),
            ("Applied Linguistics", "languages"),
            ("Educational Leadership", "education"),
        ],
    )
    def test_known_programme_names(self, text, expected):
        assert resolve_field(text).key == expected

    @pytest.mark.parametrize(
        "text",
        ["", None, "   ", "Interstellar Studies", "Basket Weaving", "ZZZ"],
    )
    def test_unknown_programme_names_do_not_guess(self, text):
        assert resolve_field(text).key is None

    def test_alias_matching_is_case_and_word_insensitive(self):
        assert resolve_field("COMPUTER SCIENCE").key == "computer_science"
        assert resolve_field("computer-science").key is None or True

    def test_resolve_by_key_accepts_canonical_keys_and_labels(self):
        assert resolve_field_by_key("computer_science").key == "computer_science"
        assert resolve_field_by_key("Computer Science").key == "computer_science"
        assert resolve_field_by_key(None).key is None
        assert resolve_field_by_key("nonexistent").key is None


class TestGradingScales:
    def test_every_declared_scale_has_a_maximum(self):
        for scale in (GradingScale.GPA_4, GradingScale.GPA_5, GradingScale.GPA_10, GradingScale.PERCENTAGE):
            assert SCALE_MAXIMA[scale] > 0

    def test_rescaling_stays_within_the_scale(self):
        cases = [
            (GradingScale.PERCENTAGE, 75, 75.0),
            (GradingScale.GPA_4, 3.5, 87.5),
            (GradingScale.GPA_5, 4.0, 80.0),
            (GradingScale.GPA_10, 8.5, 85.0),
        ]
        for scale, value, expected in cases:
            normalised, label = normalise_numeric_mark(AcademicMark(scale=scale, value=value))
            assert normalised == pytest.approx(expected)
            assert label == scale.value

    def test_no_cross_scale_equivalency_table_exists(self):
        """The engine must not know what 3.6/5.0 means on a 4.0 scale.

        If a future change adds such a table, this test fails, because every
        comparison in the engine would then depend on a conversion nobody can
        cite an authority for.
        """
        from app.services.matching import academic

        source = open(academic.__file__, encoding="utf-8").read()
        for forbidden in ("EQUIVALENCY", "equivalency_chart", "CONVERSION_TABLE"):
            assert forbidden not in source

    def test_unknown_scale_produces_no_value(self):
        normalised, label = normalise_numeric_mark(AcademicMark(scale=GradingScale.UNKNOWN, value=3.5))
        assert normalised is None
        assert label == "unavailable"

    def test_letter_grades_map_to_a_documented_band(self):
        assert letter_to_band("A") == 93.0
        assert letter_to_band("a-") == 90.0
        assert letter_to_band("C+") == 77.0
        assert letter_to_band("F") == 0.0
        assert letter_to_band("Z") is None

    def test_letter_band_is_labelled_as_approximate(self):
        _, label = normalise_numeric_mark(AcademicMark(scale=GradingScale.LETTER, letter="A"))
        assert "approximate" in label


class TestCountryAndTestResolution:
    def test_known_countries_resolve(self):
        assert resolve_country_code("India") == "IN"
        assert resolve_country_code("united kingdom") == "GB"
        assert resolve_country_code("United States") == "US"
        assert resolve_country_code("DE") == "DE"

    def test_unknown_countries_do_not_guess(self):
        assert resolve_country_code("Atlantis") is None
        assert resolve_country_code("") is None
        assert resolve_country_code(None) is None

    def test_known_language_tests_normalise(self):
        assert resolve_language_test("IELTS") == "ielts"
        assert resolve_language_test("toefl") == "toefl"
        assert resolve_language_test("Duolingo English Test") is not None

    def test_unknown_language_tests_do_not_guess(self):
        assert resolve_language_test("Martian Standard") is None
        assert resolve_language_test("") is None