"""The matching engine.

This module is pure. It takes a normalised profile, a list of scholarship facts,
the engine version and an ``as_of`` date, and returns results. It contains no
clock, no randomness, no database session and no network call. Given identical
inputs it produces an identical response, which is what makes a score
reproducible months later and a bug report actionable.

The pipeline, in order:

    1. read published requirements for each record
    2. resolve deadline facts from existing deadline semantics
    3. run the hard eligibility gate
    4. score each fit dimension, marking unevaluable ones NOT_EVALUATED
    5. apply the coverage-aware weighted fit formula
    6. compute confidence separately, independent of the profile
    7. compute application readiness, a third independent layer
    8. classify gaps, and derive actions from those gaps
    9. rank on a total order that starts with eligibility

Three invariants are enforced structurally and covered by tests:

* A ``None`` dimension score never enters the numerator or the denominator, so
  unknown information cannot become a zero and cannot inflate a score either.
* Ranking sorts eligibility first, so an INELIGIBLE record cannot outrank an
  ELIGIBLE one no matter how high its fit score is.
* The gate never sees a fit score. ``evaluate`` is called before any scoring
  function and is not passed a score, so no sequence of edits can make the gate
  depend on fit.

The fit score arithmetic lives in :mod:`metrics`, the gate in
:mod:`eligibility`, readiness in :mod:`readiness`, confidence in
:mod:`confidence`, gaps in :mod:`gaps` and actions in :mod:`actions`, so this
file reads as a pipeline rather than as a calculation.
"""

from __future__ import annotations

from datetime import date

from .academic import academic_fit
from .actions import build_actions
from .components import (
    normalise_funding_state,
    score_field,
    score_funding,
    score_language,
    score_preference,
    score_requirements,
    score_timing,
)
from .confidence import compute_confidence
from .config import (
    API_BANDS,
    CONFIDENCE_BANDS,
    COVERAGE_BANDS,
    DEADLINE_SEMANTICS_VERSION,
    FIELD_TAXONOMY_VERSION,
    FIT_BANDS,
    FIT_COMPONENT_LABELS,
    FIT_ENGINE_VERSION,
    FIT_WEIGHTS,
    REQUIREMENT_READER_VERSION,
    SCORING_CONFIG_VERSION,
    STRONG_MATCH_THRESHOLD,
    config_snapshot,
)
from .eligibility import DeadlineEvaluation, eligibility_rank, evaluate
from .eligibility import evaluate_deadline as evaluate_record_deadline
from .explain import reason
from .gaps import deduplicate as deduplicate_gaps
from .gaps import gap as make_gap
from .metrics import compute_fit, resolve_public_fit
from .normalize import NormalisedProfile, ProfileIndex, build_profile_index
from .profile_strength import compute_profile_strength
from .readiness import compute_readiness
from .requirements import read_requirements, reader_version
from .summaries import build_facets, build_summary, coverage_band
from .taxonomy import relate_fields, resolve_field_by_key, resolve_scholarship_field
from .types import (
    ComponentScore,
    ComponentStatus,
    EligibilityStatus,
    MatchResult,
    ProfileBand,
    RequirementStatus,
    ScholarshipFacts,
)


FIT_FORMULA = (
    "fit score = SUM(component score x component weight x evaluated) / "
    "SUM(component weight x evaluated)"
)

COVERAGE_FORMULA = (
    "data coverage = SUM(component weight x evaluated) / total configured weight x 100"
)

CONTRIBUTION_FORMULA = (
    "effective weight = component weight / SUM(weight of evaluated components); "
    "contribution = effective weight x component score; contributions sum to the fit score"
)

SENSITIVITY_FORMULA = (
    "lower bound = SUM(component weight x component score) / SUM(configured weight); upper bound = "
    "(SUM(component weight x component score) + SUM(configured weight) x unevaluated weight) / "
    "SUM(configured weight). Both bounds are on the same 0-100 scale as the fit score"
)

SENSITIVITY_CAVEAT = "Mathematical sensitivity range, not a prediction."

CONFIDENCE_FORMULA = (
    "confidence = 35% data completeness + 25% provenance quality + "
    "25% requirement explicitness + 15% verification freshness"
)

READINESS_FORMULA = (
    "application readiness = SUM(readiness component x renormalised weight), where the components are "
    "eligibility certainty 30%, requirement completeness 20%, language readiness 15%, "
    "application readiness 15% and deadline readiness 20%"
)

