"""Persistent scholarship data model."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Scholarship(Base):
    __tablename__ = "scholarships"
    __table_args__ = (
        Index("ix_scholarships_country_degree", "country", "degree"),
        Index("ix_scholarships_status_deadline", "status", "deadline_date"),
        UniqueConstraint("official_source_url", name="uq_scholarships_official_source_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    degree: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    funding: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    deadline_display: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_precision: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    # Archiving is separate from status on purpose.
    #
    # ``status`` answers "is this round open right now", so it flips back to open
    # when a new cycle is published. ``is_archived`` answers "should this record
    # be offered to a visitor at all", and it is one-way. A scholarship whose
    # deadline passed is still a true record - it just is not an opportunity, and
    # showing it among live listings sends applicants to a form that no longer
    # accepts anything. Archiving keeps the row, its history and its inbound
    # links while removing it from every public read path.
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Automatic garbage collection of closed records. `archived_at` is the
    # retention clock - it is written when the record is folded away and cleared
    # when it is reopened, so it measures the closed-and-untouched period.
    # `updated_at` cannot: it moves on every unrelated edit.
    #
    # `auto_delete_candidate_since` is the grace-period clock. A record must hold
    # every SAFE_DELETE condition continuously for DELETE_GRACE_DAYS before a
    # delete may execute, and "continuously" cannot be derived from anything
    # already on the row: if a record is reopened and re-closed between two
    # cycles, only persisted state notices. It is set when the full predicate
    # first passes and cleared the moment any condition stops passing.
    auto_delete_candidate_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # An operator override. Checked before every other condition, so protecting a
    # record never depends on the rest of the policy staying correct.
    deletion_protected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_verified_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    next_verification_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_period: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    official_source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    catalogue_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    official_updates_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    application_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    image_source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    image_source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    image_alt_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Terminal image-evaluation outcome. ``image_verified_at`` alone cannot
    # distinguish "we looked and nothing trustworthy exists" from "we never
    # looked", so an evaluated record with no image would otherwise be
    # indistinguishable from an unprocessed one. Every valid record must reach
    # exactly one terminal state; see ImageEvaluationStatus.
    image_evaluation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eligibility: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    eligibility_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    benefits: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    coverage: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    requirements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    documents: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    english_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_method: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    selection_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    program_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    best_fit: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Award economics, separated.
    #
    # ``funding`` is a 120-character label and cannot distinguish "CAD 40,000 a
    # year" from "covers tuition and living costs". Those are different facts
    # and an applicant acting on the first when only the second was true makes a
    # serious financial mistake, so the amount, its currency, its period and
    # what it actually covers are stored apart from the label.
    #
    # ``fully_funded`` is deliberately conservative: it is true only when an
    # official source states that tuition, living costs and required expenses are
    # covered. A fixed stipend is not full funding, and the default is therefore
    # false rather than unknown, because unknown reads as "probably yes".
    # ------------------------------------------------------------------
    funding_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    funding_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    funding_period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tuition_coverage: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    living_cost_coverage: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    travel_coverage: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fully_funded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ------------------------------------------------------------------
    # Structured programme detail, kept apart from the scalar columns above.
    #
    # A scholarship's official rules do not fit a fixed set of columns: which
    # deadline belongs to the university rather than the programme, how a
    # referee is tracked, what an applicant should check before submitting. That
    # varies per programme, so it lives in JSON rather than in a migration for
    # every new attribute.
    #
    # The three are separated on purpose and the split is load-bearing:
    #   official_details    - what the awarding body published
    #   applicant_utility   - guidance derived from those rules, written by us
    #   programme_verification - what we checked, and what we could not confirm
    # Presenting derived guidance as published policy is how a catalogue starts
    # telling applicants things the awarding body never said.
    # ------------------------------------------------------------------
    official_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applicant_utility: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    programme_verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    @property
    def deadline(self) -> str | None:
        """Keep the response compatible with the frontend's display value."""
        return self.deadline_display


