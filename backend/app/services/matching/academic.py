"""Academic fit and the Academic Profile Index comparison.

The comparison this module performs is deliberately narrow: it answers "does the
published minimum compare directly to what the student supplied?" and, when it
does, how much headroom there is.

The one thing it will not do is convert between grading systems. A scholarship
publishing "minimum 3.5/4.0" and a student supplying "3.6/5.0" produce
``INCOMPARABLE``. Inventing the conversion would be the single easiest way for
this feature to state something false with total confidence, and the resulting
number would be indistinguishable from a real comparison.

Monotonicity is a tested property: raising a student's mark from below a
published minimum to above it can only raise the academic fit score, never lower
it. That is enforced structurally here, because the piecewise mapping below has
no decreasing branch.

Two distinct published-anchor cases, and the difference matters:

* **Minimum and a preferred benchmark are both published.** The score is the
  locked interpolation ``100 x (student - minimum) / (preferred - minimum)``,
  clamped to 0-100. Meeting the minimum exactly therefore scores 0 on this
  component and reaching the benchmark scores 100. That is the intended reading:
  when an awarding body publishes a benchmark, the distance to it is the
  evidence. Eligibility is decided separately and is not affected.
* **Only a minimum is published.** There is no second anchor and none is
  invented, so the student receives the documented ``ACADEMIC_MINIMUM_ONLY_SCORE``.
  There is no published evidence of anything better to award.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import (
    ACADEMIC_HEADROOM_DISPLAY_SCALE,
    ACADEMIC_MINIMUM_ONLY_SCORE,
    clamp,
)
from .normalize import SCALE_MAXIMA, NormalisedProfile
from .types import AcademicMark, GradingScale, NormalisedRequirement


@dataclass(frozen=True)
class MinimumComparison:
    """The result of comparing a student mark to a published minimum."""

    #: ``ABOVE_PREFERRED`` | ``MEETS_MINIMUM`` | ``BELOW_MINIMUM`` |
    #: ``INCOMPARABLE`` | ``STUDENT_MARK_UNKNOWN`` | ``NO_MINIMUM_PUBLISHED``
    state: str
    detail: str
    score: float | None = None
    headroom: float | None = None
    #: Echoes the two scales that were compared, for the transparency panel.
    student_scale: str | None = None
    requirement_scale: str | None = None


def requirement_maximum(scale: GradingScale | None) -> float | None:
    """The denominator for a published minimum on its stated scale."""
    if scale is None:
        return None
    return SCALE_MAXIMA.get(scale)


def student_result_on_scale(profile: NormalisedProfile, scale: GradingScale) -> float | None:
    """The student's overall result expressed on a specific scale.

    Returns ``None`` unless the student's declared scale *is* the requested
    scale. Re-projecting a 0-100 normalised value back onto a 4.0 scale would be
    exactly the guessed conversion this engine refuses.
    """
    if profile.overall_result is None:
        return None

    declared = profile.overall_scale_label
    if declared == scale.value:
        return profile.overall_result
    if declared == "letter band (approximate)":
        # A letter band carries no comparable numeric denominator.
        return None
    return None


def compare_to_minimum(profile: NormalisedProfile, requirement: NormalisedRequirement) -> MinimumComparison:
    """Compare the student's academic result to a published minimum."""
    scale = requirement.scale
    if scale is None or scale is GradingScale.UNKNOWN:
        return MinimumComparison(
            state="INCOMPARABLE",
            detail=(
                "The published academic minimum does not state a grading scale, so it cannot be "
                "compared with the result supplied."
            ),
            requirement_scale=None,
        )

    maximum = requirement_maximum(scale)
    if maximum is None:
        return MinimumComparison(
            state="INCOMPARABLE",
            detail="The published academic minimum uses a grading scale ScholarZone cannot normalise.",
            requirement_scale=scale.value,
        )

    student_scale_label = profile.overall_scale_label
    if profile.overall_result is None or student_scale_label in {"unavailable", "letter band (approximate)"}:
        return MinimumComparison(
            state="STUDENT_MARK_UNKNOWN",
            detail=(
                "A minimum academic result is published, but no comparable academic result was supplied."
            ),
            requirement_scale=scale.value,
        )

    if student_scale_label != scale.value:
        return MinimumComparison(
            state="INCOMPARABLE",
            detail=(
                f"The published minimum is on the {scale.value} scale and the supplied result is on the "
                f"{student_scale_label} scale. No official conversion between them exists, so this "
                "requirement was not evaluated."
            ),
            student_scale=student_scale_label,
            requirement_scale=scale.value,
        )

    # Same scale: compare like for like.
    #
    # Both sides are put on 0-100 using the same denominator. The student's
    # result is already normalised by ``normalise_numeric_mark``; the published
    # figures are raw values on the declared scale, so they are rescaled here.
    # Rescaling both by the same maximum is an arithmetic identity, not a
    # conversion between grading systems.
    published = requirement.minimum_value or 0.0
    published_normalised = published / maximum * 100.0
    if profile.overall_result < published_normalised:
        return MinimumComparison(
            state="BELOW_MINIMUM",
            detail=(
                f"Your supplied result is below the published minimum of {requirement.minimum_value:g} "
                f"on the {scale.value} scale."
            ),
            student_scale=student_scale_label,
            requirement_scale=scale.value,
        )

    preferred = requirement.preferred_value
    if preferred is not None and preferred > published:
        preferred_normalised = preferred / maximum * 100.0
        if profile.overall_result >= preferred_normalised:
            return MinimumComparison(
                state="ABOVE_PREFERRED",
                detail=(
                    f"Your supplied result meets or exceeds the published benchmark of "
                    f"{preferred:g} on the {scale.value} scale."
                ),
                score=100.0,
                headroom=round(profile.overall_result - published_normalised, 1),
                student_scale=student_scale_label,
                requirement_scale=scale.value,
            )
        # LOCKED formula for the case where both anchors are published:
        #
        #     C = 100 x (student - minimum) / (preferred - minimum)   clamped 0-100
        #
        # Both anchors exist in the record, so neither is invented. A consequence
        # worth stating plainly, because it is visible in the product: a student
        # sitting exactly on the published minimum scores 0 on this component,
        # while a student at the published benchmark scores 100. Meeting a floor
        # and reaching a stated standard are different achievements, and when the
        # awarding body published a benchmark, the distance to it is the
        # evidence. Eligibility is unaffected - such a student is ELIGIBLE, and
        # the gate says so independently of this score.
        span = preferred_normalised - published_normalised
        ratio = (profile.overall_result - published_normalised) / span if span > 0 else 1.0
        score = clamp(100.0 * ratio)
        return MinimumComparison(
            state="MEETS_MINIMUM",
            detail=(
                f"Your supplied result meets the published minimum of {published:g} and sits below the "
                f"published benchmark of {preferred:g} on the {scale.value} scale."
            ),
            score=round(score, 1),
            headroom=round(profile.overall_result - published_normalised, 1),
            student_scale=student_scale_label,
            requirement_scale=scale.value,
        )

    return MinimumComparison(
        state="MEETS_MINIMUM",
        detail=(
            f"Your supplied result meets the published minimum of {published:g} on the "
            f"{scale.value} scale. No higher benchmark is published, so no additional score is awarded "
            "beyond meeting the stated requirement."
        ),
        score=ACADEMIC_MINIMUM_ONLY_SCORE,
        headroom=round(profile.overall_result - published_normalised, 1),
        student_scale=student_scale_label,
        requirement_scale=scale.value,
    )


