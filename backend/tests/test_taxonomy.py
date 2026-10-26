"""The place taxonomy, and the funding invariant that depends on it.

These are the rules the catalogue's three free-text place columns now obey.
They are tested here because every one of them exists because a value drifted:
``USA`` and ``United States`` were both stored and the split silently defeated
near-duplicate detection, ``Australia`` was stored as a region, and a sentence
about GDP per capita was stored as one.
"""

from __future__ import annotations

import pytest

from app.services import taxonomy


class TestCanonicalCountry:
    def test_a_plain_canonical_name_is_left_alone(self):
        for name in ("Australia", "Japan", "United Kingdom", "South Korea"):
            assert taxonomy.canonical_country(name) == name

    def test_an_alias_is_folded_onto_the_stored_spelling(self):
        # The stored spelling is the one the destinations index and the country
        # filter both use, so folding onto anything else would break both.
        assert taxonomy.canonical_country("USA") == "United States"
        assert taxonomy.canonical_country("UK") == "United Kingdom"
        assert taxonomy.canonical_country("usa") == "United States"

    @pytest.mark.parametrize(
        "stored",
        ["Türkiye", "Turkiye", "TÃ¼rkiye"],
    )
    def test_turkiye_survives_every_encoding_it_arrived_in(self, stored):
        assert taxonomy.canonical_country(stored) == "Turkey"

    def test_a_sentence_opening_with_a_country_yields_that_country(self):
        assert taxonomy.canonical_country(
            "South Africa (study must be in South Africa) - for citizens of any African country"
        ) == "South Africa"

    def test_a_list_of_places_is_multiple_not_the_first_one(self):
        # The Commonwealth Scholarship. Filing it under the first country named
        # would put a UK, Irish and LMIC award in the United Kingdom.
        assert taxonomy.canonical_country(
            "United Kingdom, Republic of Ireland, low- or middle-income countries"
        ) == taxonomy.MULTIPLE
        assert taxonomy.canonical_country("Czechia, Hungary, Poland, Slovakia") == taxonomy.MULTIPLE

    def test_a_comma_inside_parentheses_is_an_address_not_a_second_country(self):
        assert taxonomy.canonical_country(
            "South Africa (AIMS, 6 Melrose Road, Muizenberg, Cape Town); applicants"
        ) == "South Africa"

    def test_a_word_that_merely_starts_like_a_country_is_not_one(self):
        # "Indian social science scholars" must not resolve to India by accident,
        # and "Indiana" must not resolve to anything at all.
        assert taxonomy.canonical_country(
            "India (Indian social science scholars; fieldwork outside India)"
        ) == "India"
        assert taxonomy.canonical_country("Indiana") == "Indiana"

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_nothing_readable_is_none(self, value):
        assert taxonomy.canonical_country(value) is None


class TestCanonicalRegion:
    def test_every_returned_value_is_in_the_enum(self):
        countries = list(taxonomy.COUNTRY_REGION) + ["USA", "UK", "Multiple", None]
        for country in countries:
            region = taxonomy.canonical_region(country, None)
            assert region is None or region in taxonomy.REGIONS

    def test_a_country_never_survives_as_its_own_region(self):
        # The category error that let a sentence be a region.
        assert taxonomy.canonical_region("Australia", "Australia") == "Oceania"
        assert taxonomy.canonical_region("Canada", "Canada") == "North America"
        assert taxonomy.canonical_region("New Zealand", "New Zealand") == "Oceania"
        assert taxonomy.canonical_region("United States", "United States") == "North America"

    def test_a_region_that_is_already_legal_is_not_overwritten(self):
        # Erasmus Mundus is a European consortium whose country is "Multiple".
        # Deriving from the country would replace a correct answer.
        assert taxonomy.canonical_region("Multiple", "Europe") == "Europe"
        assert taxonomy.canonical_region("United Kingdom", "Asia") == "Asia"

    def test_a_sentence_is_replaced_by_the_country_it_opens_with(self):
        assert taxonomy.canonical_region(
            "Germany", "Germany (host research institution)"
        ) == "Europe"
        assert taxonomy.canonical_region(
            "Chile", "Chile (online; applicants must be citizens of an OAS Member State)"
        ) == "Latin America"

    def test_a_legacy_spelling_maps_onto_the_enum(self):
        assert taxonomy.canonical_region("Japan", "Worldwide") == "Global"
        assert taxonomy.canonical_region("Brazil", "South America") == "Latin America"

    def test_multiple_country_is_global(self):
        assert taxonomy.canonical_region("Multiple", None) == "Global"

    def test_an_unreadable_region_is_none_rather_than_a_guess(self):
        assert taxonomy.canonical_region(None, "somewhere unspecified") is None
        assert taxonomy.canonical_region("Atlantis", None) is None


