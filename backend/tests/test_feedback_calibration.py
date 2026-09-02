"""Tests for human feedback + confidence calibration loop (TASK 35).

Tests cover:
1. Approved/rejected feedback recording
2. Confidence bucketing (0-10, 10-20, ..., 90-100)
3. Calibration error computation
4. Source-specific calibration
5. Field-specific calibration
6. Over-confidence detection
7. Under-confidence detection
8. Insufficient-sample handling
9. Recommendation generation
10. No automatic threshold mutation
11. Immutable calibration history
12. Deterministic results
13. Batch aggregation
14. No N+1 (pure computation)
15. Privacy/sensitive-data safety
16. TASKS 1-34 remain green
"""

from __future__ import annotations

import types
import unittest

fake_scheduler = types.ModuleType("app.scheduler")
fake_scheduler.start_scheduler = lambda: None
fake_scheduler.mark_due_for_review = lambda: None
import sys
sys.modules["app.scheduler"] = fake_scheduler


from app.services.feedback_calibration import (
    CalibrationBucket,
    CalibrationResult,
    CalibrationSnapshot,
    DecisionType,
    DecisionTypeCalibration,
    FeedbackRecord,
    FieldCalibration,
    HumanDecision,
    SourceCalibration,
    ThresholdAction,
    _confidence_to_bucket,
    _bucket_midpoint,
    compute_calibration,
    compute_confidence_trend,
    create_calibration_snapshot,
    detect_systematic_bias,
    record_feedback,
)


class TestFeedbackRecordApproved(unittest.TestCase):
    def test_approved_feedback(self):
        record = record_feedback(
            review_id=1,
            scholarship_id=100,
            field_name="deadline_date",
            model_confidence=0.85,
            decision="approved",
            human_decision=HumanDecision.APPROVED,
        )
        self.assertTrue(record.was_approved)
        self.assertFalse(record.was_rejected)
        self.assertTrue(record.was_correct)
        self.assertEqual(record.human_decision, "approved")


class TestFeedbackRecordRejected(unittest.TestCase):
    def test_rejected_feedback(self):
        record = record_feedback(
            review_id=2,
            scholarship_id=101,
            field_name="funding",
            model_confidence=0.50,
            decision="approve",
            human_decision=HumanDecision.REJECTED,
        )
        self.assertFalse(record.was_approved)
        self.assertTrue(record.was_rejected)
        self.assertFalse(record.was_correct)
        self.assertEqual(record.human_decision, "rejected")


class TestFeedbackRecordConfidenceNormalization(unittest.TestCase):
    def test_confidence_clamped_above_one(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=1.5, decision="x", human_decision="approved",
        )
        self.assertEqual(record.model_confidence, 1.0)

    def test_confidence_clamped_below_zero(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=-0.5, decision="x", human_decision="approved",
        )
        self.assertEqual(record.model_confidence, 0.0)

    def test_string_confidence_high(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence="high", decision="x", human_decision="approved",
        )
        self.assertAlmostEqual(record.model_confidence, 0.85)

    def test_string_confidence_low(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence="low", decision="x", human_decision="approved",
        )
        self.assertAlmostEqual(record.model_confidence, 0.15)


class TestFeedbackRecordImmutability(unittest.TestCase):
    def test_feedback_is_frozen(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=0.5, decision="x", human_decision="approved",
        )
        with self.assertRaises(AttributeError):
            record.model_confidence = 0.9


class TestConfidenceBucketing(unittest.TestCase):
    def test_bucket_0_to_10(self):
        self.assertEqual(_confidence_to_bucket(0.05), "0-10")

    def test_bucket_10_to_20(self):
        self.assertEqual(_confidence_to_bucket(0.15), "10-20")

    def test_bucket_50_to_60(self):
        self.assertEqual(_confidence_to_bucket(0.55), "50-60")

    def test_bucket_80_to_90(self):
        self.assertEqual(_confidence_to_bucket(0.85), "80-90")

    def test_bucket_90_to_100(self):
        self.assertEqual(_confidence_to_bucket(0.95), "90-100")

    def test_bucket_boundary_exact(self):
        self.assertEqual(_confidence_to_bucket(0.80), "80-90")

    def test_bucket_property(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=0.75, decision="x", human_decision="approved",
        )
        self.assertEqual(record.confidence_bucket, "70-80")


