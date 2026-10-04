"""Deciding whether a piece of link text names an academic.

The earlier implementation rejected place and organisation names with a long list
of known-bad words - cities, states, countries, campuses. That was the wrong shape
of solution. A blacklist only ever contains the cases somebody already thought of,
and it silently loses ground every time a university invents a new way to name a
place. It also reads as if the blacklist *is* the safety mechanism, which means the
real safety property is unstated and untested.

So the primary mechanism here is positive evidence, and it is the same evidence a
person actually leaves behind:

* an **academic role** - "Dr", "Professor", "Reader", "Research Fellow"; or
* **source context** - the link sits at the personal-profile path of a page the
  pipeline has already established is a faculty directory.

Either is sufficient on its own. Absent both, the text is not a person. That
single rule is what rejects "South Australia", "Adelaide City", "English Language
Centre", "School of Computing", "Faculty of Engineering" and "Admissions Office" -
not because they are on a list, but because none of them claims to be a person.

Two deliberate design points:

**A name is not a professor.** This module decides *personhood*, never academic
role by itself and never supervisor suitability. "Dr Smith" is a person; whether
they can supervise is established by the programme's evidence elsewhere. Returning
a :class:`PersonSignal` with an explicit ``role_evidence`` field keeps that
separation visible at the call site rather than implied.

**Domain ownership is not identity.** Nothing here looks at the host. A page on an
institution's own domain is necessary for the *caller* to accept a relationship,
and it is not sufficient - the person evidence is judged separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

#: Academic roles that identify a person. "Faculty" is deliberately absent: it
#: names a collective, and "Faculty of Engineering" is an institution, not a
#: person. "Staff" is absent for the same reason.
ACADEMIC_ROLE_PHRASES: tuple[str, ...] = (
    "professor",
    "associate professor",
    "assistant professor",
    "prof",
    "dr",
    "doctor",
    "reader",
    "lecturer",
    "researcher",
    "research fellow",
    "senior fellow",
    "fellow",
    "postdoctoral researcher",
    "postdoc",
    "academic",
    "chancellor",
    "vice-chancellor",
    "dean",
    "head of school",
    "department head",
)

#: Honorifics that may lead a name. Matched as a whole token so "Drive" does not
#: become a doctor.
HONORIFICS: frozenset[str] = frozenset(
    {
        "dr", "prof", "professor", "mr", "mrs", "ms", "miss", "mx",
        "sir", "dame", "lord", "lady", "rev", "fr", "sr",
    }
)

#: Tokens that may appear inside a personal slug but never identify a person on
#: their own. This is a *navigational* set, not a geographic one: it lists words
#: that describe a section of a site rather than a human being. It is small,
#: justified, and only consulted for the weaker structural signal.
NAVIGATIONAL_SLUG_WORDS: frozenset[str] = frozenset(
    {
        "all", "about", "contact", "directory", "faculty", "find", "index",
        "list", "overview", "people", "search", "staff", "team",
    }
)

#: Path roots that introduce a personal profile. A slug is only meaningful
#: directly after one of these, so `/life-at-adelaide/adelaide-and-south-australia`
#: never qualifies no matter what its last segment is called.
PERSON_PATH_ROOTS: tuple[str, ...] = (
    "/people/",
    "/person/",
    "/people",
    "/person",
    "/profile/",
    "/profiles/",
    "/staff/",
    "/academics/",
    "/faculty/",
)

#: Tokens permitted inside a name without being capitalised: the particles that
#: genuinely occur in surnames.
NAME_PARTICLES: frozenset[str] = frozenset(
    {"van", "von", "de", "der", "den", "del", "della", "di", "da", "dos", "du", "la", "le", "el", "bin", "ibn", "st"}
)

MIN_NAME_TOKENS = 2
MAX_NAME_TOKENS = 5
MAX_LABEL_LENGTH = 120

#: Characters that indicate the text is not a name at all.
_MARKUP_CHARACTERS = "<>{}[]|/\\@#$%^&*+=~`\"'"

#: Separators that split "Jane Smith - Professor of Computing" into its two claims.
_SEGMENT_SPLIT = re.compile(r"\s+[—–-]\s+|\s+[|]\s+|\s+[•·]\s+")

_TOKEN_PATTERN = re.compile(r"[A-Za-zÀ-ÿ'’-]+")


@dataclass(frozen=True)
class PersonSignal:
    """Evidence that a piece of link text names one person.

    ``role_evidence`` is the mechanism that justified the decision, kept explicit
    so a caller can require a strong signal rather than any signal.
    """

    name: str
    role: str | None
    #: ``honorific`` | ``inline_role`` | ``source_context``
    role_evidence: str
    #: True when an academic role was stated. Structural directory context alone
    #: is weaker and is reported as such.
    academic_role_stated: bool

    @property
    def evidence_strength(self) -> str:
        return "strong" if self.academic_role_stated else "contextual"


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text or "")


def _is_person_shaped(text: str) -> bool:
    """Return whether ``text`` has the surface form of one person's name."""
    tokens = _tokens(text)
    if not MIN_NAME_TOKENS <= len(tokens) <= MAX_NAME_TOKENS:
        return False
    meaningful = 0
    for token in tokens:
        lowered = token.lower()
        if lowered in NAME_PARTICLES:
            continue
        meaningful += 1
        if not token[:1].isupper():
            return False
        # An all-caps token is an acronym or a heading, not a name.
        if token.isupper() and len(token) > 1:
            return False
    return meaningful >= MIN_NAME_TOKENS