PROFILE_INDEX_FORMULA = (
    "profile index = SUM(supplied academic component x renormalised weight), where each component is "
    "normalised within its own declared grading scale"
)

NORMALISATION_NOTE = (
    "Each supplied academic result is rescaled using only the grading scale you declared. No conversion "
    "between different grading systems is applied, so a published minimum on a different scale is reported "
    "as not evaluated rather than compared."
)

MISSING_DATA_NOTE = (
    "Missing information is not treated as zero. A dimension that could not be evaluated is excluded from "
    "both halves of the fit formula and shown as 'Not evaluated'."
)


def _band(score: float, bands) -> tuple[str, str]:
    for threshold, key, display in bands:
        if score >= threshold:
            return key, display
    return bands[-1][1], bands[-1][2]


def _component(
    name: str,
    score: float | None,
    detail: str,
    evidence: dict | None = None,
) -> ComponentScore:
    """Build one dimension, preserving the None/evaluated distinction."""
    return ComponentScore(
        name=name,
        label=FIT_COMPONENT_LABELS[name],
        weight=FIT_WEIGHTS[name],
        status=ComponentStatus.EVALUATED if score is not None else ComponentStatus.NOT_EVALUATED,
        score=score,
        detail=detail,
        evidence=evidence,
    )


def _academic_reasons(academic_score, academic_detail, requirement, absent):
    """Reason codes for the academic dimension."""
    if academic_score is None:
        return [reason("ACADEMIC_RESULT_NOT_PROVIDED", component="academic")]

    reasons: list = []
    if requirement is None and absent:
        reasons.append(reason("ACADEMIC_NO_PUBLISHED_MINIMUM", component="academic"))
        return reasons
    if requirement is None:
        return reasons

    if academic_score >= 100.0:
        reasons.append(reason("ACADEMIC_ABOVE_MINIMUM", component="academic"))
    elif academic_score <= 0.0:
        reasons.append(reason("ACADEMIC_AT_PUBLISHED_MINIMUM", component="academic"))
    else:
        reasons.append(reason("ACADEMIC_MEETS_MINIMUM", component="academic"))

    if "different grading scale" in academic_detail:
        reasons.append(reason("ACADEMIC_SCALE_MISMATCH", component="academic"))
    return reasons


