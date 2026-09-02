"""Tests for the Confidence Decay + Evidence Aging layer.

Tests cover:
- Fresh evidence (negligible decay)
- Aged evidence (significant decay)
- Critical fields decay faster than stable descriptive fields
- Never verified fields
- Source health degradation accelerates decay
- Manual overrides respected
- New verification resets decay
- Bounded [0,1]
- Monotonic decay
- Historical confidence preserved
- Scheduler urgency increases appropriately
- Deterministic output
- Batch operations
- No N+1
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.confidence_decay import (
    CONFIDENCE_STATE_AGING,
    CONFIDENCE_STATE_CRITICAL,
    CONFIDENCE_STATE_DEGRADED,
    CONFIDENCE_STATE_FRESH,
    CONFIDENCE_STATE_NEVER_VERIFIED,
    CLASS_DECAY_HALF_LIFE_DAYS,
    ConfidenceDecayOverride,
    ConfidenceDecayProfile,
    ConfidenceState,
    batch_evaluate_confidence_decay,
    classify_confidence_state,
    compute_decay_factor,
    compute_evidence_freshness_factor,
    evaluate_field_confidence_decay,
    evaluate_scholarship_confidence_decay,
    get_decay_summary,
    reset_confidence_after_verification,
    should_trigger_review,
)
from app.services.freshness_governance import (
    FRESHNESS_CLASS_CRITICAL,
    FRESHNESS_CLASS_HIGH,
    FRESHNESS_CLASS_LOW,
    FRESHNESS_CLASS_MEDIUM,
)


class TestFreshEvidence:
    """Tests for fresh evidence (negligible decay)."""

    def test_fresh_evidence_no_decay(self):
        """Evidence verified today should have no decay."""
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.9,
            last_verified_at=date.today(),
        )
        assert profile.age_days == 0
        assert profile.decay_factor == 1.0
        assert profile.decayed_confidence == 0.9
        assert profile.confidence_state == CONFIDENCE_STATE_FRESH

    def test_fresh_evidence_one_day_old(self):
        """Evidence verified one day ago should have negligible decay."""
        yesterday = date.today() - timedelta(days=1)
        profile = evaluate_field_confidence_decay(
            field_name="title",
            original_confidence=0.8,
            last_verified_at=yesterday,
        )
        assert profile.age_days == 1
        assert profile.decay_factor > 0.95
        assert profile.confidence_state == CONFIDENCE_STATE_FRESH

    def test_fresh_evidence_high_confidence(self):
        """High confidence evidence remains fresh when recently verified."""
        last_week = date.today() - timedelta(days=7)
        profile = evaluate_field_confidence_decay(
            field_name="description",
            original_confidence=0.95,
            last_verified_at=last_week,
        )
        assert profile.decayed_confidence > 0.8
        assert profile.confidence_state == CONFIDENCE_STATE_FRESH


class TestAgedEvidence:
    """Tests for aged evidence (significant decay)."""

    def test_aged_evidence_half_life(self):
        """Evidence at half-life should have ~50% freshness factor."""
        half_life_days = int(CLASS_DECAY_HALF_LIFE_DAYS[FRESHNESS_CLASS_MEDIUM])
        last_verified = date.today() - timedelta(days=half_life_days)
        factor = compute_evidence_freshness_factor(
            half_life_days,
            FRESHNESS_CLASS_MEDIUM,
        )
        assert 0.49 < factor < 0.51

    def test_aged_evidence_significant_decay(self):
        """Evidence aged beyond half-life should show significant decay."""
        old_date = date.today() - timedelta(days=120)
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.9,
            last_verified_at=old_date,
        )
        assert profile.decayed_confidence < 0.5
        assert profile.confidence_state in (CONFIDENCE_STATE_DEGRADED, CONFIDENCE_STATE_CRITICAL)

    def test_very_old_evidence_critical_decay(self):
        """Evidence aged very long should be in critical state."""
        very_old = date.today() - timedelta(days=365)
        profile = evaluate_field_confidence_decay(
            field_name="eligibility",
            original_confidence=0.95,
            last_verified_at=very_old,
        )
        assert profile.confidence_state == CONFIDENCE_STATE_CRITICAL
        assert profile.decayed_confidence < 0.2


class TestCriticalFieldFasterDecay:
    """Tests confirming critical fields decay faster than stable fields."""

    def test_critical_field_half_life_shorter(self):
        """Critical fields should have shorter half-life than low fields."""
        assert CLASS_DECAY_HALF_LIFE_DAYS[FRESHNESS_CLASS_CRITICAL] < CLASS_DECAY_HALF_LIFE_DAYS[FRESHNESS_CLASS_LOW]

    def test_critical_field_decays_faster_than_low(self):
        """Same age: critical field decays faster than low field."""
        age_days = 30
        last_verified = date.today() - timedelta(days=age_days)

        critical_profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.9,
            last_verified_at=last_verified,
        )
        low_profile = evaluate_field_confidence_decay(
            field_name="description",
            original_confidence=0.9,
            last_verified_at=last_verified,
        )

        assert critical_profile.decay_factor < low_profile.decay_factor
        assert critical_profile.decayed_confidence < low_profile.decayed_confidence

    def test_all_classes_decay_ordering(self):
        """Decay factors should be ordered: CRITICAL < HIGH < MEDIUM < LOW."""
        age_days = 30
        last_verified = date.today() - timedelta(days=age_days)

        classes = [
            (FRESHNESS_CLASS_CRITICAL, "deadline"),
            (FRESHNESS_CLASS_HIGH, "application_link"),
            (FRESHNESS_CLASS_MEDIUM, "duration"),
            (FRESHNESS_CLASS_LOW, "title"),
        ]

        decay_factors = []
        for _, field_name in classes:
            profile = evaluate_field_confidence_decay(
                field_name=field_name,
                original_confidence=0.8,
                last_verified_at=last_verified,
            )
            decay_factors.append(profile.decay_factor)

        assert decay_factors[0] < decay_factors[1] < decay_factors[2] < decay_factors[3]


class TestStableFieldSlowerDecay:
    """Tests confirming stable fields decay slower."""

    def test_low_field_retains_confidence_longer(self):
        """Low freshness class retains confidence longer than critical."""
        age_days = 60
        last_verified = date.today() - timedelta(days=age_days)

        low_profile = evaluate_field_confidence_decay(
            field_name="notes",
            original_confidence=0.7,
            last_verified_at=last_verified,
        )

        assert low_profile.decayed_confidence > 0.4
        assert low_profile.decay_factor > 0.5

    def test_low_field_still_fresh_at_30_days(self):
        """Low field at 30 days should still have significant confidence."""
        last_verified = date.today() - timedelta(days=30)
        profile = evaluate_field_confidence_decay(
            field_name="country",
            original_confidence=0.8,
            last_verified_at=last_verified,
        )
        assert profile.decay_factor > 0.7
        assert profile.confidence_state == CONFIDENCE_STATE_FRESH


class TestNeverVerified:
    """Tests for never-verified fields."""

    def test_never_verified_zero_confidence(self):
        """Fields never verified should have zero confidence."""
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.0,
            last_verified_at=None,
        )
        assert profile.decayed_confidence == 0.0
        assert profile.confidence_state == CONFIDENCE_STATE_NEVER_VERIFIED

    def test_never_verified_reason_code(self):
        """Never verified fields should have 'never_verified' reason code."""
        profile = evaluate_field_confidence_decay(
            field_name="funding",
            original_confidence=0.0,
            last_verified_at=None,
        )
        assert "never_verified" in profile.decay_reason_codes

    def test_zero_original_confidence(self):
        """Zero original confidence should result in zero decayed confidence."""
        last_verified = date.today() - timedelta(days=10)
        profile = evaluate_field_confidence_decay(
            field_name="title",
            original_confidence=0.0,
            last_verified_at=last_verified,
        )
        assert profile.decayed_confidence == 0.0


class TestSourceHealthDegradation:
    """Tests for source health accelerating decay."""

    def test_healthy_source_no_acceleration(self):
        """Healthy source should not accelerate decay beyond freshness."""
        last_verified = date.today() - timedelta(days=30)
        source_health = MagicMock()
        source_health.manual_override = None
        source_health.health_status = "healthy"

        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=last_verified,
            source_health=source_health,
        )
        assert profile.source_reliability == 1.0

    def test_degraded_source_accelerates_decay(self):
        """Degraded source should accelerate decay."""
        last_verified = date.today() - timedelta(days=30)
        healthy_health = MagicMock()
        healthy_health.manual_override = None
        healthy_health.health_status = "healthy"

        degraded_health = MagicMock()
        degraded_health.manual_override = None
        degraded_health.health_status = "degraded"

        healthy_profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=last_verified,
            source_health=healthy_health,
        )
        degraded_profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=last_verified,
            source_health=degraded_health,
        )

        assert degraded_profile.decayed_confidence < healthy_profile.decayed_confidence

    def test_unhealthy_source_maximum_acceleration(self):
        """Unhealthy source should significantly accelerate decay."""
        last_verified = date.today() - timedelta(days=30)
        unhealthy_health = MagicMock()
        unhealthy_health.manual_override = None
        unhealthy_health.health_status = "unhealthy"

        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=last_verified,
            source_health=unhealthy_health,
        )
        assert profile.source_reliability == 0.4

    def test_source_health_acceleration_reason_code(self):
        """Source health acceleration should be reflected in reason codes."""
        last_verified = date.today() - timedelta(days=30)
        degraded_health = MagicMock()
        degraded_health.manual_override = None
        degraded_health.health_status = "degraded"

        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=last_verified,
            source_health=degraded_health,
        )
        assert "source_health_acceleration" in profile.decay_reason_codes


class TestManualOverride:
    """Tests for manual overrides."""

    def test_override_forced_confidence(self):
        """Manual override should set forced confidence value."""
        overrides = {
            "deadline": ConfidenceDecayOverride(
                field_name="deadline",
                forced_confidence=0.95,
                reason_code="expert_verified",
            ),
        }
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.5,
            last_verified_at=date.today() - timedelta(days=100),
            overrides=overrides,
        )
        assert profile.decayed_confidence == 0.95
        assert "expert_verified" in profile.decay_reason_codes

    def test_override_forced_state(self):
        """Manual override should set forced state."""
        overrides = {
            "title": ConfidenceDecayOverride(
                field_name="title",
                forced_confidence=1.0,
                forced_state=CONFIDENCE_STATE_FRESH,
                reason_code="curator_override",
            ),
        }
        profile = evaluate_field_confidence_decay(
            field_name="title",
            original_confidence=0.3,
            last_verified_at=None,
            overrides=overrides,
        )
        assert profile.confidence_state == CONFIDENCE_STATE_FRESH

    def test_no_override_normal_decay(self):
        """Without overrides, normal decay should apply."""
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=date.today() - timedelta(days=60),
        )
        assert profile.decayed_confidence < 0.8


class TestNewVerificationResetsDecay:
    """Tests for new verification resetting decay."""

    def test_reset_returns_new_confidence(self):
        """New verification should return newly verified confidence."""
        decayed = 0.3
        new_verified = 0.9
        result = reset_confidence_after_verification(decayed, new_verified)
        assert result == 0.9

    def test_reset_bounded(self):
        """Reset confidence should be bounded [0,1]."""
        assert reset_confidence_after_verification(0.5, 1.5) == 1.0
        assert reset_confidence_after_verification(0.5, -0.1) == 0.0

    def test_new_verification_improves_confidence(self):
        """New verification with higher confidence should improve result."""
        old_profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.5,
            last_verified_at=date.today() - timedelta(days=100),
        )
        new_confidence = reset_confidence_after_verification(
            old_profile.decayed_confidence,
            0.95,
        )
        assert new_confidence > old_profile.decayed_confidence


class TestBoundedConfidence:
    """Tests for confidence bounded [0,1]."""

    def test_lower_bound(self):
        """Confidence should never go below 0."""
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.1,
            last_verified_at=date.today() - timedelta(days=1000),
        )
        assert profile.decayed_confidence >= 0.0

    def test_upper_bound(self):
        """Confidence should never exceed 1."""
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=1.0,
            last_verified_at=date.today(),
        )
        assert profile.decayed_confidence <= 1.0

    def test_decay_factor_bounded(self):
        """Decay factor should be bounded [0,1]."""
        factor = compute_decay_factor(1000, FRESHNESS_CLASS_CRITICAL, 0.4)
        assert 0.0 <= factor <= 1.0

    def test_freshness_factor_bounded(self):
        """Freshness factor should be bounded [0,1]."""
        factor = compute_evidence_freshness_factor(10000, FRESHNESS_CLASS_LOW)
        assert 0.0 <= factor <= 1.0


class TestMonotonicDecay:
    """Tests for monotonic decay."""

    def test_decay_decreases_with_age(self):
        """Older evidence should have equal or lower confidence."""
        original_confidence = 0.8
        today = date.today()

        profiles = []
        for age in [0, 10, 30, 60, 90, 180]:
            last_verified = today - timedelta(days=age)
            profile = evaluate_field_confidence_decay(
                field_name="deadline",
                original_confidence=original_confidence,
                last_verified_at=last_verified,
            )
            profiles.append((age, profile.decayed_confidence))

        for i in range(1, len(profiles)):
            assert profiles[i][1] <= profiles[i - 1][1], (
                f"Age {profiles[i][0]} confidence {profiles[i][1]} should be <= "
                f"age {profiles[i-1][0]} confidence {profiles[i-1][1]}"
            )

    def test_freshness_factor_monotonic(self):
        """Freshness factor should decrease monotonically with age."""
        factors = []
        for age in [0, 10, 20, 30, 60, 120]:
            factor = compute_evidence_freshness_factor(age, FRESHNESS_CLASS_HIGH)
            factors.append(factor)

        for i in range(1, len(factors)):
            assert factors[i] <= factors[i - 1]

    def test_critical_field_steeper_monotonic(self):
        """Critical fields should have steeper monotonic decay than low."""
        today = date.today()
        critical_decay = []
        low_decay = []

        for age in [0, 15, 30, 60]:
            last = today - timedelta(days=age)
            critical = evaluate_field_confidence_decay(
                field_name="deadline",
                original_confidence=0.9,
                last_verified_at=last,
            )
            low = evaluate_field_confidence_decay(
                field_name="title",
                original_confidence=0.9,
                last_verified_at=last,
            )
            critical_decay.append(critical.decayed_confidence)
            low_decay.append(low.decayed_confidence)

        critical_diff = critical_decay[0] - critical_decay[-1]
        low_diff = low_decay[0] - low_decay[-1]
        assert critical_diff > low_diff


class TestHistoricalConfidencePreserved:
    """Tests that historical confidence/context is preserved."""

    def test_original_confidence_stored(self):
        """Original confidence should be preserved in the profile."""
        original = 0.85
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=original,
            last_verified_at=date.today() - timedelta(days=30),
        )
        assert profile.original_confidence == original

    def test_historical_snapshot_retains_confidence(self):
        """Historical confidence values should not be rewritten."""
        original_confidence = 0.95
        old_date = date.today() - timedelta(days=365)

        profile = evaluate_field_confidence_decay(
            field_name="eligibility",
            original_confidence=original_confidence,
            last_verified_at=old_date,
        )
        assert profile.original_confidence == original_confidence

    def test_decay_factor_separate_from_original(self):
        """Decay factor is separate from original confidence."""
        profile = evaluate_field_confidence_decay(
            field_name="funding",
            original_confidence=0.7,
            last_verified_at=date.today() - timedelta(days=60),
        )
        assert profile.decay_factor < 1.0
        assert profile.original_confidence == 0.7


class TestSchedulerUrgency:
    """Tests for scheduler urgency increasing appropriately."""

    def test_fresh_evidence_low_urgency(self):
        """Fresh evidence should have low verification urgency."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={"deadline": 0.9},
            field_timestamps={"deadline": date.today()},
        )
        assert result.verification_urgency < 30

    def test_old_evidence_high_urgency(self):
        """Old evidence should have high verification urgency."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={"deadline": 0.9},
            field_timestamps={"deadline": date.today() - timedelta(days=200)},
        )
        assert result.verification_urgency > 50

    def test_urgency_increases_with_decay(self):
        """Urgency should increase as confidence decays."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        fresh = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={"deadline": 0.9},
            field_timestamps={"deadline": date.today()},
        )
        aged = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={"deadline": 0.9},
            field_timestamps={"deadline": date.today() - timedelta(days=120)},
        )
        assert aged.verification_urgency > fresh.verification_urgency

    def test_next_required_verification_set(self):
        """Next required verification date should be set for aged fields."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={"deadline": 0.9},
            field_timestamps={"deadline": date.today() - timedelta(days=100)},
        )
        assert result.next_required_verification is not None

    def test_summary_includes_urgency(self):
        """Decay summary should include verification urgency."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={"deadline": 0.5},
            field_timestamps={"deadline": date.today() - timedelta(days=100)},
        )
        summary = get_decay_summary(result)
        assert "verification_urgency" in summary
        assert summary["verification_urgency"] > 0


