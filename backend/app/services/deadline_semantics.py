"""Deadline semantics: rolling, annual and recurring deadlines.

An exact calendar date is only one of the ways a provider states a deadline.
Government programmes frequently publish "applications are accepted on a
rolling basis", "open year-round", or "deadline: 30 November annually". The
extractor cannot turn those into a date, and should not try: inventing a year
for a recurring deadline produces a date that is wrong the moment it is
written, and `deadline_date` then drives a status badge and a deadline sort.

So those cases get an explicit semantic classification instead. A
`recurring` or `rolling` deadline is now *representable* rather than
indistinguishable from "the provider never said", which is what left the field
blank in the first place. The provider's own wording is preserved verbatim in
`deadline_display` so nothing is lost.
"""

from __future__ import annotations

import re
from enum import StrEnum


class DeadlineKind(StrEnum):
    EXACT = "exact"
    ROLLING = "rolling"
    ANNUAL = "annual"
    MONTH = "month"
    UNKNOWN = "unknown"


#: Phrases meaning the programme accepts applications continuously. The page
#: genuinely publishes a deadline policy; it just has no fixed date.
_ROLLING_PATTERNS = (
    r"\brolling\s+basis\b",
    r"\brolling\s+admission",
    r"\brolling\s+deadline",
    r"\bopen\s+year[\s-]?round\b",
    r"\byear[\s-]?round\b",
    r"all\s+year\s+round",
    r"throughout\s+the\s+year",
    r"any\s+time\s+(of|during)\s+the\s+year",
    r"applications?\s+(are\s+)?(accepted|received)\s+at\s+any\s+time",
    r"no\s+(fixed\s+)?deadline",
    r"continuous\s+application",
    r"open\s+until\s+(filled|places\s+are\s+filled)",
    r"first\s+come,\s*first\s+served",
)

#: Phrases meaning a fixed day repeats each cycle.
_ANNUAL_PATTERNS = (
    r"\b(\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"[a-z]*)\s+(every\s+)?year\b",
    r"\bannual(ly)?\b",
    r"\bevery\s+year\b",
    r"\bper\s+academic\s+year\b",
    r"\beach\s+academic\s+year\b",
    r"\bdeadline\s*:\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*\(?\s*annually",
    r"\buniversity\s+term\s+deadline\b",
)

_ROLLING_RE = re.compile("|".join(_ROLLING_PATTERNS), re.IGNORECASE)
_ANNUAL_RE = re.compile("|".join(_ANNUAL_PATTERNS), re.IGNORECASE)

_MONTH_ONLY_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\b(?!\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)


def classify_deadline_text(text: str | None) -> DeadlineKind:
    """Classify a published deadline statement.

    Rolling wins over annual: "applications are reviewed on a rolling basis
    throughout the year" is a rolling policy even though it contains the word
    "year". Exact-date detection is the caller's job, because only it can see
    whether a real calendar date was parsed.
    """
    if not text:
        return DeadlineKind.UNKNOWN
    if _ROLLING_RE.search(text):
        return DeadlineKind.ROLLING
    if _ANNUAL_RE.search(text):
        return DeadlineKind.ANNUAL
    if _MONTH_ONLY_RE.search(text):
        return DeadlineKind.MONTH
    return DeadlineKind.UNKNOWN


def is_rolling_or_recurring(text: str | None) -> bool:
    """True when the provider states a continuing or repeating deadline.

    Used to stop an empty ``deadline_display`` from reading as "nothing was
    published" when in fact the page said the programme never closes.
    """
    kind = classify_deadline_text(text)
    return kind in (DeadlineKind.ROLLING, DeadlineKind.ANNUAL)


def normalise_deadline_precision(parsed_date_is_exact: bool, text: str | None) -> str:
    """Resolve the stored ``deadline_precision`` for a published statement."""
    if parsed_date_is_exact:
        return "exact"
    kind = classify_deadline_text(text)
    if kind is DeadlineKind.ROLLING:
        return "rolling"
    if kind is DeadlineKind.ANNUAL:
        return "recurring"
    if kind is DeadlineKind.MONTH:
        return "month"
    return "unknown"


# Every value `deadline_precision` is allowed to hold.
#
# The column is `String(16) NOT NULL`, so this is a hard constraint rather than
# a convention. It matters because the extractor's `deadline_type` is free text:
# a live discovery round tried to insert `application_deadline` (19 characters)
# and every one of those inserts died with
# `StringDataRightTruncation: value too long for type character varying(16)`.
# The failure was caught and logged per-candidate, so the run stayed green
# while silently losing records.
DEADLINE_PRECISION_VALUES: frozenset[str] = frozenset(
    {"exact", "month", "year", "rolling", "recurring", "varies", "approximate", "unknown"}
)


def coerce_deadline_precision(value: object) -> str:
    """Map any extractor-supplied precision onto the stored vocabulary.

    Unrecognised input becomes ``"unknown"`` rather than being passed through.
    That is the honest mapping: if the extractor produced a token the schema has
    never heard of, the safe claim is that the precision is unknown, not that it
    is whatever the token happened to say. Passing it through would trade a
    truthful placeholder for a crash, and truncating it would produce a value
    that looks authoritative and means nothing.
    """
    if value is None:
        return "unknown"
    text = str(value).strip().lower()
    if not text:
        return "unknown"
    if text in DEADLINE_PRECISION_VALUES:
        return text
    # The extractor sometimes emits a phrase rather than a single token, e.g.
    # "application_deadline" for a deadline it read off an application page.
    # Substring matching keeps the recognisable cases rather than collapsing
    # everything to "unknown".
    for known in ("exact", "rolling", "recurring", "approximate", "varies"):
        if known in text:
            return known
    if "month" in text:
        return "month"
    if "year" in text:
        return "year"
    return "unknown"

