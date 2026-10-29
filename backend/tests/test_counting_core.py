"""Count Intelligence 2.0: the counting core and the count contract.

Reuses the established ``make_facts`` / ``strong_profile`` helpers from
``test_matching_v2`` by importing them, rather than declaring a second database
fixture or a second set of record builders. The counting layer's correctness claim
is that it measures the engine's output correctly, so its inputs have to be the
engine's real output.

The invariants under test are the ones the architecture makes mandatory:

    eligible + needs_verification + ineligible == total_candidates
    scored     + not_scored                == total_candidates
    fit tiers                              == scored_count

and, around them: that a null is never counted as zero, that a known-unknown is
never folded into a measured bucket, that one candidate reconciles like any other,
and that the contract cannot be loaded in an inconsistent state.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.counting import contract as counting_contract
from app.services.counting.contract import (
    COUNT_CONTRACT_VERSION,
    METRICS,
    PARTITIONS,
    PARTITIONS_BY_NAME,
    contract_snapshot,
    metrics_for,
)
from app.services.counting.core import (
    CountError,
    count_all_partitions,
    count_partition,
    distribution,
    integrity,
    partition_population,
    reconcile,
)
from app.services.counting.types import CountBasis, CountUniverse, IntegrityStatus

from test_matching_v2 import AS_OF, make_facts, score, strong_profile

from app.services.matching.types import (
    EligibilityStatus,
    FundingState,
    MatchProfileRequest,
    ScholarshipFacts,
)


def results_for(count: int, **fact_overrides):
    """``count`` scored results from records that differ only in their id."""
    scored = []
    for index in range(count):
        facts = make_facts(id=index + 1, **fact_overrides)
        scored.append(score(strong_profile(), facts))
    return scored


# ---------------------------------------------------------------------------
# The contract itself
# ---------------------------------------------------------------------------


class TestCountContract:
    def test_the_contract_declares_a_version(self):
        assert COUNT_CONTRACT_VERSION == "2.0.0"

    def test_every_partition_names_its_universe_explicitly(self):
        for spec in PARTITIONS:
            assert isinstance(spec.universe, CountUniverse)

    def test_every_metric_defines_all_nine_required_attributes(self):
        for metric in METRICS:
            assert metric.name
            assert metric.universe
            assert metric.partition
            assert isinstance(metric.partition_type, CountBasis)
            assert metric.null_policy is not None
            assert metric.unknown_policy is not None
            assert isinstance(metric.as_of_dependency, bool)
            assert isinstance(metric.engine_dependency, tuple)
            assert isinstance(metric.version_dependency, tuple)

    def test_metric_names_are_unique(self):
        names = [metric.name for metric in METRICS]
        assert len(names) == len(set(names))

    def test_every_partition_has_a_metric_for_every_bucket(self):
        for spec in PARTITIONS:
            for key, _label in spec.buckets:
                names = {metric.name for metric in metrics_for(spec.name)}
                assert f"{spec.name}.{key}" in names

    def test_the_three_canonical_universes_are_all_declared_and_all_produced(self):
        declared = {spec.universe for spec in PARTITIONS}
        assert CountUniverse.CATALOGUE in declared
        assert CountUniverse.MATCH_ANALYSED in declared

        # MATCH_RETURNED_PAGE is not a partition: it is the basis facet counts
        # describe. It has to name a real producer or it is a naming convention.
        snapshot = contract_snapshot()
        assert CountUniverse.MATCH_RETURNED_PAGE.value in snapshot["universe_producers"]
        for universe, producer in snapshot["universe_producers"].items():
            assert producer, universe

    def test_the_fit_tiers_reconcile_to_the_scored_set_not_the_universe(self):
        assert PARTITIONS_BY_NAME["fit_tier"].reconciles_against == "SCORED"

    def test_eligibility_declares_exactly_the_three_gate_states(self):
        buckets = [key for key, _ in PARTITIONS_BY_NAME["eligibility"].buckets]
        assert buckets == ["ELIGIBLE", "NEEDS_VERIFICATION", "INELIGIBLE"]

    def test_the_deadline_precision_partition_covers_both_recurring_vocabularies(self):
        """One concept, two spellings, both counted.

        `deadline_semantics` spells the recurring state "recurring"; the Match result
        publishes "annual". Declaring only one leaves records uncounted - which is how
        this was found, by reconciliation refusing to publish a 89-of-91 partition.
        Picking one spelling would mean changing a Match 2.0 module, so the contract
        covers the union instead.
        """
        keys = [key for key, _ in PARTITIONS_BY_NAME["deadline_precision"].buckets]
        assert "recurring" in keys
        assert "annual" in keys

    def test_every_value_the_engine_publishes_for_precision_has_a_bucket(self):
        from app.services.matching.engine import score_record
        from app.services.matching.normalize import normalise_profile

        spec = PARTITIONS_BY_NAME["deadline_precision"]
        buckets = {key for key, _ in spec.buckets}
        for precision in ("exact", "month", "rolling", "annual", "recurring", "unknown"):
            result = score_record(
                normalise_profile(strong_profile()),
                make_facts(id=1, deadline_precision=precision),
                AS_OF,
            )
            assert result.deadline_precision in buckets, precision

    def test_unknown_funding_is_its_own_bucket_and_never_folded(self):
        buckets = [key for key, _ in PARTITIONS_BY_NAME["funding"].buckets]
        assert "UNKNOWN" in buckets
        assert "NONE" in buckets
        # They must remain distinct: collapsing them would report a published "no
        # funding" for a record whose funding was simply never established.
        assert buckets.index("UNKNOWN") != buckets.index("NONE")

    def test_the_snapshot_is_serialisable_and_complete(self):
        snapshot = contract_snapshot()
        assert snapshot["count_contract_version"] == COUNT_CONTRACT_VERSION
        assert len(snapshot["partitions"]) == len(PARTITIONS)
        for declared in snapshot["partitions"]:
            assert declared["name"]
            assert declared["partition_type"] in {basis.value for basis in CountBasis}
            assert declared["buckets"]

    def test_loading_an_unknown_metric_is_an_error_not_a_default(self):
        with pytest.raises(KeyError):
            counting_contract.metric("eligibility.NOT_A_STATE")

    def test_a_metric_with_no_predicate_refuses_to_evaluate(self):
        unclassified = counting_contract.metric("fit_tier.UNCLASSIFIED")
        with pytest.raises(ValueError):
            unclassified.evaluate(object())


# ---------------------------------------------------------------------------
# Partition counting
# ---------------------------------------------------------------------------


class TestCountingPartitions:
    def test_an_empty_universe_counts_zero_everywhere(self):
        partitions = count_all_partitions([])
        assert partitions
        for partition in partitions:
            assert partition.bucket_total == 0

    def test_a_single_candidate_reconciles(self):
        results = results_for(1)
        partitions = count_all_partitions(results, scored=len(results))
        verdict = integrity(partitions, total=1, scored=1)
        assert verdict.status is IntegrityStatus.PASS

    def test_eligibility_states_sum_to_total_candidates(self):
        for size in (1, 3, 7):
            results = results_for(size)
            partitions = count_all_partitions(results, scored=size)
            verdict = integrity(partitions, total=size, scored=size)
            assert verdict.status is IntegrityStatus.PASS, size

    def test_scored_and_not_scored_partition_the_whole_universe(self):
        results = results_for(5)
        scored_partition = count_partition(results, PARTITIONS_BY_NAME["scored"])
        buckets = {bucket.key: bucket.count for bucket in scored_partition.buckets}
        assert buckets["SCORED"] + buckets["NOT_SCORED"] == 5

    def test_the_scored_partition_counts_a_not_scored_record(self):
        """A record nothing could be evaluated for is NOT_SCORED, not absent.

        Both halves of the partition have to be real predicates, or the pair cannot
        sum to the universe.
        """
        result = score(strong_profile(), make_facts(id=1, eligibility=[], requirements=[]))
        if result.fit_score is not None:
            pytest.skip("this record still produced a fit score")
        partition = count_partition([result], PARTITIONS_BY_NAME["scored"])
        buckets = {bucket.key: bucket.count for bucket in partition.buckets}
        assert buckets["NOT_SCORED"] == 1
        assert buckets["SCORED"] == 0

    def test_fit_tiers_partition_the_scored_set(self):
        results = results_for(6)
        scored = [item for item in results if item.fit_score is not None]
        partition = count_partition(
            partition_population("fit_tier", results),
            PARTITIONS_BY_NAME["fit_tier"],
        )
        assert partition.bucket_total + partition.unclassified_count == len(scored)

    def test_partition_population_of_the_fit_tiers_is_the_scored_set(self):
        results = results_for(6)
        population = partition_population("fit_tier", results)
        assert len(population) == sum(1 for item in results if item.fit_score is not None)

    def test_an_ineligible_result_carries_no_fit_tier(self):
        """The gate refuses it, so it cannot be filed under a band."""
        result = score(
            strong_profile(citizenship="Nigeria"),
            make_facts(id=1, eligibility=["Applicants must be citizens of India."]),
        )
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        assert result.fit_score is None
        partition = count_partition([result], PARTITIONS_BY_NAME["fit_tier"])
        assert partition.bucket_total == 0

    def test_a_record_with_no_funding_evidence_is_unknown_not_none(self):
        """A funding label with no verified coverage is UNKNOWN.

        It is not NONE: no coverage detail was established, which is a statement
        about our evidence rather than a statement by the awarding body.
        """
        result = score(
            strong_profile(funding_requirement=None),
            make_facts(
                id=1,
                funding_label="Fully Funded",
                funding_amount=None,
                coverage=[],
                tuition_coverage=None,
                living_cost_coverage=None,
                fully_funded=False,
            ),
        )
        assert result.funding_state is FundingState.UNKNOWN

        partition = count_partition([result], PARTITIONS_BY_NAME["funding"])
        buckets = {bucket.key: bucket.count for bucket in partition.buckets}
        assert buckets["UNKNOWN"] == 1
        assert buckets["NONE"] == 0

    def test_a_published_no_funding_is_none_and_never_unknown(self):
        result = score(
            strong_profile(funding_requirement=None),
            make_facts(
                id=1,
                funding_label="No funding available",
                funding_amount=None,
                coverage=[],
                tuition_coverage=False,
                living_cost_coverage=False,
                fully_funded=False,
            ),
        )
        assert result.funding_state is FundingState.NONE

        partition = count_partition([result], PARTITIONS_BY_NAME["funding"])
        buckets = {bucket.key: bucket.count for bucket in partition.buckets}
        assert buckets["NONE"] == 1
        assert buckets["UNKNOWN"] == 0

    def test_every_record_lands_in_exactly_one_funding_bucket(self):
        results = results_for(4)
        partition = count_partition(results, PARTITIONS_BY_NAME["funding"])
        buckets = {bucket.key: bucket.count for bucket in partition.buckets}
        assert sum(buckets.values()) == 4

    def test_counting_is_order_independent(self):
        results = results_for(8)
        forward = count_all_partitions(results, scored=8)
        backward = count_all_partitions(list(reversed(results)), scored=8)
        for left, right in zip(forward, backward):
            assert left.bucket_total == right.bucket_total

    def test_counting_the_same_records_twice_gives_the_same_numbers(self):
        results = results_for(4)
        first = count_all_partitions(results, scored=4)
        second = count_all_partitions(results, scored=4)
        assert [p.buckets for p in first] == [p.buckets for p in second]

    def test_duplicate_records_are_counted_once_each(self):
        """Two identical records are two candidates, not one.

        The counting layer never deduplicates: a catalogue containing the same
        scholarship twice really does contain two rows, and hiding one would make
        the count disagree with the listing.
        """
        one = score(strong_profile(), make_facts(id=1))
        twice = [one, one]
        partition = count_partition(twice, PARTITIONS_BY_NAME["eligibility"])
        assert partition.bucket_total == 2

    def test_an_unknown_partition_name_raises(self):
        with pytest.raises(KeyError):
            count_all_partitions([], partitions=["not_a_partition"])


# ---------------------------------------------------------------------------
# Reconciliation and integrity
# ---------------------------------------------------------------------------


class TestReconciliation:
    def test_a_correct_set_passes(self):
        results = results_for(5)
        partitions = count_all_partitions(results, scored=5)
        verdict = integrity(partitions, total=5, scored=5)
        assert verdict.status is IntegrityStatus.PASS
        assert verdict.issues == []
        assert all(check.holds for check in verdict.reconciliations)

    def test_every_reconciliation_publishes_its_expression_and_both_numbers(self):
        results = results_for(3)
        partitions = count_all_partitions(results, scored=3)
        for check in reconcile(partitions, total=3, scored=3):
            assert check.expression
            assert isinstance(check.observed, int)
            assert isinstance(check.expected, int)

    def test_a_wrong_total_is_reported_as_a_failure_not_raised(self):
        results = results_for(3)
        partitions = count_all_partitions(results, scored=3)
        verdict = integrity(partitions, total=99, scored=3)
        assert verdict.status is IntegrityStatus.FAIL
        assert verdict.issues

    def test_a_missing_baseline_is_a_warning_not_a_failure(self):
        results = results_for(4)
        partitions = count_all_partitions(results, scored=4)
        verdict = integrity(
            partitions, total=4, scored=4, warnings=["no historical baseline"]
        )
        assert verdict.status is IntegrityStatus.WARNING
        assert all(check.holds for check in verdict.reconciliations)

    def test_a_fit_partition_without_a_scored_count_cannot_be_reconciled(self):
        results = results_for(3)
        partitions = count_all_partitions(results, scored=3)
        with pytest.raises(CountError):
            reconcile(partitions, total=3, scored=None)

    def test_a_partition_that_is_not_a_partition_is_never_asserted(self):
        """Independent measures have no identity, so none is invented for them."""
        results = results_for(3)
        partitions = count_all_partitions(results, scored=3)
        names = {check.name for check in reconcile(partitions, total=3, scored=3)}
        assert not any(name.startswith("catalogue_evidence") for name in names)


# ---------------------------------------------------------------------------
# Safe aggregates
# ---------------------------------------------------------------------------


class TestDistributions:
    def test_nulls_are_excluded_and_the_exclusion_is_published(self):
        summary = distribution([1.0, None, 3.0], dimension="fit_score",
                               universe=CountUniverse.MATCH_ANALYSED)
        assert summary.sample_count == 2
        assert summary.excluded_count == 1
        assert summary.minimum == 1.0
        assert summary.maximum == 3.0

    def test_a_null_is_never_averaged_in_as_zero(self):
        with_none = distribution([10.0, None], dimension="fit_score",
                                 universe=CountUniverse.MATCH_ANALYSED)
        as_zero = distribution([10.0, 0.0], dimension="fit_score",
                               universe=CountUniverse.MATCH_ANALYSED)
        assert with_none.mean != as_zero.mean
        assert with_none.mean == 10.0

    def test_an_entirely_absent_dimension_publishes_nothing_rather_than_zero(self):
        summary = distribution([None, None], dimension="fit_score",
                               universe=CountUniverse.MATCH_ANALYSED)
        assert summary.sample_count == 0
        assert summary.mean is None
        assert summary.median is None
        assert summary.caveat

    def test_the_median_of_an_even_sample_is_the_midpoint(self):
        summary = distribution([1.0, 2.0, 3.0, 4.0], dimension="fit_score",
                               universe=CountUniverse.MATCH_ANALYSED)
        assert summary.median == 2.5

    def test_a_tiny_sample_is_labelled_rather_than_presented_as_a_distribution(self):
        summary = distribution([90.0, 91.0], dimension="fit_score",
                               universe=CountUniverse.MATCH_ANALYSED)
        assert summary.caveat
        assert "Too few" in summary.caveat

    def test_a_healthy_sample_carries_no_caveat(self):
        summary = distribution([float(v) for v in range(20)], dimension="fit_score",
                               universe=CountUniverse.MATCH_ANALYSED)
        assert summary.caveat == ""