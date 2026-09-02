"""Source consensus and evidence arbitration engine.

When multiple official sources provide different values for the same scholarship
field, this module determines:
- Which evidence should be trusted (the winner)
- Whether consensus exists across sources
- Whether the field must be escalated to human review

Design principles:
- Deterministic: same inputs always produce same outputs
- Explainable: every decision includes reason codes
- Non-destructive: never mutates source evidence
- Safety-first: conflicts between authoritative sources escalate to review
- Low-latency: no network calls, reuses collected evidence

Authority hierarchy (highest to lowest):
    OFFICIAL_SCHOLARSHIP_PROGRAM > OFFICIAL_APPLICATION_PORTAL >
    OFFICIAL_UNIVERSITY > OFFICIAL_GOVERNMENT > THIRD_PARTY

Decision types:
    CONSENSUS: Multiple authoritative sources agree on the value
    SINGLE_TRUSTED_SOURCE: One authoritative source, no conflict
    CONFLICT: Authoritative sources disagree (escalates to review)
    INSUFFICIENT: No authoritative evidence available
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from .scholarship_evidence import (
    EvidenceItem,
    SourceType,
    is_authoritative_source,
)
from .verification_confidence import (
    _calculate_source_authority,
    _normalize_value,
    _values_agree,
)


class ArbitrationDecision(str, Enum):
    """The arbitration outcome for a field."""
    CONSENSUS = "consensus"
    SINGLE_TRUSTED_SOURCE = "single_trusted_source"
    CONFLICT = "conflict"
    INSUFFICIENT = "insufficient"


class ReasonCode(str, Enum):
    """Reason codes explaining the arbitration decision."""
    MULTIPLE_AUTHORITATIVE_AGREE = "multiple_authoritative_agree"
    SINGLE_AUTHORITATIVE = "single_authoritative"
    AUTHORITATIVE_CONFLICT = "authoritative_conflict"
    NO_AUTHORITATIVE_EVIDENCE = "no_authoritative_evidence"
    FRESHNESS_TIEBREAK = "freshness_tiebreak"
    HEALTH_TIEBREAK = "health_tiebreak"
    AUTHORITY_TIEBREAK = "authority_tiebreak"
    SPECIFICITY_TIEBREAK = "specificity_tiebreak"
    THIRD_PARTY_NEVER_OVERRIDES = "third_party_never_overrides"
    STALE_EVIDENCE = "stale_evidence"
    UNHEALTHY_SOURCE = "unhealthy_source"
    NO_EVIDENCE = "no_evidence"
    ONLY_ONE_SOURCE = "only_one_source"
    ALL_SOURCES_AGREE = "all_sources_agree"
    PARTIAL_AGREEMENT = "partial_agreement"
    VALUE_MATCH = "value_match"
    VALUE_MISMATCH = "value_match"


# Source authority scores for arbitration (higher = more authoritative)
_SOURCE_AUTHORITY_SCORES: dict[SourceType, int] = {
    SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM: 100,
    SourceType.OFFICIAL_APPLICATION_PORTAL: 90,
    SourceType.OFFICIAL_UNIVERSITY: 80,
    SourceType.OFFICIAL_GOVERNMENT: 70,
    SourceType.THIRD_PARTY: 0,
}

# Source health confidence multipliers
_HEALTH_CONFIDENCE_FACTOR: dict[str, float] = {
    "healthy": 1.0,
    "degraded": 0.7,
    "unhealthy": 0.4,
    "unknown": 0.85,
}

# Thresholds
_CONSENSUS_MIN_AUTHORITATIVE = 2
_CONFLICT_AUTHORITY_THRESHOLD = 70
_FRESHNESS_HALF_LIFE_DAYS = 30


@dataclass(frozen=True)
class EvidenceScore:
    """Score breakdown for a single evidence item."""
    evidence_index: int
    source_authority: int
    freshness_score: float
    health_score: float
    specificity_score: float
    composite_score: float
    source_url: str
    source_type: SourceType
    extracted_value: Any


@dataclass
class ArbitrationResult:
    """Complete arbitration result for a single field."""
    field_name: str
    decision: ArbitrationDecision
    winning_value: Any
    winning_source_url: str | None
    winning_source_type: SourceType | None
    consensus_score: float
    winning_evidence: EvidenceItem | None
    conflicting_evidence: list[EvidenceItem]
    all_evidence: list[EvidenceItem]
    scored_evidence: list[EvidenceScore]
    reason_codes: list[ReasonCode]
    reason_text: str
    arbitrator_id: str
    arbitr_at: str


def _extract_domain(url: str) -> str | None:
    """Extract domain from URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
        return parsed.netloc.lower() if parsed.netloc else None
    except Exception:
        return None


