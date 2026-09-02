"""Disaster recovery and snapshot restore workflow.

Provides safe, atomic, auditable, idempotent snapshot restore/recovery.

Design principles:
- Reuse existing temporal_versioning, scholarship_updater, scholarship_history,
  counterfactual_safety components. Do not redesign them.
- Restore ONLY from valid historical ScholarshipSnapshot.
- Never directly mutate Scholarship fields during restore.
- Apply changes through apply_verified_updates().
- Run counterfactual safety BEFORE commit.
- BLOCK restore on CRITICAL safety result.
- Reject restores that would reintroduce a REJECTED review change.
- Create restore audit history.
- Create a new current snapshot; never mutate old snapshots.
- Fully atomic: scholarship + history + snapshot + restore record all-or-nothing.
- Idempotent: same restore operation must not create duplicate history/snapshots.
- Fail closed on integrity errors.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..models import (
    Scholarship,
    ScholarshipRestoreRecord,
    ScholarshipReview,
    ScholarshipSnapshot,
)
from .counterfactual_safety import (
    CounterfactualSeverity,
    simulate_counterfactual,
)
from .scholarship_history import HistoryEntry, write_verification_history
from .scholarship_updater import (
    _ALLOWLISTED_FIELDS,
    _FROZEN_FIELDS,
    apply_verified_updates,
)
from .temporal_versioning import (
    _SNAPSHOT_FIELDS,
    _extract_snapshot_data,
    _serialize_field_value,
    create_snapshot,
)


class RestoreOutcome:
    SUCCESS = "success"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    FAILED = "failed"
    NOOP = "noop"
    IDEMPOTENT = "idempotent"


class RestoreBlockReason:
    SNAPSHOT_NOT_FOUND = "snapshot_not_found"
    SCHOLARSHIP_NOT_FOUND = "scholarship_not_found"
    CORRUPT_SNAPSHOT = "corrupt_snapshot"
    BROKEN_VERSION_CHAIN = "broken_version_chain"
    MULTIPLE_CURRENT_VERSIONS = "multiple_current_versions"
    REJECTED_REVIEW_CONFLICT = "rejected_review_conflict"
    SAFETY_CRITICAL = "safety_critical"
    FROZEN_FIELD = "frozen_field"
    NO_CHANGES = "no_changes"
    TRANSACTION_FAILED = "transaction_failed"


@dataclass
class RestoreResult:
    success: bool = False
    outcome: str = ""
    operation_id: str | None = None
    restore_record_id: int | None = None
    source_version_id: str | None = None
    target_version_id: str | None = None
    restored_fields: list[str] = field(default_factory=list)
    block_reason: str | None = None
    error: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_operation_id(
    scholarship_id: int,
    source_version_id: str,
    operator: str,
    timestamp: datetime,
) -> str:
    content = json.dumps(
        {
            "scholarship_id": scholarship_id,
            "source_version_id": source_version_id,
            "operator": operator,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _values_equal(current: Any | None, expected: Any | None) -> bool:
    if current is None and expected is None:
        return True
    if current is None or expected is None:
        return False

    if isinstance(current, list) and isinstance(expected, list):
        return sorted(str(x) for x in current) == sorted(str(x) for x in expected)

    if isinstance(current, list) and not isinstance(expected, list):
        normalized_current = sorted(str(x) for x in current)
        normalized_expected = [str(expected)] if expected else []
        return normalized_current == normalized_expected

    if not isinstance(current, list) and isinstance(expected, list):
        normalized_current = [str(current)] if current else []
        normalized_expected = sorted(str(x) for x in expected)
        return normalized_current == normalized_expected

    return str(current).strip() == str(expected).strip()


def validate_snapshot_integrity(
    session: Session,
    snapshot: ScholarshipSnapshot,
) -> tuple[bool, str | None]:
    """Validate snapshot_data integrity before restore.

    Checks:
    - snapshot_data exists and is a dict
    - version_id is present and valid length
    - valid_from is present
    - is_current and valid_to consistency
    - changed_fields are valid snapshot fields
    """
    if not snapshot.snapshot_data or not isinstance(snapshot.snapshot_data, dict):
        return False, "snapshot_data is missing or not a dict"

    if not snapshot.version_id or len(snapshot.version_id) != 16:
        return False, "invalid version_id"

    if not snapshot.valid_from:
        return False, "missing valid_from"

    if snapshot.is_current and snapshot.valid_to is not None:
        return False, "current snapshot cannot have valid_to"

    if not snapshot.is_current and snapshot.valid_to is None:
        return False, "non-current snapshot must have valid_to"

    for field_name in snapshot.changed_fields:
        if field_name not in _SNAPSHOT_FIELDS:
            return False, f"unknown field in changed_fields: {field_name}"

    return True, None


def verify_version_chain(
    session: Session,
    scholarship_id: int,
) -> tuple[bool, str | None]:
    """Verify valid_from/valid_to chain and exactly one current version.

    Checks:
    - At most one snapshot is_current=True
    - The latest snapshot by valid_from is the current one
    - Non-current snapshots have valid_to set
    - Chain is unbroken (no missing valid_to for non-current snapshots)
    """
    stmt = (
        select(ScholarshipSnapshot)
        .where(ScholarshipSnapshot.scholarship_id == scholarship_id)
        .order_by(ScholarshipSnapshot.valid_from.asc())
    )
    snapshots = list(session.execute(stmt).scalars().all())

    if not snapshots:
        return True, None

    current_count = sum(1 for s in snapshots if s.is_current)
    if current_count > 1:
        return False, f"multiple current versions found: {current_count}"

    if current_count == 1:
        last_snapshot = snapshots[-1]
        if not last_snapshot.is_current:
            return False, "latest snapshot is not marked as current"

    for i, snapshot in enumerate(snapshots):
        if snapshot.is_current:
            if snapshot.valid_to is not None:
                return False, f"current snapshot {snapshot.version_id} has valid_to"
        else:
            if snapshot.valid_to is None:
                return False, f"non-current snapshot {snapshot.version_id} missing valid_to"

        if i > 0:
            prev = snapshots[i - 1]
            if not prev.is_current and prev.valid_to is None:
                return False, f"chain break: snapshot {prev.version_id} has no valid_to"

    return True, None


def check_rejected_review_conflicts(
    session: Session,
    scholarship_id: int,
    proposed_changes: dict[str, Any],
) -> tuple[bool, list[str], list[int]]:
    """Check if restore would reintroduce a REJECTED review change.

    Returns:
        (has_conflict, conflicting_fields, conflicting_review_ids)
    """
    stmt = (
        select(ScholarshipReview)
        .where(ScholarshipReview.scholarship_id == scholarship_id)
        .where(ScholarshipReview.decision == "rejected")
    )
    rejected_reviews = list(session.execute(stmt).scalars().all())

    if not rejected_reviews:
        return False, [], []

    conflicting_fields = []
    conflicting_review_ids = []

    for review in rejected_reviews:
        if review.field_name in proposed_changes:
            proposed_value = proposed_changes[review.field_name]
            if _values_equal(proposed_value, review.proposed_value):
                conflicting_fields.append(review.field_name)
                conflicting_review_ids.append(review.id)

    return len(conflicting_fields) > 0, conflicting_fields, conflicting_review_ids


def _find_existing_restore(
    session: Session,
    operation_id: str,
) -> ScholarshipRestoreRecord | None:
    stmt = select(ScholarshipRestoreRecord).where(
        ScholarshipRestoreRecord.operation_id == operation_id
    )
    return session.execute(stmt).scalar_one_or_none()


def _write_restore_record(
    session: Session,
    operation_id: str,
    scholarship_id: int,
    source_version_id: str,
    target_version_id: str,
    restored_fields: list[str],
    outcome: str,
    operator: str,
    reason: str,
    error_detail: str | None,
    timestamp: datetime,
) -> int:
    record = ScholarshipRestoreRecord(
        operation_id=operation_id,
        scholarship_id=scholarship_id,
        source_version_id=source_version_id,
        target_version_id=target_version_id,
        operator=operator,
        reason=reason,
        restored_fields=restored_fields,
        outcome=outcome,
        error_detail=error_detail,
        created_at=timestamp,
    )

    session.add(record)
    session.flush()
    return record.id


def restore_snapshot(
    session: Session,
    scholarship_id: int,
    source_version_id: str,
    operator: str,
    reason: str,
) -> RestoreResult:
    """Restore a scholarship to a previous snapshot state.

    This is the main entry point for disaster recovery. It:
    1. Checks for idempotent re-run (same operation_id)
    2. Validates snapshot integrity
    3. Verifies version chain consistency
    4. Computes proposed changes (diff between snapshot and current state)
    5. Checks for frozen field violations
    6. Checks for rejected review conflicts
    7. Runs counterfactual safety simulation
    8. Applies changes through safe updater (atomic commit)
    9. Writes verification history
    10. Creates new current snapshot
    11. Writes restore audit record

    All operations after the safety check are atomic: either all succeed
    or all rollback.
    """
    result = RestoreResult(source_version_id=source_version_id)
    now = _now()

    operation_id = _compute_operation_id(scholarship_id, source_version_id, operator, now)
    result.operation_id = operation_id

    existing_restore = _find_existing_restore(session, operation_id)
    if existing_restore is not None:
        result.success = True
        result.outcome = RestoreOutcome.IDEMPOTENT
        result.restore_record_id = existing_restore.id
        result.target_version_id = existing_restore.target_version_id
        result.restored_fields = list(existing_restore.restored_fields)
        return result

    snapshot_stmt = (
        select(ScholarshipSnapshot)
        .where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship_id,
                ScholarshipSnapshot.version_id == source_version_id,
            )
        )
    )
    source_snapshot = session.execute(snapshot_stmt).scalar_one_or_none()

    if source_snapshot is None:
        result.outcome = RestoreOutcome.REJECTED
        result.block_reason = RestoreBlockReason.SNAPSHOT_NOT_FOUND
        result.error = f"snapshot {source_version_id} not found for scholarship {scholarship_id}"
        return result

    chain_valid, chain_error = verify_version_chain(session, scholarship_id)
    if not chain_valid:
        result.outcome = RestoreOutcome.REJECTED
        result.block_reason = RestoreBlockReason.BROKEN_VERSION_CHAIN
        result.error = f"version chain integrity check failed: {chain_error}"
        return result

    is_valid, integrity_error = validate_snapshot_integrity(session, source_snapshot)
    if not is_valid:
        result.outcome = RestoreOutcome.REJECTED
        result.block_reason = RestoreBlockReason.CORRUPT_SNAPSHOT
        result.error = f"snapshot integrity check failed: {integrity_error}"
        return result

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        result.outcome = RestoreOutcome.FAILED
        result.block_reason = RestoreBlockReason.SCHOLARSHIP_NOT_FOUND
        result.error = f"scholarship {scholarship_id} not found"
        return result

    proposed_changes: dict[str, Any] = {}
    for field_name in _ALLOWLISTED_FIELDS:
        if field_name in source_snapshot.snapshot_data:
            snapshot_value = source_snapshot.snapshot_data[field_name]
            current_value = getattr(scholarship, field_name, None)
            serialized_current = _serialize_field_value(current_value)

            if snapshot_value != serialized_current:
                proposed_changes[field_name] = snapshot_value

    for field_name in source_snapshot.snapshot_data:
        if field_name in _FROZEN_FIELDS and field_name not in proposed_changes:
            snapshot_value = source_snapshot.snapshot_data[field_name]
            current_value = getattr(scholarship, field_name, None)
            serialized_current = _serialize_field_value(current_value)

            if snapshot_value != serialized_current:
                result.outcome = RestoreOutcome.REJECTED
                result.block_reason = RestoreBlockReason.FROZEN_FIELD
                result.error = f"restore would modify frozen field: {field_name}"
                return result

    if not proposed_changes:
        result.outcome = RestoreOutcome.NOOP
        result.error = "no changes required - scholarship already matches snapshot"
        return result

    has_rejected_conflict, rejected_fields, _ = check_rejected_review_conflicts(
        session, scholarship_id, proposed_changes
    )
    if has_rejected_conflict:
        result.outcome = RestoreOutcome.REJECTED
        result.block_reason = RestoreBlockReason.REJECTED_REVIEW_CONFLICT
        result.error = f"restore conflicts with rejected reviews for fields: {rejected_fields}"
        return result

    current_state = _extract_snapshot_data(scholarship)
    counterfactual_result = simulate_counterfactual(
        session=session,
        scholarship=scholarship,
        proposed_changes=proposed_changes,
        current_state=current_state,
    )

    if counterfactual_result.severity == CounterfactualSeverity.CRITICAL:
        result.outcome = RestoreOutcome.BLOCKED
        result.block_reason = RestoreBlockReason.SAFETY_CRITICAL
        result.error = f"counterfactual safety blocked restore: {counterfactual_result.explanation}"
        return result

    candidates = []
    for field_name, new_value in proposed_changes.items():
        current_value = getattr(scholarship, field_name, None)
        candidates.append({
            "field": field_name,
            "old_value": _serialize_field_value(current_value),
            "new_value": new_value,
            "confidence": "high",
            "is_update_candidate": True,
        })

    try:
        update_result = apply_verified_updates(session, scholarship_id, candidates)

        if update_result.concurrency_conflict:
            result.outcome = RestoreOutcome.FAILED
            result.error = f"concurrency conflict during restore: {update_result.error_reason}"
            return result

        if update_result.update_status == "rejected":
            result.outcome = RestoreOutcome.FAILED
            result.error = f"update rejected: {update_result.error_reason}"
            return result

        restored_fields = update_result.updated_fields

        history_entries = []
        for field_name in restored_fields:
            old_value = current_state.get(field_name)
            new_value = proposed_changes.get(field_name)
            history_entries.append(
                HistoryEntry(
                    field_name=field_name,
                    old_value=old_value,
                    new_value=new_value,
                    change_type="restored",
                    source_url=source_snapshot.source_url,
                    evidence_text=f"Restored from snapshot {source_version_id}",
                    confidence="high",
                    verification_status="restored",
                )
            )

        write_verification_history(session, scholarship_id, history_entries)

        session.refresh(scholarship)

        new_snapshot_result = create_snapshot(
            session=session,
            scholarship=scholarship,
            changed_fields=restored_fields,
            source_url=f"restore:{source_version_id}",
            provenance={
                "restore_operation_id": operation_id,
                "source_version_id": source_version_id,
                "operator": operator,
                "reason": reason,
            },
        )

        if not new_snapshot_result.created:
            session.rollback()
            result.outcome = RestoreOutcome.FAILED
            result.error = "failed to create post-restore snapshot"
            return result

        result.target_version_id = new_snapshot_result.version_id
        result.restored_fields = restored_fields

        restore_record_id = _write_restore_record(
            session=session,
            operation_id=operation_id,
            scholarship_id=scholarship_id,
            source_version_id=source_version_id,
            target_version_id=new_snapshot_result.version_id,
            restored_fields=restored_fields,
            outcome=RestoreOutcome.SUCCESS,
            operator=operator,
            reason=reason,
            error_detail=None,
            timestamp=now,
        )

        session.commit()

        result.restore_record_id = restore_record_id
        result.success = True
        result.outcome = RestoreOutcome.SUCCESS

    except Exception as exc:
        session.rollback()
        result.outcome = RestoreOutcome.FAILED
        result.block_reason = RestoreBlockReason.TRANSACTION_FAILED
        result.error = f"transaction failed: {exc}"
        return result

    return result


def get_restore_history(
    session: Session,
    scholarship_id: int,
    limit: int = 50,
) -> list[ScholarshipRestoreRecord]:
    """Retrieve restore history for a scholarship.

    Returns records ordered by most recent first.
    """
    stmt = (
        select(ScholarshipRestoreRecord)
        .where(ScholarshipRestoreRecord.scholarship_id == scholarship_id)
        .order_by(ScholarshipRestoreRecord.created_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
