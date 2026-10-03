"""Pydantic schemas for the public scholarship API."""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .services.list_columns import LIST_COLUMNS
from .verification_contract import (
    UNCERTAIN_VERIFICATION_STATUS,
    normalize_public_verification_status,
    public_verified_from_status,
)


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
    OFFICIAL_OG = "official_og"
    OFFICIAL_MEDIA = "official_media"
    GENERIC_OFFICIAL = "generic_official"


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

    @field_validator("status", mode="before")
    @classmethod
    def _unknown_status_becomes_null(cls, value):
        """A status the catalogue does not define is surfaced, not raised.

        Some records carry "active" in the status column, which is a
        verification_status value rather than a round status. A strict enum made
        Pydantic raise, and because the whole page serialises together, one such
        record turned any page containing it into HTTP 500 - which is why
        /api/scholarships?limit=100&page=4 failed while page=3 succeeded.

        The value is reported as null so the interface can say "status not
        published" instead of inventing one. The underlying rows still need
        correcting; this only stops bad data from taking the catalogue offline.
        """
        if value is None:
            return None
        allowed = {member.value for member in ScholarshipStatus}
        if isinstance(value, str):
            return value if value in allowed else None
        return value

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
    status: ScholarshipStatus | None = None
    verified: bool = Field(
        default=False, validation_alias=AliasChoices("verified", "is_verified")
    )
    last_verified_at: date | None = None
    verification_status: str = UNCERTAIN_VERIFICATION_STATUS
    next_verification_due: date | None = None
    verified_by: str | None = None
    verification_notes: str | None = None
    updated_at: datetime
    image_url: str | None = None
    image_source_type: str | None = None
    image_kind: str | None = None

    @field_validator("verification_status", mode="before")
    @classmethod
    def _absent_status_is_uncertain(cls, value):
        """A record with no usable status is reported as unresolved, not active.

        The stored column is non-null, so this only guards a malformed row. It
        exists because a single bad record must never fail serialisation for the
        whole page, and because an absent status must never read as verified.
        """
        return normalize_public_verification_status(value)

    @model_validator(mode="after")
    def _verified_follows_verification_status(self):
        """Derive the public ``verified`` boolean from the authoritative status.

        ``verification_status`` is the source of truth. Any value supplied for the
        legacy ``verified``/``is_verified`` boolean is ignored, so the
        backward-compatible field can never contradict the status beside it.
        """
        self.verified = public_verified_from_status(self.verification_status)
        return self


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

    @field_validator(*LIST_COLUMNS, "required_documents", mode="before")
    @classmethod
    def _normalise_legacy_list_shape(cls, value):
        """Accept the shape the JSON column has historically been allowed to hold.

        A bare string in one of these columns is a real, complete sentence that
        was filed in the wrong container. Returning it as a one-element list is
        the honest reading: the text is published exactly as stored, and the
        contract stops being the thing that fails an applicant with a 500.

        Anything that is not a list or a string is returned untouched so Pydantic
        reports the real type error. Coercing a number or an object into a list
        of strings would invent the sentence it never had.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value


class PaginationMetadata(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class ScholarshipListResponse(BaseModel):
    items: list[ScholarshipResponse]
    pagination: PaginationMetadata


class ScholarshipStatsResponse(BaseModel):
    """Live aggregate statistics served from the database."""

    total: int
    countries: int
    open: int
    closing_soon: int
    upcoming: int
    verified_active: int
    fully_funded: int
    with_image: int
    with_official_source: int


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
# redeploy trigger
