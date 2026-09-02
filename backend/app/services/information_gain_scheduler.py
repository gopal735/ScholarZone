"""Information-gain driven verification scheduling intelligence.

Ranks verification candidates by expected information value,
while preserving all existing safety, freshness, retry, cost, and priority rules.

Design principles:
- Deterministic: same inputs always produce same outputs
- Safety-first: never bypasses safety gates, freshness checks, retry rules
- No network calls: pure computation using existing signals
- No ML/LLM: rule-based arithmetic
- Batch-friendly: supports batch candidate scoring
- Low-latency: O(1) per candidate where possible
- No N+1: reuses already-available telemetry/history

Signals used:
- Fingerprint unchanged probability (inverse)
- Source health / reliability / latency
- Retry state
- Staleness / freshness gap
- Change impact / frequency
- Deadline urgency
- Dependency set size / unresolved deps
- Evidence consensus / conflict state
- Anomaly detection scores
- Confidence / verification state
- Lifecycle state
- Historical verification duration
- Source change frequency

Information gain increases when:
- data is stale/unknown
- recent changes are likely
- source is historically change-prone
- critical fields are uncertain
- conflicting/weak evidence exists
- deadline is approaching
- dependency fields are unresolved
- previous fingerprint/history suggests possible change

Information gain decreases when:
- recently verified
- stable over time
- highly redundant with already verified sources
- fingerprint strongly indicates unchanged
- source is temporarily unavailable

Core formula:
    information_gain
        × impact
        × urgency
        × uncertainty
        × source_reliability
        ÷ estimated_cost

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

Version: 1 (initial information-gain scheduler)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any

from .change_impact_staleness import (
    CRITICAL,
    FIELD_CRITICALITY,
    compute_change_impact,
    compute_deadline_urgency,
    compute_field_staleness,
    get_field_criticality,
    get_freshness_threshold,
)
from .content_fingerprinting import FingerprintStatus
from .dependency_graph import CriticalityLevel, analyze_dependencies


class InformationGainTier(str, Enum):
    """Tier classification for information gain."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


INFORMATION_GAIN_VERSION = "v1"

BASE_INFORMATION_GAIN = 30.0

IMPACT_WEIGHT = 0.25
URGENCY_WEIGHT = 0.20
UNCERTAINTY_WEIGHT = 0.20
SOURCE_RELIABILITY_WEIGHT = 0.15
COST_WEIGHT = 0.20

FINGERPRINT_HIGH_UNCHANGED_PROB = 0.9
FINGERPRINT_MEDIUM_UNCHANGED_PROB = 0.6

DEADLINE_CRITICAL_URGENCY = 80
DEADLINE_URGENT_URGENCY = 50

FRESHNESS_CRITICAL_STALENESS = 80
FRESHNESS_STALENESS = 50

HIGH_CHANGE_FREQUENCY_THRESHOLD = 5
MODERATE_CHANGE_FREQUENCY_THRESHOLD = 2

CONFLICT_PENALTY_THRESHOLD = 0.5
LOW_RELIABILITY_THRESHOLD = 40.0

SOURCE_UNHEALTHY_PENALTY = 0.6
SOURCE_DEGRADED_PENALTY = 0.8

REDUNDANCY_PENALTY_PER_SOURCE = 0.05
MAX_REDUNDANCY_PENALTY = 0.5

RECENCY_DECAY_HALF_LIFE_DAYS = 14.0

STABILITY_BONUS_THRESHOLD = 90

MIN_ESTIMATED_COST = 1.0
MAX_ESTIMATED_COST = 100.0

COST_NETWORK_WEIGHT = 0.30
COST_LATENCY_WEIGHT = 0.25
COST_COMPUTE_WEIGHT = 0.20
COST_DB_WEIGHT = 0.15
COST_SOURCE_LOAD_WEIGHT = 0.10

BASE_NETWORK_COST = 25.0
BASE_LATENCY_COST = 20.0
BASE_COMPUTE_COST = 15.0
BASE_DB_COST = 10.0
BASE_SOURCE_LOAD_COST = 8.0

TIER_CRITICAL_THRESHOLD = 80.0
TIER_HIGH_THRESHOLD = 60.0
TIER_MEDIUM_THRESHOLD = 40.0
TIER_LOW_THRESHOLD = 20.0


@dataclass(frozen=True)
class InformationGainProfile:
    """Complete information-gain profile for a verification candidate.

    Ranks the expected value of verifying a specific field/source,
    considering staleness, uncertainty, impact, urgency, and cost.
    """
    expected_information_gain: float
    uncertainty_score: float
    change_probability: float
    freshness_gap: float
    impact_score: float
    source_reliability: float
    redundancy_penalty: float
    estimated_cost: float
    efficiency: float
    priority: float
    reason_codes: tuple[str, ...]
    field_name: str
    field_criticality: str
    staleness_score: int
    deadline_urgency: int
    fingerprint_unchanged_probability: float
    source_health_status: str
    lifecycle_state: str
    dependency_set_size: int
    has_unresolved_conflict: bool
    anomaly_score: float
    confidence_level: str
    verification_state: str
    tier: InformationGainTier
    version: str = INFORMATION_GAIN_VERSION

    @property
    def should_verify(self) -> bool:
        """Check if verification is recommended based on information gain."""
        return self.tier in (
            InformationGainTier.CRITICAL,
            InformationGainTier.HIGH,
            InformationGainTier.MEDIUM,
        )

    @property
    def is_deferrable(self) -> bool:
        """Check if verification can be deferred."""
        return self.tier in (InformationGainTier.LOW, InformationGainTier.MINIMAL)

    @property
    def has_safety_concern(self) -> bool:
        """Check if there are safety concerns requiring immediate attention."""
        return (
            self.has_unresolved_conflict
            or self.anomaly_score >= 0.5
            or self.deadline_urgency >= DEADLINE_CRITICAL_URGENCY
            or self.field_criticality == CRITICAL
        )


