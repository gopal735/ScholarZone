"""Anomaly detection and intelligent change validation engine.

Detects suspicious but technically possible scholarship changes before
they reach AUTO_UPDATE. Uses deterministic signals from existing systems:
- temporal snapshots/history
- change impact + staleness
- source health
- telemetry
- lifecycle
- evidence arbitration
- confidence
- knowledge graph

Design principles:
- Deterministic: same inputs always produce same outputs
- Explainable: every anomaly includes reason codes and explanation
- Non-destructive: never mutates source data
- Safety-first: HIGH/CRITICAL anomalies escalate to review
- No ML/LLM: rule-based, transparent logic
- No network calls: all data from existing persisted state
- No duplicate history: does not write new history entries
- Batch-friendly: process multiple scholarships in one call
- Low-latency: single-pass detection per scholarship

Severity levels:
- LOW: minor deviation, logged but does not block
- MEDIUM: notable deviation, flagged for monitoring
- HIGH: significant anomaly, escalates to review
- CRITICAL: severe anomaly, blocks auto-update
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any

from .change_impact_staleness import FIELD_CRITICALITY, compute_change_impact
from .evidence_arbitration import ArbitrationDecision, ArbitrationResult
from .verification_confidence import ConfidenceLevel, VerificationState


class AnomalySeverity(str, Enum):
    """Severity levels for detected anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyReasonCode(str, Enum):
    """Reason codes explaining detected anomalies."""
    # Deadline anomalies
    LARGE_DEADLINE_SHIFT = "large_deadline_shift"
    DEADLINE_MOVES_BACKWARD = "deadline_moves_backward"
    DEADLINE_FAR_FUTURE = "deadline_far_future"

    # Funding anomalies
    FUNDING_REDUCTION = "funding_reduction"
    FUNDING_TO_NONE = "funding_to_none"
    FUNDING_SUDDEN_FULL = "funding_sudden_full"

    # Duration anomalies
    DURATION_CHANGE_LARGE = "duration_change_large"
    DURATION_ZERO = "duration_zero"
    DURATION_EXTENDED_LARGE = "duration_extended_large"

    # Multi-field anomalies
    MULTI_CRITICAL_FIELD_CHANGE = "multi_critical_field_change"
    MULTI_HIGH_FIELD_CHANGE = "multi_high_field_change"

    # Historical pattern anomalies
    CHANGE_FREQUENCY_SPIKE = "change_frequency_spike"
    FIELD_CHURN_ANOMALY = "field_churn_anomaly"
    VALUE_OSCILLATION = "value_oscillation"

    # Source anomalies
    SOURCE_DISAGREEMENT = "source_disagreement"
    CONSENSUS_DROP = "consensus_drop"
    SOURCE_HEALTH_DEGRADATION = "source_health_degradation"

    # Confidence anomalies
    CONFIDENCE_DOWNGRADE = "confidence_downgrade"
    VERIFICATION_STATE_REGRESSION = "verification_state_regression"

    # Lifecycle anomalies
    LIFECYCLE_MISMATCH = "lifecycle_mismatch"
    INVALID_TRANSITION = "invalid_transition"

    # Eligibility anomalies
    ELIGIBILITY_RESTRICTED = "eligibility_restricted"
    ELIGIBILITY_BROADENED = "eligibility_broadened"

    # Normal
    NORMAL = "normal"


@dataclass(frozen=True)
class HistoricalComparison:
    """Comparison of current value against historical patterns."""
    field_name: str
    current_value: str | None
    previous_value: str | None
    historical_median: float | None = None
    historical_mean: float | None = None
    historical_std: float | None = None
    change_count_30d: int = 0
    change_count_90d: int = 0
    days_since_last_change: int | None = None
    expected_range: tuple[float, float] | None = None
    is_within_expected: bool = True


@dataclass
class AnomalyResult:
    """Result of anomaly detection for a single field or scholarship."""
    anomaly_detected: bool
    severity: AnomalySeverity
    anomaly_score: float
    reason_codes: list[str] = field(default_factory=list)
    affected_fields: list[str] = field(default_factory=list)
    historical_comparison: dict[str, HistoricalComparison] = field(default_factory=dict)
    expected_range: dict[str, tuple[float, float] | None] = field(default_factory=dict)
    explanation: str = ""
    field_name: str | None = None
    current_value: str | None = None
    proposed_value: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def requires_review(self) -> bool:
        """Check if this anomaly requires human review."""
        return self.severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)

    def should_block(self) -> bool:
        """Check if this anomaly should block auto-update."""
        return self.severity == AnomalySeverity.CRITICAL


# Thresholds for anomaly detection
_DEADLINE_SHIFT_MEDIUM_DAYS = 30
_DEADLINE_SHIFT_HIGH_DAYS = 60
_DEADLINE_SHIFT_CRITICAL_DAYS = 90
_DEADLINE_FAR_FUTURE_DAYS = 365 * 3

_DURATION_CHANGE_MEDIUM_PCT = 0.30
_DURATION_CHANGE_HIGH_PCT = 0.60
_DURATION_CHANGE_CRITICAL_PCT = 1.00

_MULTI_CRITICAL_FIELD_THRESHOLD = 3
_MULTI_HIGH_FIELD_THRESHOLD = 5

