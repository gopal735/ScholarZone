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
    program_type: str | None = None
    study_mode: str | None = None
    intake: str | None = None

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
        _store(fields, confidence, "provider", provider_match.group(1), ExtractionConfidence.MEDIUM)

    degree_match = re.search(r'(?:degree|level)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if degree_match:
        _store(fields, confidence, "degree_level", degree_match.group(1), ExtractionConfidence.MEDIUM)

    # "Award" also appears in interface chrome ("Select award type",
    # "Award type:"). A mandatory separator keeps the label/value reading while
    # dropping both forms, because neither is followed directly by a separator.
    award_match = re.search(
        r'(?:award amount|total award|value|amount|award)\s*[:\-]\s*([^\n]{2,180})',
        text,
        re.IGNORECASE,
    )
    if award_match:
        _store(fields, confidence, "award_amount", award_match.group(1), ExtractionConfidence.MEDIUM)

    tuition_match = re.search(r'(?:full[\s-]?tuition|tuition)[:\s]+([^\n]{2,200})', text, re.IGNORECASE)
    if tuition_match:
        _store(fields, confidence, "tuition_coverage", tuition_match.group(1), ExtractionConfidence.MEDIUM)

    # "Living stipend of $15,000" is the common phrasing; consume the connective
    # so the captured value is the amount rather than the fragment "of $15,000".
    stipend_match = re.search(
        r'(?:living\s+stipend|stipend)(?:\s+of)?[:\s]+([^\n]{2,200})', text, re.IGNORECASE
    )
    if stipend_match:
        _store(fields, confidence, "living_stipend", stipend_match.group(1), ExtractionConfidence.MEDIUM)

    duration_match = re.search(r'(?:duration|length)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if duration_match:
        _store(fields, confidence, "duration", duration_match.group(1), ExtractionConfidence.MEDIUM)

    gpa_match = re.search(r'(?:gpa|grade\s+point\s+average)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if gpa_match:
        _store(fields, confidence, "gpa_requirement", gpa_match.group(1), ExtractionConfidence.MEDIUM)

    language_match = re.search(r'(?:language|english|ielts|toefl)[:\s]+([^\n]+)', text, re.IGNORECASE)
    if language_match:
        _store(fields, confidence, "language_requirement", language_match.group(1), ExtractionConfidence.MEDIUM)

    # Two real page shapes exist for eligibility:
    #   1. "Eligibility: <criteria>"   (label and value on one line)
    #   2. "Eligibility Criteria" as a heading, criteria on the following line
    # A mandatory separator is required for (1) because a dry run captured
    # "requirements, attracting candidates that show excellent academic
    # performance" -- a mid-sentence fragment, not a fact.
    eligibility_match = re.search(
        r'(?:eligib(?:ility)\s+criteria|eligibility\s+criteria|eligibility|requirements?)\s*[:\-]\s*([^\n]{2,200})',
        text,
        re.IGNORECASE,
    )
    if eligibility_match:
        _store(fields, confidence, "eligibility", eligibility_match.group(1), ExtractionConfidence.MEDIUM)
    else:
        heading_value = _value_after_label_heading(
            text,
            r'(?:eligib(?:ility)\s+criteria|eligibility\s+criteria|admission requirements?)\s*:?\s*$',
        )
        if heading_value:
            _store(fields, confidence, "eligibility", heading_value, ExtractionConfidence.MEDIUM)

    fields, confidence = _extract_labelled_detail(text, fields, confidence)

    return fields, confidence, notes


# Label-anchored detail patterns for enrichment fields.
#
# SAFETY RULES (learned from a real dry run over 489 official pages):
#
# 1. The separator is MANDATORY (`:` or `-`). An earlier revision allowed it to
#    be optional, which made patterns match label words inside running prose and
#    produced fragments like "of Excellence at KAIST".
# 2. The label is anchored to the start of a line. The text extractor emits one
#    DOM text node per line, so line-start is a reliable "this is a field label"
#    signal.
# 3. The value is bounded and structurally validated by _is_usable_detail_value.
#    Prose, negations, and unbalanced fragments are rejected.
#
# Consequence: pages without structured "Label: value" content simply do not
# enrich. That is the intended, honest behaviour.
_LABELLED_DETAIL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("eligible_nationalities", r"^(?:Eligible nationalities?|Nationality)\s*[:\-]\s*([^\n]{2,180})"),
    ("eligible_fields", r"^(?:Fields? of study|Study (?:fields|areas|subjects)|Eligible fields?|Disciplines?)\s*[:\-]\s*([^\n]{2,180})"),
    ("academic_requirements", r"^(?:Academic (?:and |entry )?requirements?|Educational requirements?|Entry requirements?|Qualifications?)\s*[:\-]\s*([^\n]{2,180})"),
    ("test_requirements", r"^(?:IELTS|TOEFL|GRE|GMAT|SAT|ACT|English (?:language )?test)\s*(?:score|minimum|min\.)?\s*[:\-]\s*([^\n]{2,120})"),
    ("housing", r"^(?:Housing|Accommodation|Dormitor(?:y|ies)|Room and board|Residence)\s*[:\-]\s*([^\n]{2,180})"),
    ("travel", r"^(?:Travel (?:allowance|grant|support|benefits?)?|Airfare|Air ticket|Flights?)\s*[:\-]\s*([^\n]{2,180})"),
    ("insurance", r"^(?:Health insurance|Insurance|Medical (?:insurance|cover))\s*[:\-]\s*([^\n]{2,180})"),
    ("renewal_conditions", r"^(?:Renewal|Renewable|Continuation)\s*[:\-]\s*([^\n]{2,180})"),
    ("application_method", r"^(?:How to apply|Application process|Application steps?|Applying|Apply through)\s*[:\-]\s*([^\n]{2,180})"),
    ("program_type", r"^(?:Programme? type|Program type|Type of (?:programme|program|award))\s*[:\-]\s*([^\n]{2,120})"),
    ("study_mode", r"^(?:Study mode|Mode of study|Delivery)\s*[:\-]\s*([^\n]{2,120})"),
    ("intake", r"^(?:Intake|Application (?:intake|round)s?|Start dates?)\s*[:\-]\s*([^\n]{2,120})"),
)

# Values that state a NEGATIVE must never be recorded as a positive benefit or
# coverage item. "Tuition fees are not covered" stored under "coverage" actively
# misinforms the reader, so it is rejected outright.
_NEGATION_RE = re.compile(
    r"\b(?:not\s+covered|are\s+not|is\s+not|isn't|aren't|does\s+not|do\s+not|no\s+support|"
    r"not\s+included|excluded|not\s+available|not\s+offered|unavailable|none)\b",
    re.IGNORECASE,
)

# Bare noun labels that appear where a *value* is expected. A dry run over 489
# official pages produced coverage entries of literally "fees" and benefits
# entries of "Select award type" / "Eligibility", which are page chrome rather
# than facts.
_GENERIC_VALUES: frozenset[str] = frozenset({
    "fees", "fee", "tuition", "tuition fees", "tuition waiver", "stipend",
    "stipends", "amount", "award", "awards", "scholarship", "scholarships",
    "benefits", "benefit", "coverage", "eligibility", "requirements",
    "requirement", "documents", "document", "apply", "application",
    "assistance", "support", "funding", "grant", "award type", "amount type",
    "level", "type", "duration", "period", "deadline", "language", "level of study",
    "course", "program", "programme", "n/a", "tbc", "see below", "see website",
    "more", "read more", "details", "click here", "apply now", "select award type",
    "select", "choose", "enter", "submit", "view", "next", "back", "home",
    # Form labels that appear in the value position on real application pages.
    "open date", "close date", "start date", "end date", "scholarship type",
    "application type", "study level", "number of scholarships awarded",
    "number of awards", "award type", "amount type", "course type",
    "scholarship name", "programme name", "program name", "results",
    "search", "filter", "sort", "sort by", "showing", "no results",
    "terms and conditions", "terms & conditions", "terms and conditions apply",
    "eligibility criteria", "admission requirements", "how to apply",
    "application procedure", "important dates", "key dates", "overview",
})

# The text extractor wraps anchor text in these markers so links can be
# identified later. They must never survive into a stored fact.
_LINK_MARKER_RE = re.compile(r"\[/?LINK\]", re.IGNORECASE)

# Interface verbs that indicate navigation chrome rather than a fact.
_UI_VERB_RE = re.compile(
    r"^\s*(?:select|choose|click|view|see|read|learn|explore|discover|apply|submit|"
    r"register|download|print|share|save|browse|search|find|contact|check|get)\b",
    re.IGNORECASE,
)

# A financial value is only informative if it states an amount or an explicit
# coverage outcome. "fees" and "tuition" state neither.
_CURRENCY_RE = re.compile(r"[€$£¥₹₽\d]|\b(?:EUR|USD|GBP|CHF|JPY|CAD|AUD|NOK|SEK|DKK|INR|euros?|dollars?|pounds?|yen|euro)\b", re.IGNORECASE)
_COVERAGE_VERB_RE = re.compile(
    r"\b(?:covered?|covers|waived?|funded|provided|included|granted|paid|offered|"
    r"awarded|receives?|entitled|receipt|reimburse[ds]?|reimbursed)\b",
    re.IGNORECASE,
)

# A captured value that begins with one of these is almost certainly a
# mid-sentence continuation rather than the value belonging to the label.
_FRAGMENT_STARTERS = frozenset(
    {
        "of", "and", "or", "for", "to", "in", "on", "at", "the", "a", "an",
        "which", "that", "with", "from", "by", "as", "is", "are", "was", "were",
        "be", "been", "it", "its", "this", "these", "those", "if", "when",
        "per", "such", "including", "except", "however", "but", "so", "then",
    }
)


def _is_usable_detail_value(value: str, *, financial: bool = False) -> bool:
    """Reject prose, fragments, negations, chrome, and placeholders.

    ``financial=True`` additionally requires the value to state an amount or an
    explicit coverage outcome, which is what stopped bare "fees" from being
    recorded as a coverage item.
    """
    text = value.strip()
    if len(text) < 2 or len(text) > 200:
        return False

    text = _LINK_MARKER_RE.sub("", text).strip()
    if len(text) < 2:
        return False

    lowered = text.lower().rstrip(".")
    if lowered in _GENERIC_VALUES:
        return False

    if _UI_VERB_RE.match(text):
        return False

    # Balanced delimiters: unbalanced means we cut mid-clause.
    if text.count("(") != text.count(")"):
        return False
    if text.count("[") != text.count("]"):
        return False

    # Strip leading punctuation before the fragment test: "(Including ..." is
    # just as much a mid-sentence fragment as "of Excellence ...".
    probe = text.lstrip(" \t([{\"'*-").lower()
    first_word = re.split(r"[\s,;:]+", probe, maxsplit=1)[0]
    if first_word in _FRAGMENT_STARTERS:
        return False

    # A value ending in an unbalanced conjunction is a truncated capture.
    if lowered.endswith((",", ";", "and", "or", "of", "the", "a", "an", "to", "in")):
        return False

    if financial and not (_CURRENCY_RE.search(text) or _COVERAGE_VERB_RE.search(text)):
        return False

    return True


# Fields that describe what an award PROVIDES. A negated statement in one of
# these is not a benefit and must never be recorded as one.
_POSITIVE_FIELDS = frozenset(
    {"award_amount", "tuition_coverage", "living_stipend", "housing", "travel", "insurance"}
)


def _value_after_label_heading(text: str, heading_pattern: str) -> str | None:
    """Return the first substantive line following a label heading.

    Handles the common page shape where a section is introduced by a heading
    ("Eligibility Criteria") and the content begins on the following line.
    Returns None when the heading is absent or nothing usable follows it.
    """
    lines = text.split("\n")
    rx = re.compile(heading_pattern, re.IGNORECASE)
    for index, line in enumerate(lines):
        if not rx.search(line.strip()):
            continue
        for candidate in lines[index + 1 : index + 4]:
            cleaned = _normalize_whitespace(candidate)
            if not cleaned:
                continue
            if not _is_usable_detail_value(cleaned):
                # Skip over chrome but keep scanning a little further.
                continue
            return cleaned
        return None
    return None


def _store(
    fields: dict[str, object],
    confidence: dict[str, str],
    name: str,
    value: str | None,
    conf: str,
) -> None:
    """Validate a captured value and store it only if it survives review.

    Applying this to the ORIGINAL loose patterns as well as the new anchored
    ones is deliberate: a real dry run showed `tuition[:\\s]+(.+)` capturing
    "fees are not covered by the programme", which would have been stored as
    coverage and actively misled the reader.
    """
    if not value:
        return
    candidate = _normalize_whitespace(value)
    if not candidate:
        return
    is_financial = name in _POSITIVE_FIELDS
    if not _is_usable_detail_value(candidate, financial=is_financial):
        return
    if is_financial and _NEGATION_RE.search(candidate):
        return
    fields[name] = candidate
    confidence[name] = conf


def _extract_labelled_detail(
    text: str,
    fields: dict[str, object],
    confidence: dict[str, str],
) -> tuple[dict[str, object], dict[str, str]]:
    """Populate enrichment fields from strict "Label: value" lines.

    A field already populated by a higher-specificity pattern above is never
    overwritten here.
    """
    for field_name, pattern in _LABELLED_DETAIL_PATTERNS:
        if field_name in fields:
            continue
        for line in text.split("\n"):
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if not match:
                continue
            candidate = _normalize_whitespace(match.group(1))
            if not candidate:
                continue
            is_financial = field_name in ("coverage", "benefits", "housing", "travel", "insurance")
            if not _is_usable_detail_value(candidate, financial=is_financial):
                continue
            if is_financial and _NEGATION_RE.search(candidate):
                continue
            fields[field_name] = candidate
            confidence[field_name] = ExtractionConfidence.MEDIUM
            break
    return fields, confidence


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
