"""Application readiness: "how ready is this student to act on this right now?"

This is a third number, deliberately distinct from the other two:

* **fit** asks how closely the student's profile matches the published
  requirements;
* **confidence** asks how trustworthy the scholarship record is;
* **readiness** asks how much of the application preparation the available
  evidence actually covers.

Conflating them is how a product ends up telling a student their readiness of
72% means they have a 72% chance. It does not. Nothing here is an outcome
prediction, and the layer is reported separately precisely so it cannot be read
as one.

LOCKED weights, renormalised across whatever could be evaluated, exactly as the
fit engine renormalises over its evaluated components:

    Eligibility certainty         30%
    Requirement completeness      20%
    Language readiness            15%
    Application/source readiness  15%
    Deadline readiness            20%

When no readiness component can be evaluated the score is ``None``. Reporting
``0`` would claim the student is unprepared when the truth is that there was
nothing to measure.

Two rules govern every component:

* **Missing information is unevaluated, not zero.** A published language
  requirement with no credential supplied makes language readiness NOT_EVALUATED,
  because the student may well hold an equivalent score ScholarZone cannot read.
  It is not zero, and it is not a penalty.
* **A confirmed failure is a real zero.** A language score below the published
  minimum, or a closed round, genuinely is zero readiness. That is a different
  state and the interface says so.

The module never claims the student possesses a document. "Requirement
completeness" measures how many published conditions the supplied profile can
answer; it never asserts that a transcript exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import (
    READINESS_BANDS,
    READINESS_COMPONENT_LABELS,
    READINESS_COMPONENT_ORDER,
    READINESS_WEIGHTS,
    clamp,
)
from .normalize import NormalisedProfile
from .types import (
    ComponentStatus,
    EligibilityResult,
    EligibilityStatus,
    ReadinessComponent,
    ReadinessResult,
)


#: The confidence penalty applied per unresolved mandatory condition. A record
#: where every published condition was checked is certain; one where none could be
#: checked is not.
READINESS_UNVERIFIED_PENALTY = 40.0

#: Deadline readiness thresholds, as (minimum days remaining, score). Read once,
#: in one place, so the readiness layer and the timing component cannot disagree
#: about what "comfortable" means.
READINESS_DEADLINE_BANDS: tuple[tuple[int, float], ...] = (
    (60, 100.0),
    (30, 85.0),
    (14, 65.0),
    (7, 45.0),
    (1, 25.0),
)

#: Readiness where a published condition could not be checked at all, and no other
#: condition was published. Low, but not zero: nothing has been disproved.
READINESS_UNCHECKED_CEILING = 60.0


@dataclass(frozen=True)
class _Draft:
    """A readiness component before weight renormalisation."""

    name: str
    score: float | None
    detail: str


def _draft(name: str, score: float | None, detail: str) -> _Draft:
    return _Draft(name=name, score=clamp(score) if score is not None else None, detail=detail)


def _eligibility_certainty(eligibility: EligibilityResult) -> _Draft:
    """How certain the eligibility verdict is.

    ELIGIBLE means every published condition was checked, so it is full credit.
    NEEDS_VERIFICATION is discounted in proportion to how much of the published
    surface went unchecked. INELIGIBLE is zero: there is nothing left to be ready
    for, and reporting readiness on a record the gate already refused would be
    incoherent.
    """
    if eligibility.status is EligibilityStatus.INELIGIBLE:
        return _draft(
            "eligibility_certainty",
            0.0,
            "A published mandatory condition is not met, so there is no application to be ready for.",
        )

    if eligibility.status is EligibilityStatus.ELIGIBLE:
        if eligibility.satisfied:
            return _draft(
                "eligibility_certainty",
                100.0,
                "Every published mandatory condition was checked and satisfied.",
            )
        return _draft(
            "eligibility_certainty",
            100.0,
            "This scholarship publishes no mandatory conditions, so nothing blocks an application.",
        )

    unchecked = len(eligibility.unverified)
    checked = len(eligibility.satisfied)
    total = unchecked + checked
    if total == 0:
        return _draft(
            "eligibility_certainty",
            READINESS_UNCHECKED_CEILING,
            (
                "A published mandatory condition could not be checked against the information supplied. "
                "Nothing has been disproved."
            ),
        )

    score = 100.0 - READINESS_UNVERIFIED_PENALTY * (unchecked / total)
    return _draft(
        "eligibility_certainty",
        score,
        (
            f"{checked} of {total} published mandatory condition(s) could be checked. "
            f"{unchecked} still need verifying."
        ),
    )


def _requirement_completeness(eligibility: EligibilityResult) -> _Draft:
    """How much of the published condition surface the profile can answer.

    This is the student's completeness, not the record's. A condition the
    supplied profile can answer counts; one it cannot, and one it fails, both
    reduce readiness, because in both cases the student has work to do before
    applying.

    A record that publishes no conditions produces no component at all: there is
    nothing for the student to complete, and inventing a score would imply there
    was.
    """
    total = len(eligibility.satisfied) + len(eligibility.unverified) + len(eligibility.blockers)
    if total == 0:
        return _draft(
            "requirement_completeness",
            None,
            "This scholarship publishes no conditions for you to work through.",
        )

    answered = len(eligibility.satisfied)
    return _draft(
        "requirement_completeness",
        100.0 * answered / total,
        (
            f"You can answer {answered} of {total} published condition(s) from the information supplied."
        ),
    )


def _language_readiness(language_state: str | None, language_detail: str, not_required: bool) -> _Draft:
    """Whether the student actually meets a published language threshold.

    Only the same test is compared; no conversion is attempted. A mismatch or an
    absent credential is NOT_EVALUATED rather than zero, because holding a
    different test may well satisfy the requirement and ScholarZone has no
    authoritative equivalency to say so. A score genuinely below the published
    minimum is a real zero.
    """
    if not_required:
        return _draft(
            "language_readiness",
            None,
            "This scholarship states that a language test is not a requirement.",
        )
    if language_state is None:
        return _draft(
            "language_readiness",
            None,
            "This scholarship publishes no language requirement to prepare for.",
        )
    if language_state == "MEETS":
        return _draft("language_readiness", 100.0, language_detail)
    if language_state == "BELOW":
        return _draft("language_readiness", 0.0, language_detail)
    return _draft(
        "language_readiness",
        None,
        (
            "A language requirement is published but could not be checked. "
            "Verify it on the awarding body's page."
        ),
    )


def _application_readiness(facts, document_count: int) -> _Draft:
    """Whether there is a usable application route, and a known document list.

    Two distinct facts, both from the record. Neither says anything about what
    the student possesses: a published document list is what the awarding body
    asks for, and this component reports that it is known, not that it is held.
    """
    has_source = bool(facts.official_source_url or facts.official_source)

    if not has_source:
        return _draft(
            "application_readiness",
            0.0,
            "No official source is recorded for this scholarship, so the application route could not be established.",
        )

    if document_count > 0:
        return _draft(
            "application_readiness",
            100.0,
            (
                f"An official source is recorded and the record publishes {document_count} document(s) to "
                "prepare."
            ),
        )

    return _draft(
        "application_readiness",
        70.0,
        "An official source is recorded, but this record does not publish a document list.",
    )


def _deadline_readiness(
    days: int | None,
    closed: bool,
    kind: str | None,
    approximate: bool,
) -> _Draft:
    """Whether there is still usable time to apply.

    A closed round is a real zero. A rolling, annual or unpublished deadline is
    NOT_EVALUATED: the programme is open and there is simply no fixed date to
    count down to, which is not the same as being late. A month-precision date
    is measured from the end of the published month and labelled approximate,
    because presenting it as an exact number of days would overstate our
    precision.
    """
    if closed:
        return _draft("deadline_readiness", 0.0, "This round is closed, so there is no time left to apply.")

    if days is None or kind in {"rolling", "recurring", "annual"}:
        return _draft(
            "deadline_readiness",
            None,
            "No fixed application deadline is published, so there is no countdown to be ready against.",
        )

    for lower_bound, score in READINESS_DEADLINE_BANDS:
        if days >= lower_bound:
            suffix = (
                " The published deadline names a month rather than a day, so this figure is approximate."
                if approximate
                else ""
            )
            return _draft(
                "deadline_readiness",
                score,
                f"There {'are approximately ' if approximate else 'are'} {days} days left to apply.{suffix}",
            )

    return _draft(
        "deadline_readiness",
        25.0,
        f"There {'are approximately ' if approximate else 'are'} {days} days left to apply.",
    )


def _band(score: float | None) -> tuple[str | None, str | None]:
    if score is None:
        return None, None
    for threshold, key, label in READINESS_BANDS:
        if score >= threshold:
            return key, label
    return READINESS_BANDS[-1][1], READINESS_BANDS[-1][2]


def compute_readiness(
    profile: NormalisedProfile,
    facts,
    eligibility: EligibilityResult,
    language_state: str | None,
    language_detail: str,
    language_not_required: bool,
    deadline_days: int | None,
    deadline_closed: bool,
    deadline_kind: str | None,
    deadline_approximate: bool,
) -> ReadinessResult:
    """Assemble the readiness layer for one record.

    Pure. Same inputs, same readiness, always.
    """
    document_count = len([item for item in (facts.documents or []) if item])

    drafts = {
        draft.name: draft
        for draft in (
            _eligibility_certainty(eligibility),
            _requirement_completeness(eligibility),
            _language_readiness(language_state, language_detail, language_not_required),
            _application_readiness(facts, document_count),
            _deadline_readiness(deadline_days, deadline_closed, deadline_kind, deadline_approximate),
        )
    }

    evaluated = [name for name in READINESS_COMPONENT_ORDER if drafts[name].score is not None]
    denominator = sum(READINESS_WEIGHTS[name] for name in evaluated)

    components: list[ReadinessComponent] = []
    numerator = 0.0
    for name in READINESS_COMPONENT_ORDER:
        draft = drafts[name]
        if draft.score is None:
            components.append(
                ReadinessComponent(
                    name=name,
                    label=READINESS_COMPONENT_LABELS[name],
                    weight=READINESS_WEIGHTS[name],
                    status=ComponentStatus.NOT_EVALUATED,
                    score=None,
                    detail=draft.detail,
                    effective_weight=None,
                    contribution=None,
                )
            )
            continue

        effective = READINESS_WEIGHTS[name] / denominator if denominator > 0 else 0.0
        contribution = effective * draft.score
        numerator += READINESS_WEIGHTS[name] * draft.score
        components.append(
            ReadinessComponent(
                name=name,
                label=READINESS_COMPONENT_LABELS[name],
                weight=READINESS_WEIGHTS[name],
                status=ComponentStatus.EVALUATED,
                score=round(draft.score, 1),
                detail=draft.detail,
                effective_weight=round(effective, 4),
                contribution=round(contribution, 2),
            )
        )

    if denominator > 0:
        score = round(clamp(numerator / denominator), 1)
        band, label = _band(score)
        detail = (
            f"{len(evaluated)} of {len(READINESS_COMPONENT_ORDER)} readiness components could be "
            "evaluated from the available evidence."
        )
    else:
        score, band, label = None, None, None
        detail = "No readiness component could be evaluated from the available evidence."

    return ReadinessResult(
        score=score,
        band=band,
        label=label,
        components=components,
        evaluated_coverage=round(clamp(denominator) * 100.0, 1),
        detail=detail,
    )


__all__ = [
    "READINESS_DEADLINE_BANDS",
    "READINESS_UNCHECKED_CEILING",
    "READINESS_UNVERIFIED_PENALTY",
    "compute_readiness",
]