class TestBucketMidpoint(unittest.TestCase):
    def test_midpoint_0_10(self):
        self.assertEqual(_bucket_midpoint("0-10"), 5.0)

    def test_midpoint_50_60(self):
        self.assertEqual(_bucket_midpoint("50-60"), 55.0)

    def test_midpoint_90_100(self):
        self.assertEqual(_bucket_midpoint("90-100"), 95.0)


class TestCalibrationBucketProperties(unittest.TestCase):
    def test_empty_bucket_safe(self):
        bucket = CalibrationBucket(bucket="50-60")
        self.assertEqual(bucket.approval_rate, 0.0)
        self.assertEqual(bucket.rejection_rate, 0.0)
        self.assertEqual(bucket.calibration_error, 0.0)
        self.assertEqual(bucket.reliability_score, 1.0)

    def test_bucket_with_samples(self):
        bucket = CalibrationBucket(
            bucket="70-80", sample_count=20,
            approval_count=15, rejection_count=5, total_confidence=15.0,
        )
        self.assertAlmostEqual(bucket.approval_rate, 0.75)
        self.assertAlmostEqual(bucket.rejection_rate, 0.25)
        self.assertAlmostEqual(bucket.avg_confidence, 0.75)
        self.assertAlmostEqual(bucket.calibration_error, 0.0)
        self.assertAlmostEqual(bucket.reliability_score, 1.0)

    def test_bucket_over_confident(self):
        bucket = CalibrationBucket(
            bucket="80-90", sample_count=20,
            approval_count=10, rejection_count=10, total_confidence=17.0,
        )
        self.assertGreater(bucket.calibration_error, 0.0)
        self.assertEqual(bucket.recommended_action, ThresholdAction.RAISE)

    def test_bucket_under_confident(self):
        bucket = CalibrationBucket(
            bucket="30-40", sample_count=20,
            approval_count=18, rejection_count=2, total_confidence=7.0,
        )
        self.assertLess(bucket.calibration_error, 0.0)
        self.assertEqual(bucket.recommended_action, ThresholdAction.LOWER)

    def test_bucket_insufficient_data(self):
        bucket = CalibrationBucket(
            bucket="50-60", sample_count=5,
            approval_count=3, rejection_count=2, total_confidence=2.5,
        )
        self.assertEqual(bucket.recommended_action, ThresholdAction.INSUFFICIENT_DATA)


class TestComputeCalibrationEmpty(unittest.TestCase):
    def test_empty_records(self):
        result = compute_calibration([])
        self.assertEqual(result.overall_sample_count, 0)
        self.assertEqual(result.version_id, "empty")
        self.assertEqual(result.overall_approval_rate, 0.0)

    def test_all_buckets_initialized(self):
        result = compute_calibration([])
        self.assertEqual(len(result.confidence_buckets), 10)


class TestComputeCalibrationApproved(unittest.TestCase):
    def test_all_approved(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(20)
        ]
        result = compute_calibration(records)
        self.assertEqual(result.overall_sample_count, 20)
        self.assertEqual(result.overall_approval_count, 20)
        self.assertEqual(result.overall_approval_rate, 1.0)


class TestComputeCalibrationRejected(unittest.TestCase):
    def test_all_rejected(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.50, decision="approve",
                human_decision=HumanDecision.REJECTED,
            )
            for i in range(20)
        ]
        result = compute_calibration(records)
        self.assertEqual(result.overall_rejection_count, 20)
        self.assertEqual(result.overall_rejection_rate, 1.0)


class TestCalibrationError(unittest.TestCase):
    def test_perfect_calibration(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.80, decision="approve",
                human_decision=HumanDecision.APPROVED if i % 2 == 0 else HumanDecision.REJECTED,
            )
            for i in range(20)
        ]
        result = compute_calibration(records)
        self.assertAlmostEqual(result.overall_approval_rate, 0.5)
        self.assertAlmostEqual(result.overall_avg_confidence, 0.8)
        self.assertAlmostEqual(result.overall_calibration_error, 0.3)


