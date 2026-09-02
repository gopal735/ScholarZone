"""Human feedback + confidence calibration loop.

Uses APPROVED/REJECTED human review outcomes to measure and calibrate
verification confidence and decision quality over time.

This module is:
- Deterministic: same inputs always produce same outputs
- Read-only: does not modify the database
- Safe: NEVER auto-rewrites production thresholds
- Explainable: every recommendation includes reason codes
- Immutable: calibration history is append-only

Pipeline:
    Human Review -> Feedback Record -> Calibration Statistics ->
    Recommendation -> Explicit Human Approval -> Versioned Threshold Change (optional)

Calibration MUST NOT automatically rewrite production safety rules.

Human feedback may:
- produce calibration statistics
- flag thresholds for review
- recommend adjustments

Human feedback must NOT:
- bypass safety gates
- auto-approve conflicts
- directly modify Scholarship
- silently change thresholds
- retrain an uncontrolled model
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Sequence
from urllib.parse import urlparse

from .verification_confidence import ConfidenceLevel


# Confidence level string to numeric value mapping
_CONFIDENCE_VALUE: dict[str, float] = {
    "high": 0.85,
    "medium": 0.50,
    "low": 0.15,
    "conflict": 0.0,
}

# Confidence bucket boundaries (percentage)
_BUCKET_RANGES: list[tuple[int, int]] = [
    (0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
    (50, 60), (60, 70), (70, 80), (80, 90), (90, 100),
]

# Minimum samples before making recommendations
_MIN_SAMPLES_BUCKET = 10
_MIN_SAMPLES_SOURCE = 5
_MIN_SAMPLES_FIELD = 5

# Calibration error thresholds for generating recommendations
_OVER_CONFIDENT_THRESHOLD = 0.15
_UNDER_CONFIDENT_THRESHOLD = -0.15


class HumanDecision(str, Enum):
    """Human reviewer decision values."""
    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionType(str, Enum):
    """Types of decisions that can be calibrated."""
    AUTO_UPDATE = "auto_update"
    HUMAN_REVIEW = "human_review"
    CONFLICT_RESOLUTION = "conflict_resolution"


class ThresholdAction(str, Enum):
    """Recommended action for a threshold."""
    RAISE = "raise"
    LOWER = "lower"
    MAINTAIN = "maintain"
    INSUFFICIENT_DATA = "insufficient_data"
    REVIEW_RECOMMENDED = "review_recommended"


@dataclass(frozen=True)
class FeedbackRecord:
    """Immutable record of human feedback on a verification decision.

    Captures the relationship between model/system confidence and
    actual human decision for calibration analysis.
    """

    review_id: int
    scholarship_id: int
    field_name: str
    model_confidence: float
    decision: str
    human_decision: str
    reason: str | None = None
    source_url: str | None = None
    evidence_context: str | None = None
    decision_type: str = DecisionType.HUMAN_REVIEW
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            'model_confidence',
            max(0.0, min(1.0, float(self.model_confidence))),
        )

    @property
    def source_domain(self) -> str | None:
        """Extract domain from source_url for source-level calibration."""
        if not self.source_url:
            return None
        try:
            parsed = urlparse(self.source_url.strip())
            return parsed.netloc.lower() if parsed.netloc else None
        except Exception:
            return None

    @property
    def was_correct(self) -> bool:
        """Whether the model decision matched the human decision."""
        return self.decision.lower() == self.human_decision.lower()

    @property
    def was_approved(self) -> bool:
        return self.human_decision == HumanDecision.APPROVED

    @property
    def was_rejected(self) -> bool:
        return self.human_decision == HumanDecision.REJECTED

    @property
    def confidence_bucket(self) -> str:
        return _confidence_to_bucket(self.model_confidence)


@dataclass
class CalibrationBucket:
    """Statistics for a single confidence bucket."""

    bucket: str
    sample_count: int = 0
    approval_count: int = 0
    rejection_count: int = 0
    total_confidence: float = 0.0

    @property
    def approval_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.approval_count / self.sample_count

    @property
    def rejection_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.rejection_count / self.sample_count

    @property
    def avg_confidence(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.total_confidence / self.sample_count

    @property
    def predicted_confidence(self) -> float:
        return _bucket_midpoint(self.bucket) / 100.0

    @property
    def calibration_error(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.avg_confidence - self.approval_rate

    @property
    def reliability_score(self) -> float:
        return max(0.0, 1.0 - abs(self.calibration_error))

    @property
    def recommended_action(self) -> ThresholdAction:
        if self.sample_count < _MIN_SAMPLES_BUCKET:
            return ThresholdAction.INSUFFICIENT_DATA
        error = self.calibration_error
        if error > _OVER_CONFIDENT_THRESHOLD:
            return ThresholdAction.RAISE
        elif error < _UNDER_CONFIDENT_THRESHOLD:
            return ThresholdAction.LOWER
        else:
            return ThresholdAction.MAINTAIN


@dataclass
class SourceCalibration:
    """Calibration statistics for a specific source domain."""

    domain: str
    sample_count: int = 0
    approval_count: int = 0
    rejection_count: int = 0
    total_confidence: float = 0.0

    @property
    def approval_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.approval_count / self.sample_count

    @property
    def rejection_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.rejection_count / self.sample_count

    @property
    def avg_confidence(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.total_confidence / self.sample_count

    @property
    def calibration_error(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.avg_confidence - self.approval_rate

    @property
    def is_over_confident(self) -> bool:
        if self.sample_count < _MIN_SAMPLES_SOURCE:
            return False
        return self.calibration_error > _OVER_CONFIDENT_THRESHOLD

    @property
    def is_under_confident(self) -> bool:
        if self.sample_count < _MIN_SAMPLES_SOURCE:
            return False
        return self.calibration_error < _UNDER_CONFIDENT_THRESHOLD


@dataclass
class FieldCalibration:
    """Calibration statistics for a specific scholarship field."""

    field_name: str
    sample_count: int = 0
    approval_count: int = 0
    rejection_count: int = 0

    @property
    def approval_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.approval_count / self.sample_count

    @property
    def rejection_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.rejection_count / self.sample_count

    @property
    def is_problematic(self) -> bool:
        if self.sample_count < _MIN_SAMPLES_FIELD:
            return False
        return self.rejection_rate > 0.5


@dataclass
class DecisionTypeCalibration:
    """Calibration statistics for a decision type."""

    decision_type: str
    sample_count: int = 0
    approval_count: int = 0
    rejection_count: int = 0

    @property
    def approval_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.approval_count / self.sample_count

    @property
    def rejection_rate(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.rejection_count / self.sample_count


@dataclass
class CalibrationResult:
    """Complete calibration result with statistics and recommendations."""

    confidence_buckets: dict[str, CalibrationBucket] = field(default_factory=dict)
    source_calibrations: dict[str, SourceCalibration] = field(default_factory=dict)
    field_calibrations: dict[str, FieldCalibration] = field(default_factory=dict)
    decision_type_calibrations: dict[str, DecisionTypeCalibration] = field(default_factory=dict)

    overall_sample_count: int = 0
    overall_approval_count: int = 0
    overall_rejection_count: int = 0
    overall_confidence_sum: float = 0.0

    recommendations: list[str] = field(default_factory=list)
    version_id: str = ""
    computed_at: str = ""
    is_deterministic: bool = True

    @property
    def overall_approval_rate(self) -> float:
        if self.overall_sample_count == 0:
            return 0.0
        return self.overall_approval_count / self.overall_sample_count

    @property
    def overall_rejection_rate(self) -> float:
        if self.overall_sample_count == 0:
            return 0.0
        return self.overall_rejection_count / self.overall_sample_count

    @property
    def overall_avg_confidence(self) -> float:
        if self.overall_sample_count == 0:
            return 0.0
        return self.overall_confidence_sum / self.overall_sample_count

    @property
    def overall_calibration_error(self) -> float:
        if self.overall_sample_count == 0:
            return 0.0
        return self.overall_avg_confidence - self.overall_approval_rate

    @property
    def over_confident_sources(self) -> list[str]:
        return [d for d, s in sorted(self.source_calibrations.items()) if s.is_over_confident]

    @property
    def under_confident_sources(self) -> list[str]:
        return [d for d, s in sorted(self.source_calibrations.items()) if s.is_under_confident]

    @property
    def problematic_fields(self) -> list[str]:
        return [f for f, c in sorted(self.field_calibrations.items()) if c.is_problematic]

    @property
    def has_sufficient_data(self) -> bool:
        return self.overall_sample_count >= _MIN_SAMPLES_BUCKET


@dataclass(frozen=True)
class CalibrationSnapshot:
    """Immutable historical calibration version for audit trail."""

    version_id: str
    computed_at: str
    feedback_count: int
    result_summary: dict[str, Any]


def _confidence_to_bucket(confidence: float) -> str:
    """Convert a 0.0-1.0 confidence value to its percentage bucket string."""
    pct = int(confidence * 100)
    # Handle the edge case where confidence is exactly 1.0
    if pct == 100:
        return "90-100"
    for low, high in _BUCKET_RANGES:
        if low <= pct < high:
            return f"{low}-{high}"
    return "90-100"


def _bucket_midpoint(bucket: str) -> float:
    """Get the midpoint value of a bucket range string."""
    parts = bucket.split("-")
    if len(parts) == 2:
        try:
            low = float(parts[0])
            high = float(parts[1])
            return (low + high) / 2
        except ValueError:
            return 50.0
    return 50.0


def _compute_version_id(records: Sequence[FeedbackRecord], computed_at: str) -> str:
    """Compute a deterministic version ID from feedback records only."""
    record_ids = sorted(str(r.review_id) for r in records)
    data = json.dumps({"ids": record_ids}, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _sanitize_value(value: Any) -> Any:
    """Remove potentially sensitive data from values."""
    if isinstance(value, str) and len(value) > 200:
        return value[:200] + "...[truncated]"
    return value


def record_feedback(
    review_id: int,
    scholarship_id: int,
    field_name: str,
    model_confidence: float | str,
    decision: str,
    human_decision: str,
    *,
    reason: str | None = None,
    source_url: str | None = None,
    evidence_context: str | None = None,
    decision_type: str = DecisionType.HUMAN_REVIEW,
    created_at: datetime | None = None,
) -> FeedbackRecord:
    """Create a feedback record from a human review outcome.

    Factory function that normalizes confidence values and creates
    an immutable FeedbackRecord.
    """
    if isinstance(model_confidence, str):
        model_confidence = _CONFIDENCE_VALUE.get(model_confidence.lower(), 0.5)

    return FeedbackRecord(
        review_id=review_id,
        scholarship_id=scholarship_id,
        field_name=field_name,
        model_confidence=float(model_confidence),
        decision=decision,
        human_decision=human_decision,
        reason=reason,
        source_url=source_url,
        evidence_context=evidence_context,
        decision_type=decision_type,
        created_at=created_at or datetime.now(timezone.utc),
    )


def compute_calibration(records: Sequence[FeedbackRecord]) -> CalibrationResult:
    """Compute calibration statistics from feedback records.

    Aggregates feedback by confidence bucket, source domain, field,
    and decision type. Generates recommendations but does NOT modify
    any thresholds or production rules.
    """
    buckets: dict[str, CalibrationBucket] = {}
    for low, high in _BUCKET_RANGES:
        bucket_key = f"{low}-{high}"
        buckets[bucket_key] = CalibrationBucket(bucket=bucket_key)

    if not records:
        return CalibrationResult(
            confidence_buckets=buckets,
            version_id="empty",
            computed_at=datetime.now(timezone.utc).isoformat(),
        )

    source_calibs: dict[str, SourceCalibration] = {}
    field_calibs: dict[str, FieldCalibration] = {}
    decision_calibs: dict[str, DecisionTypeCalibration] = {}

    computed_at = datetime.now(timezone.utc).isoformat()
    version_id = _compute_version_id(records, computed_at)

    total_approvals = 0
    total_rejections = 0
    total_confidence = 0.0

    for record in records:
        bucket_key = record.confidence_bucket
        bucket = buckets[bucket_key]
        bucket.sample_count += 1
        bucket.total_confidence += record.model_confidence

        if record.was_approved:
            bucket.approval_count += 1
            total_approvals += 1
        else:
            bucket.rejection_count += 1
            total_rejections += 1

        total_confidence += record.model_confidence

        domain = record.source_domain
        if domain:
            if domain not in source_calibs:
                source_calibs[domain] = SourceCalibration(domain=domain)
            sc = source_calibs[domain]
            sc.sample_count += 1
            sc.total_confidence += record.model_confidence
            if record.was_approved:
                sc.approval_count += 1
            else:
                sc.rejection_count += 1

        if record.field_name not in field_calibs:
            field_calibs[record.field_name] = FieldCalibration(field_name=record.field_name)
        fc = field_calibs[record.field_name]
        fc.sample_count += 1
        if record.was_approved:
            fc.approval_count += 1
        else:
            fc.rejection_count += 1

        dt = record.decision_type
        if dt not in decision_calibs:
            decision_calibs[dt] = DecisionTypeCalibration(decision_type=dt)
        dc = decision_calibs[dt]
        dc.sample_count += 1
        if record.was_approved:
            dc.approval_count += 1
        else:
            dc.rejection_count += 1

    result = CalibrationResult(
        confidence_buckets=buckets,
        source_calibrations=source_calibs,
        field_calibrations=field_calibs,
        decision_type_calibrations=decision_calibs,
        overall_sample_count=len(records),
        overall_approval_count=total_approvals,
        overall_rejection_count=total_rejections,
        overall_confidence_sum=total_confidence,
        version_id=version_id,
        computed_at=computed_at,
    )

    result.recommendations = _generate_recommendations(result)

    return result


def _generate_recommendations(result: CalibrationResult) -> list[str]:
    """Generate actionable recommendations from calibration results.

    Recommendations are advisory only. They do NOT modify thresholds.
    """
    recommendations: list[str] = []

    if not result.has_sufficient_data:
        recommendations.append(
            f"Insufficient data for reliable calibration. "
            f"Need at least {_MIN_SAMPLES_BUCKET} samples, got {result.overall_sample_count}."
        )
        return recommendations

    error = result.overall_calibration_error
    if error > _OVER_CONFIDENT_THRESHOLD:
        recommendations.append(
            f"System is over-confident by {error:.1%}. "
            f"Consider raising confidence thresholds for auto-update."
        )
    elif error < _UNDER_CONFIDENT_THRESHOLD:
        recommendations.append(
            f"System is under-confident by {abs(error):.1%}. "
            f"Consider lowering confidence thresholds for auto-update."
        )

    for domain, sc in sorted(result.source_calibrations.items()):
        if sc.is_over_confident:
            recommendations.append(
                f"Source '{domain}' is over-confident "
                f"(avg_confidence={sc.avg_confidence:.2f}, "
                f"approval_rate={sc.approval_rate:.1%}). "
                f"Consider lowering trust for this source."
            )
        elif sc.is_under_confident:
            recommendations.append(
                f"Source '{domain}' is under-confident "
                f"(avg_confidence={sc.avg_confidence:.2f}, "
                f"approval_rate={sc.approval_rate:.1%}). "
                f"Consider raising trust for this source."
            )

    for field_name, fc in sorted(result.field_calibrations.items()):
        if fc.is_problematic:
            recommendations.append(
                f"Field '{field_name}' has high rejection rate ({fc.rejection_rate:.1%}). "
                f"Review extraction logic or evidence requirements."
            )

    if not recommendations:
        recommendations.append("Calibration within acceptable bounds. No changes recommended.")

    return recommendations


def create_calibration_snapshot(result: CalibrationResult) -> CalibrationSnapshot:
    """Create immutable snapshot of calibration result for audit trail."""
    summary = {
        "overall_approval_rate": result.overall_approval_rate,
        "overall_calibration_error": result.overall_calibration_error,
        "over_confident_sources": result.over_confident_sources,
        "under_confident_sources": result.under_confident_sources,
        "problematic_fields": result.problematic_fields,
    }
    return CalibrationSnapshot(
        version_id=result.version_id,
        computed_at=result.computed_at,
        feedback_count=result.overall_sample_count,
        result_summary=summary,
    )


def detect_systematic_bias(
    records: Sequence[FeedbackRecord],
    *,
    min_samples: int = 20,
) -> dict[str, Any]:
    """Detect systematic over/under-confidence patterns.

    Returns a bias report. Does not modify any state.
    """
    result = compute_calibration(records)

    if result.overall_sample_count < min_samples:
        return {
            "has_sufficient_data": False,
            "min_samples_required": min_samples,
            "actual_samples": result.overall_sample_count,
            "overall_error": result.overall_calibration_error,
        }

    return {
        "has_sufficient_data": True,
        "overall_error": result.overall_calibration_error,
        "is_over_confident": result.overall_calibration_error > _OVER_CONFIDENT_THRESHOLD,
        "is_under_confident": result.overall_calibration_error < _UNDER_CONFIDENT_THRESHOLD,
        "well_calibrated": abs(result.overall_calibration_error) <= _OVER_CONFIDENT_THRESHOLD,
        "over_confident_sources": result.over_confident_sources,
        "under_confident_sources": result.under_confident_sources,
        "problematic_fields": result.problematic_fields,
    }


def compute_confidence_trend(
    snapshots: Sequence[CalibrationSnapshot],
) -> dict[str, Any]:
    """Analyze calibration trends over multiple snapshots.

    Takes a sequence of historical snapshots and computes trend.
    """
    if not snapshots:
        return {"has_data": False, "trend": "no_data"}

    errors = [s.result_summary.get("overall_calibration_error", 0.0) for s in snapshots]

    if len(errors) < 2:
        return {
            "has_data": True,
            "trend": "stable",
            "latest_error": errors[0],
            "snapshot_count": 1,
        }

    first_half = errors[:len(errors) // 2]
    second_half = errors[len(errors) // 2:]

    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)

    diff = avg_second - avg_first
    if abs(diff) < 0.05:
        trend = "stable"
    elif diff > 0:
        trend = "worsening_over_confidence"
    else:
        trend = "improving"

    return {
        "has_data": True,
        "trend": trend,
        "latest_error": errors[-1],
        "snapshot_count": len(snapshots),
        "error_delta": diff,
    }
