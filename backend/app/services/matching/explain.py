"""Deterministic explanations.

Every sentence the interface shows about a match is rendered here from a fixed
template and a reason code. There is no free-text generation anywhere in the
matching path: the same inputs produce the same sentences on every run, which is
what makes a stored result quotable and a support conversation possible.

Three buckets, matching three different things a reader needs:

``reasons``  What was established in the student's favour.
``gaps``     What could not be evaluated. Never a failure - these are the honest
             limits of the available data.
``blockers`` What definitively disqualifies the student. Only ever populated
             when eligibility is INELIGIBLE.

Codes are stable identifiers. The message is a presentation detail and may be
reworded without a version bump; a code changing meaning requires one.
"""

from __future__ import annotations

from .constants import FIT_COMPONENT_LABELS
from .types import Reason


#: code -> template. ``{placeholders}`` are filled only from stored values.
REASON_TEMPLATES: dict[str, str] = {
    # Academic
    "ACADEMIC_ABOVE_MINIMUM": "Your academic result is above the published benchmark for this scholarship.",
    "ACADEMIC_MEETS_MINIMUM": "Your academic result meets the published minimum.",
    "ACADEMIC_AT_PUBLISHED_MINIMUM": (
        "Your academic result meets the published minimum but sits below the published benchmark."
    ),
    "ACADEMIC_NO_PUBLISHED_MINIMUM": (
        "This scholarship publishes no academic minimum, so your result is reported as supplied."
    ),
    "ACADEMIC_SCALE_MISMATCH": (
        "The published minimum uses a different grading scale from your result, so it was not compared."
    ),
    "ACADEMIC_RESULT_NOT_PROVIDED": "No academic result was supplied, so academic fit was not evaluated.",
    "ACADEMIC_SUBJECT_MATCH": "Your {field} subject result matches the programme field.",
    # Field
    "FIELD_EXACT": "Your field of study matches the published programme field.",
    "FIELD_RELATED": "Your field of study is related to the published programme field.",
    "FIELD_UNRELATED": "Your field of study is a different discipline from the published programme field.",
    "FIELD_NOT_PUBLISHED": "This scholarship does not publish a programme field, so field fit was not evaluated.",
    "FIELD_NOT_PROVIDED": "No field of study was supplied, so field fit was not evaluated.",
    # Funding
    "FUNDING_FULL_MATCH": "The funding structure matches your funding requirement.",
    "FUNDING_TUITION_MATCH": "This scholarship covers the tuition you need covered.",
    "FUNDING_PARTIAL": "This scholarship offers partial funding only.",
    "FUNDING_NONE": "This scholarship offers no funding.",
    "FUNDING_UNKNOWN": (
        "This scholarship's funding coverage could not be established from verified data."
    ),
    # Requirement
    "REQUIREMENTS_DOCUMENTED": "This scholarship publishes a clear list of required documents.",
    "REQUIREMENTS_PUBLISHED": "This scholarship publishes {count} condition(s) ScholarZone could evaluate.",
    "REQUIREMENT_UNKNOWN": "{count} published condition(s) could not be evaluated.",
    # Language
    "LANGUAGE_MEETS_REQUIREMENT": "Your language score meets the published threshold.",
    "LANGUAGE_EXCEEDS_REQUIREMENT": "Your language score is above the published threshold.",
    "LANGUAGE_NOT_REQUIRED": "This scholarship states that a language test is not a requirement.",
    "LANGUAGE_NOT_PROVIDED": "No language test was supplied, so the published threshold could not be checked.",
    "LANGUAGE_TEST_MISMATCH": (
        "You supplied a different language test from the one this scholarship publishes, and "
        "ScholarZone does not convert between tests."
    ),
    "LANGUAGE_NOT_PUBLISHED": "This scholarship publishes no language requirement.",
    # Preference
    "PREFERENCE_COUNTRY_MATCH": "This scholarship is in one of your preferred countries.",
    "PREFERENCE_COUNTRY_MISMATCH": "This scholarship is not in your preferred countries.",
    "PREFERENCE_NOT_PROVIDED": "No country preference was supplied, so preference fit was not evaluated.",
    # Timing
    "DEADLINE_APPROACHING": "There is a reasonable amount of time to apply.",
    "DEADLINE_COMFORTABLE": "There is comfortable time to apply.",
    "DEADLINE_WORKABLE": "The remaining window is workable.",
    "DEADLINE_TIGHT": "The deadline is close.",
    "DEADLINE_URGENT": "The deadline is imminent. Verify the official page before investing effort.",
    "DEADLINE_SOON": "The deadline is approaching.",
    "DEADLINE_APPROXIMATE": (
        "The published deadline states a month rather than a day, so the remaining time is approximate."
    ),
    "DEADLINE_ROLLING": "This scholarship publishes a rolling or recurring deadline rather than a fixed date.",
    "DEADLINE_NOT_PUBLISHED": "No fixed application deadline is published for this scholarship.",
    "DEADLINE_CLOSED": "This scholarship round is closed.",
    # Eligibility
    "ELIGIBILITY_VERIFIED": "Every published mandatory condition was checked and satisfied.",
    "ELIGIBILITY_NO_PUBLISHED_CONDITIONS": "This scholarship publishes no mandatory conditions.",
    "ELIGIBILITY_NEEDS_VERIFICATION": (
        "{count} mandatory condition(s) could not be checked against the information supplied."
    ),
    "ELIGIBILITY_BLOCKED": "{count} published mandatory condition(s) are not met.",
    "NATIONALITY_BLOCKED": "Your nationality does not satisfy the published citizenship requirement.",
    "AGE_BLOCKED": "Your age does not satisfy the published age limit.",
    "DEGREE_LEVEL_BLOCKED": "Your degree level does not satisfy the published requirement.",
    "ACADEMIC_MINIMUM_BLOCKED": "Your academic result is below the published minimum.",
    "LANGUAGE_MINIMUM_BLOCKED": "Your language score is below the published minimum.",
    "PROGRAMME_RESTRICTION_BLOCKED": "Your intended programme is outside the published restriction.",
    "STUDY_MODE_BLOCKED": "Your intended study mode does not match the published condition.",
    "APPLICATION_WINDOW_BLOCKED": "This scholarship round is closed.",
    # Confidence / evidence
    "SOURCE_INCOMPLETE": "Some of this scholarship's published details are missing from the catalogue.",
    "SOURCE_UNVERIFIED": "This scholarship has not been marked verified in the catalogue.",
    "CONFIDENCE_LOW": "The available information for this scholarship is limited, so confidence is low.",
    "CONFIDENCE_MEDIUM": "Some of this scholarship's published details are missing, so confidence is medium.",
}


def reason(code: str, component: str | None = None, **fields) -> Reason:
    """Render one reason from its template.

    An unknown code renders as the code itself rather than raising, so a new code
    can be added to a scorer before its template exists and the failure is
    visible instead of fatal.
    """
    template = REASON_TEMPLATES.get(code)
    if template is None:
        return Reason(code=code, message=code, component=component)
    try:
        message = template.format(**fields)
    except (KeyError, IndexError):
        message = template
    return Reason(code=code, message=message, component=component)


def component_label(component: str) -> str:
    return FIT_COMPONENT_LABELS.get(component, component.replace("_", " ").title())


def join_quotes(quotes: list[str], limit: int = 3) -> str:
    """Join up to ``limit`` provider quotes into one evidence line."""
    unique = [quote for quote in dict.fromkeys(q for q in quotes if q)]
    if not unique:
        return ""
    shown = unique[:limit]
    suffix = f" (+{len(unique) - limit} more)" if len(unique) > limit else ""
    return " ".join(shown) + suffix


__all__ = ["REASON_TEMPLATES", "component_label", "join_quotes", "reason"]