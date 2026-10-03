"""The seven fit-score dimensions.

Each function here answers one question and returns ``(score, detail)`` where
``score is None`` means the dimension was NOT_EVALUATED. None is never used as a
zero, and the weight-normalisation step in engine.py excludes every dimension
that returned it.

The dimensions, and the reason each behaves as it does:

``field``       Controlled taxonomy only. An unresolved programme field is
                unknown, not unrelated.
``funding``     Built from the coverage columns rather than the short funding
                label, because "Fully Funded" is a label and tuition coverage is
                a fact. ``fully_funded = False`` is explicitly not treated as
                proof of "not funded": the column defaults to false, so false
                means "not established as fully funded".
``language``    Published threshold versus the test the student actually holds.
                No cross-test conversion exists anywhere, so a mismatched test
                is unknown rather than converted. The component score uses the
                locked bounded surplus model against a per-test configured
                range; a test with no configured range has no scoreable surplus
                and becomes NOT_EVALUATED rather than being invented.
``funding``     A table lookup against the centralised compatibility matrix in
                :mod:`config`, never a chain of conditionals, so revising a
                number cannot leave one branch behind.
``preference``  A table lookup against the centralised preference matrix. Never
                penalising an absent preference.
``timing``      Only a trustworthy fixed deadline produces a score. Rolling,
                annual and unpublished deadlines are NOT_EVALUATED, and the same
                day count is bucketed once for the results summary.
``requirement`` Non-hard published conditions the profile can answer, with the
                evidence that contributed reported by name.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from .config import (
    FUNDING_NEED_FULL,
    FUNDING_NEED_NEUTRAL,
    FUNDING_NEED_PARTIAL,
    FUNDING_NEED_TUITION,
    LANGUAGE_BELOW_MINIMUM_SCORE,
    LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED,
    LANGUAGE_SURPLUS_RANGES,
    PREFERENCE_MATCH,
    PREFERENCE_NO_MATCH,
    TIMING_BANDS,
    TIMING_BUCKETS,
    TIMING_FINAL_BAND_MAX_DAYS,
    TIMING_BUCKET_CLOSED,
    TIMING_BUCKET_UNKNOWN,
    clamp,
    funding_score,
    language_surplus_range,
    preference_score,
)
from .eligibility import DeadlineEvaluation
from .normalize import NormalisedProfile, normalise_text, resolve_country_code
from .taxonomy import FieldRelationship, relate_fields
from .types import (
    FundingRequirement,
    FundingState,
    NormalisedRequirement,
    RequirementKind,
    ScholarshipFacts,
)


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


#: Plain-language statement of which funding need the matrix row represents. Kept
#: beside the resolver so the sentence a reader sees and the row that produced the
#: number cannot drift apart.
FUNDING_NEED_BASIS: dict[str, str] = {
    FUNDING_NEED_FULL: "You require full funding.",
    FUNDING_NEED_TUITION: "You need the tuition covered and can fund the rest yourself.",
    FUNDING_NEED_PARTIAL: "You can accept partial funding.",
    FUNDING_NEED_NEUTRAL: "You did not state a specific funding requirement.",
}


# ---------------------------------------------------------------------------
# Field / programme
# ---------------------------------------------------------------------------


def score_field(relationship: FieldRelationship | None, student_field, scholarship_field) -> tuple[float | None, str, dict]:
    """Score the field dimension from the controlled taxonomy."""
    evidence = {
        "student_field": student_field.label if student_field else None,
        "student_field_key": student_field.key if student_field else None,
        "scholarship_field": scholarship_field.label if scholarship_field else None,
        "scholarship_field_key": scholarship_field.key if scholarship_field else None,
        "matched_alias": scholarship_field.matched_alias if scholarship_field else None,
        "source_field": scholarship_field.source_field if scholarship_field else None,
    }

    if student_field is None or student_field.key is None:
        return (
            None,
            "No field of study was supplied, so field fit was not evaluated.",
            {**evidence, "relationship": None},
        )
    if scholarship_field is None or scholarship_field.key is None:
        return (
            None,
            (
                "This scholarship does not publish a programme field that ScholarZone can resolve, "
                "so field fit was not evaluated."
            ),
            {**evidence, "relationship": None},
        )

    evidence["relationship"] = relationship.level if relationship else None
    return relationship.score, relationship.detail, evidence


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


def normalise_funding_state(facts: ScholarshipFacts) -> tuple[FundingState, str, dict]:
    """Derive a funding state from verified evidence.

    The order of evidence matters and is deliberate:

    1. The coverage columns. ``tuition_coverage`` and ``living_cost_coverage``
       are tri-state and were written from official evidence, so they are the
       primary signal.
    2. The published coverage text in ``coverage``/``benefits``, read
       conservatively by ``read_funding_coverage``. This is official evidence
       too, and it is available on far more records than the structured columns,
       which are still null across much of the catalogue.
    3. The award economics, ``funding_amount``/``funding_currency``/
       ``funding_period``, which establish that *something* is awarded even when
       coverage was never stated.
    4. The short ``funding`` label, used only to distinguish "no funding at
       all" from "funding exists but is unquantified".

    ``fully_funded`` is never used to establish a state on its own. The column
    is NOT NULL with a default of false, so a false value cannot be
    distinguished from "not established as fully funded" - and reading it as "not
    fully funded" would turn a gap in our evidence into a claim about the award.
    It is retained as corroboration only: it is reported in the evidence payload
    and noted when it agrees with the derived state, and it is never the reason a
    state was reached.
    """
    tuition = facts.tuition_coverage
    living = facts.living_cost_coverage
    has_amount = facts.funding_amount is not None and float(facts.funding_amount) > 0
    label = normalise_text(facts.funding_label)

    from .requirements import read_funding_coverage

    published_state, published_quote = read_funding_coverage(facts.coverage)

    evidence = {
        "tuition_coverage": tuition,
        "living_cost_coverage": living,
        "funding_amount": float(facts.funding_amount) if facts.funding_amount is not None else None,
        "funding_currency": facts.funding_currency,
        "funding_period": facts.funding_period,
        "travel_coverage": facts.travel_coverage,
        "funding_label": facts.funding_label,
        "published_coverage_state": published_state,
        "published_coverage_quote": published_quote or None,
        "fully_funded_corroboration": facts.fully_funded,
        "fully_funded_used_to_derive_state": False,
    }

    if tuition is True and living is True:
        return FundingState.FULL, "Official evidence states tuition and living costs are both covered.", evidence

    if tuition is True and living is False:
        return (
            FundingState.TUITION_ONLY,
            "Official evidence states tuition is covered but living costs are not.",
            evidence,
        )

    if tuition is True and living is None:
        return (
            FundingState.TUITION_PLUS_LIVING,
            (
                "Official evidence states tuition is covered. Living-cost coverage is not stated, so this "
                "is recorded as tuition covered with living costs unconfirmed."
            ),
            evidence,
        )

    # The structured columns say nothing usable, so fall back to what the
    # awarding body published about what the award pays for.
    if published_state == FundingState.FULL.value:
        return (
            FundingState.FULL,
            "The published coverage statement says tuition and living costs are both covered.",
            evidence,
        )
    if published_state == FundingState.TUITION_PLUS_LIVING.value:
        return (
            FundingState.TUITION_PLUS_LIVING,
            "The published coverage statement says tuition is covered and addresses living costs.",
            evidence,
        )
    if published_state == FundingState.TUITION_ONLY.value:
        return (
            FundingState.TUITION_ONLY,
            "The published coverage statement says tuition is covered and living costs are not included.",
            evidence,
        )
    if published_state == FundingState.NONE.value:
        return FundingState.NONE, "The published coverage statement says no funding is offered.", evidence

    if has_amount:
        return (
            FundingState.PARTIAL,
            (
                "A monetary award is recorded, but the record does not state that tuition is covered."
            ),
            evidence,
        )

    if "no funding" in label or "unfunded" in label or "not funded" in label:
        return FundingState.NONE, "The record states no funding is offered.", evidence

    if label:
        return (
            FundingState.UNKNOWN,
            (
                f'The record carries the funding label "{facts.funding_label}" but no verified coverage '
                "detail, so the actual coverage could not be established."
            ),
            evidence,
        )

    return (
        FundingState.UNKNOWN,
        "No verified funding detail is recorded for this scholarship.",
        evidence,
    )


def funding_need_for(profile: NormalisedProfile) -> str:
    """Resolve which row of the funding compatibility matrix applies.

    A student who needs living-cost support is treated as requiring full coverage
    even when they did not pick a funding option explicitly, because the two
    statements mean the same thing.
    """
    requirement = profile.funding_requirement

    if requirement is FundingRequirement.FULL_FUNDING.value or (
        requirement is None and profile.living_cost_support_required is True
    ):
        return FUNDING_NEED_FULL
    if requirement is FundingRequirement.TUITION_ONLY_SUFFICIENT.value:
        return FUNDING_NEED_TUITION
    if requirement is FundingRequirement.PARTIAL_OK.value:
        return FUNDING_NEED_PARTIAL
    if requirement is FundingRequirement.NO_SPECIFIC_NEED.value:
        return FUNDING_NEED_NEUTRAL

    # No funding preference supplied at all. A known award is mildly positive and
    # "no funding" is mildly negative, but nothing is penalised as a failure
    # because the student never said what they needed.
    return FUNDING_NEED_NEUTRAL


def score_funding(
    profile: NormalisedProfile,
    state: FundingState,
    state_detail: str,
) -> tuple[float | None, str, dict]:
    """Compare the normalised funding state against the student's need.

    A table lookup, not a chain of conditionals: the whole matrix lives in
    :mod:`config`, so revising a number is a configuration edit and cannot leave
    one branch behind. An UNKNOWN state returns ``None`` before the lookup,
    because an unestablished funding state is missing evidence rather than a
    published "no funding".
    """
    need = funding_need_for(profile)
    evidence = {"funding_state": state.value, "funding_need": need, "basis": state_detail}

    if state is FundingState.UNKNOWN:
        return (
            None,
            (
                "This scholarship's funding coverage could not be established from verified data, so "
                "funding fit was not evaluated."
            ),
            evidence,
        )

    score = funding_score(need, state.value)
    if score is None:
        return None, "Funding coverage could not be compared with your requirement.", evidence

    basis = FUNDING_NEED_BASIS[need]
    evidence["basis"] = basis
    return score, f"{basis} {state_detail}", evidence


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LanguageComparison:
    state: str
    detail: str
    #: The bounded-surplus component score, or ``None`` when the comparison
    #: produced no scoreable number. ``state`` and ``score`` are separate on
    #: purpose: the eligibility gate reads ``state`` only, so an undocumented
    #: surplus range can never become a hidden gate.
    score: float | None = None
    #: How many points above the published minimum the student is, on the same
    #: test. Reported for transparency even when no surplus range is configured.
    surplus: float | None = None
    surplus_range: float | None = None


def compare_language(
    profile: NormalisedProfile,
    requirement: NormalisedRequirement,
) -> LanguageComparison:
    """Compare a held language credential to a published threshold.

    Only the SAME test is ever compared. No cross-test equivalency exists in this
    engine and none is invented, so a TOEFL score against an IELTS threshold is
    ``UNKNOWN`` rather than a fabricated conversion.

    When the student holds the published test, the score comes from the locked
    bounded surplus model:

        surplus_ratio   = (student - minimum) / configured surplus range
        component_score = 100 x clamp(surplus_ratio, 0, 1)

    A test with no configured surplus range returns ``score=None``: the gate can
    still say MEETS or BELOW, because comparing two numbers on the same scale
    needs no conversion, but there is no documented basis for scoring the
    headroom, and inventing one would be the same error as inventing an
    equivalency.
    """
    required_test = requirement.test_name
    threshold = requirement.minimum_value

    if not profile.language_credentials:
        return LanguageComparison(
            state="NO_CREDENTIAL",
            detail=(
                f"This scholarship publishes a {required_test.upper()} requirement and no language "
                "test was supplied, so the requirement could not be checked."
            ),
        )

    if threshold is None:
        return LanguageComparison(
            state="UNKNOWN",
            detail="The published language requirement does not state a comparable threshold.",
        )

    matching = [credential for credential in profile.language_credentials if credential[0] == required_test]
    if not matching:
        held = ", ".join(sorted({credential[0].upper() for credential in profile.language_credentials}))
        if LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED:
            matching = list(profile.language_credentials)
        else:
            return LanguageComparison(
                state="UNKNOWN",
                detail=(
                    f"This scholarship requires {required_test.upper()} and you supplied {held}. "
                    "ScholarZone does not convert between language tests, so this requirement could "
                    "not be evaluated."
                ),
            )

    best = None
    for test, score, level in matching:
        if score is not None:
            best = score
            break
    if best is None:
        return LanguageComparison(
            state="UNKNOWN",
            detail=(
                f"A {required_test.upper()} credential was supplied but without a score, so the "
                "published threshold could not be compared."
            ),
        )

    if best < threshold:
        # A real evaluated zero: the published gate fails on the same test.
        return LanguageComparison(
            state="BELOW",
            detail=(
                f"Your {required_test.upper()} score of {best:g} is below the published minimum of "
                f"{threshold:g}."
            ),
            score=LANGUAGE_BELOW_MINIMUM_SCORE,
            surplus=best - threshold,
            surplus_range=language_surplus_range(required_test),
        )

    surplus = best - threshold
    surplus_range = language_surplus_range(required_test)
    detail = (
        f"Your {required_test.upper()} score of {best:g} meets the published minimum of {threshold:g}."
        if surplus <= 0
        else (
            f"Your {required_test.upper()} score of {best:g} exceeds the published minimum of "
            f"{threshold:g}."
        )
    )

    if surplus_range is None:
        # The gate answered; the component has no documented basis for a number.
        return LanguageComparison(
            state="MEETS",
            detail=(
                f"{detail} ScholarZone has no documented scoring range for {required_test.upper()}, "
                "so language fit was not scored."
            ),
            surplus=surplus,
            surplus_range=None,
        )

    # The ratio is clamped to the closed unit interval, not to 0-100. clamp()
    # defaults to the 0-100 score scale, so clamping the *ratio* there left a
    # score above the published maximum (IELTS 9.0 against a 6.5 minimum with a
    # 2.0 range produced 125), and a component above 100 would then be silently
    # pulled back by the fit formula's own clamp while the language component
    # still reported the inflated number to the reader.
    ratio = clamp(surplus / surplus_range, 0.0, 1.0)
    score = 100.0 * ratio
    return LanguageComparison(
        state="MEETS",
        detail=detail,
        score=round(score, 1),
        surplus=round(surplus, 2),
        surplus_range=surplus_range,
    )


def score_language(
    profile: NormalisedProfile,
    requirement: NormalisedRequirement | None,
    not_required: bool,
) -> tuple[float | None, str, dict]:
    """Score the language dimension."""
    evidence: dict = {
        "published_requirement": requirement.raw_quote if requirement else None,
        "required_test": requirement.test_name if requirement else None,
        "published_minimum": requirement.minimum_value if requirement else None,
        "cross_test_conversion": LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED,
    }

    if requirement is None:
        if not_required:
            # The provider stated language is not a condition of eligibility.
            # A full 100 is correct: there is nothing to meet and nothing to be
            # penalised for. NOT_EVALUATED would imply a requirement existed.
            return (
                100.0,
                "This scholarship states that a language test is not a requirement.",
                {**evidence, "basis": "not_required_by_publication"},
            )
        return (
            None,
            "This scholarship publishes no language requirement, so language fit was not evaluated.",
            {**evidence, "basis": "no_published_requirement"},
        )

    comparison = compare_language(profile, requirement)
    evidence["state"] = comparison.state
    evidence["student_credentials"] = [
        {"test": test.upper(), "score": score, "level": level}
        for test, score, level in profile.language_credentials
    ]
    evidence["quote"] = requirement.raw_quote

    if comparison.score is None:
        return None, comparison.detail, evidence
    return comparison.score, comparison.detail, evidence


# ---------------------------------------------------------------------------
# Preference
# ---------------------------------------------------------------------------


def score_preference(
    profile: NormalisedProfile,
    facts: ScholarshipFacts,
) -> tuple[float | None, str, dict]:
    """Score the optional student preferences.

    A missing preference is never a penalty. It makes the dimension
    NOT_EVALUATED, which removes it from the average rather than dragging it
    down.

    The country comparison is a lookup in the centralised preference matrix
    rather than a pair of inline constants, so the relationship between a stated
    preference and a stated non-match is one documented number.
    """
    evidence: dict = {"preferred_countries": list(profile.preferred_country_codes)}

    if not profile.preferred_country_codes:
        return (
            None,
            "No preferred countries were supplied, so preference fit was not evaluated.",
            evidence,
        )

    scholarship_country = resolve_country_code(facts.country)
    evidence["scholarship_country"] = facts.country
    evidence["scholarship_country_code"] = scholarship_country
    if scholarship_country is None:
        # A multi-country record such as "EU (multiple)" cannot be scored against
        # a specific preference list. Absent is not a mismatch.
        return (
            None,
            (
                f'This scholarship covers "{facts.country}" rather than a single country, so it could '
                "not be compared with your preferred countries."
            ),
            evidence,
        )

    if scholarship_country in profile.preferred_country_codes:
        relationship = PREFERENCE_MATCH
        detail = f"This scholarship is in {facts.country}, which is one of your preferred countries."
    else:
        relationship = PREFERENCE_NO_MATCH
        detail = f"This scholarship is in {facts.country}, which is not among your preferred countries."

    evidence["relationship"] = relationship
    score = preference_score(relationship)
    if score is None:
        return None, "The stated country preference could not be compared.", evidence
    return score, detail, evidence


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


def _month_end(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def score_timing(
    facts: ScholarshipFacts,
    deadline: DeadlineEvaluation,
) -> tuple[float | None, str, dict]:
    """Score the timing dimension from the existing deadline semantics.

    Only a fixed, trustworthy date produces a number. A rolling or recurring
    deadline is not "urgent" and not "comfortable" - it has no single date - so
    it is NOT_EVALUATED.

    A month-precision date is scored from the *last* day of the published month.
    The stored date is normalised to the first of the month, so counting to it
    would report less time than a reader actually has. The precision is carried
    into the response so the interface labels the figure as approximate instead of
    presenting it as exact.
    """
    evidence: dict = {
        "deadline_precision": deadline.precision,
        "deadline_kind": deadline.kind,
        "deadline_display": facts.deadline_display,
        "approximate": False,
    }

    if deadline.closed:
        evidence["bucket"] = TIMING_BUCKET_CLOSED
        return None, "This scholarship round is closed.", evidence

    if deadline.days_remaining is None:
        evidence["bucket"] = TIMING_BUCKET_UNKNOWN
        if deadline.kind in {"rolling", "recurring", "annual"}:
            return (
                None,
                (
                    "This scholarship publishes a rolling or recurring deadline rather than a fixed "
                    "date, so timing was not scored."
                ),
                evidence,
            )
        return (
            None,
            "No fixed application deadline is published for this scholarship, so timing was not scored.",
            evidence,
        )

    days = deadline.days_remaining
    evidence["days_remaining"] = days

    if deadline.precision == "month" and facts.deadline_date:
        try:
            parsed = date.fromisoformat(facts.deadline_date)
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            extra = _month_end(parsed.year, parsed.month) - parsed.day
            days = days + extra
            evidence["days_remaining"] = days
            evidence["approximate"] = True
            evidence["basis"] = (
                "The published deadline states a month rather than a day, so the remaining time is "
                "measured to the end of that month."
            )

    for lower_bound, score, descriptor in TIMING_BANDS:
        if days >= lower_bound:
            evidence["band"] = descriptor
            evidence["bucket"] = timing_bucket(days, closed=False, kind=deadline.kind)
            detail = (
                f"There are {days} days left to apply."
                if not evidence.get("approximate")
                else (
                    f"There are approximately {days} days left to apply. The published deadline states "
                    "a month rather than a day."
                )
            )
            return score, detail, evidence

    if days <= TIMING_FINAL_BAND_MAX_DAYS:
        evidence["band"] = "urgent"
        evidence["bucket"] = "CLOSING_SOON"
        return (
            30.0,
            f"There are only {days} days left to apply.",
            evidence,
        )

    return None, "The deadline could not be placed in a timing band.", evidence


def timing_bucket(days: int | None, closed: bool = False, kind: str | None = None) -> str:
    """Classify a deadline for the results summary.

    The same day count the timing component already resolved, bucketed for
    counting. A month-precision date is bucketed from the same measurement the
    component used, and the summary reports it as approximate. Rolling, annual
    and unpublished deadlines are ``UNKNOWN``: they are open, not unknown in the
    sense of "we could not check", and the interface says "rolling" rather than
    pretending a date exists.
    """
    if closed:
        return TIMING_BUCKET_CLOSED
    if days is None:
        return TIMING_BUCKET_UNKNOWN
    if kind in {"rolling", "recurring", "annual"}:
        return TIMING_BUCKET_UNKNOWN
    for lower_bound, bucket in TIMING_BUCKETS:
        if days >= lower_bound:
            return bucket
    return "CLOSING_SOON"


# ---------------------------------------------------------------------------
# Non-hard requirements
# ---------------------------------------------------------------------------

#: Requirements the profile can answer without any eligibility decision. They are
#: scored, but failing one is a low fit score rather than INELIGIBLE.
_NON_HARD_MARKERS = (
    "work experience",
    "employment",
    "professional experience",
    "research experience",
    "publication",
    "volunteer",
    "leadership",
    "portfolio",
    "transcript",
    "documents",
    "required document",
)

_DOCUMENT_HINTS = {
    "transcript": "academic transcript",
    "cv": "curriculum vitae",
    "resume": "curriculum vitae",
    "recommendation letter": "recommendation letter",
    "personal statement": "personal statement",
    "motivation letter": "motivation letter",
    "proof of citizenship": "proof of citizenship",
    "passport": "passport copy",
    "language certificate": "language certificate",
    "research proposal": "research proposal",
}


@dataclass(frozen=True)
class RequirementFit:
    evaluated: int
    matched: int
    unknown: int
    score: float | None
    detail: str
    evidence: dict


def score_requirements(facts: ScholarshipFacts) -> RequirementFit:
    """Score the non-hard published conditions the profile can answer.

    Only document readiness and explicitly published experience conditions are
    considered, and each evaluation is reported by name. A requirement whose
    status is genuinely unknown counts as unknown, never as a failure.
    """
    evidence: dict = {"documents_requested": [], "documents_unknown": [], "experience_unknown": []}

    documents = [normalise_text(item) for item in (facts.documents or []) if normalise_text(item)]
    known_hint = False
    for document in documents:
        matched = False
        for hint, label in _DOCUMENT_HINTS.items():
            if hint in document:
                evidence["documents_requested"].append(label)
                matched = True
                known_hint = True
                break
        if not matched:
            evidence["documents_unknown"].append(document[:120])

    experience_text = " ".join(
        [normalise_text(item) for item in (facts.requirements or [])]
        + [normalise_text(facts.eligibility_summary or "")]
    )
    experience_present = [marker for marker in _NON_HARD_MARKERS if marker in experience_text]
    for marker in experience_present:
        evidence["experience_unknown"].append(marker)

    evaluated = 0
    matched = 0
    unknown = 0

    if documents:
        evaluated += 1
        matched += 1  # Document readiness: the student is told what to prepare.
        unknown += len(evidence["documents_unknown"])

    if experience_present:
        evaluated += 1
        # Experience conditions cannot be evaluated from the profile, so they add
        # unknown weight without claiming a match.
        unknown += len(experience_present)

    total = matched + unknown
    if total == 0:
        return RequirementFit(
            evaluated=0,
            matched=0,
            unknown=0,
            score=None,
            detail="This scholarship publishes no non-mandatory conditions ScholarZone can evaluate.",
            evidence=evidence,
        )

    # A list of documents is a real, satisfied requirement: the student knows
    # exactly what to prepare. Unknown document types reduce precision but never
    # count as a failure.
    score = (matched / total) * 100.0
    return RequirementFit(
        evaluated=evaluated,
        matched=matched,
        unknown=unknown,
        score=round(score, 1),
        detail=(
            f"{matched} of {total} published condition(s) could be confirmed from your profile or the "
            "record. The rest are reported as not evaluated."
        ),
        evidence=evidence,
    )


def summarise_requirement_status(read) -> list[tuple[RequirementKind, str, str, str | None]]:
    """Flatten published requirements for the response's requirement list."""
    entries: list[tuple[RequirementKind, str, str, str | None]] = []
    mapping = (
        (read.academic_minimum, "ACADEMIC_MINIMUM"),
        (read.language_minimum, "LANGUAGE_MINIMUM"),
        (read.nationality, "NATIONALITY"),
        (read.age, "AGE"),
        (read.study_mode, "STUDY_MODE"),
    )
    for requirement, label in mapping:
        if requirement is not None:
            entries.append(
                (
                    requirement.kind,
                    label,
                    requirement.raw_quote,
                    requirement.provenance_url,
                )
            )
    return entries


__all__ = [
    "FUNDING_NEED_BASIS",
    "LanguageComparison",
    "RequirementFit",
    "compare_language",
    "funding_need_for",
    "normalise_funding_state",
    "score_field",
    "score_funding",
    "score_language",
    "score_preference",
    "score_requirements",
    "score_timing",
    "summarise_requirement_status",
    "timing_bucket",
]