class TestCoverageBoolean:
    def test_a_boolean_is_read(self):
        assert taxonomy.coverage_boolean(True) is True
        assert taxonomy.coverage_boolean(False) is False

    @pytest.mark.parametrize(
        "value",
        [
            "Full tuition fees for up to 4 years",
            "partial",
            None,
            1,
            "",
        ],
    )
    def test_prose_and_near_misses_are_not_coerced(self, value):
        # A researcher's sentence is prose, not evidence. Coercing it to True is
        # how a record ends up claiming coverage nobody published.
        assert taxonomy.coverage_boolean(value) is None


class TestFundingInvariant:
    def test_full_funding_requires_tuition_coverage(self):
        assert taxonomy.fully_funded_is_permitted(True, True) is True

    def test_an_integer_column_reads_as_the_boolean_it_stores(self):
        # A SQLite BOOLEAN comes back as 1, and `1 is True` is False. Reading the
        # invariant with `is` made a correctly-stored row look unsupported and
        # would have cleared every full-funding claim on the second run.
        assert taxonomy.as_bool(1) is True
        assert taxonomy.as_bool(0) is False
        assert taxonomy.fully_funded_is_permitted(1, 1) is True
        assert taxonomy.fully_funded_is_permitted(1, 0) is False

    @pytest.mark.parametrize("tuition", [False, None, 0])
    def test_a_stipend_is_not_a_scholarship_that_pays_your_tuition(self, tuition):
        assert taxonomy.fully_funded_is_permitted(True, tuition) is False

    @pytest.mark.parametrize("tuition", ["partial", "Full tuition fees for up to 4 years", 2])
    def test_prose_is_not_boolean_evidence(self, tuition):
        assert taxonomy.fully_funded_is_permitted(True, tuition) is False

    def test_partial_funding_is_never_permitted(self):
        assert taxonomy.fully_funded_is_permitted(False, True) is False


class TestFundingLabel:
    def test_a_spelling_variant_is_folded(self):
        assert taxonomy.canonical_funding_label("Fully funded") == "Fully Funded"
        assert taxonomy.canonical_funding_label("Partial") == "Partially Funded"
        assert taxonomy.canonical_funding_label("Tuition fee waiver") == "Tuition Fee Waiver"

    def test_a_label_carrying_a_figure_is_not_flattened(self):
        # The card renders this column verbatim. Collapsing a labelled amount into
        # a bare term would publish less than the source does.
        for value in (
            "Tuition Fee Waiver (NZ$15,000 towards tuition fees)",
            "Fully Funded (4-year bond)",
            "Stipend + Accommodation + Travel",
        ):
            assert taxonomy.canonical_funding_label(value) == value


class TestSeedDataUsesCanonicalSpellings:
    """The seed modules are re-upserted by ``app.seed``, so an alias in them
    reintroduces the drift that this taxonomy exists to remove."""

    @pytest.mark.parametrize(
        "module",
        ["app.data.verified_scholarships", "app.data.additional_scholarships"],
    )
    def test_no_seed_record_stores_an_alias_country(self, module):
        import importlib
        import re

        source = open(
            importlib.import_module(module).__file__, encoding="utf-8"
        ).read()
        offenders = re.findall(r'country\s*=\s*"(USA|UK|US)"', source)
        assert not offenders, (
            f"{module} still stores alias country spellings: {set(offenders)}"
        )