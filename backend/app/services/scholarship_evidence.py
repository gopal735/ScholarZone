"""Evidence layer for scholarship field extraction traceability.

Every extracted scholarship field that may become an update candidate is traceable
to the official source evidence that produced it.

This module is deterministic, read-only, and does not modify the database.
It integrates with ScholarshipExtractionResult and ChangeSet architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

from .scholarship_extractor import ScholarshipExtractionResult
from .scholarship_diff import ChangeSet, FieldChangeType


class SourceType(str, Enum):
    """Classification of source authority for evidence items."""

    OFFICIAL_GOVERNMENT = "official_government"
    OFFICIAL_UNIVERSITY = "official_university"
    OFFICIAL_SCHOLARSHIP_PROGRAM = "official_scholarship_program"
    OFFICIAL_APPLICATION_PORTAL = "official_application_portal"
    THIRD_PARTY = "third_party"


class EvidenceStatus(str, Enum):
    """Status of an evidence item after safety evaluation."""

    HIGH_CONFIDENCE = "high_confidence"
    LOW_CONFIDENCE = "low_confidence"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    IDENTITY_CONFLICT = "identity_conflict"


# Official government domains and patterns
_GOVERNMENT_DOMAINS: frozenset[str] = frozenset({
    ".gov", ".gov.uk", ".gov.au", ".gc.ca", ".gob.mx",
    ".go.jp", ".go.kr", ".gov.in", ".gov.br", ".gob.ec",
    ".admin.ch", ".bund.de", ".gouv.fr", ".gov.sg",
})

_GOVERNMENT_HOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^www\.gov\.", re.IGNORECASE),
    re.compile(r"^gov\.", re.IGNORECASE),
    re.compile(r"\.gov\.", re.IGNORECASE),
    re.compile(r"\.gob\.", re.IGNORECASE),
    re.compile(r"\.go\.", re.IGNORECASE),
    re.compile(r"\.gc\.ca$", re.IGNORECASE),
    re.compile(r"\.admin\.ch$", re.IGNORECASE),
    re.compile(r"\.bund\.de$", re.IGNORECASE),
    re.compile(r"\.gouv\.fr$", re.IGNORECASE),
]

# Official university domains
_UNIVERSITY_DOMAINS: frozenset[str] = frozenset({
    ".edu", ".ac.uk", ".ac.jp", ".ac.kr", ".ac.in",
    ".ac.nz", ".ac.za", ".edu.au", ".edu.br", ".edu.sg",
    ".uni-", ".university",
})

_UNIVERSITY_HOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^www\.edu\.", re.IGNORECASE),
    re.compile(r"\.edu\.", re.IGNORECASE),
    re.compile(r"\.ac\.", re.IGNORECASE),
    re.compile(r"^uni-", re.IGNORECASE),
    re.compile(r"\.edu$", re.IGNORECASE),
    re.compile(r"\.ac\.\w+$", re.IGNORECASE),
]

# Known scholarship program domains
_SCHOLARSHIP_PROGRAM_HOSTS: frozenset[str] = frozenset({
    "www.daad.de",
    "www.campusfrance.org",
    "www.sbfi.admin.ch",
    "www.studyinindia.gov.in",
    "www.jasso.go.jp",
    "www.deutschlandstipendium.de",
    "www.chevening.org",
    "csc.edu.cn",
    "www.scholars4dev.com",
})

# Known application portal domains
_APPLICATION_PORTAL_HOSTS: frozenset[str] = frozenset({
    "apply.daad.de",
    "portal.campusfrance.org",
    "apply.sbfi.admin.ch",
    "www.studyinindia.gov.in",
    "apply.jasso.go.jp",
    "www.applyweb.com",
    "www.commonapp.org",
    "www.universityadmissions.se",
    "www.ucas.com",
})

# Mapping from extractor field names to source text search patterns
# Used to find the smallest useful evidence snippet
_FIELD_EVIDENCE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "scholarship_name": [
        re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL),
    ],
    "provider": [
        re.compile(r"(?:offered?\s+by|provided?\s+by|funded?\s+by|sponsored?\s+by)[:\s]+([^\n]+)", re.IGNORECASE),
    ],
    "degree_level": [
        re.compile(r'(?:degree|level)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "eligibility": [
        re.compile(r'(?:eligib(?:ility)\s+criteria|criteria|eligib(?:ility)|requirements?)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "duration": [
        re.compile(r'(?:duration|length)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "deadline": [
        re.compile(r"deadline[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"applications?\s+close[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"apply\s+by[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"applications?\s+are\s+due[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"closing\s+date[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
        re.compile(r"due\s+date[:\s]+(.+?)(?:\n|$)", re.IGNORECASE),
    ],
    "award_amount": [
        re.compile(r'(?:award|amount|value)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "tuition_coverage": [
        re.compile(r'(?:full[\s-]?tuition|tuition)[:\s]+(.+)', re.IGNORECASE),
    ],
    "living_stipend": [
        re.compile(r'(?:living\s+stipend|stipend)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "gpa_requirement": [
        re.compile(r'(?:gpa|grade\s+point\s+average)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "language_requirement": [
        re.compile(r'(?:language|english|ielts|toefl)[:\s]+([^\n]+)', re.IGNORECASE),
    ],
    "application_url": [
        re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL),
    ],
}


@dataclass(frozen=True)
class EvidenceItem:
    """A single piece of evidence supporting an extracted field value.

    Each evidence item traces one extracted field back to its source.
    """

    scholarship_id: int
    field_name: str
    extracted_value: Any
    source_url: str
    evidence_text: str
    confidence: str | None
    source_type: SourceType
    verification_timestamp: str
    status: EvidenceStatus = EvidenceStatus.MISSING


@dataclass
class EvidenceCollection:
    """A collection of evidence items for a single scholarship."""

    scholarship_id: int
    source_url: str
    items: list[EvidenceItem] = field(default_factory=list)
    collected_at: str = ""

    @property
    def high_confidence_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.HIGH_CONFIDENCE]

    @property
    def low_confidence_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.LOW_CONFIDENCE]

    @property
    def missing_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.MISSING]

    @property
    def ambiguous_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.AMBIGUOUS]

    @property
    def identity_conflict_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.status == EvidenceStatus.IDENTITY_CONFLICT]

    @property
    def has_any_evidence(self) -> bool:
        return any(i.status not in (EvidenceStatus.MISSING,) for i in self.items)

    def get_evidence_for_field(self, field_name: str) -> EvidenceItem | None:
        for item in self.items:
            if item.field_name == field_name:
                return item
        return None


def classify_source(source_url: str) -> SourceType:
    """Classify a source URL by its authority level.

    Deterministic classification based on domain patterns.
    """
    if not source_url:
        return SourceType.THIRD_PARTY

    parsed = urlsplit(source_url)
    hostname = parsed.netloc.lower()

    # Remove port if present
    if ":" in hostname:
        hostname = hostname.split(":")[0]

    # Check known scholarship program hosts first (most specific)
    if hostname in _SCHOLARSHIP_PROGRAM_HOSTS:
        return SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM

    # Check known application portal hosts
    if hostname in _APPLICATION_PORTAL_HOSTS:
        return SourceType.OFFICIAL_APPLICATION_PORTAL

    # Check government patterns
    for pattern in _GOVERNMENT_HOST_PATTERNS:
        if pattern.search(hostname):
            return SourceType.OFFICIAL_GOVERNMENT

    # Check university patterns
    for pattern in _UNIVERSITY_HOST_PATTERNS:
        if pattern.search(hostname):
            return SourceType.OFFICIAL_UNIVERSITY

    return SourceType.THIRD_PARTY


def _extract_evidence_text(
    field_name: str,
    extracted_value: Any,
    source_content: str,
) -> str:
    """Extract the smallest useful evidence snippet from source content.

    Returns the matching text snippet that supports the extracted value.
    If no specific pattern matches, returns an empty string.
    """
    if not source_content or extracted_value is None:
        return ""

    patterns = _FIELD_EVIDENCE_PATTERNS.get(field_name, [])

    for pattern in patterns:
        match = pattern.search(source_content)
        if match:
            # For patterns with groups, use the first group
            if match.lastindex and match.lastindex >= 1:
                return match.group(1).strip()
            return match.group(0).strip()

    # Fallback: try to find the extracted value directly in the source
    value_str = str(extracted_value)
    if value_str and value_str != "None":
        # Search for the value in the source content
        escaped = re.escape(value_str[:100])  # Limit search length
        fallback_pattern = re.compile(escaped, re.IGNORECASE)
        match = fallback_pattern.search(source_content)
        if match:
            # Return surrounding context (up to 200 chars)
            start = max(0, match.start() - 50)
            end = min(len(source_content), match.end() + 150)
            return source_content[start:end].strip()

    return ""


def _evaluate_evidence_status(
    confidence: str | None,
    evidence_text: str,
    change_type: FieldChangeType | None,
    is_identity_conflict: bool = False,
) -> EvidenceStatus:
    """Evaluate the status of an evidence item based on confidence and context."""
    if is_identity_conflict:
        return EvidenceStatus.IDENTITY_CONFLICT

    if change_type == FieldChangeType.IDENTITY_CONFLICT:
        return EvidenceStatus.IDENTITY_CONFLICT

    if confidence == "low":
        return EvidenceStatus.LOW_CONFIDENCE

    if not evidence_text or evidence_text.strip() == "":
        return EvidenceStatus.MISSING

    if confidence == "high":
        return EvidenceStatus.HIGH_CONFIDENCE

    if confidence == "medium":
        return EvidenceStatus.HIGH_CONFIDENCE

    return EvidenceStatus.LOW_CONFIDENCE


def collect_evidence(
    scholarship_id: int,
    source_url: str,
    source_content: str,
    extraction_result: ScholarshipExtractionResult,
    changeset: ChangeSet | None = None,
) -> EvidenceCollection:
    """Collect evidence for all extracted fields from a scholarship source.

    This is the main entry point for building the evidence layer.
    It is deterministic and read-only.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    source_type = classify_source(source_url)

    collection = EvidenceCollection(
        scholarship_id=scholarship_id,
        source_url=source_url,
        collected_at=timestamp,
    )

    # Build a map of field -> change info from changeset
    change_map: dict[str, Any] = {}
    identity_conflict_fields: set[str] = set()
    if changeset:
        for change in changeset.changes:
            change_map[change.field] = change
            if change.change_type == FieldChangeType.IDENTITY_CONFLICT:
                identity_conflict_fields.add(change.field)

    # Map extractor field names to ORM field names (from scholarship_diff._FIELD_CONFIG)
    extractor_to_orm_fields = {
        "scholarship_name": "title",
        "provider": "official_source",
        "degree_level": "degree",
        "eligibility": "eligibility",
        "duration": "duration",
        "application_method": "application_method",
        "deadline": "deadline_display",
        "status": "status",
        "application_url": "application_link",
    }

    # Collect evidence for all fields present in the extraction result
    processed_orm_fields: set[str] = set()

    for extractor_field, orm_field in extractor_to_orm_fields.items():
        if orm_field in processed_orm_fields:
            continue

        extracted_value = getattr(extraction_result, extractor_field, None)
        confidence = extraction_result.confidence.get(extractor_field)

        # Get change info if available
        change = change_map.get(orm_field)
        change_type = change.change_type if change else None
        is_identity_conflict = orm_field in identity_conflict_fields

        # Extract evidence text from source
        evidence_text = _extract_evidence_text(extractor_field, extracted_value, source_content)

        # Evaluate status
        status = _evaluate_evidence_status(confidence, evidence_text, change_type, is_identity_conflict)

        item = EvidenceItem(
            scholarship_id=scholarship_id,
            field_name=orm_field,
            extracted_value=extracted_value,
            source_url=source_url,
            evidence_text=evidence_text,
            confidence=confidence,
            source_type=source_type,
            verification_timestamp=timestamp,
            status=status,
        )
        collection.items.append(item)
        processed_orm_fields.add(orm_field)

    # Also collect evidence for unmapped extractor fields that have values
    unmapped_fields = [
        "eligible_nationalities", "eligible_fields", "academic_requirements",
        "gpa_requirement", "language_requirement", "test_requirements",
        "award_amount", "tuition_coverage", "living_stipend", "housing",
        "travel", "insurance", "renewal_conditions", "deadline_type",
        "scholarship_cycle",
    ]

    for extractor_field in unmapped_fields:
        extracted_value = getattr(extraction_result, extractor_field, None)
        if extracted_value is None:
            continue

        confidence = extraction_result.confidence.get(extractor_field)
        evidence_text = _extract_evidence_text(extractor_field, extracted_value, source_content)
        status = _evaluate_evidence_status(confidence, evidence_text, None, False)

        item = EvidenceItem(
            scholarship_id=scholarship_id,
            field_name=extractor_field,
            extracted_value=extracted_value,
            source_url=source_url,
            evidence_text=evidence_text,
            confidence=confidence,
            source_type=source_type,
            verification_timestamp=timestamp,
            status=status,
        )
        collection.items.append(item)

    return collection


