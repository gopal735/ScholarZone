"""Safe, verified update engine for scholarship automatic update candidates.

This service applies validated ChangeSet candidates to the database with:
- Strict field allowlisting (scholarship-content fields only)
- Atomic transactions (all-or-nothing commits)
- Stale-write protection (optimistic concurrency via old_value checks)
- Idempotent operations (reapplying same candidates is a no-o)
- Individual field updates (never replaces the entire ORM object)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..models import Scholarship
from .scholarship_diff import ChangeSet, FieldChangeType


_UPDATE_STATUS_SUCCESS = "success"
_UPDATE_STATUS_PARTIAL = "partial"
_UPDATE_STATUS_REJECTED = "rejected"
_UPDATE_STATUS_CONFLICT = "conflict"
_UPDATE_STATUS_NOOP = "noop"


_FROZEN_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "title",
        "country",
        "official_source",
        "official_source_url",
        "is_verified",
        "last_verified_at",
        "last_verified_date",
        "verification_status",
        "next_verification_due",
        "verified_by",
        "verification_notes",
        "created_at",
        "updated_at",
    }
)


_ALLOWLISTED_FIELDS: frozenset[str] = frozenset(
    {
        "degree",
        "funding",
        "description",
        "deadline_date",
        "deadline_display",
        "deadline_precision",
        "status",
        "region",
        "duration",
        "application_period",
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


@dataclass
class UpdateResult:
    scholarship_id: int
    updated_fields: list[str] = field(default_factory=list)
    skipped_fields: list[str] = field(default_factory=list)
    rejected_fields: list[dict[str, str]] = field(default_factory=list)
    update_status: str = _UPDATE_STATUS_SUCCESS
    concurrency_conflict: bool = False
    error_reason: str | None = None


def _is_valid_candidate(candidate: dict[str, Any]) -> tuple[bool, str | None]:
    if not candidate or not isinstance(candidate, dict):
        return False, "invalid candidate structure"

    change_type = candidate.get("change_type")
    if change_type == FieldChangeType.IDENTITY_CONFLICT:
        return False, "identity conflict"
    if change_type == FieldChangeType.UNCERTAIN:
        return False, "uncertain change"
    if change_type == FieldChangeType.UNCHANGED:
        return False, "unchanged field"

    confidence = candidate.get("confidence")
    if confidence == "low":
        return False, "low confidence"

    if candidate.get("is_update_candidate") is False:
        return False, "not an update candidate"

    field_name = candidate.get("field")
    if not field_name:
        return False, "missing field name"

    return True, None


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


def apply_verified_updates(
    session: Session,
    scholarship_id: int,
    candidates: list[dict[str, Any]],
) -> UpdateResult:
    result = UpdateResult(scholarship_id=scholarship_id)

    if not candidates:
        result.update_status = _UPDATE_STATUS_NOOP
        result.error_reason = "no candidates provided"
        return result

    scholarship: Scholarship | None = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        result.update_status = _UPDATE_STATUS_REJECTED
        result.error_reason = f"scholarship {scholarship_id} not found"
        return result

    approved_updates: list[tuple[str, Any]] = []
    has_conflict = False

    for candidate in candidates:
        field_name = candidate.get("field", "<unknown>")

        is_valid, rejection_reason = _is_valid_candidate(candidate)
        if not is_valid:
            result.rejected_fields.append(
                {"field": field_name, "reason": rejection_reason or "rejected"}
            )
            continue

        if field_name in _FROZEN_FIELDS:
            result.rejected_fields.append(
                {"field": field_name, "reason": "field is frozen"}
            )
            continue

        if field_name not in _ALLOWLISTED_FIELDS:
            result.rejected_fields.append(
                {"field": field_name, "reason": "field not in allowlist"}
            )
            continue

        if not hasattr(Scholarship, field_name):
            result.rejected_fields.append(
                {"field": field_name, "reason": "field does not exist on model"}
            )
            continue

        old_value = candidate.get("old_value")
        new_value = candidate.get("new_value")

        current_value = getattr(scholarship, field_name, None)

        if _values_equal(current_value, new_value):
            result.skipped_fields.append(field_name)
            continue

        if not _values_equal(current_value, old_value):
            has_conflict = True
            result.rejected_fields.append(
                {
                    "field": field_name,
                    "reason": "concurrency conflict: current value does not match expected old value",
                }
            )
            continue

        approved_updates.append((field_name, new_value))

    if has_conflict:
        result.concurrency_conflict = True
        result.update_status = _UPDATE_STATUS_CONFLICT
        result.error_reason = "concurrency conflict detected"
        session.rollback()
        return result

    if not approved_updates:
        if result.rejected_fields:
            result.update_status = _UPDATE_STATUS_REJECTED
            result.error_reason = "all candidates rejected"
        else:
            result.update_status = _UPDATE_STATUS_NOOP
            result.error_reason = "no fields required updating"
        return result

    try:
        for field_name, new_value in approved_updates:
            setattr(scholarship, field_name, new_value)
            result.updated_fields.append(field_name)

        session.flush()
        session.commit()
    except Exception as exc:
        session.rollback()
        result.updated_fields.clear()
        result.update_status = _UPDATE_STATUS_REJECTED
        result.error_reason = f"transaction failed: {exc}"
        return result

    if result.rejected_fields:
        result.update_status = _UPDATE_STATUS_PARTIAL
    else:
        result.update_status = _UPDATE_STATUS_SUCCESS

    return result


def apply_changeset(
    session: Session,
    scholarship_id: int,
    changeset: ChangeSet,
) -> UpdateResult:
    candidates = []
    for change in changeset.changes:
        candidates.append(
            {
                "field": change.field,
                "change_type": change.change_type,
                "old_value": change.old_value,
                "new_value": change.new_value,
                "confidence": change.confidence,
                "is_update_candidate": change.is_update_candidate,
            }
        )
    return apply_verified_updates(session, scholarship_id, candidates)
