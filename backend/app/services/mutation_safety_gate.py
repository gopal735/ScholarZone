"""One safety gate for every automatic mutation of a scholarship.

Verification and enrichment both write to `Scholarship` from parsed evidence.
Until the anomaly gate was extracted here, only verification was protected:
enrichment's ``_apply_proposals`` wrote through its own path with no anomaly
check at all, so a source page that moved a deadline backwards or collapsed a
funding value could be merged silently.

This module is the single place that decides. It is:

* **pure** - `evaluate_mutation` performs no query, no fetch and no write;
* **deterministic** - same inputs, same verdict, no clock or randomness;
* **shared** - both pipelines call it, and the anomaly logic itself is not
  duplicated or reimplemented;
* **fail-closed** - if the detector raises, the mutation is held back. A
  safety layer that fails open is not a safety layer.

A held-back mutation is never silently dropped. `record_blocked_mutation`
writes it to the existing review queue, keyed so that re-running an
idempotent pipeline does not accumulate duplicate rows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Scholarship, ScholarshipReview
from . import anomaly_detection
from .anomaly_detection import AnomalySeverity

logger = logging.getLogger(__name__)

BLOCKED_REVIEW_PREFIX = "anomaly:"
REVIEW_DECISION_PENDING = "pending"

# Fields whose anomaly detectors are date-aware; the gate passes them through
# unchanged, so this exists only to document that no field is special-cased.
_ALL_FIELDS_ARE_GATED = True


@dataclass(frozen=True)
class GateVerdict:
    """Whether a single proposed mutation may be written automatically."""

    allowed: bool
    severity: str | None = None
    reasons: tuple[str, ...] = ()
    failed_closed: bool = False

    @property
    def reason_text(self) -> str:
        return "; ".join(self.reasons) or "blocked by safety gate"


ALLOWED = GateVerdict(allowed=True)


def _summarise(anomalies) -> tuple[str, ...]:
    out: list[str] = []
    for anomaly in anomalies:
        reason = getattr(getattr(anomaly, "reason_code", None), "value", None) or "anomaly"
        detail = getattr(anomaly, "explanation", None) or ""
        out.append(f"{reason}: {detail}".strip(": ").strip())
    return tuple(out)


def evaluate_mutation(
    scholarship: Scholarship,
    field_name: str,
    old_value: Any,
    new_value: Any,
) -> GateVerdict:
    """Decide whether one proposed field change may be written automatically.

    HIGH and CRITICAL anomalies are never applied automatically. MEDIUM and
    below keep whatever the calling pipeline's own confidence and evidence
    rules already decided - this gate narrows the set of automatic writes, it
    never widens it.
    """
    if not _ALL_FIELDS_ARE_GATED:  # pragma: no cover - documentation only
        return ALLOWED
    if not field_name:
        return ALLOWED

    try:
        # Resolved through the module rather than bound at import, so a
        # substituted detector is actually observed by this gate.
        anomalies = anomaly_detection.detect_anomalies(
            field_name,
            old_value,
            new_value,
            source_url=scholarship.official_source_url,
            scholarship_status=scholarship.status,
            deadline_date=scholarship.deadline_date,
            is_verified=scholarship.is_verified,
        )
    except Exception as exc:  # noqa: BLE001
        # Fail closed. If the safety layer cannot decide, the answer is no.
        logger.warning(
            "anomaly gate failed closed for field=%s id=%s: %s",
            field_name,
            getattr(scholarship, "id", "?"),
            exc,
        )
        return GateVerdict(
            allowed=False,
            severity=AnomalySeverity.HIGH.value,
            reasons=(f"safety gate unavailable: {type(exc).__name__}",),
            failed_closed=True,
        )

    if not anomalies:
        return ALLOWED

    worst = AnomalySeverity.LOW
    for anomaly in anomalies:
        try:
            severity = anomaly.severity
            if isinstance(severity, str):
                severity = AnomalySeverity(severity)
        except ValueError:  # pragma: no cover - unknown severity, treat as high
            severity = AnomalySeverity.HIGH
        if _SEVERITY_ORDER[severity] > _SEVERITY_ORDER[worst]:
            worst = severity

    if worst in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL):
        return GateVerdict(
            allowed=False,
            severity=worst.value,
            reasons=_summarise(anomalies),
        )
    return ALLOWED


_SEVERITY_ORDER = {
    AnomalySeverity.LOW: 0,
    AnomalySeverity.MEDIUM: 1,
    AnomalySeverity.HIGH: 2,
    AnomalySeverity.CRITICAL: 3,
}


def partition_candidates(
    candidates: Sequence[dict],
    scholarship: Scholarship,
) -> tuple[list[dict], list[tuple[str, GateVerdict]]]:
    """Split verification-style candidates into writable and held-back.

    Returns ``(safe, blocked)`` where ``blocked`` pairs a field name with its
    verdict. A candidate with no recognisable field name passes through
    untouched, so the gate cannot break an unfamiliar caller.
    """
    safe: list[dict] = []
    blocked: list[tuple[str, GateVerdict]] = []
    for candidate in candidates or []:
        field_name = candidate.get("field") or candidate.get("field_name")
        if not field_name:
            safe.append(candidate)
            continue
        verdict = evaluate_mutation(
            scholarship,
            str(field_name),
            candidate.get("old_value"),
            candidate.get("new_value"),
        )
        if verdict.allowed:
            safe.append(candidate)
        else:
            blocked.append((str(field_name), verdict))
    return safe, blocked


def record_blocked_mutation(
    session: Session,
    scholarship_id: int,
    field_name: str,
    verdict: GateVerdict,
    *,
    old_value: Any = None,
    new_value: Any = None,
    source_url: str | None = None,
) -> bool:
    """Route a held-back mutation to the existing review queue.

    Idempotent by construction: the review table has a unique constraint on
    ``(scholarship_id, field_name, decision)``, and this checks for an existing
    pending row first, so a pipeline that runs twice on unchanged data does not
    accumulate duplicates.

    Returns True when a new review row was created.
    """
    conflict_reason = f"{BLOCKED_REVIEW_PREFIX}{verdict.severity or 'high'}"[:255]
    existing = session.scalars(
        select(ScholarshipReview).where(
            ScholarshipReview.scholarship_id == scholarship_id,
            ScholarshipReview.field_name == field_name[:120],
            ScholarshipReview.decision == REVIEW_DECISION_PENDING,
        )
    ).first()
    if existing is not None:
        return False

    session.add(
        ScholarshipReview(
            scholarship_id=scholarship_id,
            field_name=field_name[:120],
            current_value=_as_text(old_value),
            proposed_value=_as_text(new_value),
            conflict_reason=conflict_reason,
            verification_state="anomaly_blocked",
            confidence=verdict.severity,
            source_urls=[source_url] if source_url else [],
            evidence_text=verdict.reason_text[:2000],
            decision=REVIEW_DECISION_PENDING,
        )
    )
    return True


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)[:2000]
    return str(value)[:2000]
