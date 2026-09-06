"""Pydantic schemas for the public scholarship API."""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ScholarshipSort(str, Enum):
    DEFAULT = "default"
    RECOMMENDED = "recommended"
    RECENTLY_ADDED = "recently-added"
    RECENTLY_UPDATED = "recently-updated"
    DEADLINE_SOON = "deadline-soon"
    FULLY_FUNDED = "fully-funded"
    DEADLINE_EARLIEST = "deadline-earliest"
    DEADLINE_LATEST = "deadline-latest"
    NAME_ASC = "name-asc"
    NAME_DESC = "name-desc"


class ScholarshipStatus(str, Enum):
    OPEN = "open"
    UPCOMING = "upcoming"
    CLOSING_SOON = "closing-soon"
    CLOSED = "closed"


class ImageKind(str, Enum):
    PROGRAM_IMAGE = "program_image"
    OFFICIAL_BANNER = "official_banner"
    OFFICIAL_LOGO = "official_logo"


class ScholarshipQuery(BaseModel):
    """Validated values accepted by the directory endpoint."""

    search: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=120)
    degree: str | None = Field(default=None, max_length=255)
    funding: str | None = Field(default=None, max_length=120)
    deadline_month: int | None = Field(default=None, ge=1, le=12)
    status: ScholarshipStatus | None = None
    sort: ScholarshipSort = ScholarshipSort.DEFAULT
    page: int = Field(default=1, ge=1, le=100_000)
    limit: int = Field(default=12, ge=1, le=100)


class ScholarshipResponse(BaseModel):
    """Frontend-compatible scholarship list item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    name: str = Field(validation_alias=AliasChoices("name", "title"))
    country: str
    degree: str
    degree_levels: str = Field(validation_alias=AliasChoices("degree_levels", "degree"))
    funding: str
    funding_type: str = Field(validation_alias=AliasChoices("funding_type", "funding"))
    deadline: str | None = None
    deadline_date: date | None = None
    deadline_precision: str
    status: ScholarshipStatus
    verified: bool = Field(validation_alias=AliasChoices("verified", "is_verified"))
    last_verified_at: date | None = None
    verification_status: str = "active"
    next_verification_due: date | None = None
    verified_by: str | None = None
    verification_notes: str | None = None
    updated_at: datetime
    image_url: str | None = None
    image_source_type: str | None = None
    image_kind: str | None = None


class ScholarshipDetailResponse(ScholarshipResponse):
    description: str | None = None
    region: str | None = None
    duration: str | None = None
    application_period: str | None = None
    official_source: str | None = None
    official_source_url: str | None = None
    catalogue_url: str | None = None
    official_updates_url: str | None = None
    application_link: str | None = None
    image_url: str | None = None
    image_source_url: str | None = None
    image_source_type: str | None = None
    image_kind: str | None = None
    image_verified_at: datetime | None = None
    image_alt_text: str | None = None
    eligibility: list[str] = Field(default_factory=list)
    eligibility_summary: str | None = None
    benefits: list[str] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("required_documents", "documents"),
    )
    english_requirement: str | None = None
    application_method: list[str] = Field(default_factory=list)
    selection_notes: str | None = None
    program_type: str | None = None
    best_fit: str | None = None
    last_verified_date: date | None = None
    notes: str | None = None


class PaginationMetadata(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class ScholarshipListResponse(BaseModel):
    items: list[ScholarshipResponse]
    pagination: PaginationMetadata


class ScholarshipImageVerifyRequest(BaseModel):
    scholarship_id: int = Field(ge=1)
    image_url: str = Field(max_length=2048)
    image_source_url: str = Field(max_length=2048)
    image_source_type: Literal[
        "official_scholarship",
        "official_university",
        "official_government",
        "official_provider",
    ]
    image_kind: ImageKind | None = None
    image_alt_text: str | None = Field(default=None, max_length=512)


class ImageReviewDecision(BaseModel):
    approved: bool
    reviewer_note: str | None = Field(default=None, max_length=1024)


class ImageReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scholarship_id: int
    scholarship_title: str | None = None
    image_url: str
    image_kind: str
    source_page: str | None = None
    source_type: str | None = None
    relevance_evidence: str | None = None
    licensing_status: str | None = None
    licensing_evidence: str | None = None
    confidence: str
    reason_for_review: str | None = None
    decision: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    reviewer_note: str | None = None
    created_at: datetime


class ScholarshipVerificationUpdate(BaseModel):
    verification_status: Literal["active", "needs_review", "inactive"]
    verification_notes: str | None = None
    verified_by: str | None = None