class TestDeterministicOutput:
    """Tests for deterministic output."""

    def test_same_input_same_output(self):
        """Same inputs should always produce same outputs."""
        results = []
        for _ in range(5):
            profile = evaluate_field_confidence_decay(
                field_name="deadline",
                original_confidence=0.8,
                last_verified_at=date.today() - timedelta(days=45),
            )
            results.append(profile)

        for r in results[1:]:
            assert r.decayed_confidence == results[0].decayed_confidence
            assert r.decay_factor == results[0].decay_factor
            assert r.confidence_state == results[0].confidence_state

    def test_deterministic_decay_factor(self):
        """Decay factor should be deterministic."""
        factor1 = compute_decay_factor(30, FRESHNESS_CLASS_HIGH, 0.8)
        factor2 = compute_decay_factor(30, FRESHNESS_CLASS_HIGH, 0.8)
        assert factor1 == factor2

    def test_deterministic_freshness_factor(self):
        """Freshness factor should be deterministic."""
        factor1 = compute_evidence_freshness_factor(45, FRESHNESS_CLASS_MEDIUM)
        factor2 = compute_evidence_freshness_factor(45, FRESHNESS_CLASS_MEDIUM)
        assert factor1 == factor2


class TestBatchOperations:
    """Tests for batch evaluation."""

    def test_batch_returns_all_results(self):
        """Batch should return results for all scholarships."""
        session = MagicMock()
        scholarships = []
        confidences_map = {}
        timestamps_map = {}

        for i in range(3):
            s = MagicMock()
            s.id = i + 1
            s.official_source_url = f"https://source{i}.com"
            scholarships.append(s)
            confidences_map[s.id] = {"deadline": 0.8}
            timestamps_map[s.id] = {"deadline": date.today() - timedelta(days=30)}

        results = batch_evaluate_confidence_decay(
            session=session,
            scholarships=scholarships,
            field_confidences_map=confidences_map,
            field_timestamps_map=timestamps_map,
        )
        assert len(results) == 3
        for s in scholarships:
            assert s.id in results

    def test_batch_caches_source_health(self):
        """Batch should cache source health lookups."""
        session = MagicMock()
        session.scalar.return_value = None

        scholarships = []
        confidences_map = {}
        timestamps_map = {}

        for i in range(3):
            s = MagicMock()
            s.id = i + 1
            s.official_source_url = "https://same-source.com/scholarship"
            scholarships.append(s)
            confidences_map[s.id] = {"deadline": 0.8}
            timestamps_map[s.id] = {"deadline": date.today()}

        batch_evaluate_confidence_decay(
            session=session,
            scholarships=scholarships,
            field_confidences_map=confidences_map,
            field_timestamps_map=timestamps_map,
        )
        assert session.scalar.call_count == 1

    def test_batch_empty_input(self):
        """Batch with empty input should return empty dict."""
        session = MagicMock()
        results = batch_evaluate_confidence_decay(
            session=session,
            scholarships=[],
            field_confidences_map={},
            field_timestamps_map={},
        )
        assert results == {}


