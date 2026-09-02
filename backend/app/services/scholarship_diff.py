"""Deterministic diff engine between Scholarship ORM and extracted data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.models import Scholarship
from app.services.scholarship_extractor import (
    ExtractionConfidence,
    ScholarshipExtractionResult,
)


class FieldChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    IDENTITY_CONFLICT = "identity_conflict"
    CYCLE_CHANGED = "cycle_changed"
    UNCERTAIN = "uncertain"


class FieldSource(str, Enum):
    EXTRACTOR = "extractor"
    DATABASE = "database"


@dataclass
class FieldChange:
    field: str
    change_type: FieldChangeType
    old_value: Any | None = None
    new_value: Any | None = None
    source: str = ""
    confidence: str | None = None
    is_update_candidate: bool = False


@dataclass
class ChangeSet:
    changes: list[FieldChange] = field(default_factory=list)
    is_new_scholarship: bool = False
    identity_conflict: bool = False
    cycle_changed: bool = False

    @property
    def has_changes(self) -> bool:
        return any(c.change_type != FieldChangeType.UNCHANGED for c in self.changes)

    @property
    def update_candidates(self) -> list[FieldChange]:
        return [c for c in self.changes if c.is_update_candidate]


_ORM_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "id",
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

_SEMANTIC_DEADLINES: frozenset[str] = frozenset({"rolling", "not announced", "varies"})

_IDENTITY_ORM_FIELDS: frozenset[str] = frozenset({"title", "official_source"})

_FIELD_CONFIG: dict[str, tuple[str | None, str]] = {
    "scholarship_name": ("title", "text"),
    "degree_level": ("degree", "text"),
    "provider": ("official_source", "text"),
    "eligibility": ("eligibility", "json_list"),
    "duration": ("duration", "text"),
    "application_method": ("application_method", "json_list"),
    "deadline": ("deadline_display", "deadline"),
    "status": ("status", "text"),
    "application_url": ("application_link", "url"),
}

_EXTRACTOR_UNMAPPED_FIELDS: frozenset[str] = frozenset(
    {
        "eligible_nationalities",
        "eligible_fields",
        "academic_requirements",
        "gpa_requirement",
        "language_requirement",
        "test_requirements",
        "award_amount",
        "tuition_coverage",
        "living_stipend",
        "housing",
        "travel",
        "insurance",
        "renewal_conditions",
        "deadline_type",
        "scholarship_cycle",
    }
)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text.lower() if text else None


def _normalize_deadline(value: str | None) -> str | None:
    if value is None:
        return None
    text = _normalize_text(value)
    if text is None:
        return None
    if text in _SEMANTIC_DEADLINES:
        return text
    return text


def _normalize_json_list(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, list):
        items = [_normalize_text(str(v)) for v in value if v is not None]
        items = [v for v in items if v is not None]
        return tuple(sorted(items)) if items else None
    text = _normalize_text(str(value))
    return (text,) if text else None


def _normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    text = _normalize_text(value)
    return text if text else None


_NORMALIZERS: dict[str, Any] = {
    "text": _normalize_text,
    "deadline": _normalize_deadline,
    "json_list": _normalize_json_list,
    "url": _normalize_url,
}


def _get_confidence(extracted: ScholarshipExtractionResult, field: str) -> str | None:
    return extracted.confidence.get(field)


def _is_low_confidence(confidence: str | None) -> bool:
    return confidence == ExtractionConfidence.LOW


def diff_scholarship(
    scholarship: Scholarship,
    extracted: ScholarshipExtractionResult,
) -> ChangeSet:
    changes: list[FieldChange] = []
    identity_conflict = False

    for extractor_field, (orm_field, normalizer_name) in _FIELD_CONFIG.items():
        if orm_field is None:
            continue

        normalizer = _NORMALIZERS[normalizer_name]
        extractor_raw = getattr(extracted, extractor_field, None)
        orm_raw = getattr(scholarship, orm_field, None)

        norm_extractor = normalizer(extractor_raw)
        norm_orm = normalizer(orm_raw)
        confidence = _get_confidence(extracted, extractor_field)

        if norm_extractor is None:
            change_type = FieldChangeType.REMOVED
            is_update_candidate = False
        elif norm_orm is None:
            change_type = FieldChangeType.ADDED
            is_update_candidate = not _is_low_confidence(confidence)
        else:
            if norm_extractor == norm_orm:
                change_type = FieldChangeType.UNCHANGED
                is_update_candidate = False
            else:
                change_type = FieldChangeType.MODIFIED
                is_update_candidate = not _is_low_confidence(confidence)

        change = FieldChange(
            field=orm_field,
            change_type=change_type,
            old_value=orm_raw,
            new_value=extractor_raw,
            source=f"{FieldSource.EXTRACTOR.value} -> {FieldSource.DATABASE.value}",
            confidence=confidence,
            is_update_candidate=is_update_candidate,
        )
        changes.append(change)

    for change in changes:
        if change.field in _IDENTITY_ORM_FIELDS and change.change_type == FieldChangeType.MODIFIED:
            identity_conflict = True
            change.change_type = FieldChangeType.IDENTITY_CONFLICT
            change.is_update_candidate = False

    return ChangeSet(
        changes=changes,
        is_new_scholarship=False,
        identity_conflict=identity_conflict,
        cycle_changed=False,
    )
