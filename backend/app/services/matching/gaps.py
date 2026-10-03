"""Gaps: what could not be evaluated, and why it matters.

Every match result reports what it could not determine. That is the honest
counterweight to a score, and collapsing it - by hiding unevaluated dimensions,
or by scoring them as zero - is how a catalogue starts telling applicants
something it never established.

Four categories, and the distinction between them is the whole point of this
module:

``KNOWN_GAP``
    Something about the fit is measurable but weak, and we can say so. A
    programme field that resolved to a broad parent rather than the exact field is
    a known gap.

``UNVERIFIED``
    The provider published a mandatory condition and it could not be checked
    against the supplied profile. Nobody has been disqualified and nobody has
    been approved.

``MISSING_USER_INFORMATION``
    The student did not supply something the calculation could have used.
    This one is actionable by them, so it comes with a suggestion.

``MISSING_SCHOLARSHIP_DATA``
    The catalogue does not hold what it would need. No action by the student can
    change this, and saying so plainly is more useful than implying they are
    somehow short of information.

Nothing in this module is ever phrased as a failure. A missing field is a
statement about measurement; only the eligibility gate is allowed to make a
statement about the student's eligibility, and it makes it from published
conditions alone.
"""

from __future__ import annotations

from .types import Gap, GapCategory


