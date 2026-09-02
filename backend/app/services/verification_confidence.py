"""Confidence and cross-source verification engine for scholarship data.

Turns extracted values, evidence, source authority, and cross-source agreement
into deterministic verification decisions.

This module is:
- Deterministic: same inputs always produce same outputs
- Read-only: does not modify the database
- Isolated: no scheduler, no retries, no frontend dependencies
- Safety-first: hard rules block automatic updates on any uncertainty

Pipeline:
    Evidence -> Source Authority -> Evidence Quality -> Cross-Source Comparison
    -> Confidence Assessment -> Verification Decision
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .scholarship_evidence import (
    EvidenceItem,
    SourceType,
    is_authoritative_source,
)


class ConfidenceLevel(str, Enum):
    """Confidence levels for field-level verification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CONFLICT = "conflict"


class VerificationState(str, Enum):
    """Final verification states for a field."""

    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNCERTAIN = "uncertain"
    CONFLICT = "conflict"
    UNSUPPORTED = "unsupported"


# Source authority scores (higher = more authoritative)
_SOURCE_AUTHORITY_SCORES: dict[SourceType, int] = {
    SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM: 100,
    SourceType.OFFICIAL_APPLICATION_PORTAL: 90,
    SourceType.OFFICIAL_UNIVERSITY: 80,
    SourceType.OFFICIAL_GOVERNMENT: 70,
    SourceType.THIRD_PARTY: 0,
}

# Source priority for conflict resolution (lower = higher priority)
_SOURCE_PRIORITY: dict[SourceType, int] = {
    SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM: 1,
    SourceType.OFFICIAL_APPLICATION_PORTAL: 2,
    SourceType.OFFICIAL_UNIVERSITY: 3,
    SourceType.OFFICIAL_GOVERNMENT: 4,
    SourceType.THIRD_PARTY: 99,
}

# Extractor confidence scores
_EXTRACTOR_CONFIDENCE_SCORES: dict[str, int] = {
    "high": 100,
    "medium": 60,
    "low": 20,
}

# Semantic deadline values that are exact
_SEMANTIC_DEADLINES: frozenset[str] = frozenset({
    "rolling",
    "not announced",
    "varies",
    "varies by country",
    "varies by program",
    "tba",
    "to be announced",
    "tbd",
    "to be determined",
})

# Patterns indicating vague/imprecise dates
_VAGUE_DATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\busually\s+", re.IGNORECASE),
    re.compile(r"\btypically\s+", re.IGNORECASE),
    re.compile(r"\bapproximately\s+", re.IGNORECASE),
    re.compile(r"\baround\s+", re.IGNORECASE),
    re.compile(r"\bsometime\s+in\s+", re.IGNORECASE),
    re.compile(r"\bcloses?\s+soon\b", re.IGNORECASE),
    re.compile(r"\bvaries\b", re.IGNORECASE),
    re.compile(r"\bdepends?\s+on\b", re.IGNORECASE),
    re.compile(r"\bcheck\s+(?:the\s+)?website\b", re.IGNORECASE),
    re.compile(r"\bcontact\s+(?:the\s+)?(?:university|office)\b", re.IGNORECASE),
]