def academic_fit(
    profile: NormalisedProfile,
    requirement: NormalisedRequirement | None,
    minimum_absent_by_publication: bool,
) -> tuple[float | None, str, dict]:
    """Score the academic dimension.

    Returns ``(score_or_None, detail, evidence)``. ``score is None`` means the
    dimension is NOT_EVALUATED and its weight will be redistributed; it never
    means zero.

    Three outcomes are possible and they are genuinely different:

    * The provider published no numeric minimum. The dimension is scored from
      the student's own academic profile against a fixed, documented reference
      band, and the reason code says plainly that no published minimum exists.
      A scholarship that states it does not grade applicants should not be
      punished as though the student had failed.
    * A minimum was published and is comparable: scored against it.
    * A minimum was published but is not comparable, or the student supplied
      nothing: NOT_EVALUATED.
    """
    if requirement is None and minimum_absent_by_publication:
        if profile.overall_result is None:
            return (
                None,
                "This scholarship publishes no academic minimum, and no academic result was supplied.",
                {"basis": "no_published_minimum", "student_result": None},
            )
        score = profile.overall_result
        return (
            round(score, 1),
            (
                "This scholarship publishes no academic minimum. Your academic result is shown as "
                "supplied, without a published threshold to compare it against."
            ),
            {
                "basis": "no_published_minimum",
                "student_result": round(profile.overall_result, 1),
                "scale": profile.overall_scale_label,
            },
        )

    if requirement is None:
        if profile.overall_result is None:
            return (
                None,
                "No published academic minimum and no academic result supplied, so academic fit was not evaluated.",
                {"basis": "no_requirement_no_result"},
            )
        return (
            round(profile.overall_result, 1),
            "No academic minimum is published for this scholarship, so your supplied result is reported as provided.",
            {
                "basis": "no_requirement",
                "student_result": round(profile.overall_result, 1),
                "scale": profile.overall_scale_label,
            },
        )

    comparison = compare_to_minimum(profile, requirement)
    if comparison.score is None:
        return (
            None,
            comparison.detail,
            {
                "basis": "minimum_published",
                "state": comparison.state,
                "published_minimum": requirement.minimum_value,
                "published_scale": comparison.requirement_scale,
                "student_scale": comparison.student_scale,
                "quote": requirement.raw_quote,
            },
        )

    return (
        comparison.score,
        comparison.detail,
        {
            "basis": "minimum_published",
            "state": comparison.state,
            "published_minimum": requirement.minimum_value,
            "published_scale": comparison.requirement_scale,
            "student_scale": comparison.student_scale,
            "headroom": comparison.headroom,
            "quote": requirement.raw_quote,
        },
    )


def relevant_subject_component(profile: NormalisedProfile, resolution) -> tuple[float | None, str]:
    """Fold the student's mark in the relevant field into the academic index.

    Only marks whose subject resolves to the same canonical field as the target
    programme count. An unrelated subject mark is not evidence about the
    programme the student is applying to.
    """
    if not profile.subject_results:
        return None, "No subject results supplied."
    if resolution is None or resolution.key is None:
        return None, "The programme field could not be resolved, so subject results were not matched."

    matched = [value for key, value in profile.subject_results.items() if key == resolution.key]
    if not matched:
        return None, (
            f"No supplied subject result matched {resolution.label}, so subject performance was not used."
        )
    average = sum(matched) / len(matched)
    return round(average, 1), f"Average of {len(matched)} {resolution.label} subject result(s)."


__all__ = [
    "ACADEMIC_HEADROOM_DISPLAY_SCALE",
    "MinimumComparison",
    "academic_fit",
    "compare_to_minimum",
    "relevant_subject_component",
    "requirement_maximum",
    "student_result_on_scale",
]