"""Recover documents and selection criteria that are buried inside prose.

Official pages routinely state a required document in the middle of a
paragraph rather than in a bulleted list:

    "Applicants must submit a certified transcript of records together with two
     reference letters and a copy of their passport."

Section classification routes that line to eligibility, because the sentence
opens with "Applicants must". The document requirements are real, stated
verbatim by the provider, and were being discarded. This module isolates them
from the sentence they were embedded in.

The same applies to selection criteria, which providers often write as a
sentence inside a funding or programme section ("shortlisted candidates are
interviewed by a selection committee").

Design constraints, in order of importance:

1. Nothing is invented. A clause is only emitted when the source sentence
   actually contains a document noun in a document context, and the emitted
   text is a substring of the original sentence - never a rewrite.
2. Negated and optional material is excluded. "A language certificate is not
   required" must not become a required document, and "recommended" is not
   required.
3. Duplicates across sections collapse onto one entry.
"""

from __future__ import annotations

import re

#: A document noun. Matched with word boundaries so "cv" does not fire inside
#: "scFv" and "id" does not fire inside "consider".
_DOCUMENT_NOUNS = (
    r"transcript(?:\s+of\s+(?:records|results))?",
    r"academic\s+(?:transcript|records|record)",
    r"certified\s+copy\s+of\s+(?:transcripts?|records?)",
    r"(?:degree|diploma|graduation)\s+certificate",
    r"certificate\s+of\s+(?:completion|graduation|award)",
    r"passport(?:\s+(?:copy|photocopy|page))?",
    r"national\s+identity\s+(?:card|document)",
    r"proof\s+of\s+(?:nationality|residence|identity)",
    r"(?:curriculum\s+vitae|\bcv\b)",
    r"(?:motivation|cover)\s+letter",
    r"statement\s+of\s+(?:purpose|purpose|interest|objectives)",
    r"\bsop\b",
    r"(?:research|project)\s+(?:proposal|plan)",
    r"letters?\s+of\s+recommendation",
    r"recommendation\s+letters?",
    r"reference\s+letters?",
    r"academic\s+references?",
    r"(?:personal|academic)\s+statement",
    r"(?:writing|essays?|personal\s+statement)",
    r"(?:portfolio|works\s+sample)",
    r"(?:english|language)\s+(?:language\s+)?(?:test|proof|certificate|qualification)",
    r"\bielts\b(?:\s+(?:score|certificate|results?))?",
    r"\btoefl\b(?:\s+(?:score|certificate|results?))?",
    r"(?:gre|gmAT|gmat|gate)\s+(?:score|results?)",
    r"birth\s+certificate",
    r"medical\s+certificate",
    r"police\s+clearance",
    r"bank\s+statement",
    r"marriage\s+certificate",
    r"(?:signed\s+)?application\s+form",
    r"study\s+plan",
    r"research\s+proposal",
)

_DOC_NOUN_RE = re.compile(r"\b(?:" + "|".join(_DOCUMENT_NOUNS) + r")\b", re.IGNORECASE)

#: A clause is only a requirement when it is in a requiring context.
_REQUIRE_CONTEXT = re.compile(
    r"\b(submit|submitting|provide|providing|supply|supplying|attach|attaching|"
    r"upload|uploading|present|presenting|send|sending|require|required|requires|"
    r"must\s+(?:be\s+)?(?:submit|provide|attach|upload|present|send)|"
    r"along\s+with|together\s+with|accompanied\s+by)\b",
    re.IGNORECASE,
)

#: Markers that make a document optional. These clauses are deliberately not
#: promoted to required documents.
_OPTIONAL_MARKER = re.compile(
    r"\b(optional|optionally|not\s+required|isn'?t\s+required|not\s+mandatory|"
    r"if\s+applicable|if\s+relevant|recommended|encouraged|preferred|may\s+be|"
    r"might\s+be|could\s+be|as\s+needed|at\s+your\s+discretion)\b",
    re.IGNORECASE,
)

#: The whole clause is negated, not just optional.
_NEGATION_RE = re.compile(
    r"\b(?:not\s+required|is\s+not\s+required|no\s+.{0,30}\s+required|"
    r"is\s+not\s+necessary|do\s+not\s+need|does\s+not\s+need|without)\b",
    re.IGNORECASE,
)