@dataclass(frozen=True)
class _GainInputs:
    """Internal inputs for information gain computation."""
    field_name: str
    field_criticality: str
    staleness_score: int
    deadline_urgency: int
    fingerprint_unchanged_probability: float
    source_health_status: str
    source_reliability: float
    source_change_frequency_30d: int
    source_stability_score: float
    source_avg_latency_ms: float
    source_error_rate: float
    lifecycle_state: str
    lifecycle_is_terminal: bool
    dependency_set_size: int
    unresolved_dependency_count: int
    has_unresolved_conflict: bool
    anomaly_score: float
    confidence_level: str
    verification_state: str
    consensus_score: float
    redundant_verified_count: int
    last_verified_at: datetime | date | None
    change_frequency_30d: int
    historical_change_rate: float
    days_since_last_change: int | None
    content_size_bytes: int
    today: date | None = None


@dataclass(frozen=True)
class BatchRankingResult:
    """Result of batch ranking over multiple candidates."""
    candidates: tuple[InformationGainProfile, ...]
    total_information_gain: float
    total_cost: float
    average_efficiency: float
    critical_candidates: tuple[InformationGainProfile, ...]
    high_candidates: tuple[InformationGainProfile, ...]
    medium_candidates: tuple[InformationGainProfile, ...]
    low_candidates: tuple[InformationGainProfile, ...]
    minimal_candidates: tuple[InformationGainProfile, ...]
    ranked_order: tuple[InformationGainProfile, ...]
    reason_codes: tuple[str, ...]


def _compute_uncertainty_score(
    inputs: _GainInputs,
) -> float:
    """Compute uncertainty score (0-100).

    Higher = more uncertain = more potential information gain.
    """
    uncertainty = 0.0

    staleness_factor = inputs.staleness_score / 100.0
    uncertainty += staleness_factor * 30.0

    if inputs.fingerprint_unchanged_probability >= FINGERPRINT_HIGH_UNCHANGED_PROB:
        uncertainty += 5.0
    elif inputs.fingerprint_unchanged_probability >= FINGERPRINT_MEDIUM_UNCHANGED_PROB:
        uncertainty += 15.0
    elif inputs.fingerprint_unchanged_probability > 0:
        uncertainty += 25.0
    else:
        uncertainty += 35.0

    if inputs.verification_state == "uncertain":
        uncertainty += 20.0
    elif inputs.verification_state == "partially_verified":
        uncertainty += 10.0
    elif inputs.verification_state == "conflict":
        uncertainty += 25.0
    elif inputs.verification_state == "unsupported":
        uncertainty += 15.0

    if inputs.confidence_level == "low":
        uncertainty += 15.0
    elif inputs.confidence_level == "conflict":
        uncertainty += 20.0
    elif inputs.confidence_level == "medium":
        uncertainty += 5.0

    if inputs.has_unresolved_conflict:
        uncertainty += 15.0

    if inputs.consensus_score < 0.5:
        uncertainty += 10.0
    elif inputs.consensus_score < 0.8:
        uncertainty += 5.0

    if inputs.unresolved_dependency_count > 0:
        uncertainty += min(15.0, inputs.unresolved_dependency_count * 3.0)

    return min(100.0, uncertainty)


def _compute_change_probability(
    inputs: _GainInputs,
) -> float:
    """Compute probability of change (0-1).

    Higher = more likely to have changed = more information gain.
    """
    if inputs.fingerprint_unchanged_probability >= FINGERPRINT_HIGH_UNCHANGED_PROB:
        return 0.05
    elif inputs.fingerprint_unchanged_probability >= FINGERPRINT_MEDIUM_UNCHANGED_PROB:
        probability = 0.2
    elif inputs.fingerprint_unchanged_probability > 0:
        probability = 0.5
    else:
        probability = 0.7

    if inputs.source_change_frequency_30d >= HIGH_CHANGE_FREQUENCY_THRESHOLD:
        probability = max(probability, 0.8)
    elif inputs.source_change_frequency_30d >= MODERATE_CHANGE_FREQUENCY_THRESHOLD:
        probability = max(probability, 0.5)

    if inputs.change_frequency_30d >= HIGH_CHANGE_FREQUENCY_THRESHOLD:
        probability = max(probability, 0.75)
    elif inputs.change_frequency_30d >= MODERATE_CHANGE_FREQUENCY_THRESHOLD:
        probability = max(probability, 0.45)

    if inputs.source_stability_score < 30:
        probability = max(probability, 0.7)
    elif inputs.source_stability_score < 60:
        probability = max(probability, 0.5)
    elif inputs.source_stability_score >= STABILITY_BONUS_THRESHOLD:
        probability = min(probability, 0.3)

    if inputs.days_since_last_change is not None:
        if inputs.days_since_last_change <= 7:
            probability = max(probability, 0.6)
        elif inputs.days_since_last_change <= 30:
            probability = max(probability, 0.4)

    if inputs.historical_change_rate > 0.5:
        probability = max(probability, 0.7)
    elif inputs.historical_change_rate > 0.2:
        probability = max(probability, 0.5)

    if inputs.staleness_score >= FRESHNESS_CRITICAL_STALENESS:
        probability = max(probability, 0.6)
    elif inputs.staleness_score >= FRESHNESS_STALENESS:
        probability = max(probability, 0.4)

    return min(1.0, probability)


