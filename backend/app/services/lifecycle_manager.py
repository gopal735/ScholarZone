"""Scholarship lifecycle state management with strict transition enforcement.

Enforces the production lifecycle states:
    OPEN, UPCOMING, CLOSING-SOON, CLOSED

Transitions are validated against an explicit state graph.
All transitions are audited in verification history.

Temporary source/network failures are handled via the existing retry/
source-health mechanism and do NOT mutate the public scholarship status.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal

from sqlalchemy.orm import Session

from ..models import Scholarship, ScholarshipVerificationHistory
from .scholarship_diff import ChangeSet

logger = logging.getLogger(__name__)


class LifecycleState(str, Enum):
    OPEN = "open"
    UPCOMING = "upcoming"
    CLOSING_SOON = "closing-soon"
    CLOSED = "closed"


VALID_TRANSITIONS: dict[str, set[str]] = {
    LifecycleState.OPEN: {
        LifecycleState.CLOSING_SOON,
        LifecycleState.CLOSED,
    },
    LifecycleState.UPCOMING: {
        LifecycleState.OPEN,
        LifecycleState.CLOSED,
    },
    LifecycleState.CLOSING_SOON: {
        LifecycleState.CLOSED,
        LifecycleState.OPEN,
    },
    LifecycleState.CLOSED: {
        LifecycleState.UPCOMING,
    },
}


@dataclass(frozen=True)
class LifecycleEvaluation:
    current_state: str
    proposed_state: str | None
    transition_allowed: bool
    reason: str
    should_transition: bool


@dataclass(frozen=True)
class LifecycleTransitionResult:
    scholarship_id: int
    from_state: str
    to_state: str
    reason: str
    history_written: bool


def evaluate_lifecycle(
    scholarship: Scholarship,
    verification_result: dict | None = None,
    today: date | None = None,
) -> LifecycleEvaluation:
    """Evaluate the proposed lifecycle state for a scholarship.

    Determines the proposed state based on:
    - Official source fetch success/failure
    - Deadline proximity
    - Application period
    - Next cycle announcements

    Args:
        scholarship: The scholarship to evaluate
        verification_result: Optional verification result dict with fetch_status, etc.
        today: Optional date override for testing

    Returns:
        LifecycleEvaluation with proposed state and transition validity
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    current = (scholarship.status or "open").lower()
    try:
        current_state = LifecycleState(current)
    except ValueError:
        current_state = LifecycleState.OPEN

    proposed_state = current_state
    reason = "no_change"

    fetch_failed = False
    if verification_result:
        fetch_status = verification_result.get("fetch_status")
        fetch_failed = fetch_status == "failed"

    if fetch_failed:
        return LifecycleEvaluation(
            current_state=current_state.value,
            proposed_state=current_state.value,
            transition_allowed=False,
            reason="source_fetch_failed",
            should_transition=False,
        )

    deadline = scholarship.deadline_date
    if isinstance(deadline, datetime):
        deadline = deadline.date()

    if deadline is not None:
        delta = (deadline - today).days

        if delta < 0:
            proposed_state = LifecycleState.CLOSED
            reason = "deadline_passed"
        elif delta <= 14:
            proposed_state = LifecycleState.CLOSING_SOON
            reason = "deadline_within_14_days"
        else:
            if current_state == LifecycleState.CLOSED:
                if scholarship.is_verified and delta > 0:
                    proposed_state = LifecycleState.OPEN
                    reason = "verified_future_deadline"
            elif current_state == LifecycleState.UPCOMING:
                if scholarship.is_verified and scholarship.application_period and "open" in (scholarship.application_period or "").lower():
                    proposed_state = LifecycleState.OPEN
                    reason = "application_open"
            elif current_state == LifecycleState.OPEN:
                reason = "open_with_future_deadline"
    else:
        if current_state == LifecycleState.CLOSED:
            pass
        elif current_state == LifecycleState.UPCOMING and scholarship.is_verified:
            if scholarship.application_period and "open" in (scholarship.application_period or "").lower():
                proposed_state = LifecycleState.OPEN
                reason = "application_open_no_deadline"

    if proposed_state == current_state and current_state == LifecycleState.CLOSED:
        if _has_next_cycle_announcement(scholarship):
            proposed_state = LifecycleState.UPCOMING
            reason = "next_cycle_announced"

    return LifecycleEvaluation(
        current_state=current_state.value,
        proposed_state=proposed_state.value,
        transition_allowed=_is_valid_transition(current_state.value, proposed_state.value),
        reason=reason,
        should_transition=(current_state != proposed_state and _is_valid_transition(current_state.value, proposed_state.value)),
    )


