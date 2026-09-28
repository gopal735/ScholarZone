"""Section-aware extraction from real official scholarship webpages.

The original extractor only recognised strict ``Label: value`` text. A dry run
over 489 official pages showed why that plateaus: real programme pages publish
their facts as prose, bullet lists, tables, definition lists and
heading-delimited sections, so most of the catalogue stayed empty even when the
page plainly stated the information.

This module reads a page the way a person does:

1. split the document into sections at its headings,
2. classify each section by what it is about (eligibility, funding,
   application, documents, language, selection, programme),
3. read facts from within the section using structures that actually carry
   meaning -- definition lists, two-column tables, bullet lists, and prose.

Every extracted value keeps the section heading and the line it came from, so
the result is provably grounded rather than a guess. Values are only returned
when they pass the same quality gate the strict extractor uses, so prose
fragments, negation, navigation text and UI chrome still cannot be stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .scholarship_extractor import _is_usable_detail_value, _normalize_whitespace

# Widget furniture that survives HTML tag stripping. Pages built with an icon
# font rather than <img> decode to bare words - a Humboldt selection section
# was yielding "Icon Notification" into selection_notes, which is UI chrome,
# not a statement the official page made.
_CHROME_WORDS = frozenset(
    {
        "icon", "icons", "notification", "notifications", "chevron", "caret",
        "arrow", "menu", "close", "search", "share", "print", "expand",
        "collapse", "toggle", "tooltip", "breadcrumb", "divider", "spinner",
        "placeholder", "loader", "click", "here", "more", "next", "previous",
        "back", "open", "link", "read", "learn", "show", "see", "view",
    }
)
_CHROME_PREFIX_RE = re.compile(
    r"^\s*(?:icon|icons|notification|notifications|chevron|caret|arrow|menu|"
    r"close|search|share|print|expand|collapse|toggle|tooltip|breadcrumb|"
    r"pagination|spinner|loader|placeholder|divider)\s*(?:[\s:.\-–—]|$)",
    re.IGNORECASE,
)


def _is_ui_chrome(value: str) -> bool:
    """True when a value is widget furniture rather than page content."""
    if not value:
        return True
    if _CHROME_PREFIX_RE.match(value):
        return True
    words = re.findall(r"[A-Za-z]+", value)
    # A value made only of chrome words, in any order, is not a fact.
    return bool(words) and len(words) <= 4 and all(
        w.lower() in _CHROME_WORDS for w in words
    )

# --------------------------------------------------------------------------
# Section classification
# --------------------------------------------------------------------------

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "eligibility": (
        "eligib", "who can apply", "am i eligible", "candidate", "requirements",
        "criteria", "admission", "entry requirement",
    ),
    "funding": (
        "funding", "benefi", "what you get", "financial", "scholarship amount",
        "stipend", "tuition", "allowance", "coverage", "award",
    ),
    "application": (
        "how to apply", "application", "apply", "submission", "deadline",
        "closing date", "opening date", "important dates", "timeline", "portal",
    ),
    "documents": (
        "document", "checklist", "required document", "supporting", "upload",
        "what to submit", "paperwork",
    ),
    "language": (
        "english", "ielts", "toefl", "language requirement", "language test",
    ),
    "selection": (
        "selection", "assessment", "evaluation", "interview", "review process",
        "decision", "notification",
    ),
    "programme": (
        "programme", "program", "course", "study", "duration", "structure",
        "curriculum", "intake", "overview", "about", "introduction",
    ),
    # "renewal" is spelled out so it outranks the equally long "award" in a
    # heading like "Renewal of the award", which otherwise classified as
    # funding and lost its renewal conditions entirely.
    "renewal": ("renewal", "renew", "continuation", "extension", "maintain"),
}

_HEADING_RE = re.compile(r"^(h[1-6])$")


@dataclass
class PageSection:
    """One heading-delimited region of a page, with its text lines."""

    heading: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class ExtractedFact:
    """A single grounded value with the context that proves what it means."""

    field_name: str
    value: str
    evidence: str
    section: str
    structure: str
    confidence: str = "medium"


def split_sections(html: str) -> list[PageSection]:
    """Split a page into heading-delimited sections.

    Text before the first heading is kept under a synthetic "page" heading so
    an intro paragraph is not lost.
    """
    try:
        from bs4 import BeautifulSoup
    except Exception:  # noqa: BLE001
        return []

    try:
        soup = BeautifulSoup(html[:600_000], "html.parser")
    except Exception:  # noqa: BLE001
        return []

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "form"]):
        tag.decompose()

    sections: list[PageSection] = []
    current = PageSection(heading="page", lines=[])

    def add_text(value: str) -> None:
        text = _normalize_whitespace(value)
        if not text or len(text) > 2000:
            return
        if len(text) < 3 and not text.isdigit():
            return
        current.lines.append(text)

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "dt", "dd"]):
        try:
            if _HEADING_RE.match(element.name or ""):
                if current.lines or current.heading != "page":
                    sections.append(current)
                current = PageSection(heading=element.get_text(" ", strip=True)[:160])
                continue
            add_text(element.get_text(" ", strip=True))
        except Exception:  # noqa: BLE001 - malformed markup must not abort a page
            continue

    if current.lines:
        sections.append(current)
    return sections


def classify_section(heading: str, sample_lines: list[str] | None = None) -> str | None:
    """Map a heading (optionally reinforced by its first lines) to a topic.

    A heading like "English Requirements" is about language even though the
    word "requirement" also appears in the eligibility topic, so the
    most specific keyword wins by length and language-specific phrasing is
    scored explicitly.
    """
    haystack = (heading or "").lower()
    if not haystack and sample_lines:
        haystack = " ".join(sample_lines[:2]).lower()
    if not haystack:
        return None

    # An explicit language-test mention resolves the common ambiguity where a
    # language heading also contains "requirement(s)".
    if any(token in haystack for token in ("ielts", "toefl", "english", "pte", "language")):
        return "language"

    best: tuple[int, str] | None = None
    for topic, keywords in SECTION_KEYWORDS.items():
        if topic == "language":
            continue
        for kw in keywords:
            if kw in haystack:
                if best is None or len(kw) > best[0]:
                    best = (len(kw), topic)
    return best[1] if best else None


# --------------------------------------------------------------------------
# Structure readers
# --------------------------------------------------------------------------

# Two-column table rows and definition lists are the strongest structured
# signals a page offers, so they are read first and labelled explicitly.
_TABLE_LABEL_RE = re.compile(r"^([^:]{2,60}):\s*(.+)$")
_PROSE_SENTENCE_RE = re.compile(r"^(.{25,240}?)\.$")


def _from_labeled_lines(section: PageSection) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in section.lines:
        m = _TABLE_LABEL_RE.match(line)
        if m:
            label, value = m.group(1).strip(), m.group(2).strip()
            if _is_usable_detail_value(value):
                out.append((label, value))
    return out


def _sentences_from_prose(section: PageSection) -> list[str]:
    out: list[str] = []
    for line in section.lines:
        if not line.endswith("."):
            continue
        for raw in re.split(r"(?<=[.!?])\s+", line):
            sentence = raw.strip()
            if 30 <= len(sentence) <= 400 and _is_usable_detail_value(sentence):
                out.append(sentence)
    return out


# --------------------------------------------------------------------------
# Field-specific rules
# --------------------------------------------------------------------------

# (target field, section topics that may produce it, value keywords)
FIELD_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("english_requirement", ("language",), (
        "ielts", "toefl", "english", "language", "pte", "gre score",
    )),
    ("eligibility", ("eligibility",), (
        "eligib", "citizen", "nationality", "nationals", "resident", "degree",
        "bachelor", "master", "gpa", "grade", "age", "experience", "citizenship",
        "must", "open to", "limited to",
    )),
    ("requirements", ("eligibility",), (
        "submit", "provide", "require", "upload", "certificate", "transcript",
        "passport", "curriculum", "cv", "reference", "letter", "proposal",
        "portfolio", "essay", "diploma", "testimonial",
    )),
    # A funding section states what the award PAYS FOR. That is the coverage
    # contract, so funding-section lines go to `coverage` and not to `benefits`.
    # An earlier revision mapped the same lines into both, producing identical
    # lists in two columns that mean different things.
    ("coverage", ("funding",), (
        "tuition", "fee", "stipend", "allowance", "insurance", "accommodation",
        "housing", "travel", "airfare", "flight", "visa", "research", "books",
        "health", "settlement", "living", "full cost", "waiver", "salary",
        "pension", "contribution",
    )),
    # `benefits` is reserved for the distinct non-cost advantages an award adds.
    ("benefits", ("funding",), (
        "discount", "free membership", "networking", "mentoring", "mentorship",
        "access to", "priority", "additional support", "career",
    )),
    ("application_period", ("application",), (
        "deadline", "closing", "opens", "opening", "apply between", "by ",
        "until", "period", "cycle", "intake", "round",
    )),
    ("application_method", ("application",), (
        "apply", "application form", "online", "portal", "submit", "email",
        "post", "download", "register", "procedure", "steps", "process",
    )),
    ("selection_notes", ("selection",), (
        "interview", "assessment", "evaluation", "criteria", "shortlist",
        "committee", "notification", "decision", "review", "score", "ranking",
    )),
    ("duration", ("programme",), (
        "duration", "length", "months", "years", "semester", "one year",
        "two year", "full-time", "part-time",
    )),
    ("best_fit", ("programme",), (
        "aimed at", "designed for", "intended for", "ideal for", "suitable for",
        "target", "seeking", "aspiring",
    )),
    # A section that lists what to send is a documents list, not an
    # eligibility or generic-requirements list. Routing it to 'requirements'
    # left the documents column empty on 416 records whose official page
    # listed every required document by name.
    #
    # Most providers do not give documents their own heading; they put them
    # inside "How to apply". The application topic is therefore included, but
    # only when the line actually names a document, so ordinary application
    # prose is not misfiled as a document requirement.
    ("documents", ("documents", "application"), (
        "transcript", "certificate", "passport", "id card", "identity",
        "curriculum vitae", "cv", "motivation", "recommendation", "reference",
        "proposal", "portfolio", "essay", "statement", "diploma", "transcripts",
        "academic records", "language test", "language certificate",
    )),
    # The overview of a programme page is its description. Official pages
    # routinely open with "The X Scholarship is ..." under a heading like
    # About / Programme / Overview, and that sentence is the authoritative
    # description of what the award is.
    ("description", ("programme", "eligibility", "funding", "selection"), (
        "scholarship", "fellowship", "programme", "program", "award", "grant",
        "aims to", "designed to", "intended to", "supports", "offers", "provides",
        "open to", "is a ", "is an ", "purpose",
    )),
    ("renewal_conditions", ("renewal",), (
        "renew", "extend", "maintain", "continuation", "further year",
    )),
    # Programme classification. Only stated explicitly on the page - the
    # scholarship calling itself a fellowship, exchange or doctoral award is
    # the official's own classification. Degree level is deliberately NOT a
    # trigger: inferring "doctoral" from a Master's record would fabricate it.
    ("program_type", ("programme",), (
        "scholarship", "fellowship", "exchange", "traineeship", "studentship",
        "bursary", "grant", "award", "studentship", "postdoctoral", "post-doctoral",
        "doctoral", "phd", "doctorate", "master's", "masters", "mba", "bachelor",
        "undergraduate", "graduate", "research studentship", "visiting",
    )),
)

# Label patterns that map a section heading to a field with a value on the
# same line, used for the classic "Stipend: X" row inside any section.
_LABEL_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "stipend": ("coverage", "benefits"),
    "living stipend": ("coverage", "benefits"),
    "tuition": ("coverage",),
    "tuition fee": ("coverage",),
    "tuition waiver": ("coverage",),
    "accommodation": ("coverage", "benefits"),
    "housing": ("coverage", "benefits"),
    "travel": ("coverage", "benefits"),
    "airfare": ("coverage", "benefits"),
    "insurance": ("coverage", "benefits"),
    "visa": ("coverage", "benefits"),
    "award amount": ("benefits",),
    "amount": ("benefits",),
    "duration": ("duration",),
    "study mode": ("programme",),
    "intake": ("application_period",),
    "application fee": ("application_method",),
    "deadline": ("application_period",),
    "closing date": ("application_period",),
    "opening date": ("application_period",),
    "eligible fields": ("eligibility",),
    "eligible nationalities": ("eligibility",),
    "nationality": ("eligibility",),
    "age limit": ("eligibility",),
    "minimum gpa": ("eligibility", "requirements"),
    "ielts": ("english_requirement",),
    "toefl": ("english_requirement",),
}


def extract_sections(html: str) -> list[ExtractedFact]:
    """Extract grounded facts from a page's heading-delimited sections."""
    sections = split_sections(html)
    if not sections:
        return []

    facts: list[ExtractedFact] = []

    # 1. Label/value rows anywhere, using the explicit label map.
    for section in sections:
        for label, value in _from_labeled_lines(section):
            key = label.strip().lower().rstrip(":")
            targets = _LABEL_FIELD_MAP.get(key)
            if targets:
                facts.append(
                    ExtractedFact(
                        field_name=targets[0],
                        value=value,
                        evidence=f"{label}: {value}",
                        section=section.heading,
                        structure="label_value",
                        confidence="high" if len(label) > 3 else "medium",
                    )
                )

    # 2. Section-scoped prose and bullets.
    #
    # More than one fact per field per section is worth keeping: a funding
    # section usually states the stipend, the tuition treatment and the travel
    # allowance as separate lines, and an earlier revision stopped at the first
    # match and silently discarded the rest.
    # Three facts per section per field was low enough to truncate real
    # document lists (a four-item list silently lost its fourth item) and
    # funding sections, which commonly enumerate more than three items.
    MAX_PER_FIELD_PER_SECTION = 6

    for section in sections:
        topic = classify_section(section.heading, section.lines[:2])
        if not topic:
            continue
        for field_name, topics, keywords in FIELD_RULES:
            if topic not in topics:
                continue
            taken = 0
            for line in section.lines:
                if taken >= MAX_PER_FIELD_PER_SECTION:
                    break
                lowered = line.lower()
                if not any(kw in lowered for kw in keywords):
                    continue
                if not _is_usable_detail_value(line):
                    continue
                if _is_ui_chrome(line):
                    continue
                # A labelled line was already captured with higher confidence.
                if _TABLE_LABEL_RE.match(line):
                    continue
                structure = "bullet" if len(line) < 200 else "prose"
                facts.append(
                    ExtractedFact(
                        field_name=field_name,
                        value=line,
                        evidence=f"[{section.heading}] {line}",
                        section=section.heading,
                        structure=structure,
                    )
                )
                taken += 1

    return facts


