"""Safe bootstrap for legacy records and the canonical verified catalogue."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .data.verified_scholarships import VERIFIED_SCHOLARSHIPS
from .models import Scholarship
from .services.scholarship_ingestion import upsert_verified_scholarships


# These pre-existing records have no official source URL in this project, so
# they remain untouched by verified URL-based ingestion until official data is
# supplied. They preserve the IDs already used by saved/compare preferences.
LEGACY_BOOTSTRAP_SCHOLARSHIPS = (
    {
        "id": 2,
        "title": "ICCR Scholarship",
        "country": "India",
        "degree": "Bachelor",
        "funding": "Fully Funded",
        "deadline_date": date(2027, 4, 1),
        "deadline_display": "April 2027",
        "deadline_precision": "month",
        "status": "open",
        "is_verified": True,
    },
    {
        "id": 3,
        "title": "DAAD Scholarship",
        "country": "Germany",
        "degree": "Master",
        "funding": "Fully Funded",
        "deadline_date": date(2026, 10, 1),
        "deadline_display": "October 2026",
        "deadline_precision": "month",
        "status": "open",
        "is_verified": True,
    },
)


def get_deadline_status(deadline: date | None, today: date | None = None) -> str:
    """Derive a safe listing status from the normalized deadline date."""
    if deadline is None:
        return "open"

    current_date = today or date.today()
    if deadline < current_date:
        return "closed"
    if deadline <= current_date + timedelta(days=30):
        return "closing-soon"
    return "open"


def refresh_scholarship_statuses(session: Session) -> int:
    updated_count = 0
    for scholarship in session.scalars(select(Scholarship)):
        status = get_deadline_status(scholarship.deadline_date)
        if scholarship.status != status:
            scholarship.status = status
            updated_count += 1

    return updated_count


def seed_scholarships(session: Session) -> int:
    """Insert missing stable records without overwriting later administrative edits."""
    created_count = 0
    for record in LEGACY_BOOTSTRAP_SCHOLARSHIPS:
        if session.get(Scholarship, record["id"]) is None:
            session.add(Scholarship(**record))
            created_count += 1

    status_changes = refresh_scholarship_statuses(session)
    if created_count or status_changes:
        session.commit()

    return created_count


def seed_database() -> int:
    from .database import get_session_factory

    with get_session_factory()() as session:
        bootstrap_created = seed_scholarships(session)
        verified_created, _ = upsert_verified_scholarships(session, VERIFIED_SCHOLARSHIPS)
        return bootstrap_created + verified_created
