"""Business-level operations for scholarship discovery."""

from datetime import date, timedelta
from math import ceil

from sqlalchemy import asc, func, or_, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..repositories.scholarships import (
    get_scholarship_by_id,
    list_scholarships,
    public_visibility_conditions,
)
from ..schemas import PaginationMetadata, ScholarshipListResponse, ScholarshipQuery, ScholarshipVerificationUpdate


def get_scholarship_directory(session: Session, query: ScholarshipQuery) -> ScholarshipListResponse:
    scholarships, total = list_scholarships(session, query)
    return ScholarshipListResponse(
        items=scholarships,
        pagination=PaginationMetadata(
            page=query.page,
            limit=query.limit,
            total=total,
            total_pages=ceil(total / query.limit) if total else 0,
        ),
    )


def get_scholarship_details(session: Session, scholarship_id: int):
    """The public read path for one scholarship, scoped to the public universe.

    This used to call ``get_scholarship_by_id``, which is a bare primary-key
    lookup. That made the catalogue's detail endpoint a second, larger universe
    than its own list: anything excluded from ``/scholarships`` - archived,
    quarantined, awaiting review, or failing the image gate - was still fully
    readable by walking ids. The list and the detail disagreed, and the detail
    was the more permissive of the two, which is the wrong way round for a trust
    surface.

    The predicate is the canonical one rather than a restatement of it. A copy is
    exactly how a list and a detail page drift apart, and this repository already
    carries a test refusing a second definition.

    The deliberately permissive ``get_scholarship_by_id`` is left untouched: the
    verification pipeline and the administrator's verify endpoint have to reach
    records that are *meant* to be invisible to applicants, and tightening the
    shared loader would have broken them without closing this hole. The boundary
    belongs here, on the public read.
    """
    scholarship = session.scalar(
        select(Scholarship)
        .where(Scholarship.id == scholarship_id)
        .where(*public_visibility_conditions())
    )
    if scholarship is None:
        # The caller turns this into the same 404 a missing id produces, so the
        # response cannot be used to discover that a hidden record exists.
        return None

    dirty = False
    for field in (
        "eligibility",
        "benefits",
        "coverage",
        "requirements",
        "documents",
        "application_method",
    ):
        if getattr(scholarship, field) is None:
            setattr(scholarship, field, [])
            dirty = True

    if dirty:
        session.commit()
        session.refresh(scholarship)

    return scholarship


def pending_review_conditions(today: date | None = None):
    """The one definition of "this record is awaiting a verification decision".

    A record qualifies on any one of three independent grounds, so the queue is
    not merely "status says needs_review": a record can also fall due for periodic
    re-verification, or have never been verified at all. Expressed once here so
    the queue and any count derived from it cannot drift apart.
    """
    return (
        or_(
            Scholarship.verification_status == "needs_review",
            Scholarship.next_verification_due <= (today or date.today()),
            Scholarship.last_verified_date.is_(None),
        )
    )


def get_verification_queue(session: Session) -> list[Scholarship]:
    statement = (
        select(Scholarship)
        .where(pending_review_conditions())
        .order_by(Scholarship.next_verification_due.asc().nullsfirst())
    )
    return list(session.scalars(statement))


def verify_scholarship(session: Session, scholarship_id: int, payload: ScholarshipVerificationUpdate) -> Scholarship | None:
    scholarship = get_scholarship_by_id(session, scholarship_id)
    if scholarship is None:
        return None

    scholarship.last_verified_date = date.today()
    scholarship.next_verification_due = date.today() + timedelta(days=90)
    scholarship.verification_status = payload.verification_status
    scholarship.verified_by = payload.verified_by
    scholarship.verification_notes = payload.verification_notes

    session.commit()
    session.refresh(scholarship)
    return scholarship