def _compute_freshness_gap(inputs: _GainInputs) -> float:
    """Compute freshness gap (0-100).

    Higher = bigger gap = more information gain from refreshing.
    """
    gap = float(inputs.staleness_score)

    threshold = get_freshness_threshold(inputs.field_name)
    if inputs.last_verified_at is not None:
        if isinstance(inputs.last_verified_at, datetime):
            last_date = inputs.last_verified_at.date()
        else:
            last_date = inputs.last_verified_at
        today = inputs.today or date.today()
        age_days = (today - last_date).days
        if age_days < 0:
            age_days = 0
        expected_gap = threshold * 0.5
        if expected_gap > 0:
            gap = max(gap, min(100.0, (age_days / expected_gap) * 50.0))
    elif inputs.field_name:
        gap = max(gap, 80.0)

    return min(100.0, gap)


def _compute_impact_score(inputs: _GainInputs) -> float:
    """Compute impact score (0-100).

    Higher = more impactful field = more information gain.
    """
    impact = 0.0

    if inputs.field_criticality == CRITICAL:
        impact = 100.0
    elif inputs.field_criticality == "high":
        impact = 70.0
    elif inputs.field_criticality == "medium":
        impact = 40.0
    else:
        impact = 15.0

    if inputs.dependency_set_size > 5:
        impact = min(100.0, impact * 1.3)
    elif inputs.dependency_set_size > 2:
        impact = min(100.0, impact * 1.15)

    if inputs.unresolved_dependency_count > 0:
        impact = min(100.0, impact * (1.0 + inputs.unresolved_dependency_count * 0.05))

    if inputs.lifecycle_state in ("deadline_near", "application_open"):
        impact = min(100.0, impact * 1.2)
    elif inputs.lifecycle_state == "discovered":
        impact = min(100.0, impact * 1.1)

    return impact


def _compute_source_reliability(inputs: _GainInputs) -> float:
    """Compute source reliability factor (0-1).

    Higher = more reliable = more trustworthy information gain.
    """
    if inputs.source_reliability > 0:
        reliability = inputs.source_reliability / 100.0
    else:
        if inputs.source_health_status == "healthy":
            reliability = 0.8
        elif inputs.source_health_status == "degraded":
            reliability = 0.5
        elif inputs.source_health_status == "unhealthy":
            reliability = 0.2
        else:
            reliability = 0.5

    if inputs.source_health_status == "unhealthy":
        reliability *= SOURCE_UNHEALTHY_PENALTY
    elif inputs.source_health_status == "degraded":
        reliability *= SOURCE_DEGRADED_PENALTY

    if inputs.source_error_rate > 0.5:
        reliability *= 0.5
    elif inputs.source_error_rate > 0.3:
        reliability *= 0.7
    elif inputs.source_error_rate > 0.1:
        reliability *= 0.9

    if inputs.source_avg_latency_ms > 5000:
        reliability *= 0.8
    elif inputs.source_avg_latency_ms > 2000:
        reliability *= 0.9

    return max(0.0, min(1.0, reliability))


def _compute_redundancy_penalty(inputs: _GainInputs) -> float:
    """Compute redundancy penalty (0-1).

    Higher = more redundant = less unique information gain.
    """
    penalty = 0.0

    penalty += inputs.redundant_verified_count * REDUNDANCY_PENALTY_PER_SOURCE
    penalty = min(MAX_REDUNDANCY_PENALTY, penalty)

    if inputs.consensus_score > 0.9 and inputs.redundant_verified_count >= 2:
        penalty = max(penalty, 0.3)

    if inputs.verification_state == "verified" and inputs.confidence_level == "high":
        penalty = max(penalty, 0.25)

    return min(MAX_REDUNDANCY_PENALTY, penalty)


