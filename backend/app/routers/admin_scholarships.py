"""Authenticated administrative CRUD for scholarship records.

Four surfaces, and the differences between them are deliberate:

* **create / update** write the row and one audit row per request, with the
  before/after values of every changed field in the audit;
* **archive** is the soft delete the product contract already has
  (``is_archived`` + ``archived_at`` + ``archived_reason``): the record
  leaves the public catalogue and keeps everything, reversible with three
  UPDATEs;
* **delete** is the permanent one and it is hard to reach on purpose. It
  needs an explicit typed confirmation of the id, a reason, a dependency
  report that comes back empty for that id, and a transaction that either
  commits the audit row and the deletion together or neither. A record with
  anything depending on it - a student's saved list, an application, a
  verification trail - is refused with what blocks it, because those are
  other people's records.

The audit trail lives in ``scholarship_admin_audit``, which holds no foreign
key to the scholarships table: an audit row that would block the deletion
it records is worse than no audit row.

There is no unauthenticated variant of any of this. The public catalogue
does not write at all.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from ..core.admin_auth import require_admin_secret
from ..database import get_db
from ..models import Scholarship, ScholarshipAdminAudit
from ..services.retention_engine import reference_dependencies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/scholarships", tags=["admin-scholarships"])

#: Columns an administrator may set. Identity, lifecycle and verification
#: machinery are not in here: the id is not assignable, the timestamps are
#: the database's, and the verification queue is a different, separately
#: authenticated flow. Field-of-study is expressed through ``best_fit`` and
#: ``program_type`` on the record, not a separate column.
EDITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "country",
        "region",
        "degree",
        "program_type",
        "best_fit",
        "status",
        "deadline_date",
        "deadline_display",
        "deadline_precision",
        "funding",
        "funding_amount",
        "funding_currency",
        "funding_period",
        "tuition_coverage",
        "living_cost_coverage",
        "travel_coverage",
        "fully_funded",
        "duration",
        "application_period",
        "description",
        "eligibility",
        "eligibility_summary",
        "benefits",
        "coverage",
        "requirements",
        "documents",
        "english_requirement",
        "application_method",
        "selection_notes",
        "official_source",
        "official_source_url",
        "application_link",
        "catalogue_url",
        "official_updates_url",
        "image_url",
        "image_source_url",
        "image_source_type",
        "image_kind",
        "image_alt_text",
        "best_fit",
    }
)

LIST_COLUMNS = (
    "id",
    "title",
    "country",
    "degree",
    "funding",
    "status",
    "deadline_date",
    "deadline_precision",
    "official_source",
    "official_source_url",
    "is_archived",
    "archived_at",
    "archived_reason",
    "updated_at",
    "created_at",
)


class AdminScholarshipCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    country: str = Field(min_length=1, max_length=160)
    degree: str | None = Field(default=None, max_length=512)
    best_fit: str | None = Field(default=None, max_length=2000)
    status: Literal["open", "upcoming", "closed"] = "open"
    funding: str | None = Field(default=None, max_length=512)
    official_source_url: str | None = Field(default=None, max_length=2048)
    reason: str | None = Field(default=None, max_length=2000)
    fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("official_source_url")
    @classmethod
    def _source_must_be_absolute(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("official_source_url must be an absolute http(s) URL")
        return value

    @field_validator("fields")
    @classmethod
    def _fields_must_be_assignable(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(value) - EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"not assignable by this endpoint: {unknown}")
        return value


class AdminScholarshipUpdate(BaseModel):
    fields: dict[str, Any] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("fields")
    @classmethod
    def _fields_must_be_assignable(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(value) - EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"not assignable by this endpoint: {unknown}")
        return value


class AdminArchiveRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class AdminDeleteRequest(BaseModel):
    # The confirm string must repeat the id. A caller who knows only the id
    # from a list response does not delete anything by accident.
    confirm: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)


def _jsonable(value: Any) -> Any:
    """Make a record snapshot JSON-storable.

    The audit columns store the timestamps of the row they describe, and a
    JSON column refuses a datetime object. The row is preserved verbatim
    with ISO-8601 text instead, which is the same instant expressed without
    pretending a database type survived.
    """
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _record_dict(record: Scholarship) -> dict[str, Any]:
    return _jsonable(
        {
            column: getattr(record, column, None)
            for column in LIST_COLUMNS
        }
    )


def _write_audit(
    session: Session,
    *,
    scholarship_id: int,
    scholarship_title: str | None,
    action: str,
    changed_fields: list[str],
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    operator: str,
    reason: str | None,
) -> None:
    session.add(
        ScholarshipAdminAudit(
            scholarship_id=scholarship_id,
            scholarship_title=scholarship_title,
            action=action,
            changed_fields=list(changed_fields),
            before_values=before,
            after_values=after,
            operator=operator,
            reason=reason,
            recorded_at=datetime.now(timezone.utc),
        )
    )


@router.get("")
def list_scholarships(
    q: str | None = Query(default=None, max_length=200),
    status: Literal["open", "upcoming", "closed"] | None = None,
    archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: str = Depends(require_admin_secret),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    statement: Select = select(Scholarship)
    conditions = [Scholarship.is_archived.is_(True) if archived else Scholarship.is_archived.is_(False)]
    if status:
        conditions.append(Scholarship.status == status)
    if q:
        pattern = f"%{q}%"
        conditions.append(
            or_(
                Scholarship.title.ilike(pattern),
                Scholarship.country.ilike(pattern),
                Scholarship.official_source.ilike(pattern),
            )
        )
    statement = statement.where(and_(*conditions)).order_by(Scholarship.id.desc())
    total = db.query(Scholarship).where(and_(*conditions)).count()
    rows = db.execute(
        statement.offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {
        "items": [_record_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{scholarship_id}")
def get_scholarship(
    scholarship_id: int,
    _: str = Depends(require_admin_secret),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    record = db.get(Scholarship, scholarship_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such scholarship record.")
    return {c.key: getattr(record, c.key) for c in Scholarship.__table__.columns}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_scholarship(
    payload: AdminScholarshipCreate,
    _: str = Depends(require_admin_secret),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "title": payload.title.strip(),
        "country": payload.country.strip(),
        "degree": payload.degree,
        "status": payload.status,
    }
    for key in ("best_fit", "funding", "official_source_url"):
        value = getattr(payload, key)
        if value is not None:
            values[key] = value
    values.update(payload.fields)
    record = Scholarship(**values)
    from sqlalchemy.exc import IntegrityError

    try:
        db.add(record)
        db.flush()
        _write_audit(
            db,
            scholarship_id=record.id,
            scholarship_title=record.title,
            action="create",
            changed_fields=sorted(values),
            before=None,
            after=_record_dict(record),
            operator="admin",
            reason=payload.reason,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        logger.info("Admin create refused by a unique constraint: %s", error.__class__.__name__)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": "The record violates a database constraint.",
                "hint": "A record with this official_source_url already exists; deduplicate before creating.",
            },
        )
    db.refresh(record)
    logger.info("Admin created scholarship %s", record.id)
    return _record_dict(record)


@router.patch("/{scholarship_id}")
def update_scholarship(
    scholarship_id: int,
    payload: AdminScholarshipUpdate,
    _: str = Depends(require_admin_secret),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    record = db.get(Scholarship, scholarship_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such scholarship record.")
    before = _record_dict(record)
    changed: list[str] = []
    after: dict[str, Any] = {}
    for key, value in payload.fields.items():
        if getattr(record, key) != value:
            setattr(record, key, value)
            changed.append(key)
            after[key] = value
    if not changed:
        return _record_dict(record)
    _write_audit(
            db,
            scholarship_id=record.id,
            scholarship_title=record.title,
            action="update",
            changed_fields=sorted(changed),
        before=before,
        after=after,
        operator="admin",
        reason=payload.reason,
    )
    db.commit()
    db.refresh(record)
    logger.info("Admin updated scholarship %s: %s", record.id, sorted(changed))
    return _record_dict(record)


@router.post("/{scholarship_id}/archive")
def archive_scholarship(
    scholarship_id: int,
    payload: AdminArchiveRequest,
    _: str = Depends(require_admin_secret),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    record = db.get(Scholarship, scholarship_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such scholarship record.")
    if record.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Record is already archived.")
    before = _record_dict(record)
    archived_at = datetime.now(timezone.utc)
    record.is_archived = True
    record.archived_at = archived_at
    record.archived_reason = payload.reason
    _write_audit(
        db,
        scholarship_id=record.id,
        scholarship_title=record.title,
        action="archive",
        changed_fields=["is_archived", "archived_at", "archived_reason"],
        before=before,
        after=_record_dict(record),
        operator="admin",
        reason=payload.reason,
    )
    db.commit()
    db.refresh(record)
    logger.info("Admin archived scholarship %s", record.id)
    return _record_dict(record)


@router.delete("/{scholarship_id}", status_code=status.HTTP_200_OK)
def delete_scholarship(
    scholarship_id: int,
    payload: AdminDeleteRequest,
    _: str = Depends(require_admin_secret),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    record = db.get(Scholarship, scholarship_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such scholarship record.")
    if payload.confirm.strip() != f"DELETE {scholarship_id}":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Refused: confirm must be exactly "DELETE {scholarship_id}".',
        )

    # The dependency report is computed by the retention engine against the
    # live metadata, so a table added later shows up as unclassified rather
    # than being ignored. Anything blocking here is another record that must
    # survive: student data, verification history, snapshots, knowledge nodes.
    dependencies = reference_dependencies(db, [scholarship_id]).get(scholarship_id, frozenset())
    if dependencies:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "blocked_by": sorted(dependencies),
                "message": (
                    "Records depend on this scholarship and must survive it. Archive it "
                    "instead, or resolve the dependants first."
                ),
            },
        )

    before = _record_dict(record)
    full_before = _jsonable({c.key: getattr(record, c.key) for c in Scholarship.__table__.columns})
    title = record.title
    try:
        db.execute(
            ScholarshipAdminAudit.__table__.insert().values(
                scholarship_id=scholarship_id,
                scholarship_title=title,
                action="delete",
                changed_fields=["<row>"],
                before_values=full_before,
                after_values=None,
                operator="admin",
                reason=payload.reason,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        db.delete(record)
        db.commit()
    except Exception:  # noqa: BLE001 - a partial delete is worse than none
        db.rollback()
        logger.exception("Admin delete of scholarship %s rolled back", scholarship_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deletion failed and was rolled back; nothing was removed.",
        )
    logger.warning("Admin deleted scholarship %s (%s)", scholarship_id, title)
    return {"deleted": scholarship_id, "before": before}


@router.get("/{scholarship_id}/audit")
def scholarship_audit_trail(
    scholarship_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    _: str = Depends(require_admin_secret),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.execute(
            select(ScholarshipAdminAudit)
            .where(ScholarshipAdminAudit.scholarship_id == scholarship_id)
            .order_by(ScholarshipAdminAudit.recorded_at.desc(), ScholarshipAdminAudit.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "scholarship_title": row.scholarship_title,
                "changed_fields": row.changed_fields,
                "before_values": row.before_values,
                "after_values": row.after_values,
                "operator": row.operator,
                "reason": row.reason,
                "recorded_at": row.recorded_at,
            }
            for row in rows
        ],
        "total": len(rows),
    }
