"""The hard eligibility gate.

This runs before any fit scoring and its verdict is not advisory. Three rules
define its behaviour:

1. **One confirmed violation ends it.** If a published mandatory condition is
   definitively violated, the result is INELIGIBLE. Nothing downstream - not fit,
   not confidence, not a high score on every other dimension - can move that.

2. **A mandatory condition that cannot be evaluated is its own answer.**
   NEEDS_VERIFICATION means the published rule exists and could not be checked
   against the supplied profile. It is deliberately distinct from INELIGIBLE:
   telling a student they are ineligible because we lack their nationality is a
   claim the data does not support, and telling them they are eligible would be
   worse.

3. **Silence is not a rule.** A requirement that was never published produces no
   gate at all. Only conditions actually read out of the record are enforced.

The gate reasons over published requirements and the supplied profile only. It
never consults a fit score, and no function in this module accepts one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import ELIGIBILITY_RANK
from .normalize import NormalisedProfile
from .requirements import ReadRequirements
from .types import (
    EligibilityResult,
    EligibilityStatus,
    FundingState,
    RequirementKind,
    RequirementOutcome,
    RequirementStatus,
    ScholarshipFacts,
)


@dataclass(frozen=True)
class DeadlineEvaluation:
    """Timing facts, resolved once and shared by the gate and the timer scorer."""

    #: ``None`` means no trustworthy fixed deadline exists.
    days_remaining: int | None
    precision: str
    kind: str
    #: True only when the record is a closed round the student cannot apply to.
    closed: bool


def _outcome(
    requirement,
    status: RequirementStatus,
    summary: str,
) -> RequirementOutcome:
    return RequirementOutcome(
        kind=requirement.kind,
        status=status,
        summary=summary,
        raw_quote=requirement.raw_quote,
        provenance_url=requirement.provenance_url,
    )


def evaluate_deadline(facts: ScholarshipFacts, as_of) -> DeadlineEvaluation:
    """Resolve deadline facts using ScholarZone's own deadline semantics.

    Reuses ``classify_deadline_text`` rather than introducing a second deadline
    model. A rolling or annual deadline has no fixed date to count down to and is
    reported as such; a month-precision date is reported with its precision
    intact so the interface never presents it as exact.
    """
    from ..deadline_semantics import classify_deadline_text, coerce_deadline_precision

    text = facts.deadline_display or ""
    stored_precision = coerce_deadline_precision(facts.deadline_precision)
    text_kind = classify_deadline_text(text)

    precision = stored_precision
    if precision in {"unknown", "varies"}:
        precision = text_kind.value if text_kind.value != "unknown" else precision

    # A record can be marked closed by the lifecycle stage even with a future
    # date, so the stored status is honoured first.
    if facts.status == "closed":
        return DeadlineEvaluation(days_remaining=None, precision=precision, kind="closed", closed=True)

    if facts.deadline_date is None:
        # Rolling and recurring deadlines genuinely have no single date. They are
        # explicitly not a failure: the programme is open.
        return DeadlineEvaluation(
            days_remaining=None,
            precision=precision,
            kind=text_kind.value if text_kind.value != "unknown" else "none",
            closed=False,
        )

    try:
        from datetime import date as _date

        deadline = _date.fromisoformat(facts.deadline_date)
    except (TypeError, ValueError):
        return DeadlineEvaluation(days_remaining=None, precision=precision, kind="unparseable", closed=False)

    days = (deadline - as_of).days
    if days < 0:
        return DeadlineEvaluation(days_remaining=days, precision=precision, kind="closed", closed=True)

    return DeadlineEvaluation(days_remaining=days, precision=precision, kind=text_kind.value, closed=False)


def evaluate(
    profile: NormalisedProfile,
    facts: ScholarshipFacts,
    read: ReadRequirements,
    deadline: DeadlineEvaluation,
) -> EligibilityResult:
    """Evaluate every published mandatory condition against the profile.

    Conditions are evaluated in a fixed order, and the order is reported:

        1. application window
        2. academic minimum
        3. language minimum
        4. nationality
        5. age
        6. degree level
        7. study mode
        8. other explicit mandatory conditions (programme restriction)

    The order does not change the verdict - one confirmed violation anywhere is
    enough - but recording it means a reader can see which condition was checked
    first rather than inferring it.

    No function in this module accepts, reads or derives from a fit score. The
    gate is upstream of scoring and stays there.
    """
    blockers: list[RequirementOutcome] = []
    unverified: list[RequirementOutcome] = []
    satisfied: list[RequirementOutcome] = []
    gate_order: list[str] = []

    # ------------------------------------------------------------------
    # 1. Application window. A closed round is the one gate that cannot be
    #    argued with, so it is checked first.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.APPLICATION_WINDOW.value)
    if deadline.closed:
        blockers.append(
            RequirementOutcome(
                kind=RequirementKind.APPLICATION_WINDOW,
                status=RequirementStatus.FAIL,
                summary=(
                    "This scholarship round is closed, so applications are not being accepted."
                ),
                raw_quote=facts.deadline_display or facts.deadline_date or "Round closed",
                provenance_url=facts.official_source_url,
            )
        )

    # ------------------------------------------------------------------
    # 2. Academic minimum.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.ACADEMIC_MINIMUM.value)
    academic = read.academic_minimum
    if academic is not None:
        from .academic import compare_to_minimum

        comparison = compare_to_minimum(profile, academic)
        if comparison.state == "BELOW_MINIMUM":
            blockers.append(_outcome(academic, RequirementStatus.FAIL, comparison.detail))
        elif comparison.state in {"MEETS_MINIMUM", "ABOVE_PREFERRED"}:
            satisfied.append(_outcome(academic, RequirementStatus.MATCH, comparison.detail))
        else:
            # The minimum was published but the student's mark is absent or on a
            # different grading scale. Refusing to convert is not a failure and
            # it is not a pass either.
            unverified.append(_outcome(academic, RequirementStatus.UNKNOWN, comparison.detail))

    # ------------------------------------------------------------------
    # 3. Language minimum.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.LANGUAGE_MINIMUM.value)
    language = read.language_minimum
    if language is not None:
        from .components import compare_language

        comparison = compare_language(profile, language)
        if comparison.state == "MEETS":
            satisfied.append(_outcome(language, RequirementStatus.MATCH, comparison.detail))
        elif comparison.state == "BELOW":
            blockers.append(_outcome(language, RequirementStatus.FAIL, comparison.detail))
        else:
            unverified.append(_outcome(language, RequirementStatus.UNKNOWN, comparison.detail))

    # ------------------------------------------------------------------
    # 4. Nationality.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.NATIONALITY.value)
    nationality = read.nationality
    if nationality is not None:
        allowed = nationality.allowed_terms
        if not allowed:
            unverified.append(
                _outcome(
                    nationality,
                    RequirementStatus.UNKNOWN,
                    "The scholarship restricts eligibility by country, and the published restriction could not be enumerated.",
                )
            )
        elif allowed == ("DESIGNATED_SCHEME",):
            # A designated-country scheme is not a list we can check a
            # nationality against.
            unverified.append(
                _outcome(
                    nationality,
                    RequirementStatus.UNKNOWN,
                    (
                        "Eligibility is limited to nationals of a designated country list. "
                        "Confirm your citizenship is on the official list before applying."
                    ),
                )
            )
        elif profile.citizenship_code is None:
            unverified.append(
                _outcome(
                    nationality,
                    RequirementStatus.UNKNOWN,
                    "This scholarship has a published citizenship requirement. Provide your nationality to check it.",
                )
            )
        elif profile.citizenship_code in allowed:
            satisfied.append(
                _outcome(
                    nationality,
                    RequirementStatus.MATCH,
                    "Your nationality satisfies the published citizenship requirement.",
                )
            )
        else:
            blockers.append(
                _outcome(
                    nationality,
                    RequirementStatus.FAIL,
                    (
                        "This scholarship is restricted to a published set of nationalities that does not "
                        "include yours."
                    ),
                )
            )

    # ------------------------------------------------------------------
    # 5. Age.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.AGE.value)
    age = read.age
    if age is not None:
        if profile.age is None:
            unverified.append(
                _outcome(
                    age,
                    RequirementStatus.UNKNOWN,
                    "This scholarship publishes an age limit. Provide your age to check it.",
                )
            )
        elif (age.age_max is not None and profile.age > age.age_max) or (
            age.age_min is not None and profile.age < age.age_min
        ):
            bounds = []
            if age.age_min is not None:
                bounds.append(f"at least {age.age_min}")
            if age.age_max is not None:
                bounds.append(f"no older than {age.age_max}")
            blockers.append(
                _outcome(
                    age,
                    RequirementStatus.FAIL,
                    f"The published age limit ({', '.join(bounds)}) is not met by the supplied age.",
                )
            )
        else:
            satisfied.append(
                _outcome(
                    age,
                    RequirementStatus.MATCH,
                    "Your age satisfies the published age limit.",
                )
            )

    # ------------------------------------------------------------------
    # 6. Degree level, read from the curated structured degree column.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.DEGREE_LEVEL.value)
    degree_levels = read.degree_levels
    if degree_levels is not None:
        allowed = degree_levels.allowed_terms
        intended = profile.intended_degree_level
        if not allowed:
            unverified.append(
                _outcome(
                    degree_levels,
                    RequirementStatus.UNKNOWN,
                    "This scholarship states which degree levels it covers, but they could not be enumerated.",
                )
            )
        elif intended is None:
            unverified.append(
                _outcome(
                    degree_levels,
                    RequirementStatus.UNKNOWN,
                    f"This scholarship is open to {', '.join(allowed).lower().replace('_', ' ')} applicants. "
                    "Provide your intended degree level to check it.",
                )
            )
        elif intended == "OTHER":
            # "Other" is the student saying the level does not map onto our
            # vocabulary. That is not a mismatch; it is an unanswered question.
            unverified.append(
                _outcome(
                    degree_levels,
                    RequirementStatus.UNKNOWN,
                    (
                        "Your degree level is recorded as other, so it could not be compared with the "
                        "degree levels this scholarship publishes."
                    ),
                )
            )
        elif intended in allowed:
            satisfied.append(
                _outcome(
                    degree_levels,
                    RequirementStatus.MATCH,
                    "Your intended degree level is one this scholarship publishes.",
                )
            )
        else:
            blockers.append(
                _outcome(
                    degree_levels,
                    RequirementStatus.FAIL,
                    (
                        f"This scholarship publishes {', '.join(allowed).lower().replace('_', ' ')} as its "
                        "degree level, which does not include your intended level."
                    ),
                )
            )

    # ------------------------------------------------------------------
    # 7. Study mode.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.STUDY_MODE.value)
    study_mode = read.study_mode
    if study_mode is not None:
        required_modes = tuple(study_mode.allowed_terms)
        if profile.study_mode is None:
            unverified.append(
                _outcome(
                    study_mode,
                    RequirementStatus.UNKNOWN,
                    "This scholarship states a study-mode condition. Provide your intended study mode to check it.",
                )
            )
        elif profile.study_mode in required_modes:
            satisfied.append(
                _outcome(
                    study_mode,
                    RequirementStatus.MATCH,
                    "Your intended study mode matches the published condition.",
                )
            )
        else:
            blockers.append(
                _outcome(
                    study_mode,
                    RequirementStatus.FAIL,
                    "The published study-mode condition does not match your intended study mode.",
                )
            )

    # ------------------------------------------------------------------
    # 8. Other explicit mandatory conditions: a published programme
    #    restriction. Only produced by the reader when the named programme
    #    resolved to a canonical field, so this compares keys, not prose.
    # ------------------------------------------------------------------
    gate_order.append(RequirementKind.PROGRAMME_RESTRICTION.value)
    programme = read.programme_restriction
    if programme is not None:
        from .taxonomy import relate_fields, resolve_field_by_key

        required_key = programme.allowed_terms[0]
        student_field = resolve_field_by_key(profile.intended_field)
        if student_field.key is None:
            unverified.append(
                _outcome(
                    programme,
                    RequirementStatus.UNKNOWN,
                    "This scholarship publishes a programme-specific eligibility condition. "
                    "Provide your field of study to check it.",
                )
            )
        else:
            relationship = relate_fields(student_field.key, required_key)
            if relationship.level in {"EXACT", "CLOSE_SPECIALIZATION"}:
                satisfied.append(
                    _outcome(
                        programme,
                        RequirementStatus.MATCH,
                        "Your field of study satisfies the published programme condition.",
                    )
                )
            elif relationship.level in {"RELATED_FIELD", "BROAD_FIELD"}:
                # Adjacent is not the same programme. Reporting this as a match
                # would overstate what the awarding body published, so it needs
                # verification rather than a verdict.
                unverified.append(
                    _outcome(
                        programme,
                        RequirementStatus.UNKNOWN,
                        (
                            "This scholarship names a specific programme, and your field is adjacent to "
                            "it rather than identical. Confirm the programme on the official page."
                        ),
                    )
                )
            else:
                blockers.append(
                    _outcome(
                        programme,
                        RequirementStatus.FAIL,
                        (
                            "This scholarship publishes an eligibility condition naming a different "
                            "programme of study from the one you intend to apply to."
                        ),
                    )
                )

    if blockers:
        status = EligibilityStatus.INELIGIBLE
        detail = (
            f"{len(blockers)} published mandatory condition(s) are not met. A fit score cannot override this."
        )
    elif unverified:
        status = EligibilityStatus.NEEDS_VERIFICATION
        detail = (
            f"{len(unverified)} mandatory condition(s) could not be checked against the information supplied."
        )
    else:
        status = EligibilityStatus.ELIGIBLE
        detail = (
            "All published mandatory conditions were evaluated and satisfied."
            if satisfied
            else "No mandatory conditions are published for this scholarship."
        )

    return EligibilityResult(
        status=status,
        blockers=blockers,
        unverified=unverified,
        satisfied=satisfied,
        detail=detail,
        gate_order=gate_order,
    )


def eligibility_rank(status: EligibilityStatus) -> int:
    """Sort key. Lower is better, and an INELIGIBLE record can never sort first."""
    return ELIGIBILITY_RANK[status.value]


__all__ = [
    "DeadlineEvaluation",
    "evaluate",
    "evaluate_deadline",
    "eligibility_rank",
    "FundingState",
]