# Patterns indicating direct/strong evidence
_STRONG_EVIDENCE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "deadline": [
        re.compile(r"(?:deadline|closes?|due|apply\s+by)[:\s]+(.{1,100})", re.IGNORECASE),
        re.compile(r"(?:applications?\s+(?:must\s+be\s+)?(?:received|submitted|completed))[:\s]+(.{1,100})", re.IGNORECASE),
    ],
    "award_amount": [
        re.compile(r"(?:award|amount|value|funding)[:\s]+([€$£]?\s*[\d,]+(?:\s*(?:per|\/)\s*\w+)?)", re.IGNORECASE),
        re.compile(r"(?:€|\$|£)\s*[\d,]+(?:\s*(?:per|\/)\s*\w+)?", re.IGNORECASE),
    ],
    "duration": [
        re.compile(r"(?:duration|length|lasts?)[:\s]+(.{1,50})", re.IGNORECASE),
        re.compile(r"\b\d+\s*(?:years?|months?|semesters?|weeks?)\b", re.IGNORECASE),
    ],
    "eligibility": [
        re.compile(r"(?:eligib(?:ility)|criteria|requirements?)[:\s]+(.{1,200})", re.IGNORECASE),
        re.compile(r"(?:open\s+to|available\s+to)[:\s]+(.{1,100})", re.IGNORECASE),
    ],
    "tuition_coverage": [
        re.compile(r"(?:full[\s-]?tuition|tuition\s+(?:fee\s+)?(?:waiver|coverage|cover))[:\s]*(.{1,50})", re.IGNORECASE),
        re.compile(r"(?:covers?\s+(?:the\s+)?(?:full|entire)\s+tuition)", re.IGNORECASE),
    ],
    "living_stipend": [
        re.compile(r"(?:living\s+stipend|stipend|monthly\s+allowance)[:\s]+([€$£]?\s*[\d,]+)", re.IGNORECASE),
        re.compile(r"(?:€|\$|£)\s*[\d,]+\s*(?:per|\/)\s*month", re.IGNORECASE),
    ],
}

# Patterns for current-cycle detection
_CYCLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b20\d{2}\s*[-–]\s*20\d{2}\b"),
    re.compile(r"\b20\d{2}\s*[-–]\s*\d{2}\b"),
    re.compile(r"\bacademic\s+year\s+20\d{2}\b", re.IGNORECASE),
    re.compile(r"\b20\d{2}[-/]20\d{2}\b"),
    re.compile(r"\b20\d{2}[-/]\d{2}\b"),
]


@dataclass
class FieldConfidenceResult:
    """Structured confidence result for a single field."""

    field_name: str
    value: Any
    confidence: ConfidenceLevel
    verification_state: VerificationState
    source_count: int
    authoritative_source_count: int
    agreeing_source_count: int
    conflicting_source_count: int
    evidence_references: list[str] = field(default_factory=list)
    reason: str = ""
    is_update_candidate: bool = False
    authority_score: int = 0
    quality_score: int = 0
    cross_source_score: int = 0


@dataclass
class VerificationAssessment:
    """Complete verification assessment for a scholarship."""

    scholarship_id: int
    field_results: list[FieldConfidenceResult] = field(default_factory=list)
    assessed_at: str = ""

    @property
    def verified_fields(self) -> list[FieldConfidenceResult]:
        return [f for f in self.field_results if f.verification_state == VerificationState.VERIFIED]

    @property
    def conflicted_fields(self) -> list[FieldConfidenceResult]:
        return [f for f in self.field_results if f.verification_state == VerificationState.CONFLICT]

    @property
    def uncertain_fields(self) -> list[FieldConfidenceResult]:
        return [f for f in self.field_results if f.verification_state == VerificationState.UNCERTAIN]

    @property
    def update_candidates(self) -> list[FieldConfidenceResult]:
        return [f for f in self.field_results if f.is_update_candidate]

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicted_fields) > 0

    def get_field_result(self, field_name: str) -> FieldConfidenceResult | None:
        for result in self.field_results:
            if result.field_name == field_name:
                return result
        return None


def _normalize_value(value: Any) -> str:
    """Normalize a value for comparison."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _create_date_fingerprint(value: Any) -> str | None:
    """Create a fingerprint for date values that recognizes equivalent dates.

    Converts various date formats to a canonical form for comparison.
    Returns None if the value doesn't appear to be a date.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Month name to number mapping
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
        "oct": 10, "nov": 11, "dec": 12,
    }

    text_lower = text.lower()

    # Extract 4-digit year
    year_match = re.search(r"\b(20\d{2})\b", text)
    year = year_match.group(1) if year_match else None

    month = None
    day = None

    # Try YYYY-MM-DD format first
    ymd_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if ymd_match:
        year = ymd_match.group(1)
        month = int(ymd_match.group(2))
        day = int(ymd_match.group(3))
    else:
        # Try to find month name
        month_name_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b",
            text_lower,
        )
        if month_name_match:
            month = month_names.get(month_name_match.group(1))
            # Try to find day number near month
            day_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", text)
            if day_match:
                d = int(day_match.group(1))
                if 1 <= d <= 31:
                    day = d

    if year and month:
        return f"{year}-{month:02d}-{day:02d}" if day else f"{year}-{month:02d}"
    elif year:
        return year
    return None


