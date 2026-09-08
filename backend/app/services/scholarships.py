"""Business-level operations for scholarship discovery."""

from datetime import date, timedelta
from math import ceil

from sqlalchemy import asc, func, or_, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..repositories.scholarships import get_scholarship_by_id, list_scholarships
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
    scholarship = get_scholarship_by_id(session, scholarship_id)
    if scholarship is None:
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


def get_verification_queue(session: Session) -> list[Scholarship]:
    today = date.today()
    statement = (
        select(Scholarship)
        .where(
            or_(
                Scholarship.verification_status == "needs_review",
                Scholarship.next_verification_due <= today,
                Scholarship.last_verified_date.is_(None),
            )
        )
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
