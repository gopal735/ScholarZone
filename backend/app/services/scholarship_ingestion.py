"""Validated, URL-identified ingestion for verified scholarship records."""

from __future__ import annotations

from datetime import date
from typing import Iterable
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Scholarship


class ScholarshipIngestionRecord(BaseModel):
    """The canonical data format for a verified scholarship catalogue entry."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=1, max_length=120)
    degree_levels: str = Field(min_length=1, max_length=255)
    funding_type: str | None = Field(default=None, min_length=1, max_length=120)
    official_source_url: str
    is_verified: bool = True
    last_verified_date: date | None = None

    region: str | None = None
    duration: str | None = None
    deadline: str | None = None
    deadline_date: date | None = None
    deadline_precision: str | None = None
    application_period: str | None = None
    eligibility_summary: str | None = None
    eligibility: list[str] | None = None
    coverage: list[str] | None = None
    required_documents: list[str] | None = None
    catalogue_url: str | None = None
    official_updates_url: str | None = None
    official_source: str | None = None
    english_requirement: str | None = None
    requirements: list[str] | None = None
    application_method: list[str] | None = None
    selection_notes: str | None = None
    program_type: str | None = None
    best_fit: str | None = None
    notes: str | None = None
    image_url: str | None = None
    image_source_url: str | None = None
    image_source_type: str | None = None
    image_verified_at: date | None = None
    image_alt_text: str | None = None

    # Migration-only metadata: never stored as scholarship content.
    legacy_titles: tuple[str, ...] = ()
    preferred_id: int | None = Field(default=None, ge=1)

    @field_validator("official_source_url")
    @classmethod
    def validate_official_source_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if not normalized or parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("official_source_url must be a non-empty HTTPS URL")
        return normalized

    @field_validator("catalogue_url", "official_updates_url")
    @classmethod
    def validate_optional_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if not normalized or parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("optional source URLs must be non-empty HTTPS URLs when supplied")
        return normalized

    def to_persistence_fields(self, verified_on: date) -> dict[str, object]:
        """Map canonical ingestion keys to the established database/API contract."""
        fields: dict[str, object] = {
            "title": self.name,
            "country": self.country,
            "degree": self.degree_levels,
            "official_source_url": self.official_source_url,
            "application_link": self.official_source_url,
            "is_verified": self.is_verified,
            "last_verified_date": verified_on,
            "last_verified_at": verified_on,
        }
        if self.funding_type is not None:
            fields["funding"] = self.funding_type
        mappings = {
            "region": "region",
            "duration": "duration",
            "deadline": "deadline_display",
            "deadline_date": "deadline_date",
            "deadline_precision": "deadline_precision",
            "application_period": "application_period",
            "eligibility_summary": "eligibility_summary",
            "eligibility": "eligibility",
            "coverage": "coverage",
            "required_documents": "documents",
            "catalogue_url": "catalogue_url",
            "official_updates_url": "official_updates_url",
            "official_source": "official_source",
            "english_requirement": "english_requirement",
            "requirements": "requirements",
            "application_method": "application_method",
            "selection_notes": "selection_notes",
            "program_type": "program_type",
            "best_fit": "best_fit",
            "notes": "notes",
            "image_url": "image_url",
            "image_source_url": "image_source_url",
            "image_source_type": "image_source_type",
            "image_verified_at": "image_verified_at",
            "image_alt_text": "image_alt_text",
        }
        for source_field, database_field in mappings.items():
            if source_field in self.model_fields_set:
                fields[database_field] = getattr(self, source_field)

        if "coverage" in self.model_fields_set:
            fields["benefits"] = self.coverage
        return fields


def validate_catalogue(records: Iterable[ScholarshipIngestionRecord]) -> tuple[ScholarshipIngestionRecord, ...]:
    """Reject duplicate official source URLs before any database writes occur."""
    normalized_records = tuple(records)
    seen_urls: set[str] = set()
    for record in normalized_records:
        if record.official_source_url in seen_urls:
            raise ValueError(f"Duplicate official_source_url in verified catalogue: {record.official_source_url}")
        seen_urls.add(record.official_source_url)
    return normalized_records


def _find_existing_scholarship(session: Session, record: ScholarshipIngestionRecord) -> Scholarship | None:
    """Find strictly by URL, with a migration fallback for pre-URL legacy titles."""
    source_url_variants = (record.official_source_url, f"{record.official_source_url}/")
    source_url_candidates = session.scalars(
        select(Scholarship).where(Scholarship.official_source_url.in_(source_url_variants))
    ).all()
    if len(source_url_candidates) > 1:
        raise RuntimeError(
            f"Multiple records use official source URL {record.official_source_url!r}; resolve them before seeding."
        )
    if source_url_candidates:
        return source_url_candidates[0]

    legacy_url_candidates = session.scalars(
        select(Scholarship).where(Scholarship.application_link.in_(source_url_variants))
    ).all()
    if len(legacy_url_candidates) > 1:
        raise RuntimeError(
            f"Multiple records use application URL {record.official_source_url!r}; resolve them before seeding."
        )
    if legacy_url_candidates:
        return legacy_url_candidates[0]

    if not record.legacy_titles:
        return None

    legacy_candidates = session.scalars(
        select(Scholarship).where(func.lower(Scholarship.title).in_(record.legacy_titles))
    ).all()
    if len(legacy_candidates) > 1:
        raise RuntimeError(
            f"Multiple legacy rows match {record.official_source_url!r}; resolve them before seeding."
        )
    return legacy_candidates[0] if legacy_candidates else None


def upsert_verified_scholarships(
    session: Session,
    records: Iterable[ScholarshipIngestionRecord],
) -> tuple[int, int]:
    """Insert or update official records while preserving existing IDs and relations."""
    catalogue = validate_catalogue(records)
    created_count = 0
    updated_count = 0
    verified_on = date.today()

    for record in catalogue:
        scholarship = _find_existing_scholarship(session, record)
        persistence_fields = record.to_persistence_fields(verified_on)

        if scholarship is None:
            if record.funding_type is None:
                raise ValueError("funding_type is required when inserting a new scholarship record")
            if record.preferred_id is not None and session.get(Scholarship, record.preferred_id) is None:
                persistence_fields["id"] = record.preferred_id
            session.add(Scholarship(**persistence_fields))
            created_count += 1
            continue

        for field, value in persistence_fields.items():
            setattr(scholarship, field, value)
        updated_count += 1

    session.commit()
    return created_count, updated_count