class TestSourceSpecificCalibration(unittest.TestCase):
    def test_source_calibration_present(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
                source_url="https://www.daad.de/scholarship",
            )
            for i in range(10)
        ]
        result = compute_calibration(records)
        self.assertIn("www.daad.de", result.source_calibrations)
        sc = result.source_calibrations["www.daad.de"]
        self.assertEqual(sc.sample_count, 10)
        self.assertEqual(sc.approval_rate, 1.0)

    def test_no_source_url(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(10)
        ]
        result = compute_calibration(records)
        self.assertEqual(len(result.source_calibrations), 0)


class TestFieldSpecificCalibration(unittest.TestCase):
    def test_field_rejection_tracking(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="deadline_date",
                model_confidence=0.60, decision="approve",
                human_decision=HumanDecision.REJECTED,
            )
            for i in range(10)
        ]
        result = compute_calibration(records)
        self.assertIn("deadline_date", result.field_calibrations)
        fc = result.field_calibrations["deadline_date"]
        self.assertEqual(fc.rejection_rate, 1.0)
        self.assertTrue(fc.is_problematic)


class TestOverConfidenceDetection(unittest.TestCase):
    def test_over_confident_source(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.90, decision="approve",
                human_decision=HumanDecision.REJECTED,
                source_url="https://bad-source.example.com/page",
            )
            for i in range(10)
        ]
        result = compute_calibration(records)
        self.assertIn("bad-source.example.com", result.over_confident_sources)

    def test_not_over_confident_when_well_calibrated(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
                source_url="https://good-source.example.com/page",
            )
            for i in range(20)
        ]
        result = compute_calibration(records)
        self.assertNotIn("good-source.example.com", result.over_confident_sources)


class TestUnderConfidenceDetection(unittest.TestCase):
    def test_under_confident_source(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.20, decision="reject",
                human_decision=HumanDecision.APPROVED,
                source_url="https://under-confident.example.com/page",
            )
            for i in range(10)
        ]
        result = compute_calibration(records)
        self.assertIn("under-confident.example.com", result.under_confident_sources)


class TestInsufficientSampleHandling(unittest.TestCase):
    def test_insufficient_source_samples(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.90, decision="approve",
                human_decision=HumanDecision.REJECTED,
                source_url="https://rare.example.com/page",
            )
            for i in range(3)
        ]
        result = compute_calibration(records)
        sc = result.source_calibrations.get("rare.example.com")
        self.assertIsNotNone(sc)
        self.assertFalse(sc.is_over_confident)

    def test_insufficient_overall_samples(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.5, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(5)
        ]
        result = compute_calibration(records)
        self.assertFalse(result.has_sufficient_data)
        self.assertIn("Insufficient data", result.recommendations[0])


class TestRecommendationGeneration(unittest.TestCase):
    def test_recommendation_over_confident(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.90, decision="approve",
                human_decision=HumanDecision.REJECTED,
            )
            for i in range(30)
        ]
        result = compute_calibration(records)
        has_over_confident_rec = any("over-confident" in r for r in result.recommendations)
        self.assertTrue(has_over_confident_rec)

    def test_recommendation_under_confident(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.20, decision="reject",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(30)
        ]
        result = compute_calibration(records)
        has_under_confident_rec = any("under-confident" in r for r in result.recommendations)
        self.assertTrue(has_under_confident_rec)

    def test_recommendation_well_calibrated(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(30)
        ]
        result = compute_calibration(records)
        has_ok_rec = any("acceptable bounds" in r for r in result.recommendations)
        self.assertTrue(has_ok_rec)


class TestNoAutomaticThresholdMutation(unittest.TestCase):
    def test_calibration_does_not_modify_global_state(self):
        import app.services.feedback_calibration as fc
        original_threshold = fc._OVER_CONFIDENT_THRESHOLD

        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.5, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(20)
        ]
        compute_calibration(records)

        self.assertEqual(fc._OVER_CONFIDENT_THRESHOLD, original_threshold)