def _extract_numeric_value(value: Any) -> str | None:
    """Extract numeric portion from a value for comparison."""
    if value is None:
        return None
    text = str(value)
    # Find all numbers (including decimals and commas)
    numbers = re.findall(r"[\d,]+\.?\d*", text)
    if numbers:
        # Return the first number, normalized
        return numbers[0].replace(",", "")
    return None


def _is_semantic_deadline(value: Any) -> bool:
    """Check if a value is a semantic deadline (rolling, varies, etc.)."""
    if value is None:
        return False
    normalized = _normalize_value(value)
    return normalized in _SEMANTIC_DEADLINES


def _is_vague_date(evidence_text: str) -> bool:
    """Check if evidence text indicates a vague/imprecise date."""
    if not evidence_text:
        return False
    return any(pattern.search(evidence_text) for pattern in _VAGUE_DATE_PATTERNS)


def _is_rolling_deadline(value: Any) -> bool:
    """Check if a value represents a rolling deadline."""
    if value is None:
        return False
    normalized = _normalize_value(value)
    return "rolling" in normalized


def _is_varies_deadline(value: Any) -> bool:
    """Check if a value represents a varies-by deadline."""
    if value is None:
        return False
    normalized = _normalize_value(value)
    return "varies" in normalized or "depends" in normalized


def _values_agree(value1: Any, value2: Any, field_name: str) -> bool:
    """Determine if two values agree for cross-source comparison."""
    if value1 is None and value2 is None:
        return True
    if value1 is None or value2 is None:
        return False

    norm1 = _normalize_value(value1)
    norm2 = _normalize_value(value2)

    # Exact match after normalization
    if norm1 == norm2:
        return True

    # For deadline fields, use date fingerprinting
    if "deadline" in field_name.lower():
        # Both are semantic deadlines
        if _is_semantic_deadline(value1) and _is_semantic_deadline(value2):
            return norm1 == norm2
        # Check for rolling
        if _is_rolling_deadline(value1) and _is_rolling_deadline(value2):
            return True
        # Check for varies
        if _is_varies_deadline(value1) and _is_varies_deadline(value2):
            return True
        # Use date fingerprinting
        fp1 = _create_date_fingerprint(value1)
        fp2 = _create_date_fingerprint(value2)
        if fp1 is not None and fp2 is not None and fp1 == fp2:
            return True

    # For numeric fields, compare numeric portions
    num1 = _extract_numeric_value(value1)
    num2 = _extract_numeric_value(value2)
    if num1 is not None and num2 is not None:
        # Allow small tolerance for formatting differences
        try:
            f1 = float(num1)
            f2 = float(num2)
            if f1 == f2:
                return True
        except ValueError:
            pass

    return False


def _calculate_source_authority(source_type: SourceType) -> int:
    """Calculate authority score for a source type."""
    return _SOURCE_AUTHORITY_SCORES.get(source_type, 0)


def _evaluate_evidence_quality(
    evidence_text: str,
    field_name: str,
    extracted_value: Any,
) -> tuple[int, str]:
    """Evaluate the quality of evidence text.

    Returns a quality score (0-100) and a reason string.
    """
    if not evidence_text or evidence_text.strip() == "":
        return 0, "No evidence text available"

    score = 50  # Base score for having evidence
    reasons: list[str] = []

    # Check for strong evidence patterns
    field_patterns = _STRONG_EVIDENCE_PATTERNS.get(field_name, [])
    has_strong_pattern = False
    for pattern in field_patterns:
        if pattern.search(evidence_text):
            has_strong_pattern = True
            score += 20
            reasons.append("Strong evidence pattern match")
            break

    # Check if extracted value appears in evidence
    if extracted_value is not None:
        value_str = str(extracted_value).lower()
        if value_str in evidence_text.lower():
            score += 15
            reasons.append("Extracted value found in evidence")

    # Penalize vague dates
    if _is_vague_date(evidence_text):
        score -= 30
        reasons.append("Vague/imprecise date language detected")

    # Check evidence length (too short = weak, too long = noisy)
    text_length = len(evidence_text)
    if text_length < 10:
        score -= 10
        reasons.append("Evidence text too short")
    elif text_length > 500:
        score -= 5
        reasons.append("Evidence text very long (may be noisy)")
    elif 20 <= text_length <= 200:
        score += 5
        reasons.append("Evidence text optimal length")

    # Clamp score
    score = max(0, min(100, score))

    reason_str = "; ".join(reasons) if reasons else "Standard evidence quality"
    return score, reason_str


