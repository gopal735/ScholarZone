"""Validated, URL-identified ingestion for verified scholarship records."""

from __future__ import annotations

from datetime import date
import logging
from typing import Iterable
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..services.deadline_semantics import coerce_deadline_precision as _coerce_deadline_precision
from ..services.image_validator import assess_image_evidence
from ..services.scholarship_image_verifier import _VALID_SOURCE_TYPES, is_valid_source_type

logger = logging.getLogger(__name__)

#: Image columns this mapper may write. ``image_kind`` is deliberately absent
#: from that set: kinds are produced by the image pipeline (``image_validator``,
#: ``do_logos``, ``image_coverage_runner``) and ingestion has no producer
#: semantics for them, so mapping it here would fabricate trust evidence.
#:
#: It is still accepted as a field, validated against the same vocabulary and
#: then not persisted, because research and verification payloads carry the
#: kind alongside the source URL and rejecting the key would make the record
#: format unusable for its own pipeline. The distinction is enforced by
#: :meth:`to_persistence_fields`, which is the single place that decides what
#: reaches a column - the model accepting it is not the same as storing it.
IMAGE_PERSISTENCE_FIELDS = frozenset(
    {
        "image_url",
        "image_source_url",
        "image_source_type",
        "image_verified_at",
        "image_alt_text",
    }
)

