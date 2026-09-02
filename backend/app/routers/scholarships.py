"""Public scholarship discovery endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ScholarshipDetailResponse, ScholarshipListResponse, ScholarshipQuery, ScholarshipSort, ScholarshipStatus, ScholarshipVerificationUpdate
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
