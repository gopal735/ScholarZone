"""Draft and template routes.

``POST /supervisor-email/draft`` returns text. It does not send, queue or schedule
anything, and there is no bulk variant of it. That absence is the privacy and
anti-spam control for 1.0, not an oversight: a student's draft is their own words
until they choose to send it, and no code path here can send on their behalf.

Identity comes from ``require_user`` — the same dependency the rest of the
student-facing surface uses — because the student's own name and stated interests
go into the generated text.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.rate_limit import RateLimitExceeded, draft_limiter
from ..database import get_db
from ..dependencies import require_user
from ..models import User
from ..models_supervisor import ProfessorProfile
from ..schemas import ContactTemplateResponse, EmailDraftRequest, EmailDraftResponse
from ..services.supervisor_email import (
    DraftRequest,
    build_draft,
    get_builtin_template,
    list_templates,
    verified_relationship,
)
from ..services.supervisor_public import ScholarshipNotPublic, get_public_scholarship_or_404

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supervisor-email", tags=["supervisor-email"])

#: Bounded so one request cannot be used to generate an unbounded amount of text.
MAX_INTERESTS = 20
MAX_INTEREST_LENGTH = 120


@router.get("/templates", response_model=list[ContactTemplateResponse])
def templates(db: Session = Depends(get_db)) -> list[ContactTemplateResponse]:
    """Return the available outreach templates. Public: they contain no data."""
    return [
        ContactTemplateResponse(
            id=row.id,
            template_key=row.template_key,
            title=row.title,
            degree_level=row.degree_level,
            subject_hint=row.subject_hint,
            body_text=row.body_text,
        )
        for row in list_templates(db)
    ]


@router.post("/draft", response_model=EmailDraftResponse)
def draft(
    payload: EmailDraftRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> EmailDraftResponse:
    """Build one personalised draft for the signed-in student.

    The student's stated interests are used for this response and are not stored.
    """
    try:
        draft_limiter.check(f"draft:{user.id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many drafts requested. Please slow down.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    try:
        scholarship = get_public_scholarship_or_404(db, payload.scholarship_id)
    except ScholarshipNotPublic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scholarship not found.")

    # A draft may only be prepared against a relationship the public API would
    # actually show. Otherwise this endpoint becomes a way to pull a professor's
    # stored details for a pairing that was never published.
    link = verified_relationship(db, payload.scholarship_id, payload.professor_id)
    if link is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "That professor is not a verified match for this scholarship.",
        )
    professor = db.get(ProfessorProfile, payload.professor_id)
    if professor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Professor not found.")

    template = get_builtin_template(payload.template_key)
    interests = [
        value[:MAX_INTEREST_LENGTH]
        for value in payload.interests
        if isinstance(value, str) and value.strip()
    ][:MAX_INTERESTS]

    result = build_draft(
        db,
        DraftRequest(
            professor=professor,
            programme_title=scholarship.title,
            degree_level=scholarship.degree or "",
            relationship_type=link.relationship_type,
            verified_availability=[],
            # ScholarZone's account has no name field, so the sign-off is left for
            # the student to complete rather than derived from their address.
            student_name="",
            student_interests=interests,
            student_field=None,
        ),
        template,
    )
    return EmailDraftResponse(**result)


__all__ = ["MAX_INTERESTS", "MAX_INTEREST_LENGTH", "router"]