def _compute_estimated_cost(inputs: _GainInputs) -> float:
    """Compute estimated cost for verification.

    Lower = cheaper = higher efficiency.
    """
    network_cost = BASE_NETWORK_COST
    latency_cost = BASE_LATENCY_COST
    compute_cost = BASE_COMPUTE_COST
    db_cost = BASE_DB_COST
    source_load_cost = BASE_SOURCE_LOAD_COST

    if inputs.source_avg_latency_ms > 5000:
        latency_cost *= 1.5
        network_cost *= 1.3
    elif inputs.source_avg_latency_ms > 2000:
        latency_cost *= 1.2
        network_cost *= 1.1
    elif inputs.source_avg_latency_ms > 0:
        latency_cost *= 0.8

    if inputs.source_error_rate > 0.3:
        network_cost *= 1.0 + inputs.source_error_rate
        latency_cost *= 1.0 + inputs.source_error_rate * 0.5

    if inputs.source_health_status == "unhealthy":
        network_cost *= 1.5
        source_load_cost *= 1.8
    elif inputs.source_health_status == "degraded":
        network_cost *= 1.2
        source_load_cost *= 1.3

    if inputs.dependency_set_size > 5:
        compute_cost *= 1.4
        db_cost *= 1.3
    elif inputs.dependency_set_size > 2:
        compute_cost *= 1.2
        db_cost *= 1.1

    if inputs.content_size_bytes > 100000:
        compute_cost *= 1.3
        network_cost *= 1.2
    elif inputs.content_size_bytes > 10000:
        compute_cost *= 1.1

    total_cost = (
        network_cost * COST_NETWORK_WEIGHT
        + latency_cost * COST_LATENCY_WEIGHT
        + compute_cost * COST_COMPUTE_WEIGHT
        + db_cost * COST_DB_WEIGHT
        + source_load_cost * COST_SOURCE_LOAD_WEIGHT
    )

    return max(MIN_ESTIMATED_COST, min(MAX_ESTIMATED_COST, total_cost))


def _compute_information_gain(
    inputs: _GainInputs,
) -> float:
    """Compute expected information gain.

    Core formula:
        information_gain
            × impact
            × urgency
            × uncertainty
            × source_reliability
            ÷ estimated_cost
    """
    uncertainty = _compute_uncertainty_score(inputs)
    change_prob = _compute_change_probability(inputs)
    freshness_gap = _compute_freshness_gap(inputs)
    impact = _compute_impact_score(inputs)
    source_reliability = _compute_source_reliability(inputs)
    redundancy_penalty = _compute_redundancy_penalty(inputs)
    estimated_cost = _compute_estimated_cost(inputs)

    base_gain = BASE_INFORMATION_GAIN

    change_factor = 0.3 + change_prob * 0.7

    freshness_factor = 0.2 + (freshness_gap / 100.0) * 0.8

    urgency_factor = 0.3
    if inputs.deadline_urgency >= DEADLINE_CRITICAL_URGENCY:
        urgency_factor = 1.0
    elif inputs.deadline_urgency >= DEADLINE_URGENT_URGENCY:
        urgency_factor = 0.7
    elif inputs.deadline_urgency > 0:
        urgency_factor = 0.5

    impact_factor = impact / 100.0

    uncertainty_factor = uncertainty / 100.0

    source_factor = 0.3 + source_reliability * 0.7

    anomaly_factor = 1.0 + inputs.anomaly_score * 0.5

    raw_gain = (
        base_gain
        * (1.0 + impact_factor * IMPACT_WEIGHT)
        * (1.0 + urgency_factor * URGENCY_WEIGHT)
        * (1.0 + uncertainty_factor * UNCERTAINTY_WEIGHT)
        * (0.5 + source_factor * SOURCE_RELIABILITY_WEIGHT)
        * change_factor
        * freshness_factor
        * anomaly_factor
    )

    cost_factor = max(MIN_ESTIMATED_COST, estimated_cost) / MAX_ESTIMATED_COST
    cost_adjusted_gain = raw_gain / (0.5 + cost_factor * 0.5)

    redundancy_adjusted = cost_adjusted_gain * (1.0 - redundancy_penalty)

    if inputs.lifecycle_is_terminal:
        redundancy_adjusted *= 0.1

    return max(0.0, redundancy_adjusted)


def _compute_efficiency(information_gain: float, estimated_cost: float) -> float:
    """Compute efficiency as information gain per unit cost."""
    cost = max(MIN_ESTIMATED_COST, estimated_cost)
    return information_gain / cost


def _compute_priority(inputs: _GainInputs, information_gain: float) -> float:
    """Compute priority score combining information gain with safety factors."""
    priority = information_gain * 0.5

    if inputs.deadline_urgency >= DEADLINE_CRITICAL_URGENCY:
        priority += 30.0
    elif inputs.deadline_urgency >= DEADLINE_URGENT_URGENCY:
        priority += 20.0
    elif inputs.deadline_urgency > 0:
        priority += 10.0

    if inputs.has_unresolved_conflict:
        priority += 15.0

    if inputs.anomaly_score >= 0.7:
        priority += 20.0
    elif inputs.anomaly_score >= 0.5:
        priority += 10.0

    if inputs.field_criticality == CRITICAL:
        priority += 15.0
    elif inputs.field_criticality == "high":
        priority += 8.0

    if inputs.unresolved_dependency_count > 0:
        priority += min(10.0, inputs.unresolved_dependency_count * 2.0)

    if inputs.staleness_score >= FRESHNESS_CRITICAL_STALENESS:
        priority += 10.0

    return min(100.0, priority)