_CHANGE_FREQUENCY_MULTIPLIER = 3.0
_FIELD_CHURN_MULTIPLIER = 2.5

_CONFIDENCE_DOWNGRADE_SEVERITY = {
    (ConfidenceLevel.HIGH, ConfidenceLevel.LOW): AnomalySeverity.HIGH,
    (ConfidenceLevel.HIGH, ConfidenceLevel.CONFLICT): AnomalySeverity.CRITICAL,
    (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW): AnomalySeverity.MEDIUM,
    (ConfidenceLevel.MEDIUM, ConfidenceLevel.CONFLICT): AnomalySeverity.HIGH,
}


def _max_severity(a: AnomalySeverity, b: AnomalySeverity) -> AnomalySeverity:
    """Return the higher severity."""
    order = {
        AnomalySeverity.CRITICAL: 3,
        AnomalySeverity.HIGH: 2,
        AnomalySeverity.MEDIUM: 1,
        AnomalySeverity.LOW: 0,
    }
    return a if order.get(a, 0) >= order.get(b, 0) else b


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_between(d1: date | datetime | None, d2: date | datetime | None) -> int | None:
    """Calculate days between two dates (always positive)."""
    if d1 is None or d2 is None:
        return None
    if isinstance(d1, datetime):
        d1 = d1.date() if hasattr(d1, 'date') else d1
    if isinstance(d2, datetime):
        d2 = d2.date() if hasattr(d2, 'date') else d2
    try:
        return abs((d2 - d1).days)
    except (TypeError, AttributeError):
        return None


def _days_shift(old: date | datetime | None, new: date | datetime | None) -> int | None:
    """Calculate signed days shift from old to new (positive = forward, negative = backward)."""
    if old is None or new is None:
        return None
    if isinstance(old, datetime):
        old = old.date() if hasattr(old, 'date') else old
    if isinstance(new, datetime):
        new = new.date() if hasattr(new, 'date') else new
    try:
        return (new - old).days
    except (TypeError, AttributeError):
        return None


def _safe_numeric(value: str | None) -> float | None:
    """Safely extract numeric value from string."""
    if value is None:
        return None
    try:
        cleaned = ''.join(c for c in str(value) if c.isdigit() or c == '.')
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def _anomaly_id(field_name: str, scholarship_id: int | str | None = None) -> str:
    """Generate deterministic anomaly detection ID."""
    content = f"{field_name}:{scholarship_id}:{_now().strftime('%Y%m%d%H%M%S')}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _normalize_funding(value: str | None) -> str | None:
    """Normalize funding value for comparison."""
    if value is None:
        return None
    v = str(value).lower().strip()
    if v in ("full", "full scholarship", "full funding", "fully funded", "100%"):
        return "full"
    if v in ("partial", "partial scholarship", "partial funding"):
        return "partial"
    if v in ("none", "no funding", "unfunded", "self-funded", "n/a", ""):
        return "none"
    return v