#: code -> (category, plain-language message). Templates only; nothing here is
#: generated from scholarship prose, so the same inputs always produce the same
#: sentences.
GAP_TEMPLATES: dict[str, tuple[GapCategory, str]] = {
    # Missing scholarship data - the catalogue, not the student.
    "FIELD_NOT_PUBLISHED": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "This record does not publish a programme field ScholarZone can resolve, so field alignment was not evaluated.",
    ),
    "FIELD_UNKNOWN": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "The programme field for this scholarship is not structured in the catalogue, so field alignment was not evaluated.",
    ),
    "FUNDING_UNKNOWN": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "Funding coverage for this scholarship is not structured in the catalogue, so funding alignment was not evaluated.",
    ),
    "FUNDING_NOT_FULLY_STRUCTURED": (
        GapCategory.KNOWN_GAP,
        "Funding coverage is partly documented, so funding alignment was scored conservatively.",
    ),
    "LANGUAGE_NOT_PUBLISHED": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "This record publishes no language requirement, so language alignment was not evaluated.",
    ),
    "LANGUAGE_TEST_MISMATCH": (
        GapCategory.KNOWN_GAP,
        (
            "You supplied a different language test from the one this scholarship publishes, and ScholarZone "
            "does not convert between tests."
        ),
    ),
    "LANGUAGE_NO_SURPLUS_RANGE": (
        GapCategory.KNOWN_GAP,
        (
            "The published threshold was compared on the same test, but ScholarZone has no documented scoring "
            "range for it, so language alignment was not scored."
        ),
    ),
    "DEADLINE_NOT_PUBLISHED": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "No fixed application deadline is published for this scholarship, so timing was not scored.",
    ),
    "DEADLINE_ROLLING": (
        GapCategory.KNOWN_GAP,
        "This scholarship publishes a rolling or recurring deadline, so timing was not scored.",
    ),
    "DEADLINE_MONTH_PRECISION": (
        GapCategory.KNOWN_GAP,
        "The published deadline names a month rather than a day, so the remaining time is approximate.",
    ),
    "DEADLINE_CLOSED": (
        GapCategory.KNOWN_GAP,
        "This scholarship round is closed.",
    ),
    "REQUIREMENT_UNKNOWN": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "Some published conditions are not structured in the catalogue, so they were not scored.",
    ),
    "SOURCE_INCOMPLETE": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "Some of this scholarship's published details are missing from the catalogue.",
    ),
    "SOURCE_UNVERIFIED": (
        GapCategory.MISSING_SCHOLARSHIP_DATA,
        "This scholarship has not been marked verified in the catalogue.",
    ),
    "CONFIDENCE_LOW": (
        GapCategory.KNOWN_GAP,
        "The available information for this scholarship is limited, so confidence is low.",
    ),
    "CONFIDENCE_MEDIUM": (
        GapCategory.KNOWN_GAP,
        "Some of this scholarship's published details are missing, so confidence is medium.",
    ),
    # Missing user information - actionable by the student.
    "ACADEMIC_RESULT_NOT_PROVIDED": (
        GapCategory.MISSING_USER_INFORMATION,
        "Add your academic result so published academic minima can be compared with it.",
    ),
    "ACADEMIC_SCALE_MISMATCH": (
        GapCategory.KNOWN_GAP,
        (
            "The published academic minimum uses a different grading scale from your result, so the two were "
            "not compared."
        ),
    ),
    "FIELD_NOT_PROVIDED": (
        GapCategory.MISSING_USER_INFORMATION,
        "Add your field of study so programme alignment can be evaluated.",
    ),
    "LANGUAGE_NOT_PROVIDED": (
        GapCategory.MISSING_USER_INFORMATION,
        "Add your language test score so the published threshold can be checked.",
    ),
    "PREFERENCE_NOT_PROVIDED": (
        GapCategory.MISSING_USER_INFORMATION,
        "Add your preferred countries so location preferences can be compared.",
    ),
    "DEGREE_LEVEL_NOT_PROVIDED": (
        GapCategory.MISSING_USER_INFORMATION,
        "Add your intended degree level so degree-level conditions can be checked.",
    ),
    # Unverified - a published rule nobody has checked yet.
    "ELIGIBILITY_NEEDS_VERIFICATION": (
        GapCategory.UNVERIFIED,
        "One or more published mandatory conditions still need verifying against your details.",
    ),
    "NATIONALITY_NEEDS_VERIFICATION": (
        GapCategory.UNVERIFIED,
        "This scholarship restricts eligibility by country. Confirm your citizenship is on the official list.",
    ),
    "AGE_NEEDS_VERIFICATION": (
        GapCategory.UNVERIFIED,
        "This scholarship publishes an age limit. Add your age to check it.",
    ),
    "STUDY_MODE_NEEDS_VERIFICATION": (
        GapCategory.UNVERIFIED,
        "This scholarship states a study-mode condition. Add your intended study mode to check it.",
    ),
    "DEGREE_LEVEL_NEEDS_VERIFICATION": (
        GapCategory.UNVERIFIED,
        "This scholarship publishes which degree levels it covers. Add yours to check it.",
    ),
    "PROGRAMME_RESTRICTION_NEEDS_VERIFICATION": (
        GapCategory.UNVERIFIED,
        (
            "This scholarship names a specific programme. Confirm your programme on the awarding body's page."
        ),
    ),
}


def gap(code: str, component: str | None = None) -> Gap:
    """Build one gap from its template.

    An unknown code renders its own code rather than raising, so a new gap can
    be raised by a scorer before its wording exists and the omission is visible
    instead of fatal.
    """
    entry = GAP_TEMPLATES.get(code)
    if entry is None:
        return Gap(code=code, message=code, category=GapCategory.KNOWN_GAP, component=component)
    category, message = entry
    return Gap(code=code, message=message, category=category, component=component)


def category_of(code: str) -> GapCategory:
    """The category a gap code belongs to. Defaults to KNOWN_GAP."""
    entry = GAP_TEMPLATES.get(code)
    return entry[0] if entry else GapCategory.KNOWN_GAP


def deduplicate(gaps: list[Gap]) -> list[Gap]:
    """Order-preserving de-duplication: several paths can reach the same code."""
    seen: set[tuple[str, str | None]] = set()
    unique: list[Gap] = []
    for item in gaps:
        key = (item.code, item.component)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


__all__ = ["GAP_TEMPLATES", "category_of", "deduplicate", "gap"]