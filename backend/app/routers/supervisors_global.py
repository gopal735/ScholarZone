"""Global Supervisor Discovery routes.

Read-only and unauthenticated. Provides a global search across all eligible
OPEN and UPCOMING scholarships for supervisor discovery.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

from ..core.rate_limit import RateLimitExceeded, supervisor_read_limiter
from ..database import get_db
from ..schemas import (
    ProfessorResponse,
    OfficialContactResponse,
    SupervisorCoverageResponse,
    SupervisorListResponse,
    SupervisorSummaryResponse,
)
from ..services.supervisor_public import (
    ScholarshipNotPublic,
    SchemaNotReadyError,
    build_supervisor_list,
    coverage_public_state,
    count_publishable_links,
    get_coverage,
    get_coverage_report,
    get_public_scholarship_or_404,
    global_supervisor_search,
    GlobalSupervisorSearchRequest,
    GlobalSupervisorSearchResponse,
    GlobalSupervisorSearchResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supervisors", tags=["supervisors-global"])

# Bounded because interests are matched term-by-term and an unbounded list would
# turn one request into unbounded work.
MAX_INTERESTS = 20
MAX_INTEREST_LENGTH = 120


class GlobalSupervisorSearchRequestModel(BaseModel):
    """Request model for global supervisor search."""
    research_interests: list[str] = Field(default_factory=list, max_length=20)
    degree_levels: list[str] = Field(default_factory=list)
    lifecycle: list[str] = Field(default_factory=list)
    country: str | None = Field(default=None, max_length=120)
    subject: str | None = Field(default=None, max_length=255)
    institution: str | None = Field(default=None, max_length=255)
    contact_types: list[str] = Field(default_factory=list)
    verified_email_only: bool = False
    scholarship_id: int | None = Field(default=None, ge=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class GlobalSupervisorSearchResultModel(BaseModel):
    """Response model for a single global search result."""
    scholarship_id: int
    scholarship_title: str
    country: str
    degree_level: str
    original_degree_text: str
    effective_lifecycle: str
    opening_date: str | None = None
    deadline: str | None = None
    awarding_institution: str | None = None
    host_institution: str | None = None
    professor_id: int
    official_name: str
    academic_title: str | None = None
    institution: str
    department: str | None = None
    official_profile_url: str
    research_areas: list[str] = Field(default_factory=list)
    relationship_type: str
    relationship_verification_status: str
    research_alignment: dict
    official_email: str | None = None
    official_email_verified: bool = False
    official_contact_url: str | None = None
    official_department_page: str | None = None
    research_group_url: str | None = None
    source_url: str
    last_verified_at: str | None = None


class GlobalSupervisorSearchResponseModel(BaseModel):
    """Response model for global supervisor search."""
    items: list[GlobalSupervisorSearchResultModel]
    total: int
    page: int
    page_size: int
    total_pages: int


# Coverage Report Models
class ScholarshipCoverageSummaryModel(BaseModel):
    """Response model for a single scholarship coverage summary."""
    scholarship_id: int
    title: str
    country: str
    degree: str
    status: str
    coverage_status: str
    existing_contacts: int
    verified_contacts: int
    has_verified_email: bool
    research_supervisors: int
    course_instructors: int
    programme_faculty: int
    department_contacts: int
    university_leadership: int
    programme_office: int
    last_checked: str | None = None
    next_check: str | None = None
    error_summary: str | None = None


class CoverageReportModel(BaseModel):
    """Response model for the complete coverage report."""
    total_eligible: int
    open_count: int
    upcoming_count: int
    closed_excluded: int
    unknown_lifecycle: int
    
    not_started: int
    existing_contacts_audited: int
    host_mapping_pending: int
    research_in_progress: int
    partially_researched: int
    research_completed: int
    source_blocked: int
    no_public_contact_found: int
    needs_review: int
    not_applicable: int
    
    total_existing_contacts: int
    total_verified_contacts: int
    total_verified_emails: int
    total_research_supervisors: int
    total_course_instructors: int
    total_programme_faculty: int
    total_department_contacts: int
    total_university_leadership: int
    total_programme_office: int
    
    unique_institutions: int
    unique_departments: int
    
    scholarships: list[ScholarshipCoverageSummaryModel]


@router.post("/search", response_model=GlobalSupervisorSearchResponseModel)
def search_supervisors(
    request: GlobalSupervisorSearchRequestModel,
    db: Session = Depends(get_db),
) -> GlobalSupervisorSearchResponseModel:
    """Search supervisors globally across all eligible scholarships.

    Returns paginated results with scholarship and professor information.
    The default search universe is OPEN and UPCOMING publicly visible scholarships.
    """
    # Clean research interests
    cleaned_interests = [
        value.strip()[:MAX_INTEREST_LENGTH]
        for value in request.research_interests
        if isinstance(value, str) and value.strip()
    ][:MAX_INTERESTS]

    # Validate degree levels
    valid_degree_levels = ["BACHELOR", "MASTER", "PHD", "OTHER"]
    degree_levels = [d.upper() for d in request.degree_levels if d.upper() in valid_degree_levels]

    # Validate lifecycle
    valid_lifecycles = ["OPEN", "UPCOMING", "CLOSED", "UNKNOWN"]
    lifecycle = [l.upper() for l in request.lifecycle if l.upper() in valid_lifecycles]

    search_request = GlobalSupervisorSearchRequest(
        research_interests=cleaned_interests,
        degree_levels=degree_levels,
        lifecycle=lifecycle,
        country=request.country,
        subject=request.subject,
        institution=request.institution,
        contact_types=request.contact_types,
        verified_email_only=request.verified_email_only,
        scholarship_id=request.scholarship_id,
        page=request.page,
        page_size=request.page_size,
    )

    try:
        supervisor_read_limiter.check("global-search")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please slow down.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    try:
        result = global_supervisor_search(db, search_request)
    except (ProgrammingError, DBAPIError) as exc:
        # Check if it's a missing schema error
        from ..services.supervisor_public import _missing_schema_error
        if _missing_schema_error(exc):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                {
                    "error_code": "schema_not_ready",
                    "message": "Supervisor discovery schema is not ready. Missing required database object.",
                    "retry_after_seconds": 300,
                },
                headers={"Retry-After": "300"},
            )
        raise

    # Convert to response model
    items = [
        GlobalSupervisorSearchResultModel(
            scholarship_id=item.scholarship_id,
            scholarship_title=item.scholarship_title,
            country=item.country,
            degree_level=item.degree_level,
            original_degree_text=item.original_degree_text,
            effective_lifecycle=item.effective_lifecycle,
            opening_date=item.opening_date,
            deadline=item.deadline,
            awarding_institution=item.awarding_institution,
            host_institution=item.host_institution,
            professor_id=item.professor_id,
            official_name=item.official_name,
            academic_title=item.academic_title,
            institution=item.institution,
            department=item.department,
            official_profile_url=item.official_profile_url,
            research_areas=item.research_areas,
            relationship_type=item.relationship_type,
            relationship_verification_status=item.relationship_verification_status,
            research_alignment=item.research_alignment,
            official_email=item.official_email,
            official_email_verified=item.official_email_verified,
            official_contact_url=item.official_contact_url,
            official_department_page=item.official_department_page,
            research_group_url=item.research_group_url,
            source_url=item.source_url,
            last_verified_at=item.last_verified_at,
        )
        for item in result.items
    ]

    return GlobalSupervisorSearchResponseModel(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/coverage-report", response_model=CoverageReportModel)
def coverage_report(
    db: Session = Depends(get_db),
) -> CoverageReportModel:
    """Get a comprehensive coverage report for all eligible scholarships.
    
    Shows statistics on discovery progress, contact counts, and per-scholarship status.
    """
    try:
        supervisor_read_limiter.check("coverage-report")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please slow down.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    
    try:
        report = get_coverage_report(db)
    except (ProgrammingError, DBAPIError) as exc:
        from ..services.supervisor_public import _missing_schema_error
        if _missing_schema_error(exc):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                {
                    "error_code": "schema_not_ready",
                    "message": "Supervisor discovery schema is not ready. Missing required database object.",
                    "retry_after_seconds": 300,
                },
                headers={"Retry-After": "300"},
            )
        raise
    
    return CoverageReportModel(
        total_eligible=report.total_eligible,
        open_count=report.open_count,
        upcoming_count=report.upcoming_count,
        closed_excluded=report.closed_excluded,
        unknown_lifecycle=report.unknown_lifecycle,
        not_started=report.not_started,
        existing_contacts_audited=report.existing_contacts_audited,
        host_mapping_pending=report.host_mapping_pending,
        research_in_progress=report.research_in_progress,
        partially_researched=report.partially_researched,
        research_completed=report.research_completed,
        source_blocked=report.source_blocked,
        no_public_contact_found=report.no_public_contact_found,
        needs_review=report.needs_review,
        not_applicable=report.not_applicable,
        total_existing_contacts=report.total_existing_contacts,
        total_verified_contacts=report.total_verified_contacts,
        total_verified_emails=report.total_verified_emails,
        total_research_supervisors=report.total_research_supervisors,
        total_course_instructors=report.total_course_instructors,
        total_programme_faculty=report.total_programme_faculty,
        total_department_contacts=report.total_department_contacts,
        total_university_leadership=report.total_university_leadership,
        total_programme_office=report.total_programme_office,
        unique_institutions=report.unique_institutions,
        unique_departments=report.unique_departments,
        scholarships=[
            ScholarshipCoverageSummaryModel(
                scholarship_id=s.scholarship_id,
                title=s.title,
                country=s.country,
                degree=s.degree,
                status=s.status,
                coverage_status=s.coverage_status,
                existing_contacts=s.existing_contacts,
                verified_contacts=s.verified_contacts,
                has_verified_email=s.has_verified_email,
                research_supervisors=s.research_supervisors,
                course_instructors=s.course_instructors,
                programme_faculty=s.programme_faculty,
                department_contacts=s.department_contacts,
                university_leadership=s.university_leadership,
                programme_office=s.programme_office,
                last_checked=s.last_checked,
                next_check=s.next_check,
                error_summary=s.error_summary,
            )
            for s in report.scholarships
        ],
    )


__all__ = ["router"]