"""Temporal versioning and time-travel reconstruction for scholarships.

Provides immutable version history with deterministic reconstruction
of scholarship state at any historical point or application cycle.

Design principles:
- Append-only: existing history is never mutated
- Idempotent: reprocessing same change creates no duplicate versions
- Deterministic: same inputs always produce same version_id
- Bounded: compact snapshots with indexed lookups
- No N+1: batch-friendly reconstruction
- No network calls: all data from existing models
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..models import Scholarship, ScholarshipSnapshot, ScholarshipVerificationHistory


@dataclass(frozen=True)
class TemporalVersion:
    """Represents a single version of a scholarship at a point in time."""

    scholarship_id: int
    version_id: str
    cycle_id: str | None
    valid_from: datetime
    valid_to: datetime | None
    is_current: bool
    changed_fields: tuple[str, ...]
    snapshot_data: dict[str, Any]
    source_url: str | None
    provenance: dict[str, Any]
    created_at: datetime


@dataclass
class ReconstructionResult:
    """Result of a temporal reconstruction query."""

    scholarship_id: int
    timestamp: datetime
    state: dict[str, Any]
    version_id: str | None
    is_current: bool
    versions_applied: int = 0
    found: bool = True


@dataclass
class SnapshotWriteResult:
    """Result of creating a snapshot."""

    snapshot_id: int = 0
    version_id: str = ""
    created: bool = False
    scholarship_id: int = 0
    error: str | None = None


_SNAPSHOT_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "country",
        "degree",
        "funding",
        "description",
        "deadline_date",
        "deadline_display",
        "deadline_precision",
        "status",
        "is_verified",
        "last_verified_at",
        "last_verified_date",
        "verification_status",
        "next_verification_due",
        "verified_by",
        "verification_notes",
        "region",
        "duration",
        "application_period",
        "official_source",
        "official_source_url",
        "catalogue_url",
        "official_updates_url",
        "application_link",
        "eligibility",
        "eligibility_summary",
        "benefits",
        "coverage",
        "requirements",
        "documents",
        "english_requirement",
        "application_method",
        "selection_notes",
        "program_type",
        "best_fit",
        "notes",
    }
)


def _serialize_field_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _extract_snapshot_data(scholarship: Scholarship) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field_name in _SNAPSHOT_FIELDS:
        value = getattr(scholarship, field_name, None)
        data[field_name] = _serialize_field_value(value)
    return data


def _compute_version_id(
    scholarship_id: int,
    timestamp: datetime,
    changed_fields: list[str],
    snapshot_data: dict[str, Any],
) -> str:
    content = json.dumps(
        {
            "scholarship_id": scholarship_id,
            "timestamp": timestamp.isoformat(),
            "changed_fields": sorted(changed_fields),
            "snapshot": snapshot_data,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _compute_evidence_hash(
    scholarship_id: int,
    timestamp: datetime,
    changed_fields: list[str],
) -> str:
    content = json.dumps(
        {
            "scholarship_id": scholarship_id,
            "timestamp": timestamp.isoformat(),
            "changed_fields": sorted(changed_fields),
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _row_to_temporal_version(row: ScholarshipSnapshot) -> TemporalVersion:
    return TemporalVersion(
        scholarship_id=row.scholarship_id,
        version_id=row.version_id,
        cycle_id=row.cycle_id,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        is_current=row.is_current,
        changed_fields=tuple(row.changed_fields) if row.changed_fields else (),
        snapshot_data=dict(row.snapshot_data) if row.snapshot_data else {},
        source_url=row.source_url,
        provenance=dict(row.provenance) if row.provenance else {},
        created_at=row.created_at,
    )


def create_snapshot(
    session: Session,
    scholarship: Scholarship,
    changed_fields: list[str],
    source_url: str | None = None,
    cycle_id: str | None = None,
    timestamp: datetime | None = None,
    provenance: dict[str, Any] | None = None,
) -> SnapshotWriteResult:
    result = SnapshotWriteResult(scholarship_id=scholarship.id)

    if not changed_fields:
        return result

    now = timestamp or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    snapshot_data = _extract_snapshot_data(scholarship)
    version_id = _compute_version_id(scholarship.id, now, changed_fields, snapshot_data)
    evidence_hash = _compute_evidence_hash(scholarship.id, now, changed_fields)

    existing = session.scalar(
        select(ScholarshipSnapshot).where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship.id,
                ScholarshipSnapshot.version_id == version_id,
            )
        )
    )
    if existing is not None:
        return result

    current_version = session.scalar(
        select(ScholarshipSnapshot).where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship.id,
                ScholarshipSnapshot.is_current == True,
            )
        )
    )

    snapshot = ScholarshipSnapshot(
        scholarship_id=scholarship.id,
        version_id=version_id,
        cycle_id=cycle_id,
        valid_from=now,
        valid_to=None,
        is_current=True,
        changed_fields=sorted(set(changed_fields)),
        snapshot_data=snapshot_data,
        source_url=source_url or scholarship.official_source_url,
        evidence_hash=evidence_hash,
        provenance=provenance or {},
    )
    session.add(snapshot)
    session.flush()

    if current_version is not None and current_version.id != snapshot.id:
        current_version.is_current = False
        current_version.valid_to = now
        session.flush()

    result.snapshot_id = snapshot.id
    result.version_id = version_id
    result.created = True
    return result


def get_current_version(session: Session, scholarship_id: int) -> TemporalVersion | None:
    row = session.scalar(
        select(ScholarshipSnapshot).where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship_id,
                ScholarshipSnapshot.is_current == True,
            )
        )
    )
    if row is None:
        return None
    return _row_to_temporal_version(row)


def get_version_history(
    session: Session,
    scholarship_id: int,
    limit: int = 100,
) -> list[TemporalVersion]:
    stmt = (
        select(ScholarshipSnapshot)
        .where(ScholarshipSnapshot.scholarship_id == scholarship_id)
        .order_by(ScholarshipSnapshot.valid_from.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).scalars().all()
    return [_row_to_temporal_version(r) for r in rows]


def get_state_at(
    session: Session,
    scholarship_id: int,
    timestamp: datetime,
) -> ReconstructionResult:
    stmt = (
        select(ScholarshipSnapshot)
        .where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship_id,
                ScholarshipSnapshot.valid_from <= timestamp,
            )
        )
        .order_by(ScholarshipSnapshot.valid_from.desc())
        .limit(1)
    )
    row = session.execute(stmt).scalar_one_or_none()

    if row is None:
        return ReconstructionResult(
            scholarship_id=scholarship_id,
            timestamp=timestamp,
            state={},
            version_id=None,
            is_current=False,
            versions_applied=0,
            found=False,
        )

    return ReconstructionResult(
        scholarship_id=scholarship_id,
        timestamp=timestamp,
        state=dict(row.snapshot_data) if row.snapshot_data else {},
        version_id=row.version_id,
        is_current=row.is_current,
        versions_applied=1,
        found=True,
    )


def get_cycle_state(
    session: Session,
    scholarship_id: int,
    cycle_id: str,
) -> ReconstructionResult | None:
    stmt = (
        select(ScholarshipSnapshot)
        .where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship_id,
                ScholarshipSnapshot.cycle_id == cycle_id,
            )
        )
        .order_by(ScholarshipSnapshot.valid_from.desc())
    )
    row = session.execute(stmt).scalars().first()

    if row is None:
        return None

    return ReconstructionResult(
        scholarship_id=scholarship_id,
        timestamp=row.valid_from,
        state=dict(row.snapshot_data) if row.snapshot_data else {},
        version_id=row.version_id,
        is_current=row.is_current,
        versions_applied=1,
        found=True,
    )


def reconstruct_at_timestamp(
    session: Session,
    scholarship_id: int,
    timestamp: datetime,
) -> ReconstructionResult:
    return get_state_at(session, scholarship_id, timestamp)


def batch_reconstruct_at_timestamps(
    session: Session,
    scholarship_id: int,
    timestamps: list[datetime],
) -> list[ReconstructionResult]:
    if not timestamps:
        return []

    stmt = (
        select(ScholarshipSnapshot)
        .where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship_id,
                ScholarshipSnapshot.valid_from <= max(timestamps),
            )
        )
        .order_by(ScholarshipSnapshot.valid_from.asc())
    )
    all_versions = session.execute(stmt).scalars().all()

    if not all_versions:
        return [
            ReconstructionResult(
                scholarship_id=scholarship_id,
                timestamp=ts,
                state={},
                version_id=None,
                is_current=False,
                versions_applied=0,
                found=False,
            )
            for ts in timestamps
        ]

    sorted_versions = sorted(all_versions, key=lambda v: v.valid_from)
    results: list[ReconstructionResult] = []

    for ts in timestamps:
        applicable: ScholarshipSnapshot | None = None
        for version in sorted_versions:
            if version.valid_from <= ts:
                applicable = version
            else:
                break

        if applicable is None:
            results.append(
                ReconstructionResult(
                    scholarship_id=scholarship_id,
                    timestamp=ts,
                    state={},
                    version_id=None,
                    is_current=False,
                    versions_applied=0,
                    found=False,
                )
            )
        else:
            results.append(
                ReconstructionResult(
                    scholarship_id=scholarship_id,
                    timestamp=ts,
                    state=dict(applicable.snapshot_data) if applicable.snapshot_data else {},
                    version_id=applicable.version_id,
                    is_current=applicable.is_current,
                    versions_applied=1,
                    found=True,
                )
            )

    return results


def get_versions_in_range(
    session: Session,
    scholarship_id: int,
    start: datetime,
    end: datetime,
) -> list[TemporalVersion]:
    stmt = (
        select(ScholarshipSnapshot)
        .where(
            and_(
                ScholarshipSnapshot.scholarship_id == scholarship_id,
                ScholarshipSnapshot.valid_from >= start,
                ScholarshipSnapshot.valid_from <= end,
            )
        )
        .order_by(ScholarshipSnapshot.valid_from.asc())
    )
    rows = session.execute(stmt).scalars().all()
    return [_row_to_temporal_version(r) for r in rows]


def has_meaningful_changes(
    session: Session,
    scholarship: Scholarship,
    changed_fields: list[str],
) -> bool:
    if not changed_fields:
        return False

    current = get_current_version(session, scholarship.id)
    if current is None:
        return True

    current_data = current.snapshot_data
    for field_name in changed_fields:
        new_value = _serialize_field_value(getattr(scholarship, field_name, None))
        old_value = current_data.get(field_name)
        if new_value != old_value:
            return True

    return False


def initialize_version_history(
    session: Session,
    scholarship: Scholarship,
    timestamp: datetime | None = None,
) -> SnapshotWriteResult:
    now = timestamp or datetime.now(timezone.utc)

    existing = session.scalar(
        select(ScholarshipSnapshot).where(
            ScholarshipSnapshot.scholarship_id == scholarship.id,
        ).limit(1)
    )
    if existing is not None:
        return SnapshotWriteResult(scholarship_id=scholarship.id)

    snapshot_data = _extract_snapshot_data(scholarship)
    version_id = _compute_version_id(scholarship.id, now, ["__initial__"], snapshot_data)

    snapshot = ScholarshipSnapshot(
        scholarship_id=scholarship.id,
        version_id=version_id,
        cycle_id=None,
        valid_from=scholarship.created_at or now,
        valid_to=None,
        is_current=True,
        changed_fields=["__initial__"],
        snapshot_data=snapshot_data,
        source_url=scholarship.official_source_url,
        evidence_hash=None,
        provenance={"origin": "initialization"},
    )
    session.add(snapshot)
    session.flush()

    return SnapshotWriteResult(
        snapshot_id=snapshot.id,
        version_id=version_id,
        created=True,
        scholarship_id=scholarship.id,
    )