def _compute_freshness_score(verification_timestamp: str, now: datetime) -> float:
    """Compute freshness score (0.0 to 1.0) based on evidence age.

    Uses exponential decay with configurable half-life.
    """
    if not verification_timestamp:
        return 0.5

    try:
        ts = datetime.fromisoformat(verification_timestamp)
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        age_days = (now.replace(tzinfo=None) - ts).total_seconds() / 86400.0
    except (ValueError, TypeError):
        return 0.5

    if age_days < 0:
        return 1.0

    import math
    half_life = _FRESHNESS_HALF_LIFE_DAYS
    score = math.exp(-0.693 * age_days / half_life)
    return max(0.0, min(1.0, score))


def _compute_health_score(health_status: str | None) -> float:
    """Compute health confidence score from source health status."""
    if not health_status:
        return 0.85
    return _HEALTH_CONFIDENCE_FACTOR.get(health_status, 0.85)


def _compute_specificity_score(evidence_text: str) -> float:
    """Compute specificity score based on evidence text quality."""
    if not evidence_text or evidence_text.strip() == "":
        return 0.0

    text = evidence_text.strip()
    length = len(text)

    if length < 10:
        return 0.3
    elif length < 30:
        return 0.5
    elif length <= 200:
        return 1.0
    elif length <= 500:
        return 0.8
    else:
        return 0.6


def _compute_composite_score(
    authority: int,
    freshness: float,
    health: float,
    specificity: float,
    is_authoritative: bool,
) -> float:
    """Compute composite score for an evidence item.

    Weights:
    - Authority: 40%
    - Freshness: 25%
    - Health: 20%
    - Specificity: 15%

    Third-party sources get a heavy penalty.
    """
    authority_norm = authority / 100.0

    if not is_authoritative:
        authority_norm *= 0.1

    composite = (
        authority_norm * 0.40
        + freshness * 0.25
        + health * 0.20
        + specificity * 0.15
    )

    return max(0.0, min(1.0, composite))


def _group_evidence_by_value(
    evidence_items: list[EvidenceItem],
    field_name: str,
) -> dict[str, list[int]]:
    """Group evidence indices by their normalized value."""
    groups: dict[str, list[int]] = {}
    for idx, item in enumerate(evidence_items):
        norm = _normalize_value(item.extracted_value)
        if norm not in groups:
            groups[norm] = []
        groups[norm].append(idx)
    return groups