def score_record(
    profile: NormalisedProfile,
    facts: ScholarshipFacts,
    as_of: date,
) -> MatchResult:
    """Score one scholarship record end to end.

    Eligibility is evaluated before any component is scored, and the scoring
    functions are never given the eligibility verdict. The fit arithmetic runs
    through :func:`compute_fit`, which handles coverage, effective weights,
    contributions and the sensitivity range in one place.
    """
    read = read_requirements(facts)
    deadline: DeadlineEvaluation = evaluate_record_deadline(facts, as_of)
    eligibility = evaluate(profile, facts, read, deadline)

    # ---------------------------------------------------------------- academic
    academic_score, academic_detail, academic_evidence = academic_fit(
        profile, read.academic_minimum, read.academic_minimum_absent_by_publication
    )
    academic = _component("academic", academic_score, academic_detail, academic_evidence)

    # ------------------------------------------------------------------- field
    student_field = resolve_field_by_key(profile.intended_field)
    scholarship_field = resolve_scholarship_field(facts)
    relationship = None
    if student_field.key and scholarship_field.key:
        relationship = relate_fields(student_field.key, scholarship_field.key)
    field_score, field_detail, field_evidence = score_field(
        relationship, student_field, scholarship_field
    )
    field = _component("field", field_score, field_detail, field_evidence)

    # ----------------------------------------------------------------- funding
    funding_state, funding_state_detail, funding_evidence = normalise_funding_state(facts)
    funding_score_value, funding_detail, funding_evidence_out = score_funding(
        profile, funding_state, funding_state_detail
    )
    funding_evidence_out = {**funding_evidence, **funding_evidence_out}
    funding = _component("funding", funding_score_value, funding_detail, funding_evidence_out)

    # ------------------------------------------------------------- requirement
    requirement_fit = score_requirements(facts)
    requirement_component = _component(
        "requirement",
        requirement_fit.score,
        requirement_fit.detail,
        requirement_fit.evidence,
    )

    # ---------------------------------------------------------------- language
    language_score, language_detail, language_evidence = score_language(
        profile, read.language_minimum, read.language_not_required
    )
    language = _component("language", language_score, language_detail, language_evidence)

    # -------------------------------------------------------------- preference
    preference_score, preference_detail, preference_evidence = score_preference(profile, facts)
    preference = _component("preference", preference_score, preference_detail, preference_evidence)

    # ------------------------------------------------------------------ timing
    timing_score, timing_detail, timing_evidence = score_timing(facts, deadline)
    timing = _component("timing", timing_score, timing_detail, timing_evidence)

    components = [
        academic,
        field,
        funding,
        requirement_component,
        language,
        preference,
        timing,
    ]

    # -------------------------------------------------- the fit arithmetic
    #
    # Unmeasured is not zero. compute_fit excludes every unevaluated component
    # from both halves of the fraction, records what each evaluated component
    # actually contributed, and brackets the unevaluated ones.
    metrics = compute_fit(
        tuple(
            {
                "name": component.name,
                "weight": component.weight,
                "score": component.score,
            }
            for component in components
        )
    )

    contributions = {item.name: item for item in metrics.contributions}
    components = [
        component.model_copy(
            update={
                "effective_weight": round(contributions[component.name].effective_weight, 4)
                if component.name in contributions
                else None,
                "contribution": round(contributions[component.name].contribution, 2)
                if component.name in contributions
                else None,
            }
        )
        for component in components
    ]

    confidence = compute_confidence(facts, read, as_of)

    language_comparison_state = language_evidence.get("state")

    readiness = compute_readiness(
        profile=profile,
        facts=facts,
        eligibility=eligibility,
        language_state=language_comparison_state,
        language_detail=language_detail,
        language_not_required=read.language_not_required,
        deadline_days=timing_evidence.get("days_remaining"),
        deadline_closed=deadline.closed,
        deadline_kind=deadline.kind,
        deadline_approximate=bool(timing_evidence.get("approximate")),
    )

    # ----------------------------------------------------------------- reasons
    reasons = _academic_reasons(
        academic_score,
        academic_detail,
        read.academic_minimum,
        read.academic_minimum_absent_by_publication,
    )
    if relationship is not None:
        if relationship.level == "EXACT":
            reasons.append(reason("FIELD_EXACT", component="field"))
        elif relationship.level in {"CLOSE_SPECIALIZATION", "RELATED_FIELD", "BROAD_FIELD"}:
            reasons.append(reason("FIELD_RELATED", component="field"))
        elif relationship.level == "UNRELATED":
            reasons.append(reason("FIELD_UNRELATED", component="field"))

    if funding_score_value is not None:
        if funding_state.value == "FULL":
            reasons.append(reason("FUNDING_FULL_MATCH", component="funding"))
        elif funding_state.value == "TUITION_ONLY":
            reasons.append(reason("FUNDING_TUITION_MATCH", component="funding"))
        elif funding_state.value == "PARTIAL":
            reasons.append(reason("FUNDING_PARTIAL", component="funding"))
        elif funding_state.value == "NONE":
            reasons.append(reason("FUNDING_NONE", component="funding"))

    if language_score is not None:
        if read.language_not_required:
            reasons.append(reason("LANGUAGE_NOT_REQUIRED", component="language"))
        elif language_score >= 100.0:
            reasons.append(reason("LANGUAGE_EXCEEDS_REQUIREMENT", component="language"))
        elif language_score > 0:
            reasons.append(reason("LANGUAGE_MEETS_REQUIREMENT", component="language"))
    if requirement_component.score is not None:
        reasons.append(
            reason("REQUIREMENTS_PUBLISHED", component="requirement", count=requirement_fit.evaluated)
        )

    if preference_score is not None:
        reasons.append(
            reason(
                "PREFERENCE_COUNTRY_MATCH" if preference_score >= 100.0 else "PREFERENCE_COUNTRY_MISMATCH",
                component="preference",
            )
        )

    if timing_score is not None:
        band = timing_evidence.get("band")
        if band == "comfortable":
            reasons.append(reason("DEADLINE_COMFORTABLE", component="timing"))
        elif band == "approaching":
            reasons.append(reason("DEADLINE_APPROACHING", component="timing"))
        elif band == "workable":
            reasons.append(reason("DEADLINE_WORKABLE", component="timing"))
        elif band == "tight":
            reasons.append(reason("DEADLINE_TIGHT", component="timing"))
        elif band == "urgent":
            reasons.append(reason("DEADLINE_URGENT", component="timing"))
        if timing_evidence.get("approximate"):
            reasons.append(reason("DEADLINE_APPROXIMATE", component="timing"))

    # -------------------------------------------------------------------- gaps
    gaps: list = []

    if academic.status is ComponentStatus.NOT_EVALUATED:
        gaps.append(make_gap("ACADEMIC_RESULT_NOT_PROVIDED", component="academic"))
    elif "different grading scale" in academic_detail:
        gaps.append(make_gap("ACADEMIC_SCALE_MISMATCH", component="academic"))

    if field.status is ComponentStatus.NOT_EVALUATED:
        if student_field.key is None:
            gaps.append(make_gap("FIELD_NOT_PROVIDED", component="field"))
        else:
            gaps.append(make_gap("FIELD_NOT_PUBLISHED", component="field"))

    if funding.status is ComponentStatus.NOT_EVALUATED:
        gaps.append(make_gap("FUNDING_UNKNOWN", component="funding"))

    if language.status is ComponentStatus.NOT_EVALUATED:
        if read.language_minimum is None:
            gaps.append(make_gap("LANGUAGE_NOT_PUBLISHED", component="language"))
        elif "does not convert" in language_detail:
            gaps.append(make_gap("LANGUAGE_TEST_MISMATCH", component="language"))
        elif "no documented scoring range" in language_detail:
            gaps.append(make_gap("LANGUAGE_NO_SURPLUS_RANGE", component="language"))
        else:
            gaps.append(make_gap("LANGUAGE_NOT_PROVIDED", component="language"))

    if preference.status is ComponentStatus.NOT_EVALUATED:
        gaps.append(make_gap("PREFERENCE_NOT_PROVIDED", component="preference"))

    if timing.status is ComponentStatus.NOT_EVALUATED:
        if deadline.closed:
            gaps.append(make_gap("DEADLINE_CLOSED", component="timing"))
        elif deadline.kind in {"rolling", "recurring", "annual"}:
            gaps.append(make_gap("DEADLINE_ROLLING", component="timing"))
        else:
            gaps.append(make_gap("DEADLINE_NOT_PUBLISHED", component="timing"))
    elif timing_evidence.get("approximate"):
        gaps.append(make_gap("DEADLINE_MONTH_PRECISION", component="timing"))

    if requirement_fit.unknown:
        gaps.append(
            make_gap("REQUIREMENT_UNKNOWN", component="requirement")
        )

    if not facts.official_source_url and not facts.official_source:
        gaps.append(make_gap("SOURCE_INCOMPLETE"))
    elif not facts.is_verified:
        gaps.append(make_gap("SOURCE_UNVERIFIED"))

    if confidence.label == "LOW":
        gaps.append(make_gap("CONFIDENCE_LOW"))
    elif confidence.label == "MEDIUM":
        gaps.append(make_gap("CONFIDENCE_MEDIUM"))

    # ---------------------------------------------------------------- blockers
    blockers: list = []
    if eligibility.status is EligibilityStatus.INELIGIBLE:
        blockers.append(
            reason("ELIGIBILITY_BLOCKED", component=None, count=len(eligibility.blockers))
        )
        for outcome in eligibility.blockers:
            blockers.append(reason(outcome.kind.value + "_BLOCKED", component="eligibility"))
    elif eligibility.status is EligibilityStatus.NEEDS_VERIFICATION:
        gaps.append(make_gap("ELIGIBILITY_NEEDS_VERIFICATION", component="eligibility"))
        for outcome in eligibility.unverified:
            code = f"{outcome.kind.value}_NEEDS_VERIFICATION"
            gaps.append(make_gap(code, component="eligibility"))
        if profile.intended_degree_level is None and read.degree_levels is not None:
            gaps.append(make_gap("DEGREE_LEVEL_NOT_PROVIDED", component="eligibility"))

    if eligibility.status is EligibilityStatus.ELIGIBLE and eligibility.satisfied:
        reasons.append(reason("ELIGIBILITY_VERIFIED", component="eligibility"))
    elif eligibility.status is EligibilityStatus.ELIGIBLE:
        reasons.append(reason("ELIGIBILITY_NO_PUBLISHED_CONDITIONS", component="eligibility"))

    reasons = list(dict.fromkeys(reasons))
    gaps = deduplicate_gaps(gaps)
    blockers = list(dict.fromkeys(blockers))

    # --------------------------------------------------------- the gate's veto
    #
    # The fit arithmetic and the fit disclosure are one explicit state model in
    # metrics.resolve_public_fit, not string juggling here. In short: an
    # INELIGIBLE record publishes no fit score and no fit band, because a high
    # number there would read as a recommendation the gate has already refused.
    # A NEEDS_VERIFICATION record keeps its deterministic score and band, because
    # that verdict is about our evidence rather than about the student's fit.
    public_fit = resolve_public_fit(eligibility.status, metrics)

    actions = build_actions(
        gaps=gaps,
        eligibility=eligibility.status,
        official_source_url=facts.official_source_url or facts.official_source,
        blocker_count=len(eligibility.blockers),
        document_count=len([item for item in (facts.documents or []) if item]),
    )

    return MatchResult(
        scholarship_id=facts.id,
        scholarship_name=facts.title,
        institution=facts.official_source,
        country=facts.country,
        degree_levels=facts.degree_levels,
        image_url=facts.image_url,
        image_alt_text=facts.image_alt_text,
        detail_url=f"/scholarships/{facts.id}",
        official_source_url=facts.official_source_url,
        eligibility=eligibility.status,
        eligibility_detail=eligibility,
        fit_score=public_fit.fit_score,
        fit_label=public_fit.fit_label,
        fit_label_display=public_fit.fit_label_display,
        confidence_score=confidence.score,
        confidence_label=confidence.label,
        confidence_label_display=confidence.label_display,
        confidence_coverage_band=coverage_band(metrics.data_coverage),
        data_coverage=metrics.data_coverage,
        field=scholarship_field.key,
        field_label=scholarship_field.label,
        evaluated_components=metrics.evaluated_component_count,
        total_components=metrics.total_component_count,
        readiness=readiness,
        sensitivity=(
            {
                "lower_bound": metrics.sensitivity.lower_bound,
                "upper_bound": metrics.sensitivity.upper_bound,
                "unevaluated_weight": metrics.sensitivity.unevaluated_weight,
                "unevaluated_components": list(metrics.sensitivity.unevaluated_components),
                "caveat": metrics.sensitivity.caveat,
            }
            if metrics.sensitivity
            else None
        ),
        score_breakdown=components,
        requirements=[
            outcome
            for outcome in (
                eligibility.satisfied + eligibility.blockers + eligibility.unverified
            )
        ],
        reasons=reasons,
        gaps=gaps,
        blockers=blockers,
        actions=actions,
        evidence_status=confidence.evidence,
        days_to_deadline=deadline.days_remaining,
        deadline_precision=deadline.precision,
        timing_bucket=timing_evidence.get("bucket"),
        funding_state=funding_state,
        funding_alignment_score=funding_score_value,
        field_alignment_level=relationship.level if relationship else None,
    )


