"""Tests for anomaly detection and intelligent change validation engine.

Tests cover:
- Normal small change (no anomaly)
- Large deadline shift (anomaly)
- Abnormal funding change (anomaly)
- Drastic duration change (anomaly)
- Critical multi-field change (anomaly)
- Historical pattern deviation (anomaly)
- Source disagreement anomaly (anomaly)
- Unhealthy-source anomaly (anomaly)
- Lifecycle inconsistency (anomaly)
- Severity thresholds
- Deterministic score
- False-positive control
- No N+1 (batch detection)
- Batch detection
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.anomaly_detection import (
    AnomalyReasonCode,
    AnomalyResult,
    AnomalySeverity,
    aggregate_anomaly_severity,
    compute_anomaly_score,
    detect_anomalies,
    detect_batch_anomalies,
    detect_change_frequency_anomaly,
    detect_confidence_anomaly,
    detect_deadline_anomaly,
    detect_duration_anomaly,
    detect_eligibility_anomaly,
    detect_funding_anomaly,
    detect_lifecycle_anomaly,
    detect_multi_field_anomaly,
    detect_source_disagreement_anomaly,
    detect_source_health_anomaly,
    detect_value_oscillation,
    summarize_anomalies,
)
from app.services.evidence_arbitration import (
    ArbitrationDecision,
    ArbitrationResult,
)
from app.services.verification_confidence import (
    ConfidenceLevel,
    VerificationState,
)


class TestNormalSmallChange:
    """Test that normal small changes produce no anomalies."""

    def test_normal_small_deadline_change(self):
        old_date = date(2026, 6, 1)
        new_date = date(2026, 6, 15)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert not result.anomaly_detected
        assert result.severity == AnomalySeverity.LOW
        assert result.anomaly_score == 0.0

    def test_normal_funding_same(self):
        result = detect_funding_anomaly("funding", "full", "full")
        assert not result.anomaly_detected

    def test_normal_duration_small_change(self):
        result = detect_duration_anomaly("duration", "24", "25")
        assert not result.anomaly_detected

    def test_normal_eligibility_tweak(self):
        result = detect_eligibility_anomaly(
            "eligibility",
            "Open to all nationalities",
            "Open to all nationalities with bachelor degree",
        )
        assert result is None


class TestLargeDeadlineShift:
    """Test deadline shift anomalies."""

    def test_medium_deadline_shift(self):
        old_date = date(2026, 6, 1)
        new_date = date(2026, 7, 15)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.MEDIUM
        assert AnomalyReasonCode.LARGE_DEADLINE_SHIFT.value in result.reason_codes

    def test_high_deadline_shift(self):
        old_date = date(2026, 6, 1)
        new_date = date(2026, 8, 15)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.HIGH

    def test_critical_deadline_shift(self):
        old_date = date(2026, 6, 1)
        new_date = date(2026, 12, 1)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.CRITICAL

    def test_critical_deadline_shift_nine_months(self):
        old_date = date(2026, 6, 1)
        new_date = date(2027, 3, 1)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.CRITICAL

    def test_deadline_moves_backward(self):
        old_date = date(2026, 9, 1)
        new_date = date(2026, 6, 1)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert result.anomaly_detected
        assert AnomalyReasonCode.DEADLINE_MOVES_BACKWARD.value in result.reason_codes
        # Large backward shift (92 days) is CRITICAL
        assert result.severity == AnomalySeverity.CRITICAL

    def test_deadline_far_future(self):
        old_date = date(2026, 6, 1)
        new_date = date(2030, 6, 1)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert result.anomaly_detected
        assert AnomalyReasonCode.DEADLINE_FAR_FUTURE.value in result.reason_codes


class TestAbnormalFundingChange:
    """Test funding change anomalies."""

    def test_full_to_none(self):
        result = detect_funding_anomaly("funding", "full", "none")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.CRITICAL
        assert AnomalyReasonCode.FUNDING_TO_NONE.value in result.reason_codes

    def test_full_to_partial(self):
        result = detect_funding_anomaly("funding", "full", "partial")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.HIGH
        assert AnomalyReasonCode.FUNDING_REDUCTION.value in result.reason_codes

    def test_partial_to_none(self):
        result = detect_funding_anomaly("funding", "partial", "none")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.HIGH

    def test_none_to_full(self):
        result = detect_funding_anomaly("funding", "none", "full")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.MEDIUM
        assert AnomalyReasonCode.FUNDING_SUDDEN_FULL.value in result.reason_codes

    def test_partial_to_full(self):
        result = detect_funding_anomaly("funding", "partial", "full")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.LOW


class TestDrasticDurationChange:
    """Test duration change anomalies."""

    def test_large_reduction(self):
        result = detect_duration_anomaly("duration", "24", "6")
        assert result.anomaly_detected
        assert result.severity in (AnomalySeverity.HIGH, AnomalySeverity.MEDIUM)

    def test_large_extension(self):
        result = detect_duration_anomaly("duration", "12", "36")
        assert result.anomaly_detected
        assert result.severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)

    def test_critical_change(self):
        result = detect_duration_anomaly("duration", "12", "48")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.CRITICAL

    def test_duration_to_zero(self):
        result = detect_duration_anomaly("duration", "24", "0")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.HIGH
        assert AnomalyReasonCode.DURATION_ZERO.value in result.reason_codes

    def test_medium_change(self):
        result = detect_duration_anomaly("duration", "24", "15")
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.MEDIUM


class TestCriticalMultiFieldChange:
    """Test multi-field change anomalies."""

    def test_three_critical_fields(self):
        changed = {
            "deadline_date": ("2026-06-01", "2026-09-01"),
            "funding": ("full", "partial"),
            "eligibility": ("all", "restricted"),
            "title": ("Old", "New"),  # LOW criticality
        }
        result = detect_multi_field_anomaly(changed)
        assert result is not None
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.CRITICAL

    def test_five_high_fields(self):
        changed = {
            "duration": ("24", "36"),
            "required_documents": ("5", "10"),
            "documents": ("list1", "list2"),
            "requirements": ("req1", "req2"),
            "application_period": ("jun", "sep"),
        }
        result = detect_multi_field_anomaly(changed)
        assert result is not None
        assert result.severity == AnomalySeverity.HIGH

    def test_normal_changes(self):
        changed = {
            "title": ("Old", "New"),
            "description": ("Desc1", "Desc2"),
        }
        result = detect_multi_field_anomaly(changed)
        assert result is None

    def test_two_critical_two_high(self):
        changed = {
            "deadline_date": ("2026-06-01", "2026-09-01"),
            "funding": ("full", "partial"),
            "duration": ("24", "36"),
            "required_documents": ("5", "10"),
        }
        result = detect_multi_field_anomaly(changed)
        assert result is not None
        assert result.severity == AnomalySeverity.HIGH


class TestHistoricalPatternDeviation:
    """Test historical pattern anomalies."""

    def test_deadline_shift_exceeds_historical(self):
        historical = [
            date(2025, 1, 1),
            date(2025, 6, 1),
            date(2026, 1, 1),
        ]
        old_date = date(2026, 6, 1)
        new_date = date(2026, 9, 1)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date, historical)
        assert result.historical_comparison
        assert "deadline_date" in result.historical_comparison

    def test_change_frequency_spike(self):
        result = detect_change_frequency_anomaly("funding", 6, 10, 1.5)
        assert result is not None
        assert result.anomaly_detected
        assert AnomalyReasonCode.CHANGE_FREQUENCY_SPIKE.value in result.reason_codes

    def test_normal_frequency(self):
        result = detect_change_frequency_anomaly("funding", 2, 5, 1.5)
        assert result is None

    def test_value_oscillation(self):
        history = ["full", "partial", "full", "partial", "full", "partial"]
        result = detect_value_oscillation("funding", history)
        assert result is not None
        assert result.anomaly_detected
        assert AnomalyReasonCode.VALUE_OSCILLATION.value in result.reason_codes

    def test_no_oscillation(self):
        history = ["full", "full", "partial", "partial", "partial"]
        result = detect_value_oscillation("funding", history)
        assert result is None


class TestSourceDisagreementAnomaly:
    """Test source disagreement anomalies."""

    def test_arbitration_conflict(self):
        arbitration = ArbitrationResult(
            field_name="funding",
            decision=ArbitrationDecision.CONFLICT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=["authoritative_conflict"],
            reason_text="Authoritative sources disagree",
            arbitrator_id="abc123",
            arbitr_at="2026-01-01T00:00:00Z",
        )
        result = detect_source_disagreement_anomaly(arbitration)
        assert result is not None
        assert result.anomaly_detected
        assert result.severity == AnomalySeverity.HIGH

    def test_arbitration_insufficient(self):
        arbitration = ArbitrationResult(
            field_name="funding",
            decision=ArbitrationDecision.INSUFFICIENT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=["no_authoritative_evidence"],
            reason_text="No authoritative evidence",
            arbitrator_id="abc123",
            arbitr_at="2026-01-01T00:00:00Z",
        )
        result = detect_source_disagreement_anomaly(arbitration)
        assert result is not None
        assert result.severity == AnomalySeverity.MEDIUM

    def test_arbitration_consensus(self):
        arbitration = ArbitrationResult(
            field_name="funding",
            decision=ArbitrationDecision.CONSENSUS,
            winning_value="full",
            winning_source_url="https://example.com",
            winning_source_type=None,
            consensus_score=0.9,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=["multiple_authoritative_agree"],
            reason_text="Multiple authoritative sources agree",
            arbitrator_id="abc123",
            arbitr_at="2026-01-01T00:00:00Z",
        )
        result = detect_source_disagreement_anomaly(arbitration)
        assert result is None


class TestUnhealthySourceAnomaly:
    """Test source health anomalies."""

    def test_health_degradation(self):
        result = detect_source_health_anomaly(
            "https://example.com",
            45.0,
            85.0,
            "degraded",
            "healthy",
        )
        assert result is not None
        assert result.anomaly_detected
        assert AnomalyReasonCode.SOURCE_HEALTH_DEGRADATION.value in result.reason_codes

    def test_reliability_drop(self):
        result = detect_source_health_anomaly(
            "https://example.com",
            50.0,
            85.0,
            "healthy",
            "healthy",
        )
        assert result is not None
        assert result.severity in (AnomalySeverity.MEDIUM, AnomalySeverity.HIGH)

    def test_low_reliability(self):
        result = detect_source_health_anomaly(
            "https://example.com",
            20.0,
            None,
            "unhealthy",
            None,
        )
        assert result is not None
        assert result.severity == AnomalySeverity.HIGH

    def test_healthy_source(self):
        result = detect_source_health_anomaly(
            "https://example.com",
            90.0,
            85.0,
            "healthy",
            "healthy",
        )
        assert result is None


class TestLifecycleInconsistency:
    """Test lifecycle inconsistency anomalies."""

    def test_deadline_past_but_active(self):
        past_date = date(2025, 1, 1)
        result = detect_lifecycle_anomaly(
            "status",
            "active",
            past_date,
            is_verified=True,
        )
        assert result is not None
        assert result.anomaly_detected
        assert AnomalyReasonCode.LIFECYCLE_MISMATCH.value in result.reason_codes

    def test_unverified_near_deadline(self):
        near_future = date.today() + timedelta(days=14)
        result = detect_lifecycle_anomaly(
            "deadline_date",
            "active",
            near_future,
            is_verified=False,
        )
        assert result is not None
        assert result.anomaly_detected

    def test_consistent_lifecycle(self):
        future_date = date.today() + timedelta(days=90)
        result = detect_lifecycle_anomaly(
            "status",
            "active",
            future_date,
            is_verified=True,
        )
        assert result is None


class TestSeverityThresholds:
    """Test severity threshold logic."""

    def test_critical_severity(self):
        assert AnomalySeverity.CRITICAL.value == "critical"

    def test_high_severity(self):
        assert AnomalySeverity.HIGH.value == "high"

    def test_medium_severity(self):
        assert AnomalySeverity.MEDIUM.value == "medium"

    def test_low_severity(self):
        assert AnomalySeverity.LOW.value == "low"

    def test_requires_review_high(self):
        result = AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.HIGH,
            anomaly_score=0.7,
        )
        assert result.requires_review()

    def test_requires_review_critical(self):
        result = AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.CRITICAL,
            anomaly_score=1.0,
        )
        assert result.requires_review()

    def test_no_review_low(self):
        result = AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.LOW,
            anomaly_score=0.1,
        )
        assert not result.requires_review()

    def test_should_block_critical(self):
        result = AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.CRITICAL,
            anomaly_score=1.0,
        )
        assert result.should_block()

    def test_no_block_high(self):
        result = AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.HIGH,
            anomaly_score=0.7,
        )
        assert not result.should_block()


class TestDeterministicScore:
    """Test deterministic behavior."""

    def test_same_input_same_output(self):
        old_date = date(2026, 6, 1)
        new_date = date(2026, 9, 15)
        result1 = detect_deadline_anomaly("deadline_date", old_date, new_date)
        result2 = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert result1.anomaly_score == result2.anomaly_score
        assert result1.severity == result2.severity
        assert result1.reason_codes == result2.reason_codes

    def test_funding_deterministic(self):
        result1 = detect_funding_anomaly("funding", "full", "none")
        result2 = detect_funding_anomaly("funding", "full", "none")
        assert result1.anomaly_score == result2.anomaly_score

    def test_duration_deterministic(self):
        result1 = detect_duration_anomaly("duration", "24", "6")
        result2 = detect_duration_anomaly("duration", "24", "6")
        assert result1.anomaly_score == result2.anomaly_score


class TestFalsePositiveControl:
    """Test false-positive control."""

    def test_small_deadline_change_no_anomaly(self):
        old_date = date(2026, 6, 1)
        new_date = date(2026, 6, 7)
        result = detect_deadline_anomaly("deadline_date", old_date, new_date)
        assert not result.anomaly_detected

    def test_same_values_no_anomaly(self):
        result = detect_funding_anomaly("funding", "full", "full")
        assert not result.anomaly_detected

    def test_normal_frequency_no_anomaly(self):
        result = detect_change_frequency_anomaly("funding", 1, 3, 1.5)
        assert result is None

    def test_consistent_values_no_oscillation(self):
        history = ["full", "full", "full", "full"]
        result = detect_value_oscillation("funding", history)
        assert result is None

    def test_empty_history_no_oscillation(self):
        result = detect_value_oscillation("funding", [])
        assert result is None

    def test_none_values_no_crash(self):
        result = detect_funding_anomaly("funding", None, None)
        assert not result.anomaly_detected

    def test_invalid_duration_no_crash(self):
        result = detect_duration_anomaly("duration", "abc", "def")
        assert not result.anomaly_detected


class TestNoNPlusOne:
    """Test batch detection avoids N+1."""

    def test_batch_detects_multiple_anomalies(self):
        changes = [
            {"field_name": "deadline_date", "old_value": date(2026, 6, 1), "new_value": date(2027, 3, 1)},
            {"field_name": "funding", "old_value": "full", "new_value": "none"},
            {"field_name": "duration", "old_value": "24", "new_value": "6"},
        ]
        results = detect_batch_anomalies(changes)
        assert "deadline_date" in results
        assert "funding" in results
        assert "duration" in results

    def test_batch_empty_input(self):
        results = detect_batch_anomalies([])
        assert results == {}

    def test_batch_single_change(self):
        changes = [{"field_name": "funding", "old_value": "full", "new_value": "none"}]
        results = detect_batch_anomalies(changes)
        assert "funding" in results


class TestBatchDetection:
    """Test batch anomaly detection."""

    def test_multi_field_detected_in_batch(self):
        changes = [
            {"field_name": "deadline_date", "old_value": "2026-06-01", "new_value": "2026-09-01"},
            {"field_name": "funding", "old_value": "full", "new_value": "partial"},
            {"field_name": "eligibility", "old_value": "all", "new_value": "restricted"},
        ]
        results = detect_batch_anomalies(changes)
        all_anomalies = [a for anomalies in results.values() for a in anomalies]
        assert len(all_anomalies) > 0

    def test_summary_aggregation(self):
        anomalies = [
            AnomalyResult(anomaly_detected=True, severity=AnomalySeverity.MEDIUM, anomaly_score=0.4),
            AnomalyResult(anomaly_detected=True, severity=AnomalySeverity.HIGH, anomaly_score=0.7),
        ]
        summary = summarize_anomalies(anomalies)
        assert summary["anomaly_detected"]
        assert summary["severity"] == AnomalySeverity.HIGH.value
        assert summary["requires_review"]
        assert summary["total_anomalies"] == 2

    def test_summary_empty(self):
        summary = summarize_anomalies([])
        assert not summary["anomaly_detected"]
        assert summary["total_anomalies"] == 0

    def test_aggregate_severity(self):
        severities = [AnomalySeverity.LOW, AnomalySeverity.HIGH, AnomalySeverity.MEDIUM]
        assert aggregate_anomaly_severity(severities) == AnomalySeverity.HIGH

    def test_aggregate_empty(self):
        assert aggregate_anomaly_severity([]) == AnomalySeverity.LOW

    def test_compute_score(self):
        anomalies = [
            AnomalyResult(anomaly_detected=True, severity=AnomalySeverity.HIGH, anomaly_score=0.7),
            AnomalyResult(anomaly_detected=True, severity=AnomalySeverity.MEDIUM, anomaly_score=0.4),
        ]
        score = compute_anomaly_score(anomalies)
        assert 0.0 < score < 1.0

    def test_compute_score_empty(self):
        assert compute_anomaly_score([]) == 0.0


class TestConfidenceAnomaly:
    """Test confidence downgrade detection."""

    def test_high_to_low(self):
        result = detect_confidence_anomaly(
            "funding",
            ConfidenceLevel.LOW,
            ConfidenceLevel.HIGH,
        )
        assert result is not None
        assert result.severity == AnomalySeverity.HIGH
        assert AnomalyReasonCode.CONFIDENCE_DOWNGRADE.value in result.reason_codes

    def test_high_to_conflict(self):
        result = detect_confidence_anomaly(
            "funding",
            ConfidenceLevel.CONFLICT,
            ConfidenceLevel.HIGH,
        )
        assert result is not None
        assert result.severity == AnomalySeverity.CRITICAL

    def test_medium_to_low(self):
        result = detect_confidence_anomaly(
            "funding",
            ConfidenceLevel.LOW,
            ConfidenceLevel.MEDIUM,
        )
        assert result is not None
        assert result.severity == AnomalySeverity.MEDIUM

    def test_no_change(self):
        result = detect_confidence_anomaly(
            "funding",
            ConfidenceLevel.HIGH,
            ConfidenceLevel.HIGH,
        )
        assert result is None

    def test_state_regression(self):
        result = detect_confidence_anomaly(
            "funding",
            ConfidenceLevel.LOW,
            ConfidenceLevel.HIGH,
            VerificationState.UNCERTAIN,
            VerificationState.VERIFIED,
        )
        assert result is not None
        assert AnomalyReasonCode.VERIFICATION_STATE_REGRESSION.value in result.reason_codes


class TestEligibilityAnomaly:
    """Test eligibility change detection."""

    def test_restriction_increase(self):
        result = detect_eligibility_anomaly(
            "eligibility",
            "Open to all",
            "Only citizens of specific countries with limited slots",
        )
        assert result is not None
        assert result.anomaly_detected
        assert AnomalyReasonCode.ELIGIBILITY_RESTRICTED.value in result.reason_codes

    def test_no_change(self):
        result = detect_eligibility_anomaly(
            "eligibility",
            "Open to all",
            "Open to all",
        )
        assert result is None

    def test_normal_expansion(self):
        result = detect_eligibility_anomaly(
            "eligibility",
            "Some countries",
            "Many countries",
        )
        assert result is None or result.severity == AnomalySeverity.LOW


class TestDetectAnomaliesIntegration:
    """Integration tests for the main detect_anomalies function."""

    def test_normal_change_returns_empty(self):
        anomalies = detect_anomalies(
            "title",
            "Old Title",
            "New Title",
        )
        assert anomalies == []

    def test_deadline_anomaly_via_main(self):
        anomalies = detect_anomalies(
            "deadline_date",
            date(2026, 6, 1),
            date(2027, 3, 1),
        )
        assert len(anomalies) > 0
        assert any(a.severity == AnomalySeverity.CRITICAL for a in anomalies)

    def test_funding_anomaly_via_main(self):
        anomalies = detect_anomalies(
            "funding",
            "full",
            "none",
        )
        assert len(anomalies) > 0

    def test_multiple_anomalies_same_field(self):
        anomalies = detect_anomalies(
            "deadline_date",
            date(2026, 9, 1),
            date(2026, 6, 1),  # Moves backward + large shift
        )
        assert len(anomalies) >= 1
        # Should detect backward movement
        all_codes = [rc for a in anomalies for rc in a.reason_codes]
        assert AnomalyReasonCode.DEADLINE_MOVES_BACKWARD.value in all_codes

    def test_with_arbitration_result(self):
        arbitration = ArbitrationResult(
            field_name="funding",
            decision=ArbitrationDecision.CONFLICT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=["authoritative_conflict"],
            reason_text="Authoritative sources disagree",
            arbitrator_id="abc123",
            arbitr_at="2026-01-01T00:00:00Z",
        )
        anomalies = detect_anomalies(
            "funding",
            "full",
            "partial",
            arbitration_result=arbitration,
        )
        assert any(AnomalyReasonCode.SOURCE_DISAGREEMENT.value in a.reason_codes for a in anomalies)

    def test_with_value_history(self):
        anomalies = detect_anomalies(
            "funding",
            "partial",
            "full",
            value_history=["full", "partial", "full", "partial", "full", "partial"],
        )
        assert any(AnomalyReasonCode.VALUE_OSCILLATION.value in a.reason_codes for a in anomalies)
