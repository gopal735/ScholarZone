"""Profile strength: how complete the student's own input is.

This is emphatically not the fit score and not confidence. It answers a
question about the *request*, not about any scholarship:

    "Did you tell us enough to match you properly?"

Two students with an identical profile strength can have completely different
matches, and a strong profile does not make any particular scholarship a better
match for anyone. Reporting it beside the fit score without that framing would
invite exactly the reading the product refuses to make.

LOCKED weights:

    Academic 25% | Study goal 25% | Language 20% | Funding 20% | Identity 10%

Unlike the fit components, an absent field here is a real ``EVALUATED`` zero.
That is not a penalty and not a judgement: it is a measurement of completeness,
which is the entire question this layer asks. The reason it is safe to score
absence as zero here and must never be done in the fit engine is precisely that
completeness is the property being measured. When nothing at all was supplied the
score is ``None`` rather than 0, because then even the completeness measure is
undefined.
"""

from __future__ import annotations

from .config import (
    PROFILE_STRENGTH_BANDS,
    PROFILE_STRENGTH_LABELS,
    PROFILE_STRENGTH_WEIGHTS,
    clamp,
)
from .normalize import NormalisedProfile
from .types import (
    ComponentStatus,
    ProfileStrengthResult,
    ReadinessComponent,
    Reason,
)


#: Partial credit where a student supplied part of a group. Deliberately simple
#: and symmetric: each group is "how much of what could have been supplied was".
PARTIAL = 50.0


def _component(name: str, score: float, detail: str) -> tuple[str, tuple[float, str]]:
    return name, (clamp(score), detail)


def _measurements(profile: NormalisedProfile) -> dict[str, tuple[float, str]]:
    """Score each group from what the profile actually contains."""
    return dict(
        [
            _component(
                "academic",
                100.0
                if profile.overall_result is not None
                else (PARTIAL if profile.subject_results else 0.0),
                "An overall result was supplied."
                if profile.overall_result is not None
                else (
                    "Only subject results were supplied."
                    if profile.subject_results
                    else "No academic result was supplied."
                ),
            ),
            _component(
                "study_goal",
                (
                    100.0
                    if profile.intended_degree_level and profile.intended_field
                    else (PARTIAL if profile.intended_degree_level or profile.intended_field else 0.0)
                ),
                "A degree level and a field of study were supplied."
                if profile.intended_degree_level and profile.intended_field
                else (
                    "Only part of your study goal was supplied."
                    if profile.intended_degree_level or profile.intended_field
                    else "No study goal was supplied."
                ),
            ),
            _component(
                "language",
                100.0
                if any(score is not None for _, score, _ in profile.language_credentials)
                else (PARTIAL if profile.language_credentials else 0.0),
                "A language test with a score was supplied."
                if any(score is not None for _, score, _ in profile.language_credentials)
                else (
                    "A language test was named without a score."
                    if profile.language_credentials
                    else "No language test was supplied."
                ),
            ),
            _component(
                "funding",
                100.0
                if profile.funding_requirement
                else (PARTIAL if profile.living_cost_support_required is not None else 0.0),
                "A funding requirement was supplied."
                if profile.funding_requirement
                else (
                    "You stated whether you need living-cost support."
                    if profile.living_cost_support_required is not None
                    else "No funding requirement was supplied."
                ),
            ),
            _component(
                "identity",
                (
                    100.0
                    if profile.citizenship_code and profile.age is not None
                    else (PARTIAL if profile.citizenship_code or profile.age is not None else 0.0)
                ),
                "Your nationality and age were supplied."
                if profile.citizenship_code and profile.age is not None
                else (
                    "Only part of your identity details were supplied."
                    if profile.citizenship_code or profile.age is not None
                    else "No nationality or age was supplied."
                ),
            ),
        ]
    )


#: What each missing group costs in matching quality, stated as a suggestion and
#: never as a failure.
_IMPROVEMENT_TEMPLATES: dict[str, str] = {
    "academic": "Add your academic result so published academic minima can be compared with it.",
    "study_goal": "Add the degree level and field you want to study, so programme-level requirements can be checked.",
    "language": "Add your English test score so published language thresholds can be compared.",
    "funding": "Add your funding requirement so funding coverage can be compared with your need.",
    "identity": "Add your nationality and age so published eligibility conditions can be checked.",
}


def _band(score: float | None) -> tuple[str | None, str | None]:
    if score is None:
        return None, None
    for threshold, key, label in PROFILE_STRENGTH_BANDS:
        if score >= threshold:
            return key, label
    return PROFILE_STRENGTH_BANDS[-1][1], PROFILE_STRENGTH_BANDS[-1][2]


def compute_profile_strength(profile: NormalisedProfile) -> ProfileStrengthResult:
    """Measure the completeness of the supplied profile. Pure."""
    measurements = _measurements(profile)

    supplied_any = any(score > 0 for score, _ in measurements.values())
    denominator = sum(PROFILE_STRENGTH_WEIGHTS.values())

    components: list[ReadinessComponent] = []
    complete: list[str] = []
    improvements: list[Reason] = []
    numerator = 0.0

    for name in PROFILE_STRENGTH_WEIGHTS:
        score, detail = measurements[name]
        numerator += PROFILE_STRENGTH_WEIGHTS[name] * score
        effective = PROFILE_STRENGTH_WEIGHTS[name] / denominator
        components.append(
            ReadinessComponent(
                name=name,
                label=PROFILE_STRENGTH_LABELS[name],
                weight=PROFILE_STRENGTH_WEIGHTS[name],
                status=ComponentStatus.EVALUATED,
                score=round(score, 1),
                detail=detail,
                effective_weight=round(effective, 4),
                contribution=round(effective * score, 2),
            )
        )
        if score >= 100.0:
            complete.append(PROFILE_STRENGTH_LABELS[name])
        if score < 100.0:
            improvements.append(
                Reason(
                    code=f"PROFILE_STRENGTH_{name.upper()}_INCOMPLETE",
                    message=_IMPROVEMENT_TEMPLATES[name],
                    component=None,
                )
            )

    if not supplied_any:
        return ProfileStrengthResult(
            score=None,
            band=None,
            label=None,
            components=components,
            complete=[],
            improvements=improvements,
            detail=(
                "No profile information was supplied, so matching quality could not be measured. Every "
                "scholarship is reported as not evaluated rather than as a poor match."
            ),
        )

    score = round(clamp(numerator / denominator), 1)
    band, label = _band(score)

    return ProfileStrengthResult(
        score=score,
        band=band,
        label=label,
        components=components,
        complete=complete,
        improvements=improvements,
        detail=(
            "This measures how much of your profile was supplied, so that matching quality can be judged. "
            "It is not a fit score and it is not a prediction."
        ),
    )


__all__ = ["compute_profile_strength"]