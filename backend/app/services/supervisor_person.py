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
    #: True when ``name`` itself made the claim of personhood, rather than
    #: borrowing a role stated in a neighbouring segment of the same link text.
    #:
    #: The storage gate sees only ``name`` and ``role``, and those two do not
    #: distinguish "Rachit Agarwal Professor" - one clause, a person and a role -
    #: from "Nanyang Research | Researchers" - a heading beside a role. Both arrive
    #: as a person-shaped name plus a role string, so the gate cannot separate them
    #: by re-reading them. The distinction is visible only here, while the segments
    #: are still in hand, which is why it is carried rather than derived.
    #:
    #: Surface form cannot stand in for it: "Nanyang Research" and "S Chandra Das"
    #: are both two capitalised words, so no word list separates them.
    name_claims_person: bool = True

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
        #
        # The leading boundary also excludes '-', so a role phrase is not read out
        # of the middle of a hyphenated compound. "Non-Academic Services" is a
        # service listing that *negates* the academic role; matching "academic"
        # inside it and then removing it leaves the fragment "Non-" to satisfy the
        # name test, and the listing becomes a verified professor. A role phrase
        # has to stand as its own word to be one.
        if re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w])", lowered):
            return phrase
    return None


def states_role_about_a_person(segment: str, role: str) -> bool:
    """Return whether ``segment`` claims a person *in addition to* stating ``role``.

    A role word on its own is a claim about a category, not about an individual.
    "Academic Staff" states a role and names the collective that holds it - there
    is no person in the text. "Rachit Agarwal Professor" states a role and names
    who holds it. Both contain a role word, so the presence of one settles
    nothing; the question is whether a person-shaped claim survives once the role
    claim is taken away.

    This is why the rule cannot be a list of forbidden words. Whether a label
    names somebody is a property of its structure - does anything remain that
    reads as a human name - and that holds for a university nobody has heard of.
    It is also why removing the *role* is the right operation rather than the
    name: "Academic Staff" collapses to a single non-name token, while
    "Rachit Agarwal Professor" collapses to "Rachit Agarwal", which is a person.

    Measured on the real Cornell Computer Science directory, which produced both
    shapes: fourteen labels reduced to a person, two navigation links did not.
    """
    if not role:
        return False
    remainder = re.sub(
        rf"(?<![\w.]){re.escape(role)}(?![\w])", " ", segment or "", flags=re.IGNORECASE
    )
    return _is_person_shaped(remainder)


def role_words_are_the_whole_name(name: str, role: str | None) -> bool:
    """Return whether ``name`` is nothing but the role claim written out.

    The narrow form of :func:`states_role_about_a_person`, for the storage gate,
    which sees only the name and role a candidate ended up with rather than the
    segment they were read from. True means the text claimed a category and
    nothing else, so no individual is evidenced anywhere in it.
    """
    if not role:
        return False
    return not states_role_about_a_person(name, role)


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


def profile_url_is_person_profile(url: str) -> bool:
    """Return whether ``url`` sits at a personal-profile path.

    A URL is person-bearing when its path begins with a recognised personal-profile
    root and the immediately following slug is not navigational. This is the same
    test the classifier applies for source-context evidence, lifted here so the
    gating layer can require it for inline-role evidence as well.
    """
    if not url:
        return False
    slug = _slug_after_person_root(url)
    return _slug_is_personal(slug)


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
                    name_claims_person=True,
                )

    for index, segment in enumerate(segments):
        role = _find_role(segment)
        if role is None:
            continue
        # The name is a sibling segment when the role sits in its own clause.
        siblings = [other for position, other in enumerate(segments) if position != index]
        # Otherwise the name is taken from the role-bearing segment itself, which
        # is the case that has to be checked: the tokens used as the name include
        # the role word, so "Academic Staff" offers itself as a person called
        # "Academic Staff" with the role "academic". A name is only independent
        # evidence of a person when something person-shaped survives removing the
        # role, which "Rachit Agarwal Professor" does and "Academic Staff" does
        # not. See states_role_about_a_person.
        #
        # ``segment_claims_person`` is the part a sibling cannot lend. This segment
        # vouches for a name taken out of itself only if the role is really a word
        # of its own and a person survives its removal. When the role belongs to
        # another segment - "Nanyang Research | Researchers" - nothing is removed
        # from this one, nothing person-shaped is left to find, and the name has
        # claimed nobody. Surface form cannot say so: "Nanyang Research" and
        # "S Chandra Das" are both two capitalised words.
        segment_claims_person = states_role_about_a_person(segment, role)
        candidates = list(siblings)
        if segment_claims_person:
            candidates.append(" ".join(_tokens(segment)[:2]))
        for candidate in candidates:
            candidate = candidate.strip()
            if _is_person_shaped(candidate):
                return PersonSignal(
                    name=candidate,
                    role=role,
                    role_evidence="inline_role",
                    academic_role_stated=True,
                    # A sibling segment carries its own claim about whoever the
                    # role names, not about this name.
                    name_claims_person=segment_claims_person,
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
                    # Structure said the page is a directory. That says the page is
                    # about people, not that this label is one.
                    name_claims_person=False,
                )

    return None


def name_is_person_shaped(text: str) -> bool:
    """Return whether ``text`` has the surface form of one person's name.

    The *structural* half of personhood: capitalised tokens, the right number of
    them, no acronyms, no digits. :func:`looks_like_a_person_name` answers the
    narrower question of whether a role or honorific appears, and is the wrong
    tool for a storage decision.

    This is necessary but not sufficient on its own, and using it alone is a
    known trap: "Academic Staff" and "School of Computing" are both two
    capitalised words, so both pass here and neither names an individual. Pair it
    with :func:`role_words_are_the_whole_name`, which removes the role and asks
    whether anything person-shaped survives - and which is what makes the pair
    equivalent to "this text claims a person" rather than "this text is two
    capitalised words".

    Public so the gate module can ask the question without reaching into this
    module's internals. It delegates to the same private predicate
    :func:`classify_person_candidate` uses, so there is one definition of
    person shape and the two cannot drift apart.
    """
    return _is_person_shaped(text)


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
    "name_is_person_shaped",
    "profile_url_is_person_profile",
    "role_words_are_the_whole_name",
    "states_role_about_a_person",
]
