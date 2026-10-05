"""Private outreach routes.

Everything here is scoped to the signed-in student, resolved by
``app.dependencies.require_user`` — the same dependency Dashboard 1.0 and
Application Workspace use. No second identity system is introduced, and no
``user_id`` is ever accepted from a request.

A record belonging to another student answers 404 rather than 403: the caller
should not learn that it exists. That is the same rule ``applications.py``
documents, and matching it matters because a 403 would confirm the existence and
rough shape of someone else's private activity.

This module does not send anything. There is no mail path in it, and the only
outbound email in the codebase is a single-recipient operator notification. That
is the intended shape for 1.0: the student prepares a draft, reviews it, and
sends it from their own mail client.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.rate_limit import RateLimitExceeded, outreach_write_limiter
from ..database import get_db
from ..dependencies import require_user
from ..models import User
from ..models_supervisor import (
    ProfessorOutreachRecord,
    ProfessorProfile,
    ScholarshipProfessorLink,
)
from ..schemas import (
    OutreachCreateRequest,
    OutreachResponse,
    OutreachSummaryResponse,
    OutreachUpdateRequest,
)
from ..services.supervisor_status import (
    PUBLIC_RELATIONSHIP_STATUSES,
    OutreachStatus,
    outreach_transition_is_legal,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["outreach"])

MAX_NOTES_LENGTH = 4000
MAX_DRAFT_BODY_LENGTH = 12000
MAX_SUBJECT_LENGTH = 255
MAX_NEXT_ACTION_LENGTH = 255

_NOT_FOUND = "Outreach record not found."

#: The recognised outreach statuses, as the plain strings a client sends.
#:
#: Membership has to be tested against this rather than against ``OutreachStatus``
#: itself. `"sent" in OutreachStatus` is not a documented operation: on Python
#: 3.12 and later it resolves by value, while on 3.11 - the version CI runs - it
#: raises ``TypeError: unsupported operand type(s) for 'in': 'str' and
#: 'EnumType'``. Same source, same request, different answer, so the branch was
#: reachable on a laptop and unreachable in the gate.
#:
#: ``OutreachStatus.__members__`` is not the fix either: it is keyed by member
#: NAME, so `"sent" in OutreachStatus.__members__` is False and every legitimate
#: status would be rejected as unrecognised. These are the values, which is what
#: the column and the payload both hold.
_RECOGNISED_OUTREACH_STATUSES: frozenset[str] = frozenset(
    str(member) for member in OutreachStatus
)

#: Notes are stored and returned as plain text and rendered as text. Rejecting
#: angle brackets and braces costs the student nothing here and removes the
#: temptation to treat this column as a rendering surface later.
_MARKUP_PATTERN = re.compile(r"[<>{}]")


def _reject_markup(value: str | None, field: str, limit: int) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if len(trimmed) > limit:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{field} must be {limit} characters or fewer.",
        )
    if _MARKUP_PATTERN.search(trimmed):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{field} must be plain text and cannot contain angle brackets or braces.",
        )
    return trimmed or None


def _rate_limit(user: User) -> None:
    try:
        outreach_write_limiter.check(f"write:{user.id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please slow down.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )


def _owned_record(db: Session, record_id: int, user: User) -> ProfessorOutreachRecord:
    """Return the record only if this student owns it.

    The ownership test is part of the query rather than a check afterwards, so
    another student's row is never even loaded. Combined with the identical 404,
    a caller cannot probe for the existence of someone else's record.
    """
    row = db.execute(
        select(ProfessorOutreachRecord).where(
            and_(
                ProfessorOutreachRecord.id == record_id,
                ProfessorOutreachRecord.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return row


def _validate_pair(db: Session, scholarship_id: int, professor_id: int) -> None:
    """Reject a pair that no verified public relationship supports.

    Without this a student could manufacture an outreach record against any
    professor id, and the record would then sit next to a scholarship that
    academic has no evidenced connection to.
    """
    exists = db.execute(
        select(ScholarshipProfessorLink.id).where(
            and_(
                ScholarshipProfessorLink.scholarship_id == scholarship_id,
                ScholarshipProfessorLink.professor_id == professor_id,
                ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
            )
        )
    ).first()
    if exists is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "That professor is not a verified match for this scholarship.",
        )
    professor = db.get(ProfessorProfile, professor_id)
    if professor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Professor not found.")


def _to_response(row: ProfessorOutreachRecord) -> OutreachResponse:
    return OutreachResponse(
        id=row.id,
        scholarship_id=row.scholarship_id,
        professor_id=row.professor_id,
        application_id=row.application_id,
        status=row.status,
        draft_subject=row.draft_subject,
        draft_body=row.draft_body,
        first_contacted_at=row.first_contacted_at,
        last_contacted_at=row.last_contacted_at,
        follow_up_due_at=row.follow_up_due_at,
        response_status=row.response_status,
        response_at=row.response_at,
        next_action=row.next_action,
        notes=row.notes,
        template_id=row.template_id,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[OutreachResponse])
def list_outreach(
    outreach_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[OutreachResponse]:
    """Return the signed-in student's own outreach records."""
    query = select(ProfessorOutreachRecord).where(ProfessorOutreachRecord.user_id == user.id)
    if outreach_status:
        query = query.where(ProfessorOutreachRecord.status == outreach_status)
    rows = db.execute(
        query.order_by(ProfessorOutreachRecord.updated_at.desc()).limit(limit).offset(offset)
    ).scalars()
    return [_to_response(row) for row in rows]