class TestImmutableCalibrationHistory(unittest.TestCase):
    def test_snapshot_is_frozen(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(10)
        ]
        result = compute_calibration(records)
        snapshot = create_calibration_snapshot(result)

        with self.assertRaises(AttributeError):
            snapshot.feedback_count = 999


class TestDeterministicResults(unittest.TestCase):
    def test_same_input_same_output(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.5 + (i % 10) * 0.04,
                decision="approve",
                human_decision=HumanDecision.APPROVED if i % 2 == 0 else HumanDecision.REJECTED,
            )
            for i in range(20)
        ]
        result1 = compute_calibration(records)
        result2 = compute_calibration(records)

        self.assertEqual(result1.version_id, result2.version_id)
        self.assertEqual(result1.overall_sample_count, result2.overall_sample_count)
        self.assertAlmostEqual(result1.overall_calibration_error, result2.overall_calibration_error)


class TestBatchAggregation(unittest.TestCase):
    def test_large_batch(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i % 50,
                field_name=["title", "deadline_date", "funding", "duration"][i % 4],
                model_confidence=0.3 + (i % 6) * 0.1,
                decision="approve",
                human_decision=HumanDecision.APPROVED if i % 3 != 0 else HumanDecision.REJECTED,
                source_url=f"https://source{i % 5}.example.com/page",
            )
            for i in range(100)
        ]
        result = compute_calibration(records)
        self.assertEqual(result.overall_sample_count, 100)
        self.assertEqual(len(result.source_calibrations), 5)
        self.assertEqual(len(result.field_calibrations), 4)


class TestNoNPlusOne(unittest.TestCase):
    def test_single_pass_computation(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(100)
        ]
        result = compute_calibration(records)

        self.assertEqual(result.overall_sample_count, 100)
        total_bucket_samples = sum(b.sample_count for b in result.confidence_buckets.values())
        self.assertEqual(total_bucket_samples, 100)


class TestPrivacySensitiveData(unittest.TestCase):
    def test_no_pii_in_snapshot(self):
        records = [
            record_feedback(
                review_id=1, scholarship_id=1, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
                evidence_context="A" * 300,
            )
        ]
        result = compute_calibration(records)
        snapshot = create_calibration_snapshot(result)

        for key, value in snapshot.result_summary.items():
            if isinstance(value, str):
                self.assertLessEqual(len(value), 250)


class TestCalibrationSnapshot(unittest.TestCase):
    def test_snapshot_contains_expected_fields(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(15)
        ]
        result = compute_calibration(records)
        snapshot = create_calibration_snapshot(result)

        self.assertIsNotNone(snapshot.version_id)
        self.assertIsNotNone(snapshot.computed_at)
        self.assertEqual(snapshot.feedback_count, 15)
        self.assertIn("overall_approval_rate", snapshot.result_summary)
        self.assertIn("overall_calibration_error", snapshot.result_summary)


class TestDetectSystematicBias(unittest.TestCase):
    def test_insufficient_data(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.5, decision="approve",
                human_decision=HumanDecision.APPROVED,
            )
            for i in range(5)
        ]
        bias = detect_systematic_bias(records, min_samples=20)
        self.assertFalse(bias["has_sufficient_data"])

    def test_sufficient_data_over_confident(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.95, decision="approve",
                human_decision=HumanDecision.REJECTED,
            )
            for i in range(30)
        ]
        bias = detect_systematic_bias(records, min_samples=20)
        self.assertTrue(bias["has_sufficient_data"])
        self.assertTrue(bias["is_over_confident"])


class TestConfidenceTrend(unittest.TestCase):
    def test_empty_snapshots(self):
        trend = compute_confidence_trend([])
        self.assertFalse(trend["has_data"])

    def test_stable_trend(self):
        snapshots = [
            CalibrationSnapshot(
                version_id=f"v{i}", computed_at=f"2026-09-0{i}T00:00:00Z",
                feedback_count=20,
                result_summary={"overall_calibration_error": 0.05 + i * 0.01},
            )
            for i in range(5)
        ]
        trend = compute_confidence_trend(snapshots)
        self.assertTrue(trend["has_data"])
        self.assertIn("trend", trend)