def _arbitration_id(field_name: str, evidence_count: int) -> str:
    """Generate deterministic arbitration ID."""
    content = f"{field_name}:{evidence_count}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def arbitrate_field(
    field_name: str,
    evidence_items: list[EvidenceItem],
    source_health: dict[str, str] | None = None,
    now: datetime | None = None,
) -> ArbitrationResult:
    """Arbitrate conflicting evidence for a single field.

    This is the main entry point for the arbitration engine.

    Args:
        field_name: The ORM field name being arbitrated
        evidence_items: All evidence items for this field from various sources
        source_health: Optional map of domain -> health_status
        now: Optional timestamp for deterministic testing

    Returns:
        ArbitrationResult with decision, winner, and explanation
    """
    if now is None:
        now = datetime.now(timezone.utc)

    source_health = source_health or {}

    if not evidence_items:
        return ArbitrationResult(
            field_name=field_name,
            decision=ArbitrationDecision.INSUFFICIENT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=[ReasonCode.NO_EVIDENCE],
            reason_text="No evidence available for arbitration",
            arbitrator_id=_arbitration_id(field_name, 0),
            arbitr_at=now.isoformat(),
        )

    # Score each evidence item
    scored: list[EvidenceScore] = []
    for idx, item in enumerate(evidence_items):
        domain = _extract_domain(item.source_url)
        health_status = source_health.get(domain) if domain else None

        authority = _calculate_source_authority(item.source_type)
        freshness = _compute_freshness_score(item.verification_timestamp, now)
        health = _compute_health_score(health_status)
        specificity = _compute_specificity_score(item.evidence_text)
        is_auth = is_authoritative_source(item.source_type)

        composite = _compute_composite_score(
            authority, freshness, health, specificity, is_auth
        )

        scored.append(EvidenceScore(
            evidence_index=idx,
            source_authority=authority,
            freshness_score=freshness,
            health_score=health,
            specificity_score=specificity,
            composite_score=composite,
            source_url=item.source_url,
            source_type=item.source_type,
            extracted_value=item.extracted_value,
        ))

    # Filter to authoritative evidence
    auth_indices = [
        i for i, s in enumerate(scored)
        if is_authoritative_source(evidence_items[i].source_type)
    ]

    # Case 1: No authoritative evidence
    if not auth_indices:
        # Check if we have any third-party evidence
        third_party = [
            i for i, s in enumerate(scored)
            if s.source_type == SourceType.THIRD_PARTY
        ]
        if third_party:
            best_third = max(third_party, key=lambda i: scored[i].composite_score)
            return ArbitrationResult(
                field_name=field_name,
                decision=ArbitrationDecision.INSUFFICIENT,
                winning_value=None,
                winning_source_url=None,
                winning_source_type=None,
                consensus_score=0.0,
                winning_evidence=None,
                conflicting_evidence=[],
                all_evidence=evidence_items,
                scored_evidence=scored,
                reason_codes=[ReasonCode.NO_AUTHORITATIVE_EVIDENCE, ReasonCode.THIRD_PARTY_NEVER_OVERRIDES],
                reason_text="Only third-party evidence available; cannot auto-resolve",
                arbitrator_id=_arbitration_id(field_name, len(evidence_items)),
                arbitr_at=now.isoformat(),
            )
        return ArbitrationResult(
            field_name=field_name,
            decision=ArbitrationDecision.INSUFFICIENT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=evidence_items,
            scored_evidence=scored,
            reason_codes=[ReasonCode.NO_AUTHORITATIVE_EVIDENCE],
            reason_text="No authoritative evidence available",
            arbitrator_id=_arbitration_id(field_name, len(evidence_items)),
            arbitr_at=now.isoformat(),
        )

    # Group authoritative evidence by value
    auth_evidence = [evidence_items[i] for i in auth_indices]
    auth_scored = [scored[i] for i in auth_indices]

    # Build value groups using cross-source comparison
    value_groups: dict[str, list[int]] = {}
    for local_idx, (global_idx, item) in enumerate(zip(auth_indices, auth_evidence)):
        norm = _normalize_value(item.extracted_value)
        if norm not in value_groups:
            value_groups[norm] = []
        value_groups[norm].append(local_idx)

    # Check if all authoritative sources agree
    if len(value_groups) == 1:
        # All authoritative sources agree
        best_local = max(
            range(len(auth_scored)),
            key=lambda i: auth_scored[i].composite_score,
        )
        best_global = auth_indices[best_local]
        best_item = evidence_items[best_global]
        best_score = scored[best_global]

        is_consensus = len(auth_indices) >= _CONSENSUS_MIN_AUTHORITATIVE
        decision = ArbitrationDecision.CONSENSUS if is_consensus else ArbitrationDecision.SINGLE_TRUSTED_SOURCE
        reason_codes = [ReasonCode.ALL_SOURCES_AGREE]
        if is_consensus:
            reason_codes.append(ReasonCode.MULTIPLE_AUTHORITATIVE_AGREE)
        else:
            reason_codes.append(ReasonCode.SINGLE_AUTHORITATIVE)

        consensus_score = sum(s.composite_score for s in auth_scored) / len(auth_scored)

        return ArbitrationResult(
            field_name=field_name,
            decision=decision,
            winning_value=best_item.extracted_value,
            winning_source_url=best_item.source_url,
            winning_source_type=best_item.source_type,
            consensus_score=consensus_score,
            winning_evidence=best_item,
            conflicting_evidence=[],
            all_evidence=evidence_items,
            scored_evidence=scored,
            reason_codes=reason_codes,
            reason_text=f"All {len(auth_indices)} authoritative sources agree",
            arbitrator_id=_arbitration_id(field_name, len(evidence_items)),
            arbitr_at=now.isoformat(),
        )

    # Multiple values detected - find the best group
    group_scores: dict[str, float] = {}
    group_best_authority: dict[str, int] = {}
    for norm, local_indices in value_groups.items():
        group_composite = sum(auth_scored[i].composite_score for i in local_indices) / len(local_indices)
        group_auth = max(auth_scored[i].source_authority for i in local_indices)
        group_scores[norm] = group_composite
        group_best_authority[norm] = group_auth

    # Sort groups by composite score, then by best authority
    sorted_groups = sorted(
        value_groups.keys(),
        key=lambda n: (group_scores[n], group_best_authority[n]),
        reverse=True,
    )

    best_norm = sorted_groups[0]
    best_local_indices = value_groups[best_norm]
    best_global_indices = [auth_indices[i] for i in best_local_indices]

    # Check if conflicting sources are also authoritative
    conflicting_norms = [n for n in sorted_groups[1:] if group_best_authority[n] >= _CONFLICT_AUTHORITY_THRESHOLD]

    if conflicting_norms:
        # High-authority conflict detected
        conflicting_evidence_list = []
        for norm in conflicting_norms:
            for local_idx in value_groups[norm]:
                conflicting_evidence_list.append(evidence_items[auth_indices[local_idx]])

        return ArbitrationResult(
            field_name=field_name,
            decision=ArbitrationDecision.CONFLICT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=conflicting_evidence_list,
            all_evidence=evidence_items,
            scored_evidence=scored,
            reason_codes=[ReasonCode.AUTHORITATIVE_CONFLICT, ReasonCode.VALUE_MISMATCH],
            reason_text=f"Authoritative sources disagree: {len(value_groups)} distinct values",
            arbitrator_id=_arbitration_id(field_name, len(evidence_items)),
            arbitr_at=now.isoformat(),
        )

    # Conflicting sources are lower authority - winner takes all
    best_local = max(best_local_indices, key=lambda i: auth_scored[i].composite_score)
    best_global = auth_indices[best_local]
    best_item = evidence_items[best_global]

    # Determine tiebreak reason
    best_group = best_norm
    second_norm = sorted_groups[1] if len(sorted_groups) > 1 else None

    reason_codes = [ReasonCode.PARTIAL_AGREEMENT]
    if second_norm:
        best_auth = group_best_authority[best_group]
        second_auth = group_best_authority[second_norm]
        if best_auth > second_auth:
            reason_codes.append(ReasonCode.AUTHORITY_TIEBREAK)
        else:
            reason_codes.append(ReasonCode.FRESHNESS_TIEBREAK)

    # Collect non-authoritative conflicting evidence
    non_auth_conflicting = []
    for norm in sorted_groups[1:]:
        for local_idx in value_groups[norm]:
            global_idx = auth_indices[local_idx]
            if not is_authoritative_source(evidence_items[global_idx].source_type):
                non_auth_conflicting.append(evidence_items[global_idx])

    consensus_score = group_scores[best_norm]

    return ArbitrationResult(
        field_name=field_name,
        decision=ArbitrationDecision.SINGLE_TRUSTED_SOURCE,
        winning_value=best_item.extracted_value,
        winning_source_url=best_item.source_url,
        winning_source_type=best_item.source_type,
        consensus_score=consensus_score,
        winning_evidence=best_item,
        conflicting_evidence=non_auth_conflicting,
        all_evidence=evidence_items,
        scored_evidence=scored,
        reason_codes=reason_codes,
        reason_text=f"Winner selected from {len(value_groups)} value groups by authority/freshness",
        arbitrator_id=_arbitration_id(field_name, len(evidence_items)),
        arbitr_at=now.isoformat(),
    )


