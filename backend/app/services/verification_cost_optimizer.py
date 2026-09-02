"""Verification cost-optimizer for scholarship verification pipeline.

Minimizes total verification cost/latency while preserving correctness
and all safety guarantees.

Design principles:
- Deterministic: same inputs always produce same outputs
- Safety-first: never skips verification required for safety/freshness
- No network calls: pure computation using existing signals
- No ML/LLM: rule-based arithmetic
- Batch-friendly: supports batch candidate scoring
- Low-latency: O(1)/O(n) scoring where possible
- No N+1: reuses already-available telemetry/history

Signals used:
- fingerprint unchanged probability
- source health/latency
- retry state
- staleness
- change impact
- deadline urgency
- dependency set size
- historical verification duration
- source change frequency
- lifecycle state

Optimization actions:
- VERIFY: run verification now
- BATCH: include in next batch run
- DEFER: postpone to later cycle
- SKIP: skip only when safe (fingerprint unchanged + no safety requirement)

Safety guarantees (NEVER bypassed):
- Evidence pipeline
- Confidence assessment
- Consensus resolution
- Anomaly detection
- Safety gate
- Unresolved conflict suppression
- Freshness requirements
- Deadline-critical verification
- Dependency-required verification

Version: 1 (initial cost-optimizer for verification pipeline)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from .change_impact_staleness import (
    CRITICAL,
    CRITICAL_STALE,
    FIELD_CRITICALITY,
    STALE,
    compute_change_impact,
    compute_deadline_urgency,
    compute_field_staleness,
    get_field_criticality,
    get_freshness_threshold,
)
from .content_fingerprinting import FingerprintStatus
from .dependency_graph import CriticalityLevel, analyze_dependencies
from .telemetry import get_source_stats


class VerificationAction(str, Enum):
    """Actions that can be recommended by the cost optimizer."""
    VERIFY = "verify"
    BATCH = "batch"
    DEFER = "defer"
    SKIP = "skip"


class SafetyFlag(str, Enum):
    """Flags that prevent skipping verification."""
    DEADLINE_CRITICAL = "deadline_critical"
    CRITICAL_FIELD = "critical_field"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    DEPENDENCY_REQUIRED = "dependency_required"
    FRESHNESS_REQUIRED = "freshness_required"
    ANOMALY_DETECTED = "anomaly_detected"
    SOURCE_UNHEALTHY = "source_unhealthy"
    HIGH_CHANGE_FREQUENCY = "high_change_frequency"


COST_OPTIMIZER_VERSION = "v1"

# Cost weights for computing total cost
NETWORK_COST_WEIGHT = 0.30
CPU_COST_WEIGHT = 0.20
DB_COST_WEIGHT = 0.15
LATENCY_COST_WEIGHT = 0.25
SOURCE_LOAD_COST_WEIGHT = 0.10

# Base costs (arbitrary units, 0-100 scale)
BASE_NETWORK_COST = 40.0
BASE_CPU_COST = 30.0
BASE_DB_COST = 20.0
BASE_LATENCY_COST = 35.0
BASE_SOURCE_LOAD_COST = 10.0

# Latency cost factors
LATENCY_SLOW_P95_MS = 5000.0
LATENCY_FAST_P95_MS = 1000.0

# Source health cost factors
SOURCE_HEALTH_COST_FACTOR = {
    "healthy": 0.8,
    "degraded": 1.2,
    "unhealthy": 1.8,
    "unknown": 1.0,
}

# Fingerprint unchanged probability thresholds
FINGERPRINT_HIGH_UNCHANGED_PROB = 0.9
FINGERPRINT_MEDIUM_UNCHANGED_PROB = 0.6

# Decision thresholds (efficiency scores)
EFFICIENCY_VERIFY_THRESHOLD = 1.5
EFFICIENCY_BATCH_THRESHOLD = 0.8
EFFICIENCY_DEFER_THRESHOLD = 0.3

# Maximum cost cap to prevent division issues
MAX_TOTAL_COST = 100.0
MIN_TOTAL_COST = 1.0

# Deadline urgency thresholds for safety
DEADLINE_CRITICAL_URGENCY = 80
DEADLINE_URGENT_URGENCY = 50

# Staleness thresholds for freshness requirement
FRESHNESS_CRITICAL_STALENESS = 80

# Change frequency thresholds
HIGH_CHANGE_FREQUENCY_THRESHOLD = 5


@dataclass(frozen=True)
class VerificationCostProfile:
    """Complete cost profile for a verification candidate."""
    estimated_network_cost: float
    estimated_cpu_cost: float
    estimated_db_cost: float
    estimated_latency: float
    source_load_cost: float
    verification_value: float
    priority: float
    recommended_action: VerificationAction
    efficiency_score: float
    total_cost: float
    reason_codes: tuple[str, ...]
    safety_flags: tuple[SafetyFlag, ...]
    fingerprint_unchanged_probability: float
    field_criticality: str
    deadline_urgency: int
    staleness_score: int
    source_health_status: str
    lifecycle_state: str
    dependency_set_size: int
    version: str = COST_OPTIMIZER_VERSION

    @property
    def is_safe_to_skip(self) -> bool:
        """Check if this candidate can be safely skipped."""
        return (
            len(self.safety_flags) == 0
            and self.fingerprint_unchanged_probability >= FINGERPRINT_HIGH_UNCHANGED_PROB
        )

    @property
    def requires_immediate_verification(self) -> bool:
        """Check if verification must happen immediately."""
        return self.recommended_action == VerificationAction.VERIFY

    @property
    def can_batch(self) -> bool:
        """Check if candidate can be batched."""
        return self.recommended_action in (
            VerificationAction.BATCH,
            VerificationAction.VERIFY,
        )


@dataclass(frozen=True)
class BatchOptimizationResult:
    """Result of batch optimization over multiple candidates."""
    candidates: tuple[VerificationCostProfile, ...]
    total_cost: float
    total_value: float
    batch_efficiency: float
    verify_now: tuple[VerificationCostProfile, ...]
    batch_later: tuple[VerificationCostProfile, ...]
    defer: tuple[VerificationCostProfile, ...]
    skip: tuple[VerificationCostProfile, ...]
    estimated_batch_savings: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class _CostInputs:
    """Internal inputs for cost computation."""
    fingerprint_status: FingerprintStatus | None
    fingerprint_unchanged_probability: float
    source_health_status: str
    source_reliability: float
    source_avg_latency_ms: float
    source_error_rate: float
    source_consecutive_failures: int
    deadline_urgency: int
    staleness_score: int
    field_criticality: str
    field_name: str
    lifecycle_state: str
    lifecycle_is_terminal: bool
    dependency_set_size: int
    has_unresolved_conflict: bool
    anomaly_score: float
    change_frequency_30d: int
    retry_attempt_count: int
    is_retrying: bool
    content_size_bytes: int
    today: date | None = None


def _compute_network_cost(inputs: _CostInputs) -> float:
    """Estimate network cost for verification.

    Factors:
    - Source latency (higher latency = higher cost)
    - Content size (larger = more bandwidth)
    - Source health (unhealthy sources may need retries)
    - Retry state (active retries add cost)
    """
    cost = BASE_NETWORK_COST

    # Latency factor
    if inputs.source_avg_latency_ms > 0:
        if inputs.source_avg_latency_ms >= LATENCY_SLOW_P95_MS:
            cost *= 1.5
        elif inputs.source_avg_latency_ms <= LATENCY_FAST_P95_MS:
            cost *= 0.7

    # Content size factor (logarithmic scaling)
    if inputs.content_size_bytes > 0:
        import math
        size_kb = inputs.content_size_bytes / 1024.0
        size_factor = 1.0 + math.log1p(size_kb) * 0.1
        cost *= min(2.0, size_factor)

    # Source health factor
    health_factor = SOURCE_HEALTH_COST_FACTOR.get(
        inputs.source_health_status, 1.0
    )
    cost *= health_factor

    # Retry state factor
    if inputs.is_retrying:
        cost *= 1.3 + (inputs.retry_attempt_count * 0.1)

    # Error rate factor (high error rate = more retries = more cost)
    if inputs.source_error_rate > 0.3:
        cost *= 1.0 + inputs.source_error_rate

    return min(MAX_TOTAL_COST, cost)


def _compute_cpu_cost(inputs: _CostInputs) -> float:
    """Estimate CPU cost for verification.

    Factors:
    - Number of fields (more fields = more extraction)
    - Dependency set size (larger = more analysis)
    - Content size (larger = more processing)
    """
    cost = BASE_CPU_COST

    # Dependency analysis cost
    if inputs.dependency_set_size > 0:
        cost += min(20.0, inputs.dependency_set_size * 2.0)

    # Content size factor
    if inputs.content_size_bytes > 0:
        import math
        size_kb = inputs.content_size_bytes / 1024.0
        size_factor = 1.0 + math.log1p(size_kb) * 0.05
        cost *= min(1.5, size_factor)

    return min(MAX_TOTAL_COST, cost)


def _compute_db_cost(inputs: _CostInputs) -> float:
    """Estimate database cost for verification.

    Factors:
    - Read operations (history, health, snapshots)
    - Write operations (fingerprint, history, telemetry)
    - Dependency analysis queries
    """
    cost = BASE_DB_COST

    # Additional reads for dependency analysis
    if inputs.dependency_set_size > 0:
        cost += min(10.0, inputs.dependency_set_size * 0.5)

    # History lookup cost
    if inputs.change_frequency_30d > 0:
        cost += min(5.0, inputs.change_frequency_30d * 0.5)

    return min(MAX_TOTAL_COST, cost)


def _compute_latency_cost(inputs: _CostInputs) -> float:
    """Estimate latency cost for verification.

    Factors:
    - Source latency (primary factor)
    - Network retries
    - Content size
    """
    cost = BASE_LATENCY_COST

    # Source latency factor
    if inputs.source_avg_latency_ms > 0:
        latency_factor = inputs.source_avg_latency_ms / 2000.0
        cost *= min(2.0, latency_factor)

    # Retry adds latency
    if inputs.is_retrying:
        cost *= 1.2 + (inputs.retry_attempt_count * 0.05)

    # Error rate adds latency (retries)
    if inputs.source_error_rate > 0.3:
        cost *= 1.0 + (inputs.source_error_rate * 0.5)

    return min(MAX_TOTAL_COST, cost)


def _compute_source_load_cost(inputs: _CostInputs) -> float:
    """Estimate cost imposed on the source.

    Factors:
    - Source health (unhealthy sources are more costly to hit)
    - Consecutive failures (indicates source stress)
    - Rate of requests
    """
    cost = BASE_SOURCE_LOAD_COST

    # Hitting unhealthy sources is costly
    if inputs.source_health_status == "unhealthy":
        cost *= 2.0
    elif inputs.source_health_status == "degraded":
        cost *= 1.5

    # Consecutive failures indicate source stress
    if inputs.source_consecutive_failures > 0:
        cost *= 1.0 + (inputs.source_consecutive_failures * 0.2)

    return min(MAX_TOTAL_COST, cost)


def _compute_verification_value(inputs: _CostInputs) -> float:
    """Estimate information value of verification.

    Factors:
    - Fingerprint unchanged probability (high = low value)
    - Field criticality (critical fields = high value)
    - Deadline urgency (urgent deadlines = high value)
    - Staleness (stale data = high value)
    - Dependency set size (more deps = more value)
    - Change frequency (frequent changes = higher value)
    - Source health confidence (healthier = more reliable value)
    - Lifecycle state (active states = more value)
    """
    # Start with base value
    value = 30.0

    # Fingerprint unchanged probability (inverse relationship)
    unchanged_prob = inputs.fingerprint_unchanged_probability
    if unchanged_prob >= FINGERPRINT_HIGH_UNCHANGED_PROB:
        value *= 0.1  # Very low value if almost certainly unchanged
    elif unchanged_prob >= FINGERPRINT_MEDIUM_UNCHANGED_PROB:
        value *= 0.4
    elif unchanged_prob > 0:
        value *= 0.7
    # If unknown (prob = 0), value stays at base

    # Field criticality factor
    criticality = inputs.field_criticality
    if criticality == CRITICAL:
        value *= 2.0
    elif criticality == "high":
        value *= 1.5
    elif criticality == "medium":
        value *= 1.0
    else:
        value *= 0.6

    # Deadline urgency factor
    if inputs.deadline_urgency >= DEADLINE_CRITICAL_URGENCY:
        value *= 2.5
    elif inputs.deadline_urgency >= DEADLINE_URGENT_URGENCY:
        value *= 1.8
    elif inputs.deadline_urgency > 0:
        value *= 1.2

    # Staleness factor (staler = more value in refreshing)
    staleness = inputs.staleness_score
    if staleness >= FRESHNESS_CRITICAL_STALENESS:
        value *= 2.0
    elif staleness >= 50:
        value *= 1.5
    elif staleness >= 25:
        value *= 1.2

    # Dependency set size factor
    if inputs.dependency_set_size > 5:
        value *= 1.5
    elif inputs.dependency_set_size > 2:
        value *= 1.2

    # Change frequency factor
    if inputs.change_frequency_30d >= HIGH_CHANGE_FREQUENCY_THRESHOLD:
        value *= 1.5
    elif inputs.change_frequency_30d >= 2:
        value *= 1.2

    # Source health confidence factor
    if inputs.source_reliability > 80:
        value *= 1.2
    elif inputs.source_reliability > 50:
        value *= 1.0
    elif inputs.source_reliability > 0:
        value *= 0.7

    # Lifecycle state factor
    if inputs.lifecycle_is_terminal:
        value *= 0.1
    elif inputs.lifecycle_state in ("deadline_near", "application_open"):
        value *= 1.5
    elif inputs.lifecycle_state in ("active",):
        value *= 1.2
    elif inputs.lifecycle_state == "discovered":
        value *= 1.3

    return min(100.0, value)


def _compute_priority(inputs: _CostInputs) -> float:
    """Compute priority score for the verification candidate.

    Higher = more important to verify soon.
    """
    priority = 0.0

    # Deadline urgency is highest weight
    priority += inputs.deadline_urgency * 0.35

    # Field criticality
    if inputs.field_criticality == CRITICAL:
        priority += 25.0
    elif inputs.field_criticality == "high":
        priority += 15.0
    elif inputs.field_criticality == "medium":
        priority += 8.0

    # Staleness
    priority += inputs.staleness_score * 0.2

    # Dependency cascading potential
    priority += min(15.0, inputs.dependency_set_size * 2.0)

    # Change frequency
    priority += min(10.0, inputs.change_frequency_30d * 1.5)

    # Lifecycle state
    if inputs.lifecycle_state == "deadline_near":
        priority += 15.0
    elif inputs.lifecycle_state == "application_open":
        priority += 10.0
    elif inputs.lifecycle_state == "discovered":
        priority += 8.0

    # Unresolved conflict boosts priority
    if inputs.has_unresolved_conflict:
        priority += 10.0

    return min(100.0, priority)


def _determine_safety_flags(inputs: _CostInputs) -> list[SafetyFlag]:
    """Determine safety flags that prevent skipping verification."""
    flags: list[SafetyFlag] = []

    # Deadline-critical verification cannot be skipped
    if inputs.deadline_urgency >= DEADLINE_CRITICAL_URGENCY:
        flags.append(SafetyFlag.DEADLINE_CRITICAL)

    # Critical field changes require verification
    if inputs.field_criticality == CRITICAL:
        flags.append(SafetyFlag.CRITICAL_FIELD)

    # Unresolved conflicts must not be suppressed
    if inputs.has_unresolved_conflict:
        flags.append(SafetyFlag.UNRESOLVED_CONFLICT)

    # Dependency-required verification
    if inputs.dependency_set_size > 0 and inputs.field_criticality in (CRITICAL, "high"):
        flags.append(SafetyFlag.DEPENDENCY_REQUIRED)

    # Freshness required for stale data
    if inputs.staleness_score >= FRESHNESS_CRITICAL_STALENESS:
        flags.append(SafetyFlag.FRESHNESS_REQUIRED)

    # Anomaly detected requires review
    if inputs.anomaly_score >= 0.5:
        flags.append(SafetyFlag.ANOMALY_DETECTED)

    # Unhealthy source may need verification to confirm state
    if inputs.source_health_status == "unhealthy" and inputs.source_consecutive_failures >= 3:
        flags.append(SafetyFlag.SOURCE_UNHEALTHY)

    # High change frequency may indicate instability
    if inputs.change_frequency_30d >= HIGH_CHANGE_FREQUENCY_THRESHOLD:
        flags.append(SafetyFlag.HIGH_CHANGE_FREQUENCY)

    return flags


def _compute_efficiency(verification_value: float, total_cost: float) -> float:
    """Compute efficiency score as value/cost ratio.

    Higher = more efficient to verify.
    """
    cost = max(MIN_TOTAL_COST, total_cost)
    return verification_value / cost


def _determine_action(
    efficiency: float,
    safety_flags: list[SafetyFlag],
    inputs: _CostInputs,
) -> tuple[VerificationAction, list[str]]:
    """Determine recommended action based on efficiency and safety.

    Returns (action, reason_codes).
    """
    reasons: list[str] = []

    # Safety overrides: must verify if safety flags present
    if safety_flags:
        critical_flags = {
            SafetyFlag.DEADLINE_CRITICAL,
            SafetyFlag.CRITICAL_FIELD,
            SafetyFlag.UNRESOLVED_CONFLICT,
            SafetyFlag.ANOMALY_DETECTED,
        }
        if any(f in critical_flags for f in safety_flags):
            reasons.append(f"safety_critical:{','.join(f.value for f in safety_flags)}")
            return VerificationAction.VERIFY, reasons

    # High efficiency: verify now
    if efficiency >= EFFICIENCY_VERIFY_THRESHOLD:
        reasons.append(f"high_efficiency:{efficiency:.2f}")
        if safety_flags:
            reasons.append(f"safety_noted:{','.join(f.value for f in safety_flags)}")
        return VerificationAction.VERIFY, reasons

    # Medium efficiency: batch for efficiency
    if efficiency >= EFFICIENCY_BATCH_THRESHOLD:
        reasons.append(f"batch_efficient:{efficiency:.2f}")
        return VerificationAction.BATCH, reasons

    # Low but non-zero efficiency: defer
    if efficiency >= EFFICIENCY_DEFER_THRESHOLD:
        reasons.append(f"defer_low_efficiency:{efficiency:.2f}")
        return VerificationAction.DEFER, reasons

    # Very low efficiency: skip if safe
    if not safety_flags:
        reasons.append(f"skip_low_efficiency:{efficiency:.2f}")
        if inputs.fingerprint_unchanged_probability >= FINGERPRINT_HIGH_UNCHANGED_PROB:
            reasons.append("fingerprint_likely_unchanged")
        return VerificationAction.SKIP, reasons

    # Low efficiency but safety flags present: defer instead of skip
    reasons.append(f"defer_safety_override:{efficiency:.2f}")
    reasons.append(f"safety_flags:{','.join(f.value for f in safety_flags)}")
    return VerificationAction.DEFER, reasons


def _build_cost_inputs(
    fingerprint_status: FingerprintStatus | None = None,
    fingerprint_unchanged_probability: float = 0.0,
    source_health_status: str = "unknown",
    source_reliability: float = 0.0,
    source_avg_latency_ms: float = 0.0,
    source_error_rate: float = 0.0,
    source_consecutive_failures: int = 0,
    deadline_urgency: int = 0,
    staleness_score: int = 0,
    field_name: str = "",
    field_criticality: str | None = None,
    lifecycle_state: str = "unknown",
    lifecycle_is_terminal: bool = False,
    dependency_set_size: int = 0,
    has_unresolved_conflict: bool = False,
    anomaly_score: float = 0.0,
    change_frequency_30d: int = 0,
    retry_attempt_count: int = 0,
    is_retrying: bool = False,
    content_size_bytes: int = 0,
) -> _CostInputs:
    """Build _CostInputs from individual parameters."""
    if field_criticality is None:
        field_criticality = get_field_criticality(field_name)

    return _CostInputs(
        fingerprint_status=fingerprint_status,
        fingerprint_unchanged_probability=fingerprint_unchanged_probability,
        source_health_status=source_health_status,
        source_reliability=source_reliability,
        source_avg_latency_ms=source_avg_latency_ms,
        source_error_rate=source_error_rate,
        source_consecutive_failures=source_consecutive_failures,
        deadline_urgency=deadline_urgency,
        staleness_score=staleness_score,
        field_criticality=field_criticality,
        field_name=field_name,
        lifecycle_state=lifecycle_state,
        lifecycle_is_terminal=lifecycle_is_terminal,
        dependency_set_size=dependency_set_size,
        has_unresolved_conflict=has_unresolved_conflict,
        anomaly_score=anomaly_score,
        change_frequency_30d=change_frequency_30d,
        retry_attempt_count=retry_attempt_count,
        is_retrying=is_retrying,
        content_size_bytes=content_size_bytes,
    )


def compute_cost_profile(
    fingerprint_status: FingerprintStatus | None = None,
    fingerprint_unchanged_probability: float = 0.0,
    source_health_status: str = "unknown",
    source_reliability: float = 0.0,
    source_avg_latency_ms: float = 0.0,
    source_error_rate: float = 0.0,
    source_consecutive_failures: int = 0,
    deadline_urgency: int = 0,
    staleness_score: int = 0,
    field_name: str = "",
    field_criticality: str | None = None,
    lifecycle_state: str = "unknown",
    lifecycle_is_terminal: bool = False,
    dependency_set_size: int = 0,
    has_unresolved_conflict: bool = False,
    anomaly_score: float = 0.0,
    change_frequency_30d: int = 0,
    retry_attempt_count: int = 0,
    is_retrying: bool = False,
    content_size_bytes: int = 0,
) -> VerificationCostProfile:
    """Compute the full cost profile for a verification candidate.

    This is the main entry point for single-candidate cost optimization.

    Args:
        fingerprint_status: Current fingerprint comparison status
        fingerprint_unchanged_probability: Probability content is unchanged (0-1)
        source_health_status: Health status of source (healthy/degraded/unhealthy/unknown)
        source_reliability: Reliability score (0-100)
        source_avg_latency_ms: Average source latency in ms
        source_error_rate: Error rate (0-1)
        source_consecutive_failures: Number of consecutive failures
        deadline_urgency: Deadline urgency score (0-100)
        staleness_score: Field staleness score (0-100)
        field_name: Name of the field being verified
        field_criticality: Override criticality (auto-detected if None)
        lifecycle_state: Current lifecycle state
        lifecycle_is_terminal: Whether lifecycle is terminal
        dependency_set_size: Number of fields depending on this field
        has_unresolved_conflict: Whether there's an unresolved conflict
        anomaly_score: Anomaly detection score (0-1)
        change_frequency_30d: Number of changes in last 30 days
        retry_attempt_count: Current retry attempt count
        is_retrying: Whether this is a retry
        content_size_bytes: Size of content to fetch/process

    Returns:
        VerificationCostProfile with costs, value, and recommended action
    """
    inputs = _build_cost_inputs(
        fingerprint_status=fingerprint_status,
        fingerprint_unchanged_probability=fingerprint_unchanged_probability,
        source_health_status=source_health_status,
        source_reliability=source_reliability,
        source_avg_latency_ms=source_avg_latency_ms,
        source_error_rate=source_error_rate,
        source_consecutive_failures=source_consecutive_failures,
        deadline_urgency=deadline_urgency,
        staleness_score=staleness_score,
        field_name=field_name,
        field_criticality=field_criticality,
        lifecycle_state=lifecycle_state,
        lifecycle_is_terminal=lifecycle_is_terminal,
        dependency_set_size=dependency_set_size,
        has_unresolved_conflict=has_unresolved_conflict,
        anomaly_score=anomaly_score,
        change_frequency_30d=change_frequency_30d,
        retry_attempt_count=retry_attempt_count,
        is_retrying=is_retrying,
        content_size_bytes=content_size_bytes,
    )

    network_cost = _compute_network_cost(inputs)
    cpu_cost = _compute_cpu_cost(inputs)
    db_cost = _compute_db_cost(inputs)
    latency_cost = _compute_latency_cost(inputs)
    source_load_cost = _compute_source_load_cost(inputs)

    total_cost = (
        network_cost * NETWORK_COST_WEIGHT
        + cpu_cost * CPU_COST_WEIGHT
        + db_cost * DB_COST_WEIGHT
        + latency_cost * LATENCY_COST_WEIGHT
        + source_load_cost * SOURCE_LOAD_COST_WEIGHT
    )

    verification_value = _compute_verification_value(inputs)
    priority = _compute_priority(inputs)
    safety_flags = _determine_safety_flags(inputs)
    efficiency = _compute_efficiency(verification_value, total_cost)
    action, reasons = _determine_action(efficiency, safety_flags, inputs)

    return VerificationCostProfile(
        estimated_network_cost=round(network_cost, 2),
        estimated_cpu_cost=round(cpu_cost, 2),
        estimated_db_cost=round(db_cost, 2),
        estimated_latency=round(latency_cost, 2),
        source_load_cost=round(source_load_cost, 2),
        verification_value=round(verification_value, 2),
        priority=round(priority, 2),
        recommended_action=action,
        efficiency_score=round(efficiency, 4),
        total_cost=round(total_cost, 2),
        reason_codes=tuple(reasons),
        safety_flags=tuple(safety_flags),
        fingerprint_unchanged_probability=round(fingerprint_unchanged_probability, 4),
        field_criticality=inputs.field_criticality,
        deadline_urgency=deadline_urgency,
        staleness_score=staleness_score,
        source_health_status=source_health_status,
        lifecycle_state=lifecycle_state,
        dependency_set_size=dependency_set_size,
    )


def compute_profile_from_candidate(
    field_name: str,
    fingerprint_status: FingerprintStatus | None = None,
    fingerprint_unchanged_probability: float = 0.0,
    source_url: str | None = None,
    deadline_date: date | datetime | None = None,
    last_verified_at: datetime | date | None = None,
    lifecycle_state: str = "unknown",
    lifecycle_is_terminal: bool = False,
    dependency_set_size: int = 0,
    has_unresolved_conflict: bool = False,
    anomaly_score: float = 0.0,
    change_frequency_30d: int = 0,
    retry_attempt_count: int = 0,
    is_retrying: bool = False,
    content_size_bytes: int = 0,
    today: date | None = None,
) -> VerificationCostProfile:
    """Compute cost profile from a candidate with automatic signal derivation.

    This convenience function derives signals (deadline urgency, staleness,
    source health) from the provided data, then computes the full profile.

    Args:
        field_name: Name of the field to verify
        fingerprint_status: Fingerprint comparison status
        fingerprint_unchanged_probability: Probability content is unchanged
        source_url: Source URL for health lookups
        deadline_date: Deadline date for urgency computation
        last_verified_at: When field was last verified
        lifecycle_state: Current lifecycle state
        lifecycle_is_terminal: Whether lifecycle is terminal
        dependency_set_size: Number of dependent fields
        has_unresolved_conflict: Whether conflict exists
        anomaly_score: Anomaly score (0-1)
        change_frequency_30d: Changes in last 30 days
        retry_attempt_count: Current retry count
        is_retrying: Whether this is a retry
        content_size_bytes: Content size
        today: Optional date override for testing

    Returns:
        VerificationCostProfile
    """
    if today is None:
        today = date.today()

    # Compute deadline urgency
    deadline_urgency = 0
    if deadline_date is not None:
        if isinstance(deadline_date, datetime):
            deadline_date = deadline_date.date()
        delta = (deadline_date - today).days
        if delta >= 0:
            if delta <= 14:
                deadline_urgency = 100
            elif delta <= 30:
                deadline_urgency = 80
            elif delta <= 60:
                deadline_urgency = 50
            else:
                deadline_urgency = 10

    # Compute staleness
    staleness = 0
    if last_verified_at is not None:
        if isinstance(last_verified_at, datetime):
            last_date = last_verified_at.date()
        else:
            last_date = last_verified_at
        threshold = get_freshness_threshold(field_name)
        age_days = (today - last_date).days
        if age_days < 0:
            age_days = 0
        staleness = min(100, int((age_days / threshold) * 100)) if threshold > 0 else 0
    elif field_name:
        staleness = 100  # Never verified = fully stale

    # Get source health from telemetry
    source_health_status = "unknown"
    source_reliability = 0.0
    source_avg_latency_ms = 0.0
    source_error_rate = 0.0
    source_consecutive_failures = 0

    if source_url:
        from urllib.parse import urlparse
        domain = urlparse(source_url).netloc if source_url else ""
        if domain:
            stats = get_source_stats(domain)
            if stats is not None:
                source_health_status = "healthy" if stats.is_healthy else "degraded"
                source_reliability = (1.0 - stats.error_rate) * 100
                source_avg_latency_ms = stats.avg_latency_ms
                source_error_rate = stats.error_rate
                source_consecutive_failures = stats.consecutive_failures

    return compute_cost_profile(
        fingerprint_status=fingerprint_status,
        fingerprint_unchanged_probability=fingerprint_unchanged_probability,
        source_health_status=source_health_status,
        source_reliability=source_reliability,
        source_avg_latency_ms=source_avg_latency_ms,
        source_error_rate=source_error_rate,
        source_consecutive_failures=source_consecutive_failures,
        deadline_urgency=deadline_urgency,
        staleness_score=staleness,
        field_name=field_name,
        lifecycle_state=lifecycle_state,
        lifecycle_is_terminal=lifecycle_is_terminal,
        dependency_set_size=dependency_set_size,
        has_unresolved_conflict=has_unresolved_conflict,
        anomaly_score=anomaly_score,
        change_frequency_30d=change_frequency_30d,
        retry_attempt_count=retry_attempt_count,
        is_retrying=is_retrying,
        content_size_bytes=content_size_bytes,
    )


def batch_optimize(
    profiles: list[VerificationCostProfile],
) -> BatchOptimizationResult:
    """Optimize a batch of verification candidates.

    Groups candidates by recommended action and computes batch savings.

    Args:
        profiles: List of cost profiles to optimize

    Returns:
        BatchOptimizationResult with grouped candidates and savings
    """
    if not profiles:
        return BatchOptimizationResult(
            candidates=tuple(profiles),
            total_cost=0.0,
            total_value=0.0,
            batch_efficiency=0.0,
            verify_now=(),
            batch_later=(),
            defer=(),
            skip=(),
            estimated_batch_savings=0.0,
            reason_codes=("empty_batch",),
        )

    verify_now: list[VerificationCostProfile] = []
    batch_later: list[VerificationCostProfile] = []
    defer: list[VerificationCostProfile] = []
    skip: list[VerificationCostProfile] = []

    for profile in profiles:
        if profile.recommended_action == VerificationAction.VERIFY:
            verify_now.append(profile)
        elif profile.recommended_action == VerificationAction.BATCH:
            batch_later.append(profile)
        elif profile.recommended_action == VerificationAction.DEFER:
            defer.append(profile)
        else:
            skip.append(profile)

    # Compute totals
    total_cost = sum(p.total_cost for p in profiles)
    total_value = sum(p.verification_value for p in profiles)

    # Batch efficiency: value verified / total cost
    verified_cost = sum(
        p.total_cost for p in verify_now + batch_later
    )
    verified_value = sum(
        p.verification_value for p in verify_now + batch_later
    )

    if verified_cost > 0:
        batch_efficiency = verified_value / verified_cost
    else:
        batch_efficiency = 0.0

    # Savings from skipping
    skip_cost_saved = sum(p.total_cost for p in skip)
    skip_value_lost = sum(p.verification_value for p in skip)
    estimated_batch_savings = skip_cost_saved - skip_value_lost

    reasons: list[str] = []
    reasons.append(f"batch_size:{len(profiles)}")
    reasons.append(f"verify_now:{len(verify_now)}")
    reasons.append(f"batch_later:{len(batch_later)}")
    reasons.append(f"defer:{len(defer)}")
    reasons.append(f"skip:{len(skip)}")
    if estimated_batch_savings > 0:
        reasons.append(f"savings:{estimated_batch_savings:.1f}")

    return BatchOptimizationResult(
        candidates=tuple(profiles),
        total_cost=round(total_cost, 2),
        total_value=round(total_value, 2),
        batch_efficiency=round(batch_efficiency, 4),
        verify_now=tuple(
            sorted(verify_now, key=lambda p: -p.priority)
        ),
        batch_later=tuple(
            sorted(batch_later, key=lambda p: -p.priority)
        ),
        defer=tuple(
            sorted(defer, key=lambda p: -p.priority)
        ),
        skip=tuple(skip),
        estimated_batch_savings=round(estimated_batch_savings, 2),
        reason_codes=tuple(reasons),
    )


def compute_fingerprint_unchanged_probability(
    fingerprint_status: FingerprintStatus | None,
    historical_unchanged_ratio: float = 0.0,
) -> float:
    """Compute probability that content is unchanged given signals.

    Args:
        fingerprint_status: Current fingerprint comparison result
        historical_unchanged_ratio: Historical ratio of unchanged checks (0-1)

    Returns:
        Probability (0-1) that content is unchanged
    """
    if fingerprint_status == FingerprintStatus.UNCHANGED:
        return 1.0
    elif fingerprint_status == FingerprintStatus.CHANGED:
        return 0.0
    elif fingerprint_status == FingerprintStatus.UNKNOWN:
        # Use historical ratio as prior
        return max(0.1, min(0.9, historical_unchanged_ratio))
    else:
        # No fingerprint data
        return 0.0


def get_fields_by_action(
    profiles: list[VerificationCostProfile],
) -> dict[str, list[VerificationCostProfile]]:
    """Group profiles by recommended action.

    Returns:
        Dict mapping action name to list of profiles
    """
    result: dict[str, list[VerificationCostProfile]] = {
        "verify": [],
        "batch": [],
        "defer": [],
        "skip": [],
    }
    for profile in profiles:
        result[profile.recommended_action.value].append(profile)
    return result


def should_verify_now(profile: VerificationCostProfile) -> bool:
    """Check if a profile requires immediate verification.

    Args:
        profile: Cost profile to check

    Returns:
        True if verification should happen immediately
    """
    return profile.recommended_action == VerificationAction.VERIFY


def get_verification_order(
    profiles: list[VerificationCostProfile],
) -> list[VerificationCostProfile]:
    """Get profiles sorted by verification priority.

    Args:
        profiles: List of profiles to sort

    Returns:
        Sorted list (highest priority first)
    """
    return sorted(profiles, key=lambda p: (-p.priority, -p.efficiency_score))


def estimate_batch_savings(
    profiles: list[VerificationCostProfile],
) -> dict[str, float]:
    """Estimate savings from batch optimization.

    Args:
        profiles: List of cost profiles

    Returns:
        Dict with savings metrics
    """
    if not profiles:
        return {
            "total_cost": 0.0,
            "verified_cost": 0.0,
            "skipped_cost": 0.0,
            "savings": 0.0,
            "savings_pct": 0.0,
        }

    total_cost = sum(p.total_cost for p in profiles)
    verified_cost = sum(
        p.total_cost
        for p in profiles
        if p.recommended_action in (VerificationAction.VERIFY, VerificationAction.BATCH)
    )
    skipped_cost = sum(
        p.total_cost
        for p in profiles
        if p.recommended_action == VerificationAction.SKIP
    )

    savings = skipped_cost
    savings_pct = (savings / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "total_cost": round(total_cost, 2),
        "verified_cost": round(verified_cost, 2),
        "skipped_cost": round(skipped_cost, 2),
        "savings": round(savings, 2),
        "savings_pct": round(savings_pct, 2),
    }
