"""Explainable verification intelligence.

Generates deterministic, human-readable explanations for every verification
decision. Distinguishes AUTO_UPDATE, REVIEW_REQUIRED, REJECTED, and NO_CHANGE.

Reuses outputs from TASKS 7-17:
- change_impact_staleness (ChangeImpact, FieldStaleness, UrgencyScore)
- lifecycle_identity (LifecycleState, IdentityResolution)
- source_health_service (SourceHealth, HealthConfig)
- scheduler_priority (PriorityScore)
- discovery_identity (MatchResult)

Deterministic, no network calls, no AI/LLM required.
All metrics derived from existing persisted data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from ..models import Scholarship
from .change_impact_staleness import (
    CRITICAL,
    HIGH,
    compute_change_impact,
    compute_field_staleness,
    get_source_health_confidence,
)
from .lifecycle_identity import (
    ARCHIVED,
    CLOSED,
    LifecycleState,
    classify_lifecycle_state,
)
from .source_health_service import (
    DEGRADED,
    HEALTHY,
    UNKNOWN,
    UNHEALTHY,
    SourceHealth as SourceHealthModel,
    get_source_health,
)


AUTO_UPDATE = "auto_update"
REVIEW_REQUIRED = "review_required"
REJECTED = "rejected"
NO_CHANGE = "no_change"

DECISION_TYPES = frozenset({AUTO_UPDATE, REVIEW_REQUIRED, REJECTED, NO_CHANGE})


class ReasonCode(Enum):
    NO_CHANGE_DETECTED = "no_change_detected"
    FIELD_UNCHANGED = "field_unchanged"
    LOW_CRITICALITY_CHANGE = "low_criticality_change"
    HIGH_CRITICALITY_CHANGE = "high_criticality_change"
    CRITICAL_FIELD_CHANGE = "critical_field_change"
    SOURCE_UNHEALTHY = "source_unhealthy"
    SOURCE_MANUAL_BLOCK = "source_manual_block"
    IDENTITY_MISMATCH = "identity_mismatch"
    LIFECYCLE_TERMINAL = "lifecycle_terminal"
    LIFECYCLE_ARCHIVED = "lifecycle_archived"
    STALE_VERIFICATION = "stale_verification"
    CONFLICTING_SOURCES = "conflicting_sources"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    EXCEEDS_CHANGE_THRESHOLD = "exceeds_change_THRESHOLD"
    TITLE_CHANGE_SIGNIFICANT = "title_change_significant"
    FUNDING_CHANGE_SIGNIFICANT = "funding_change_significant"
    ELIGIBILITY_CHANGE_SIGNIFICANT = "eligibility_change_significant"
    DEADLINE_CHANGE_SIGNIFICANT = "deadline_change_significant"
    AUTO_LOW_IMPACT = "auto_low_impact"
    AUTO_NEW_FIELD = "auto_new_field"
    AUTO_TRUSTED_SOURCE = "auto_trusted_source"
    REVIEW_MULTIPLE_FIELDS = "review_multiple_fields"
    REVIEW_STALE_SOURCE = "review_stale_source"
    REVIEW_IDENTITY_REVIEW = "review_identity_review"
    REJECT_DUPLICATE = "reject_duplicate"
    REJECT_BLOCKED_SOURCE = "reject_blocked_source"
    REJECT_UNVERIFIABLE = "reject_unverifiable"


@dataclass(frozen=True)
class FieldExplanation:
    field_name: str
    decision: str
    reason_code: str
    old_value: str | None
    new_value: str | None
    impact_level: str
    impact_score: int
    staleness_state: str
    freshness_threshold_days: int
    age_days: int | None
    explanation: str


@dataclass(frozen=True)
class SourceAuthority:
    domain: str
    health_status: str
    reliability_score: float
    confidence_factor: float
    is_trusted: bool
    is_blocked: bool
    explanation: str


@dataclass(frozen=True)
class ChangeSummary:
    total_fields_changed: int
    critical_fields_changed: int
    high_fields_changed: int
    fields_cleared: int
    fields_populated: int
    max_impact_level: str
    overall_impact_score: int


@dataclass(frozen=True)
class VerificationExplanation:
    scholarship_id: int
    decision: str
    primary_reason_code: str
    summary: str
    field_explanations: list[FieldExplanation]
    source_authority: SourceAuthority
    change_summary: ChangeSummary
    lifecycle_state: str
    lifecycle_reason: str
    confidence: float
    factors: list[str]
    reason_codes: list[str]
    explanation_text: str
    generated_at: datetime


@dataclass(frozen=True)
class VerificationInput:
    scholarship: Scholarship
    candidate_fields: dict[str, tuple[object | None, object | None]]
    source_url: str | None
    source_health: SourceHealthModel | None
    lifecycle_state: LifecycleState
    today: date


def _coerce_value(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        import json
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _values_equal(a: object | None, b: object | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return _coerce_value(a) == _coerce_value(b)


def _compute_source_authority(
    session: Session,
    scholarship: Scholarship,
    source_url: str | None,
    source_health: SourceHealthModel | None,
) -> SourceAuthority:
    if not source_url:
        return SourceAuthority(
            domain="",
            health_status=UNKNOWN,
            reliability_score=0.0,
            confidence_factor=0.5,
            is_trusted=False,
            is_blocked=False,
            explanation="no_source_url:source_authority_unknown",
        )

    from .source_health_service import extract_domain
    domain = extract_domain(source_url) or ""

    if source_health is None:
        health = get_source_health(session, domain)
    else:
        health = source_health

    if health is None:
        return SourceAuthority(
            domain=domain,
            health_status=UNKNOWN,
            reliability_score=0.0,
            confidence_factor=0.85,
            is_trusted=True,
            is_blocked=False,
            explanation=f"domain={domain}:no_health_history:assumed_reliable",
        )

    confidence_factor = get_source_health_confidence(health)
    is_blocked = health.manual_override == UNHEALTHY
    is_trusted = health.health_status in (HEALTHY, UNKNOWN) and not is_blocked

    explanation = (
        f"domain={domain}:health={health.health_status}:"
        f"reliability={health.reliability_score:.1f}:confidence={confidence_factor:.2f}"
    )

    return SourceAuthority(
        domain=domain,
        health_status=health.health_status,
        reliability_score=health.reliability_score,
        confidence_factor=confidence_factor,
        is_trusted=is_trusted,
        is_blocked=is_blocked,
        explanation=explanation,
    )


def _explain_field(
    field_name: str,
    old_value: object | None,
    new_value: object | None,
    last_verified: datetime | None,
    today: date,
) -> FieldExplanation:
    impact = compute_change_impact(field_name, old_value, new_value)
    staleness = compute_field_staleness(field_name, last_verified, today)

    old_str = _coerce_value(old_value)
    new_str = _coerce_value(new_value)

    if old_value is None and new_value is not None:
        change_desc = f"field populated: '{new_str[:80]}'"
    elif old_value is not None and new_value is None:
        change_desc = f"field cleared (was '{old_str[:80]}')"
    elif old_value != new_value:
        change_desc = f"changed from '{old_str[:60]}' to '{new_str[:60]}'"
    else:
        change_desc = "no change"

    if impact.impact_score > 0:
        explanation = (
            f"{field_name}: {change_desc}. "
            f"Impact: {impact.impact_level} ({impact.impact_score}/100). "
            f"Staleness: {staleness.freshness_state} "
            f"(threshold={staleness.freshness_threshold_days}d, "
            f"age={staleness.age_days}d)."
        )
    else:
        explanation = f"{field_name}: no change detected."

    return FieldExplanation(
        field_name=field_name,
        decision=AUTO_UPDATE if impact.impact_score > 0 else NO_CHANGE,
        reason_code=ReasonCode.FIELD_UNCHANGED.value if impact.impact_score == 0 else impact.reason,
        old_value=old_str,
        new_value=new_str,
        impact_level=impact.impact_level,
        impact_score=impact.impact_score,
        staleness_state=staleness.freshness_state,
        freshness_threshold_days=staleness.freshness_threshold_days,
        age_days=staleness.age_days,
        explanation=explanation,
    )


def _summarize_changes(field_explanations: list[FieldExplanation]) -> ChangeSummary:
    changed = [f for f in field_explanations if f.impact_score > 0]
    critical = sum(1 for f in changed if f.impact_level == CRITICAL)
    high = sum(1 for f in changed if f.impact_level == HIGH)
    cleared = sum(1 for f in changed if f.old_value is not None and f.new_value is None)
    populated = sum(1 for f in changed if f.old_value is None and f.new_value is not None)

    if not changed:
        max_level = "none"
        max_score = 0
    elif critical > 0:
        max_level = CRITICAL
        max_score = max(f.impact_score for f in changed if f.impact_level == CRITICAL)
    elif high > 0:
        max_level = HIGH
        max_score = max(f.impact_score for f in changed if f.impact_level == HIGH)
    else:
        max_level = changed[0].impact_level
        max_score = max(f.impact_score for f in changed)

    return ChangeSummary(
        total_fields_changed=len(changed),
        critical_fields_changed=critical,
        high_fields_changed=high,
        fields_cleared=cleared,
        fields_populated=populated,
        max_impact_level=max_level,
        overall_impact_score=max_score,
    )


def _decide_decision(
    field_explanations: list[FieldExplanation],
    source_authority: SourceAuthority,
    lifecycle_state: LifecycleState,
    change_summary: ChangeSummary,
) -> tuple[str, str, list[str], list[str]]:
    factors: list[str] = []
    reason_codes: list[str] = []

    if change_summary.total_fields_changed == 0:
        return NO_CHANGE, ReasonCode.NO_CHANGE_DETECTED.value, ["no_fields_changed"], [ReasonCode.NO_CHANGE_DETECTED.value]

    if source_authority.is_blocked:
        factors.append(f"source_blocked:{source_authority.domain}")
        reason_codes.append(ReasonCode.REJECT_BLOCKED_SOURCE.value)
        return REJECTED, ReasonCode.REJECT_BLOCKED_SOURCE.value, factors, reason_codes

    if lifecycle_state.state in (ARCHIVED, CLOSED):
        factors.append(f"lifecycle_terminal:{lifecycle_state.state}")
        reason_codes.append(ReasonCode.LIFECYCLE_TERMINAL.value)
        return REJECTED, ReasonCode.LIFECYCLE_TERMINAL.value, factors, reason_codes

    factors.append(f"source_health={source_authority.health_status}")
    factors.append(f"source_confidence={source_authority.confidence_factor:.2f}")
    factors.append(f"lifecycle={lifecycle_state.state}")

    if change_summary.critical_fields_changed > 0:
        factors.append(f"critical_fields_changed={change_summary.critical_fields_changed}")
        reason_codes.append(ReasonCode.CRITICAL_FIELD_CHANGE.value)
        return REVIEW_REQUIRED, ReasonCode.CRITICAL_FIELD_CHANGE.value, factors, reason_codes

    if change_summary.total_fields_changed >= 5:
        factors.append(f"many_fields_changed={change_summary.total_fields_changed}")
        reason_codes.append(ReasonCode.REVIEW_MULTIPLE_FIELDS.value)
        return REVIEW_REQUIRED, ReasonCode.REVIEW_MULTIPLE_FIELDS.value, factors, reason_codes

    if change_summary.fields_cleared > 0:
        fields_cleared_names = [f.field_name for f in field_explanations if f.old_value is not None and f.new_value is None]
        factors.append(f"fields_cleared={fields_cleared_names}")
        reason_codes.append(ReasonCode.REVIEW_STALE_SOURCE.value)
        return REVIEW_REQUIRED, ReasonCode.REVIEW_STALE_SOURCE.value, factors, reason_codes

    if source_authority.health_status == DEGRADED:
        factors.append("source_degraded")
        reason_codes.append(ReasonCode.REVIEW_STALE_SOURCE.value)
        return REVIEW_REQUIRED, ReasonCode.REVIEW_STALE_SOURCE.value, factors, reason_codes

    if change_summary.high_fields_changed > 2:
        factors.append(f"high_fields_changed={change_summary.high_fields_changed}")
        reason_codes.append(ReasonCode.HIGH_CRITICALITY_CHANGE.value)
        return REVIEW_REQUIRED, ReasonCode.HIGH_CRITICALITY_CHANGE.value, factors, reason_codes

    if source_authority.is_trusted:
        factors.append("source_trusted")
        reason_codes.append(ReasonCode.AUTO_TRUSTED_SOURCE.value)

    factors.append(f"low_impact_changes={change_summary.total_fields_changed}")
    reason_codes.append(ReasonCode.AUTO_LOW_IMPACT.value)
    return AUTO_UPDATE, ReasonCode.AUTO_LOW_IMPACT.value, factors, reason_codes


def _compute_confidence(
    source_authority: SourceAuthority,
    change_summary: ChangeSummary,
    decision: str,
) -> float:
    base = source_authority.confidence_factor

    if change_summary.total_fields_changed == 0:
        return 1.0

    if decision == REJECTED:
        return min(1.0, base + 0.2)

    if decision == REVIEW_REQUIRED:
        return max(0.3, base - 0.1)

    if change_summary.critical_fields_changed > 0:
        return max(0.2, base - 0.3)

    if change_summary.high_fields_changed > 0:
        return max(0.4, base - 0.15)

    return min(1.0, base + 0.1)


def _build_explanation_text(
    decision: str,
    primary_reason: str,
    change_summary: ChangeSummary,
    source_authority: SourceAuthority,
    lifecycle_state: LifecycleState,
) -> str:
    parts = [f"decision={decision}"]

    if decision == NO_CHANGE:
        parts.append("no changes detected in any field")
        return ". ".join(parts) + "."

    parts.append(f"reason={primary_reason}")
    parts.append(
        f"changes={change_summary.total_fields_changed} "
        f"(critical={change_summary.critical_fields_changed}, "
        f"high={change_summary.high_fields_changed})"
    )
    parts.append(
        f"source={source_authority.domain} health={source_authority.health_status} "
        f"confidence={source_authority.confidence_factor:.2f}"
    )
    parts.append(f"lifecycle={lifecycle_state.state}")

    return ". ".join(parts) + "."


def explain_verification(
    session: Session,
    input_data: VerificationInput,
) -> VerificationExplanation:
    today = input_data.today or date.today()
    field_timestamps = _get_field_timestamps(input_data.scholarship)

    field_explanations = []
    for field_name, (old_val, new_val) in input_data.candidate_fields.items():
        last_verified = field_timestamps.get(field_name)
        fe = _explain_field(field_name, old_val, new_val, last_verified, today)
        field_explanations.append(fe)

    source_authority = _compute_source_authority(
        session,
        input_data.scholarship,
        input_data.source_url,
        input_data.source_health,
    )

    change_summary = _summarize_changes(field_explanations)
    decision, primary_reason, factors, reason_codes = _decide_decision(
        field_explanations,
        source_authority,
        input_data.lifecycle_state,
        change_summary,
    )

    confidence = _compute_confidence(source_authority, change_summary, decision)
    explanation_text = _build_explanation_text(
        decision,
        primary_reason,
        change_summary,
        source_authority,
        input_data.lifecycle_state,
    )

    if change_summary.total_fields_changed == 0:
        summary = "no changes detected"
    else:
        summary = (
            f"{change_summary.total_fields_changed} field(s) changed, "
            f"max impact: {change_summary.max_impact_level}"
        )

    return VerificationExplanation(
        scholarship_id=input_data.scholarship.id,
        decision=decision,
        primary_reason_code=primary_reason,
        summary=summary,
        field_explanations=field_explanations,
        source_authority=source_authority,
        change_summary=change_summary,
        lifecycle_state=input_data.lifecycle_state.state,
        lifecycle_reason=input_data.lifecycle_state.reason,
        confidence=confidence,
        factors=factors,
        reason_codes=reason_codes,
        explanation_text=explanation_text,
        generated_at=datetime.now(timezone.utc),
    )


def _get_field_timestamps(scholarship: Scholarship) -> dict[str, datetime | None]:
    from .lifecycle_identity import get_lifecycle_timestamp_fields
    timestamps = get_lifecycle_timestamp_fields(scholarship)
    last_verified = timestamps.get("last_verified_at")
    return {field: last_verified for field in _VERIFIED_FIELDS}


_VERIFIED_FIELDS = frozenset({
    "title", "country", "degree", "funding", "description",
    "deadline_date", "deadline_display", "status",
    "eligibility", "eligibility_summary", "benefits", "coverage",
    "requirements", "documents", "english_requirement",
    "application_method", "selection_notes", "program_type",
    "best_fit", "notes", "official_source", "official_source_url",
    "catalogue_url", "official_updates_url", "application_link",
})


def quick_explain(
    session: Session,
    scholarship: Scholarship,
    candidate_fields: dict[str, tuple[object | None, object | None]],
    source_url: str | None = None,
    source_health: SourceHealthModel | None = None,
    today: date | None = None,
) -> VerificationExplanation:
    if today is None:
        today = date.today()

    lifecycle = classify_lifecycle_state(session, scholarship, today)
    input_data = VerificationInput(
        scholarship=scholarship,
        candidate_fields=candidate_fields,
        source_url=source_url or scholarship.official_source_url,
        source_health=source_health,
        lifecycle_state=lifecycle,
        today=today,
    )
    return explain_verification(session, input_data)


def batch_explain(
    session: Session,
    inputs: list[VerificationInput],
) -> list[VerificationExplanation]:
    return [explain_verification(session, inp) for inp in inputs]


def is_auto_approved(explanation: VerificationExplanation) -> bool:
    return explanation.decision == AUTO_UPDATE


def is_review_required(explanation: VerificationExplanation) -> bool:
    return explanation.decision == REVIEW_REQUIRED


def is_rejected(explanation: VerificationExplanation) -> bool:
    return explanation.decision == REJECTED


def is_no_change(explanation: VerificationExplanation) -> bool:
    return explanation.decision == NO_CHANGE


def get_explanation_summary(explanation: VerificationExplanation) -> dict:
    return {
        "scholarship_id": explanation.scholarship_id,
        "decision": explanation.decision,
        "primary_reason_code": explanation.primary_reason_code,
        "confidence": explanation.confidence,
        "summary": explanation.summary,
        "fields_changed": explanation.change_summary.total_fields_changed,
        "max_impact_level": explanation.change_summary.max_impact_level,
        "source_health": explanation.source_authority.health_status,
        "lifecycle_state": explanation.lifecycle_state,
        "explanation_text": explanation.explanation_text,
    }