class ScholarshipVerificationHistory(Base):
    __tablename__ = "scholarship_verification_history"
    __table_args__ = (
        Index("ix_verification_history_scholarship_created", "scholarship_id", "created_at"),
        Index("ix_verification_history_scholarship_field_created", "scholarship_id", "field_name", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ScholarshipReview(Base):
    __tablename__ = "scholarship_reviews"
    __table_args__ = (
        Index("ix_reviews_scholarship_decision", "scholarship_id", "decision"),
        Index("ix_reviews_scholarship_field_decision", "scholarship_id", "field_name", "decision"),
        UniqueConstraint("scholarship_id", "field_name", "decision", name="uq_reviews_scholarship_field_decision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    current_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    verification_state: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScholarshipFetchAttempt(Base):
    __tablename__ = "scholarship_fetch_attempts"
    __table_args__ = (
        Index("ix_fetch_attempts_scholarship_status", "scholarship_id", "status"),
        Index("ix_fetch_attempts_source_status", "source_url", "status"),
        Index("ix_fetch_attempts_next_retry", "next_retry_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_error_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovedSource(Base):
    __tablename__ = "approved_sources"
    __table_args__ = (
        Index("ix_approved_sources_domain", "domain"),
        UniqueConstraint("domain", name="uq_approved_sources_domain"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="official_government")
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    discovery_url_patterns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceHealth(Base):
    __tablename__ = "source_health"
    __table_args__ = (
        Index("ix_source_health_domain", "domain"),
        Index("ix_source_health_status", "health_status"),
        UniqueConstraint("domain", name="uq_source_health_domain"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_limit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminal_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reliability_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    health_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    manual_override: Mapped[str | None] = mapped_column(String(16), nullable=True)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def total_count(self) -> int:
        return self.success_count + self.failure_count


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (
        Index("ix_knowledge_nodes_entity_type", "entity_type"),
        Index("ix_knowledge_nodes_normalized_value", "normalized_value"),
        UniqueConstraint("entity_type", "normalized_value", name="uq_knowledge_nodes_type_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"
    __table_args__ = (
        Index("ix_knowledge_edges_source", "source_node_id"),
        Index("ix_knowledge_edges_target", "target_node_id"),
        Index("ix_knowledge_edges_relation", "relation_type"),
        Index("ix_knowledge_edges_status", "status"),
        UniqueConstraint("source_node_id", "target_node_id", "relation_type", name="uq_knowledge_edges_source_target_relation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False)
    target_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="verified")
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ScholarshipSnapshot(Base):
    __tablename__ = "scholarship_snapshots"
    __table_args__ = (
        Index("ix_snapshots_scholarship_valid", "scholarship_id", "valid_from", "valid_to"),
        Index("ix_snapshots_scholarship_current", "scholarship_id", "is_current"),
        Index("ix_snapshots_cycle", "scholarship_id", "cycle_id"),
        UniqueConstraint("scholarship_id", "version_id", name="uq_snapshots_scholarship_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cycle_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DiscoveryCandidate(Base):
    __tablename__ = "discovery_candidates"
    __table_args__ = (
        Index("ix_discovery_candidates_status", "status"),
        Index("ix_discovery_candidates_normalized_url", "normalized_url"),
        Index("ix_discovery_candidates_match_status", "match_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    funding: Mapped[str | None] = mapped_column(String(120), nullable=True)
    official_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    official_source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    match_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unmatched")
    matched_scholarship_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=True)
    extracted_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    discovery_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    discovery_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImageReview(Base):
    __tablename__ = "image_reviews"
    __table_args__ = (
        Index("ix_image_reviews_scholarship_decision", "scholarship_id", "decision"),
        Index("ix_image_reviews_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    image_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_page: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    relevance_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    licensing_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    licensing_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_for_review: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ScholarshipRestoreRecord(Base):
    __tablename__ = "scholarship_restore_records"
    __table_args__ = (
        Index("ix_restore_records_scholarship", "scholarship_id"),
        Index("ix_restore_records_scholarship_outcome", "scholarship_id", "outcome"),
        Index("ix_restore_records_operation_id", "operation_id"),
        UniqueConstraint("operation_id", name="uq_restore_records_operation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    scholarship_id: Mapped[int] = mapped_column(Integer, ForeignKey("scholarships.id"), nullable=False, index=True)
    source_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    restored_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MaintenanceCursor(Base):
    """Durable per-stream progress marker for autonomous maintenance.

    The scheduled enrichment stage used to select ``ORDER BY id LIMIT n`` with
    no cursor at all, so every twelve-hour run re-processed the same first
    records and the tail of the catalogue was never reached. A cursor is the
    smallest thing that fixes that: it is one row, it lives in the same
    database as the work, and it survives a failed run, a runner swap, a
    cancelled workflow and a manual dispatch identically.

    It is deliberately *not* stored in the Actions cache: a cache is scoped to
    a branch and can be evicted without warning, so a cache-based cursor can
    silently rewind and re-do work.

    ``last_id`` advances monotonically and wraps to zero once the catalogue is
    exhausted, which turns repeated runs into a round-robin sweep. Every record
    is therefore revisited on a fixed, bounded cadence instead of never, and a
    record is never visited twice inside a single cycle.
    """

    __tablename__ = "maintenance_cursors"
    __table_args__ = (
        Index("ix_maintenance_cursors_updated", "updated_at"),
    )

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cycles_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_visited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cycle_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MaintenanceRun(Base):
    """One row per maintenance run, for free operational visibility.

    The worker prints a summary to stdout, which GitHub keeps for weeks, but a
    database that cannot answer "when did enrichment last advance?" or "is the
    nightly run still succeeding?" is not observable on its own. This is the
    smallest table that makes the autonomous system debuggable after the fact
    without a paid monitoring service.

    Only counts, stage names, statuses and error text are stored. No secret is
    ever passed to this table.
    """

    __tablename__ = "maintenance_runs"
    __table_args__ = (
        Index("ix_maintenance_runs_started", "started_at"),
        Index("ix_maintenance_runs_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    worker: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    stages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class ContentFingerprintRecord(Base):
    __tablename__ = "content_fingerprints"
    __table_args__ = (
        Index("ix_fingerprints_source_url", "source_url"),
        Index("ix_fingerprints_source_hash", "source_url", "normalized_content_hash"),
        Index("ix_fingerprints_generated", "source_url", "generated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    normalized_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    algorithm_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