def detect_deadline_anomaly(
    field_name: str,
    old_value: str | date | datetime | None,
    new_value: str | date | datetime | None,
    historical_dates: list[date | datetime] | None = None,
) -> AnomalyResult:
    """Detect anomalies in deadline changes."""
    old_date = old_value if isinstance(old_value, (date, datetime)) else None
    new_date = new_value if isinstance(new_value, (date, datetime)) else None

    if old_date is None or new_date is None:
        return AnomalyResult(
            anomaly_detected=False,
            severity=AnomalySeverity.LOW,
            anomaly_score=0.0,
            field_name=field_name,
            current_value=str(old_value) if old_value else None,
            proposed_value=str(new_value) if new_value else None,
        )

    days_shift = _days_between(old_date, new_date)
    signed_shift = _days_shift(old_date, new_date)
    if days_shift is None:
        return AnomalyResult(
            anomaly_detected=False,
            severity=AnomalySeverity.LOW,
            anomaly_score=0.0,
            field_name=field_name,
            current_value=str(old_value),
            proposed_value=str(new_value),
        )

    # Check deadline moving backward
    if isinstance(old_date, datetime):
        old_cmp = old_date.date() if hasattr(old_date, 'date') else old_date
    else:
        old_cmp = old_date
    if isinstance(new_date, datetime):
        new_cmp = new_date.date() if hasattr(new_date, 'date') else new_date
    else:
        new_cmp = new_date

    moves_backward = new_cmp < old_cmp

    # Check far future
    days_from_now = _days_between(_now().date(), new_cmp)
    is_far_future = days_from_now is not None and days_from_now > _DEADLINE_FAR_FUTURE_DAYS

    reason_codes = []
    severity = AnomalySeverity.LOW
    score = 0.0

    if moves_backward:
        reason_codes.append(AnomalyReasonCode.DEADLINE_MOVES_BACKWARD)
        severity = AnomalySeverity.HIGH
        score = max(score, 0.7)

    if days_shift >= _DEADLINE_SHIFT_CRITICAL_DAYS:
        reason_codes.append(AnomalyReasonCode.LARGE_DEADLINE_SHIFT)
        severity = AnomalySeverity.CRITICAL
        score = 1.0
    elif days_shift >= _DEADLINE_SHIFT_HIGH_DAYS:
        reason_codes.append(AnomalyReasonCode.LARGE_DEADLINE_SHIFT)
        severity = _max_severity(severity, AnomalySeverity.HIGH)
        score = max(score, 0.7)
    elif days_shift >= _DEADLINE_SHIFT_MEDIUM_DAYS:
        reason_codes.append(AnomalyReasonCode.LARGE_DEADLINE_SHIFT)
        severity = _max_severity(severity, AnomalySeverity.MEDIUM)
        score = max(score, 0.4)

    if is_far_future:
        reason_codes.append(AnomalyReasonCode.DEADLINE_FAR_FUTURE)
        severity = _max_severity(severity, AnomalySeverity.HIGH)
        score = max(score, 0.8)

    # Historical comparison
    hist_comparison = None
    expected_range = None
    if historical_dates and len(historical_dates) >= 2:
        shifts = []
        for i in range(1, len(historical_dates)):
            d = _days_between(historical_dates[i-1], historical_dates[i])
            if d is not None:
                shifts.append(d)
        if shifts:
            median_shift = sorted(shifts)[len(shifts) // 2]
            expected_range = (0.0, median_shift * 3)
            is_within = days_shift <= median_shift * 3
            hist_comparison = HistoricalComparison(
                field_name=field_name,
                current_value=str(new_value),
                previous_value=str(old_value),
                historical_median=median_shift,
                expected_range=expected_range,
                is_within_expected=is_within,
            )
            if not is_within and severity == AnomalySeverity.LOW:
                severity = AnomalySeverity.MEDIUM
                score = max(score, 0.4)

    anomaly_detected = len(reason_codes) > 0

    explanation_parts = []
    if AnomalyReasonCode.DEADLINE_MOVES_BACKWARD in reason_codes:
        explanation_parts.append("Deadline moved backward (earlier)")
    if AnomalyReasonCode.LARGE_DEADLINE_SHIFT in reason_codes:
        explanation_parts.append(f"Deadline shifted by {days_shift} days")
    if AnomalyReasonCode.DEADLINE_FAR_FUTURE in reason_codes:
        explanation_parts.append(f"Deadline is {days_from_now} days in the future")

    return AnomalyResult(
        anomaly_detected=anomaly_detected,
        severity=severity,
        anomaly_score=score,
        reason_codes=[rc.value for rc in reason_codes],
        affected_fields=[field_name] if anomaly_detected else [],
        historical_comparison={field_name: hist_comparison} if hist_comparison else {},
        expected_range={field_name: expected_range} if expected_range else {},
        explanation="; ".join(explanation_parts) if explanation_parts else "Normal deadline change",
        field_name=field_name,
        current_value=str(old_value),
        proposed_value=str(new_value),
    )


def detect_funding_anomaly(
    field_name: str,
    old_value: str | None,
    new_value: str | None,
) -> AnomalyResult:
    """Detect anomalies in funding changes."""
    old_norm = _normalize_funding(old_value)
    new_norm = _normalize_funding(new_value)

    if old_norm is None or new_norm is None or old_norm == new_norm:
        return AnomalyResult(
            anomaly_detected=False,
            severity=AnomalySeverity.LOW,
            anomaly_score=0.0,
            field_name=field_name,
            current_value=old_value,
            proposed_value=new_value,
        )

    reason_codes = []
    severity = AnomalySeverity.LOW
    score = 0.0

    # Full to none
    if old_norm == "full" and new_norm == "none":
        reason_codes.append(AnomalyReasonCode.FUNDING_TO_NONE)
        severity = AnomalySeverity.CRITICAL
        score = 1.0
    # Full to partial
    elif old_norm == "full" and new_norm == "partial":
        reason_codes.append(AnomalyReasonCode.FUNDING_REDUCTION)
        severity = AnomalySeverity.HIGH
        score = 0.7
    # Partial to none
    elif old_norm == "partial" and new_norm == "none":
        reason_codes.append(AnomalyReasonCode.FUNDING_REDUCTION)
        severity = AnomalySeverity.HIGH
        score = 0.7
    # None to full (suspicious but positive)
    elif old_norm == "none" and new_norm == "full":
        reason_codes.append(AnomalyReasonCode.FUNDING_SUDDEN_FULL)
        severity = AnomalySeverity.MEDIUM
        score = 0.4
    # Partial to full
    elif old_norm == "partial" and new_norm == "full":
        reason_codes.append(AnomalyReasonCode.FUNDING_SUDDEN_FULL)
        severity = AnomalySeverity.LOW
        score = 0.2

    anomaly_detected = len(reason_codes) > 0

    explanation_parts = []
    if AnomalyReasonCode.FUNDING_TO_NONE in reason_codes:
        explanation_parts.append("Funding changed from full to none")
    elif AnomalyReasonCode.FUNDING_REDUCTION in reason_codes:
        explanation_parts.append(f"Funding reduced: {old_norm} -> {new_norm}")
    elif AnomalyReasonCode.FUNDING_SUDDEN_FULL in reason_codes:
        explanation_parts.append(f"Funding suddenly became full: {old_norm} -> {new_norm}")

    return AnomalyResult(
        anomaly_detected=anomaly_detected,
        severity=severity,
        anomaly_score=score,
        reason_codes=[rc.value for rc in reason_codes],
        affected_fields=[field_name] if anomaly_detected else [],
        explanation="; ".join(explanation_parts) if explanation_parts else "Normal funding change",
        field_name=field_name,
        current_value=old_value,
        proposed_value=new_value,
    )


def detect_duration_anomaly(
    field_name: str,
    old_value: str | None,
    new_value: str | None,
    unit_months: bool = True,
) -> AnomalyResult:
    """Detect anomalies in duration changes."""
    old_num = _safe_numeric(old_value)
    new_num = _safe_numeric(new_value)

    if old_num is None or new_num is None or old_num == 0:
        return AnomalyResult(
            anomaly_detected=False,
            severity=AnomalySeverity.LOW,
            anomaly_score=0.0,
            field_name=field_name,
            current_value=old_value,
            proposed_value=new_value,
        )

    change_ratio = abs(new_num - old_num) / old_num

    reason_codes = []
    severity = AnomalySeverity.LOW
    score = 0.0

    # Duration became zero
    if new_num == 0 and old_num > 0:
        reason_codes.append(AnomalyReasonCode.DURATION_ZERO)
        severity = AnomalySeverity.HIGH
        score = 0.8

    # Large extension
    elif new_num > old_num and change_ratio >= _DURATION_CHANGE_CRITICAL_PCT:
        reason_codes.append(AnomalyReasonCode.DURATION_EXTENDED_LARGE)
        severity = AnomalySeverity.CRITICAL
        score = 1.0
    elif new_num > old_num and change_ratio >= _DURATION_CHANGE_HIGH_PCT:
        reason_codes.append(AnomalyReasonCode.DURATION_EXTENDED_LARGE)
        severity = AnomalySeverity.HIGH
        score = 0.7

    # Large reduction or change
    elif change_ratio >= _DURATION_CHANGE_CRITICAL_PCT:
        reason_codes.append(AnomalyReasonCode.DURATION_CHANGE_LARGE)
        severity = AnomalySeverity.CRITICAL
        score = 1.0
    elif change_ratio >= _DURATION_CHANGE_HIGH_PCT:
        reason_codes.append(AnomalyReasonCode.DURATION_CHANGE_LARGE)
        severity = AnomalySeverity.HIGH
        score = 0.7
    elif change_ratio >= _DURATION_CHANGE_MEDIUM_PCT:
        reason_codes.append(AnomalyReasonCode.DURATION_CHANGE_LARGE)
        severity = AnomalySeverity.MEDIUM
        score = 0.4

    anomaly_detected = len(reason_codes) > 0

    unit_str = "months" if unit_months else "periods"
    explanation_parts = []
    if AnomalyReasonCode.DURATION_ZERO in reason_codes:
        explanation_parts.append(f"Duration became zero (was {old_num} {unit_str})")
    elif AnomalyReasonCode.DURATION_EXTENDED_LARGE in reason_codes:
        explanation_parts.append(f"Duration extended significantly: {old_num} -> {new_num} {unit_str}")
    elif AnomalyReasonCode.DURATION_CHANGE_LARGE in reason_codes:
        explanation_parts.append(f"Duration changed significantly: {old_num} -> {new_num} {unit_str}")

    return AnomalyResult(
        anomaly_detected=anomaly_detected,
        severity=severity,
        anomaly_score=score,
        reason_codes=[rc.value for rc in reason_codes],
        affected_fields=[field_name] if anomaly_detected else [],
        explanation="; ".join(explanation_parts) if explanation_parts else "Normal duration change",
        field_name=field_name,
        current_value=old_value,
        proposed_value=new_value,
    )


def detect_multi_field_anomaly(
    changed_fields: dict[str, tuple[str | None, str | None]],
) -> AnomalyResult | None:
    """Detect anomalies when multiple fields change simultaneously."""
    critical_changes = []
    high_changes = []
    medium_changes = []

    for field_name, (old_val, new_val) in changed_fields.items():
        if old_val == new_val:
            continue
        impact = compute_change_impact(field_name, old_val, new_val)
        if impact.impact_level == "critical":
            critical_changes.append(field_name)
        elif impact.impact_level == "high":
            high_changes.append(field_name)
        elif impact.impact_level == "medium":
            medium_changes.append(field_name)

    total_significant = len(critical_changes) + len(high_changes)

    if len(critical_changes) >= _MULTI_CRITICAL_FIELD_THRESHOLD:
        return AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.CRITICAL,
            anomaly_score=1.0,
            reason_codes=[AnomalyReasonCode.MULTI_CRITICAL_FIELD_CHANGE],
            affected_fields=critical_changes,
            explanation=f"{len(critical_changes)} critical fields changed simultaneously",
            metadata={"critical_count": len(critical_changes), "high_count": len(high_changes)},
        )
    elif total_significant >= _MULTI_HIGH_FIELD_THRESHOLD:
        return AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.HIGH,
            anomaly_score=0.7,
            reason_codes=[AnomalyReasonCode.MULTI_HIGH_FIELD_CHANGE],
            affected_fields=critical_changes + high_changes,
            explanation=f"{total_significant} high/critical fields changed simultaneously",
            metadata={"critical_count": len(critical_changes), "high_count": len(high_changes)},
        )
    elif len(critical_changes) >= 2 and len(high_changes) >= 2:
        return AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.HIGH,
            anomaly_score=0.6,
            reason_codes=[AnomalyReasonCode.MULTI_CRITICAL_FIELD_CHANGE],
            affected_fields=critical_changes + high_changes,
            explanation=f"Multiple critical and high-priority fields changed",
            metadata={"critical_count": len(critical_changes), "high_count": len(high_changes)},
        )

    return None


