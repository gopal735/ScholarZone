"""Persistent verification history layer.

Provides low-latency, append-only persistence of field-level verification changes.

Design principles:
- O(n) relative to changed fields (single bulk INSERT per verification event)
- No N+1 queries (accepts scholarship_id, no repeated Scholarship loads)
- No network operations, no parsing, no AI work
- Transaction-friendly: caller controls commit/rollback
- Append-only: history rows are immutable
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import ScholarshipVerificationHistory


@dataclass
class HistoryEntry:
    """A single field change to persist in verification history."""

    field_name: str
    old_value: Any = None
    new_value: Any = None
    change_type: str = "modified"
    source_url: str | None = None
    evidence_text: str | None = None
    confidence: str | None = None
    verification_status: str = "active"


@dataclass
class HistoryWriteResult:
    """Result of a history write operation."""

    entries_written: int = 0
    scholarship_id: int = 0
    history_ids: list[int] = field(default_factory=list)
    error: str | None = None


def _serialize_value(value: Any) -> str | None:
    """Serialize a value to a deterministic, immutable string representation.

    Ensures historical records remain understandable even if the current
    scholarship record changes later.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, bool):
        return "true" if value else "false"

    return str(value)


def write_verification_history(
    session: Session,
    scholarship_id: int,
    entries: list[HistoryEntry],
    source_url: str | None = None,
    verification_status: str = "active",
) -> HistoryWriteResult:
    """Persist field-level verification changes to history.

    This function is designed to be called within a larger transaction.
    It does NOT commit or rollback - the caller controls transaction boundaries.

    Args:
        session: SQLAlchemy session (caller-managed)
        scholarship_id: ID of the scholarship being verified
        entries: List of field changes to persist
        source_url: Optional override for source URL (used if entry has none)
        verification_status: Optional override for verification status

    Returns:
        HistoryWriteResult with count and IDs of inserted rows

    Raises:
        ValueError: If scholarship_id does not exist
        Does NOT raise database errors. Caller must handle SQLAlchemy exceptions
        and rollback the transaction if needed.
    """
    from sqlalchemy import exists, select

    from ..models import Scholarship

    result = HistoryWriteResult(scholarship_id=scholarship_id)

    if not entries:
        return result

    # Validate scholarship exists (lightweight EXISTS query)
    scholarship_exists = session.scalar(
        select(exists().where(Scholarship.id == scholarship_id))
    )
    if not scholarship_exists:
        raise ValueError(f"scholarship_id {scholarship_id} does not exist")

    now = datetime.now(timezone.utc)
    history_records: list[ScholarshipVerificationHistory] = []

    for entry in entries:
        record = ScholarshipVerificationHistory(
            scholarship_id=scholarship_id,
            field_name=entry.field_name,
            old_value=_serialize_value(entry.old_value),
            new_value=_serialize_value(entry.new_value),
            change_type=entry.change_type,
            source_url=entry.source_url or source_url,
            evidence_text=entry.evidence_text,
            confidence=entry.confidence,
            verification_status=entry.verification_status or verification_status,
            created_at=now,
        )
        history_records.append(record)

    session.add_all(history_records)
    session.flush()

    for record in history_records:
        result.history_ids.append(record.id)
        result.entries_written += 1

    return result


def write_changeset_history(
    session: Session,
    scholarship_id: int,
    changeset: Any,
    source_url: str | None = None,
    evidence_collection: Any = None,
    confidence_assessment: Any = None,
    verification_status: str = "active",
) -> HistoryWriteResult:
    """Persist a ChangeSet to verification history.

    Convenience wrapper that converts a ChangeSet into HistoryEntry objects
    and writes them in a single batch.

    Args:
        session: SQLAlchemy session (caller-managed)
        scholarship_id: ID of the scholarship
        changeset: ChangeSet from the verification pipeline
        source_url: Source URL for the verification
        evidence_collection: EvidenceCollection for evidence text lookup
        confidence_assessment: VerificationAssessment for confidence lookup
        verification_status: Overall verification status

    Returns:
        HistoryWriteResult with count and IDs of inserted rows
    """
    from .scholarship_diff import FieldChangeType

    entries: list[HistoryEntry] = []

    if changeset is None or not hasattr(changeset, 'changes'):
        return HistoryWriteResult(scholarship_id=scholarship_id)

    for change in changeset.changes:
        if change.change_type == FieldChangeType.UNCHANGED:
            continue

        evidence_text = None
        confidence = None

        if evidence_collection is not None:
            evidence_item = evidence_collection.get_evidence_for_field(change.field)
            if evidence_item is not None:
                evidence_text = evidence_item.evidence_text

        if confidence_assessment is not None:
            field_result = confidence_assessment.get_field_result(change.field)
            if field_result is not None:
                confidence = field_result.confidence

        entry = HistoryEntry(
            field_name=change.field,
            old_value=change.old_value,
            new_value=change.new_value,
            change_type=change.change_type,
            source_url=source_url,
            evidence_text=evidence_text,
            confidence=confidence,
            verification_status=verification_status,
        )
        entries.append(entry)

    return write_verification_history(
        session=session,
        scholarship_id=scholarship_id,
        entries=entries,
        source_url=source_url,
        verification_status=verification_status,
    )


def get_verification_history(
    session: Session,
    scholarship_id: int,
    field_name: str | None = None,
    limit: int = 100,
) -> list[ScholarshipVerificationHistory]:
    """Retrieve verification history for a scholarship.

    Uses indexed lookups for efficient querying.

    Args:
        session: SQLAlchemy session
        scholarship_id: ID of the scholarship
        field_name: Optional field name filter
        limit: Maximum number of rows to return

    Returns:
        List of ScholarshipVerificationHistory rows, ordered by created_at DESC
    """
    from sqlalchemy import select

    stmt = (
        select(ScholarshipVerificationHistory)
        .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
        .order_by(ScholarshipVerificationHistory.created_at.desc())
        .limit(limit)
    )

    if field_name is not None:
        stmt = stmt.where(ScholarshipVerificationHistory.field_name == field_name)

    return list(session.execute(stmt).scalars().all())


def write_verification_history_with_snapshot(
    session: Session,
    scholarship_id: int,
    entries: list[HistoryEntry],
    scholarship: Any = None,
    source_url: str | None = None,
    verification_status: str = "active",
    cycle_id: str | None = None,
) -> HistoryWriteResult:
    """Persist verification history and create a temporal snapshot.

    This wraps write_verification_history and additionally creates a
    ScholarshipSnapshot when meaningful changes are detected and a
    scholarship object is provided.

    Args:
        session: SQLAlchemy session (caller-managed)
        scholarship_id: ID of the scholarship being verified
        entries: List of field changes to persist
        scholarship: Optional Scholarship object for snapshot creation
        source_url: Optional override for source URL
        verification_status: Optional override for verification status
        cycle_id: Optional application cycle identifier

    Returns:
        HistoryWriteResult with count and IDs of inserted rows
    """
    from .temporal_versioning import create_snapshot

    result = write_verification_history(
        session=session,
        scholarship_id=scholarship_id,
        entries=entries,
        source_url=source_url,
        verification_status=verification_status,
    )

    if scholarship is not None and entries:
        changed_fields = [e.field_name for e in entries]
        create_snapshot(
            session=session,
            scholarship=scholarship,
            changed_fields=changed_fields,
            source_url=source_url,
            cycle_id=cycle_id,
        )

    return result
