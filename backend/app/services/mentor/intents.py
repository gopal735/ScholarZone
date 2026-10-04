"""Deterministic intent classification.

The mentor decides what a message is *about* before it decides what to say, and
that decision is made by counting phrase hits against a fixed table. There is no
model in this path, which means the same message always resolves to the same
intent, an unrecognised message is recognised as unrecognised rather than
guessed at, and the classification can be asserted in a test exactly.

The vocabulary is published to the client with every response, following the
precedent in ``schemas_dashboard.application_states``: the server owns the list of
things it understands, so the interface offers exactly those and cannot drift
into suggesting one the API would reject.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .guards import MAX_MESSAGE_LENGTH, contains_injection_marker, normalize_message

#: Ordered. When two intents score identically the earlier entry wins, which is
#: what makes ties deterministic rather than dependent on dict ordering.
INTENT_ORDER: tuple[str, ...] = (
    "NEXT_ACTION",
    "DEADLINE",
    "APPLICATION_PROGRESS",
    "READINESS",
    "SCHOLARSHIP_EXPLANATION",
    "MATCH_EXPLANATION",
    "REQUIREMENT_GUIDANCE",
    "SCHOLARSHIP_COMPARISON",
    "DECISION_SUPPORT",
    "PROFILE_GAPS",
    "GENERAL_GUIDANCE",
)

INTENT_LABELS: dict[str, str] = {
    "NEXT_ACTION": "What to do next",
    "SCHOLARSHIP_EXPLANATION": "Why this scholarship fits",
    "MATCH_EXPLANATION": "Reading your match",
    "READINESS": "Readiness and eligibility",
    "DEADLINE": "Deadlines",
    "APPLICATION_PROGRESS": "Application progress",
    "PROFILE_GAPS": "Improving your profile",
    "SCHOLARSHIP_COMPARISON": "Comparing saved scholarships",
    "REQUIREMENT_GUIDANCE": "Trusted requirements",
    "DECISION_SUPPORT": "Choosing what to work on",
    "GENERAL_GUIDANCE": "What to focus on",
}

#: Phrases are matched on a normalised, space-padded haystack. Two-word entries
#: are deliberate: "what next" and "next steps" are how people actually ask,
#: while a bare "next" would capture unrelated sentences.
_PHRASES: dict[str, tuple[str, ...]] = {
    "NEXT_ACTION": (
        "what should i do",
        "what do i do",
        "what should i do now",
        "what should i do next",
        "what is my next step",
        "what are my next steps",
        "next step",
        "next steps",
        "do next",
        "where do i start",
        "what now",
        "right now",
        "to do next",
    ),
    "DEADLINE": (
        "deadline",
        "deadlines",
        "days left",
        "days remaining",
        "how long do i have",
        "closing soon",
        "when is it due",
        "when do they close",
        "expires",
        "closing date",
        "due date",
        "what dates",
    ),
    "APPLICATION_PROGRESS": (
        "my application",
        "this application",
        "current application",
        "application progress",
        "checklist",
        "what should i finish",
        "what do i still need to do",
        "remaining tasks",
        "how far through",
        "tasks left",
    ),
    "READINESS": (
        "am i ready",
        "am i eligible",
        "readiness",
        "what am i missing",
        "what is missing",
        "missing before",
        "do i qualify",
        "can i apply",
        "what is blocking",
        "blocked",
    ),
    "SCHOLARSHIP_EXPLANATION": (
        "why is this",
        "good match for me",
        "tell me about this",
        "what is this scholarship",
        "is this worth",
        "should i apply to this",
        "is this a good fit",
        "why this scholarship",
        "explain this scholarship",
    ),
    "MATCH_EXPLANATION": (
        "match score",
        "my match",
        "why is my score",
        "why is my fit",
        "fit score",
        "coverage",
        "confidence score",
        "why is my match",
        "score low",
        "score high",
        "low match",
        "high match",
    ),
    "REQUIREMENT_GUIDANCE": (
        "requirement",
        "requirements",
        "documents",
        "what documents",
        "what do i need to prepare",
        "what to prepare",
        "materials",
        "evidence do i need",
        "proof do i need",
    ),
    "SCHOLARSHIP_COMPARISON": (
        "compare",
        "which saved",
        "which of my saved",
        "prioritize",
        "prioritise",
        "which one should i",
        "choose between",
        "shortlist",
    ),
    "DECISION_SUPPORT": (
        "which application",
        "which should i work on",
        "which should i focus on",
        "what should i work on",
        "where should i start",
        "which opportunity",
        "help me decide",
    ),
    "PROFILE_GAPS": (
        "my profile",
        "improve my profile",
        "profile gaps",
        "strengthen my profile",
        "what should i add to my profile",
        "profile strength",
        "complete my profile",
    ),
    "GENERAL_GUIDANCE": (
        "what should i focus on",
        "this week",
        "general advice",
        "study plan",
        "how should i plan",
        "where should i begin",
        "getting started",
        "what should i be doing",
    ),
}

#: Phrases that mean "I did not understand, and I will say so". Checked before
#: scoring, because an explicit "what is this" is a real question about the
#: catalogue and must not be answered as though it were a request for guidance.
_META = (
    "what can you do",
    "what do you do",
    "who are you",
    "what are you",
    "help",
)

#: An explicit numeric reference only. "scholarship 42", "scholarship #42",
#: "#42" and "/scholarships/42" all count; a bare number does not, because "I
#: have 3 scholarships" is a statement about the student, not a record id.
_SCHOLARSHIP_REF = re.compile(
    r"/scholarships/\s*(\d{1,9})|scholarship\s*#?\s*(\d{1,9})|#\s*(\d{1,9})",
    re.IGNORECASE,
)
_APPLICATION_REF = re.compile(
    r"/applications/\s*(\d{1,9})|application\s*#?\s*(\d{1,9})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Intent:
    """What the mentor understood, and what it could not."""

    kind: str
    label: str
    #: True when nothing matched and the answer must say so rather than guess.
    unsupported: bool
    scholarship_id: int | None = None
    application_id: int | None = None
    injection_markers: tuple[str, ...] = ()
    truncated: bool = False

    @property
    def supported(self) -> bool:
        return not self.unsupported


def extract_scholarship_id(text: str) -> int | None:
    """Read a scholarship id out of a URL or a short reference.

    Only an explicit numeric reference counts. Guessing which scholarship a
    student meant from prose would be the mentor inventing the subject of the
    question, and every downstream fact would then be confidently about the
    wrong record.
    """
    match = _SCHOLARSHIP_REF.search(text)
    if not match:
        return None
    raw = next((group for group in match.groups() if group), None)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def extract_application_id(text: str) -> int | None:
    match = _APPLICATION_REF.search(text)
    if not match:
        return None
    raw = next((group for group in match.groups() if group), None)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def classify(message: object) -> Intent:
    """Resolve a raw message into a single supported intent, or admit failure.

    The whole message is scored, not the first matching keyword, so a question
    that names both a deadline and a checklist resolves to whichever the student
    actually emphasised more rather than to whichever appears first in the table.
    """
    normalized = normalize_message(message)
    truncated = len(normalized) > MAX_MESSAGE_LENGTH
    haystack = f" {normalized.lower()} "

    scholarship_id = extract_scholarship_id(normalized)
    application_id = extract_application_id(normalized)

    # A bare reference to a specific application is unambiguous even when the
    # phrasing is thin ("application 9"), so it is read before phrase scoring
    # rather than being outvoted by a single generic keyword.
    if application_id is not None and not any(
        phrase in haystack for phrases in _PHRASES.values() for phrase in phrases
    ):
        return Intent(
            kind="APPLICATION_PROGRESS",
            label=INTENT_LABELS["APPLICATION_PROGRESS"],
            unsupported=False,
            application_id=application_id,
            injection_markers=tuple(contains_injection_marker(normalized)),
            truncated=truncated,
        )

    lowered = normalized.lower()
    if any(marker in lowered for marker in _META) and not normalized.strip():
        return Intent(
            kind="GENERAL_GUIDANCE",
            label=INTENT_LABELS["GENERAL_GUIDANCE"],
            unsupported=False,
            injection_markers=(),
            truncated=truncated,
        )

    best_kind: str | None = None
    best_score = 0
    for kind in INTENT_ORDER:
        score = sum(1 for phrase in _PHRASES[kind] if phrase in haystack)
        if score > best_score:
            best_kind, best_score = kind, score

    if best_kind is None:
        # An explicit reference to a record the student named is a question about
        # that record, even when the phrasing around it is thin ("tell me about
        # scholarship 42"). Refusing to answer would be unhelpful; guessing at a
        # subject they did not name would be inventing one.
        if scholarship_id is not None:
            return Intent(
                kind="SCHOLARSHIP_EXPLANATION",
                label=INTENT_LABELS["SCHOLARSHIP_EXPLANATION"],
                unsupported=False,
                scholarship_id=scholarship_id,
                application_id=application_id,
                injection_markers=tuple(contains_injection_marker(normalized)),
                truncated=truncated,
            )
        return Intent(
            kind="UNSUPPORTED",
            label="Not a grounded question",
            unsupported=True,
            scholarship_id=scholarship_id,
            application_id=application_id,
            injection_markers=tuple(contains_injection_marker(normalized)),
            truncated=truncated,
        )

    return Intent(
        kind=best_kind,
        label=INTENT_LABELS[best_kind],
        unsupported=False,
        scholarship_id=scholarship_id,
        application_id=application_id,
        injection_markers=tuple(contains_injection_marker(normalized)),
        truncated=truncated,
    )