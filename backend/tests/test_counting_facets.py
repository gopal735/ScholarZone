"""Count Intelligence 2.0: facets, filter semantics and self-exclusion.

The properties under test are the ones a reader would notice being wrong.

* A facet's count is the number of records one click away. Never stale.
* Self-exclusion works: selecting Germany must not hide every other country.
* Reset is exact. The same candidate ids, counts, facets and ordering come back.
* Labels are the published strings, verbatim.
* Germany stays available, and the field facet exists.
* No facet truncates its values.

Inputs are real ``MatchResult`` objects built by the established
``make_facts`` / ``strong_profile`` helpers, so a facet bug cannot be papered over by
testing against a shape the engine never produces.
"""

from __future__ import annotations

import pytest

from app.services.counting.contract import PARTITIONS_BY_NAME
from app.services.counting.core import count_partition
from app.services.counting.facets import (
    DIMENSION_FIELDS,
    FACET_FAMILIES,
    FACET_FAMILIES_BY_NAME,
    SELF_EXCLUSION_SEMANTICS,
    FilterState,
    active_values,
    assert_facets_reconciled,
    build_facets,
    facet_candidate_sets,
    known_regions,
    region_for_country,
)

from test_matching_v2 import make_facts, score, strong_profile

from app.services.matching.types import MatchProfileRequest


COUNTRIES = ["Germany", "France", "India", "Canada", "Brazil"]


def results_for_countries(countries):
    """One result per country, in the order given."""
    scored = []
    for index, country in enumerate(countries):
        facts = make_facts(
            id=index + 1,
            country=country,
            official_source=f"University of {country}",
        )
        scored.append(score(strong_profile(preferred_countries=[country]), facts))
    return scored


@pytest.fixture
def germany_results():
    return results_for_countries(COUNTRIES)


def buckets_of(facets, family):
    return {bucket.key: bucket.count for bucket in facets[family]}


# ---------------------------------------------------------------------------
# Facet completeness
# ---------------------------------------------------------------------------