def detect_change_frequency_anomaly(
    field_name: str,
    change_count_30d: int,
    change_count_90d: int,
    historical_avg_changes_per_30d: float | None = None,
) -> AnomalyResult | None:
    """Detect anomalies in how frequently a field changes."""
    if historical_avg_changes_per_30d is not None and historical_avg_changes_per_30d > 0:
        if change_count_30d > historical_avg_changes_per_30d * _CHANGE_FREQUENCY_MULTIPLIER:
            return AnomalyResult(
                anomaly_detected=True,
                severity=AnomalySeverity.HIGH,
                anomaly_score=0.7,
                reason_codes=[AnomalyReasonCode.CHANGE_FREQUENCY_SPIKE],
                affected_fields=[field_name],
                explanation=(
                    f"Field changed {change_count_30d} times in 30 days "
                    f"(historical avg: {historical_avg_changes_per_30d:.1f})"
                ),
                field_name=field_name,
                metadata={
                    "change_count_30d": change_count_30d,
                    "historical_avg": historical_avg_changes_per_30d,
                },
            )

    # Heuristic: if changed more than 5 times in 30 days, suspicious
    if change_count_30d >= 5:
        return AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.MEDIUM,
            anomaly_score=0.4,
            reason_codes=[AnomalyReasonCode.CHANGE_FREQUENCY_SPIKE],
            affected_fields=[field_name],
            explanation=f"Field changed {change_count_30d} times in 30 days",
            field_name=field_name,
            metadata={"change_count_30d": change_count_30d},
        )

    return None


