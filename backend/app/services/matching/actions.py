"""Next best actions.

A result that identifies a problem without suggesting what to do about it is
only half an answer. Each action below is produced from something the record or
the profile actually contains, and two rules keep the list honest:

* **Nothing is invented.** A document is named only when the record names it. No
  action ever asserts that the student possesses something.
* **Actions are ordered, not dumped.** Priority 10 is "resolve the thing that
  could disqualify you"; priority 90 is "read the official page". The first
  action is the one worth doing next.

The action list is derived from the gaps and the eligibility verdict rather than
re-derived from the raw record, which is what keeps it consistent with everything
else on the card: an action never contradicts a gap the same card is showing.
"""

from __future__ import annotations

from .gaps import GAP_TEMPLATES, category_of
from .types import ActionItem, EligibilityStatus, Gap


#: Priority bands. Named so the ordering rule is legible rather than implied by
#: scattered integers.
PRIORITY_BLOCKER = 10
PRIORITY_UNVERIFIED = 20
PRIORITY_MISSING_USER_DATA = 30
PRIORITY_RECORD_GAP = 50
PRIORITY_PREPARE = 60
PRIORITY_READ_SOURCE = 80
PRIORITY_VISIT_SOURCE = 90


#: Actions keyed by the gap code that raises them. A gap with no entry produces no
#: action, which is deliberate: silence is better than a generic suggestion.
GAP_ACTIONS: dict[str, str] = {
    "ACADEMIC_RESULT_NOT_PROVIDED": "Add your academic result to your profile, then recalculate.",
    "ACADEMIC_SCALE_MISMATCH": (
        "Check the grading scale this scholarship states, and add your result on that same scale if you can."
    ),
    "FIELD_NOT_PROVIDED": "Add your field of study to your profile, then recalculate.",
    "FIELD_NOT_PUBLISHED": (
        "Check the awarding body's programme list, since this record does not publish a resolvable field."
    ),
    "FIELD_UNKNOWN": (
        "Check the awarding body's programme list, since the programme field is not structured here."
    ),
    "FUNDING_UNKNOWN": (
        "Check what the awarding body's page actually covers, since funding coverage is not structured here."
    ),
    "FUNDING_NOT_FULLY_STRUCTURED": "Read the benefits section to confirm exactly what the award covers.",
    "LANGUAGE_NOT_PROVIDED": "Add your language test score to your profile, then recalculate.",
    "LANGUAGE_TEST_MISMATCH": (
        "Check which tests the awarding body accepts; ScholarZone does not convert between tests."
    ),
    "LANGUAGE_NO_SURPLUS_RANGE": (
        "Compare your score with the published threshold directly on the awarding body's page."
    ),
    "LANGUAGE_NOT_PUBLISHED": "Check the awarding body's page for any language requirement.",
    "PREFERENCE_NOT_PROVIDED": "Add your preferred countries to sharpen the ordering of your results.",
    "DEADLINE_NOT_PUBLISHED": "Check the awarding body's page for the current application deadline.",
    "DEADLINE_ROLLING": "Check the awarding body's page for the current round and its deadline.",
    "DEADLINE_MONTH_PRECISION": (
        "Confirm the exact closing date with the awarding body before relying on the approximate figure."
    ),
    "DEADLINE_CLOSED": "Look for the next round of this scholarship.",
    "ELIGIBILITY_NEEDS_VERIFICATION": "Work through the unverified conditions listed on this card.",
    "NATIONALITY_NEEDS_VERIFICATION": "Confirm your citizenship is on the awarding body's eligible-country list.",
    "AGE_NEEDS_VERIFICATION": "Check the published age limit on the awarding body's page.",
    "STUDY_MODE_NEEDS_VERIFICATION": "Check the published study-mode condition on the awarding body's page.",
    "DEGREE_LEVEL_NEEDS_VERIFICATION": "Check which degree levels this scholarship accepts.",
    "DEGREE_LEVEL_NOT_PROVIDED": "Add your intended degree level so degree-level conditions can be checked.",
    "PROGRAMME_RESTRICTION_NEEDS_VERIFICATION": (
        "Confirm your programme is the one named in this scholarship's eligibility section."
    ),
    "REQUIREMENT_UNKNOWN": "Read the eligibility section for conditions the catalogue could not structure.",
    "SOURCE_INCOMPLETE": "Check the awarding body's page for anything missing from this record.",
    "SOURCE_UNVERIFIED": "Treat this record as unconfirmed and verify it on the awarding body's page.",
    "CONFIDENCE_LOW": (
        "Treat this result as provisional. Confirm the details on the awarding body's page before applying."
    ),
    "CONFIDENCE_MEDIUM": "Spot-check the published details on the awarding body's page.",
}