def _determine_tier(information_gain: float, inputs: _GainInputs) -> InformationGainTier:
    """Determine the information gain tier."""
    adjusted_gain = information_gain

    if inputs.deadline_urgency >= DEADLINE_CRITICAL_URGENCY:
        adjusted_gain = max(adjusted_gain, 70.0)

    if inputs.has_unresolved_conflict:
        adjusted_gain = max(adjusted_gain, 60.0)

    if inputs.anomaly_score >= 0.7:
        adjusted_gain = max(adjusted_gain, 65.0)

    if inputs.field_criticality == CRITICAL and inputs.staleness_score >= FRESHNESS_STALENESS:
        adjusted_gain = max(adjusted_gain, 60.0)

    if adjusted_gain >= TIER_CRITICAL_THRESHOLD:
        return InformationGainTier.CRITICAL
    elif adjusted_gain >= TIER_HIGH_THRESHOLD:
        return InformationGainTier.HIGH
    elif adjusted_gain >= TIER_MEDIUM_THRESHOLD:
        return InformationGainTier.MEDIUM
    elif adjusted_gain >= TIER_LOW_THRESHOLD:
        return InformationGainTier.LOW
    else:
        return InformationGainTier.MINIMAL


def _build_reason_codes(
    inputs: _GainInputs,
    information_gain: float,
    uncertainty: float,
    change_prob: float,
    tier: InformationGainTier,
) -> list[str]:
    """Build reason codes explaining the information gain score."""
    reasons: list[str] = []

    if inputs.staleness_score >= FRESHNESS_CRITICAL_STALENESS:
        reasons.append(f"critical_staleness:{inputs.staleness_score}")
    elif inputs.staleness_score >= FRESHNESS_STALENESS:
        reasons.append(f"stale_data:{inputs.staleness_score}")

    if inputs.deadline_urgency >= DEADLINE_CRITICAL_URGENCY:
        reasons.append(f"deadline_critical:{inputs.deadline_urgency}")
    elif inputs.deadline_urgency >= DEADLINE_URGENT_URGENCY:
        reasons.append(f"deadline_urgent:{inputs.deadline_urgency}")

    if inputs.fingerprint_unchanged_probability < 0.3:
        reasons.append("fingerprint_suggests_change")
    elif inputs.fingerprint_unchanged_probability < 0.6:
        reasons.append("fingerprint_uncertain")

    if inputs.source_change_frequency_30d >= HIGH_CHANGE_FREQUENCY_THRESHOLD:
        reasons.append(f"change_prone_source:{inputs.source_change_frequency_30d}")
    elif inputs.source_change_frequency_30d >= MODERATE_CHANGE_FREQUENCY_THRESHOLD:
        reasons.append(f"moderate_change_source:{inputs.source_change_frequency_30d}")

    if uncertainty >= 70:
        reasons.append(f"high_uncertainty:{uncertainty:.0f}")
    elif uncertainty >= 50:
        reasons.append(f"moderate_uncertainty:{uncertainty:.0f}")

    if inputs.has_unresolved_conflict:
        reasons.append("unresolved_conflict")

    if inputs.anomaly_score >= 0.5:
        reasons.append(f"anomaly_detected:{inputs.anomaly_score:.2f}")

    if inputs.unresolved_dependency_count > 0:
        reasons.append(f"unresolved_deps:{inputs.unresolved_dependency_count}")

    if inputs.verification_state in ("uncertain", "conflict"):
        reasons.append(f"low_confidence_state:{inputs.verification_state}")

    if inputs.field_criticality == CRITICAL:
        reasons.append("critical_field")
    elif inputs.field_criticality == "high":
        reasons.append("high_impact_field")

    if inputs.redundant_verified_count >= 2:
        reasons.append(f"redundant_verified:{inputs.redundant_verified_count}")

    if inputs.lifecycle_state == "discovered":
        reasons.append("newly_discovered")

    reasons.append(f"tier:{tier.value}")
    reasons.append(f"gain:{information_gain:.1f}")

    return reasons