def _find_role(text: str) -> str | None:
    """Return the academic role stated in ``text``, if any."""
    lowered = (text or "").lower()
    for phrase in ACADEMIC_ROLE_PHRASES:
        # Word-boundary match so "dr" does not match inside "drama" or a domain.
        if re.search(rf"(?<![\w.]){re.escape(phrase)}(?![\w])", lowered):
            return phrase
    return None


def _honorific_of(text: str) -> str | None:
    tokens = _tokens(text)
    if not tokens:
        return None
    first = tokens[0].lower().rstrip(".")
    return first if first in HONORIFICS else None


def _slug_after_person_root(url: str) -> str | None:
    """Return the slug that directly follows a personal-profile path root.

    Deliberately narrow. ``/life-at-adelaide/adelaide-and-south-australia`` has no
    personal root, so it returns ``None`` and the caller has no structural signal
    to fall back on - which is exactly the Adelaide case that produced place names.
    """
    if not url:
        return None
    path = (urlparse(url).path or "").lower().rstrip("/")
    for root in sorted(PERSON_PATH_ROOTS, key=len, reverse=True):
        if not root.endswith("/"):
            continue
        if path.startswith(root):
            remainder = path[len(root) :]
            if remainder and "/" not in remainder:
                return remainder
    return None


def _slug_is_personal(slug: str | None) -> bool:
    if not slug:
        return False
    words = [word for word in re.split(r"[-_]+", slug) if word]
    if not words:
        return False
    return not any(word in NAVIGATIONAL_SLUG_WORDS for word in words)


def classify_person_candidate(
    label: str,
    *,
    url: str = "",
    directory_context: bool = False,
    document_labels: frozenset[str] = frozenset(),
) -> PersonSignal | None:
    """Return evidence that ``label`` names one person, or ``None``.

    ``directory_context`` asserts the enclosing page was already established as a
    faculty directory. It never creates a person on its own; it only unlocks the
    structural signal, and even then the text must be person-shaped and the slug
    must sit directly under a personal-profile root.

    ``document_labels`` carries text taken from the document itself - the site
    name, page headings, breadcrumb labels. An exact match against it is rejected,
    because a navigation label is not a person however it is capitalised. This is
    document-derived rather than a hardcoded list, which is what lets it generalise
    to a university nobody has heard of.
    """
    raw = (label or "").strip()
    if not raw or len(raw) > MAX_LABEL_LENGTH:
        return None
    if any(character.isdigit() for character in raw):
        return None
    if any(character in raw for character in _MARKUP_CHARACTERS):
        return None

    normalised = raw.casefold().strip(" .,:;")
    if normalised and normalised in document_labels:
        return None

    segments = [segment.strip() for segment in _SEGMENT_SPLIT.split(raw) if segment.strip()]
    if not segments:
        segments = [raw]

    # Strongest evidence first: a role stated in the label itself.
    for segment in segments:
        honorific = _honorific_of(segment)
        if honorific is not None:
            remainder_tokens = _tokens(segment)[1:]
            remainder = " ".join(remainder_tokens).strip()
            if _is_person_shaped(remainder):
                return PersonSignal(
                    name=remainder,
                    role=honorific,
                    role_evidence="honorific",
                    academic_role_stated=honorific
                    in ("dr", "prof", "professor", "doctor", "reader", "lecturer"),
                )

    for index, segment in enumerate(segments):
        role = _find_role(segment)
        if role is None:
            continue
        # The name is a sibling segment when the role sits in its own clause.
        candidates = [other for position, other in enumerate(segments) if position != index]
        candidates.append(" ".join(_tokens(segment)[:2]))
        for candidate in candidates:
            candidate = candidate.strip()
            if _is_person_shaped(candidate):
                return PersonSignal(
                    name=candidate,
                    role=role,
                    role_evidence="inline_role",
                    academic_role_stated=True,
                )

    # Weaker evidence: personal-profile structure inside a known directory.
    if directory_context and _slug_is_personal(_slug_after_person_root(url)):
        for segment in segments:
            if _find_role(segment) is not None:
                continue
            if _is_person_shaped(segment):
                return PersonSignal(
                    name=segment,
                    role=None,
                    role_evidence="source_context",
                    academic_role_stated=False,
                )

    return None


def academic_role_in(text: str) -> str | None:
    """Return the first academic role ``text`` states about a person, if any.

    The single definition of that vocabulary, shared with
    :func:`classify_person_candidate` so the discovery module and the classifier
    cannot drift into disagreeing about what counts as a role.
    """
    return _find_role(text or "")


def looks_like_a_person_name(text: str) -> bool:
    """Convenience predicate: does this text claim to be a person at all?

    Retained because callers want a cheap screen before doing the full
    classification. It answers the *narrower* question - "is any academic role
    stated here" - and therefore returns ``False`` for a bare "Grace Hopper" that
    would still be accepted by :func:`classify_person_candidate` in a real faculty
    directory. Use the classifier for any decision that matters.
    """
    return _find_role(text or "") is not None or _honorific_of(text or "") is not None


__all__ = [
    "ACADEMIC_ROLE_PHRASES",
    "HONORIFICS",
    "NAVIGATIONAL_SLUG_WORDS",
    "PERSON_PATH_ROOTS",
    "PersonSignal",
    "academic_role_in",
    "classify_person_candidate",
    "looks_like_a_person_name",
]