def detect_source_disagreement_anomaly(
    arbitration_result: ArbitrationResult,
) -> AnomalyResult | None:
    """Detect anomalies from evidence arbitration conflicts."""
    if arbitration_result.decision == ArbitrationDecision.CONFLICT:
        return AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.HIGH,
            anomaly_score=0.8,
            reason_codes=[AnomalyReasonCode.SOURCE_DISAGREEMENT],
            affected_fields=[arbitration_result.field_name],
            explanation=arbitration_result.reason_text,
            field_name=arbitration_result.field_name,
            current_value=arbitration_result.winning_value,
            proposed_value=None,
            metadata={
                "conflict_count": len(arbitration_result.conflicting_evidence),
                "decision": arbitration_result.decision.value,
            },
        )

    if arbitration_result.decision == ArbitrationDecision.INSUFFICIENT:
        return AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.MEDIUM,
            anomaly_score=0.4,
            reason_codes=[AnomalyReasonCode.SOURCE_DISAGREEMENT],
            affected_fields=[arbitration_result.field_name],
            explanation="Insufficient authoritative evidence for field",
            field_name=arbitration_result.field_name,
            metadata={"decision": arbitration_result.decision.value},
        )

    return None


def detect_source_health_anomaly(
    source_url: str | None,
    reliability_score: float,
    previous_reliability_score: float | None = None,
    health_status: str | None = None,
    previous_health_status: str | None = None,
) -> AnomalyResult | None:
    """Detect anomalies from source health degradation."""
    if source_url is None:
        return None

    reason_codes = []
    severity = AnomalySeverity.LOW
    score = 0.0

    # Health status degradation
    if previous_health_status and health_status:
        status_order = {"healthy": 0, "degraded": 1, "unhealthy": 2, "unknown": -1}
        prev_level = status_order.get(previous_health_status, -1)
        curr_level = status_order.get(health_status, -1)
        if curr_level > prev_level and curr_level >= 1:
            reason_codes.append(AnomalyReasonCode.SOURCE_HEALTH_DEGRADATION)
            if curr_level >= 2:
                severity = AnomalySeverity.HIGH
                score = 0.7
            else:
                severity = AnomalySeverity.MEDIUM
                score = 0.4

    # Reliability score drop
    if previous_reliability_score is not None:
        drop = previous_reliability_score - reliability_score
        if drop >= 30:
            reason_codes.append(AnomalyReasonCode.SOURCE_HEALTH_DEGRADATION)
            severity = _max_severity(severity, AnomalySeverity.HIGH)
            score = max(score, 0.7)
        elif drop >= 20:
            reason_codes.append(AnomalyReasonCode.SOURCE_HEALTH_DEGRADATION)
            severity = _max_severity(severity, AnomalySeverity.MEDIUM)
            score = max(score, 0.4)

    # Very low reliability
    if reliability_score < 30:
        reason_codes.append(AnomalyReasonCode.SOURCE_HEALTH_DEGRADATION)
        severity = _max_severity(severity, AnomalySeverity.HIGH)
        score = max(score, 0.6)

    if reason_codes:
        return AnomalyResult(
            anomaly_detected=True,
            severity=severity,
            anomaly_score=score,
            reason_codes=[rc.value for rc in reason_codes],
            affected_fields=[],
            explanation=f"Source health degraded: {previous_health_status}->{health_status}, reliability {previous_reliability_score}->{reliability_score}",
            current_value=str(previous_reliability_score),
            proposed_value=str(reliability_score),
            source_url=source_url,
            metadata={
                "reliability_score": reliability_score,
                "previous_reliability_score": previous_reliability_score,
                "health_status": health_status,
                "previous_health_status": previous_health_status,
            },
        )

    return None