def _rank_key(result: MatchResult):
    """The total order used for ranking.

    Eligibility first, then fit, then confidence, then coverage, then deadline
    urgency, and finally the record id so that two otherwise identical records
    still have a stable relative order. Without the final tiebreak the sort would
    depend on input order, and the same request could return two different lists.

    An INELIGIBLE record has no public fit score, so its fit key is 0 - it can
    never be lifted by an arithmetic result the interface refuses to show.
    """
    days = result.days_to_deadline
    return (
        eligibility_rank(result.eligibility),
        -(result.fit_score if result.fit_score is not None else 0.0),
        -(result.confidence_score or 0.0),
        -(result.data_coverage or 0.0),
        days if days is not None else 10**6,
        result.scholarship_id,
    )


def rank_results(results: list[MatchResult]) -> list[MatchResult]:
    """Sort by the total order above."""
    return sorted(results, key=_rank_key)


def engine_metadata(as_of: date) -> dict:
    """Versions and formulas reported with every response."""
    return {
        "engine_version": FIT_ENGINE_VERSION,
        "scoring_config_version": SCORING_CONFIG_VERSION,
        "field_taxonomy_version": FIELD_TAXONOMY_VERSION,
        "requirement_reader_version": reader_version(),
        "deadline_semantics_version": DEADLINE_SEMANTICS_VERSION,
        "as_of": as_of.isoformat(),
        "weights": dict(FIT_WEIGHTS),
        "formula": FIT_FORMULA,
        "coverage_formula": COVERAGE_FORMULA,
        "contribution_formula": CONTRIBUTION_FORMULA,
        "sensitivity_formula": SENSITIVITY_FORMULA,
        "sensitivity_caveat": SENSITIVITY_CAVEAT,
        "confidence_formula": CONFIDENCE_FORMULA,
        "readiness_formula": READINESS_FORMULA,
        "profile_index_formula": PROFILE_INDEX_FORMULA,
        "normalisation_note": NORMALISATION_NOTE,
        "missing_data_note": MISSING_DATA_NOTE,
        "scoring_config": config_snapshot(),
    }


