"""Whether supervisor discovery applies to a record at all.

``NOT_APPLICABLE`` is the strongest negative in the supervisor vocabulary, so
the evidence bar for reaching it is deliberately high: it asserts that a record
*cannot* have supervisors by nature, not that we failed to find any. Two rules
keep that assertion honest.

**Unknown is applicable.** A record whose degree field says ``Unknown``,
``Other``, ``Not specified`` or nothing at all has stated nothing either way.
Discovery still runs for it, and whatever it finds - or fails to find - is
recorded as such. Marking such a record not-applicable would launder "we were
not told" into "there is nothing to tell".

**Positive evidence of a degree or research programme wins.** If the record's
own fields mention any research- or degree-bearing level, supervision is
possible in principle and discovery applies. The check is a substring scan over
the two structured fields the catalogue maintains - ``degree`` and
``program_type`` - and every rationale quotes the field it came from, so a
reviewer can see exactly what was read rather than trusting a category.

The module is pure: it reads attributes off one object and returns a value. No
database, no network, no session.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

#: Words that assert a degree-bearing or research level. A record carrying any
#: of these can have a supervising academic somewhere, so discovery applies
#: even when every other field is missing.
DEGREE_LEVEL_TOKENS: tuple[str, ...] = (
    "bachelor",
    "master",
    "doctoral",
    "doctorate",
    "doctor",
    "phd",
    "dphil",
    "mphil",
    "mba",
    "msc",
    "bsc",
    "m.sc",
    "b.sc",
    "undergraduate",
    "postgraduate",
    "graduate",
    "postdoc",
    "post-doctoral",
    "research",
    "degree",
    "diploma",
    "honours",
    "associate",
    "foundation year",
)

#: Negations that contain a degree-level word. ``non-degree`` contains the
#: substring ``degree``, so the positive scan must have them removed first or
#: the one phrase that denies a degree would be read as claiming one.
_NEGATED_PHRASES: tuple[str, ...] = (
    "non-degree",
    "non degree",
    "not a degree",
    "non-doctoral",
    "non doctoral",
)

#: Words that assert the record is *not* a supervised degree or research
#: programme. Only reached when no degree-level token is present, so a
#: "Master's (short course)" is still applicable - it is a degree first.
NON_PROGRAMME_TOKENS: tuple[str, ...] = (
    "short-term",
    "short term",
    "professional development",
    "language course",
    "language pathway",
    "language studies",
    "language program",
    "language training",
    "pre-tertiary",
    "non-degree",
    "summer school",
    "summer programme",
    "training course",
    "workshop",
    "conference",
    "olympiad",
    "competition",
    "internship",
    "apprenticeship",
    "vocational",
    "staff exchange",
    "study tour",
    "study visit",
)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Applicability:
    """The answer for one record, with the evidence that produced it."""

    #: Whether discovery should run for this record at all.
    applicable: bool
    #: The quoted, record-sourced reason a record is *not* applicable. ``None``
    #: whenever ``applicable`` is true: there is nothing to explain.
    rationale: str | None = None

    @property
    def is_not_applicable(self) -> bool:
        return not self.applicable


class _Record(Protocol):
    """The shape this module judges - what the catalogue row already stores."""

    degree: str | None
    program_type: str | None


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return _WHITESPACE.sub(" ", value).strip()


def _without_negations(value: str) -> str:
    """Return ``value`` with every explicit degree negation removed."""
    cleaned = value
    for phrase in _NEGATED_PHRASES:
        cleaned = cleaned.replace(phrase, " ")
    return _WHITESPACE.sub(" ", cleaned).strip()


def _quoted(degree: str, program_type: str) -> str:
    """Return the record's own words, for the rationale and for the audit log."""
    parts = []
    if degree:
        parts.append(f'degree="{degree}"')
    if program_type:
        parts.append(f'program_type="{program_type}"')
    return "; ".join(parts)


def classify_supervisor_applicability(record: _Record) -> Applicability:
    """Return whether supervisor discovery applies to ``record``.

    Three outcomes, in this order, and the order is the safety property: a
    degree-level token anywhere means *applicable* even if the same string also
    names a short course, and only a record that states a non-programme
    category and no degree level reaches ``NOT_APPLICABLE``.
    """
    quoted_degree = _clean(getattr(record, "degree", None))
    quoted_program_type = _clean(getattr(record, "program_type", None))
    degree = quoted_degree.casefold()
    program_type = quoted_program_type.casefold()
    both = f"{degree} {program_type}".strip()

    if not both:
        # The record states nothing about its own shape. That is not evidence
        # of anything, so discovery applies and its outcome will be recorded
        # honestly rather than pre-empted here.
        return Applicability(applicable=True)

    if any(token in _without_negations(both) for token in DEGREE_LEVEL_TOKENS):
        return Applicability(applicable=True)

    matched = [token for token in NON_PROGRAMME_TOKENS if token in both]
    if matched:
        return Applicability(
            applicable=False,
            rationale=(
                "The record describes an award that is not a supervised degree or "
                "research programme, so academic supervision is not applicable. "
                f"Stated on the record as {_quoted(quoted_degree, quoted_program_type)}; "
                f"the non-programme category is {matched[0]!r}. No professor is listed "
                "for this award and none should be inferred."
            ),
        )

    # Neither a degree level nor a known non-programme category: "Other",
    # "Unknown", "Not specified". Applicable, because the record has not said
    # either way and discovery is what produces the answer.
    return Applicability(applicable=True)


__all__ = [
    "DEGREE_LEVEL_TOKENS",
    "NON_PROGRAMME_TOKENS",
    "Applicability",
    "classify_supervisor_applicability",
]