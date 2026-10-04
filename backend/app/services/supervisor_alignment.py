"""Deterministic research alignment.

This answers one narrow question: does what the student explicitly said they are
interested in overlap what a professor's official page says they research?

It is a band, not a score. There is no percentage, because a number here would
be read as a probability of getting in, and nothing in this file measures that.
The strongest possible output is "your stated interest matches a published
research area", which is a fact about two published lists.

Two rules make it safe to publish:

* Interests are only ever taken from an explicit list the student supplied. They
  are never inferred from a profile, a document, a country or anything else,
  because an inferred interest is an invented fact about a person.
* With no interests, or with no verified research areas to compare against, the
  result is ``INSUFFICIENT_EVIDENCE``. That is the default for every student in
  1.0 and it is a correct answer rather than a missing feature.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .supervisor_status import ResearchAlignmentBand

#: Terms too common in academic prose to carry any signal about a topic. Removed
#: before comparison so "research" cannot manufacture an overlap.
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
        "is", "it", "its", "of", "on", "or", "over", "research", "studies", "study",
        "the", "their", "this", "to", "using", "with", "based", "new", "applied",
    }
)

#: Bounded so a pathological input cannot make this quadratic in effort.
_MAX_TERMS = 40
_MAX_TERM_LENGTH = 80


def _normalize_term(value: str) -> str:
    """Reduce a phrase to comparable form.

    Accents are folded and punctuation is dropped so that "Machine Learning",
    "machine-learning" and "Machine  learning" compare equal. This is
    presentation normalisation only; it does not translate between languages or
    guess at synonyms.
    """
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    # A hyphen is a separator, not a negation marker, so it becomes a space.
    collapsed = re.sub(r"[^a-z0-9+#]+", " ", stripped.replace("-", " "))
    return " ".join(collapsed.split())


def _terms(values: list[str] | tuple[str, ...] | None) -> set[str]:
    """Return the comparable term set for a list of phrases."""
    result: set[str] = set()
    for value in values or ():
        if not isinstance(value, str):
            continue
        normalized = _normalize_term(value)
        if not normalized or len(normalized) > _MAX_TERM_LENGTH:
            continue
        result.add(normalized)
        for token in normalized.split():
            if token not in _STOPWORDS and len(token) > 2:
                result.add(token)
        if len(result) >= _MAX_TERMS:
            break
    return result


@dataclass(frozen=True)
class ResearchAlignment:
    """One alignment result, with the evidence for the band it was given."""

    band: ResearchAlignmentBand
    #: The student's stated interests that matched a published area. Bounded and
    #: plain, so the explanation can quote what actually overlapped.
    matched_interests: tuple[str, ...] = ()
    #: The verified faculty areas that produced the match.
    matched_areas: tuple[str, ...] = ()
    #: One sentence naming the overlap, or naming why no comparison was possible.
    explanation: str = ""

    def as_dict(self) -> dict:
        return {
            "band": str(self.band),
            "matched_interests": list(self.matched_interests),
            "matched_areas": list(self.matched_areas),
            "explanation": self.explanation,
        }


def align_research(
    interests: list[str] | tuple[str, ...] | None,
    research_areas: list[str] | tuple[str, ...] | None,
    research_keywords: list[str] | tuple[str, ...] | None = None,
) -> ResearchAlignment:
    """Return the alignment band for one professor.

    Bands are decided in a fixed order and the first match wins, so the result
    is a pure function of its inputs:

    ``STRONG``   a stated interest matches a published area as a whole phrase.
    ``MODERATE`` every significant word of a stated interest is present in the
    published areas, but not as one phrase.
    ``RELATED``  some significant word overlaps. This is the weakest band that
    still reflects a real shared term, and it is deliberately generous rather
    than precise.
    ``INSUFFICIENT_EVIDENCE`` either side is empty.

    No arithmetic on the inputs produces a number, so there is nothing here that
    can be mistaken for a likelihood.
    """
    interest_phrases = [
        normalized
        for normalized in (_normalize_term(value) for value in interests or () if isinstance(value, str))
        if normalized
    ]
    area_phrases = [
        normalized
        for normalized in (
            _normalize_term(value) for value in list(research_areas or []) + list(research_keywords or []) if isinstance(value, str)
        )
        if normalized
    ]

    if not interest_phrases:
        return ResearchAlignment(
            band=ResearchAlignmentBand.INSUFFICIENT_EVIDENCE,
            explanation=(
                "No research interests were supplied, so no comparison was made. "
                "Add your research interests to see which faculty areas overlap."
            ),
        )
    if not area_phrases:
        return ResearchAlignment(
            band=ResearchAlignmentBand.INSUFFICIENT_EVIDENCE,
            matched_interests=tuple(interest_phrases[:5]),
            explanation=(
                "No verified research areas are published for this academic, "
                "so there is nothing to compare your interests against."
            ),
        )

    area_set = _terms(area_phrases)
    area_phrase_set = set(area_phrases)

    strong_matches = [
        phrase for phrase in interest_phrases if phrase in area_phrase_set
    ]
    if strong_matches:
        return ResearchAlignment(
            band=ResearchAlignmentBand.STRONG_RESEARCH_ALIGNMENT,
            matched_interests=tuple(strong_matches[:5]),
            matched_areas=tuple(strong_matches[:5]),
            explanation=(
                "Strong research alignment: your stated interest "
                f"{_quote(strong_matches[0])} matches a verified faculty research area."
            ),
        )

    moderate_matches: list[str] = []
    for phrase in interest_phrases:
        tokens = [token for token in phrase.split() if token not in _STOPWORDS and len(token) > 2]
        # Two significant words, not one. A single shared generic word such as
        # "approaches" or "systems" is a coincidence, not an alignment, and
        # reporting it as MODERATE would overstate the evidence.
        if len(tokens) < 2:
            continue
        if all(token in area_set for token in tokens):
            moderate_matches.append(phrase)
    if moderate_matches:
        matched_area = next(
            (area for area in area_phrases if any(token in area for token in moderate_matches[0].split())),
            moderate_matches[0],
        )
        return ResearchAlignment(
            band=ResearchAlignmentBand.MODERATE_RESEARCH_ALIGNMENT,
            matched_interests=tuple(moderate_matches[:5]),
            matched_areas=(matched_area,),
            explanation=(
                "Moderate research alignment: every significant word in your stated interest "
                f"{_quote(moderate_matches[0])} appears across this academic's verified research areas."
            ),
        )

    related_matches: list[str] = []
    for phrase in interest_phrases:
        tokens = [token for token in phrase.split() if token not in _STOPWORDS and len(token) > 2]
        if any(token in area_set for token in tokens):
            related_matches.append(phrase)
    if related_matches:
        shared = sorted(
            {
                token
                for phrase in related_matches
                for token in phrase.split()
                if token not in _STOPWORDS and len(token) > 2 and token in area_set
            }
        )[:5]
        return ResearchAlignment(
            band=ResearchAlignmentBand.RELATED,
            matched_interests=tuple(related_matches[:5]),
            matched_areas=tuple(shared),
            explanation=(
                "Related: this shares the term "
                f"{_quote(shared[0])} with the verified research areas, which is a weak signal."
            ),
        )

    return ResearchAlignment(
        band=ResearchAlignmentBand.INSUFFICIENT_EVIDENCE,
        matched_interests=tuple(interest_phrases[:5]),
        explanation=(
            "No overlap found between your stated interests and this academic's "
            "verified research areas."
        ),
    )


def _quote(value: str) -> str:
    return f'"{value}"'


__all__ = ["ResearchAlignment", "align_research"]