"""Persistent scholarship data model."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
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
    deadline_display: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deadline_precision: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_verified_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    next_verification_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_period: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    official_source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    catalogue_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    official_updates_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    application_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
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