@router.get("/summary", response_model=OutreachSummaryResponse)
def outreach_summary(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> OutreachSummaryResponse:
    """Return counts of this student's own outreach.

    A separate surface from the catalogue's counts on purpose. These numbers are
    never added to the application, match, saved or catalogue totals, and no
    response-rate style metric is derived from them — there is not yet enough real
    outbound data to support one, and a synthesised one would be a fiction.
    """
    now = datetime.now(timezone.utc)
    counts = dict(
        db.execute(
            select(ProfessorOutreachRecord.status, func.count(ProfessorOutreachRecord.id))
            .where(ProfessorOutreachRecord.user_id == user.id)
            .group_by(ProfessorOutreachRecord.status)
        ).all()
    )
    follow_ups_due = db.execute(
        select(func.count(ProfessorOutreachRecord.id)).where(
            and_(
                ProfessorOutreachRecord.user_id == user.id,
                ProfessorOutreachRecord.follow_up_due_at.isnot(None),
                ProfessorOutreachRecord.follow_up_due_at <= now,
                ProfessorOutreachRecord.status.in_(
                    [str(OutreachStatus.SENT), str(OutreachStatus.FOLLOW_UP_DUE)]
                ),
            )
        )
    ).scalar_one()
    awaiting_reply = sum(
        counts.get(state, 0) for state in (OutreachStatus.SENT, OutreachStatus.FOLLOW_UP_DUE)
    )
    return OutreachSummaryResponse(
        total=sum(counts.values()),
        by_status={str(key): value for key, value in counts.items()},
        follow_ups_due=follow_ups_due,
        awaiting_reply=awaiting_reply,
        positive_responses=counts.get(str(OutreachStatus.POSITIVE), 0),
    )


@router.post("", response_model=OutreachResponse, status_code=status.HTTP_201_CREATED)
def create_outreach(
    payload: OutreachCreateRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> OutreachResponse:
    """Start tracking one professor, idempotently.

    The unique constraint on (user, scholarship, professor) means a
    double-submitted form returns the record that already exists rather than
    creating a second one and splitting the history in two.
    """
    _rate_limit(user)
    _validate_pair(db, payload.scholarship_id, payload.professor_id)

    existing = db.execute(
        select(ProfessorOutreachRecord).where(
            and_(
                ProfessorOutreachRecord.user_id == user.id,
                ProfessorOutreachRecord.scholarship_id == payload.scholarship_id,
                ProfessorOutreachRecord.professor_id == payload.professor_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _to_response(existing)

    now = datetime.now(timezone.utc)
    row = ProfessorOutreachRecord(
        user_id=user.id,
        scholarship_id=payload.scholarship_id,
        professor_id=payload.professor_id,
        template_id=payload.template_id,
        draft_subject=_reject_markup(payload.draft_subject, "Subject", MAX_SUBJECT_LENGTH),
        draft_body=_reject_markup(payload.draft_body, "Draft body", MAX_DRAFT_BODY_LENGTH),
        next_action=_reject_markup(payload.next_action, "Next action", MAX_NEXT_ACTION_LENGTH),
        status=str(OutreachStatus.NOT_CONTACTED),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent identical request. The other writer's row
        # is the correct answer, not an error.
        db.rollback()
        existing = db.execute(
            select(ProfessorOutreachRecord).where(
                and_(
                    ProfessorOutreachRecord.user_id == user.id,
                    ProfessorOutreachRecord.scholarship_id == payload.scholarship_id,
                    ProfessorOutreachRecord.professor_id == payload.professor_id,
                )
            )
        ).scalar_one()
        return _to_response(existing)
    db.refresh(row)
    return _to_response(row)


@router.patch("/{record_id}", response_model=OutreachResponse)
def update_outreach(
    record_id: int,
    payload: OutreachUpdateRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> OutreachResponse:
    """Update one record, refusing a write based on a stale read.

    The client must send back the ``version`` it read. A mismatch means another
    tab saved in between, and overwriting it would silently destroy whatever the
    student typed there, so this answers 409 instead.
    """
    _rate_limit(user)
    row = _owned_record(db, record_id, user)

    if row.version != payload.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This record changed since you loaded it. Reload and try again.",
        )

    if payload.status is not None and payload.status != row.status:
        if payload.status not in _RECOGNISED_OUTREACH_STATUSES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "That outreach status is not recognised.",
            )
        if not outreach_transition_is_legal(row.status, payload.status):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"An outreach record cannot move from '{row.status}' to '{payload.status}'.",
            )

    now = datetime.now(timezone.utc)
    if payload.status is not None:
        row.status = payload.status
        if payload.status == str(OutreachStatus.SENT):
            # First contact is recorded once and never rewritten by a later send.
            if row.first_contacted_at is None:
                row.first_contacted_at = now
            row.last_contacted_at = now
        if payload.status in (str(OutreachStatus.POSITIVE), str(OutreachStatus.NEGATIVE)):
            row.response_at = now
            row.response_status = payload.response_status or payload.status
        if payload.status == str(OutreachStatus.NOT_CONTACTED):
            row.first_contacted_at = None
            row.last_contacted_at = None

    if payload.draft_subject is not None:
        row.draft_subject = _reject_markup(payload.draft_subject, "Subject", MAX_SUBJECT_LENGTH)
    if payload.draft_body is not None:
        row.draft_body = _reject_markup(payload.draft_body, "Draft body", MAX_DRAFT_BODY_LENGTH)
    if payload.notes is not None:
        row.notes = _reject_markup(payload.notes, "Notes", MAX_NOTES_LENGTH)
    if payload.next_action is not None:
        row.next_action = _reject_markup(payload.next_action, "Next action", MAX_NEXT_ACTION_LENGTH)
    if payload.follow_up_due_at is not None:
        row.follow_up_due_at = payload.follow_up_due_at
    if payload.response_status is not None:
        row.response_status = payload.response_status

    row.version += 1
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outreach(
    record_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete one of this student's own records.

    Only the student's own tracking row is removed. Professor profiles,
    relationships and provenance are untouched, so deleting an outreach record
    never erases the verified fact that the academic is faculty at that
    institution.
    """
    _rate_limit(user)
    row = _owned_record(db, record_id, user)
    db.delete(row)
    db.commit()


__all__ = [
    "MAX_DRAFT_BODY_LENGTH",
    "MAX_NOTES_LENGTH",
    "MAX_NEXT_ACTION_LENGTH",
    "MAX_SUBJECT_LENGTH",
    "router",
]