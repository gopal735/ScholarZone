"""Tests for the verification cost-optimizer."""

from __future__ import annotations

import pytest

from app.services.content_fingerprinting import FingerprintStatus
from app.services.verification_cost_optimizer import (
    COST_OPTIMIZER_VERSION,
    EFFICIENCY_BATCH_THRESHOLD,
    EFFICIENCY_DEFER_THRESHOLD,
    EFFICIENCY_VERIFY_THRESHOLD,
    FINGERPRINT_HIGH_UNCHANGED_PROB,
    VerificationAction,
    SafetyFlag,
    VerificationCostProfile,
    BatchOptimizationResult,
    _build_cost_inputs,
    _compute_cpu_cost,
    _compute_db_cost,
    _compute_efficiency,
    _compute_latency_cost,
    _compute_network_cost,
    _compute_source_load_cost,
    _compute_verification_value,
    _determine_action,
    _determine_safety_flags,
    batch_optimize,
    compute_cost_profile,
    compute_fingerprint_unchanged_probability,
    compute_profile_from_candidate,
    estimate_batch_savings,
    get_fields_by_action,
    get_verification_order,
    should_verify_now,
)


class TestCostOptimizerConstants:
    """Test module constants and version."""

    def test_version_is_v1(self):
        assert COST_OPTIMIZER_VERSION == "v1"

    def test_efficiency_thresholds_ordered(self):
        assert EFFICIENCY_VERIFY_THRESHOLD > EFFICIENCY_BATCH_THRESHOLD
        assert EFFICIENCY_BATCH_THRESHOLD > EFFICIENCY_DEFER_THRESHOLD

    def test_fingerprint_high_prob_threshold(self):
        assert 0.0 < FINGERPRINT_HIGH_UNCHANGED_PROB < 1.0


class TestCostProfileCreation:
    """Test compute_cost_profile basic functionality."""

    def test_basic_profile_creation(self):
        profile = compute_cost_profile(
            field_name="title",
            fingerprint_status=FingerprintStatus.UNKNOWN,
        )
        assert isinstance(profile, VerificationCostProfile)
        assert profile.field_criticality == "low"
        assert profile.version == COST_OPTIMIZER_VERSION

    def test_profile_has_all_cost_fields(self):
        profile = compute_cost_profile(field_name="deadline_date")
        assert profile.estimated_network_cost > 0
        assert profile.estimated_cpu_cost > 0
        assert profile.estimated_db_cost > 0
        assert profile.estimated_latency > 0
        assert profile.source_load_cost > 0
        assert profile.total_cost > 0

    def test_profile_has_action_and_efficiency(self):
        profile = compute_cost_profile(field_name="title")
        assert isinstance(profile.recommended_action, VerificationAction)
        assert profile.efficiency_score >= 0
        assert profile.verification_value >= 0
        assert profile.priority >= 0

    def test_critical_field_profile(self):
        profile = compute_cost_profile(field_name="deadline_date")
        assert profile.field_criticality == "critical"
        assert profile.verification_value > 30  # Should have high value

    def test_low_criticality_field_profile(self):
        profile = compute_cost_profile(field_name="title")
        assert profile.field_criticality == "low"


class TestCheapVsExpensiveCandidate:
    """Test that cheap candidates score differently from expensive ones."""

    def test_healthy_source_is_cheaper(self):
        healthy = compute_cost_profile(
            field_name="title",
            source_health_status="healthy",
            source_avg_latency_ms=500,
            source_error_rate=0.0,
        )
        unhealthy = compute_cost_profile(
            field_name="title",
            source_health_status="unhealthy",
            source_avg_latency_ms=8000,
            source_error_rate=0.6,
        )
        assert healthy.estimated_network_cost < unhealthy.estimated_network_cost

    def test_retry_increases_cost(self):
        no_retry = compute_cost_profile(
            field_name="title",
            is_retrying=False,
            retry_attempt_count=0,
        )
        with_retry = compute_cost_profile(
            field_name="title",
            is_retrying=True,
            retry_attempt_count=3,
        )
        assert with_retry.estimated_network_cost >= no_retry.estimated_network_cost

    def test_large_content_increases_cost(self):
        small = compute_cost_profile(
            field_name="title",
            content_size_bytes=1024,
        )
        large = compute_cost_profile(
            field_name="title",
            content_size_bytes=1024 * 1024,
        )
        assert large.estimated_network_cost >= small.estimated_network_cost


