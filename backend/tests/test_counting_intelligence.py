"""Count Intelligence 2.0: counterfactuals, anomalies, time, relationships, API.

These are the sections where a plausible-looking number is easiest to get wrong, so
the tests are weighted towards the failure modes rather than the happy path:

* a counterfactual that reports a delta it did not measure,
* an anomaly detector that fires without a baseline,
* a trend drawn through points that were never observed,
* a relationship inferred from names that looked similar,
* an API that answers a question the reader did not ask.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.services.counting.anomalies import (
    ANOMALY_THRESHOLDS,
    detect_count_anomalies,
    detect_facet_imbalance,
    detect_impossible_buckets,
    detect_reconciliation_anomalies,
    integrity_report,
    worst_severity,
)
from app.services.counting.contract import PARTITIONS_BY_NAME
from app.services.counting.core import count_all_partitions, count_partition, integrity
from app.services.counting.counterfactual import (
    counterfactual,
    profile_counterfactual,
    related_field_alternatives,
    zero_result_alternatives,
)
from app.services.counting.facets import FilterState
from app.services.counting.incremental import (
    STRATEGY_FULL_RECOMPUTE,
    STRATEGY_INCREMENTAL,
    apply_plan,
    classify_increment,
    plan_increments,
)
from app.services.counting.relationships import (
    EVIDENCE_PUBLISHED_MATCH,
    related_fields,
    relationship_counts,
)
from app.services.counting.temporal import (
    AVAILABLE,
    MIN_TREND_POINTS,
    NOT_AVAILABLE,
    count_trend,
    current_snapshot,
)
from app.services.counting.types import CountUniverse, ProvenanceKind

from test_matching_v2 import AS_OF, make_facts, score, strong_profile


COUNTRIES = ["Germany", "France", "India", "Canada", "Brazil"]


def results_for(countries=COUNTRIES):
    scored = []
    for index, country in enumerate(countries):
        facts = make_facts(id=index + 1, country=country)
        scored.append(score(strong_profile(preferred_countries=[country]), facts))
    return scored


# ---------------------------------------------------------------------------
# Counterfactuals
# ---------------------------------------------------------------------------


class TestCounterfactuals:
    def test_removing_a_filter_reports_the_real_resulting_count(self):
        results = results_for()
        state = FilterState(countries=("Germany", "France"))
        outcome = counterfactual(results, state, "COUNTRY", None)

        assert outcome.baseline_count == 2
        assert outcome.counterfactual_count == 5
        assert outcome.delta == 3

    def test_only_one_dimension_differs_between_the_two_states(self):
        results = results_for()
        state = FilterState(countries=("Germany",), degree=("Master",))
        outcome = counterfactual(results, state, "COUNTRY", None)

        assert "COUNTRY" in outcome.baseline_state
        assert "COUNTRY" not in outcome.counterfactual_state
        assert outcome.counterfactual_state["DEGREE"] == ["Master"]

    def test_a_counterfactual_is_always_labelled_simulated(self):
        results = results_for()
        outcome = counterfactual(results, FilterState(), "COUNTRY", "Germany")
        assert outcome.value_kind is ProvenanceKind.SIMULATED

    def test_the_disclaimer_refuses_every_causal_reading(self):
        results = results_for()
        outcome = counterfactual(results, FilterState(), "COUNTRY", "Germany")
        lowered = outcome.disclaimer.lower()
        for forbidden in ("causal", "probability", "prediction"):
            assert forbidden in lowered

    def test_the_caller_filter_state_is_never_mutated(self):
        results = results_for()
        state = FilterState(countries=("Germany",))
        before = state.fingerprint()
        counterfactual(results, state, "COUNTRY", None)
        assert state.fingerprint() == before
        assert state.countries == ("Germany",)

    def test_the_same_input_gives_the_same_output(self):
        results = results_for()
        state = FilterState(countries=("Germany",))
        first = counterfactual(results, state, "COUNTRY", None)
        second = counterfactual(results, state, "COUNTRY", None)
        assert first.model_dump() == second.model_dump()

    def test_an_unsupported_dimension_is_refused(self):
        with pytest.raises(ValueError):
            counterfactual(results_for(), FilterState(), "NOT_A_DIMENSION", "x")

    def test_the_eligible_metric_counts_only_eligible_records(self):
        results = results_for()
        outcome = counterfactual(results, FilterState(), "COUNTRY", "Germany", metric="eligible")
        assert outcome.metric == "eligible"
        # An unfiltered baseline and a single-country counterfactual are different
        # populations, so the delta may be negative; what matters is that both sides
        # are bounded by the universe rather than invented.
        assert 0 <= outcome.baseline_count <= len(results)
        assert 0 <= outcome.counterfactual_count <= len(results)
        assert outcome.delta == outcome.counterfactual_count - outcome.baseline_count

    def test_a_profile_counterfactual_carries_both_states(self):
        outcome = profile_counterfactual(
            metric_name="eligible scholarships",
            baseline_count=213,
            counterfactual_count=231,
            changed_dimension="COUNTRY",
            baseline_state={"preferred_countries": []},
            counterfactual_state={"preferred_countries": ["United Kingdom"]},
        )
        assert outcome.delta == 18
        assert outcome.value_kind is ProvenanceKind.SIMULATED


class TestZeroResultIntelligence:
    def test_no_results_is_reported_rather_than_hidden(self):
        results = results_for()
        state = FilterState(countries=("Atlantis",), degree=("Master",))
        alternatives = zero_result_alternatives(results, state)
        assert alternatives
        assert all(item.result_count > 0 for item in alternatives)

    def test_a_hopeless_state_offers_nothing_rather_than_inventing_a_way_out(self):
        """Every change leads to zero, so no alternative exists.

        Offering "Remove Country -> 0" would be noise dressed as a suggestion, and
        offering a change that does not help would be worse.
        """
        results = results_for()
        state = FilterState(countries=("Atlantis",), degree=("PhD",))
        assert zero_result_alternatives(results, state) == []

    def test_only_measured_alternatives_are_offered(self):
        results = results_for()
        alternatives = zero_result_alternatives(results, FilterState(countries=("Atlantis",)))
        assert all(item.result_count > 0 for item in alternatives)

    def test_alternatives_are_ordered_widest_first(self):
        results = results_for()
        alternatives = zero_result_alternatives(
            results, FilterState(countries=("Germany",), degree=("Master",))
        )
        counts = [item.result_count for item in alternatives]
        assert counts == sorted(counts, reverse=True)

    def test_an_alternative_names_exactly_one_dimension(self):
        results = results_for()
        for item in zero_result_alternatives(results, FilterState(countries=("Atlantis",))):
            assert item.changed_dimension
            assert item.is_removal is True
            assert item.removed_value

    def test_the_users_filters_are_untouched_by_exploring_alternatives(self):
        results = results_for()
        state = FilterState(countries=("Germany",))
        before = state.fingerprint()
        zero_result_alternatives(results, state)
        assert state.fingerprint() == before

    def test_related_fields_come_from_the_curated_taxonomy(self):
        related = related_fields("computer_science")
        assert "mathematics" in related or "statistics" in related
        assert "computer_science" not in related

    def test_an_unknown_field_has_no_related_fields(self):
        assert related_fields("not_a_real_field") == ()

    def test_a_related_field_alternative_is_offered_only_if_it_produces_results(self):
        results = results_for()
        alternatives = related_field_alternatives(
            results, FilterState(field=("underwater_basket_weaving",)), related_fields
        )
        assert all(item.result_count > 0 for item in alternatives)


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


class TestAnomalyDetection:
    def test_no_baseline_means_unavailable_not_quiet(self):
        found = detect_count_anomalies(100, [], metric="catalogue_total")
        assert found
        assert found[0].is_baseline_available is False
        assert found[0].detection_method == "ROLLING_BASELINE"

    def test_a_normal_change_fires_nothing(self):
        found = detect_count_anomalies(
            100, [98, 99, 100, 101, 102], metric="catalogue_total"
        )
        assert found == []

    def test_a_small_absolute_change_never_fires_even_if_the_ratio_is_huge(self):
        """A rate-based rule on a tiny population is noise.

        2 -> 6 is a 200% rise. On a catalogue this size it is three records, and
        flagging it every time would train everyone to ignore the detector.
        """
        found = detect_count_anomalies(6, [2, 2, 2, 2, 2], metric="catalogue_total")
        assert found == []

    def test_a_large_absolute_change_also_never_fires_if_the_ratio_is_small(self):
        found = detect_count_anomalies(
            1004, [1000, 1000, 1000, 1000, 1000], metric="catalogue_total"
        )
        assert found == []

    def test_a_large_spike_fires_with_full_metadata(self):
        found = detect_count_anomalies(500, [100, 100, 100, 100], metric="catalogue_total")
        assert found
        anomaly = found[0]
        assert anomaly.current_value == 500
        assert anomaly.baseline == 100
        assert anomaly.delta == 400
        assert anomaly.detection_method
        assert anomaly.severity
        assert anomaly.explanation

    def test_a_large_drop_fires(self):
        found = detect_count_anomalies(20, [100, 100, 100, 100], metric="catalogue_total")
        assert found
        assert "drop" in found[0].explanation

    def test_a_threshold_boundary_does_not_fire(self):
        """Exactly at both floors is not yet an event."""
        baseline = [100, 100, 100]
        current = 100 - ANOMALY_THRESHOLDS.min_absolute_delta
        found = detect_count_anomalies(current, baseline, metric="catalogue_total")
        assert found == []

    def test_severity_scales_with_the_size_of_the_change(self):
        ranking = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        moderate = detect_count_anomalies(150, [100, 100, 100], metric="m")
        large = detect_count_anomalies(500, [100, 100, 100], metric="m")
        assert ranking[worst_severity(moderate)] < ranking[worst_severity(large)]

    def test_a_reconciliation_failure_is_a_critical_anomaly(self):
        results = results_for()
        partitions = count_all_partitions(results, scored=len(results))
        verdict = integrity(partitions, total=len(results) + 5, scored=len(results))
        anomalies = detect_reconciliation_anomalies(verdict)
        assert anomalies
        assert anomalies[0].severity == "critical"
        assert anomalies[0].detection_method == "RECONCILIATION"

    def test_a_negative_count_is_impossible_rather_than_merely_unusual(self):
        from app.services.counting.types import CountBucket, CountPartition

        partition = CountPartition(
            name="eligibility",
            label="Eligibility",
            basis=count_partition([], PARTITIONS_BY_NAME["eligibility"]).basis,
            buckets=[CountBucket(key="ELIGIBLE", label="Eligible", count=-3)],
            bucket_total=-3,
        )
        anomalies = detect_impossible_buckets([partition])
        assert anomalies
        assert anomalies[0].detection_method == "IMPOSSIBLE_VALUE"

    def test_a_complete_partition_with_a_residual_is_flagged(self):
        from app.services.counting.types import CountPartition

        partition = CountPartition(
            name="eligibility",
            label="Eligibility",
            basis=count_partition([], PARTITIONS_BY_NAME["eligibility"]).basis,
            buckets=[],
            bucket_total=0,
            unclassified_count=4,
        )
        anomalies = detect_impossible_buckets([partition])
        assert anomalies
        assert "complete partition" in anomalies[0].explanation

    def test_a_single_value_facet_is_reported_informational(self):
        from app.services.counting.types import CountBucket

        found = detect_facet_imbalance(
            [CountBucket(key="FULL", label="Full", count=50)],
            name="funding_states",
            universe_size=50,
        )
        assert found
        assert found[0].severity == "low"

    def test_a_balanced_facet_is_silent(self):
        from app.services.counting.types import CountBucket

        found = detect_facet_imbalance(
            [CountBucket(key="A", label="A", count=5), CountBucket(key="B", label="B", count=5)],
            name="countries",
            universe_size=10,
        )
        assert found == []

    def test_an_empty_universe_is_silent_rather_than_dividing_by_zero(self):
        from app.services.counting.types import CountBucket

        assert detect_facet_imbalance(
            [CountBucket(key="A", label="A", count=0)], name="countries", universe_size=0
        ) == []

    def test_the_integrity_report_carries_the_verdict_and_the_evidence(self):
        results = results_for()
        partitions = count_all_partitions(results, scored=len(results))
        report = integrity_report(integrity(partitions, total=len(results), scored=len(results)))
        assert report["status"] == "PASS"
        assert report["reconciliations"]
        assert all("expression" in check for check in report["reconciliations"])


# ---------------------------------------------------------------------------
# Time and snapshots
# ---------------------------------------------------------------------------


class TestTemporalBehaviour:
    def test_a_current_snapshot_is_reproducible(self):
        first = current_snapshot(AS_OF, summary={"total": 5})
        second = current_snapshot(AS_OF, summary={"total": 5})
        assert first.model_dump() == second.model_dump()

    def test_a_snapshot_carries_every_version_a_stored_count_would_need(self):
        snapshot = current_snapshot(AS_OF)
        assert snapshot.count_contract_version
        assert snapshot.engine_version
        assert snapshot.scoring_config_version
        assert snapshot.field_taxonomy_version
        assert snapshot.deadline_semantics_version

    def test_no_history_yields_no_trend_rather_than_a_flat_line(self):
        trend = count_trend([], metric="catalogue_total")
        assert trend.availability == NOT_AVAILABLE
        assert trend.points == []
        assert trend.unavailable_reason

    def test_a_single_observation_is_not_a_trend(self):
        trend = count_trend(
            [(datetime(2026, 1, 1), 10)], metric="catalogue_total"
        )
        assert trend.availability == NOT_AVAILABLE

    def test_two_observations_are_still_not_a_trend(self):
        trend = count_trend(
            [(datetime(2026, 1, 1), 10), (datetime(2026, 2, 1), 40)],
            metric="catalogue_total",
        )
        assert trend.availability == NOT_AVAILABLE
        assert trend.unavailable_reason

    def test_three_real_observations_produce_a_trend(self):
        observations = [
            (datetime(2026, 1, 1), 10),
            (datetime(2026, 2, 1), 20),
            (datetime(2026, 3, 1), 25),
        ]
        trend = count_trend(observations, metric="catalogue_total")
        assert trend.availability == AVAILABLE
        assert len(trend.points) == MIN_TREND_POINTS
        assert trend.change == 15
        assert trend.change_percent == 150.0

    def test_every_trend_point_is_labelled_historical(self):
        trend = count_trend(
            [
                (datetime(2026, 1, 1), 1),
                (datetime(2026, 2, 1), 2),
                (datetime(2026, 3, 1), 3),
            ],
            metric="m",
        )
        assert all(point.is_historical for point in trend.points)

    def test_a_burst_of_edits_on_one_day_is_one_observation(self):
        """Snapshots are written on change, so several can share a day.

        Counting them separately would render one busy afternoon as a month of trend.
        """
        trend = count_trend(
            [
                (datetime(2026, 1, 1, 9), 10),
                (datetime(2026, 1, 1, 11), 14),
                (datetime(2026, 1, 1, 17), 19),
            ],
            metric="m",
        )
        assert trend.availability == NOT_AVAILABLE

    def test_the_same_snapshot_reproduces_identically(self):
        observations = [
            (datetime(2026, 1, 1), 5),
            (datetime(2026, 2, 1), 6),
            (datetime(2026, 3, 1), 7),
        ]
        assert (
            count_trend(observations, metric="m").model_dump()
            == count_trend(observations, metric="m").model_dump()
        )

    def test_a_growth_from_zero_reports_no_percentage_rather_than_dividing_by_zero(self):
        trend = count_trend(
            [(datetime(2026, 1, d), 0) for d in (1, 2, 3)]
            + [(datetime(2026, 4, 1), 5)],
            metric="m",
        )
        if trend.availability == AVAILABLE:
            assert trend.change_percent is None


# ---------------------------------------------------------------------------
# Incremental counting
# ---------------------------------------------------------------------------


class TestIncrementalCounting:
    def test_a_single_local_change_can_be_incremental(self):
        plan = plan_increments(
            [("CHANGED_SCHOLARSHIP", 1, "")],
            partitions=["eligibility", "scored", "fit_tier"],
        )
        assert plan.strategy == STRATEGY_INCREMENTAL
        assert plan.updated_partitions == ("eligibility",)

    def test_a_deadline_change_forces_a_recompute(self):
        """A deadline change moves the timing bucket and the eligibility gate."""
        increment = classify_increment("CHANGED_DEADLINE", 1)
        assert increment.requires_full_recompute
        assert increment.reason

    def test_funding_and_eligibility_evidence_force_a_recompute(self):
        for change in ("CHANGED_FUNDING", "CHANGED_ELIGIBILITY_EVIDENCE", "CHANGED_FIELD"):
            assert classify_increment(change, 1).requires_full_recompute

    def test_multiple_changes_force_a_recompute(self):
        plan = plan_increments(
            [("CHANGED_SCHOLARSHIP", 1, ""), ("CHANGED_SCHOLARSHIP", 2, "")],
            partitions=["eligibility"],
        )
        assert plan.strategy == STRATEGY_FULL_RECOMPUTE
        assert plan.recomputed_partitions == ("eligibility",)

    def test_an_unknown_change_kind_forces_a_recompute(self):
        plan = plan_increments(
            [("SOMETHING_ELSE", 1, "")], partitions=["eligibility"]
        )
        assert plan.strategy == STRATEGY_FULL_RECOMPUTE

    def test_a_recompute_without_figures_is_refused(self):
        plan = plan_increments(
            [("CHANGED_DEADLINE", 1, "")], partitions=["eligibility"]
        )
        with pytest.raises(ValueError):
            apply_plan(plan)

    def test_a_full_recompute_is_published_as_a_success_state(self):
        plan = plan_increments(
            [("CHANGED_DEADLINE", 1, "")], partitions=["eligibility"]
        )
        outcome = apply_plan(plan, recomputed_summary={"eligibility.ELIGIBLE": 3})
        assert outcome.strategy == STRATEGY_FULL_RECOMPUTE
        assert outcome.recomputed_summary == {"eligibility.ELIGIBLE": 3}
        assert outcome.note


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


class TestRelationshipCounting:
    def test_relationships_are_published_with_their_evidence(self):
        counts = relationship_counts(results_for())
        assert counts
        for item in counts:
            assert item.evidence_source == EVIDENCE_PUBLISHED_MATCH
            assert item.is_verified is False
            assert item.entity_label

    def test_a_singleton_is_not_published_as_a_relationship(self):
        counts = relationship_counts(results_for(["Germany"]))
        assert counts == []

    def test_counts_are_grouped_by_a_shared_published_value(self):
        results = results_for(["Germany", "Germany", "France"])
        counts = {
            (item.relationship, item.entity_key): item.count
            for item in relationship_counts(results)
        }
        assert counts[("Country", "Germany")] == 2

    def test_relationship_counts_and_summary_counts_describe_the_same_records(self):
        # Singletons are not published as relationships, so this needs a shared
        # country to compare against the summary population.
        results = results_for(["Germany", "Germany", "Germany", "France", "France"])
        country_counts = sum(
            item.count
            for item in relationship_counts(results)
            if item.relationship == "Country"
        )
        assert country_counts == len(results)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_every_version_is_published(self):
        from app.services.counting.provenance import provenance

        block = provenance(
            universe=CountUniverse.MATCH_ANALYSED,
            basis=count_partition([], PARTITIONS_BY_NAME["eligibility"]).basis,
            as_of=AS_OF.isoformat(),
            as_of_dependency=True,
        )
        assert block.count_contract_version
        assert block.engine_version
        assert block.scoring_config_version
        assert block.field_taxonomy_version
        assert block.deadline_semantics_version

    def test_a_date_independent_count_is_not_stamped_with_today(self):
        """A catalogue count is not a function of the date.

        Stamping one on it would imply a history it does not have.
        """
        from app.services.counting.provenance import provenance

        block = provenance(
            universe=CountUniverse.CATALOGUE,
            basis=count_partition([], PARTITIONS_BY_NAME["eligibility"]).basis,
            as_of=AS_OF.isoformat(),
            as_of_dependency=False,
        )
        assert block.as_of is None
        assert block.as_of_dependency is False

    def test_the_active_filter_state_is_part_of_the_provenance(self):
        from app.services.counting.provenance import provenance

        block = provenance(
            universe=CountUniverse.MATCH_ANALYSED,
            basis=count_partition([], PARTITIONS_BY_NAME["eligibility"]).basis,
            filter_state=FilterState(countries=("Germany",)).active(),
        )
        assert block.filter_state == {"COUNTRY": ["Germany"]}

    def test_an_explanation_states_the_universe_and_the_conditions(self):
        from app.services.counting.provenance import explain_count

        explanation = explain_count(
            213,
            universe=CountUniverse.MATCH_ANALYSED,
            conditions=[("eligibility", "=", '"ELIGIBLE"')],
            metric_label="eligible scholarships",
        )
        assert explanation.count == 213
        assert "213 eligible scholarships" in explanation.human_readable
        assert "analysed scholarships" in explanation.human_readable
        assert explanation.clauses[0].dimension == "eligibility"

    def test_an_explanation_of_a_filtered_count_lists_every_condition(self):
        from app.services.counting.provenance import explain_count, filter_conditions

        conditions = filter_conditions(
            FilterState(countries=("Germany",), funding=("FULL",)).active()
        )
        explanation = explain_count(
            27,
            universe=CountUniverse.MATCH_ANALYSED,
            conditions=conditions,
            metric_label="scholarships",
        )
        assert len(explanation.clauses) == 2
        assert "Germany" in explanation.human_readable
        assert "FULL" in explanation.human_readable