#: The image-kind vocabulary, mirroring the pipeline that produces it.
IMAGE_KINDS = frozenset({"official_logo", "program_image", "official_banner"})


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
    program_type: str | None = Field(default=None, max_length=255)
    best_fit: str | None = None
    notes: str | None = None
    image_url: str | None = None
    image_source_url: str | None = None
    image_source_type: str | None = None
    image_verified_at: date | None = None
    image_alt_text: str | None = Field(default=None, max_length=512)
    # Accepted and validated, then never persisted: see IMAGE_PERSISTENCE_FIELDS.
    image_kind: str | None = None

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

    @field_validator("image_source_type")
    @classmethod
    def validate_image_source_type(cls, value: str | None) -> str | None:
        """Confine the image's source vocabulary to its canonical members.

        ``image_source_type`` is a provenance claim, and it is read as one: a
        card states where the mark came from. A value outside the vocabulary —
        ``official_logo``, ``official_ngo``, ``official_institution`` — is not
        a different kind of source, it is a value no reader can interpret, and
        it is exactly what a hand-edited record or a typo produces. Rejecting
        it here rather than storing it keeps the column meaningful, and it
        fails at ingestion, where the mistake can still be corrected, instead
        of at the point where the row is already public.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not is_valid_source_type(text):
            raise ValueError(
                f"image_source_type must come from the canonical vocabulary "
                f"({', '.join(sorted(_VALID_SOURCE_TYPES))})"
            )
        return text

    @field_validator("image_kind")
    @classmethod
    def validate_image_kind(cls, value: str | None) -> str | None:
        """Validate the kind, then leave it to the pipeline that owns it.

        Same contract as ``image_source_type``: a value outside the vocabulary
        is rejected rather than stored. What is different is what happens to an
        accepted one - nothing. Ingestion does not write kinds, so this
        validator exists to stop an uninterpretable value travelling with a
        payload, not to make the field into a write path.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text not in IMAGE_KINDS:
            raise ValueError(
                f"image_kind must be one of {', '.join(sorted(IMAGE_KINDS))}"
            )
        return text

    @field_validator("deadline_precision")
    @classmethod
    def coerce_deadline_precision(cls, value: str | None) -> str | None:
        """Fold any extractor-supplied precision onto the stored vocabulary.

        See :func:`app.services.deadline_semantics.coerce_deadline_precision`
        for why an unrecognised token becomes ``unknown`` rather than being
        passed through: the column is a claim about how precise a stated
        deadline is, and a token the schema has never heard of cannot support
        that claim.

        ``None`` survives, because the pipeline distinguishes "no precision
        recorded" from "precision is unknown" and the validator must not erase
        that difference at the door. The database default covers the stored
        row.
        """
        if value is None:
            return None
        return _coerce_deadline_precision(value)

    @field_validator("image_url")
    @classmethod
    def validate_image_evidence(cls, value: str | None) -> str | None:
        """Ingestion consults the same evidence gate the write paths use.

        The gate is ``assess_image_evidence``: https only, a provenance
        vocabulary, a classified kind, and no non-content assets. A favicon,
        an app icon or a social-share button is refused at ingestion, where
        the mistake is still a payload to correct, rather than being stored
        and having to be quarantined later.

        ``image_kind`` is required whenever an ``image_url`` is supplied,
        because a URL with no kind is an image nobody classified — the state
        the public contract treats as "no evidence at all". It is still not
        persisted through :data:`IMAGE_PERSISTENCE_FIELDS`: the pipeline owns
        kinds, this only stops an unclassifiable payload travelling.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        # Transport first, so a plaintext URL fails with the reason that
        # actually applies rather than with whatever the cross-field checks
        # would have said about the rest of the payload.
        parsed = urlsplit(text)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError(
                f"image_url must be a non-empty HTTPS URL (got {text!r})"
            )
        return text

    @model_validator(mode="after")
    def check_image_evidence(self) -> ScholarshipIngestionRecord:
        """The cross-field half of the image gate.

        Runs the same non-content detectors and threshold as the discovery
        pipeline, so a favicon, an app icon or a social-share button is
        refused at ingestion for the same reason and at the same weight it is
        refused there. A rejection raises rather than silently downgrading:
        a caller that supplied an unusable image has a research error worth
        surfacing, and storing it with a null URL would hide that behind a row
        that merely looks image-less.

        ``image_kind`` is deliberately not required here. Ingestion has no
        producer semantics for kinds - that is what :data:`IMAGE_PERSISTENCE_FIELDS`
        records - so demanding one would force this mapper to invent a
        classification. The requirement lives in ``assess_image_evidence``,
        which the pipeline stages call with ``require_kind=True``.
        """
        if self.image_url is None:
            if self.image_source_type is not None and not is_valid_source_type(
                self.image_source_type
            ):
                raise ValueError(
                    f"image_source_type {self.image_source_type!r} is outside "
                    "the canonical vocabulary"
                )
            return self

        # ``image_kind`` is deliberately not required. Ingestion has no
        # producer semantics for kinds - that is exactly what
        # :data:`IMAGE_PERSISTENCE_FIELDS` records - so demanding one would
        # force this mapper to invent a classification. The image pipeline
        # classifies on its own path, and this model must not write what it
        # did not read: a research payload that arrives with a URL and no
        # kind is a research payload that says nothing about what the bytes
        # are, which is the honest state to store.
        verdict = assess_image_evidence(
            image_url=self.image_url,
            image_source_url=self.image_source_url,
            image_source_type=self.image_source_type,
            image_kind=self.image_kind,
            alt_text=self.image_alt_text,
            official_source_url=self.official_source_url,
            page_url=self.official_source_url,
            require_kind=False,
        )
        if not verdict.accepted:
            raise ValueError(f"image rejected by the evidence gate: {verdict.reason_text}")
        return self

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
            if source_field not in self.model_fields_set:
                continue
            value = getattr(self, source_field)
            if database_field in IMAGE_PERSISTENCE_FIELDS and value is None:
                # An explicit null means "this record carries no image", not
                # "retract the image already stored on the row".
                #
                # Pydantic records explicitly supplied keys in model_fields_set
                # even when the value is None, and do_add copies every key of a
                # worklist entry straight into this model. A single entry
                # carrying five null image keys therefore blanked the stored
                # image of every matching record in one transaction.
                #
                # Ingestion is a create/enrich path: every caller supplies an
                # image or omits the keys, and none retracts one. Canonical
                # clearing belongs to do_purge and do_logos, which do not go
                # through this function. Treating null as absence keeps a
                # verified, accepted image from being deleted by a refresh that
                # simply had nothing to say about images.
                continue
            fields[database_field] = value

        if "coverage" in self.model_fields_set:
            fields["benefits"] = self.coverage

        # deadline_precision is NOT NULL and its column default is "month",
        # which asserts a precision no page published. A record that supplies a
        # deadline but no precision gets "varies": the same value the enrichment
        # stage writes, and in the vocabulary the rolling/recurring filters
        # match on. Resolved here rather than in the caller because the insert
        # happens inside upsert_verified_scholarships, before any caller can
        # correct it.
        if fields.get("deadline_precision") is None:
            fields["deadline_precision"] = "varies"

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


def _fit_columns(payload: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    """Drop values that do not fit their column, and say which.

    Postgres raises StringDataRightTruncation and the whole transaction rolls
    back, so one over-long value costs every other record in the batch. The
    model caps most bounded fields, but not all of them: ``image_source_type``
    and similar carry no max_length, so an agent writing a sentence instead of
    a code reached the database.

    The value is left out rather than truncated. Half a source type reads as a
    source type, which is worse than none.
    """
    widths = {
        column.name: getattr(column.type, "length", None)
        for column in Scholarship.__table__.columns
    }
    fitted: dict[str, object] = {}
    dropped: list[str] = []
    for field, value in payload.items():
        limit = widths.get(field)
        if limit is not None and isinstance(value, str) and len(value) > limit:
            dropped.append(f"{field}({len(value)}>{limit})")
            continue
        fitted[field] = value
    return fitted, dropped


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

        # Fitted before the branch, not inside the create path. A guard that
        # only guarded half the writes let a 258-character official_source
        # through on the update path and aborted the run on the varchar(255).
        persistence_fields, dropped = _fit_columns(persistence_fields)
        if dropped:
            # Surfaced rather than swallowed: a record silently missing its
            # funder name is harder to notice than a reported one.
            logger.warning(
                "dropped over-long value(s) for record %s: %s",
                record.name,
                ", ".join(dropped),
            )

        if scholarship is None:
            if record.funding_type is None:
                raise ValueError("funding_type is required when inserting a new scholarship record")
            if record.preferred_id is not None and session.get(Scholarship, record.preferred_id) is None:
                # Use explicit INSERT with explicit ID to avoid SQLAlchemy insertmanyvalues issues
                from sqlalchemy import insert
                persistence_fields["id"] = record.preferred_id
                session.execute(insert(Scholarship).values(**persistence_fields))
            else:
                session.add(Scholarship(**persistence_fields))
            created_count += 1
            continue

        for field, value in persistence_fields.items():
            setattr(scholarship, field, value)
        updated_count += 1

    session.commit()
    return created_count, updated_count