def detect_confidence_anomaly(
    field_name: str,
    current_confidence: ConfidenceLevel,
    previous_confidence: ConfidenceLevel | None = None,
    current_state: VerificationState | None = None,
    previous_state: VerificationState | None = None,
) -> AnomalyResult | None:
    """Detect anomalies from confidence downgrade or verification state regression."""
    reason_codes = []
    severity = AnomalySeverity.LOW
    score = 0.0

    # Confidence downgrade
    if previous_confidence:
        key = (previous_confidence, current_confidence)
        if key in _CONFIDENCE_DOWNGRADE_SEVERITY:
            severity = _CONFIDENCE_DOWNGRADE_SEVERITY[key]
            score = 0.7 if severity == AnomalySeverity.HIGH else 0.4
            reason_codes.append(AnomalyReasonCode.CONFIDENCE_DOWNGRADE)

    # Verification state regression
    if previous_state and current_state:
        state_order = {
            "verified": 3,
            "partially_verified": 2,
            "uncertain": 1,
            "conflict": 0,
            "unsupported": 0,
        }
        prev_level = state_order.get(previous_state.value, 0)
        curr_level = state_order.get(current_state.value, 0)
        if curr_level < prev_level:
            reason_codes.append(AnomalyReasonCode.VERIFICATION_STATE_REGRESSION)
            if curr_level == 0:
                severity = _max_severity(severity, AnomalySeverity.HIGH)
                score = max(score, 0.7)
            else:
                severity = _max_severity(severity, AnomalySeverity.MEDIUM)
                score = max(score, 0.4)

    if reason_codes:
        return AnomalyResult(
            anomaly_detected=True,
            severity=severity,
            anomaly_score=score,
            reason_codes=[rc.value for rc in reason_codes],
            affected_fields=[field_name],
            explanation=(
                f"Confidence downgrade: {previous_confidence} -> {current_confidence}; "
                f"State regression: {previous_state} -> {current_state}"
            ),
            field_name=field_name,
            current_value=previous_confidence.value if previous_confidence else None,
            proposed_value=current_confidence.value,
            metadata={
                "previous_confidence": previous_confidence.value if previous_confidence else None,
                "current_confidence": current_confidence.value,
                "previous_state": previous_state.value if previous_state else None,
                "current_state": current_state.value if current_state else None,
            },
        )

    return None


def detect_eligibility_anomaly(
    field_name: str,
    old_value: str | None,
    new_value: str | None,
) -> AnomalyResult | None:
    """Detect anomalies in eligibility changes."""
    if not old_value or not new_value or old_value == new_value:
        return None

    old_lower = old_value.lower()
    new_lower = new_value.lower()

    reason_codes = []
    severity = AnomalySeverity.LOW
    score = 0.0

    # Check for restriction keywords
    restriction_keywords = ["only", "restricted", "limited", "exclusive", "citizens of"]
    broadening_keywords = ["all", "any", "open to", "anyone", "everyone"]

    old_restrictive = sum(1 for kw in restriction_keywords if kw in old_lower)
    new_restrictive = sum(1 for kw in restriction_keywords if kw in new_lower)
    old_broad = sum(1 for kw in broadening_keywords if kw in old_lower)
    new_broad = sum(1 for kw in broadening_keywords if kw in new_lower)

    if new_restrictive > old_restrictive and new_restrictive >= 2:
        reason_codes.append(AnomalyReasonCode.ELIGIBILITY_RESTRICTED)
        severity = AnomalySeverity.HIGH
        score = 0.6
    elif new_restrictive > old_restrictive:
        reason_codes.append(AnomalyReasonCode.ELIGIBILITY_RESTRICTED)
        severity = AnomalySeverity.MEDIUM
        score = 0.4

    if new_broad > old_broad and new_broad >= 2:
        reason_codes.append(AnomalyReasonCode.ELIGIBILITY_BROADENED)
        severity = _max_severity(severity, AnomalySeverity.MEDIUM)
        score = max(score, 0.4)

    if reason_codes:
        return AnomalyResult(
            anomaly_detected=True,
            severity=severity,
            anomaly_score=score,
            reason_codes=[rc.value for rc in reason_codes],
            affected_fields=[field_name],
            explanation=f"Eligibility changed: restriction level shifted",
            field_name=field_name,
            current_value=old_value,
            proposed_value=new_value,
            metadata={
                "old_restriction_score": old_restrictive,
                "new_restriction_score": new_restrictive,
                "old_broadening_score": old_broad,
                "new_broadening_score": new_broad,
            },
        )

    return None