def is_authoritative_source(source_type: SourceType) -> bool:
    """Check if a source type is authoritative (official)."""
    return source_type in {
        SourceType.OFFICIAL_GOVERNMENT,
        SourceType.OFFICIAL_UNIVERSITY,
        SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
        SourceType.OFFICIAL_APPLICATION_PORTAL,
    }


def can_automatically_update(collection: EvidenceCollection) -> tuple[bool, list[str]]:
    """Determine if the evidence collection supports automatic updates.

    Safety rules:
    - No evidence -> no automatic update
    - Low-confidence evidence -> not an automatic update candidate
    - Ambiguous evidence -> needs_review
    - Identity-conflict evidence -> needs_review

    Returns:
        Tuple of (can_update, reasons)
    """
    reasons: list[str] = []

    if not collection.has_any_evidence:
        reasons.append("No evidence available for any field")
        return False, reasons

    # Check for identity conflicts
    if collection.identity_conflict_items:
        reasons.append(f"Identity conflict detected on fields: {[i.field_name for i in collection.identity_conflict_items]}")
        return False, reasons

    # Check for ambiguous evidence
    if collection.ambiguous_items:
        reasons.append(f"Ambiguous evidence on fields: {[i.field_name for i in collection.ambiguous_items]}")
        return False, reasons

    # Check that we have at least one high-confidence item
    if not collection.high_confidence_items:
        reasons.append("No high-confidence evidence available")
        return False, reasons

    # Check that source is authoritative
    if collection.items:
        source_type = collection.items[0].source_type
        if not is_authoritative_source(source_type):
            reasons.append(f"Source is not authoritative: {source_type.value}")
            return False, reasons

    return True, reasons