def arbitrate_fields(
    evidence_items: list[EvidenceItem],
    source_health: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, ArbitrationResult]:
    """Arbitrate all fields from a collection of evidence items.

    Batch-friendly: groups evidence by field and arbitrates each field
    independently. No N+1 queries.

    Args:
        evidence_items: All evidence items across all fields
        source_health: Optional map of domain -> health_status
        now: Optional timestamp for deterministic testing

    Returns:
        Dict mapping field_name -> ArbitrationResult
    """
    # Group evidence by field
    fields: dict[str, list[EvidenceItem]] = {}
    for item in evidence_items:
        if item.field_name not in fields:
            fields[item.field_name] = []
        fields[item.field_name].append(item)

    results: dict[str, ArbitrationResult] = {}
    for field_name in sorted(fields.keys()):
        results[field_name] = arbitrate_field(
            field_name=field_name,
            evidence_items=fields[field_name],
            source_health=source_health,
            now=now,
        )

    return results


def has_consensus(result: ArbitrationResult) -> bool:
    """Check if arbitration result has consensus."""
    return result.decision == ArbitrationDecision.CONSENSUS


def is_conflict(result: ArbitrationResult) -> bool:
    """Check if arbitration result is a conflict requiring review."""
    return result.decision == ArbitrationDecision.CONFLICT


def is_sufficient(result: ArbitrationResult) -> bool:
    """Check if arbitration result has sufficient evidence for auto-update."""
    return result.decision in (
        ArbitrationDecision.CONSENSUS,
        ArbitrationDecision.SINGLE_TRUSTED_SOURCE,
    )


def requires_review(result: ArbitrationResult) -> bool:
    """Check if arbitration result requires human review."""
    return result.decision in (
        ArbitrationDecision.CONFLICT,
        ArbitrationDecision.INSUFFICIENT,
    )