#: Selection-process vocabulary, used to lift selection facts out of prose.
_SELECTION_RE = re.compile(
    r"\b(interview|interviews|interviewed|selection\s+committee|selection\s+panel|"
    r"selection\s+process|shortlist(?:ed|ing)?|assessment\s+criteria|"
    r"evaluation\s+criteria|evaluation\s+committee|review\s+panel|"
    r"shortlisted\s+candidates?|decision\s+(?:will\s+be\s+)?(?:be\s+)?(?:made|notified|announced)|"
    r"notification\s+of\s+(?:results?|outcome|decision)|"
    r"notification\s+to\s+(?:successful|unsuccessful)|"
    r"reviewed\s+by|assessed\s+by|evaluated\s+by|"
    r"ranked\s+on\s+the\s+basis\s+of|"
    r"academic\s+excellence|interview\s+performance)\b",
    re.IGNORECASE,
)

#: "Please note that a language certificate is not required" - the negation
#: governs the sentence, so nothing in it may be promoted.
_NEGATION_SENTENCE_RE = re.compile(
    r"\b(?:not\s+required|is\s+not\s+required|are\s+not\s+required|"
    r"no\s+(?:proof|certificate|transcript|passport|cv|curriculum\s+vitae)\s+is\s+required|"
    r"neither.{0,40}is\s+required|no\s+language\s+(?:test|proof)\s+is\s+required)\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n+")


def _sentences(text: str) -> list[str]:
    parts = [(chunk or "").strip() for chunk in _SENTENCE_SPLIT.split(text or "")]
    return [p for p in parts if p]


def _clause_around(sentence: str, match_start: int, match_end: int) -> str:
    """Return the clause containing a document mention.

    The clause is a substring of the source, so a stored requirement can be
    traced back to the exact wording the provider used.
    """
    left = max(
        sentence.rfind(sep, 0, match_start) for sep in (",", ";", " and ", " plus ", " as well as ")
    )
    left = max(left, 0)
    right_candidates = [
        idx
        for idx in (
            sentence.find(sep, match_end)
            for sep in (",", ";", " and ", " plus ")
        )
        if idx != -1
    ]
    right = min(right_candidates) if right_candidates else len(sentence)
    return sentence[left:right].strip(" ,;.")


def extract_documents_from_prose(text: str | None, *, limit: int = 8) -> list[str]:
    """Recover explicitly-required documents embedded in ordinary prose.

    Returns verbatim clauses, so nothing is paraphrased into existence. A
    sentence that is itself negated, or that marks the document as optional,
    contributes nothing.
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    for sentence in _sentences(text):
        if _NEGATION_SENTENCE_RE.search(sentence):
            continue
        if not _REQUIRE_CONTEXT.search(sentence):
            continue
        for match in _DOC_NOUN_RE.finditer(sentence):
            window_start = max(0, match.start() - 90)
            window = sentence[window_start : match.end() + 40]
            # Only reject optionality when it qualifies this document, not when
            # an unrelated optional item appears elsewhere in the sentence.
            if _OPTIONAL_MARKER.search(window):
                continue
            if _NEGATION_RE.search(window):
                continue
            clause = _clause_around(sentence, match.start(), match.end())
            if len(clause) < 12:
                clause = match.group(0)
            # One sentence naming several documents can yield the same clause
            # for two of them; the list is a set of requirements, not a tally
            # of word hits.
            key = re.sub(r"\W+", " ", clause.lower()).strip()
            if key in seen:
                continue
            seen.add(key)
            seen.add(match.group(0).lower())
            found.append(clause[:300])
            if len(found) >= limit:
                return found
    return found


def extract_selection_from_prose(text: str | None, *, limit: int = 4) -> list[str]:
    """Recover selection-process statements from ordinary prose."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for sentence in _sentences(text):
        if _NEGATION_SENTENCE_RE.search(sentence):
            continue
        if not _SELECTION_RE.search(sentence):
            continue
        key = sentence.strip()[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(sentence.strip()[:400])
        if len(found) >= limit:
            break
    return found