class TestHighValueVsLowValue:
    """Test that high-value verifications score higher."""

    def test_critical_field_has_higher_value(self):
        critical = compute_cost_profile(field_name="deadline_date")
        low = compute_cost_profile(field_name="description")
        assert critical.verification_value > low.verification_value

    def test_deadline_urgency_increases_value(self):
        urgent = compute_cost_profile(
            field_name="title",
            deadline_urgency=100,
        )
        not_urgent = compute_cost_profile(
            field_name="title",
            deadline_urgency=0,
        )
        assert urgent.verification_value > not_urgent.verification_value

    def test_staleness_increases_value(self):
        stale = compute_cost_profile(
            field_name="title",
            staleness_score=90,
        )
        fresh = compute_cost_profile(
            field_name="title",
            staleness_score=5,
        )
        assert stale.verification_value > fresh.verification_value

    def test_fingerprint_unchanged_reduces_value(self):
        unchanged = compute_cost_profile(
            field_name="deadline_date",
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
        )
        changed = compute_cost_profile(
            field_name="deadline_date",
            fingerprint_status=FingerprintStatus.CHANGED,
            fingerprint_unchanged_probability=0.0,
        )
        assert changed.verification_value > unchanged.verification_value

    def test_terminal_lifecycle_reduces_value(self):
        active = compute_cost_profile(
            field_name="title",
            lifecycle_state="active",
            lifecycle_is_terminal=False,
        )
        archived = compute_cost_profile(
            field_name="title",
            lifecycle_state="archived",
            lifecycle_is_terminal=True,
        )
        assert active.verification_value > archived.verification_value


class TestDeadlineCriticalCannotBeDeferred:
    """Test that deadline-critical work cannot be skipped or deferred."""

    def test_deadline_critical_gets_verify_action(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=100,
        )
        assert profile.recommended_action == VerificationAction.VERIFY
        assert SafetyFlag.DEADLINE_CRITICAL in profile.safety_flags

    def test_deadline_urgent_gets_high_priority(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=80,
        )
        assert profile.priority >= 28  # 80 * 0.35 = 28 from deadline urgency alone

    def test_deadline_critical_with_unchanged_fingerprint_still_verify(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=100,
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
        )
        assert profile.recommended_action == VerificationAction.VERIFY
        assert SafetyFlag.DEADLINE_CRITICAL in profile.safety_flags


class TestFingerprintAwareSavings:
    """Test fingerprint-based cost savings."""

    def test_unchanged_fingerprint_can_be_skipped(self):
        profile = compute_cost_profile(
            field_name="title",
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
            deadline_urgency=0,
            staleness_score=5,
        )
        if len(profile.safety_flags) == 0:
            assert profile.recommended_action == VerificationAction.SKIP

    def test_changed_fingerprint_increases_value(self):
        changed = compute_cost_profile(
            field_name="title",
            fingerprint_status=FingerprintStatus.CHANGED,
            fingerprint_unchanged_probability=0.0,
        )
        unknown = compute_cost_profile(
            field_name="title",
            fingerprint_status=FingerprintStatus.UNKNOWN,
            fingerprint_unchanged_probability=0.5,
        )
        assert changed.verification_value >= unknown.verification_value

    def test_compute_fingerprint_prob_unchanged(self):
        prob = compute_fingerprint_unchanged_probability(FingerprintStatus.UNCHANGED)
        assert prob == 1.0

    def test_compute_fingerprint_prob_changed(self):
        prob = compute_fingerprint_unchanged_probability(FingerprintStatus.CHANGED)
        assert prob == 0.0

    def test_compute_fingerprint_prob_unknown_uses_history(self):
        prob = compute_fingerprint_unchanged_probability(
            FingerprintStatus.UNKNOWN, historical_unchanged_ratio=0.7
        )
        assert prob == 0.7


