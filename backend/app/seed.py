"""Safe bootstrap for legacy records and the canonical verified catalogue."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .data.verified_scholarships import VERIFIED_SCHOLARSHIPS
from .models import Scholarship, ScholarshipVerificationHistory
from .services.lifecycle_manager import apply_lifecycle_transition, evaluate_lifecycle
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
        has_authored_status = session.scalar(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship.id,
                ScholarshipVerificationHistory.field_name == "status",
            )
        ) is not None
        if has_authored_status:
            continue

        evaluation = evaluate_lifecycle(scholarship)
        if evaluation.should_transition and evaluation.transition_allowed:
            result = apply_lifecycle_transition(session, scholarship, evaluation)
            if result is not None:
                updated_count += 1

    session.flush()
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
    import sys
    from pathlib import Path
    from .database import get_session_factory

    # Add backend root to path for scripts import
    BACKEND_ROOT = Path(__file__).resolve().parents[1]
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    from scripts.seed_real_scholarships import _seed_catalogue, _load_master_id_map
    from app.data.verified_scholarships import VERIFIED_SCHOLARSHIPS
    from app.data.additional_scholarships import ADDITIONAL_VERIFIED_SCHOLARSHIPS
    from app.seed import refresh_scholarship_statuses

    master_id_map = _load_master_id_map()
    if master_id_map:
        print(f"Loaded {len(master_id_map)} master IDs for backward compatibility")

    with get_session_factory()() as session:
        verified_urls = {s.official_source_url for s in VERIFIED_SCHOLARSHIPS}
        additional_urls = {s.official_source_url for s in ADDITIONAL_VERIFIED_SCHOLARSHIPS}
        canonical_urls = verified_urls | additional_urls
        
        created_count, updated_count = _seed_catalogue(session, master_id_map, verified_urls, additional_urls, canonical_urls)
        
        # Evaluate lifecycle statuses for all records
        status_changes = refresh_scholarship_statuses(session)
        if status_changes:
            print(f"Lifecycle status changes: {status_changes}")
        
        # Ensure lifecycle changes are persisted
        session.commit()
        
        print(f"Created {created_count} scholarship record(s); updated {updated_count} record(s).")
        return created_count