def summarise(
    universe: list[MatchResult],
    visible: list[MatchResult] | None = None,
    *,
    total_candidates: int | None = None,
    truncated: bool = False,
) -> dict:
    """The authoritative counting system.

    Delegates to :mod:`summaries`, which asserts its own reconciliation
    invariants, so a dashboard that disagrees with the result list cannot be
    constructed.

    ``universe`` is every scored candidate and every summary count is computed
    from it; ``visible`` is the returned page, which is what the facets describe.
    Passing one list is correct whenever the response was not truncated.
    """
    summary = build_summary(
        universe,
        visible,
        total_candidates=total_candidates,
        truncated=truncated,
    )
    page = list(universe if visible is None else visible)
    return {
        "summary": summary,
        "facets": build_facets(page),
        # Retained at the top level so the first release's consumers keep
        # working. Both are read from the same summary, never recomputed.
        "total_candidates": summary.total_candidates,
        "eligible_count": summary.eligible_count,
        "needs_verification_count": summary.needs_verification_count,
        "ineligible_count": summary.ineligible_count,
        "strong_match_count": summary.strong_or_better_count,
        "average_confidence": summary.average_confidence,
    }


def build_profile_index_result(index: ProfileIndex) -> dict:
    """Convert the Academic Profile Index into its response shape."""
    components = [
        ComponentScore(
            name=component.name,
            label=component.label,
            weight=round(component.weight, 4),
            status=ComponentStatus.EVALUATED,
            score=component.score,
            detail=component.detail,
            effective_weight=round(component.weight, 4),
            contribution=round(component.weight * component.score, 2),
            evidence={
                "configured_weight": component.configured_weight,
                "renormalised_weight": round(component.weight, 4),
            },
        )
        for component in index.components
    ]
    band_key, band_display = (None, None)
    if index.score is not None:
        band_key, band_display = _band(index.score, API_BANDS)
    return {
        "score": index.score,
        "band": ProfileBand(band_key) if band_key else None,
        "band_display": band_display,
        "components": components,
        "evaluated_coverage": index.evaluated_coverage,
    }