def detect_lifecycle_anomaly(
    field_name: str,
    current_status: str | None,
    deadline_date: date | datetime | None,
    is_verified: bool | None = None,
    last_verified_at: datetime | None = None,
) -> AnomalyResult | None:
    """Detect lifecycle inconsistencies."""
    reason_codes = []
    severity = AnomalySeverity.LOW
    score = 0.0

    # Deadline in past but status is active/open
    if deadline_date and current_status:
        if isinstance(deadline_date, datetime):
            deadline_cmp = deadline_date.date() if hasattr(deadline_date, 'date') else deadline_date
        else:
            deadline_cmp = deadline_date

        now = _now().date()
        status_active = current_status.lower() in ("active", "application_open", "open", "discovered")

        if deadline_cmp < now and status_active:
            reason_codes.append(AnomalyReasonCode.LIFECYCLE_MISMATCH)
            severity = AnomalySeverity.MEDIUM
            score = 0.5

    # Unverified but deadline is near
    if is_verified is False and deadline_date:
        if isinstance(deadline_date, datetime):
            deadline_cmp = deadline_date.date() if hasattr(deadline_date, 'date') else deadline_date
        else:
            deadline_cmp = deadline_date

        days_to_deadline = _days_between(_now().date(), deadline_cmp)
        if days_to_deadline is not None and days_to_deadline <= 30:
            reason_codes.append(AnomalyReasonCode.LIFECYCLE_MISMATCH)
            severity = _max_severity(severity, AnomalySeverity.MEDIUM)
            score = max(score, 0.4)

    if reason_codes:
        return AnomalyResult(
            anomaly_detected=True,
            severity=severity,
            anomaly_score=score,
            reason_codes=[rc.value for rc in reason_codes],
            affected_fields=[field_name],
            explanation=f"Lifecycle inconsistency detected: status={current_status}, deadline={deadline_date}",
            field_name=field_name,
            metadata={
                "current_status": current_status,
                "deadline_date": str(deadline_date) if deadline_date else None,
                "is_verified": is_verified,
            },
        )

    return None


def detect_value_oscillation(
    field_name: str,
    value_history: list[str],
    oscillation_threshold: int = 3,
) -> AnomalyResult | None:
    """Detect value oscillation (A->B->A->B pattern)."""
    if len(value_history) < oscillation_threshold * 2:
        return None

    # Check for oscillation in recent history
    recent = value_history[-oscillation_threshold * 2:]
    unique_values = set(recent)

    if len(unique_values) > 2:
        return None

    # Count transitions
    transitions = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])

    if transitions >= oscillation_threshold:
        return AnomalyResult(
            anomaly_detected=True,
            severity=AnomalySeverity.MEDIUM,
            anomaly_score=0.4,
            reason_codes=[AnomalyReasonCode.VALUE_OSCILLATION],
            affected_fields=[field_name],
            explanation=f"Value oscillating between {unique_values} ({transitions} transitions)",
            field_name=field_name,
            metadata={
                "oscillation_count": transitions,
                "unique_values": list(unique_values),
            },
        )

    return None


def detect_anomalies(
    field_name: str,
    old_value: str | date | datetime | None,
    new_value: str | date | datetime | None,
    *,
    historical_values: list[str] | list[date] | None = None,
    arbitration_result: ArbitrationResult | None = None,
    source_url: str | None = None,
    source_reliability: float | None = None,
    previous_source_reliability: float | None = None,
    source_health_status: str | None = None,
    previous_source_health_status: str | None = None,
    current_confidence: ConfidenceLevel | None = None,
    previous_confidence: ConfidenceLevel | None = None,
    current_verification_state: VerificationState | None = None,
    previous_verification_state: VerificationState | None = None,
    scholarship_status: str | None = None,
    deadline_date: date | datetime | None = None,
    is_verified: bool | None = None,
    value_history: list[str] | None = None,
) -> list["AnomalyResult"]:
    """Run all anomaly detectors on a single field change.

    Returns a list of detected anomalies (empty if normal).
    """
    anomalies = []

    str_old = str(old_value) if old_value is not None and not isinstance(old_value, (date, datetime)) else old_value
    str_new = str(new_value) if new_value is not None and not isinstance(new_value, (date, datetime)) else new_value

    # Deadline anomaly detection
    if field_name in ("deadline_date", "deadline", "deadline_display"):
        result = detect_deadline_anomaly(field_name, old_value, new_value, historical_values)
        if result.anomaly_detected:
            anomalies.append(result)

    # Funding anomaly detection
    if field_name in ("funding", "funding_type", "coverage"):
        result = detect_funding_anomaly(field_name, str_old, str_new)
        if result.anomaly_detected:
            anomalies.append(result)

    # Duration anomaly detection
    if field_name == "duration":
        result = detect_duration_anomaly(field_name, str_old, str_new)
        if result.anomaly_detected:
            anomalies.append(result)

    # Eligibility anomaly detection
    if field_name in ("eligibility", "eligibility_summary"):
        result = detect_eligibility_anomaly(field_name, str_old, str_new)
        if result:
            anomalies.append(result)

    # Source disagreement anomaly
    if arbitration_result:
        result = detect_source_disagreement_anomaly(arbitration_result)
        if result:
            anomalies.append(result)

    # Source health anomaly
    if source_reliability is not None:
        result = detect_source_health_anomaly(
            source_url, source_reliability, previous_source_reliability,
            source_health_status, previous_source_health_status
        )
        if result:
            anomalies.append(result)

    # Confidence anomaly
    if current_confidence:
        result = detect_confidence_anomaly(
            field_name, current_confidence, previous_confidence,
            current_verification_state, previous_verification_state
        )
        if result:
            anomalies.append(result)

    # Lifecycle anomaly
    if field_name in ("status", "deadline_date"):
        result = detect_lifecycle_anomaly(
            field_name, scholarship_status, deadline_date, is_verified
        )
        if result:
            anomalies.append(result)

    # Value oscillation
    if value_history:
        result = detect_value_oscillation(field_name, value_history)
        if result:
            anomalies.append(result)

    return anomalies