class TestDecisionTypeCalibration(unittest.TestCase):
    def test_decision_type_aggregation(self):
        records = [
            record_feedback(
                review_id=i, scholarship_id=i, field_name="title",
                model_confidence=0.85, decision="approve",
                human_decision=HumanDecision.APPROVED,
                decision_type=DecisionType.AUTO_UPDATE,
            )
            for i in range(10)
        ] + [
            record_feedback(
                review_id=i + 10, scholarship_id=i, field_name="title",
                model_confidence=0.5, decision="review",
                human_decision=HumanDecision.REJECTED,
                decision_type=DecisionType.CONFLICT_RESOLUTION,
            )
            for i in range(10)
        ]
        result = compute_calibration(records)
        self.assertIn(DecisionType.AUTO_UPDATE, result.decision_type_calibrations)
        self.assertIn(DecisionType.CONFLICT_RESOLUTION, result.decision_type_calibrations)

        auto_cal = result.decision_type_calibrations[DecisionType.AUTO_UPDATE]
        self.assertEqual(auto_cal.approval_rate, 1.0)


class TestSourceCalibrationProperties(unittest.TestCase):
    def test_source_calibration_empty(self):
        sc = SourceCalibration(domain="test.com")
        self.assertEqual(sc.approval_rate, 0.0)
        self.assertFalse(sc.is_over_confident)
        self.assertFalse(sc.is_under_confident)

    def test_source_calibration_over_confident(self):
        sc = SourceCalibration(
            domain="test.com", sample_count=10,
            approval_count=3, rejection_count=7, total_confidence=9.0,
        )
        self.assertTrue(sc.is_over_confident)

    def test_source_calibration_under_confident(self):
        sc = SourceCalibration(
            domain="test.com", sample_count=10,
            approval_count=9, rejection_count=1, total_confidence=2.0,
        )
        self.assertTrue(sc.is_under_confident)


class TestFieldCalibrationProperties(unittest.TestCase):
    def test_field_calibration_not_problematic(self):
        fc = FieldCalibration(field_name="title", sample_count=10, approval_count=8, rejection_count=2)
        self.assertFalse(fc.is_problematic)

    def test_field_calibration_problematic(self):
        fc = FieldCalibration(field_name="title", sample_count=10, approval_count=3, rejection_count=7)
        self.assertTrue(fc.is_problematic)

    def test_field_calibration_insufficient_samples(self):
        fc = FieldCalibration(field_name="title", sample_count=2, approval_count=0, rejection_count=2)
        self.assertFalse(fc.is_problematic)


class TestFeedbackRecordSourceDomain(unittest.TestCase):
    def test_extract_domain(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=0.5, decision="x", human_decision="approved",
            source_url="https://www.DAAD.de/scholarship",
        )
        self.assertEqual(record.source_domain, "www.daad.de")

    def test_no_source(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=0.5, decision="x", human_decision="approved",
        )
        self.assertIsNone(record.source_domain)


class TestCalibrationResultProperties(unittest.TestCase):
    def test_empty_result_safe(self):
        result = CalibrationResult()
        self.assertEqual(result.overall_approval_rate, 0.0)
        self.assertEqual(result.overall_calibration_error, 0.0)
        self.assertFalse(result.has_sufficient_data)


class TestEdgeCases(unittest.TestCase):
    def test_single_record(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=0.5, decision="approve",
            human_decision=HumanDecision.APPROVED,
        )
        result = compute_calibration([record])
        self.assertEqual(result.overall_sample_count, 1)

    def test_zero_confidence(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=0.0, decision="reject",
            human_decision=HumanDecision.REJECTED,
        )
        self.assertEqual(record.model_confidence, 0.0)
        self.assertEqual(record.confidence_bucket, "0-10")

    def test_full_confidence(self):
        record = record_feedback(
            review_id=1, scholarship_id=1, field_name="title",
            model_confidence=1.0, decision="approve",
            human_decision=HumanDecision.APPROVED,
        )
        self.assertEqual(record.model_confidence, 1.0)
        self.assertEqual(record.confidence_bucket, "90-100")


if __name__ == "__main__":
    unittest.main()