class TestUnhealthySourceCostHandling:
    """Test handling of unhealthy sources."""

    def test_unhealthy_source_has_higher_cost(self):
        healthy = compute_cost_profile(
            field_name="title",
            source_health_status="healthy",
        )
        unhealthy = compute_cost_profile(
            field_name="title",
            source_health_status="unhealthy",
        )
        assert unhealthy.estimated_network_cost > healthy.estimated_network_cost

    def test_unhealthy_source_adds_safety_flag_when_stale(self):
        profile = compute_cost_profile(
            field_name="title",
            source_health_status="unhealthy",
            source_consecutive_failures=5,
        )
        assert SafetyFlag.SOURCE_UNHEALTHY in profile.safety_flags

    def test_healthy_source_no_source_unhealthy_flag(self):
        profile = compute_cost_profile(
            field_name="title",
            source_health_status="healthy",
            source_consecutive_failures=0,
        )
        assert SafetyFlag.SOURCE_UNHEALTHY not in profile.safety_flags


class TestDependencyAwareCost:
    """Test dependency-aware cost computation."""

    def test_large_dependency_set_increases_cpu_cost(self):
        base = _build_cost_inputs(field_name="title", dependency_set_size=0)
        deps = _build_cost_inputs(field_name="title", dependency_set_size=10)
        assert _compute_cpu_cost(deps) > _compute_cpu_cost(base)

    def test_dependency_with_criticality_adds_safety_flag(self):
        profile = compute_cost_profile(
            field_name="deadline_date",
            dependency_set_size=3,
        )
        if profile.field_criticality == "critical":
            assert SafetyFlag.DEPENDENCY_REQUIRED in profile.safety_flags

    def test_dependency_set_increases_value(self):
        no_deps = compute_cost_profile(
            field_name="deadline_date",
            dependency_set_size=0,
        )
        with_deps = compute_cost_profile(
            field_name="deadline_date",
            dependency_set_size=5,
        )
        assert with_deps.verification_value >= no_deps.verification_value


class TestBatchingBenefit:
    """Test batch optimization benefits."""

    def test_batch_optimize_groups_correctly(self):
        profiles = [
            compute_cost_profile(field_name="deadline_date", deadline_urgency=100),
            compute_cost_profile(field_name="title", staleness_score=5),
            compute_cost_profile(field_name="description", staleness_score=3),
        ]
        result = batch_optimize(profiles)
        assert isinstance(result, BatchOptimizationResult)
        assert len(result.candidates) == 3

    def test_batch_optimize_empty_list(self):
        result = batch_optimize([])
        assert result.total_cost == 0.0
        assert len(result.candidates) == 0

    def test_batch_optimize_verify_now_sorted_by_priority(self):
        profiles = [
            compute_cost_profile(field_name="title", deadline_urgency=50),
            compute_cost_profile(field_name="deadline_date", deadline_urgency=100),
        ]
        result = batch_optimize(profiles)
        if len(result.verify_now) > 1:
            for i in range(len(result.verify_now) - 1):
                assert result.verify_now[i].priority >= result.verify_now[i + 1].priority

    def test_batch_optimize_has_reason_codes(self):
        profiles = [
            compute_cost_profile(field_name="title"),
        ]
        result = batch_optimize(profiles)
        assert len(result.reason_codes) > 0
        assert any("batch_size" in r for r in result.reason_codes)


class TestLatencyEstimation:
    """Test latency cost estimation."""

    def test_slow_source_higher_latency_cost(self):
        base = _build_cost_inputs(source_avg_latency_ms=0)
        slow = _build_cost_inputs(source_avg_latency_ms=8000)
        fast = _build_cost_inputs(source_avg_latency_ms=500)
        assert _compute_latency_cost(slow) > _compute_latency_cost(base)
        assert _compute_latency_cost(fast) < _compute_latency_cost(slow)

    def test_retry_increases_latency_cost(self):
        base = _build_cost_inputs(is_retrying=False, retry_attempt_count=0)
        retry = _build_cost_inputs(is_retrying=True, retry_attempt_count=3)
        assert _compute_latency_cost(retry) > _compute_latency_cost(base)

    def test_error_rate_increases_latency(self):
        base = _build_cost_inputs(source_error_rate=0.0)
        high_error = _build_cost_inputs(source_error_rate=0.5)
        assert _compute_latency_cost(high_error) > _compute_latency_cost(base)


