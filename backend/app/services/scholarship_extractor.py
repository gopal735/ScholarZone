"""Deterministic HTML extraction for official scholarship sources."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field


class ExtractionConfidence:
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScholarshipExtractionResult(BaseModel):
    """Structured extraction from an official scholarship page."""

    model_config = ConfigDict(frozen=True)

    scholarship_name: str | None = None
    provider: str | None = None
    degree_level: str | None = None
    eligibility: str | None = None
    eligible_nationalities: str | None = None
    eligible_fields: str | None = None
    academic_requirements: str | None = None
    gpa_requirement: str | None = None
    language_requirement: str | None = None
    test_requirements: str | None = None
    award_amount: str | None = None
    tuition_coverage: str | None = None
    living_stipend: str | None = None
    housing: str | None = None
    travel: str | None = None
    insurance: str | None = None
    duration: str | None = None
    renewal_conditions: str | None = None
    application_method: str | None = None
    application_url: str | None = None
    deadline: str | None = None
    deadline_type: str | None = None
    scholarship_cycle: str | None = None
    status: str | None = None

    confidence: dict[str, str] = Field(default_factory=dict)
    extraction_notes: list[str] = Field(default_factory=list)


_IGNORED_TAGS = frozenset({"script", "style", "noscript", "nav", "footer", "header"})
_WHITESPACE_RE = re.compile(r"\s+")
_APPLY_LINK_RE = re.compile(
    r"(apply|application|apply now|scholarship application|submit application)",
    re.IGNORECASE,
)

_DEADLINE_PATTERNS = [
    (re.compile(r"deadline[:\s]+(.+?)(?:\n|$)", re.IGNORECASE), ExtractionConfidence.HIGH),
    (re.compile(r"applications?\s+close[:\s]+(.+?)(?:\n|$)", re.IGNORECASE), ExtractionConfidence.HIGH),
    (re.compile(r"apply\s+by[:\s]+(.+?)(?:\n|$)", re.IGNORECASE), ExtractionConfidence.HIGH),
    (re.compile(r"applications?\s+are\s+due[:\s]+(.+?)(?:\n|$)", re.IGNORECASE), ExtractionConfidence.HIGH),
    (re.compile(r"closing\s+date[:\s]+(.+?)(?:\n|$)", re.IGNORECASE), ExtractionConfidence.HIGH),
    (re.compile(r"due\s+date[:\s]+(.+?)(?:\n|$)", re.IGNORECASE), ExtractionConfidence.HIGH),
]

_ROLLING_RE = re.compile(r"\brolling\b", re.IGNORECASE)
_VARIES_RE = re.compile(r"\bvaries\b", re.IGNORECASE)
_NOT_ANNOUNCED_RE = re.compile(r"\bnot\s+announced\b", re.IGNORECASE)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        self._current_tag = tag
        if tag in _IGNORED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in _IGNORED_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        self._current_tag = None

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._current_tag == "a":
            self._parts.append(f"[LINK]{text}[/LINK]")
        else:
            self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def _normalize_text(text: str) -> str:
    text = unescape(text)
    lines = []
    for line in text.splitlines():
        line = _WHITESPACE_RE.sub(" ", line)
        lines.append(line.strip())
    return "\n".join(lines)


def _normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_url(url: str, base_url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(base_url, url)


def _is_noise_link(text: str) -> bool:
    noise = {"skip to main content", "skip navigation", "home", "contact", "privacy", "terms"}
    return text.lower() in noise


def _clean_deadline(text: str) -> str | None:
    text = _normalize_whitespace(text)
    if not text:
        return None
    if _ROLLING_RE.search(text):
        return "rolling"
    if _VARIES_RE.search(text):
        return "varies"
    if _NOT_ANNOUNCED_RE.search(text):
        return "not announced"
    return text


def _extract_title(html: str) -> str | None:
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        title = re.sub(r"<[^>]+>", "", match.group(1))
        title = _normalize_whitespace(title)
        return title if title else None
    return None


def _extract_deadline(text: str) -> tuple[str | None, str | None, str]:
    for pattern, confidence in _DEADLINE_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).strip()
            cleaned = _clean_deadline(raw)
            if cleaned:
                return cleaned, "application_deadline", confidence
    return None, None, ExtractionConfidence.LOW


def _extract_application_links(html: str, base_url: str) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
        href = match.group(1).strip()
        text = re.sub(r"<[^>]+>", "", match.group(2))
        text = _normalize_whitespace(text)
        if not text or _is_noise_link(text):
            continue
        if _APPLY_LINK_RE.search(text):
            links.append(_normalize_url(href, base_url))
    return links


def _extract_fields(text: str, title: str | None) -> tuple[dict[str, object], dict[str, str], list[str]]:
    fields: dict[str, object] = {}
    confidence: dict[str, str] = {}
    notes: list[str] = []

    if title:
        fields["scholarship_name"] = title
        confidence["scholarship_name"] = ExtractionConfidence.HIGH

    provider_match = re.search(r"(?:offered?\s+by|provided?\s+by|funded?\s+by|sponsored?\s+by)[:\s]+([^\n]+)", text, re.IGNORECASE)
    if provider_match:
        candidate = _normalize_whitespace(provider_match.group(1))
        if candidate:
            fields["provider"] = candidate
            confidence["provider"] = ExtractionConfidence.MEDIUM

    degree_match = re.search(r'(?:degree|level)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if degree_match:
        candidate = _normalize_whitespace(degree_match.group(1))
        if candidate:
            fields["degree_level"] = candidate
            confidence["degree_level"] = ExtractionConfidence.MEDIUM

    award_match = re.search(r'(?:award|amount|value)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if award_match:
        candidate = _normalize_whitespace(award_match.group(1))
        if candidate:
            fields["award_amount"] = candidate
            confidence["award_amount"] = ExtractionConfidence.MEDIUM

    tuition_match = re.search(r'(?:full[\s-]?tuition|tuition)[:\s]+(.+)', text, re.IGNORECASE)
    if tuition_match:
        candidate = _normalize_whitespace(tuition_match.group(1))
        if candidate:
            fields["tuition_coverage"] = candidate
            confidence["tuition_coverage"] = ExtractionConfidence.MEDIUM

    stipend_match = re.search(r'(?:living\s+stipend|stipend)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if stipend_match:
        candidate = _normalize_whitespace(stipend_match.group(1))
        if candidate:
            fields["living_stipend"] = candidate
            confidence["living_stipend"] = ExtractionConfidence.MEDIUM
    if tuition_match:
        candidate = _normalize_whitespace(tuition_match.group(1))
        if candidate:
            fields["tuition_coverage"] = candidate
            confidence["tuition_coverage"] = ExtractionConfidence.MEDIUM

    duration_match = re.search(r'(?:duration|length)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if duration_match:
        candidate = _normalize_whitespace(duration_match.group(1))
        if candidate:
            fields["duration"] = candidate
            confidence["duration"] = ExtractionConfidence.MEDIUM

    gpa_match = re.search(r'(?:gpa|grade\s+point\s+average)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if gpa_match:
        candidate = _normalize_whitespace(gpa_match.group(1))
        if candidate:
            fields["gpa_requirement"] = candidate
            confidence["gpa_requirement"] = ExtractionConfidence.MEDIUM

    language_match = re.search(r'(?:language|english|ielts|toefl)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if language_match:
        candidate = _normalize_whitespace(language_match.group(1))
        if candidate:
            fields["language_requirement"] = candidate
            confidence["language_requirement"] = ExtractionConfidence.MEDIUM

    eligibility_match = re.search(r'(?:eligib(?:ility)\s+criteria|criteria|eligib(?:ility)|requirements?)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if eligibility_match:
        candidate = _normalize_whitespace(eligibility_match.group(1))
        if candidate:
            fields["eligibility"] = candidate
            confidence["eligibility"] = ExtractionConfidence.MEDIUM

    return fields, confidence, notes


def extract_scholarship_information(html_content: str, base_url: str = "") -> ScholarshipExtractionResult:
    """Extract structured scholarship information from fetched HTML.

    Never raises. Missing or ambiguous information remains None.
    """
    if not html_content or not html_content.strip():
        return ScholarshipExtractionResult(
            extraction_notes=["Empty HTML content provided"],
        )

    try:
        title = _extract_title(html_content)
        extractor = _TextExtractor()
        extractor.feed(html_content)
        text = _normalize_text(extractor.get_text())
    except Exception:
        return ScholarshipExtractionResult(
            extraction_notes=["Failed to parse HTML"],
        )

    fields, confidence, notes = _extract_fields(text, title)
    deadline, deadline_type, deadline_confidence = _extract_deadline(text)
    if deadline:
        fields["deadline"] = deadline
        confidence["deadline"] = deadline_confidence
    if deadline_type:
        fields["deadline_type"] = deadline_type
        confidence["deadline_type"] = deadline_confidence

    app_links = _extract_application_links(html_content, base_url)
    if app_links:
        fields["application_url"] = app_links[0]
        confidence["application_url"] = ExtractionConfidence.HIGH
        if len(app_links) > 1:
            notes.append(f"Multiple application links found; using first: {app_links[0]}")

    return ScholarshipExtractionResult(
        scholarship_name=fields.get("scholarship_name"),
        provider=fields.get("provider"),
        degree_level=fields.get("degree_level"),
        eligibility=fields.get("eligibility"),
        eligible_nationalities=fields.get("eligible_nationalities"),
        eligible_fields=fields.get("eligible_fields"),
        academic_requirements=fields.get("academic_requirements"),
        gpa_requirement=fields.get("gpa_requirement"),
        language_requirement=fields.get("language_requirement"),
        test_requirements=fields.get("test_requirements"),
        award_amount=fields.get("award_amount"),
        tuition_coverage=fields.get("tuition_coverage"),
        living_stipend=fields.get("living_stipend"),
        housing=fields.get("housing"),
        travel=fields.get("travel"),
        insurance=fields.get("insurance"),
        duration=fields.get("duration"),
        renewal_conditions=fields.get("renewal_conditions"),
        application_method=fields.get("application_method"),
        application_url=fields.get("application_url"),
        deadline=fields.get("deadline"),
        deadline_type=fields.get("deadline_type"),
        scholarship_cycle=fields.get("scholarship_cycle"),
        status=fields.get("status"),
        confidence=confidence,
        extraction_notes=notes,
    )