_CATEGORY_PRIORITY = {
    "UNVERIFIED": PRIORITY_UNVERIFIED,
    "MISSING_USER_INFORMATION": PRIORITY_MISSING_USER_DATA,
    "MISSING_SCHOLARSHIP_DATA": PRIORITY_RECORD_GAP,
    "KNOWN_GAP": PRIORITY_RECORD_GAP,
}


def actions_from_gaps(gaps: list[Gap], limit: int = 4) -> list[ActionItem]:
    """Turn gaps into ordered, deduplicated actions.

    Ordered by priority first so the most consequential unresolved item leads,
    then by first appearance so the ordering is stable for identical inputs.
    """
    items: list[ActionItem] = []
    seen: set[str] = set()

    for item in gaps:
        message = GAP_ACTIONS.get(item.code)
        if message is None or item.code in seen:
            continue
        seen.add(item.code)
        items.append(
            ActionItem(
                code=f"ACTION_{item.code}",
                message=message,
                priority=_CATEGORY_PRIORITY.get(category_of(item.code), PRIORITY_RECORD_GAP),
            )
        )

    items.sort(key=lambda entry: entry.priority)
    return items[:limit]


def build_actions(
    gaps: list[Gap],
    eligibility: EligibilityStatus,
    official_source_url: str | None,
    blocker_count: int,
    document_count: int,
) -> list[ActionItem]:
    """The complete, ordered action list for one result.

    The official-source action is only ever produced when the record actually
    carries a URL. Inventing one - or rendering a button that goes nowhere -
    would be worse than omitting it.
    """
    actions = actions_from_gaps(gaps)

    if eligibility is EligibilityStatus.INELIGIBLE:
        actions.insert(
            0,
            ActionItem(
                code="ACTION_REVIEW_BLOCKING_CONDITION",
                message=(
                    "Review the eligibility section on the awarding body's page: a published mandatory "
                    "condition does not apply to you, and no score can change that."
                ),
                priority=PRIORITY_BLOCKER,
            ),
        )
    elif blocker_count:
        actions.insert(
            0,
            ActionItem(
                code="ACTION_REVIEW_BLOCKING_CONDITION",
                message="Review the conditions listed on this card before applying.",
                priority=PRIORITY_BLOCKER,
            ),
        )

    if document_count:
        actions.append(
            ActionItem(
                code="ACTION_PREPARE_DOCUMENTS",
                message=f"Prepare the {document_count} document(s) this scholarship publishes as required.",
                priority=PRIORITY_PREPARE,
            )
        )

    if official_source_url:
        actions.append(
            ActionItem(
                code="ACTION_VISIT_OFFICIAL_SOURCE",
                message="Open the official application page and confirm the details for this round.",
                url=official_source_url,
                url_label="Visit Official Source",
                priority=PRIORITY_VISIT_SOURCE,
            )
        )

    actions.sort(key=lambda entry: entry.priority)

    seen: set[str] = set()
    unique: list[ActionItem] = []
    for entry in actions:
        if entry.code in seen:
            continue
        seen.add(entry.code)
        unique.append(entry)

    return unique


__all__ = [
    "GAP_ACTIONS",
    "PRIORITY_BLOCKER",
    "PRIORITY_MISSING_USER_DATA",
    "PRIORITY_PREPARE",
    "PRIORITY_READ_SOURCE",
    "PRIORITY_RECORD_GAP",
    "PRIORITY_UNVERIFIED",
    "PRIORITY_VISIT_SOURCE",
    "actions_from_gaps",
    "build_actions",
]


# Re-exported so callers can check that a gap code has a defined template without
# importing the gaps module directly.
GAP_CODES_WITH_ACTIONS = frozenset(GAP_ACTIONS)
assert GAP_CODES_WITH_ACTIONS.issubset(GAP_TEMPLATES), (
    "Every action must be raised by a gap that has a template; an action with no "
    "gap would be an instruction the interface cannot justify."
)