def profile_index_for(profile: NormalisedProfile) -> ProfileIndex:
    """Convenience wrapper so callers need not import normalize directly."""
    return build_profile_index(profile)


def profile_strength_for(profile: NormalisedProfile):
    """Convenience wrapper so callers need not import profile_strength."""
    return compute_profile_strength(profile)


def band_labels() -> dict[str, dict[str, str]]:
    """The fit, confidence and coverage band tables, for the API's own use."""
    return {
        "fit": {key: label for _, key, label in FIT_BANDS},
        "confidence": {key: label for _, key, label in CONFIDENCE_BANDS},
        "coverage": {key: label for _, key, label in COVERAGE_BANDS},
    }


__all__ = [
    "CONFIDENCE_BANDS",
    "CONFIDENCE_FORMULA",
    "CONTRIBUTION_FORMULA",
    "COVERAGE_BANDS",
    "COVERAGE_FORMULA",
    "FIT_FORMULA",
    "MISSING_DATA_NOTE",
    "NORMALISATION_NOTE",
    "PROFILE_INDEX_FORMULA",
    "READINESS_FORMULA",
    "SENSITIVITY_CAVEAT",
    "SENSITIVITY_FORMULA",
    "STRONG_MATCH_THRESHOLD",
    "band_labels",
    "build_profile_index_result",
    "engine_metadata",
    "profile_index_for",
    "profile_strength_for",
    "rank_results",
    "score_record",
    "summarise",
]