def _build_gain_inputs(
    field_name: str = "",
    field_criticality: str | None = None,
    staleness_score: int = 0,
    deadline_urgency: int = 0,
    fingerprint_unchanged_probability: float = 0.0,
    source_health_status: str = "unknown",
    source_reliability: float = 0.0,
    source_change_frequency_30d: int = 0,
    source_stability_score: float = 50.0,
    source_avg_latency_ms: float = 0.0,
    source_error_rate: float = 0.0,
    lifecycle_state: str = "unknown",
    lifecycle_is_terminal: bool = False,
    dependency_set_size: int = 0,
    unresolved_dependency_count: int = 0,
    has_unresolved_conflict: bool = False,
    anomaly_score: float = 0.0,
    confidence_level: str = "medium",
    verification_state: str = "partially_verified",
    consensus_score: float = 0.5,
    redundant_verified_count: int = 0,
    last_verified_at: datetime | date | None = None,
    change_frequency_30d: int = 0,
    historical_change_rate: float = 0.0,
    days_since_last_change: int | None = None,
    content_size_bytes: int = 0,
    today: date | None = None,
) -> _GainInputs:
    """Build _GainInputs from individual parameters."""
    if field_criticality is None:
        field_criticality = get_field_criticality(field_name)

    return _GainInputs(
        field_name=field_name,
        field_criticality=field_criticality,
        staleness_score=staleness_score,
        deadline_urgency=deadline_urgency,
        fingerprint_unchanged_probability=fingerprint_unchanged_probability,
        source_health_status=source_health_status,
        source_reliability=source_reliability,
        source_change_frequency_30d=source_change_frequency_30d,
        source_stability_score=source_stability_score,
        source_avg_latency_ms=source_avg_latency_ms,
        source_error_rate=source_error_rate,
        lifecycle_state=lifecycle_state,
        lifecycle_is_terminal=lifecycle_is_terminal,
        dependency_set_size=dependency_set_size,
        unresolved_dependency_count=unresolved_dependency_count,
        has_unresolved_conflict=has_unresolved_conflict,
        anomaly_score=anomaly_score,
        confidence_level=confidence_level,
        verification_state=verification_state,
        consensus_score=consensus_score,
        redundant_verified_count=redundant_verified_count,
        last_verified_at=last_verified_at,
        change_frequency_30d=change_frequency_30d,
        historical_change_rate=historical_change_rate,
        days_since_last_change=days_since_last_change,
        content_size_bytes=content_size_bytes,
        today=today,
    )


def compute_information_gain(
    field_name: str = "",
    field_criticality: str | None = None,
    staleness_score: int = 0,
    deadline_urgency: int = 0,
    fingerprint_unchanged_probability: float = 0.0,
    source_health_status: str = "unknown",
    source_reliability: float = 0.0,
    source_change_frequency_30d: int = 0,
    source_stability_score: float = 50.0,
    source_avg_latency_ms: float = 0.0,
    source_error_rate: float = 0.0,
    lifecycle_state: str = "unknown",
    lifecycle_is_terminal: bool = False,
    dependency_set_size: int = 0,
    unresolved_dependency_count: int = 0,
    has_unresolved_conflict: bool = False,
    anomaly_score: float = 0.0,
    confidence_level: str = "medium",
    verification_state: str = "partially_verified",
    consensus_score: float = 0.5,
    redundant_verified_count: int = 0,
    last_verified_at: datetime | date | None = None,
    change_frequency_30d: int = 0,
    historical_change_rate: float = 0.0,
    days_since_last_change: int | None = None,
    content_size_bytes: int = 0,
    today: date | None = None,
) -> InformationGainProfile:
    """Compute the full information-gain profile for a verification candidate.

    This is the main entry point for single-candidate information-gain scoring.

    Args:
        field_name: Name of the field being verified
        field_criticality: Override criticality (auto-detected if None)
        staleness_score: Field staleness score (0-100)
        deadline_urgency: Deadline urgency score (0-100)
        fingerprint_unchanged_probability: Probability content is unchanged (0-1)
        source_health_status: Health status of source
        source_reliability: Reliability score (0-100)
        source_change_frequency_30d: Changes in source in last 30 days
        source_stability_score: Stability score of source (0-100)
        source_avg_latency_ms: Average source latency in ms
        source_error_rate: Error rate (0-1)
        lifecycle_state: Current lifecycle state
        lifecycle_is_terminal: Whether lifecycle is terminal
        dependency_set_size: Number of fields depending on this field
        unresolved_dependency_count: Number of unresolved dependencies
        has_unresolved_conflict: Whether there's an unresolved conflict
        anomaly_score: Anomaly detection score (0-1)
        confidence_level: Current confidence level
        verification_state: Current verification state
        consensus_score: Evidence consensus score (0-1)
        redundant_verified_count: Number of already-verified redundant sources
        last_verified_at: When field was last verified
        change_frequency_30d: Changes in this field in last 30 days
        historical_change_rate: Historical rate of change (0-1)
        days_since_last_change: Days since last change
        content_size_bytes: Size of content to fetch/process
        today: Optional date override for testing

    Returns:
        InformationGainProfile with gain scores and tier
    """
    inputs = _build_gain_inputs(
        field_name=field_name,
        field_criticality=field_criticality,
        staleness_score=staleness_score,
        deadline_urgency=deadline_urgency,
        fingerprint_unchanged_probability=fingerprint_unchanged_probability,
        source_health_status=source_health_status,
        source_reliability=source_reliability,
        source_change_frequency_30d=source_change_frequency_30d,
        source_stability_score=source_stability_score,
        source_avg_latency_ms=source_avg_latency_ms,
        source_error_rate=source_error_rate,
        lifecycle_state=lifecycle_state,
        lifecycle_is_terminal=lifecycle_is_terminal,
        dependency_set_size=dependency_set_size,
        unresolved_dependency_count=unresolved_dependency_count,
        has_unresolved_conflict=has_unresolved_conflict,
        anomaly_score=anomaly_score,
        confidence_level=confidence_level,
        verification_state=verification_state,
        consensus_score=consensus_score,
        redundant_verified_count=redundant_verified_count,
        last_verified_at=last_verified_at,
        change_frequency_30d=change_frequency_30d,
        historical_change_rate=historical_change_rate,
        days_since_last_change=days_since_last_change,
        content_size_bytes=content_size_bytes,
        today=today,
    )

    information_gain = _compute_information_gain(inputs)
    uncertainty = _compute_uncertainty_score(inputs)
    change_prob = _compute_change_probability(inputs)
    freshness_gap = _compute_freshness_gap(inputs)
    impact = _compute_impact_score(inputs)
    source_reliability = _compute_source_reliability(inputs)
    redundancy_penalty = _compute_redundancy_penalty(inputs)
    estimated_cost = _compute_estimated_cost(inputs)
    efficiency = _compute_efficiency(information_gain, estimated_cost)
    priority = _compute_priority(inputs, information_gain)
    tier = _determine_tier(information_gain, inputs)
    reasons = _build_reason_codes(inputs, information_gain, uncertainty, change_prob, tier)

    return InformationGainProfile(
        expected_information_gain=round(information_gain, 2),
        uncertainty_score=round(uncertainty, 2),
        change_probability=round(change_prob, 4),
        freshness_gap=round(freshness_gap, 2),
        impact_score=round(impact, 2),
        source_reliability=round(source_reliability, 4),
        redundancy_penalty=round(redundancy_penalty, 4),
        estimated_cost=round(estimated_cost, 2),
        efficiency=round(efficiency, 4),
        priority=round(priority, 2),
        reason_codes=tuple(reasons),
        field_name=field_name,
        field_criticality=inputs.field_criticality,
        staleness_score=staleness_score,
        deadline_urgency=deadline_urgency,
        fingerprint_unchanged_probability=fingerprint_unchanged_probability,
        source_health_status=source_health_status,
        lifecycle_state=lifecycle_state,
        dependency_set_size=dependency_set_size,
        has_unresolved_conflict=has_unresolved_conflict,
        anomaly_score=anomaly_score,
        confidence_level=confidence_level,
        verification_state=verification_state,
        tier=tier,
    )


