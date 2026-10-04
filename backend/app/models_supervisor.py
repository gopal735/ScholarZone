"""Supervisor discovery tables.

These live beside :mod:`app.models` rather than inside it, and import ``Base``
from it. Two reasons, both practical:

* ``app.models`` is the file every schema change contends over. Keeping a
  feature's tables in their own module means this feature's schema does not
  collide with unrelated model work, which matters because ``Base.metadata`` is
  what ``create_all`` reads and a name collision there breaks startup silently
  at the point of creation.
* Ownership is expressed by foreign key, not by redefinition. ``users`` and
  ``user_sessions`` belong to ``app/services/auth.py`` and
  ``app.dependencies.require_user``. There is exactly one identity in
  ScholarZone, and outreach keys to it.

Importing this module is what registers the tables with ``Base.metadata``. It is
imported for that side effect by :mod:`app.database` before ``create_all`` runs,
so the tables exist without any caller having to remember the order.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base

# ---------------------------------------------------------------------------
# Coverage
#
# The catalogue table is not extended. A scholarship with zero verified
# supervisors is a real, publishable state, and the coverage table exists so that
# "none found" stays distinguishable from "never looked" while still letting
# every scholarship carry an answer.
# ---------------------------------------------------------------------------


class ScholarshipSupervisorCoverage(Base):
    """Exactly one discovery state per scholarship.

    The unique constraint on ``scholarship_id`` is what makes the coverage
    invariant enforceable rather than aspirational: re-running discovery for a
    scholarship updates this row instead of adding a second one.
    """

    __tablename__ = "scholarship_supervisor_coverage"
    __table_args__ = (
        UniqueConstraint("scholarship_id", name="uq_supervisor_coverage_scholarship"),
        Index("ix_supervisor_coverage_status", "status"),
        Index("ix_supervisor_coverage_next_check_at", "next_check_at"),
        Index("ix_supervisor_coverage_scholarship_id", "scholarship_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False)
    #: One of SupervisorCoverageStatus. See app/services/supervisor_status.py.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="search_pending")
    #: Count of publicly publishable relationships, not of professors found.
    #: Zero is a legitimate value and must never be read as a failure.
    verified_supervisor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: One of CoverageEvidenceState. Records how far provenance was built, so a
    #: run that failed halfway is not reported as a completed negative.
    evidence_state: Mapped[str] = mapped_column(String(32), nullable=False, default="not_collected")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Set only when the last run could not finish. Never shown publicly; it
    #: exists so an operator can tell a blocked source from a negative result.
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProfessorProfile(Base):
    """One academic, stored once and shared across scholarships.

    The unique official profile URL is the deduplication key: the same person is
    published by one institution under one canonical page, and two runs that
    discover that page must converge on one row rather than two near-duplicates.

    ``official_email`` is populated only from an authoritative institutional page.
    The paired ``official_email_verified`` flag is what the public API reads, so
    an address that exists but is unconfirmed can never be presented as verified.
    """

    __tablename__ = "professor_profiles"
    __table_args__ = (
        UniqueConstraint("official_profile_url", name="uq_professor_official_profile_url"),
        Index("ix_professor_institution_name", "institution_name"),
        Index("ix_professor_institution_department", "institution_name", "department_name"),
        Index("ix_professor_canonical_name", "canonical_name"),
        Index("ix_professor_profile_status", "profile_status"),
        Index("ix_professor_next_verification_at", "next_verification_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: The authoritative page this record is derived from. Not merely a link: it
    #: is the identity key.
    official_profile_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    official_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    official_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lab_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    #: Only set when the institution itself publishes it. Personal pages are
    #: welcome but never authoritative on their own.
    personal_academic_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    #: Verified research areas as published by the official source. Bounded lists
    #: rather than free text, because alignment compares them.
    research_areas: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    research_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: One of ProfessorProfileStatus. Never hard-deleted; retirement keeps
    #: historical relationships and foreign keys resolvable.
    profile_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_verification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ScholarshipProfessorLink(Base):
    """A professor's evidenced relationship to one scholarship.

    The composite unique constraint is the duplicate guard the discovery worker
    needs to be safely re-runnable: the same relationship cannot be inserted
    twice, however many times the source is re-read.

    ``verification_status`` is independent of the scholarship's own verification
    state. A scholarship may be fully verified while one of its professor
    relationships is unverified, and both facts stay true at once.
    """

    __tablename__ = "scholarship_professor_links"
    __table_args__ = (
        UniqueConstraint(
            "scholarship_id",
            "professor_id",
            "relationship_type",
            name="uq_scholarship_professor_relationship",
        ),
        Index("ix_professor_links_scholarship_status", "scholarship_id", "verification_status"),
        Index("ix_professor_links_scholarship_id", "scholarship_id"),
        Index("ix_professor_links_professor_id", "professor_id"),
        Index("ix_professor_links_verification_status", "verification_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False)
    professor_id: Mapped[int] = mapped_column(Integer, ForeignKey("professor_profiles.id"), nullable=False)
    #: One of ProfessorRelationshipType. There is no plain SUPERVISOR value.
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False)
    #: Required, not nullable: a relationship without provenance may not exist.
    evidence_source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    #: One of SourceType. A secondary source may be stored here for operator
    #: context but cannot raise verification_status to VERIFIED.
    evidence_source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_quote_or_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: One of RelationshipVerificationStatus.
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unverified")
    #: An integer 0-100 describing source agreement only. Never a probability of
    #: admission, of acceptance, or of receiving a reply.
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SupervisorSourceEvidence(Base):
    """One authoritative page that was actually read, and what it said.

    Provenance is stored per source rather than only on the link, so the same
    page can be recorded once and its retrieval history kept for many
    relationships. The content hash lets a later run prove the page changed.
    """

    __tablename__ = "supervisor_source_evidence"
    __table_args__ = (
        UniqueConstraint(
            "professor_id", "source_url", "source_type", name="uq_supervisor_evidence_professor_source"
        ),
        Index("ix_supervisor_evidence_professor_id", "professor_id"),
        Index("ix_supervisor_evidence_scholarship_id", "scholarship_id"),
        Index("ix_supervisor_evidence_source_host", "source_host"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    professor_id: Mapped[int] = mapped_column(Integer, ForeignKey("professor_profiles.id"), nullable=False)
    #: Nullable: the programme page that led here may have no single professor.
    scholarship_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=True)
    link_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scholarship_professor_links.id"), nullable=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_host: Mapped[str] = mapped_column(String(255), nullable=False)
    #: One of SourceType. Only authoritative types may back a verified claim.
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unverified")
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Digest of the retrieved body, so "unchanged since" is provable.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ProfessorAvailability(Base):
    """One availability answer for one question, with its source.

    Availability is per-scope because a page that answers "I supervise master's
    students" says nothing about PhD places or funding. ``source_url`` and
    ``verified_at`` are both required: an availability claim without a source and
    a date is not a claim ScholarZone will publish.
    """

    __tablename__ = "professor_availability"
    __table_args__ = (
        UniqueConstraint("professor_id", "scope", name="uq_professor_availability_scope"),
        Index("ix_professor_availability_professor_id", "professor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    professor_id: Mapped[int] = mapped_column(Integer, ForeignKey("professor_profiles.id"), nullable=False)
    #: One of AvailabilityScope.
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    #: One of AvailabilityState. ``unknown`` is the honest default and is what a
    #: page that never mentions the question produces.
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ContactTemplate(Base):
    """A reusable, editable outreach template.

    Stored as plain text, not HTML, and never containing a claim about the
    recipient. A template states what the student wants to ask; it does not
    assert that a place, a position or funding exists.
    """

    __tablename__ = "contact_templates"
    __table_args__ = (Index("ix_contact_templates_active", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    degree_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subject_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProfessorOutreachRecord(Base):
    """A student's private record of contacting one professor about one scholarship.

    Entirely private. No column here is ever exposed through a public route, and
    ``user_id`` is resolved by ``app.dependencies.require_user`` from the session
    rather than read from a request body, so a client cannot address another
    student's record.

    The composite unique constraint keeps one row per user/scholarship/professor
    triple, so a double-submitted form updates the existing record rather than
    creating a second one that would fragment the history.

    ``version`` backs optimistic concurrency: a stale write is refused with 409
    instead of silently overwriting a note typed moments earlier.
    """

    __tablename__ = "professor_outreach_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scholarship_id", "professor_id", name="uq_outreach_user_scholarship_professor"
        ),
        Index("ix_outreach_user_status", "user_id", "status"),
        Index("ix_outreach_user_follow_up", "user_id", "follow_up_due_at"),
        Index("ix_outreach_professor_id", "professor_id"),
        Index("ix_outreach_scholarship_id", "scholarship_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: The canonical ScholarZone identity. Not a new user table.
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False)
    professor_id: Mapped[int] = mapped_column(Integer, ForeignKey("professor_profiles.id"), nullable=False)
    #: Optional correlation to Dashboard 1.0's application record. Ownership is
    #: always ``user_id``; this column never grants access, so deleting an
    #: application cannot orphan an outreach record into someone else's hands.
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: One of OutreachStatus. Advanced only through the legal transition map.
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_contacted")
    #: The student's own draft. Stored so it can be resumed, and never sent by
    #: the server: there is no send path in this codebase at all.
    draft_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    follow_up_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Bounded plain text. Validated to contain no markup: it is rendered as
    #: text, and an HTML note would be a stored-XSS surface for no benefit.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("contact_templates.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


__all__ = [
    "ContactTemplate",
    "ProfessorAvailability",
    "ProfessorOutreachRecord",
    "ProfessorProfile",
    "ScholarshipProfessorLink",
    "ScholarshipSupervisorCoverage",
    "SupervisorSourceEvidence",
]