"""Public scholarship discovery endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Scholarship
from ..schemas import (
    ScholarshipDetailResponse,
    ScholarshipListResponse,
    ScholarshipQuery,
    ScholarshipSort,
    ScholarshipStatus,
    ScholarshipStatsResponse,
    ScholarshipVerificationUpdate,
)
from ..services.scholarships import get_scholarship_details, get_scholarship_directory, get_verification_queue, verify_scholarship


router = APIRouter(prefix="/scholarships", tags=["scholarships"])


@router.get("", response_model=ScholarshipListResponse)
def list_scholarships_endpoint(
    search: Annotated[str | None, Query(max_length=100)] = None,
    country: Annotated[str | None, Query(max_length=120)] = None,
    degree: Annotated[str | None, Query(max_length=255)] = None,
    funding: Annotated[str | None, Query(max_length=120)] = None,
    deadline_month: Annotated[int | None, Query(ge=1, le=12)] = None,
    listing_status: Annotated[ScholarshipStatus | None, Query(alias="status")] = None,
    sort: ScholarshipSort = ScholarshipSort.DEFAULT,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
    session: Session = Depends(get_db),
) -> ScholarshipListResponse:
    query = ScholarshipQuery(
        search=search,
        country=country,
        degree=degree,
        funding=funding,
        deadline_month=deadline_month,
        status=listing_status,
        sort=sort,
        page=page,
        limit=limit,
    )
    return get_scholarship_directory(session, query)


@router.get("/stats", response_model=ScholarshipStatsResponse)
def get_scholarship_stats(
    session: Session = Depends(get_db),
) -> ScholarshipStatsResponse:
    """Live aggregate statistics for the public homepage and trust bar."""
    total = session.execute(select(func.count(Scholarship.id))).scalar() or 0
    countries = session.execute(select(func.count(func.distinct(Scholarship.country)))).scalar() or 0
    open_count = session.execute(
        select(func.count(Scholarship.id)).where(Scholarship.status == "open")
    ).scalar() or 0
    closing_soon = session.execute(
        select(func.count(Scholarship.id)).where(Scholarship.status == "closing-soon")
    ).scalar() or 0
    upcoming = session.execute(
        select(func.count(Scholarship.id)).where(Scholarship.status == "upcoming")
    ).scalar() or 0
    verified_active = session.execute(
        select(func.count(Scholarship.id)).where(
            Scholarship.verification_status == "active"
        )
    ).scalar() or 0
    fully_funded = session.execute(
        select(func.count(Scholarship.id)).where(
            Scholarship.funding.ilike("%fully funded%"),
                       Scholarship.funding.not_ilike("%partial%"),
        )
    ).scalar() or 0
    with_image = session.execute(
        select(func.count(Scholarship.id)).where(
            Scholarship.image_url.isnot(None),
            Scholarship.image_url != "",
        )
    ).scalar() or 0
    with_official_source = session.execute(
        select(func.count(Scholarship.id)).where(
            Scholarship.official_source.isnot(None),
            Scholarship.official_source != "",
        )
    ).scalar() or 0

    return ScholarshipStatsResponse(
        total=total,
        countries=countries,
        open=open_count,
        closing_soon=closing_soon,
        upcoming=upcoming,
        verified_active=verified_active,
        fully_funded=fully_funded,
        with_image=with_image,
        with_official_source=with_official_source,
    )


@router.get("/verification-queue", response_model=list[ScholarshipDetailResponse])
def get_verification_queue_endpoint(
    session: Session = Depends(get_db),
) -> list[ScholarshipDetailResponse]:
    scholarships = get_verification_queue(session)
    return scholarships


@router.patch("/{scholarship_id}/verify", response_model=ScholarshipDetailResponse)
def verify_scholarship_endpoint(
    scholarship_id: Annotated[int, Path(ge=1)],
    payload: ScholarshipVerificationUpdate,
    session: Session = Depends(get_db),
) -> ScholarshipDetailResponse:
    scholarship = verify_scholarship(session, scholarship_id, payload)
    if scholarship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scholarship not found")

    return scholarship


@router.get("/{scholarship_id}", response_model=ScholarshipDetailResponse)
def get_scholarship_endpoint(
    scholarship_id: Annotated[int, Path(ge=1)],
    session: Session = Depends(get_db),
) -> ScholarshipDetailResponse:
    scholarship = get_scholarship_details(session, scholarship_id)
    if scholarship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scholarship not found")

    return scholarship


@router.get("/debug/raw/{scholarship_id}")
def debug_raw_scholarship(
    scholarship_id: Annotated[int, Path(ge=1)],
    session: Session = Depends(get_db),
):
    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scholarship not found")

    from sqlalchemy import inspect as sa_inspect
    raw = {}
    for attr in sa_inspect(scholarship).attrs:
        raw[attr.key] = attr.value
    return raw


@router.get("/debug/fix-null-lists")
def debug_fix_null_lists(
    session: Session = Depends(get_db),
):
    from sqlalchemy import text
    null_eligibility = session.execute(
        text("SELECT id FROM scholarships WHERE eligibility IS NULL")
    ).fetchall()
    null_application_method = session.execute(
        text("SELECT id FROM scholarships WHERE application_method IS NULL")
    ).fetchall()

    fixed = []
    for row in null_eligibility + null_application_method:
        sid = row[0]
        scholarship = session.get(Scholarship, sid)
        if scholarship.eligibility is None:
            scholarship.eligibility = []
        if scholarship.application_method is None:
            scholarship.application_method = []
        fixed.append(sid)

    session.commit()
    return {
        "fixed_ids": fixed,
        "null_eligibility_count": len(null_eligibility),
        "null_application_method_count": len(null_application_method),
    }