def compute_gain_from_candidate(
    field_name: str,
    fingerprint_status: FingerprintStatus | None = None,
    fingerprint_unchanged_probability: float = 0.0,
    source_url: str | None = None,
    deadline_date: date | datetime | None = None,
    last_verified_at: datetime | date | None = None,
    lifecycle_state: str = "unknown",
    lifecycle_is_terminal: bool = False,
    dependency_set_size: int = 0,
    unresolved_dependency_count: int = 0,
    has_unresolved_conflict: bool = False,
    anomaly_score: float = 0.0,
    confidence_level: str = "medium",
    verification_state: str = "partially_verified",
    consensus_score: float = 0.5,
    redundant_verified_count: int = 0,
    change_frequency_30d: int = 0,
    historical_change_rate: float = 0.0,
    days_since_last_change: int | None = None,
    content_size_bytes: int = 0,
    today: date | None = None,
) -> InformationGainProfile:
    """Compute information gain from a candidate with automatic signal derivation.

    This convenience function derives signals (deadline urgency, staleness,
    source health) from the provided data, then computes the full profile.
    """
    if today is None:
        today = date.today()

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
        staleness = 100

    source_health_status = "unknown"
    source_reliability = 0.0
    source_avg_latency_ms = 0.0
    source_error_rate = 0.0
    source_change_frequency_30d = 0

    if source_url:
        from urllib.parse import urlparse
        domain = urlparse(source_url).netloc if source_url else ""
        if domain:
            from .telemetry import get_source_stats
            stats = get_source_stats(domain)
            if stats is not None:
                source_health_status = "healthy" if stats.is_healthy else "degraded"
                source_reliability = (1.0 - stats.error_rate) * 100
                source_avg_latency_ms = stats.avg_latency_ms
                source_error_rate = stats.error_rate

    return compute_information_gain(
        field_name=field_name,
        staleness_score=staleness,
        deadline_urgency=deadline_urgency,
        fingerprint_unchanged_probability=fingerprint_unchanged_probability,
        source_health_status=source_health_status,
        source_reliability=source_reliability,
        source_change_frequency_30d=source_change_frequency_30d,
        source_avg_latency_ms=source_avg_latency_ms,
        source_error_rate=source_error_rate,
        lifecycle_state=lifecycle_state,
        lifecycle_is_terminal=lifecycle_is_terminal,
        dependency_set_size=dependency_set_size,
        unresolved_dependency_count=unresolved_dependency_count,
        has_unresolved_conflict=has_unresolved_conflict,
        anomaly_score=anomaly_score,
        confidence_level=confidence_level,
        verification_state=verification_state,
        consensus_score=consensus_score,
        redundant_verified_count=redundant_verified_count,
        last_verified_at=last_verified_at,
        change_frequency_30d=change_frequency_30d,
        historical_change_rate=historical_change_rate,
        days_since_last_change=days_since_last_change,
        content_size_bytes=content_size_bytes,
        today=today,
    )