def _validate_current_cycle(
    evidence_text: str,
    current_cycle: str | None,
) -> tuple[bool, str]:
    """Validate that evidence is relevant to the current cycle.

    Returns (is_current, reason).
    """
    if not evidence_text:
        return False, "No evidence text to validate"

    if not current_cycle:
        # No cycle specified, assume current
        return True, "No cycle constraint specified"

    # Extract years from evidence
    cycle_years = set()
    for pattern in _CYCLE_PATTERNS:
        matches = pattern.findall(evidence_text)
        for match in matches:
            # Extract 4-digit years
            years = re.findall(r"20\d{2}", match)
            cycle_years.update(years)

    if not cycle_years:
        # No years found in evidence, cannot validate
        return True, "No cycle years found in evidence (assumed current)"

    # Check if current cycle year appears in evidence
    current_years = re.findall(r"20\d{2}", current_cycle)
    for year in current_years:
        if year in cycle_years:
            return True, f"Evidence references current cycle year {year}"

    # Evidence references different years
    return False, f"Evidence references years {cycle_years}, not current cycle {current_cycle}"


def _compare_sources(
    evidence_items: list[EvidenceItem],
    field_name: str,
) -> tuple[int, int, int, str]:
    """Compare evidence from multiple sources for the same field.

    Returns (agreeing_count, conflicting_count, max_authority_score, reason).
    """
    if len(evidence_items) <= 1:
        count = len(evidence_items)
        authority = _calculate_source_authority(evidence_items[0].source_type) if evidence_items else 0
        return count, 0, authority, "Single source (no comparison needed)"

    # Use date-aware grouping for deadline fields
    if "deadline" in field_name.lower():
        return _compare_date_sources(evidence_items, field_name)

    # Group by normalized value for non-date fields
    value_groups: dict[str, list[EvidenceItem]] = {}
    for item in evidence_items:
        norm = _normalize_value(item.extracted_value)
        if norm not in value_groups:
            value_groups[norm] = []
        value_groups[norm].append(item)

    if len(value_groups) == 1:
        # All sources agree
        max_authority = max(
            _calculate_source_authority(item.source_type) for item in evidence_items
        )
        return len(evidence_items), 0, max_authority, "All sources agree"

    # Multiple different values - conflict
    # Find the group with highest authority
    best_group_norm = None
    best_authority = -1
    for norm, items in value_groups.items():
        group_authority = max(
            _calculate_source_authority(item.source_type) for item in items
        )
        if group_authority > best_authority:
            best_authority = group_authority
            best_group_norm = norm

    # Count agreeing (in best group) vs conflicting
    agreeing = len(value_groups[best_group_norm])
    conflicting = len(evidence_items) - agreeing

    # Check if conflicting sources are also authoritative
    conflicting_authoritative = any(
        is_authoritative_source(item.source_type)
        for norm, items in value_groups.items()
        if norm != best_group_norm
        for item in items
    )

    if conflicting_authoritative and agreeing > 0:
        reason = f"Authoritative sources disagree: {len(value_groups)} distinct values"
    else:
        reason = f"Sources disagree: {len(value_groups)} distinct values"

    return agreeing, conflicting, best_authority, reason


