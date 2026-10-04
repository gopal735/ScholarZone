"""Public supervisor discovery routes.

Read-only and unauthenticated, because the thing being published here is public
professional information drawn from official university pages. Nothing on these
routes reads a student, and nothing they return depends on who is asking.

The response is deliberately shaped so an empty result is still informative. A
scholarship with no verified supervisors returns 200 with an empty list and a
coverage status explaining which of the honest negatives it is - never a 404,
never a fabricated placeholder, and never a message implying the university has
no professors.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.rate_limit import RateLimitExceeded, supervisor_read_limiter
from ..database import get_db
from ..schemas import (
    ProfessorResponse,
    SupervisorCoverageResponse,
    SupervisorListResponse,
    SupervisorSummaryResponse,
)
from ..services.supervisor_public import (
    ScholarshipNotPublic,
    build_supervisor_list,
    coverage_public_state,
    count_publishable_links,
    get_coverage,
    get_public_scholarship_or_404,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scholarships", tags=["supervisors"])

#: Bounded because interests are matched term-by-term and an unbounded list would
#: turn one request into unbounded work.
MAX_INTERESTS = 20
MAX_INTEREST_LENGTH = 120


@router.get("/{scholarship_id}/supervisors", response_model=SupervisorListResponse)
def list_supervisors(
    scholarship_id: int,
    interests: list[str] = Query(default=[]),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> SupervisorListResponse:
    """Return the verified potential supervisors for one scholarship.

    ``interests`` are the student's own words and are used only for alignment.
    They are not stored, not logged and not attached to any record.
    """
    cleaned = [
        value.strip()
        for value in interests
        if isinstance(value, str) and value.strip()
    ][:MAX_INTERESTS]
    cleaned = [value[:MAX_INTEREST_LENGTH] for value in cleaned]

    try:
        supervisor_read_limiter.check(f"read:{scholarship_id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please slow down.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    try:
        coverage, professors = build_supervisor_list(db, scholarship_id, cleaned, limit)
    except ScholarshipNotPublic:
        # One answer for "absent" and "not publicly visible". A 403 here would
        # confirm that an archived or quarantined record exists at this id.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scholarship not found.")

    return SupervisorListResponse(
        scholarship_id=scholarship_id,
        coverage=SupervisorCoverageResponse(**coverage),
        supervisors=[ProfessorResponse(**professor) for professor in professors],
    )


@router.get("/{scholarship_id}/supervisor-summary", response_model=SupervisorSummaryResponse)
def supervisor_summary(
    scholarship_id: int,
    db: Session = Depends(get_db),
) -> SupervisorSummaryResponse:
    """Return just the coverage state, for a scholarship card.

    Separate from the list route so a page of forty cards does not fetch forty
    professor lists. The count is read from the coverage row rather than
    recounted, so this stays a single small query.
    """
    try:
        supervisor_read_limiter.check(f"read-summary:{scholarship_id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please slow down.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    try:
        get_public_scholarship_or_404(db, scholarship_id)
    except ScholarshipNotPublic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scholarship not found.")

    coverage = get_coverage(db, scholarship_id)
    state = coverage_public_state(coverage)
    return SupervisorSummaryResponse(
        scholarship_id=scholarship_id,
        coverage_status=state["coverage_status"],
        verified_supervisor_count=state["verified_supervisor_count"],
        last_checked_at=state["last_checked_at"],
        discovery_pending=state["discovery_pending"],
    )


__all__ = ["MAX_INTERESTS", "MAX_INTEREST_LENGTH", "router"]