def _has_next_cycle_announcement(scholarship: Scholarship) -> bool:
    """Check if there is evidence of a next cycle announcement.

    This checks the scholarship notes, verification notes, and
    application_period for indicators of a future cycle.
    """
    text_fields = [
        scholarship.notes,
        scholarship.verification_notes,
        scholarship.application_period,
        scholarship.selection_notes,
    ]

    indicators = [
        "2027", "2028", "next cycle", "next year", "now open",
        "applications open", "accepting applications", "now accepting",
        "2026-2027", "2027-2028", "academic year",
    ]

    for field in text_fields:
        if not field:
            continue
        field_lower = field.lower()
        for indicator in indicators:
            if indicator in field_lower:
                return True
    return False


def _is_valid_transition(from_state: str, to_state: str) -> bool:
    if from_state == to_state:
        return False
    allowed = VALID_TRANSITIONS.get(from_state, set())
    return to_state in allowed


def apply_lifecycle_transition(
    session: Session,
    scholarship: Scholarship,
    evaluation: LifecycleEvaluation,
    source_url: str | None = None,
) -> LifecycleTransitionResult | None:
    """Apply a validated lifecycle transition to the scholarship.

    Creates audit history entries for material state changes.

    Args:
        session: SQLAlchemy session
        scholarship: The scholarship to update
        evaluation: The lifecycle evaluation result
        source_url: Optional source URL for audit trail

    Returns:
        LifecycleTransitionResult if transition was applied, None otherwise
    """
    if not evaluation.should_transition or not evaluation.transition_allowed:
        return None

    old_status = scholarship.status
    new_status = evaluation.proposed_state

    if old_status == new_status:
        return None

    scholarship.status = new_status
    scholarship.verification_status = "active"
    scholarship.last_verified_at = datetime.now(timezone.utc).date()
    scholarship.last_verified_date = datetime.now(timezone.utc).date()
    scholarship.is_verified = True

    history_entry = ScholarshipVerificationHistory(
        scholarship_id=scholarship.id,
        field_name="status",
        old_value=old_status,
        new_value=new_status,
        change_type="modified",
        source_url=source_url,
        evidence_text=f"Lifecycle transition: {evaluation.reason}",
        confidence="high",
        verification_status="active",
    )
    session.add(history_entry)
    session.flush()

    logger.info(
        "Lifecycle transition applied: scholarship_id=%d %s -> %s (%s)",
        scholarship.id, old_status, new_status, evaluation.reason,
    )

    return LifecycleTransitionResult(
        scholarship_id=scholarship.id,
        from_state=old_status,
        to_state=new_status,
        reason=evaluation.reason,
        history_written=True,
    )


def batch_evaluate_lifecycle(
    session: Session,
    scholarships: list[Scholarship],
    verification_results: dict[int, dict] | None = None,
    today: date | None = None,
) -> list[LifecycleEvaluation]:
    """Evaluate lifecycle for multiple scholarships.

    Args:
        session: SQLAlchemy session
        scholarships: List of scholarships to evaluate
        verification_results: Optional dict mapping scholarship_id to verification result
        today: Optional date override

    Returns:
        List of LifecycleEvaluation objects
    """
    results = []
    for s in scholarships:
        vresult = None
        if verification_results and s.id in verification_results:
            vresult = verification_results[s.id]
        evaluation = evaluate_lifecycle(s, vresult, today)
        results.append(evaluation)
    return results