class TestFacetCoverage:
    def test_every_required_family_is_implemented(self):
        names = {family.name for family in FACET_FAMILIES}
        required = {
            "countries",
            "regions",
            "degree_levels",
            "fields",
            "funding_states",
            "eligibility_states",
            "fit_bands",
            "confidence_bands",
            "coverage_bands",
            "readiness_bands",
            "deadline_buckets",
        }
        assert required <= names

    def test_every_family_names_its_dimension_and_labels(self):
        for family in FACET_FAMILIES:
            assert family.dimension in DIMENSION_FIELDS
            assert family.label
            assert family.note

    def test_every_bucket_has_a_readable_label(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        for family, buckets in facets.items():
            for bucket in buckets:
                assert bucket.label, f"{family}/{bucket.key}"

    def test_a_filtered_facet_set_still_reconciles(self, germany_results):
        facets = build_facets(germany_results, FilterState(countries=("Germany",)))
        assert_facets_reconciled(facets, facet_candidate_sets(germany_results, FilterState(countries=("Germany",))))

    def test_an_empty_candidate_set_produces_empty_facets_without_erroring(self):
        facets = build_facets([], FilterState())
        for family in FACET_FAMILIES:
            assert facets[family.name] == []


# ---------------------------------------------------------------------------
# Country and label preservation
# ---------------------------------------------------------------------------


class TestCountryFacet:
    def test_every_country_present_is_offered(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        assert set(buckets_of(facets, "countries")) == set(COUNTRIES)

    def test_germany_stays_available(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        assert "Germany" in buckets_of(facets, "countries")

    def test_country_labels_are_the_published_names_verbatim(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        germany = next(b for b in facets["countries"] if b.key == "Germany")
        assert germany.label == "Germany"

    def test_degree_labels_are_not_title_cased(self, germany_results):
        """A published degree string is echoed exactly.

        "Bachelor's, Master's" title-cased becomes "Bachelor'S, Master'S", and "PhD"
        becomes "Phd". Restyling text ScholarZone did not author is a defect the
        reader sees immediately.
        """
        from app.services.matching.engine import score_record
        from app.services.matching.normalize import normalise_profile

        facts = make_facts(id=1, degree_levels="Bachelor's, Master's")
        result = score_record(normalise_profile(strong_profile()), facts, facts_deadline())
        facets = build_facets([result], FilterState())
        labels = [bucket.label for bucket in facets["degree_levels"]]
        assert labels == ["Bachelor's, Master's"]

    def test_values_are_never_truncated(self):
        many = [f"Country {index:02d}" for index in range(60)]
        facets = build_facets(results_for_countries(many), FilterState())
        assert len(facets["countries"]) == 60


def facts_deadline():
    from test_matching_v2 import AS_OF

    return AS_OF


# ---------------------------------------------------------------------------
# Self-exclusion
# ---------------------------------------------------------------------------


class TestSelfExclusion:
    def test_selecting_a_country_does_not_hide_the_other_countries(self, germany_results):
        state = FilterState(countries=("Germany",))
        facets = build_facets(germany_results, state)
        assert set(buckets_of(facets, "countries")) == set(COUNTRIES)

    def test_other_dimensions_still_apply_to_the_country_facet(self, germany_results):
        """Self-exclusion removes only the facet's own dimension.

        With a degree filter active, the country facet still has to respect it -
        otherwise "France (4)" would promise four results that filtering by degree
        then contradicts.
        """
        state = FilterState(countries=("Germany",), degree=("Master",))
        facets = build_facets(germany_results, state)
        assert buckets_of(facets, "countries")["France"] == 1

    def test_the_filtered_list_itself_is_still_reduced(self, germany_results):
        state = FilterState(countries=("Germany",))
        assert len(state.filter(germany_results)) == 1

    def test_self_exclusion_can_be_switched_off(self, germany_results):
        state = FilterState(countries=("Germany",))
        facets = build_facets(germany_results, state, self_exclusion=False)
        assert set(buckets_of(facets, "countries")) == {"Germany"}

    def test_the_semantics_are_published_not_implied(self):
        assert "except its own" in SELF_EXCLUSION_SEMANTICS
        assert "count_basis" in SELF_EXCLUSION_SEMANTICS

    def test_a_facets_candidate_set_relaxes_exactly_one_dimension(self, germany_results):
        """Self-exclusion is surgical: one dimension out, the rest held."""
        state = FilterState(countries=("Germany",), degree=("Master",))
        sets = facet_candidate_sets(germany_results, state)

        # Each family relaxes its own dimension and keeps every other one. The
        # country facet therefore sees all five countries again, while the degree
        # facet still sees only the German record - Germany is a different dimension
        # and was never relaxed.
        assert len(sets["countries"]) == len(germany_results)
        assert len(sets["degree_levels"]) == 1
        assert len(sets["fit_bands"]) == 1
        assert len(sets["funding_states"]) == 1


# ---------------------------------------------------------------------------
# Filter composition and reset
# ---------------------------------------------------------------------------


class TestFilterState:
    def test_dimensions_combine_as_and_values_as_or(self, germany_results):
        both = FilterState(countries=("Germany", "France")).filter(germany_results)
        assert len(both) == 2

    def test_two_dimensions_intersect(self, germany_results):
        state = FilterState(countries=("Germany",), degree=("Master",))
        assert len(state.filter(germany_results)) == 1

    def test_an_impossible_filter_yields_nothing_rather_than_everything(self, germany_results):
        assert FilterState(countries=("Atlantis",)).filter(germany_results) == []

    def test_an_empty_state_filters_nothing(self, germany_results):
        assert len(FilterState().filter(germany_results)) == len(germany_results)

    def test_the_active_state_is_published_for_provenance(self):
        state = FilterState(countries=("Germany",), funding=("FULL",))
        assert state.active() == {"COUNTRY": ["Germany"], "FUNDING": ["FULL"]}

    def test_an_empty_state_reports_nothing_active(self):
        assert FilterState().active() == {}
        assert FilterState().is_empty()

    def test_active_values_reads_the_selected_values(self):
        state = FilterState(countries=("Germany", "France"), region="europe")
        assert active_values(state, "COUNTRY") == ["Germany", "France"]
        assert active_values(state, "REGION") == ["europe"]
        assert active_values(state, "DEGREE") == []

    def test_the_fingerprint_is_order_independent(self):
        left = FilterState(countries=("Germany", "France"), degree=("Master",))
        right = FilterState(countries=("France", "Germany"), degree=("Master",))
        assert left.fingerprint() == right.fingerprint()

    def test_different_states_have_different_fingerprints(self):
        assert (
            FilterState(countries=("Germany",)).fingerprint()
            != FilterState(countries=("France",)).fingerprint()
        )


class TestResetIntegrity:
    def test_reset_restores_the_same_ids_counts_facets_and_ordering(self, germany_results):
        """The central reset guarantee.

        An unfiltered request is the reference. A request that filters and then
        resets must be indistinguishable from never having filtered at all -
        not merely similar.
        """
        pristine = FilterState()
        filtered = FilterState(countries=("Germany",))

        reference_ids = [item.scholarship_id for item in pristine.filter(germany_results)]
        reference_facets = build_facets(germany_results, pristine)

        reset_ids = [item.scholarship_id for item in filtered.without("COUNTRY").filter(germany_results)]
        reset_facets = build_facets(germany_results, filtered.without("COUNTRY"))

        assert reset_ids == reference_ids
        assert reset_facets == reference_facets
        assert filtered.without("COUNTRY").fingerprint() == pristine.fingerprint()

    def test_filtering_preserves_the_original_ranking_order(self, germany_results):
        ranked_ids = [item.scholarship_id for item in germany_results]
        filtered_ids = [
            item.scholarship_id
            for item in FilterState(countries=("France", "Germany")).filter(germany_results)
        ]
        assert filtered_ids == [i for i in ranked_ids if i in set(filtered_ids)]

    def test_a_reset_request_reproduces_the_initial_counts_exactly(self, germany_results):
        pristine = FilterState()
        after = FilterState(countries=("Brazil",)).without("COUNTRY")
        first = count_partition(pristine.filter(germany_results), PARTITIONS_BY_NAME["eligibility"])
        second = count_partition(after.filter(germany_results), PARTITIONS_BY_NAME["eligibility"])
        assert [b.count for b in first.buckets] == [b.count for b in second.buckets]


# ---------------------------------------------------------------------------
# Region facet
# ---------------------------------------------------------------------------


class TestRegionFacet:
    def test_europe_is_a_known_curated_region(self):
        assert "europe" in known_regions()

    def test_a_country_in_exactly_one_region_resolves(self):
        assert region_for_country("Germany") == "europe"

    def test_a_country_in_two_regions_has_no_single_region_value(self):
        """Mexico is in both North America and Latin America.

        Assigning either would be an invention, so the country is absent from the
        region facet instead.
        """
        assert region_for_country("Mexico") is None

    def test_a_country_in_no_curated_region_resolves_to_nothing(self):
        assert region_for_country("Atlantis") is None

    def test_the_region_facet_only_contains_curated_regions(self, germany_results):
        """Facet keys are curated region names, never inferred groupings."""
        facets = build_facets(germany_results, FilterState())
        curated = set(known_regions())
        for bucket in facets["regions"]:
            assert bucket.key in curated

    def test_germany_appears_under_europe(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        assert "europe" in buckets_of(facets, "regions")

    def test_a_region_filter_matches_its_member_countries(self, germany_results):
        state = FilterState(region="europe")
        matched = {item.country for item in state.filter(germany_results)}
        assert matched == {"Germany", "France"}


# ---------------------------------------------------------------------------
# Field and remaining families
# ---------------------------------------------------------------------------


class TestFieldFacet:
    def test_the_field_facet_exists(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        assert "fields" in facets

    def test_a_resolved_field_is_offered_with_its_taxonomy_label(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        assert buckets_of(facets, "fields")
        for bucket in facets["fields"]:
            assert bucket.label

    def test_a_record_with_no_resolvable_field_is_absent_not_invented(self):
        """The field facet is a deliberate partial partition.

        Filing an unresolvable programme under a subject would be a subject ScholarZone
        chose, not one the record published.
        """
        from app.services.matching.engine import score_record
        from app.services.matching.normalize import normalise_profile

        from test_matching_v2 import AS_OF

        facts = make_facts(id=1, program_type=None, official_details={})
        result = score_record(normalise_profile(strong_profile()), facts, AS_OF)
        assert result.field is None
        facets = build_facets([result], FilterState())
        assert facets["fields"] == []

    def test_a_field_filter_selects_only_that_field(self, germany_results):
        state = FilterState(field=("computer_science",))
        for item in state.filter(germany_results):
            assert item.field == "computer_science"


class TestRemainingFamilies:
    def test_the_funding_facet_keeps_unknown_distinct_from_none(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        keys = set(buckets_of(facets, "funding_states"))
        assert keys <= {"FULL", "TUITION_PLUS_LIVING", "TUITION_ONLY", "PARTIAL", "NONE", "UNKNOWN"}

    def test_the_eligibility_facet_uses_the_three_gate_states(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        assert set(buckets_of(facets, "eligibility_states")) <= {
            "ELIGIBLE",
            "NEEDS_VERIFICATION",
            "INELIGIBLE",
        }

    def test_the_deadline_facet_has_no_fit_like_bucket(self, germany_results):
        facets = build_facets(germany_results, FilterState())
        assert set(buckets_of(facets, "deadline_buckets")) <= {
            "COMFORTABLE",
            "APPROACHING",
            "CLOSING_SOON",
            "CLOSED",
            "UNKNOWN",
        }

    def test_bucket_order_is_deterministic_and_largest_first(self):
        results = results_for_countries(["Germany", "France", "France", "France"])
        first = build_facets(results, FilterState())["countries"]
        second = build_facets(list(reversed(results)), FilterState())["countries"]
        assert [b.key for b in first] == [b.key for b in second]
        assert first[0].count >= first[-1].count

    def test_ties_are_broken_by_key_so_order_never_depends_on_input_order(self):
        results = results_for_countries(["Germany", "France"])
        buckets = build_facets(results, FilterState())["countries"]
        assert [b.key for b in buckets] == ["France", "Germany"]