"""Admin Verification Center API.

Everything here is private. A request must present the administrator secret in
``X-Admin-Secret``; :func:`app.core.admin_auth.require_admin_secret` decides that
before any handler runs, so hiding the page is never what keeps the queue closed.

Two rules shape the whole module:

* ``verification_status`` is the only truth about verification. The stored
  ``is_verified`` boolean is read for display as a diagnostic, and is never used
  to decide membership of the queue, a filter, or a published claim.
* Public versus storage-only is decided by the directory's own
  ``public_visibility_conditions``. The predicate is reused, not restated, so an
  administrator is never shown a different catalogue from the one applicants see.

Every count is computed by the database from the rows themselves. Nothing here
knows how many records there are.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, String, and_, func, or_, select
from sqlalchemy.orm import Session

from ..core.admin_auth import require_admin_secret
from ..database import get_db
from ..models import Scholarship, ScholarshipReview, ScholarshipVerificationHistory
from ..repositories.scholarships import public_visibility_conditions
from ..services.scholarships import pending_review_conditions
from ..verification_contract import public_verified_from_status

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/verification",
    tags=["admin"],
    dependencies=[Depends(require_admin_secret)],
)

#: The decisions this backend can actually represent. ``ScholarshipVerificationUpdate``
#: already constrains ``verification_status`` to these three states, so the admin
#: surface offers exactly those and no fourth state is invented here.
DECISION_VERIFY = "verify"
DECISION_KEEP_REVIEW = "keep_under_review"
DECISION_REJECT = "reject"

DECISION_TARGET_STATUS: dict[str, str] = {
    DECISION_VERIFY: "active",
    DECISION_KEEP_REVIEW: "needs_review",
    DECISION_REJECT: "inactive",
}

#: ``ScholarshipReview.decision`` is the audit record's own vocabulary.
DECISION_AUDIT_LABEL: dict[str, str] = {
    DECISION_VERIFY: "approved",
    DECISION_KEEP_REVIEW: "pending",
    DECISION_REJECT: "rejected",
}

PUBLIC_SCOPE = "public"
STORAGE_ONLY_SCOPE = "storage_only"
ALL_SCOPES = "all"

SORTABLE = ("next_verification_due", "updated_at", "deadline_date", "country", "title")


class AdminDecisionRequest(BaseModel):
    """One administrator's decision on one record.

    ``expected_updated_at`` and ``expected_verification_status`` are both
    required. The timestamp alone is not sufficient: it is written with
    second granularity, so two decisions inside the same second would produce an
    identical token and the second would silently overwrite the first. Pairing it
    with the status the reviewer was looking at closes that window.
    """

    decision: Literal["verify", "keep_under_review", "reject"]
    rationale: str = Field(min_length=3, max_length=2000)
    evidence_source_url: str | None = Field(default=None, max_length=2048)
    expected_updated_at: datetime
    expected_verification_status: str = Field(max_length=32)


class AdminScholarshipDetail(BaseModel):
    scholarship_id: int
    overview: dict
    claims: dict
    sources: dict
    review_flags: list[dict]
    conflicts: list[dict]
    history: list[dict]
    scope: str
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _public_ids_subquery() -> Select:
    return select(Scholarship.id).where(and_(*public_visibility_conditions()))


def _scope_of(session: Session, row: Scholarship) -> str:
    """Whether the directory would publish this record, per the canonical predicate."""
    matches = session.execute(
        select(Scholarship.id).where(
            Scholarship.id == row.id, and_(*public_visibility_conditions())
        )
    ).first()
    return PUBLIC_SCOPE if matches else STORAGE_ONLY_SCOPE


def _conflict_rows(session: Session, scholarship_id: int) -> list[ScholarshipReview]:
    return list(
        session.scalars(
            select(ScholarshipReview)
            .where(ScholarshipReview.scholarship_id == scholarship_id)
            .order_by(ScholarshipReview.id)
        )
    )


def _open_conflict_count(session: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = session.execute(
        select(ScholarshipReview.scholarship_id, func.count(ScholarshipReview.id))
        .where(
            ScholarshipReview.scholarship_id.in_(ids),
            ScholarshipReview.decision == "pending",
        )
        .group_by(ScholarshipReview.scholarship_id)
    ).all()
    return {int(sid): int(count) for sid, count in rows}


def _row_summary(session: Session, row: Scholarship, conflicts: int) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "country": row.country,
        "degree": row.degree,
        "funding": row.funding,
        "deadline_display": row.deadline_display,
        "deadline_date": row.deadline_date.isoformat() if row.deadline_date else None,
        "status": row.status,
        "verification_status": row.verification_status,
        # Derived from the status, never from the legacy column.
        "public_verified": public_verified_from_status(row.verification_status),
        "legacy_is_verified": row.is_verified,
        "legacy_agrees_with_status": row.is_verified
        == public_verified_from_status(row.verification_status),
        "scope": _scope_of(session, row),
        "is_archived": row.is_archived,
        "official_source": row.official_source,
        "official_source_url": row.official_source_url,
        "open_conflicts": conflicts,
        "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
        "last_verified_date": row.last_verified_date.isoformat() if row.last_verified_date else None,
        "next_verification_due": row.next_verification_due.isoformat()
        if row.next_verification_due
        else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@router.get("/summary")
def get_summary(session: Session = Depends(get_db)) -> dict:
    """Live review populations, computed from the rows on every call.

    Reported as three separate populations because they answer different
    questions: what needs a decision at all, what an applicant can currently see
    needing one, and what is being held back. The last is legitimate work, not
    an oversight, and collapsing it into the first would hide 25 real reviews.
    """
    pending = pending_review_conditions()
    public_ids = _public_ids_subquery()

    storage_wide = session.scalar(
        select(func.count()).select_from(Scholarship).where(pending)
    )
    public_pending = session.scalar(
        select(func.count()).select_from(Scholarship).where(pending, Scholarship.id.in_(public_ids))
    )
    storage_only_pending = session.scalar(
        select(func.count()).select_from(Scholarship).where(pending, ~Scholarship.id.in_(public_ids))
    )
    archived_pending = session.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(pending, Scholarship.is_archived.is_(True))
    )
    conflicts = session.scalar(
        select(func.count())
        .select_from(ScholarshipReview)
        .where(ScholarshipReview.decision == "pending")
    )
    return {
        "storage_wide_pending": int(storage_wide or 0),
        "public_pending": int(public_pending or 0),
        "storage_only_pending": int(storage_only_pending or 0),
        "archived_pending": int(archived_pending or 0),
        "open_field_conflicts": int(conflicts or 0),
        "as_of": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


@router.get("/queue")
def get_queue(
    session: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=200),
    verification_status: str | None = Query(default=None, max_length=32),
    scope: Literal["all", "public", "storage_only"] = Query(default="all"),
    has_conflicts: bool | None = Query(default=None),
    source: str | None = Query(default=None, max_length=120),
    sort: str = Query(default="next_verification_due"),
    order: Literal["asc", "desc"] = Query(default="asc"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """One page of the review queue, filtered and sorted in the database.

    The browser never receives the full table. Every filter is a SQL predicate so
    a queue of thousands costs the same as a queue of dozens.
    """
    if sort not in SORTABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot sort by {sort!r}. Allowed: {', '.join(SORTABLE)}.",
        )

    conditions = [pending_review_conditions()]
    if verification_status:
        conditions.append(Scholarship.verification_status == verification_status)
    if search:
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                Scholarship.title.ilike(term, escape="\\"),
                Scholarship.country.ilike(term, escape="\\"),
                func.cast(Scholarship.id, String).like(term.strip()),
            )
        )
    if source:
        conditions.append(Scholarship.official_source.ilike(f"%{source.strip()}%", escape="\\"))

    public_ids = _public_ids_subquery()
    if scope == PUBLIC_SCOPE:
        conditions.append(Scholarship.id.in_(public_ids))
    elif scope == STORAGE_ONLY_SCOPE:
        conditions.append(~Scholarship.id.in_(public_ids))

    where = and_(*conditions)

    # The conflict filter is part of the query, so it must be applied before the
    # total is counted. Counting first would report a total for an unfiltered set
    # while the page below it showed filtered rows.
    if has_conflicts is True:
        conflict_ids = select(ScholarshipReview.scholarship_id).where(
            ScholarshipReview.decision == "pending"
        )
        where = and_(where, Scholarship.id.in_(conflict_ids))
    elif has_conflicts is False:
        conflict_ids = select(ScholarshipReview.scholarship_id).where(
            ScholarshipReview.decision == "pending"
        )
        where = and_(where, ~Scholarship.id.in_(conflict_ids))

    total = session.scalar(select(func.count()).select_from(Scholarship).where(where))
    total = int(total or 0)

    column = getattr(Scholarship, sort)
    direction = column.asc if order == "asc" else column.desc
    # id is the tiebreaker so equal keys cannot reorder between requests, which
    # is what makes pagination stable.
    statement = (
        select(Scholarship)
        .where(where)
        .order_by(direction(), Scholarship.id.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = list(session.scalars(statement))
    conflicts = _open_conflict_count(session, [r.id for r in rows])

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "order": order,
        "items": [_row_summary(session, r, conflicts.get(r.id, 0)) for r in rows],
    }


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


@router.get("/scholarships/{scholarship_id}", response_model=AdminScholarshipDetail)
def get_detail(scholarship_id: int, session: Session = Depends(get_db)) -> AdminScholarshipDetail:
    row = session.get(Scholarship, scholarship_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scholarship not found.")

    reviews = _conflict_rows(session, scholarship_id)
    flags, conflicts = [], []
    for r in reviews:
        flags.append(
            {
                "review_id": r.id,
                "field_name": r.field_name,
                "conflict_reason": r.conflict_reason,
                "verification_state": r.verification_state,
                "confidence": r.confidence,
                "decision": r.decision,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
        # Both sides are reported verbatim. Averaging them into one value would
        # invent an answer no source supports.
        conflicts.append(
            {
                "review_id": r.id,
                "field_name": r.field_name,
                "current_value": r.current_value,
                "proposed_value": r.proposed_value,
                "conflict_reason": r.conflict_reason,
                "source_urls": r.source_urls or [],
                "evidence_text": r.evidence_text,
                "decision": r.decision,
            }
        )

    history = [
        {
            "id": h.id,
            "field_name": h.field_name,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "change_type": h.change_type,
            "source_url": h.source_url,
            "evidence_text": h.evidence_text,
            "confidence": h.confidence,
            "verification_status": h.verification_status,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
            .order_by(ScholarshipVerificationHistory.created_at.desc(), ScholarshipVerificationHistory.id.desc())
        )
    ]

    return AdminScholarshipDetail(
        scholarship_id=scholarship_id,
        scope=_scope_of(session, row),
        overview={
            "title": row.title,
            "country": row.country,
            "degree": row.degree,
            "region": row.region,
            "funding": row.funding,
            "deadline_display": row.deadline_display,
            "deadline_date": row.deadline_date.isoformat() if row.deadline_date else None,
            "status": row.status,
            "is_archived": row.is_archived,
            "program_type": row.program_type,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        },
        claims={
            "verification_status": row.verification_status,
            # The single published meaning of verification, from the shared contract.
            "public_verified": public_verified_from_status(row.verification_status),
            "legacy_is_verified": row.is_verified,
            "legacy_agrees_with_status": row.is_verified
            == public_verified_from_status(row.verification_status),
            "verified_by": row.verified_by,
            "verification_notes": row.verification_notes,
            "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
            "next_verification_due": row.next_verification_due.isoformat()
            if row.next_verification_due
            else None,
            "image_url": row.image_url,
            "image_kind": row.image_kind,
            "image_source_type": row.image_source_type,
            "image_verified_at": row.image_verified_at.isoformat() if row.image_verified_at else None,
            "image_evaluation_status": row.image_evaluation_status,
        },
        sources={
            "official_source": row.official_source,
            "official_source_url": row.official_source_url,
            "official_updates_url": row.official_updates_url,
            "catalogue_url": row.catalogue_url,
            "application_link": row.application_link,
            "last_verified_date": row.last_verified_date.isoformat() if row.last_verified_date else None,
        },
        review_flags=flags,
        conflicts=conflicts,
        history=history,
    )


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@router.post("/scholarships/{scholarship_id}/decision")
def post_decision(
    scholarship_id: int,
    payload: AdminDecisionRequest,
    session: Session = Depends(get_db),
    _admin: str = Depends(require_admin_secret),
) -> dict:
    """Record one administrator's decision on one record.

    There is deliberately no bulk variant. A verification decision carries a
    claim about a specific source, and reviewing sources in bulk is how an
    unsupported claim gets published.
    """
    row = session.get(Scholarship, scholarship_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scholarship not found.")

    target_status = DECISION_TARGET_STATUS[payload.decision]
    current_version = _as_utc(row.updated_at)
    if current_version != _as_utc(payload.expected_updated_at) or (
        row.verification_status != payload.expected_verification_status
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This record changed since it was opened. Reload to see the current "
                "state before deciding, so a newer decision is not overwritten."
            ),
        )

    previous_status = row.verification_status
    if previous_status == target_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Record is already {target_status!r}; nothing to decide.",
        )

    now = datetime.now(timezone.utc)
    row.verification_status = target_status
    # The legacy boolean is kept consistent with the authoritative status so the
    # internal bookkeeping column cannot drift into contradicting it again.
    row.is_verified = target_status == "active"
    row.last_verified_at = now
    row.verified_by = "admin"
    row.verification_notes = payload.rationale
    if target_status == "needs_review":
        row.next_verification_due = None

    session.add(
        ScholarshipVerificationHistory(
            scholarship_id=scholarship_id,
            field_name="verification_status",
            old_value=previous_status,
            new_value=target_status,
            change_type="admin_decision",
            source_url=payload.evidence_source_url or row.official_source_url,
            evidence_text=payload.rationale,
            confidence=None,
            verification_status=target_status,
        )
    )
    # The review row carries the actor. The history table records the state
    # change but has no actor column, so the who lives here.
    session.add(
        ScholarshipReview(
            scholarship_id=scholarship_id,
            field_name="verification_status",
            current_value=previous_status,
            proposed_value=target_status,
            conflict_reason=f"admin decision: {payload.decision}",
            verification_state=target_status,
            confidence=None,
            source_urls=[u for u in [payload.evidence_source_url, row.official_source_url] if u],
            evidence_text=payload.rationale,
            decision=DECISION_AUDIT_LABEL[payload.decision],
            created_at=now,
            reviewed_at=now,
            reviewed_by="admin",
            reviewer_note=payload.rationale,
        )
    )
    session.commit()

    logger.info(
        "Admin decision on scholarship %s: %s -> %s", scholarship_id, previous_status, target_status
    )
    return {
        "scholarship_id": scholarship_id,
        "previous_status": previous_status,
        "verification_status": target_status,
        "public_verified": public_verified_from_status(target_status),
        "scope": _scope_of(session, row),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise a timestamp so a client round-trip cannot fake a mismatch."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "DECISION_AUDIT_LABEL",
    "DECISION_TARGET_STATUS",
    "AdminDecisionRequest",
    "AdminScholarshipDetail",
    "router",
]