def _compare_date_sources(
    evidence_items: list[EvidenceItem],
    field_name: str,
) -> tuple[int, int, int, str]:
    """Compare date values from multiple sources using date fingerprinting."""
    # Create date fingerprints for each item
    fingerprinted: list[tuple[str | None, EvidenceItem]] = []
    for item in evidence_items:
        fp = _create_date_fingerprint(item.extracted_value)
        fingerprinted.append((fp, item))

    # Group by fingerprint
    fp_groups: dict[str | None, list[EvidenceItem]] = {}
    for fp, item in fingerprinted:
        key = fp if fp is not None else _normalize_value(item.extracted_value)
        if key not in fp_groups:
            fp_groups[key] = []
        fp_groups[key].append(item)

    if len(fp_groups) == 1:
        # All sources agree (by date fingerprint)
        max_authority = max(
            _calculate_source_authority(item.source_type) for item in evidence_items
        )
        return len(evidence_items), 0, max_authority, "All sources agree (date match)"

    # Multiple different values - conflict
    # Find the group with highest authority
    best_group_key = None
    best_authority = -1
    for key, items in fp_groups.items():
        group_authority = max(
            _calculate_source_authority(item.source_type) for item in items
        )
        if group_authority > best_authority:
            best_authority = group_authority
            best_group_key = key

    # Count agreeing (in best group) vs conflicting
    agreeing = len(fp_groups[best_group_key])
    conflicting = len(evidence_items) - agreeing

    # Check if conflicting sources are also authoritative
    conflicting_authoritative = any(
        is_authoritative_source(item.source_type)
        for key, items in fp_groups.items()
        if key != best_group_key
        for item in items
    )

    if conflicting_authoritative and agreeing > 0:
        reason = f"Authoritative sources disagree: {len(fp_groups)} distinct dates"
    else:
        reason = f"Sources disagree: {len(fp_groups)} distinct dates"

    return agreeing, conflicting, best_authority, reason


def _determine_confidence(
    authority_score: int,
    quality_score: int,
    extractor_confidence: str | None,
    cross_source_agreeing: int,
    cross_source_conflicting: int,
    is_current_cycle: bool,
) -> tuple[ConfidenceLevel, str]:
    """Determine the final confidence level.

    Returns (confidence, reason).
    """
    # Hard rules first
    if cross_source_conflicting > 0 and cross_source_agreeing > 0:
        return ConfidenceLevel.CONFLICT, "Conflicting values from multiple sources"

    if authority_score == 0:
        return ConfidenceLevel.LOW, "Non-authoritative source"

    if not is_current_cycle:
        return ConfidenceLevel.LOW, "Evidence not from current cycle"

    if quality_score < 20:
        return ConfidenceLevel.LOW, "Very low evidence quality"

    # Extractor confidence is a hard gate
    extractor_score = _EXTRACTOR_CONFIDENCE_SCORES.get(extractor_confidence or "", 50)
    if extractor_score < 40:  # "low" extractor confidence
        return ConfidenceLevel.LOW, f"Low extractor confidence ({extractor_confidence})"

    # Weighted combination - authority and quality are most important
    # For single sources, authority + quality + extractor should be sufficient
    # For multiple agreeing sources, add bonus
    base_score = (
        authority_score * 0.35
        + quality_score * 0.30
        + extractor_score * 0.25
    )

    # Bonus for multiple agreeing sources
    agreement_bonus = 0
    if cross_source_agreeing > 1:
        agreement_bonus = min(cross_source_agreeing * 5, 15)  # Cap at 15

    composite = base_score + agreement_bonus

    # HIGH requires strong scores across the board
    if composite >= 65 and extractor_score >= 60:
        return ConfidenceLevel.HIGH, f"Strong composite score ({composite:.0f})"
    elif composite >= 35:
        return ConfidenceLevel.MEDIUM, f"Moderate composite score ({composite:.0f})"
    else:
        return ConfidenceLevel.LOW, f"Low composite score ({composite:.0f})"