def detect_batch_anomalies(
    changes: list[dict[str, Any]],
) -> dict[str, list[AnomalyResult]]:
    """Detect anomalies across multiple field changes.

    Args:
        changes: List of dicts with field change data.
            Each dict should have:
            - field_name: str
            - old_value: Any
            - new_value: Any
            - Plus optional context fields

    Returns:
        Dict mapping field_name to list of detected anomalies.
    """
    results: dict[str, list[AnomalyResult]] = {}

    # Collect all changed fields for multi-field detection
    changed_fields = {}
    for change in changes:
        field_name = change["field_name"]
        old_val = change.get("old_value")
        new_val = change.get("new_value")
        if old_val != new_val:
            str_old = str(old_val) if not isinstance(old_val, (date, datetime)) else old_val
            str_new = str(new_val) if not isinstance(new_val, (date, datetime)) else new_val
            changed_fields[field_name] = (str_old, str_new)

    # Multi-field anomaly detection
    multi_field_result = detect_multi_field_anomaly(changed_fields)
    if multi_field_result:
        for field_name in multi_field_result.affected_fields:
            if field_name not in results:
                results[field_name] = []
            results[field_name].append(multi_field_result)

    # Per-field anomaly detection
    for change in changes:
        field_name = change["field_name"]
        anomalies = detect_anomalies(
            field_name=field_name,
            old_value=change.get("old_value"),
            new_value=change.get("new_value"),
            historical_values=change.get("historical_values"),
            arbitration_result=change.get("arbitration_result"),
            source_url=change.get("source_url"),
            source_reliability=change.get("source_reliability"),
            previous_source_reliability=change.get("previous_source_reliability"),
            source_health_status=change.get("source_health_status"),
            previous_source_health_status=change.get("previous_source_health_status"),
            current_confidence=change.get("current_confidence"),
            previous_confidence=change.get("previous_confidence"),
            current_verification_state=change.get("current_verification_state"),
            previous_verification_state=change.get("previous_verification_state"),
            scholarship_status=change.get("scholarship_status"),
            deadline_date=change.get("deadline_date"),
            is_verified=change.get("is_verified"),
            value_history=change.get("value_history"),
        )
        if anomalies:
            if field_name not in results:
                results[field_name] = []
            results[field_name].extend(anomalies)

    return results


def aggregate_anomaly_severity(anomalies: list[AnomalySeverity]) -> AnomalySeverity:
    """Aggregate multiple anomaly severities into a single severity."""
    if not anomalies:
        return AnomalySeverity.LOW

    severity_order = {
        AnomalySeverity.CRITICAL: 3,
        AnomalySeverity.HIGH: 2,
        AnomalySeverity.MEDIUM: 1,
        AnomalySeverity.LOW: 0,
    }

    max_severity = max(anomalies, key=lambda s: severity_order.get(s, 0))
    return max_severity


def compute_anomaly_score(anomalies: list[AnomalyResult]) -> float:
    """Compute aggregate anomaly score from multiple results."""
    if not anomalies:
        return 0.0

    # Weighted average: higher severity anomalies contribute more
    weights = {
        AnomalySeverity.CRITICAL: 1.0,
        AnomalySeverity.HIGH: 0.7,
        AnomalySeverity.MEDIUM: 0.4,
        AnomalySeverity.LOW: 0.1,
    }

    total_score = sum(a.anomaly_score * weights.get(a.severity, 0.1) for a in anomalies)
    max_possible = sum(weights.get(a.severity, 0.1) for a in anomalies)

    if max_possible == 0:
        return 0.0

    return min(1.0, total_score / max_possible) if max_possible > 0 else 0.0


def summarize_anomalies(anomalies: list[AnomalyResult]) -> dict[str, Any]:
    """Create a summary of detected anomalies."""
    if not anomalies:
        return {
            "anomaly_detected": False,
            "severity": AnomalySeverity.LOW.value,
            "anomaly_score": 0.0,
            "total_anomalies": 0,
            "affected_fields": [],
            "requires_review": False,
            "should_block": False,
        }

    severities = [a.severity for a in anomalies]
    overall_severity = aggregate_anomaly_severity(severities)
    overall_score = compute_anomaly_score(anomalies)
    all_fields = list(set(f for a in anomalies for f in a.affected_fields))

    return {
        "anomaly_detected": True,
        "severity": overall_severity.value,
        "anomaly_score": overall_score,
        "total_anomalies": len(anomalies),
        "affected_fields": all_fields,
        "requires_review": overall_severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL),
        "should_block": overall_severity == AnomalySeverity.CRITICAL,
        "reason_codes": list(set(rc for a in anomalies for rc in a.reason_codes)),
        "explanations": [a.explanation for a in anomalies if a.explanation],
    }