# --------------------------------------------------------------------------
# JSON-LD
# --------------------------------------------------------------------------

_JSONLD_USEFUL = ("name", "description", "startDate", "endDate", "eligibility")


def extract_jsonld(html: str) -> list[ExtractedFact]:
    """Read facts from schema.org JSON-LD blocks when a page publishes them."""
    try:
        from bs4 import BeautifulSoup
    except Exception:  # noqa: BLE001
        return []

    facts: list[ExtractedFact] = []
    try:
        soup = BeautifulSoup(html[:600_000], "html.parser")
    except Exception:  # noqa: BLE001
        return facts

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            import json

            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        for node in _iter_jsonld(data):
            if not isinstance(node, dict):
                continue
            desc = node.get("description")
            if isinstance(desc, str) and _is_usable_detail_value(desc):
                facts.append(
                    ExtractedFact(
                        field_name="description",
                        value=desc[:600],
                        evidence=f"json-ld description: {desc[:180]}",
                        section="json-ld",
                        structure="json_ld",
                        confidence="high",
                    )
                )
    return facts


def _iter_jsonld(data: Any):
    if isinstance(data, list):
        for item in data:
            yield from _iter_jsonld(item)
    elif isinstance(data, dict):
        yield data
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data:
                yield from _iter_jsonld(data[key])


def extract_all(html: str) -> list[ExtractedFact]:
    """Section extraction plus JSON-LD, de-duplicated by field and value."""
    facts = extract_jsonld(html) + extract_sections(html)
    seen: set[tuple[str, str]] = set()
    out: list[ExtractedFact] = []
    for fact in facts:
        key = (fact.field_name, fact.value.strip().lower()[:160])
        if key in seen:
            continue
        seen.add(key)
        out.append(fact)
    return out