class TestNoNPlusOne:
    """Tests ensuring no N+1 query patterns."""

    def test_batch_single_query_per_unique_source(self):
        """Batch should only query source health once per unique source."""
        session = MagicMock()
        session.scalar.return_value = None

        scholarships = []
        confidences_map = {}
        timestamps_map = {}

        for i in range(5):
            s = MagicMock()
            s.id = i + 1
            s.official_source_url = "https://shared-source.com/scholarship"
            scholarships.append(s)
            confidences_map[s.id] = {"deadline": 0.8}
            timestamps_map[s.id] = {"deadline": date.today()}

        batch_evaluate_confidence_decay(
            session=session,
            scholarships=scholarships,
            field_confidences_map=confidences_map,
            field_timestamps_map=timestamps_map,
        )
        assert session.scalar.call_count == 1


class TestConfidenceStateClassification:
    """Tests for confidence state classification."""

    def test_fresh_state(self):
        """High confidence should be FRESH state."""
        assert classify_confidence_state(0.95) == CONFIDENCE_STATE_FRESH

    def test_aging_state(self):
        """Medium-high confidence should be AGING state."""
        assert classify_confidence_state(0.55) == CONFIDENCE_STATE_AGING

    def test_degraded_state(self):
        """Medium-low confidence should be DEGRADED state."""
        assert classify_confidence_state(0.35) == CONFIDENCE_STATE_DEGRADED

    def test_critical_state(self):
        """Very low confidence should be CRITICAL state."""
        assert classify_confidence_state(0.10) == CONFIDENCE_STATE_CRITICAL


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_should_trigger_review_never_verified(self):
        """Never verified fields should trigger review."""
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.0,
            last_verified_at=None,
        )
        should, reason = should_trigger_review(profile)
        assert should is True
        assert "never verified" in reason.lower()

    def test_should_trigger_review_below_threshold(self):
        """Fields below threshold should trigger review."""
        last_verified = date.today() - timedelta(days=300)
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.5,
            last_verified_at=last_verified,
        )
        should, reason = should_trigger_review(profile, review_threshold=0.30)
        assert should is True

    def test_should_not_trigger_review_fresh(self):
        """Fresh fields should not trigger review."""
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.95,
            last_verified_at=date.today(),
        )
        should, _ = should_trigger_review(profile)
        assert should is False

    def test_get_decay_summary_structure(self):
        """Decay summary should have expected structure."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={"deadline": 0.8},
            field_timestamps={"deadline": date.today()},
        )
        summary = get_decay_summary(result)
        assert "scholarship_id" in summary
        assert "overall_confidence" in summary
        assert "confidence_state" in summary
        assert "verification_urgency" in summary
        assert "reason_codes" in summary
        assert "field_count" in summary


class TestScholarshipDecayResult:
    """Tests for scholarship-level decay results."""

    def test_overall_confidence_minimum(self):
        """Overall confidence should be minimum across fields."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={
                "deadline": 0.9,
                "title": 0.3,
                "description": 0.7,
            },
            field_timestamps={
                "deadline": date.today() - timedelta(days=100),
                "title": date.today() - timedelta(days=10),
                "description": date.today() - timedelta(days=50),
            },
        )
        assert result.overall_confidence == min(
            p.decayed_confidence for p in result.field_profiles
        )

    def test_worst_state_overall(self):
        """Overall confidence state should be worst across fields."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={
                "deadline": 0.3,
                "title": 0.9,
            },
            field_timestamps={
                "deadline": date.today() - timedelta(days=300),
                "title": date.today(),
            },
        )
        assert result.confidence_state == CONFIDENCE_STATE_CRITICAL

    def test_empty_fields_never_verified(self):
        """Scholarship with no fields should have NEVER_VERIFIED state."""
        session = MagicMock()
        scholarship = MagicMock()
        scholarship.id = 1
        scholarship.official_source_url = "https://example.com"

        result = evaluate_scholarship_confidence_decay(
            session=session,
            scholarship=scholarship,
            field_confidences={},
            field_timestamps={},
        )
        assert result.confidence_state == CONFIDENCE_STATE_NEVER_VERIFIED
        assert result.overall_confidence == 0.0


class TestEdgeCases:
    """Edge case tests."""

    def test_future_verification_date(self):
        """Future verification dates should be treated as today."""
        future_date = date.today() + timedelta(days=5)
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=future_date,
        )
        assert profile.age_days == 0
        assert profile.decayed_confidence == 0.8

    def test_very_high_original_confidence(self):
        """Very high original confidence should decay appropriately."""
        last_verified = date.today() - timedelta(days=60)
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=1.0,
            last_verified_at=last_verified,
        )
        assert profile.original_confidence == 1.0
        assert profile.decayed_confidence < 1.0

    def test_datetime_input(self):
        """Should accept datetime inputs, not just date."""
        dt = datetime.now(timezone.utc) - timedelta(days=30)
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=dt,
        )
        assert profile.age_days == 30
        assert profile.decayed_confidence < 0.8

    def test_negative_age_clamped(self):
        """Negative age should be clamped to 0."""
        future = date.today() + timedelta(days=10)
        profile = evaluate_field_confidence_decay(
            field_name="deadline",
            original_confidence=0.8,
            last_verified_at=future,
        )
        assert profile.age_days == 0
