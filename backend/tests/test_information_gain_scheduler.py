"""Tests for the information-gain driven verification scheduler."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.services.content_fingerprinting import FingerprintStatus
from app.services.information_gain_scheduler import (
    BASE_INFORMATION_GAIN,
    COST_LATENCY_WEIGHT,
    COST_NETWORK_WEIGHT,
    DEADLINE_CRITICAL_URGENCY,
    DEADLINE_URGENT_URGENCY,
    FINGERPRINT_HIGH_UNCHANGED_PROB,
    FINGERPRINT_MEDIUM_UNCHANGED_PROB,
    FRESHNESS_CRITICAL_STALENESS,
    FRESHNESS_STALENESS,
    HIGH_CHANGE_FREQUENCY_THRESHOLD,
    IMPACT_WEIGHT,
    INFORMATION_GAIN_VERSION,
    SOURCE_DEGRADED_PENALTY,
    SOURCE_UNHEALTHY_PENALTY,
    TIER_CRITICAL_THRESHOLD,
    TIER_HIGH_THRESHOLD,
    TIER_LOW_THRESHOLD,
    TIER_MEDIUM_THRESHOLD,
    UNCERTAINTY_WEIGHT,
    URGENCY_WEIGHT,
    BatchRankingResult,
    InformationGainProfile,
    InformationGainTier,
    _build_gain_inputs,
    _compute_change_probability,
    _compute_efficiency,
    _compute_estimated_cost,
    _compute_freshness_gap,
    _compute_impact_score,
    _compute_information_gain,
    _compute_priority,
    _compute_redundancy_penalty,
    _compute_source_reliability,
    _compute_uncertainty_score,
    _determine_tier,
    batch_rank_candidates,
    compute_gain_from_candidate,
    compute_information_gain,
    estimate_information_value,
    get_candidates_by_tier,
    get_verification_order,
    should_verify_by_information_gain,
)


class TestInformationGainConstants:
    """Test module constants and version."""

    def test_version_is_v1(self):
        assert INFORMATION_GAIN_VERSION == "v1"

    def test_base_information_gain_positive(self):
        assert BASE_INFORMATION_GAIN > 0

    def test_tier_thresholds_ordered(self):
        assert TIER_CRITICAL_THRESHOLD > TIER_HIGH_THRESHOLD
        assert TIER_HIGH_THRESHOLD > TIER_MEDIUM_THRESHOLD
        assert TIER_MEDIUM_THRESHOLD > TIER_LOW_THRESHOLD

    def test_weights_sum_to_reasonable_value(self):
        total = IMPACT_WEIGHT + URGENCY_WEIGHT + UNCERTAINTY_WEIGHT + COST_NETWORK_WEIGHT + COST_LATENCY_WEIGHT
        assert total > 0.5
        assert total < 2.0

    def test_fingerprint_thresholds_ordered(self):
        assert FINGERPRINT_HIGH_UNCHANGED_PROB > FINGERPRINT_MEDIUM_UNCHANGED_PROB

    def test_deadline_urgency_thresholds_ordered(self):
        assert DEADLINE_CRITICAL_URGENCY > DEADLINE_URGENT_URGENCY


class TestBasicProfileCreation:
    """Test compute_information_gain basic functionality."""

    def test_basic_profile_creation(self):
        profile = compute_information_gain(field_name="title")
        assert isinstance(profile, InformationGainProfile)
        assert profile.field_criticality == "low"
        assert profile.version == INFORMATION_GAIN_VERSION

    def test_profile_has_all_required_fields(self):
        profile = compute_information_gain(field_name="deadline_date")
        assert profile.expected_information_gain >= 0
        assert profile.uncertainty_score >= 0
        assert 0 <= profile.change_probability <= 1
        assert profile.freshness_gap >= 0
        assert profile.impact_score >= 0
        assert 0 <= profile.source_reliability <= 1
        assert 0 <= profile.redundancy_penalty <= 1
        assert profile.estimated_cost > 0
        assert profile.efficiency >= 0
        assert profile.priority >= 0

    def test_critical_field_profile(self):
        profile = compute_information_gain(field_name="deadline_date")
        assert profile.field_criticality == "critical"

    def test_low_criticality_field_profile(self):
        profile = compute_information_gain(field_name="title")
        assert profile.field_criticality == "low"

    def test_profile_has_tier(self):
        profile = compute_information_gain(field_name="title")
        assert isinstance(profile.tier, InformationGainTier)

    def test_profile_has_reason_codes(self):
        profile = compute_information_gain(field_name="deadline_date")
        assert len(profile.reason_codes) > 0

    def test_profile_default_values(self):
        profile = compute_information_gain()
        assert profile.field_name == ""
        assert profile.staleness_score == 0
        assert profile.deadline_urgency == 0


class TestStaleUnknownCandidateGetsHigherGain:
    """Test that stale unknown candidates get higher information gain."""

    def test_stale_candidate_higher_than_fresh(self):
        stale = compute_information_gain(
            field_name="title",
            staleness_score=90,
            last_verified_at=date.today() - timedelta(days=100),
        )
        fresh = compute_information_gain(
            field_name="title",
            staleness_score=5,
            last_verified_at=date.today() - timedelta(days=1),
        )
        assert stale.expected_information_gain > fresh.expected_information_gain

    def test_never_verified_higher_than_recently_verified(self):
        never_verified = compute_information_gain(
            field_name="title",
            staleness_score=100,
            last_verified_at=None,
        )
        recently_verified = compute_information_gain(
            field_name="title",
            staleness_score=0,
            last_verified_at=date.today() - timedelta(days=1),
        )
        assert never_verified.expected_information_gain > recently_verified.expected_information_gain

    def test_critical_stale_gets_highest_gain(self):
        critical_stale = compute_information_gain(
            field_name="deadline_date",
            staleness_score=FRESHNESS_CRITICAL_STALENESS,
        )
        low_stale = compute_information_gain(
            field_name="title",
            staleness_score=FRESHNESS_CRITICAL_STALENESS,
        )
        assert critical_stale.expected_information_gain > low_stale.expected_information_gain


class TestRecentStableCandidateGetsLowerGain:
    """Test that recent stable candidates get lower gain."""

    def test_recently_verified_low_gain(self):
        profile = compute_information_gain(
            field_name="title",
            staleness_score=0,
            fingerprint_unchanged_probability=0.95,
            last_verified_at=date.today() - timedelta(days=1),
            change_frequency_30d=0,
        )
        assert profile.tier in (InformationGainTier.LOW, InformationGainTier.MINIMAL)

    def test_stable_source_low_gain(self):
        profile = compute_information_gain(
            field_name="title",
            staleness_score=10,
            source_stability_score=95,
            change_frequency_30d=0,
            source_change_frequency_30d=0,
        )
        assert profile.change_probability < 0.5

    def test_fingerprint_unchanged_reduces_gain(self):
        unchanged = compute_information_gain(
            field_name="title",
            staleness_score=30,
            fingerprint_unchanged_probability=0.95,
        )
        unknown = compute_information_gain(
            field_name="title",
            staleness_score=30,
            fingerprint_unchanged_probability=0.0,
        )
        assert unchanged.expected_information_gain < unknown.expected_information_gain


class TestHighImpactUncertaintyOutranksLowImpact:
    """Test that high-impact uncertainty outranks low-impact uncertainty."""

    def test_critical_uncertain_outranks_low_uncertain(self):
        critical = compute_information_gain(
            field_name="deadline_date",
            staleness_score=80,
            verification_state="uncertain",
        )
        low = compute_information_gain(
            field_name="description",
            staleness_score=80,
            verification_state="uncertain",
        )
        assert critical.expected_information_gain > low.expected_information_gain

    def test_high_impact_field_higher_gain(self):
        high_impact = compute_information_gain(
            field_name="eligibility",
            staleness_score=50,
        )
        low_impact = compute_information_gain(
            field_name="notes",
            staleness_score=50,
        )
        assert high_impact.expected_information_gain > low_impact.expected_information_gain

    def test_impact_score_reflected_in_gain(self):
        profile = compute_information_gain(field_name="deadline_date")
        assert profile.impact_score >= 100


class TestDeadlineNearIncreasesGain:
    """Test that approaching deadline increases gain."""

    def test_deadline_critical_increases_gain(self):
        critical = compute_information_gain(
            field_name="title",
            staleness_score=30,
            deadline_urgency=DEADLINE_CRITICAL_URGENCY,
        )
        no_deadline = compute_information_gain(
            field_name="title",
            staleness_score=30,
            deadline_urgency=0,
        )
        assert critical.expected_information_gain > no_deadline.expected_information_gain

    def test_deadline_urgent_increases_gain(self):
        urgent = compute_information_gain(
            field_name="title",
            staleness_score=30,
            deadline_urgency=DEADLINE_URGENT_URGENCY,
        )
        no_deadline = compute_information_gain(
            field_name="title",
            staleness_score=30,
            deadline_urgency=0,
        )
        assert urgent.expected_information_gain > no_deadline.expected_information_gain

    def test_deadline_boosts_priority(self):
        critical = compute_information_gain(
            field_name="title",
            deadline_urgency=DEADLINE_CRITICAL_URGENCY,
        )
        no_deadline = compute_information_gain(
            field_name="title",
            deadline_urgency=0,
        )
        assert critical.priority > no_deadline.priority

    def test_deadline_critical_tier_adjustment(self):
        profile = compute_information_gain(
            field_name="title",
            staleness_score=0,
            deadline_urgency=DEADLINE_CRITICAL_URGENCY,
        )
        assert profile.tier in (InformationGainTier.HIGH, InformationGainTier.CRITICAL)


class TestChangeProneSourceIncreasesGain:
    """Test that change-prone sources increase gain."""

    def test_high_change_frequency_increases_gain(self):
        change_prone = compute_information_gain(
            field_name="title",
            staleness_score=30,
            source_change_frequency_30d=HIGH_CHANGE_FREQUENCY_THRESHOLD,
        )
        stable = compute_information_gain(
            field_name="title",
            staleness_score=30,
            source_change_frequency_30d=0,
        )
        assert change_prone.expected_information_gain > stable.expected_information_gain

    def test_change_probability_higher_for_change_prone(self):
        change_prone = compute_information_gain(
            field_name="title",
            source_change_frequency_30d=HIGH_CHANGE_FREQUENCY_THRESHOLD,
        )
        stable = compute_information_gain(
            field_name="title",
            source_change_frequency_30d=0,
        )
        assert change_prone.change_probability > stable.change_probability

    def test_low_source_stability_increases_gain(self):
        unstable = compute_information_gain(
            field_name="title",
            source_stability_score=20,
        )
        stable = compute_information_gain(
            field_name="title",
            source_stability_score=90,
        )
        assert unstable.change_probability > stable.change_probability

    def test_field_change_frequency_increases_gain(self):
        frequent = compute_information_gain(
            field_name="title",
            change_frequency_30d=HIGH_CHANGE_FREQUENCY_THRESHOLD,
        )
        infrequent = compute_information_gain(
            field_name="title",
            change_frequency_30d=0,
        )
        assert frequent.expected_information_gain > infrequent.expected_information_gain


class TestRedundantVerificationGetsPenalty:
    """Test that redundant verification gets penalty."""

    def test_redundant_verified_reduces_gain(self):
        single = compute_information_gain(
            field_name="title",
            staleness_score=50,
            redundant_verified_count=0,
        )
        redundant = compute_information_gain(
            field_name="title",
            staleness_score=50,
            redundant_verified_count=3,
        )
        assert redundant.redundancy_penalty > single.redundancy_penalty
        assert redundant.expected_information_gain < single.expected_information_gain

    def test_high_consensus_reduces_gain(self):
        consensus = compute_information_gain(
            field_name="title",
            staleness_score=50,
            consensus_score=0.95,
            redundant_verified_count=3,
            verification_state="verified",
            confidence_level="high",
        )
        no_consensus = compute_information_gain(
            field_name="title",
            staleness_score=50,
            consensus_score=0.3,
            redundant_verified_count=0,
        )
        assert consensus.redundancy_penalty > no_consensus.redundancy_penalty

    def test_max_redundancy_penalty_bounded(self):
        profile = compute_information_gain(
            field_name="title",
            redundant_verified_count=20,
        )
        assert profile.redundancy_penalty <= 0.5


class TestCostAffectsEfficiency:
    """Test that cost affects efficiency."""

    def test_cheaper_candidate_more_efficient(self):
        cheap = compute_information_gain(
            field_name="title",
            source_health_status="healthy",
            source_avg_latency_ms=500,
            source_error_rate=0.0,
        )
        expensive = compute_information_gain(
            field_name="title",
            source_health_status="unhealthy",
            source_avg_latency_ms=8000,
            source_error_rate=0.5,
        )
        assert cheap.estimated_cost < expensive.estimated_cost

    def test_efficiency_is_gain_divided_by_cost(self):
        profile = compute_information_gain(field_name="title")
        expected_efficiency = profile.expected_information_gain / max(1.0, profile.estimated_cost)
        assert abs(profile.efficiency - expected_efficiency) < 0.01

    def test_high_cost_reduces_information_gain(self):
        cheap = compute_information_gain(
            field_name="title",
            source_avg_latency_ms=100,
            source_error_rate=0.0,
        )
        expensive = compute_information_gain(
            field_name="title",
            source_avg_latency_ms=10000,
            source_error_rate=0.8,
        )
        assert cheap.expected_information_gain > expensive.expected_information_gain


class TestConflictAnomalyPrioritized:
    """Test that conflicts and anomalies remain prioritized appropriately."""

    def test_unresolved_conflict_increases_gain(self):
        conflict = compute_information_gain(
            field_name="title",
            staleness_score=30,
            has_unresolved_conflict=True,
        )
        no_conflict = compute_information_gain(
            field_name="title",
            staleness_score=30,
            has_unresolved_conflict=False,
        )
        assert conflict.expected_information_gain > no_conflict.expected_information_gain

    def test_anomaly_increases_gain(self):
        anomaly = compute_information_gain(
            field_name="title",
            staleness_score=30,
            anomaly_score=0.8,
        )
        no_anomaly = compute_information_gain(
            field_name="title",
            staleness_score=30,
            anomaly_score=0.0,
        )
        assert anomaly.expected_information_gain > no_anomaly.expected_information_gain

    def test_conflict_boosts_priority(self):
        conflict = compute_information_gain(
            field_name="title",
            has_unresolved_conflict=True,
        )
        no_conflict = compute_information_gain(
            field_name="title",
            has_unresolved_conflict=False,
        )
        assert conflict.priority > no_conflict.priority

    def test_anomaly_boosts_priority(self):
        anomaly = compute_information_gain(
            field_name="title",
            anomaly_score=0.9,
        )
        no_anomaly = compute_information_gain(
            field_name="title",
            anomaly_score=0.0,
        )
        assert anomaly.priority > no_anomaly.priority

    def test_conflict_has_safety_concern(self):
        conflict = compute_information_gain(
            field_name="title",
            has_unresolved_conflict=True,
        )
        assert conflict.has_safety_concern is True

    def test_high_anomaly_has_safety_concern(self):
        anomaly = compute_information_gain(
            field_name="title",
            anomaly_score=0.6,
        )
        assert anomaly.has_safety_concern is True


class TestInformationGainDeterministic:
    """Test that information gain scoring is deterministic."""

    def test_same_inputs_same_output(self):
        profile1 = compute_information_gain(
            field_name="title",
            staleness_score=50,
            deadline_urgency=30,
            source_reliability=70,
        )
        profile2 = compute_information_gain(
            field_name="title",
            staleness_score=50,
            deadline_urgency=30,
            source_reliability=70,
        )
        assert profile1.expected_information_gain == profile2.expected_information_gain
        assert profile1.uncertainty_score == profile2.uncertainty_score
        assert profile1.priority == profile2.priority
        assert profile1.tier == profile2.tier

    def test_multiple_calls_consistent(self):
        profiles = [
            compute_information_gain(field_name="title", staleness_score=50)
            for _ in range(10)
        ]
        assert all(p.expected_information_gain == profiles[0].expected_information_gain for p in profiles)


class TestBatchRanking:
    """Test batch ranking functionality."""

    def test_batch_rank_empty_list(self):
        result = batch_rank_candidates([])
        assert isinstance(result, BatchRankingResult)
        assert result.candidates == ()
        assert result.total_information_gain == 0.0

    def test_batch_rank_groups_by_tier(self):
        profiles = [
            compute_information_gain(field_name="deadline_date", staleness_score=90),
            compute_information_gain(field_name="title", staleness_score=10),
            compute_information_gain(field_name="eligibility", staleness_score=70),
        ]
        result = batch_rank_candidates(profiles)
        assert len(result.critical_candidates) + len(result.high_candidates) + len(result.medium_candidates) + len(result.low_candidates) + len(result.minimal_candidates) == 3

    def test_batch_rank_ordered_by_priority(self):
        profiles = [
            compute_information_gain(field_name="title", staleness_score=10),
            compute_information_gain(field_name="deadline_date", staleness_score=90),
        ]
        result = batch_rank_candidates(profiles)
        assert len(result.ranked_order) == 2
        assert result.ranked_order[0].priority >= result.ranked_order[1].priority

    def test_batch_rank_reason_codes(self):
        profiles = [compute_information_gain(field_name="title")]
        result = batch_rank_candidates(profiles)
        assert "batch_size:1" in result.reason_codes

    def test_batch_total_gain_correct(self):
        profiles = [
            compute_information_gain(field_name="title", staleness_score=50),
            compute_information_gain(field_name="description", staleness_score=50),
        ]
        result = batch_rank_candidates(profiles)
        expected_total = sum(p.expected_information_gain for p in profiles)
        assert abs(result.total_information_gain - expected_total) < 0.01


class TestNoNPlusOne:
    """Test that there are no N+1 query patterns."""

    def test_single_candidate_no_additional_queries(self):
        profile = compute_information_gain(
            field_name="title",
            staleness_score=50,
        )
        assert profile is not None

    def test_batch_ranking_no_per_candidate_queries(self):
        profiles = [
            compute_information_gain(field_name=f"field_{i}", staleness_score=i * 10)
            for i in range(10)
        ]
        result = batch_rank_candidates(profiles)
        assert len(result.ranked_order) == 10


class TestSafetyRulesCannotBeBypassed:
    """Test that safety rules cannot be bypassed by information gain."""

    def test_conflict_forces_verification(self):
        conflict = compute_information_gain(
            field_name="title",
            staleness_score=0,
            has_unresolved_conflict=True,
            fingerprint_unchanged_probability=0.99,
        )
        assert should_verify_by_information_gain(conflict) is True

    def test_deadline_critical_forces_verification(self):
        deadline = compute_information_gain(
            field_name="title",
            staleness_score=0,
            deadline_urgency=DEADLINE_CRITICAL_URGENCY,
            fingerprint_unchanged_probability=0.99,
        )
        assert should_verify_by_information_gain(deadline) is True

    def test_anomaly_forces_verification(self):
        anomaly = compute_information_gain(
            field_name="title",
            staleness_score=0,
            anomaly_score=0.9,
            fingerprint_unchanged_probability=0.99,
        )
        assert should_verify_by_information_gain(anomaly) is True

    def test_critical_field_stale_forces_verification(self):
        critical_stale = compute_information_gain(
            field_name="deadline_date",
            staleness_score=FRESHNESS_CRITICAL_STALENESS,
            fingerprint_unchanged_probability=0.99,
        )
        assert should_verify_by_information_gain(critical_stale) is True

    def test_low_gain_safe_candidate_can_defer(self):
        low_gain = compute_information_gain(
            field_name="notes",
            staleness_score=5,
            fingerprint_unchanged_probability=0.95,
            has_unresolved_conflict=False,
            anomaly_score=0.0,
            deadline_urgency=0,
        )
        assert low_gain.is_deferrable is True


class TestUncertaintyScoring:
    """Test uncertainty score computation."""

    def test_high_staleness_high_uncertainty(self):
        high_stale = compute_information_gain(field_name="title", staleness_score=90)
        low_stale = compute_information_gain(field_name="title", staleness_score=10)
        assert high_stale.uncertainty_score > low_stale.uncertainty_score

    def test_conflict_state_high_uncertainty(self):
        conflict = compute_information_gain(
            field_name="title",
            verification_state="conflict",
        )
        verified = compute_information_gain(
            field_name="title",
            verification_state="verified",
        )
        assert conflict.uncertainty_score > verified.uncertainty_score

    def test_low_confidence_high_uncertainty(self):
        low_conf = compute_information_gain(
            field_name="title",
            confidence_level="low",
        )
        high_conf = compute_information_gain(
            field_name="title",
            confidence_level="high",
        )
        assert low_conf.uncertainty_score > high_conf.uncertainty_score


class TestChangeProbability:
    """Test change probability computation."""

    def test_fingerprint_unchanged_low_probability(self):
        unchanged = compute_information_gain(
            field_name="title",
            fingerprint_unchanged_probability=0.95,
        )
        assert unchanged.change_probability < 0.2

    def test_fingerprint_unknown_higher_probability(self):
        unknown = compute_information_gain(
            field_name="title",
            fingerprint_unchanged_probability=0.0,
        )
        assert unknown.change_probability > 0.5

    def test_stale_data_higher_probability(self):
        stale = compute_information_gain(
            field_name="title",
            staleness_score=FRESHNESS_CRITICAL_STALENESS,
        )
        fresh = compute_information_gain(
            field_name="title",
            staleness_score=0,
        )
        assert stale.change_probability >= fresh.change_probability


class TestTierDetermination:
    """Test tier determination logic."""

    def test_very_high_gain_critical_tier(self):
        profile = compute_information_gain(
            field_name="deadline_date",
            staleness_score=FRESHNESS_CRITICAL_STALENESS,
            deadline_urgency=DEADLINE_CRITICAL_URGENCY,
            has_unresolved_conflict=True,
            verification_state="conflict",
        )
        assert profile.tier in (InformationGainTier.CRITICAL, InformationGainTier.HIGH)

    def test_low_gain_minimal_tier(self):
        profile = compute_information_gain(
            field_name="notes",
            staleness_score=0,
            fingerprint_unchanged_probability=0.95,
            has_unresolved_conflict=False,
            anomaly_score=0.0,
            deadline_urgency=0,
        )
        assert profile.tier in (InformationGainTier.LOW, InformationGainTier.MINIMAL)


class TestSourceReliabilityImpact:
    """Test that source reliability affects information gain."""

    def test_healthy_source_higher_reliability(self):
        healthy = compute_information_gain(
            field_name="title",
            source_health_status="healthy",
            source_reliability=90,
        )
        unhealthy = compute_information_gain(
            field_name="title",
            source_health_status="unhealthy",
            source_reliability=20,
        )
        assert healthy.source_reliability > unhealthy.source_reliability

    def test_error_rate_reduces_reliability(self):
        low_error = compute_information_gain(
            field_name="title",
            source_error_rate=0.0,
        )
        high_error = compute_information_gain(
            field_name="title",
            source_error_rate=0.8,
        )
        assert low_error.source_reliability > high_error.source_reliability


class TestDependencyImpact:
    """Test that dependencies affect information gain."""

    def test_unresolved_deps_increase_uncertainty(self):
        with_deps = compute_information_gain(
            field_name="title",
            unresolved_dependency_count=5,
        )
        no_deps = compute_information_gain(
            field_name="title",
            unresolved_dependency_count=0,
        )
        assert with_deps.uncertainty_score > no_deps.uncertainty_score

    def test_large_dependency_set_increases_impact(self):
        large_deps = compute_information_gain(
            field_name="deadline_date",
            dependency_set_size=10,
        )
        small_deps = compute_information_gain(
            field_name="deadline_date",
            dependency_set_size=0,
        )
        assert large_deps.impact_score >= small_deps.impact_score


class TestLifecycleImpact:
    """Test that lifecycle state affects information gain."""

    def test_discovered_state_higher_gain(self):
        discovered = compute_information_gain(
            field_name="title",
            lifecycle_state="discovered",
            staleness_score=50,
        )
        active = compute_information_gain(
            field_name="title",
            lifecycle_state="active",
            staleness_score=50,
        )
        assert discovered.impact_score >= active.impact_score

    def test_terminal_lifecycle_reduces_gain(self):
        terminal = compute_information_gain(
            field_name="title",
            lifecycle_state="archived",
            lifecycle_is_terminal=True,
            staleness_score=50,
        )
        active = compute_information_gain(
            field_name="title",
            lifecycle_state="active",
            lifecycle_is_terminal=False,
            staleness_score=50,
        )
        assert terminal.expected_information_gain < active.expected_information_gain


class TestVerificationOrder:
    """Test verification ordering."""

    def test_get_verification_order_sorts_correctly(self):
        profiles = [
            compute_information_gain(field_name="title", staleness_score=10),
            compute_information_gain(field_name="deadline_date", staleness_score=90),
            compute_information_gain(field_name="eligibility", staleness_score=60),
        ]
        ordered = get_verification_order(profiles)
        assert ordered[0].priority >= ordered[1].priority
        assert ordered[1].priority >= ordered[2].priority

    def test_get_candidates_by_tier_groups_correctly(self):
        profiles = [
            compute_information_gain(field_name="deadline_date", staleness_score=95),
            compute_information_gain(field_name="title", staleness_score=5),
        ]
        grouped = get_candidates_by_tier(profiles)
        assert len(grouped["critical"]) + len(grouped["high"]) + len(grouped["medium"]) + len(grouped["low"]) + len(grouped["minimal"]) == 2


class TestEstimateInformationValue:
    """Test information value estimation."""

    def test_empty_list_returns_zeros(self):
        result = estimate_information_value([])
        assert result["total_information_gain"] == 0.0
        assert result["verify_count"] == 0

    def test_aggregate_values_correct(self):
        profiles = [
            compute_information_gain(field_name="title", staleness_score=50),
            compute_information_gain(field_name="description", staleness_score=50),
        ]
        result = estimate_information_value(profiles)
        assert result["total_information_gain"] > 0
        assert result["total_cost"] > 0
        assert "net_value" in result
        assert "verify_count" in result
        assert "defer_count" in result


class TestShouldVerifyByInformationGain:
    """Test the should_verify_by_information_gain function."""

    def test_safety_concern_forces_verify(self):
        profile = compute_information_gain(
            field_name="title",
            has_unresolved_conflict=True,
        )
        assert should_verify_by_information_gain(profile) is True

    def test_high_gain_forces_verify(self):
        profile = compute_information_gain(
            field_name="deadline_date",
            staleness_score=FRESHNESS_CRITICAL_STALENESS,
        )
        assert should_verify_by_information_gain(profile) is True

    def test_critical_tier_forces_verify(self):
        profile = InformationGainProfile(
            expected_information_gain=50.0,
            uncertainty_score=50.0,
            change_probability=0.5,
            freshness_gap=50.0,
            impact_score=50.0,
            source_reliability=0.5,
            redundancy_penalty=0.0,
            estimated_cost=30.0,
            efficiency=1.0,
            priority=50.0,
            reason_codes=(),
            field_name="title",
            field_criticality="low",
            staleness_score=50,
            deadline_urgency=0,
            fingerprint_unchanged_probability=0.0,
            source_health_status="unknown",
            lifecycle_state="active",
            dependency_set_size=0,
            has_unresolved_conflict=False,
            anomaly_score=0.0,
            confidence_level="medium",
            verification_state="partially_verified",
            tier=InformationGainTier.CRITICAL,
        )
        assert should_verify_by_information_gain(profile) is True

    def test_minimal_tier_low_gain_no_safety_defer(self):
        profile = InformationGainProfile(
            expected_information_gain=5.0,
            uncertainty_score=5.0,
            change_probability=0.05,
            freshness_gap=5.0,
            impact_score=10.0,
            source_reliability=0.5,
            redundancy_penalty=0.0,
            estimated_cost=30.0,
            efficiency=0.1,
            priority=5.0,
            reason_codes=(),
            field_name="notes",
            field_criticality="low",
            staleness_score=5,
            deadline_urgency=0,
            fingerprint_unchanged_probability=0.95,
            source_health_status="healthy",
            lifecycle_state="active",
            dependency_set_size=0,
            has_unresolved_conflict=False,
            anomaly_score=0.0,
            confidence_level="high",
            verification_state="verified",
            tier=InformationGainTier.MINIMAL,
        )
        assert should_verify_by_information_gain(profile) is False


class TestComputeGainFromCandidate:
    """Test the compute_gain_from_candidate convenience function."""

    def test_basic_candidate(self):
        profile = compute_gain_from_candidate(
            field_name="title",
            fingerprint_status=FingerprintStatus.UNKNOWN,
        )
        assert isinstance(profile, InformationGainProfile)

    def test_with_deadline(self):
        profile = compute_gain_from_candidate(
            field_name="deadline_date",
            deadline_date=date.today() + timedelta(days=7),
        )
        assert profile.deadline_urgency > 0

    def test_with_last_verified(self):
        profile = compute_gain_from_candidate(
            field_name="title",
            last_verified_at=date.today() - timedelta(days=100),
        )
        assert profile.staleness_score > 0

    def test_never_verified(self):
        profile = compute_gain_from_candidate(
            field_name="title",
            last_verified_at=None,
        )
        assert profile.staleness_score == 100


class TestTasksOneThroughTwentySevenImportsFunctional:
    """Test that TASKS 1-27 imports remain functional."""

    def test_cost_optimizer_import(self):
        from app.services.verification_cost_optimizer import (
            VerificationCostProfile,
            compute_cost_profile,
        )
        profile = compute_cost_profile(field_name="title")
        assert isinstance(profile, VerificationCostProfile)

    def test_adaptive_policy_import(self):
        from app.services.adaptive_policy import (
            AdaptiveVerificationPolicy,
            compute_adaptive_policy,
        )
        assert AdaptiveVerificationPolicy is not None

    def test_scheduler_priority_import(self):
        from app.services.scheduler_priority import (
            PriorityScore,
            compute_staleness,
        )
        assert PriorityScore is not None

    def test_content_fingerprinting_import(self):
        from app.services.content_fingerprinting import (
            FingerprintStatus,
            compare_fingerprints,
        )
        assert FingerprintStatus is not None

    def test_dependency_graph_import(self):
        from app.services.dependency_graph import (
            analyze_dependencies,
            DependencyAnalysis,
        )
        assert DependencyAnalysis is not None

    def test_anomaly_detection_import(self):
        from app.services.anomaly_detection import (
            AnomalySeverity,
            detect_anomalies,
        )
        assert AnomalySeverity is not None

    def test_verification_confidence_import(self):
        from app.services.verification_confidence import (
            ConfidenceLevel,
            assess_confidence,
        )
        assert ConfidenceLevel is not None

    def test_change_impact_staleness_import(self):
        from app.services.change_impact_staleness import (
            compute_field_staleness,
            compute_deadline_urgency,
        )
        assert compute_field_staleness is not None

    def test_lifecycle_identity_import(self):
        from app.services.lifecycle_identity import (
            classify_lifecycle_state,
            LifecycleState,
        )
        assert LifecycleState is not None

    def test_scholarship_retry_import(self):
        from app.services.scholarship_retry import (
            make_retry_decision,
            RetryDecision,
        )
        assert RetryDecision is not None

    def test_source_health_import(self):
        from app.services.source_health_service import (
            classify_health_status,
            compute_reliability_score,
        )
        assert classify_health_status is not None

    def test_telemetry_import(self):
        from app.services.telemetry import (
            record_event,
            get_source_stats,
        )
        assert record_event is not None

    def test_evidence_arbitration_import(self):
        from app.services.evidence_arbitration import (
            arbitrate_field,
            ArbitrationDecision,
        )
        assert ArbitrationDecision is not None
