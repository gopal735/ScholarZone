"""The student dashboard and the state behind it.

Every route here requires ``require_user``, which resolves the account from the
session cookie. No handler accepts a user id, so there is no code path in which
a caller can name whose data they want: ownership is decided before the handler
runs, not inside it.

The same rule governs the scholarship ids a mutation may touch. A save or an
application state change resolves the id through
``public_visibility_conditions()`` first, so a client cannot use these endpoints
to discover whether an archived or unverified record exists - the write fails
exactly as the public listing hides it.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_user
from ..models import (
    ApplicationRecord,
    Scholarship,
    SavedScholarship,
    StudentProfile,
    User,
)
from ..schemas_dashboard import (
    ApplicationState,
    ApplicationUpsertRequest,
    DashboardResponse,
    ProfileUpdateRequest,
    SavedMutationResponse,
)
from ..services.dashboard import (
    MAX_SAVED_ITEMS,
    build_dashboard,
    count_saved,
    get_profile_record,
    load_stored_profile,
)
from ..services.matching.types import MatchProfileRequest
from ..repositories.scholarships import public_visibility_conditions

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _require_public_scholarship(db: Session, scholarship_id: int) -> Scholarship:
    """Resolve an id the student is allowed to act on.

    Returns 404 for anything the public directory would not list. The response
    is deliberately identical to a genuinely absent record, so this endpoint
    cannot be used to test for the existence of a hidden or archived row.
    """
    record = db.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id).where(*public_visibility_conditions())
    ).scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That scholarship is not available.",
        )
    return record


@router.get("", response_model=DashboardResponse)
@router.get("/", response_model=DashboardResponse, include_in_schema=False)
def read_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    as_of: date | None = Query(
        default=None,
        description="Evaluate deadlines as of this date. Defaults to today; injectable so a response is reproducible.",
    ),
) -> DashboardResponse:
    """Everything the dashboard renders, for one student, in one request.

    A single aggregate rather than several parallel calls, so the sections
    cannot describe different populations: Match, Count Intelligence, the
    shortlist and the application states are all read against the same
    ``as_of`` in one transaction.
    """
    return build_dashboard(db, user, as_of=as_of)


@router.get("/profile")
def read_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """The stored Match profile exactly as the engine will read it."""
    profile = load_stored_profile(db, user.id)
    return {
        "profile": profile.model_dump(mode="json", exclude_none=True) if profile else {},
        "is_empty": profile is None,
    }


@router.put("/profile")
def write_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Save the student's Match profile.

    The body is validated through ``MatchProfileRequest`` before it is stored,
    so what is persisted is the engine's own schema rather than whatever the
    browser happened to send. An unknown key is a 422 rather than a silent drop:
    a field the student typed should never disappear without an error.
    """
    try:
        validated = MatchProfileRequest.model_validate(payload.profile)
    except PydanticValidationError as error:
        # The envelope accepts an object so the error can name the offending
        # field; the profile schema then has the final word on its contents.
        # Letting the ValidationError escape would surface as a 500, which tells
        # a student their own typo is a server fault.
        raise HTTPException(
            status_code=422,
            detail="That profile could not be saved because some fields were not recognised.",
        ) from error

    stored = validated.model_dump(mode="json", exclude_none=True)

    record = get_profile_record(db, user.id)
    if record is None:
        record = StudentProfile(user_id=user.id, payload=stored)
        db.add(record)
    else:
        record.payload = stored

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your profile could not be saved. Please try again.",
        ) from None

    db.refresh(record)
    return {"profile": stored, "updated_at": record.updated_at, "is_empty": False}


@router.get("/saved")
def list_saved(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """The authoritative shortlist.

    The count is returned beside the ids, so a header count can never drift
    from the list it labels.
    """
    rows = list(
        db.execute(
            select(SavedScholarship.scholarship_id)
            .where(SavedScholarship.user_id == user.id)
            .order_by(SavedScholarship.scholarship_id.asc())
            .limit(MAX_SAVED_ITEMS)
        ).scalars()
    )
    return {"scholarship_ids": list(rows), "count": len(rows)}


@router.post("/saved", response_model=SavedMutationResponse)
def save_scholarship(
    scholarship_id: int = Query(..., description="The scholarship to add to the shortlist."),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> SavedMutationResponse:
    """Add to the shortlist. Idempotent.

    Saving the same scholarship twice is a success, not a conflict: the unique
    pair makes it a no-op, which is what a double-clicked button should do.
    """
    _require_public_scholarship(db, scholarship_id)

    existing = db.execute(
        select(SavedScholarship).where(
            SavedScholarship.user_id == user.id,
            SavedScholarship.scholarship_id == scholarship_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(SavedScholarship(user_id=user.id, scholarship_id=scholarship_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

    return SavedMutationResponse(
        scholarship_id=scholarship_id, saved=True, saved_count=count_saved(db, user.id)
    )


@router.delete("/saved/{scholarship_id}", response_model=SavedMutationResponse)
def remove_saved_scholarship(
    scholarship_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> SavedMutationResponse:
    """Remove from the shortlist.

    Scoped to the caller's own row, so this removes nothing when the id belongs
    to another student - and does not say so, because that would confirm the
    item exists.
    """
    record = db.execute(
        select(SavedScholarship).where(
            SavedScholarship.user_id == user.id,
            SavedScholarship.scholarship_id == scholarship_id,
        )
    ).scalar_one_or_none()

    if record is not None:
        db.delete(record)
        db.commit()

    return SavedMutationResponse(
        scholarship_id=scholarship_id, saved=False, saved_count=count_saved(db, user.id)
    )


@router.put("/applications/{scholarship_id}")
def set_application_state(
    scholarship_id: int,
    payload: ApplicationUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """Record where the student is with one opportunity.

    The state is validated by the enum on the request body, so an unknown value
    is a 422 before it can reach the database. There is no transition table: any
    state may follow any other, because Dashboard 1.0 records a fact rather than
    driving a workflow, and inventing a legal-move matrix here would be the
    beginning of the Application Workspace rather than the end of it.
    """
    _require_public_scholarship(db, scholarship_id)

    record = db.execute(
        select(ApplicationRecord).where(
            ApplicationRecord.user_id == user.id,
            ApplicationRecord.scholarship_id == scholarship_id,
        )
    ).scalar_one_or_none()

    if record is None:
        record = ApplicationRecord(
            user_id=user.id, scholarship_id=scholarship_id, state=payload.state.value
        )
        db.add(record)
    else:
        record.state = payload.state.value

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That application state could not be saved. Please try again.",
        ) from None

    db.refresh(record)
    return {
        "scholarship_id": scholarship_id,
        "state": record.state,
        "updated_at": record.updated_at,
    }


@router.get("/applications")
def list_applications(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """The student's application states, most recently updated first."""
    rows = list(
        db.execute(
            select(ApplicationRecord)
            .where(ApplicationRecord.user_id == user.id)
            .order_by(ApplicationRecord.updated_at.desc(), ApplicationRecord.scholarship_id.asc())
        ).scalars()
    )
    return {
        "applications": [
            {
                "scholarship_id": row.scholarship_id,
                "state": row.state,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
        "count": len(rows),
        "states": [member.value for member in ApplicationState],
    }


__all__ = ["router"]