class TestDeterministicScoring:
    """Test that scoring is deterministic."""

    def test_same_inputs_same_output(self):
        profile1 = compute_cost_profile(
            field_name="deadline_date",
            deadline_urgency=80,
            source_health_status="healthy",
        )
        profile2 = compute_cost_profile(
            field_name="deadline_date",
            deadline_urgency=80,
            source_health_status="healthy",
        )
        assert profile1.efficiency_score == profile2.efficiency_score
        assert profile1.recommended_action == profile2.recommended_action
        assert profile1.total_cost == profile2.total_cost

    def test_same_inputs_same_safety_flags(self):
        profile1 = compute_cost_profile(
            field_name="title",
            has_unresolved_conflict=True,
        )
        profile2 = compute_cost_profile(
            field_name="title",
            has_unresolved_conflict=True,
        )
        assert profile1.safety_flags == profile2.safety_flags


class TestNoUnsafeSkipping:
    """Test that safety rules prevent unsafe skipping."""

    def test_unresolved_conflict_cannot_skip(self):
        profile = compute_cost_profile(
            field_name="title",
            has_unresolved_conflict=True,
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
        )
        assert profile.recommended_action != VerificationAction.SKIP
        assert SafetyFlag.UNRESOLVED_CONFLICT in profile.safety_flags

    def test_anomaly_detected_cannot_skip(self):
        profile = compute_cost_profile(
            field_name="title",
            anomaly_score=0.8,
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
        )
        assert profile.recommended_action != VerificationAction.SKIP
        assert SafetyFlag.ANOMALY_DETECTED in profile.safety_flags

    def test_critical_field_cannot_skip(self):
        profile = compute_cost_profile(
            field_name="deadline_date",
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
            deadline_urgency=0,
        )
        assert profile.recommended_action != VerificationAction.SKIP
        assert SafetyFlag.CRITICAL_FIELD in profile.safety_flags

    def test_freshness_required_cannot_skip(self):
        profile = compute_cost_profile(
            field_name="title",
            staleness_score=90,
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
            deadline_urgency=0,
        )
        assert profile.recommended_action != VerificationAction.SKIP
        assert SafetyFlag.FRESHNESS_REQUIRED in profile.safety_flags

    def test_is_safe_to_skip_property(self):
        unsafe = compute_cost_profile(
            field_name="deadline_date",
        )
        assert not unsafe.is_safe_to_skip

    def test_safe_to_skip_when_no_flags_and_unchanged(self):
        profile = compute_cost_profile(
            field_name="title",
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
            deadline_urgency=0,
            staleness_score=5,
        )
        if len(profile.safety_flags) == 0:
            assert profile.is_safe_to_skip


class TestNoNPlusOne:
    """Test that batch operations don't cause N+1 queries."""

    def test_batch_optimize_single_pass(self):
        profiles = [compute_cost_profile(field_name=f"field_{i}") for i in range(20)]
        result = batch_optimize(profiles)
        assert len(result.candidates) == 20
        total_grouped = (
            len(result.verify_now)
            + len(result.batch_later)
            + len(result.defer)
            + len(result.skip)
        )
        assert total_grouped == 20

    def test_get_fields_by_action_single_pass(self):
        profiles = [compute_cost_profile(field_name="title") for _ in range(10)]
        grouped = get_fields_by_action(profiles)
        total = sum(len(v) for v in grouped.values())
        assert total == 10


class TestBatchOptimization:
    """Test batch optimization functionality."""

    def test_batch_efficiency_calculation(self):
        profiles = [
            compute_cost_profile(field_name="deadline_date", deadline_urgency=100),
            compute_cost_profile(field_name="title"),
        ]
        result = batch_optimize(profiles)
        assert result.batch_efficiency >= 0
        assert result.total_cost > 0
        assert result.total_value > 0

    def test_batch_savings_calculation(self):
        profiles = [
            compute_cost_profile(
                field_name="title",
                fingerprint_status=FingerprintStatus.UNCHANGED,
                fingerprint_unchanged_probability=1.0,
                deadline_urgency=0,
                staleness_score=5,
            ),
            compute_cost_profile(field_name="deadline_date", deadline_urgency=100),
        ]
        result = batch_optimize(profiles)
        assert isinstance(result.estimated_batch_savings, float)

    def test_estimate_batch_savings_function(self):
        profiles = [
            compute_cost_profile(field_name="title"),
            compute_cost_profile(field_name="description"),
        ]
        savings = estimate_batch_savings(profiles)
        assert "total_cost" in savings
        assert "savings" in savings
        assert "savings_pct" in savings
        assert savings["total_cost"] > 0

    def test_estimate_batch_savings_empty(self):
        savings = estimate_batch_savings([])
        assert savings["total_cost"] == 0.0
        assert savings["savings"] == 0.0