def batch_rank_candidates(
    profiles: list[InformationGainProfile],
) -> BatchRankingResult:
    """Rank a batch of verification candidates by information gain.

    Groups candidates by tier and computes aggregate metrics.

    Args:
        profiles: List of information-gain profiles to rank

    Returns:
        BatchRankingResult with grouped candidates and rankings
    """
    if not profiles:
        return BatchRankingResult(
            candidates=tuple(profiles),
            total_information_gain=0.0,
            total_cost=0.0,
            average_efficiency=0.0,
            critical_candidates=(),
            high_candidates=(),
            medium_candidates=(),
            low_candidates=(),
            minimal_candidates=(),
            ranked_order=(),
            reason_codes=("empty_batch",),
        )

    critical: list[InformationGainProfile] = []
    high: list[InformationGainProfile] = []
    medium: list[InformationGainProfile] = []
    low: list[InformationGainProfile] = []
    minimal: list[InformationGainProfile] = []

    for profile in profiles:
        if profile.tier == InformationGainTier.CRITICAL:
            critical.append(profile)
        elif profile.tier == InformationGainTier.HIGH:
            high.append(profile)
        elif profile.tier == InformationGainTier.MEDIUM:
            medium.append(profile)
        elif profile.tier == InformationGainTier.LOW:
            low.append(profile)
        else:
            minimal.append(profile)

    ranked = sorted(
        profiles,
        key=lambda p: (-p.priority, -p.expected_information_gain, -p.efficiency),
    )

    total_gain = sum(p.expected_information_gain for p in profiles)
    total_cost = sum(p.estimated_cost for p in profiles)
    avg_efficiency = (
        sum(p.efficiency for p in profiles) / len(profiles)
        if profiles
        else 0.0
    )

    reasons: list[str] = []
    reasons.append(f"batch_size:{len(profiles)}")
    reasons.append(f"critical:{len(critical)}")
    reasons.append(f"high:{len(high)}")
    reasons.append(f"medium:{len(medium)}")
    reasons.append(f"low:{len(low)}")
    reasons.append(f"minimal:{len(minimal)}")
    reasons.append(f"total_gain:{total_gain:.1f}")

    return BatchRankingResult(
        candidates=tuple(profiles),
        total_information_gain=round(total_gain, 2),
        total_cost=round(total_cost, 2),
        average_efficiency=round(avg_efficiency, 4),
        critical_candidates=tuple(
            sorted(critical, key=lambda p: (-p.priority, -p.expected_information_gain))
        ),
        high_candidates=tuple(
            sorted(high, key=lambda p: (-p.priority, -p.expected_information_gain))
        ),
        medium_candidates=tuple(
            sorted(medium, key=lambda p: (-p.priority, -p.expected_information_gain))
        ),
        low_candidates=tuple(
            sorted(low, key=lambda p: (-p.priority, -p.expected_information_gain))
        ),
        minimal_candidates=tuple(minimal),
        ranked_order=tuple(ranked),
        reason_codes=tuple(reasons),
    )


def get_verification_order(
    profiles: list[InformationGainProfile],
) -> list[InformationGainProfile]:
    """Get profiles sorted by verification priority.

    Args:
        profiles: List of profiles to sort

    Returns:
        Sorted list (highest priority first)
    """
    return sorted(
        profiles,
        key=lambda p: (-p.priority, -p.expected_information_gain, -p.efficiency),
    )


def get_candidates_by_tier(
    profiles: list[InformationGainProfile],
) -> dict[str, list[InformationGainProfile]]:
    """Group profiles by tier.

    Returns:
        Dict mapping tier name to list of profiles
    """
    result: dict[str, list[InformationGainProfile]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
        "minimal": [],
    }
    for profile in profiles:
        result[profile.tier.value].append(profile)
    return result


def should_verify_by_information_gain(
    profile: InformationGainProfile,
    min_gain_threshold: float = 20.0,
) -> bool:
    """Check if a profile warrants verification based on information gain.

    Args:
        profile: Information-gain profile to check
        min_gain_threshold: Minimum information gain to warrant verification

    Returns:
        True if verification is recommended
    """
    if profile.has_safety_concern:
        return True

    if profile.expected_information_gain >= min_gain_threshold:
        return True

    return profile.tier in (
        InformationGainTier.CRITICAL,
        InformationGainTier.HIGH,
    )


def estimate_information_value(
    profiles: list[InformationGainProfile],
) -> dict[str, float]:
    """Estimate aggregate information value from a batch of profiles.

    Args:
        profiles: List of information-gain profiles

    Returns:
        Dict with aggregate value metrics
    """
    if not profiles:
        return {
            "total_information_gain": 0.0,
            "total_cost": 0.0,
            "net_value": 0.0,
            "average_efficiency": 0.0,
            "verify_count": 0,
            "defer_count": 0,
        }

    total_gain = sum(p.expected_information_gain for p in profiles)
    total_cost = sum(p.estimated_cost for p in profiles)
    avg_efficiency = total_gain / len(profiles) if profiles else 0.0

    verify_count = sum(1 for p in profiles if p.should_verify)
    defer_count = sum(1 for p in profiles if p.is_deferrable)

    return {
        "total_information_gain": round(total_gain, 2),
        "total_cost": round(total_cost, 2),
        "net_value": round(total_gain - total_cost, 2),
        "average_efficiency": round(avg_efficiency, 4),
        "verify_count": verify_count,
        "defer_count": defer_count,
    }   