def _determine_verification_state(
    confidence: ConfidenceLevel,
    source_count: int,
    authoritative_count: int,
) -> VerificationState:
    """Determine the verification state from confidence and source info."""
    if confidence == ConfidenceLevel.CONFLICT:
        return VerificationState.CONFLICT

    if source_count == 0:
        return VerificationState.UNSUPPORTED

    if authoritative_count == 0:
        return VerificationState.UNSUPPORTED

    if confidence == ConfidenceLevel.HIGH:
        return VerificationState.VERIFIED

    if confidence == ConfidenceLevel.MEDIUM:
        return VerificationState.PARTIALLY_VERIFIED

    if confidence == ConfidenceLevel.LOW:
        return VerificationState.UNCERTAIN

    return VerificationState.UNSUPPORTED


def _check_update_eligibility(
    confidence: ConfidenceLevel,
    verification_state: VerificationState,
    authority_score: int,
    quality_score: int,
    cross_source_conflicting: int,
    is_current_cycle: bool,
    is_identity_conflict: bool,
    field_name: str,
    extracted_value: Any,
) -> tuple[bool, str]:
    """Check if a field is eligible for automatic update.

    Returns (is_eligible, reason).
    """
    # Hard safety rules
    if is_identity_conflict:
        return False, "Identity conflict detected"

    if cross_source_conflicting > 0:
        return False, "Conflicting sources"

    if authority_score == 0:
        return False, "Non-authoritative source"

    if not is_current_cycle:
        return False, "Evidence not from current cycle"

    if confidence == ConfidenceLevel.LOW:
        return False, "Low confidence"

    if confidence == ConfidenceLevel.CONFLICT:
        return False, "Confidence level is CONFLICT"

    if verification_state == VerificationState.UNSUPPORTED:
        return False, "No authoritative evidence"

    if verification_state == VerificationState.UNCERTAIN:
        return False, "Uncertain verification state"

    if quality_score < 40:
        return False, "Insufficient evidence quality"

    # Check for vague dates that shouldn't be exact
    if "deadline" in field_name.lower() and extracted_value is not None:
        if _is_vague_date(str(extracted_value)):
            return False, "Vague date cannot be used as exact value"

    # Check for semantic deadlines that should be preserved
    if _is_semantic_deadline(extracted_value):
        # Semantic deadlines are OK if explicitly stated
        pass

    return True, "Meets all criteria for automatic update"