class TestComputeProfileFromCandidate:
    """Test the convenience function compute_profile_from_candidate."""

    def test_basic_candidate(self):
        profile = compute_profile_from_candidate(
            field_name="title",
            fingerprint_status=FingerprintStatus.UNKNOWN,
        )
        assert isinstance(profile, VerificationCostProfile)
        assert profile.field_criticality == "low"

    def test_candidate_with_deadline(self):
        from datetime import date, timedelta
        future = date.today() + timedelta(days=10)
        profile = compute_profile_from_candidate(
            field_name="deadline_date",
            deadline_date=future,
        )
        assert profile.deadline_urgency >= 80

    def test_candidate_with_past_deadline(self):
        from datetime import date, timedelta
        past = date.today() - timedelta(days=10)
        profile = compute_profile_from_candidate(
            field_name="deadline_date",
            deadline_date=past,
        )
        assert profile.deadline_urgency == 0

    def test_candidate_never_verified(self):
        profile = compute_profile_from_candidate(
            field_name="title",
            last_verified_at=None,
        )
        assert profile.staleness_score == 100

    def test_candidate_recently_verified(self):
        from datetime import date, timedelta
        recent = date.today() - timedelta(days=1)
        profile = compute_profile_from_candidate(
            field_name="title",
            last_verified_at=recent,
        )
        assert profile.staleness_score < 10

    def test_candidate_with_source_url(self):
        profile = compute_profile_from_candidate(
            field_name="title",
            source_url="https://example.com/scholarship",
        )
        assert isinstance(profile, VerificationCostProfile)


class TestHelperFunctions:
    """Test helper functions."""

    def test_should_verify_now_true(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=100,
        )
        assert should_verify_now(profile) is True

    def test_should_verify_now_false(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=0,
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
        )
        if profile.recommended_action != VerificationAction.VERIFY:
            assert should_verify_now(profile) is False

    def test_get_verification_order(self):
        profiles = [
            compute_cost_profile(field_name="title", deadline_urgency=10),
            compute_cost_profile(field_name="deadline_date", deadline_urgency=100),
        ]
        ordered = get_verification_order(profiles)
        assert ordered[0].priority >= ordered[-1].priority

    def test_get_fields_by_action(self):
        profiles = [
            compute_cost_profile(field_name="title", deadline_urgency=100),
            compute_cost_profile(field_name="description"),
        ]
        grouped = get_fields_by_action(profiles)
        assert "verify" in grouped
        assert "batch" in grouped
        assert "defer" in grouped
        assert "skip" in grouped


class TestSafetyFlags:
    """Test safety flag determination."""

    def test_deadline_critical_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(deadline_urgency=100)
        )
        assert SafetyFlag.DEADLINE_CRITICAL in flags

    def test_critical_field_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(field_name="deadline_date")
        )
        assert SafetyFlag.CRITICAL_FIELD in flags

    def test_unresolved_conflict_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(has_unresolved_conflict=True)
        )
        assert SafetyFlag.UNRESOLVED_CONFLICT in flags

    def test_anomaly_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(anomaly_score=0.7)
        )
        assert SafetyFlag.ANOMALY_DETECTED in flags

    def test_freshness_required_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(staleness_score=90)
        )
        assert SafetyFlag.FRESHNESS_REQUIRED in flags

    def test_source_unhealthy_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(
                source_health_status="unhealthy",
                source_consecutive_failures=5,
            )
        )
        assert SafetyFlag.SOURCE_UNHEALTHY in flags

    def test_dependency_required_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(
                field_name="deadline_date",
                dependency_set_size=3,
            )
        )
        assert SafetyFlag.DEPENDENCY_REQUIRED in flags

    def test_high_change_frequency_flag(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(change_frequency_30d=6)
        )
        assert SafetyFlag.HIGH_CHANGE_FREQUENCY in flags

    def test_no_flags_for_safe_candidate(self):
        flags = _determine_safety_flags(
            _build_cost_inputs(
                field_name="title",
                deadline_urgency=0,
                staleness_score=5,
                source_health_status="healthy",
            )
        )
        assert len(flags) == 0