def assess_field_confidence(
    scholarship_id: int,
    field_name: str,
    evidence_items: list[EvidenceItem],
    current_cycle: str | None = None,
    is_identity_conflict: bool = False,
) -> FieldConfidenceResult:
    """Assess confidence for a single field across all evidence items.

    This is the main entry point for field-level confidence assessment.

    Args:
        scholarship_id: The scholarship ID
        field_name: The ORM field name being assessed
        evidence_items: List of evidence items for this field
        current_cycle: Optional current cycle string (e.g., "2026-27")
        is_identity_conflict: Whether this field has an identity conflict

    Returns:
        FieldConfidenceResult with confidence, state, and update eligibility
    """
    # Filter to items for this field
    field_items = [item for item in evidence_items if item.field_name == field_name]

    if not field_items:
        return FieldConfidenceResult(
            field_name=field_name,
            value=None,
            confidence=ConfidenceLevel.LOW,
            verification_state=VerificationState.UNSUPPORTED,
            source_count=0,
            authoritative_source_count=0,
            agreeing_source_count=0,
            conflicting_source_count=0,
            reason="No evidence items for this field",
            is_update_candidate=False,
        )

    # Use the first item's value as the primary value
    primary_item = field_items[0]
    value = primary_item.extracted_value

    # Calculate source authority
    max_authority = max(
        _calculate_source_authority(item.source_type) for item in field_items
    )
    authoritative_count = sum(
        1 for item in field_items if is_authoritative_source(item.source_type)
    )

    # Evaluate evidence quality (use best quality item)
    best_quality = 0
    best_quality_reason = ""
    for item in field_items:
        quality, reason = _evaluate_evidence_quality(
            item.evidence_text, field_name, item.extracted_value
        )
        if quality > best_quality:
            best_quality = quality
            best_quality_reason = reason

    # Validate current cycle
    is_current = True
    cycle_reason = "No cycle constraint"
    for item in field_items:
        is_current, cycle_reason = _validate_current_cycle(
            item.evidence_text, current_cycle
        )
        if not is_current:
            break

    # Cross-source comparison
    agreeing, conflicting, cross_source_authority, cross_source_reason = _compare_sources(
        field_items, field_name
    )

    # Get extractor confidence (use highest)
    extractor_confidences = [
        item.confidence for item in field_items if item.confidence is not None
    ]
    best_extractor_confidence = max(
        extractor_confidences,
        key=lambda c: _EXTRACTOR_CONFIDENCE_SCORES.get(c, 0),
        default=None,
    )

    # Determine confidence
    confidence, confidence_reason = _determine_confidence(
        authority_score=max_authority,
        quality_score=best_quality,
        extractor_confidence=best_extractor_confidence,
        cross_source_agreeing=agreeing,
        cross_source_conflicting=conflicting,
        is_current_cycle=is_current,
    )

    # Determine verification state
    verification_state = _determine_verification_state(
        confidence=confidence,
        source_count=len(field_items),
        authoritative_count=authoritative_count,
    )

    # Build evidence references
    evidence_refs = [
        f"{item.source_url}#{item.field_name}" for item in field_items
    ]

    # Check update eligibility
    is_eligible, eligibility_reason = _check_update_eligibility(
        confidence=confidence,
        verification_state=verification_state,
        authority_score=max_authority,
        quality_score=best_quality,
        cross_source_conflicting=conflicting,
        is_current_cycle=is_current,
        is_identity_conflict=is_identity_conflict,
        field_name=field_name,
        extracted_value=value,
    )

    # Build reason string
    reason_parts = [
        f"Authority: {max_authority}",
        f"Quality: {best_quality}",
        f"Sources: {len(field_items)} ({authoritative_count} authoritative)",
        f"Agreement: {agreeing} agree, {conflicting} conflict",
        f"Cycle: {cycle_reason}",
        f"Decision: {confidence_reason}",
        f"Update: {eligibility_reason}",
    ]

    return FieldConfidenceResult(
        field_name=field_name,
        value=value,
        confidence=confidence,
        verification_state=verification_state,
        source_count=len(field_items),
        authoritative_source_count=authoritative_count,
        agreeing_source_count=agreeing,
        conflicting_source_count=conflicting,
        evidence_references=evidence_refs,
        reason=" | ".join(reason_parts),
        is_update_candidate=is_eligible,
        authority_score=max_authority,
        quality_score=best_quality,
        cross_source_score=cross_source_authority,
    )


def assess_confidence(
    scholarship_id: int,
    evidence_items: list[EvidenceItem],
    current_cycle: str | None = None,
    identity_conflict_fields: set[str] | None = None,
) -> VerificationAssessment:
    """Assess confidence for all fields across all evidence items.

    This is the main entry point for the verification confidence engine.

    Args:
        scholarship_id: The scholarship ID
        evidence_items: All evidence items for this scholarship
        current_cycle: Optional current cycle string (e.g., "2026-27")
        identity_conflict_fields: Set of field names with identity conflicts

    Returns:
        VerificationAssessment with results for all fields
    """
    from datetime import datetime, timezone

    # Group evidence by field name
    fields: dict[str, list[EvidenceItem]] = {}
    for item in evidence_items:
        if item.field_name not in fields:
            fields[item.field_name] = []
        fields[item.field_name].append(item)

    # Assess each field independently
    field_results: list[FieldConfidenceResult] = []
    identity_conflicts = identity_conflict_fields or set()

    for field_name, items in sorted(fields.items()):
        result = assess_field_confidence(
            scholarship_id=scholarship_id,
            field_name=field_name,
            evidence_items=items,
            current_cycle=current_cycle,
            is_identity_conflict=field_name in identity_conflicts,
        )
        field_results.append(result)

    return VerificationAssessment(
        scholarship_id=scholarship_id,
        field_results=field_results,
        assessed_at=datetime.now(timezone.utc).isoformat(),
    )


def can_field_auto_update(result: FieldConfidenceResult) -> tuple[bool, str]:
    """Check if a single field result allows automatic update.

    Returns (can_update, reason).
    """
    if result.is_update_candidate:
        return True, "Field meets all criteria for automatic update"
    return False, result.reason