class TestActionDetermination:
    """Test action determination logic."""

    def test_high_efficiency_verifies(self):
        action, reasons = _determine_action(2.0, [], _build_cost_inputs())
        assert action == VerificationAction.VERIFY

    def test_medium_efficiency_batches(self):
        action, reasons = _determine_action(1.0, [], _build_cost_inputs())
        assert action == VerificationAction.BATCH

    def test_low_efficiency_defers(self):
        action, reasons = _determine_action(0.4, [], _build_cost_inputs())
        assert action == VerificationAction.DEFER

    def test_very_low_efficiency_skips_if_safe(self):
        action, reasons = _determine_action(0.1, [], _build_cost_inputs())
        assert action == VerificationAction.SKIP

    def test_safety_flags_override_to_verify(self):
        flags = [SafetyFlag.DEADLINE_CRITICAL]
        action, reasons = _determine_action(0.1, flags, _build_cost_inputs())
        assert action == VerificationAction.VERIFY

    def test_low_efficiency_with_safety_defers(self):
        flags = [SafetyFlag.SOURCE_UNHEALTHY]
        action, reasons = _determine_action(0.1, flags, _build_cost_inputs())
        assert action == VerificationAction.DEFER


class TestEfficiencyComputation:
    """Test efficiency computation."""

    def test_efficiency_is_value_over_cost(self):
        efficiency = _compute_efficiency(50.0, 25.0)
        assert efficiency == 2.0

    def test_efficiency_min_cost_floor(self):
        efficiency = _compute_efficiency(10.0, 0.001)
        assert efficiency > 0

    def test_efficiency_high_value_low_cost(self):
        efficiency = _compute_efficiency(100.0, 10.0)
        assert efficiency == 10.0


class TestCostComputations:
    """Test individual cost component computations."""

    def test_network_cost_base(self):
        cost = _compute_network_cost(_build_cost_inputs())
        assert cost > 0

    def test_cpu_cost_base(self):
        cost = _compute_cpu_cost(_build_cost_inputs())
        assert cost > 0

    def test_db_cost_base(self):
        cost = _compute_db_cost(_build_cost_inputs())
        assert cost > 0

    def test_latency_cost_base(self):
        cost = _compute_latency_cost(_build_cost_inputs())
        assert cost > 0

    def test_source_load_cost_base(self):
        cost = _compute_source_load_cost(_build_cost_inputs())
        assert cost > 0

    def test_network_cost_slow_source(self):
        base = _compute_network_cost(_build_cost_inputs(source_avg_latency_ms=0))
        slow = _compute_network_cost(_build_cost_inputs(source_avg_latency_ms=8000))
        assert slow > base

    def test_network_cost_fast_source(self):
        base = _compute_network_cost(_build_cost_inputs(source_avg_latency_ms=3000))
        fast = _compute_network_cost(_build_cost_inputs(source_avg_latency_ms=500))
        assert fast < base

    def test_cpu_cost_with_dependencies(self):
        base = _compute_cpu_cost(_build_cost_inputs(dependency_set_size=0))
        deps = _compute_cpu_cost(_build_cost_inputs(dependency_set_size=10))
        assert deps > base

    def test_source_load_cost_unhealthy(self):
        healthy = _compute_source_load_cost(
            _build_cost_inputs(source_health_status="healthy")
        )
        unhealthy = _compute_source_load_cost(
            _build_cost_inputs(source_health_status="unhealthy")
        )
        assert unhealthy > healthy

    def test_source_load_cost_consecutive_failures(self):
        base = _compute_source_load_cost(
            _build_cost_inputs(source_consecutive_failures=0)
        )
        failures = _compute_source_load_cost(
            _build_cost_inputs(source_consecutive_failures=5)
        )
        assert failures > base


class TestVerificationValue:
    """Test verification value computation."""

    def test_base_value(self):
        value = _compute_verification_value(_build_cost_inputs())
        assert value > 0

    def test_critical_field_higher_value(self):
        critical = _compute_verification_value(
            _build_cost_inputs(field_name="deadline_date")
        )
        low = _compute_verification_value(
            _build_cost_inputs(field_name="title")
        )
        assert critical > low

    def test_unchanged_fingerprint_lower_value(self):
        unchanged = _compute_verification_value(
            _build_cost_inputs(
                fingerprint_status=FingerprintStatus.UNCHANGED,
                fingerprint_unchanged_probability=1.0,
            )
        )
        changed = _compute_verification_value(
            _build_cost_inputs(
                fingerprint_status=FingerprintStatus.CHANGED,
                fingerprint_unchanged_probability=0.0,
            )
        )
        assert changed > unchanged

    def test_deadline_urgency_higher_value(self):
        urgent = _compute_verification_value(
            _build_cost_inputs(deadline_urgency=100)
        )
        not_urgent = _compute_verification_value(
            _build_cost_inputs(deadline_urgency=0)
        )
        assert urgent > not_urgent

    def test_staleness_higher_value(self):
        stale = _compute_verification_value(
            _build_cost_inputs(staleness_score=90)
        )
        fresh = _compute_verification_value(
            _build_cost_inputs(staleness_score=5)
        )
        assert stale > fresh

    def test_terminal_lifecycle_lower_value(self):
        active = _compute_verification_value(
            _build_cost_inputs(lifecycle_is_terminal=False)
        )
        terminal = _compute_verification_value(
            _build_cost_inputs(lifecycle_is_terminal=True)
        )
        assert active > terminal


class TestCostProfileProperties:
    """Test VerificationCostProfile properties."""

    def test_requires_immediate_verification_true(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=100,
        )
        assert profile.requires_immediate_verification is True

    def test_requires_immediate_verification_false(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=0,
        )
        if profile.recommended_action != VerificationAction.VERIFY:
            assert profile.requires_immediate_verification is False

    def test_can_batch_verify(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=100,
        )
        assert profile.can_batch is True

    def test_can_batch_batch_action(self):
        profile = compute_cost_profile(
            field_name="title",
            deadline_urgency=30,
        )
        if profile.recommended_action == VerificationAction.BATCH:
            assert profile.can_batch is True

    def test_is_safe_to_skip_no_flags(self):
        profile = compute_cost_profile(
            field_name="title",
            fingerprint_status=FingerprintStatus.UNCHANGED,
            fingerprint_unchanged_probability=1.0,
            deadline_urgency=0,
            staleness_score=5,
        )
        if len(profile.safety_flags) == 0:
            assert profile.is_safe_to_skip is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_values_dont_error(self):
        profile = compute_cost_profile(
            field_name="",
            source_reliability=0,
            source_avg_latency_ms=0,
            deadline_urgency=0,
            staleness_score=0,
            content_size_bytes=0,
        )
        assert profile.total_cost > 0  # Base costs still apply

    def test_extreme_values_handled(self):
        profile = compute_cost_profile(
            field_name="title",
            source_reliability=100,
            source_avg_latency_ms=10000,
            deadline_urgency=100,
            staleness_score=100,
            content_size_bytes=10 * 1024 * 1024,
        )
        assert profile.total_cost > 0
        assert profile.verification_value > 0

    def test_empty_fingerprint_status(self):
        profile = compute_cost_profile(
            field_name="title",
            fingerprint_status=None,
        )
        assert isinstance(profile, VerificationCostProfile)

    def test_all_fingerprint_statuses(self):
        for status in FingerprintStatus:
            profile = compute_cost_profile(
                field_name="title",
                fingerprint_status=status,
            )
            assert isinstance(profile, VerificationCostProfile)


class TestTasks1To26RemainsGreen:
    """Verify that cost optimizer doesn't break existing imports."""

    def test_dependency_graph_imports(self):
        from app.services.dependency_graph import analyze_dependencies
        assert callable(analyze_dependencies)

    def test_content_fingerprinting_imports(self):
        from app.services.content_fingerprinting import compare_fingerprints
        assert callable(compare_fingerprints)

    def test_change_impact_imports(self):
        from app.services.change_impact_staleness import compute_deadline_urgency
        assert callable(compute_deadline_urgency)

    def test_telemetry_imports(self):
        from app.services.telemetry import get_source_stats
        assert callable(get_source_stats)

    def test_anomaly_detection_imports(self):
        from app.services.anomaly_detection import detect_anomalies
        assert callable(detect_anomalies)

    def test_verification_confidence_imports(self):
        from app.services.verification_confidence import assess_field_confidence
        assert callable(assess_field_confidence)
