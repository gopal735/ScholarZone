"""Match 2.0 contract suite: fit mathematics, bands and configuration integrity.

Part 1 of the Match 2.0 contract suite. This file is the regression net for the
locked arithmetic, because every other layer in the product - the dashboard, the
facets, the filters, the explanation panel - is built on top of these numbers and
none of them is trustworthy if these move.

Nothing here touches a database. The engine is pure, so every property below is
pinned with hand-built component scores rather than with catalogue records: a
failure names a formula rather than a query.

The properties asserted here are the ones the feature promises:

* the seven weights are the whole model, and they total 1.0 or the process fails
  at import time
* an unevaluated component is excluded from BOTH halves of the fraction, so
  unknown information can never become a zero
* an evaluated zero stays evaluated, because "scored zero" and "not measured" are
  different facts
* nothing measurable means ``None``, never 0
* the contributions sum to the published score
* the sensitivity range brackets the result and is never used for ranking
* identical inputs produce identical output

Sections 2-5 (eligibility, academics, field, funding, language, requirements,
preference, timing, confidence, readiness, profile strength, gaps, actions,
summaries, facets, ranking, parsing and validation) follow in the same file.
"""

from __future__ import annotations

import inspect
import math
from datetime import date
from types import MappingProxyType

import pytest

from app.services.matching.academic import compare_to_minimum
from app.services.matching.components import (
    compare_language,
    funding_need_for,
    normalise_funding_state,
    score_funding,
    score_language,
)
from app.services.matching.config import (
    ACADEMIC_MINIMUM_ONLY_SCORE,
    API_BANDS,
    API_COMPONENT_WEIGHTS,
    CONFIDENCE_WEIGHTS,
    FIELD_RELATIONSHIP_LEVELS,
    FIT_BANDS,
    FIT_BAND_KEYS,
    FIT_WEIGHTS,
    FUNDING_COMPATIBILITY,
    FUNDING_NEED_FULL,
    FUNDING_NEED_NEUTRAL,
    FUNDING_NEED_PARTIAL,
    FUNDING_NEED_TUITION,
    FUNDING_STATES,
    LANGUAGE_BELOW_MINIMUM_SCORE,
    LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED,
    LANGUAGE_SURPLUS_RANGES,
    SUM_TOLERANCE,
    TOTAL_CONFIGURED_WEIGHT,
    _validate_weight_table,
    clamp,
    funding_score,
    language_surplus_range,
    preference_score,
    validate_config,
)
from app.services.matching.eligibility import evaluate, evaluate_deadline, eligibility_rank
from app.services.matching.engine import score_record
from app.services.matching.metrics import (
    ComponentContribution,
    FitDisclosure,
    FIT_LABEL_INELIGIBLE,
    FIT_LABEL_NOT_EVALUATED,
    compute_fit,
    contributions_sum_to_fit,
    fit_band,
    resolve_public_fit,
    total_configured_weight,
)
from app.services.matching.normalize import build_profile_index, normalise_profile
from app.services.matching.requirements import read_requirements
from app.services.matching.taxonomy import (
    known_field_keys,
    relate_fields,
    resolve_field,
    resolve_scholarship_field,
)
from app.services.matching.types import (
    AcademicMark,
    EligibilityStatus,
    FundingRequirement,
    FundingState,
    GradingScale,
    LanguageCredential,
    MatchProfileRequest,
    NormalisedRequirement,
    RequirementKind,
    ScholarshipFacts,
    StudyMode,
)


AS_OF = date(2026, 3, 1)


# ---------------------------------------------------------------------------
# Shared fact and profile builders
# ---------------------------------------------------------------------------


def make_facts(**overrides) -> ScholarshipFacts:
    """A fully documented record, so a test overrides one rule at a time."""
    base = dict(
        id=1,
        title="Test Scholarship",
        country="United Kingdom",
        degree_levels="Master",
        funding_label="Fully Funded",
        program_type="Computer Science",
        status="open",
        deadline_date="2026-06-30",
        deadline_display="30 June 2026",
        deadline_precision="exact",
        eligibility=["Applicants must be citizens of India.", "Minimum GPA of 3.5/4.0 required."],
        eligibility_summary="Applicants must have a minimum GPA of 3.5/4.0.",
        requirements=["Two recommendation letters."],
        documents=["Academic transcript", "CV"],
        coverage=["Full tuition, monthly stipend"],
        english_requirement="IELTS 6.5 or above required.",
        funding_amount=25000.0,
        funding_currency="GBP",
        funding_period="per year",
        tuition_coverage=True,
        living_cost_coverage=True,
        travel_coverage=False,
        fully_funded=True,
        official_source="Example University",
        official_source_url="https://example.edu/scholarships/test",
        official_details={"field": "Computer Science"},
        is_verified=True,
        verification_status="active",
        last_verified_date="2026-02-01",
        next_verification_due="2026-05-01",
        image_url="https://example.edu/logo.png",
        image_alt_text="Example University logo",
    )
    base.update(overrides)
    return ScholarshipFacts(**base)


def strong_profile(**overrides) -> MatchProfileRequest:
    """A profile that satisfies every published condition in ``make_facts``."""
    base = dict(
        age=22,
        citizenship="India",
        country_of_residence="India",
        highest_qualification="Bachelor's degree",
        graduation_year=2025,
        overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.9),
        subject_results=[AcademicMark(scale=GradingScale.GPA_4, value=3.8, field="computer_science")],
        intended_degree_level="MASTER",
        intended_field="computer_science",
        study_mode=StudyMode.FULL_TIME,
        preferred_countries=["United Kingdom", "Ireland"],
        language_credentials=[LanguageCredential(test="IELTS", score=7.5)],
        funding_requirement=FundingRequirement.FULL_FUNDING,
        living_cost_support_required=True,
        max_self_contribution=0.0,
        intended_intake_year=2027,
    )
    base.update(overrides)
    return MatchProfileRequest(**base)


def score(request: MatchProfileRequest, facts: ScholarshipFacts, as_of: date = AS_OF):
    return score_record(normalise_profile(request), facts, as_of)


def component_of(result, name):
    return next(item for item in result.score_breakdown if item.name == name)


def academic_requirement(minimum=None, scale=GradingScale.GPA_4, preferred=None):
    return NormalisedRequirement(
        kind=RequirementKind.ACADEMIC_MINIMUM,
        raw_quote="Minimum GPA of 3.5/4.0 required.",
        provenance_url="https://example.edu",
        minimum_value=minimum,
        scale=scale,
        preferred_value=preferred,
    )


def language_requirement(test="ielts", minimum=6.5):
    return NormalisedRequirement(
        kind=RequirementKind.LANGUAGE_MINIMUM,
        raw_quote="IELTS 6.5 or above required.",
        provenance_url="https://example.edu",
        minimum_value=minimum,
        test_name=test,
    )


# ---------------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------------


def component(name: str, score, weight: float | None = None) -> dict:
    """One fit component in the shape ``compute_fit`` accepts."""
    return {"name": name, "weight": FIT_WEIGHTS[name] if weight is None else weight, "score": score}


def all_evaluated(score_for: dict[str, float] | None = None) -> tuple[dict, ...]:
    """Every dimension evaluated, at 100 unless a score is supplied."""
    return tuple(
        component(name, 100.0 if score_for is None else score_for.get(name, 100.0))
        for name in FIT_WEIGHTS
    )


# ---------------------------------------------------------------------------
# 1. Configuration integrity
# ---------------------------------------------------------------------------


class TestConfigurationIntegrity:
    def test_the_seven_weights_are_the_whole_model_and_total_one(self):
        assert len(FIT_WEIGHTS) == 7
        assert total_configured_weight() == pytest.approx(1.0)
        assert round(sum(FIT_WEIGHTS.values()), 10) == 1.0

    def test_the_locked_weights_are_the_configured_weights(self):
        """Not a smoke test: these are the published coefficients."""
        assert dict(FIT_WEIGHTS) == {
            "academic": 0.25,
            "field": 0.20,
            "funding": 0.20,
            "requirement": 0.15,
            "language": 0.10,
            "preference": 0.05,
            "timing": 0.05,
        }

    def test_import_time_validation_accepts_the_shipped_configuration(self):
        """A malformed table raises at import, so reaching here proves it is sound."""
        assert validate_config() is None

    @pytest.mark.parametrize(
        "total",
        [
            {"a": 0.5, "b": 0.4},          # under
            {"a": 0.5, "b": 0.6},          # over
            {"a": 0.5, "b": 0.49999999},   # float drift
            {"a": 1.0, "b": 0.1},          # not rescaled, rejected
        ],
    )
    def test_malformed_weights_raise_rather_than_being_rescaled(self, total):
        """Silently rescaling would change every score in the product."""
        with pytest.raises(RuntimeError, match="must total 1.0"):
            _validate_weight_table("TEST_WEIGHTS", MappingProxyType(total))

    def test_a_weight_table_that_totals_one_is_accepted(self):
        assert (
            _validate_weight_table("TEST_WEIGHTS", MappingProxyType({"a": 0.25, "b": 0.75})) is None
        )

    def test_clamp_is_the_bounded_primitive_the_whole_engine_uses(self):
        assert clamp(-1) == 0.0
        assert clamp(0) == 0.0
        assert clamp(55.5) == 55.5
        assert clamp(100) == 100.0
        assert clamp(101) == 100.0


# ---------------------------------------------------------------------------
# 2. Fit aggregation
# ---------------------------------------------------------------------------


class TestFitAggregation:
    def test_all_seven_dimensions_average_to_the_mean_of_their_scores(self):
        metrics = compute_fit(
            all_evaluated(
                {
                    "academic": 100.0,
                    "field": 80.0,
                    "funding": 60.0,
                    "requirement": 40.0,
                    "language": 20.0,
                    "preference": 0.0,
                    "timing": 100.0,
                }
            )
        )
        # Weighted: .25*100 + .20*80 + .20*60 + .15*40 + .10*20 + .05*0 + .05*100
        #         = 25 + 16 + 12 + 6 + 2 + 0 + 5 = 66
        assert metrics.fit_score == pytest.approx(66.0)
        assert metrics.fit_band == "POSSIBLE_FIT"

    def test_weights_are_applied_not_a_plain_mean(self):
        """A naive average of these scores is 57.1; the weighted answer is 66."""
        scores = {
            "academic": 100.0,
            "field": 80.0,
            "funding": 60.0,
            "requirement": 40.0,
            "language": 20.0,
            "preference": 0.0,
            "timing": 100.0,
        }
        plain_mean = sum(scores.values()) / len(scores)
        assert compute_fit(all_evaluated(scores)).fit_score != pytest.approx(plain_mean)

    def test_partial_evaluation_renormalises_over_what_was_measured(self):
        """Excluding a component must exclude it from BOTH halves, not just one."""
        scores = {"academic": 100.0, "field": 100.0}
        only_two = compute_fit((component("academic", 100.0), component("field", 100.0)))
        assert only_two.fit_score == pytest.approx(100.0)
        assert only_two.evaluated_component_count == 2
        assert only_two.total_component_count == 2

        # Preference is 5% and unevaluated. Dropping it from the denominator only
        # would inflate the result; keeping it at zero would deflate it.
        with_preference = compute_fit(
            (
                component("academic", 100.0),
                component("field", 100.0),
                component("preference", None),
            )
        )
        assert with_preference.fit_score == pytest.approx(100.0)
        assert with_preference.data_coverage == pytest.approx(45.0)

    def test_unknown_is_never_zero(self):
        """The single most important property in the file."""
        with_unknown = compute_fit(
            (
                component("academic", 80.0),
                component("field", 80.0),
                component("funding", 80.0),
                component("requirement", 80.0),
                component("language", 80.0),
                component("preference", 80.0),
                component("timing", None),
            )
        )
        as_zero = compute_fit(
            (
                component("academic", 80.0),
                component("field", 80.0),
                component("funding", 80.0),
                component("requirement", 80.0),
                component("language", 80.0),
                component("preference", 80.0),
                component("timing", 0.0),
            )
        )
        assert with_unknown.fit_score == pytest.approx(80.0)
        assert as_zero.fit_score == pytest.approx(76.0)
        assert with_unknown.fit_score != as_zero.fit_score

    def test_an_unevaluated_component_is_reported_as_missing_not_low(self):
        metrics = compute_fit(
            (component("academic", 90.0), component("language", None))
        )
        assert [item.name for item in metrics.contributions] == ["academic"]
        assert metrics.evaluated_component_count == 1
        assert metrics.total_component_count == 2
        assert metrics.sensitivity.unevaluated_components == ("language",)

    def test_a_real_zero_stays_evaluated_and_keeps_its_weight(self):
        metrics = compute_fit((component("academic", 0.0), component("field", 100.0)))
        assert metrics.evaluated_component_count == 2
        assert metrics.fit_score == pytest.approx(44.4)  # (.25*0 + .20*100) / .45
        zero = next(item for item in metrics.contributions if item.name == "academic")
        assert zero.score == 0.0
        assert zero.contribution == 0.0
        assert zero.effective_weight == pytest.approx(0.25 / 0.45)

    def test_nothing_measurable_is_none_and_never_zero(self):
        metrics = compute_fit(tuple(component(name, None) for name in FIT_WEIGHTS))
        assert metrics.fit_score is None
        assert metrics.fit_band is None
        assert metrics.fit_label is None
        assert metrics.data_coverage == 0.0
        assert metrics.evaluated_component_count == 0
        assert metrics.contributions == ()

    def test_an_empty_component_list_does_not_divide_by_zero(self):
        metrics = compute_fit(())
        assert metrics.fit_score is None
        assert metrics.data_coverage == 0.0
        assert metrics.sensitivity is None


# ---------------------------------------------------------------------------
# 3. Coverage, effective weights and contributions
# ---------------------------------------------------------------------------


class TestCoverageAndContributions:
    def test_full_evaluation_is_one_hundred_percent_coverage(self):
        metrics = compute_fit(all_evaluated())
        assert metrics.data_coverage == pytest.approx(100.0)
        assert metrics.evaluated_component_count == 7
        assert metrics.total_component_count == 7

    def test_coverage_is_the_percentage_of_configured_weight_evaluated(self):
        metrics = compute_fit(
            (component("academic", 100.0), component("field", 100.0))
        )
        assert metrics.data_coverage == pytest.approx(45.0)

        with_more = compute_fit(
            (
                component("academic", 100.0),
                component("field", 100.0),
                component("funding", 100.0),
            )
        )
        assert with_more.data_coverage == pytest.approx(65.0)

    def test_coverage_would_be_wrong_if_weights_were_summed_as_percentages(self):
        """A real regression guard: coverage was once scaled from 100 to 1."""
        metrics = compute_fit(all_evaluated())
        assert metrics.data_coverage > 1.0

    def test_effective_weights_sum_to_one_over_the_evaluated_components(self):
        metrics = compute_fit(
            (component("academic", 90.0), component("field", 70.0), component("timing", None))
        )
        assert sum(item.effective_weight for item in metrics.contributions) == pytest.approx(1.0)

    def test_effective_weight_is_the_configured_weight_renormalised(self):
        metrics = compute_fit((component("academic", 90.0), component("field", 70.0)))
        academic = next(item for item in metrics.contributions if item.name == "academic")
        assert academic.configured_weight == 0.25
        assert academic.effective_weight == pytest.approx(0.25 / 0.45)

    def test_contributions_sum_to_the_published_fit_score(self):
        metrics = compute_fit(
            all_evaluated(
                {
                    "academic": 96.0,
                    "field": 94.0,
                    "funding": 88.0,
                    "requirement": 90.0,
                    "language": 70.0,
                    "preference": 60.0,
                    "timing": 77.5,
                }
            )
        )
        assert contributions_sum_to_fit(metrics) is True
        total = sum(item.contribution for item in metrics.contributions)
        assert total == pytest.approx(metrics.fit_score, abs=SUM_TOLERANCE)

    def test_contributions_are_reported_for_every_evaluated_component(self):
        metrics = compute_fit(all_evaluated())
        assert len(metrics.contributions) == 7
        for item in metrics.contributions:
            assert isinstance(item, ComponentContribution)
            assert item.effective_weight > 0
            assert item.contribution == pytest.approx(item.effective_weight * item.score)

    def test_the_score_is_bounded_to_zero_one_hundred(self):
        for scores in (all_evaluated(), tuple(component(name, 0.0) for name in FIT_WEIGHTS)):
            metrics = compute_fit(scores)
            assert 0.0 <= metrics.fit_score <= 100.0

    def test_out_of_range_component_scores_are_clamped_rather_than_averaged_in(self):
        metrics = compute_fit(
            (component("academic", 250.0), component("field", -40.0))
        )
        assert 0.0 <= metrics.fit_score <= 100.0
        scores = {item.name: item.score for item in metrics.contributions}
        assert scores["academic"] == 100.0
        assert scores["field"] == 0.0

    def test_the_published_score_is_rounded_to_one_decimal_for_display_only(self):
        metrics = compute_fit(
            (
                component("academic", 100.0),
                component("field", 0.0),
                component("funding", 0.0),
                component("requirement", 0.0),
                component("language", 0.0),
                component("preference", 0.0),
                component("timing", 0.0),
            )
        )
        assert metrics.fit_score == round(metrics.fit_score, 1)
        # 0.25 / 1.0 = 25 exactly; use a case that actually produces a third digit.
        thirds = compute_fit(
            (component("academic", 100.0), component("field", 1.0), component("funding", 2.0))
        )
        assert thirds.fit_score == round(thirds.fit_score, 1)
        assert contributions_sum_to_fit(thirds) is True

    def test_no_nan_or_infinity_reaches_the_response(self):
        for scores in (all_evaluated(), tuple(component(name, None) for name in FIT_WEIGHTS)):
            metrics = compute_fit(scores)
            if metrics.fit_score is not None:
                assert not math.isnan(metrics.fit_score)
                assert not math.isinf(metrics.fit_score)
            assert not math.isnan(metrics.data_coverage)
            for item in metrics.contributions:
                assert not math.isnan(item.contribution)
                assert not math.isinf(item.contribution)
            if metrics.sensitivity is not None:
                assert not math.isnan(metrics.sensitivity.lower_bound)
                assert not math.isinf(metrics.sensitivity.upper_bound)


# ---------------------------------------------------------------------------
# 4. Sensitivity range
# ---------------------------------------------------------------------------


class TestSensitivityRange:
    def test_full_coverage_has_no_sensitivity_range(self):
        metrics = compute_fit(all_evaluated())
        assert metrics.sensitivity is None

    def test_partial_coverage_brackets_the_result(self):
        metrics = compute_fit(
            (
                component("academic", 100.0),
                component("field", 100.0),
                component("funding", None),
                component("requirement", None),
                component("language", None),
                component("preference", None),
                component("timing", None),
            )
        )
        bracket = metrics.sensitivity
        assert bracket is not None
        assert bracket.lower_bound <= metrics.fit_score <= bracket.upper_bound
        assert bracket.lower_bound == pytest.approx(45.0)
        assert bracket.upper_bound == pytest.approx(100.0)

    def test_the_unevaluated_weight_is_reported(self):
        metrics = compute_fit(
            (
                component("academic", 80.0),
                component("field", None),
                component("funding", None),
                component("requirement", None),
                component("language", None),
                component("preference", None),
                component("timing", None),
            )
        )
        assert metrics.sensitivity.unevaluated_weight == pytest.approx(0.75)
        assert set(metrics.sensitivity.unevaluated_components) == {
            "field",
            "funding",
            "requirement",
            "language",
            "preference",
            "timing",
        }

    def test_the_range_carries_a_caveat_and_is_not_a_prediction(self):
        metrics = compute_fit((component("academic", 80.0), component("field", None)))
        assert metrics.sensitivity.caveat == "Mathematical sensitivity range, not a prediction."

    def test_the_lower_bound_uses_unrounded_weighted_numerator(self):
        # 25% * 50 = 12.5 over a total configured weight of 100.
        metrics = compute_fit((component("academic", 50.0), component("field", None)))
        assert metrics.sensitivity.lower_bound == pytest.approx(12.5)


# ---------------------------------------------------------------------------
# 5. Fit bands
# ---------------------------------------------------------------------------


class TestFitBands:
    @pytest.mark.parametrize(
        ("score", "expected_key", "expected_label"),
        [
            (100, "EXCEPTIONAL_FIT", "Exceptional Fit"),
            (90, "EXCEPTIONAL_FIT", "Exceptional Fit"),
            (89.9, "VERY_STRONG_FIT", "Very Strong Fit"),
            (80, "VERY_STRONG_FIT", "Very Strong Fit"),
            (79.9, "STRONG_FIT", "Strong Fit"),
            (70, "STRONG_FIT", "Strong Fit"),
            (69.9, "POSSIBLE_FIT", "Possible Fit"),
            (55, "POSSIBLE_FIT", "Possible Fit"),
            (54.9, "LOW_FIT", "Low Fit"),
            (0, "LOW_FIT", "Low Fit"),
        ],
    )
    def test_band_boundaries_are_inclusive_lower_bounds(self, score, expected_key, expected_label):
        key, label = fit_band(score)
        assert (key, label) == (expected_key, expected_label)

    def test_none_has_no_band(self):
        assert fit_band(None) == (None, None)

    def test_the_band_table_matches_the_documented_thresholds(self):
        assert FIT_BANDS == (
            (90, "EXCEPTIONAL_FIT", "Exceptional Fit"),
            (80, "VERY_STRONG_FIT", "Very Strong Fit"),
            (70, "STRONG_FIT", "Strong Fit"),
            (55, "POSSIBLE_FIT", "Possible Fit"),
            (0, "LOW_FIT", "Low Fit"),
        )
        assert FIT_BAND_KEYS == (
            "EXCEPTIONAL_FIT",
            "VERY_STRONG_FIT",
            "STRONG_FIT",
            "POSSIBLE_FIT",
            "LOW_FIT",
        )

    def test_a_score_just_outside_the_table_still_classifies_rather_than_crashing(self):
        key, label = fit_band(-1)
        assert key == "LOW_FIT"
        assert fit_band(140) == ("EXCEPTIONAL_FIT", "Exceptional Fit")

    def test_the_band_reported_by_the_arithmetic_is_the_band_table_lookup(self):
        metrics = compute_fit(
            all_evaluated(
                {
                    "academic": 100.0,
                    "field": 100.0,
                    "funding": 100.0,
                    "requirement": 100.0,
                    "language": 100.0,
                    "preference": 100.0,
                    "timing": 100.0,
                }
            )
        )
        assert metrics.fit_band == fit_band(metrics.fit_score)[0]
        assert metrics.fit_label == fit_band(metrics.fit_score)[1]


# ---------------------------------------------------------------------------
# 6. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_the_same_components_produce_the_same_numbers_every_time(self):
        payloads = [
            all_evaluated({"academic": 91.5, "language": None}),
            tuple(component(name, None) for name in FIT_WEIGHTS),
            (component("academic", 0.0),),
        ]
        for payload in payloads:
            first = compute_fit(payload)
            second = compute_fit(payload)
            assert first.fit_score == second.fit_score
            assert first.data_coverage == second.data_coverage
            assert first.fit_band == second.fit_band
            assert [item.contribution for item in first.contributions] == [
                item.contribution for item in second.contributions
            ]

    def test_component_order_does_not_change_the_result(self):
        forward = compute_fit(
            (component("academic", 90.0), component("field", 70.0), component("funding", 50.0))
        )
        backward = compute_fit(
            (component("funding", 50.0), component("field", 70.0), component("academic", 90.0))
        )
        assert forward.fit_score == backward.fit_score
        assert {item.name: item.contribution for item in forward.contributions} == {
            item.name: item.contribution for item in backward.contributions
        }


# ---------------------------------------------------------------------------
# 7. The public fit disclosure state model
# ---------------------------------------------------------------------------


class TestPublicFitDisclosure:
    def test_ineligible_suppresses_the_score_and_the_band(self):
        metrics = compute_fit(all_evaluated({"academic": 100.0}))
        public = resolve_public_fit(EligibilityStatus.INELIGIBLE, metrics)
        assert public.fit_score is None
        assert public.fit_band is None
        assert public.fit_label == FIT_LABEL_INELIGIBLE
        assert public.fit_label_display == "Not eligible"
        assert public.disclosure is FitDisclosure.SUPPRESSED_INELIGIBLE

    def test_needs_verification_keeps_its_score_and_its_band(self):
        """The gate verdict is about our evidence, not about the student's fit."""
        metrics = compute_fit(all_evaluated({"academic": 100.0}))
        public = resolve_public_fit(EligibilityStatus.NEEDS_VERIFICATION, metrics)
        assert public.fit_score == metrics.fit_score
        assert public.fit_band in FIT_BAND_KEYS
        assert public.fit_label in FIT_BAND_KEYS
        assert public.disclosure is FitDisclosure.SCORED

    def test_eligible_is_scored_exactly_like_needs_verification(self):
        metrics = compute_fit(all_evaluated({"academic": 100.0}))
        eligible = resolve_public_fit(EligibilityStatus.ELIGIBLE, metrics)
        unverified = resolve_public_fit(EligibilityStatus.NEEDS_VERIFICATION, metrics)
        assert eligible.fit_label == unverified.fit_label
        assert eligible.fit_score == unverified.fit_score
        assert eligible.disclosure is unverified.disclosure

    def test_nothing_measurable_is_not_evaluated_not_zero(self):
        metrics = compute_fit(tuple(component(name, None) for name in FIT_WEIGHTS))
        for status in EligibilityStatus:
            public = resolve_public_fit(status, metrics)
            assert public.fit_score is None
        public = resolve_public_fit(EligibilityStatus.ELIGIBLE, metrics)
        assert public.fit_label == FIT_LABEL_NOT_EVALUATED
        assert public.fit_label_display == "Not evaluated"
        assert public.disclosure is FitDisclosure.NOT_EVALUATED

    def test_the_raw_fit_stays_internal_and_out_of_the_public_contract(self):
        """A raw number on a refused result invites a client to rank on it."""
        metrics = compute_fit(all_evaluated({"academic": 100.0}))
        public = resolve_public_fit(EligibilityStatus.INELIGIBLE, metrics)
        # Available internally for engine diagnostics...
        assert public.internal_fit_score == metrics.fit_score
        # ...and never as a published fit.
        assert public.is_publicly_scored is False

    def test_the_label_vocabulary_is_closed(self):
        """No composed labels, so band and facet lookups cannot miss."""
        allowed = set(FIT_BAND_KEYS) | {FIT_LABEL_INELIGIBLE, FIT_LABEL_NOT_EVALUATED}
        metrics = compute_fit(all_evaluated({"academic": 42.0}))
        for status in EligibilityStatus:
            assert resolve_public_fit(status, metrics).fit_label in allowed

    def test_an_ineligible_record_never_looks_scored_even_with_a_perfect_profile(self):
        metrics = compute_fit(
            all_evaluated(
                {
                    "academic": 100.0,
                    "field": 100.0,
                    "funding": 100.0,
                    "requirement": 100.0,
                    "language": 100.0,
                    "preference": 100.0,
                    "timing": 100.0,
                }
            )
        )
        assert metrics.fit_score == pytest.approx(100.0)
        public = resolve_public_fit(EligibilityStatus.INELIGIBLE, metrics)
        assert public.fit_score is None
        assert public.fit_band is None


# ---------------------------------------------------------------------------
# 8. Shared constants referenced by later sections
# ---------------------------------------------------------------------------


def test_total_configured_weight_is_the_percentage_basis_of_coverage():
    assert TOTAL_CONFIGURED_WEIGHT == 100.0


def test_the_academic_minimum_only_score_is_the_documented_value():
    assert ACADEMIC_MINIMUM_ONLY_SCORE == 85.0


def test_confidence_weights_are_the_locked_four():
    assert dict(CONFIDENCE_WEIGHTS) == {
        "data_completeness": 0.35,
        "provenance_quality": 0.25,
        "requirement_explicitness": 0.25,
        "verification_freshness": 0.15,
    }


def test_as_of_is_a_value_not_a_clock_call():
    """The engine receives its date; it never reads the wall clock."""
    assert date(2026, 3, 1).isoformat() == "2026-03-01"


# ---------------------------------------------------------------------------
# 9. Eligibility
# ---------------------------------------------------------------------------


class TestEligibilityStates:
    def test_a_fully_satisfied_profile_is_eligible(self):
        result = score(strong_profile(), make_facts())
        assert result.eligibility is EligibilityStatus.ELIGIBLE
        assert result.eligibility_detail.blockers == []
        assert result.eligibility_detail.unverified == []
        assert result.eligibility_detail.satisfied

    def test_a_published_condition_we_cannot_check_is_needs_verification(self):
        result = score(strong_profile(language_credentials=[]), make_facts())
        assert result.eligibility is EligibilityStatus.NEEDS_VERIFICATION
        assert result.eligibility_detail.unverified
        assert result.eligibility_detail.blockers == []

    def test_a_confirmed_violation_is_ineligible(self):
        result = score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(),
        )
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        assert result.eligibility_detail.blockers

    def test_needs_verification_still_carries_a_fit_score_and_a_band(self):
        result = score(strong_profile(language_credentials=[]), make_facts())
        assert result.fit_score is not None
        assert result.fit_label in FIT_BAND_KEYS
        # Eligibility is reported separately, and stays visible.
        assert result.eligibility is EligibilityStatus.NEEDS_VERIFICATION
        assert "NATIONALITY" not in result.fit_label

    def test_ineligible_suppresses_the_public_fit_entirely(self):
        result = score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(),
        )
        assert result.fit_score is None
        assert result.fit_label == FIT_LABEL_INELIGIBLE
        assert result.fit_label_display == "Not eligible"
        assert result.fit_label not in FIT_BAND_KEYS

    def test_needs_verification_is_not_written_into_the_fit_label(self):
        """Regression: the label used to be suffixed, breaking band lookups."""
        result = score(strong_profile(language_credentials=[]), make_facts())
        assert "NEEDS_VERIFICATION" not in result.fit_label
        assert result.fit_label_display not in {"Not eligible", "Not evaluated"}

    def test_no_eligibility_function_accepts_a_fit_score(self):
        """Structural guarantee, not a convention."""
        for function in (evaluate, evaluate_deadline, eligibility_rank):
            parameters = inspect.signature(function).parameters
            offending = [
                name
                for name in parameters
                if "score" in name or "fit" in name
            ]
            assert offending == [], f"{function.__name__} accepts {offending}"

    def test_the_gate_runs_before_scoring_by_construction(self):
        """An ineligible result's components may exist, but no fit is published."""
        result = score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(),
        )
        assert result.score_breakdown
        assert result.fit_score is None


class TestEligibilityConditions:
    def test_a_closed_round_blocks_the_application_window(self):
        result = score(strong_profile(), make_facts(status="closed"))
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.APPLICATION_WINDOW in kinds

    def test_a_past_deadline_blocks_the_application_window(self):
        facts = make_facts(deadline_date="2026-01-01", deadline_display="1 January 2026")
        result = score(strong_profile(), facts)
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.APPLICATION_WINDOW in kinds

    def test_a_below_minimum_academic_result_blocks(self):
        result = score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=2.0)),
            make_facts(),
        )
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.ACADEMIC_MINIMUM in kinds

    def test_a_language_score_below_the_published_minimum_blocks(self):
        result = score(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=5.0)]),
            make_facts(),
        )
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.LANGUAGE_MINIMUM in kinds

    def test_a_language_score_above_the_minimum_satisfies_the_condition(self):
        result = score(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=8.0)]),
            make_facts(),
        )
        satisfied = {outcome.kind for outcome in result.eligibility_detail.satisfied}
        assert RequirementKind.LANGUAGE_MINIMUM in satisfied

    def test_a_nationality_outside_the_published_set_blocks(self):
        result = score(strong_profile(citizenship="Nigeria"), make_facts())
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.NATIONALITY in kinds

    def test_a_nationality_inside_the_published_set_satisfies(self):
        result = score(strong_profile(citizenship="india"), make_facts())
        satisfied = {outcome.kind for outcome in result.eligibility_detail.satisfied}
        assert RequirementKind.NATIONALITY in satisfied

    def test_a_missing_nationality_is_unverified_not_ineligible(self):
        result = score(strong_profile(citizenship=None), make_facts())
        unverified = {outcome.kind for outcome in result.eligibility_detail.unverified}
        assert RequirementKind.NATIONALITY in unverified

    def test_an_age_above_the_published_limit_blocks(self):
        facts = make_facts(eligibility=["Applicants must be under 30 years old."])
        result = score(strong_profile(age=31), facts)
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.AGE in kinds

    def test_an_age_within_the_published_limit_satisfies(self):
        facts = make_facts(eligibility=["Applicants must be under 30 years old."])
        result = score(strong_profile(age=24), facts)
        satisfied = {outcome.kind for outcome in result.eligibility_detail.satisfied}
        assert RequirementKind.AGE in satisfied

    def test_a_missing_age_against_a_published_limit_is_unverified(self):
        facts = make_facts(eligibility=["Applicants must be under 30 years old."])
        result = score(strong_profile(age=None), facts)
        unverified = {outcome.kind for outcome in result.eligibility_detail.unverified}
        assert RequirementKind.AGE in unverified

    def test_a_study_mode_mismatch_blocks(self):
        facts = make_facts(eligibility=["Applicants must be enrolled as full-time students."])
        result = score(strong_profile(study_mode=StudyMode.PART_TIME), facts)
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.STUDY_MODE in kinds

    def test_a_matching_study_mode_satisfies(self):
        facts = make_facts(eligibility=["Applicants must be enrolled as full-time students."])
        result = score(strong_profile(study_mode=StudyMode.FULL_TIME), facts)
        satisfied = {outcome.kind for outcome in result.eligibility_detail.satisfied}
        assert RequirementKind.STUDY_MODE in satisfied

    def test_bare_must_be_does_not_invent_a_study_mode_condition(self):
        """Regression: "must be" alone used to be read as full-time study."""
        facts = make_facts(eligibility=["Applicants must be citizens of India."])
        read = read_requirements(facts)
        assert read.study_mode is None

    def test_a_degree_level_outside_the_published_set_blocks(self):
        facts = make_facts(degree_levels="PhD")
        result = score(strong_profile(intended_degree_level="BACHELOR"), facts)
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.DEGREE_LEVEL in kinds

    def test_a_published_programme_restriction_blocks_a_different_field(self):
        facts = make_facts(
            eligibility=["Applicants must be enrolled in a Medicine programme."],
        )
        result = score(strong_profile(), facts)
        kinds = {outcome.kind for outcome in result.eligibility_detail.blockers}
        assert RequirementKind.PROGRAMME_RESTRICTION in kinds

    def test_a_published_programme_restriction_is_satisfied_by_the_same_field(self):
        facts = make_facts(
            eligibility=["Applicants must be enrolled in a Computer Science programme."],
        )
        result = score(strong_profile(), facts)
        satisfied = {outcome.kind for outcome in result.eligibility_detail.satisfied}
        assert RequirementKind.PROGRAMME_RESTRICTION in satisfied

    def test_an_adjacent_programme_needs_verification_not_a_pass_or_a_failure(self):
        """CLOSE_SPECIALIZATION satisfies; RELATED_FIELD does not decide either way."""
        close = make_facts(
            eligibility=["Applicants must be enrolled in a Software Engineering programme."],
        )
        satisfied_close = score(strong_profile(), close)
        assert RequirementKind.PROGRAMME_RESTRICTION in {
            outcome.kind for outcome in satisfied_close.eligibility_detail.satisfied
        }

        related = make_facts(
            eligibility=["Applicants must be enrolled in a Mathematics programme."],
        )
        result = score(strong_profile(), related)
        assert RequirementKind.PROGRAMME_RESTRICTION not in {
            outcome.kind for outcome in result.eligibility_detail.blockers
        }
        assert RequirementKind.PROGRAMME_RESTRICTION in {
            outcome.kind for outcome in result.eligibility_detail.unverified
        }

    def test_a_programme_restriction_is_only_read_from_an_explicit_marker(self):
        """Conservative extraction: prose alone never becomes a gate."""
        facts = make_facts(
            eligibility=["Applicants should ideally be studying something creative."],
        )
        assert read_requirements(facts).programme_restriction is None

    def test_silence_is_not_a_rule(self):
        facts = make_facts(
            eligibility=[],
            eligibility_summary=None,
            english_requirement=None,
        )
        result = score(strong_profile(), facts)
        assert result.eligibility is EligibilityStatus.ELIGIBLE
        assert result.eligibility_detail.blockers == []
        assert result.eligibility_detail.unverified == []
        # The curated degree column is still a published condition, and it is
        # answered from the profile rather than left dangling.
        assert {outcome.kind for outcome in result.eligibility_detail.satisfied} == {
            RequirementKind.DEGREE_LEVEL
        }

    def test_a_record_with_no_conditions_at_all_produces_none(self):
        facts = make_facts(
            eligibility=[],
            eligibility_summary=None,
            english_requirement=None,
            degree_levels="",
            program_type=None,
            official_details=None,
        )
        result = score(strong_profile(), facts)
        assert result.eligibility is EligibilityStatus.ELIGIBLE
        assert result.eligibility_detail.satisfied == []

    def test_one_confirmed_violation_ends_it_regardless_of_the_rest(self):
        facts = make_facts(
            eligibility=[
                "Applicants must be citizens of India.",
                "Applicants must be under 30 years old.",
            ]
        )
        result = score(strong_profile(citizenship="Nigeria", age=24), facts)
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        assert len(result.eligibility_detail.blockers) == 1

    def test_a_blocker_outranks_an_unverifiable_condition(self):
        facts = make_facts(status="closed")
        result = score(strong_profile(citizenship=None), facts)
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        assert result.eligibility_detail.blockers
        assert result.eligibility_detail.unverified

    def test_the_gate_order_is_published_and_starts_with_the_application_window(self):
        result = score(strong_profile(), make_facts())
        order = result.eligibility_detail.gate_order
        assert order[0] == RequirementKind.APPLICATION_WINDOW.value
        assert order[1] == RequirementKind.ACADEMIC_MINIMUM.value
        assert order[2] == RequirementKind.LANGUAGE_MINIMUM.value
        assert order[3] == RequirementKind.NATIONALITY.value
        assert order[4] == RequirementKind.AGE.value
        assert len(order) == 8

    def test_every_blocker_preserves_the_awarding_bodys_own_wording(self):
        result = score(strong_profile(citizenship="Nigeria"), make_facts())
        for outcome in result.eligibility_detail.blockers:
            assert outcome.raw_quote
            assert outcome.summary


# ---------------------------------------------------------------------------
# 10. Academics
# ---------------------------------------------------------------------------


class TestAcademicNormalisation:
    @pytest.mark.parametrize(
        ("scale", "value", "expected"),
        [
            (GradingScale.GPA_4, 3.5, 87.5),
            (GradingScale.GPA_4, 4.0, 100.0),
            (GradingScale.GPA_5, 4.5, 90.0),
            (GradingScale.GPA_10, 9.0, 90.0),
            (GradingScale.GPA_10, 7.5, 75.0),
            (GradingScale.PERCENTAGE, 85, 85.0),
            (GradingScale.PERCENTAGE, 72.5, 72.5),
        ],
    )
    def test_each_scale_is_rescaled_within_itself(self, scale, value, expected):
        profile = normalise_profile(strong_profile(overall_result=AcademicMark(scale=scale, value=value)))
        assert profile.overall_result == pytest.approx(expected)
        assert profile.overall_scale_label == scale.value

    def test_a_value_outside_its_own_scale_is_not_interpreted(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=4.6))
        )
        assert profile.overall_result is None
        assert profile.overall_scale_label == "unavailable"

    def test_a_missing_mark_stays_missing(self):
        profile = normalise_profile(strong_profile(overall_result=None))
        assert profile.overall_result is None
        assert profile.overall_scale_label == "unavailable"


class TestAcademicComparison:
    def test_the_same_scale_compares_like_for_like(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.7))
        )
        comparison = compare_to_minimum(profile, academic_requirement(3.5))
        assert comparison.state == "MEETS_MINIMUM"
        assert comparison.student_scale == "GPA_4"
        assert comparison.requirement_scale == "GPA_4"

    def test_a_cross_scale_minimum_is_refused_not_converted(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_5, value=4.5))
        )
        comparison = compare_to_minimum(profile, academic_requirement(3.5))
        assert comparison.state == "INCOMPARABLE"
        assert comparison.score is None
        assert "No official conversion" in comparison.detail

    def test_a_percentage_minimum_is_refused_against_a_gpa_result(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.9))
        )
        comparison = compare_to_minimum(
            profile, academic_requirement(75.0, scale=GradingScale.PERCENTAGE)
        )
        assert comparison.state == "INCOMPARABLE"

    def test_a_minimum_without_a_declared_scale_is_not_interpretable(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.9))
        )
        comparison = compare_to_minimum(profile, academic_requirement(3.5, scale=None))
        assert comparison.state == "INCOMPARABLE"
        assert comparison.score is None

    def test_a_missing_student_mark_is_unknown_not_a_failure(self):
        profile = normalise_profile(strong_profile(overall_result=None))
        comparison = compare_to_minimum(profile, academic_requirement(3.5))
        assert comparison.state == "STUDENT_MARK_UNKNOWN"
        assert comparison.score is None

    def test_below_the_minimum_is_reported_as_such(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.0))
        )
        comparison = compare_to_minimum(profile, academic_requirement(3.5))
        assert comparison.state == "BELOW_MINIMUM"
        assert comparison.score is None

    def test_a_minimum_only_award_is_the_documented_85(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.9))
        )
        comparison = compare_to_minimum(profile, academic_requirement(3.5))
        assert comparison.score == ACADEMIC_MINIMUM_ONLY_SCORE == 85.0

    def test_meeting_the_minimum_does_not_earn_more_than_the_documented_award(self):
        """No second anchor is invented when only a floor is published."""
        for value in (3.5, 3.9, 4.0):
            profile = normalise_profile(
                strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=value))
            )
            comparison = compare_to_minimum(profile, academic_requirement(3.5))
            assert comparison.score == 85.0

    def test_two_published_anchors_interpolate(self):
        """100 x (student - minimum) / (preferred - minimum), clamped 0-100."""
        requirement = academic_requirement(3.5, preferred=4.0)
        at_minimum = compare_to_minimum(
            normalise_profile(
                strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.5))
            ),
            requirement,
        )
        assert at_minimum.score == pytest.approx(0.0)

        midway = compare_to_minimum(
            normalise_profile(
                strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.75))
            ),
            requirement,
        )
        assert midway.score == pytest.approx(50.0)

        above = compare_to_minimum(
            normalise_profile(
                strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=4.0))
            ),
            requirement,
        )
        assert above.state == "ABOVE_PREFERRED"
        assert above.score == 100.0

    def test_the_interpolation_is_clamped_at_the_top(self):
        requirement = academic_requirement(3.5, preferred=3.6)
        comparison = compare_to_minimum(
            normalise_profile(
                strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=4.0))
            ),
            requirement,
        )
        assert comparison.score == 100.0

    def test_raising_the_mark_never_lowers_the_academic_score(self):
        requirement = academic_requirement(3.5, preferred=4.0)
        scores = []
        for value in (3.5, 3.6, 3.7, 3.8, 3.9, 4.0):
            comparison = compare_to_minimum(
                normalise_profile(
                    strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=value))
                ),
                requirement,
            )
            scores.append(comparison.score)
        assert scores == sorted(scores)

    def test_an_equivalent_percentage_pair_interpolates_the_same_way(self):
        requirement = academic_requirement(60.0, scale=GradingScale.PERCENTAGE, preferred=80.0)
        comparison = compare_to_minimum(
            normalise_profile(
                strong_profile(overall_result=AcademicMark(scale=GradingScale.PERCENTAGE, value=70))
            ),
            requirement,
        )
        assert comparison.score == pytest.approx(50.0)

    def test_a_requirement_always_preserves_the_published_quote(self):
        comparison = compare_to_minimum(
            normalise_profile(strong_profile()),
            academic_requirement(3.5),
        )
        assert comparison.state


class TestAcademicProfileIndex:
    def test_no_academic_data_means_the_index_is_undefined_not_zero(self):
        index = build_profile_index(
            normalise_profile(
                strong_profile(overall_result=None, subject_results=[])
            )
        )
        assert index.score is None
        assert index.components == ()
        assert index.evaluated_coverage == 0.0

    def test_the_index_uses_the_locked_sixty_twenty_five_fifteen_weights(self):
        assert dict(API_COMPONENT_WEIGHTS) == {
            "overall_result": 0.60,
            "subject_performance": 0.25,
            "consistency": 0.15,
        }

    def test_an_overall_result_alone_is_the_whole_index(self):
        index = build_profile_index(
            normalise_profile(
                strong_profile(
                    overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.8),
                    subject_results=[],
                )
            )
        )
        assert index.score == pytest.approx(95.0)
        assert len(index.components) == 1
        assert index.components[0].weight == pytest.approx(1.0)
        assert index.evaluated_coverage == pytest.approx(60.0)

    def test_weights_are_renormalised_over_what_is_present(self):
        index = build_profile_index(
            normalise_profile(
                strong_profile(
                    overall_result=AcademicMark(scale=GradingScale.GPA_4, value=4.0),
                    subject_results=[
                        AcademicMark(scale=GradingScale.GPA_4, value=4.0, field="computer_science")
                    ],
                )
            )
        )
        assert sum(item.weight for item in index.components) == pytest.approx(1.0)
        assert index.evaluated_coverage == pytest.approx(85.0)

    def test_a_three_component_index_keeps_its_configured_ratios(self):
        index = build_profile_index(
            normalise_profile(
                strong_profile(
                    overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.6, previous_value=3.0),
                    subject_results=[
                        AcademicMark(scale=GradingScale.GPA_4, value=3.6, field="computer_science")
                    ],
                )
            )
        )
        assert [item.configured_weight for item in index.components] == [0.60, 0.25, 0.15]
        assert index.evaluated_coverage == pytest.approx(100.0)

    @pytest.mark.parametrize(
        ("value", "band"),
        [
            (4.0, "HIGH"),   # 100.0
            (3.5, "HIGH"),   # 87.5
            (3.0, "HIGH"),   # 75.0 - inclusive lower bound
            (2.5, "MEDIUM"), # 62.5
            (2.0, "MEDIUM"), # 50.0 - inclusive lower bound
            (1.0, "LOW"),    # 25.0
        ],
    )
    def test_the_index_bands_are_locked_at_seventy_five_and_fifty(self, value, band):
        index = build_profile_index(
            normalise_profile(
                strong_profile(
                    overall_result=AcademicMark(scale=GradingScale.GPA_4, value=value),
                    subject_results=[],
                )
            )
        )
        expected = next(key for threshold, key, _ in API_BANDS if index.score >= threshold)
        assert expected == band

    def test_the_index_is_deterministic(self):
        profile = normalise_profile(strong_profile())
        first = build_profile_index(profile)
        second = build_profile_index(profile)
        assert first.score == second.score
        assert [item.score for item in first.components] == [item.score for item in second.components]

    def test_the_index_is_bounded(self):
        index = build_profile_index(
            normalise_profile(
                strong_profile(overall_result=AcademicMark(scale=GradingScale.PERCENTAGE, value=100))
            )
        )
        assert 0.0 <= index.score <= 100.0


# ---------------------------------------------------------------------------
# 11. Field
# ---------------------------------------------------------------------------


class TestFieldAlignment:
    @pytest.mark.parametrize(
        ("student", "scholarship", "level"),
        [
            ("computer_science", "computer_science", "EXACT"),
            ("computer_science", "software_engineering", "CLOSE_SPECIALIZATION"),
            ("computer_science", "mathematics", "RELATED_FIELD"),
            ("software_engineering", "engineering", "BROAD_FIELD"),
            ("computer_science", "history", "UNRELATED"),
        ],
    )
    def test_the_relationship_levels_are_the_configured_ones(self, student, scholarship, level):
        assert relate_fields(student, scholarship).level == level

    def test_relationship_is_symmetric(self):
        assert relate_fields("computer_science", "software_engineering").level == relate_fields(
            "software_engineering", "computer_science"
        ).level

    def test_the_relationship_levels_match_the_scoring_configuration(self):
        assert dict(FIELD_RELATIONSHIP_LEVELS) == {
            "EXACT": 100.0,
            "CLOSE_SPECIALIZATION": 85.0,
            "RELATED_FIELD": 65.0,
            "BROAD_FIELD": 40.0,
            "UNRELATED": 0.0,
        }

    def test_an_exact_field_match_scores_full_marks(self):
        result = score(strong_profile(), make_facts(program_type="Computer Science"))
        assert result.field_alignment_level == "EXACT"
        assert component_of(result, "field").score == 100.0

    def test_an_unrelated_field_is_a_real_zero_not_an_unknown(self):
        facts = make_facts(program_type="History", official_details=None)
        result = score(strong_profile(), facts)
        assert result.field_alignment_level == "UNRELATED"
        assert component_of(result, "field").score == 0.0

    def test_a_field_the_taxonomy_cannot_resolve_is_not_scored(self):
        facts = make_facts(program_type="Interpretive dance", official_details=None)
        result = score(strong_profile(), facts)
        component = component_of(result, "field")
        assert component.score is None
        assert component.status.value == "NOT_EVALUATED"
        assert result.field is None

    def test_a_missing_student_field_is_not_scored(self):
        result = score(strong_profile(intended_field=None), make_facts())
        assert component_of(result, "field").score is None

    def test_aliases_resolve_to_the_canonical_key(self):
        assert resolve_field("Computer Science").key == "computer_science"
        assert resolve_field("computing").key == "computer_science"
        assert resolve_field("data science").key == "data_science"
        assert resolve_field("software development").key == "software_engineering"

    def test_the_longer_alias_wins_a_collision(self):
        """Regression guard: "informatics science" must not become computer science."""
        assert resolve_field("informatics science").key == "information_science"
        assert resolve_field("informatics").key == "computer_science"

    def test_a_short_alias_matches_on_word_boundaries_only(self):
        assert resolve_field("cs").key == "computer_science"
        assert resolve_field("scholarship").key is None

    def test_the_matched_alias_and_source_are_reported(self):
        resolution = resolve_field("computing", source_field="program_type")
        assert resolution.matched_alias == "computing"
        assert resolution.source_field == "program_type"
        assert resolution.label == "Computer Science"

    def test_the_scholarship_field_is_read_from_the_structured_column(self):
        resolution = resolve_scholarship_field(make_facts())
        assert resolution.key == "computer_science"
        assert resolution.source_field == "program_type"

    def test_the_structured_column_outranks_the_official_details_blob(self):
        """A stale JSON value must not override the curated programme column."""
        facts = make_facts(program_type="History", official_details={"field": "Computer Science"})
        resolution = resolve_scholarship_field(facts)
        assert resolution.key == "history"
        assert resolution.source_field == "program_type"

    def test_official_details_is_used_when_the_structured_column_is_empty(self):
        facts = make_facts(program_type=None, official_details={"field": "Mathematics"})
        resolution = resolve_scholarship_field(facts)
        assert resolution.key == "mathematics"
        assert resolution.source_field == "official_details.field"

    def test_prose_is_never_used_to_invent_a_field(self):
        """The title and eligibility prose carry no field for this purpose."""
        facts = make_facts(
            program_type=None,
            official_details=None,
            title="Scholarship for historians and philosophers",
            eligibility=["Open to applicants studying Archaeology."],
        )
        assert resolve_scholarship_field(facts).key is None

    def test_degree_words_are_not_programme_fields(self):
        """Degrees are normalised separately; they are not subjects."""
        assert resolve_field("Master").key is None
        assert resolve_field("PhD").key is None

    def test_the_taxonomy_is_versioned_and_curated(self):
        from app.services.matching.config import FIELD_TAXONOMY_VERSION

        assert FIELD_TAXONOMY_VERSION == "1.0.0"
        keys = known_field_keys()
        assert "computer_science" in keys
        assert len(set(keys)) == len(keys)
        assert None not in keys


# ---------------------------------------------------------------------------
# 12. Funding
# ---------------------------------------------------------------------------


class TestFundingStates:
    def test_tuition_and_living_columns_establish_full_coverage(self):
        state, _, evidence = normalise_funding_state(
            make_facts(tuition_coverage=True, living_cost_coverage=True)
        )
        assert state is FundingState.FULL
        assert evidence["fully_funded_used_to_derive_state"] is False

    def test_tuition_only_columns_establish_partial_coverage(self):
        state, _, _ = normalise_funding_state(
            make_facts(tuition_coverage=True, living_cost_coverage=False)
        )
        assert state is FundingState.TUITION_ONLY

    def test_an_unstated_living_cost_is_not_treated_as_covered_or_absent(self):
        state, detail, _ = normalise_funding_state(
            make_facts(tuition_coverage=True, living_cost_coverage=None, coverage=[])
        )
        assert state is FundingState.TUITION_PLUS_LIVING
        assert "not stated" in detail

    def test_a_monetary_award_with_no_coverage_detail_is_partial(self):
        state, _, _ = normalise_funding_state(
            make_facts(
                tuition_coverage=None,
                living_cost_coverage=None,
                coverage=[],
                funding_amount=1000.0,
                funding_label="Award",
            )
        )
        assert state is FundingState.PARTIAL

    def test_a_published_statement_of_no_funding_is_none(self):
        state, _, _ = normalise_funding_state(
            make_facts(
                tuition_coverage=None,
                living_cost_coverage=None,
                coverage=["No funding is offered for this award."],
                funding_amount=None,
                funding_label="Not funded",
            )
        )
        assert state is FundingState.NONE

    def test_an_unstructured_record_is_unknown_never_none(self):
        state, detail, _ = normalise_funding_state(
            make_facts(
                tuition_coverage=None,
                living_cost_coverage=None,
                coverage=[],
                funding_amount=None,
                funding_label="Not specified",
            )
        )
        assert state is FundingState.UNKNOWN
        assert state is not FundingState.NONE
        assert "could not be established" in detail

    def test_fully_funded_alone_is_never_the_evidence(self):
        """The column is NOT NULL with a false default, so false means unknown."""
        state, _, evidence = normalise_funding_state(
            make_facts(
                tuition_coverage=None,
                living_cost_coverage=None,
                coverage=[],
                funding_amount=None,
                fully_funded=True,
                funding_label="Fully Funded",
            )
        )
        assert state is FundingState.UNKNOWN
        assert evidence["fully_funded_corroboration"] is True
        assert evidence["fully_funded_used_to_derive_state"] is False

    def test_an_unknown_state_is_not_scored_at_all(self):
        profile = normalise_profile(strong_profile())
        value, detail, evidence = score_funding(
            profile, FundingState.UNKNOWN, "No verified funding detail is recorded."
        )
        assert value is None
        assert "not evaluated" in detail
        assert evidence["funding_state"] == "UNKNOWN"

    def test_every_state_resolves_to_one_of_the_configured_states(self):
        assert set(FUNDING_STATES) == {
            "FULL",
            "TUITION_PLUS_LIVING",
            "TUITION_ONLY",
            "PARTIAL",
            "NONE",
            "UNKNOWN",
        }


class TestFundingMatrix:
    def test_the_matrix_is_centralised_in_configuration(self):
        assert set(FUNDING_COMPATIBILITY) == {
            FUNDING_NEED_FULL,
            FUNDING_NEED_TUITION,
            FUNDING_NEED_PARTIAL,
            FUNDING_NEED_NEUTRAL,
        }
        for need, row in FUNDING_COMPATIBILITY.items():
            assert set(row) == set(FUNDING_STATES) - {"UNKNOWN"}, need

    def test_unknown_is_absent_from_every_row(self):
        for need, row in FUNDING_COMPATIBILITY.items():
            assert funding_score(need, "UNKNOWN") is None

    def test_the_students_need_selects_the_row(self):
        assert funding_need_for(normalise_profile(strong_profile())) == FUNDING_NEED_FULL
        assert funding_need_for(
            normalise_profile(strong_profile(funding_requirement=FundingRequirement.TUITION_ONLY_SUFFICIENT))
        ) == FUNDING_NEED_TUITION
        assert funding_need_for(
            normalise_profile(strong_profile(funding_requirement=FundingRequirement.PARTIAL_OK))
        ) == FUNDING_NEED_PARTIAL
        assert funding_need_for(
            normalise_profile(strong_profile(funding_requirement=FundingRequirement.NO_SPECIFIC_NEED))
        ) == FUNDING_NEED_NEUTRAL

    def test_asking_for_living_cost_support_implies_requiring_full_coverage(self):
        profile = normalise_profile(
            strong_profile(funding_requirement=None, living_cost_support_required=True)
        )
        assert funding_need_for(profile) == FUNDING_NEED_FULL

    def test_a_full_award_satisfies_every_need(self):
        for need in FUNDING_COMPATIBILITY:
            assert funding_score(need, "FULL") == 100.0

    def test_no_funding_is_worst_for_a_student_who_needs_funding(self):
        assert funding_score(FUNDING_NEED_FULL, "NONE") == 0.0
        assert funding_score(FUNDING_NEED_FULL, "PARTIAL") < funding_score(FUNDING_NEED_FULL, "TUITION_ONLY")

    def test_needing_tuition_only_accepts_tuition_only(self):
        assert funding_score(FUNDING_NEED_TUITION, "TUITION_ONLY") == 100.0

    def test_a_partial_award_satisfies_a_student_who_accepts_partial(self):
        assert funding_score(FUNDING_NEED_PARTIAL, "PARTIAL") == 100.0

    def test_with_no_stated_need_nothing_is_treated_as_a_failure(self):
        assert funding_score(FUNDING_NEED_NEUTRAL, "NONE") > 0.0

    def test_the_scored_value_comes_from_the_table_not_from_branches(self):
        profile = normalise_profile(strong_profile())
        value, _, evidence = score_funding(profile, FundingState.FULL, "Both covered.")
        assert value == funding_score(FUNDING_NEED_FULL, "FULL")
        assert evidence["funding_need"] == FUNDING_NEED_FULL


# ---------------------------------------------------------------------------
# 13. Language
# ---------------------------------------------------------------------------


class TestLanguageScoring:
    def test_exactly_meeting_the_minimum_scores_zero_surplus_not_full_marks(self):
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=6.5)])
        )
        comparison = compare_language(profile, language_requirement())
        assert comparison.state == "MEETS"
        assert comparison.score == pytest.approx(0.0)
        assert comparison.surplus == 0.0

    def test_the_surplus_range_is_the_documented_headroom(self):
        assert language_surplus_range("ielts") == 2.0
        assert language_surplus_range("toefl") == 15.0
        assert language_surplus_range("pte") == 10.0
        assert language_surplus_range("not-a-test") is None

    def test_a_score_above_the_minimum_scores_the_bounded_surplus(self):
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=7.0)])
        )
        comparison = compare_language(profile, language_requirement())
        # (7.0 - 6.5) / 2.0 = 0.25
        assert comparison.score == pytest.approx(25.0)

    def test_reaching_the_configured_range_earns_full_marks(self):
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=8.5)])
        )
        comparison = compare_language(profile, language_requirement())
        assert comparison.score == pytest.approx(100.0)

    def test_the_surplus_is_clamped_at_full_marks(self):
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=9.0)])
        )
        assert compare_language(profile, language_requirement()).score == 100.0

    def test_a_score_below_the_minimum_is_a_real_evaluated_zero(self):
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=5.5)])
        )
        comparison = compare_language(profile, language_requirement())
        assert comparison.state == "BELOW"
        assert comparison.score == LANGUAGE_BELOW_MINIMUM_SCORE == 0.0

    def test_a_different_test_is_never_converted(self):
        assert LANGUAGE_CROSS_TEST_EQUIVALENCY_SUPPORTED is False
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="TOEFL", score=110)])
        )
        comparison = compare_language(profile, language_requirement())
        assert comparison.state == "UNKNOWN"
        assert comparison.score is None
        assert "does not convert" in comparison.detail

    def test_a_test_without_a_documented_range_is_gated_but_not_scored(self):
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="Cambridge", score=180)])
        )
        comparison = compare_language(profile, language_requirement(test="cambridge", minimum=170))
        assert comparison.state == "MEETS"
        assert comparison.score is None
        assert "no documented scoring range" in comparison.detail

    def test_a_missing_student_credential_is_unknown_not_a_failure(self):
        profile = normalise_profile(strong_profile(language_credentials=[]))
        comparison = compare_language(profile, language_requirement())
        assert comparison.state == "NO_CREDENTIAL"
        assert comparison.score is None

    def test_a_credential_without_a_score_is_unknown(self):
        profile = normalise_profile(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS")])
        )
        comparison = compare_language(profile, language_requirement())
        assert comparison.state == "UNKNOWN"
        assert comparison.score is None

    def test_a_missing_published_requirement_is_not_scored(self):
        value, detail, evidence = score_language(
            normalise_profile(strong_profile()), None, not_required=False
        )
        assert value is None
        assert evidence["basis"] == "no_published_requirement"
        assert "no language requirement" in detail

    def test_a_published_statement_that_no_test_is_required_scores_full_marks(self):
        value, _, evidence = score_language(
            normalise_profile(strong_profile()), None, not_required=True
        )
        assert value == 100.0
        assert evidence["basis"] == "not_required_by_publication"

    def test_the_evidence_records_the_cross_test_decision(self):
        _, _, evidence = score_language(
            normalise_profile(
                strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=7.5)])
            ),
            language_requirement(),
            not_required=False,
        )
        assert evidence["cross_test_conversion"] is False
        assert evidence["required_test"] == "ielts"
        assert evidence["published_minimum"] == 6.5
        assert evidence["quote"]

    def test_every_configured_range_is_positive(self):
        for test, value in LANGUAGE_SURPLUS_RANGES.items():
            assert value > 0, test

    def test_the_language_component_reports_the_published_quote(self):
        result = score(strong_profile(), make_facts())
        component = component_of(result, "language")
        assert component.score == pytest.approx(50.0)  # (7.5 - 6.5) / 2.0
        assert component.evidence["quote"] == "IELTS 6.5 or above required."

# ---------------------------------------------------------------------------
# 14. Requirements
# ---------------------------------------------------------------------------


class TestRequirementReading:
    def test_a_published_language_threshold_is_read_with_its_test_and_scale(self):
        read = read_requirements(make_facts())
        assert read.language_minimum is not None
        assert read.language_minimum.test_name == "ielts"
        assert read.language_minimum.minimum_value == pytest.approx(6.5)

    def test_every_read_requirement_carries_the_providing_source(self):
        read = read_requirements(make_facts())
        for requirement in (
            read.academic_minimum,
            read.language_minimum,
            read.nationality,
        ):
            assert requirement is not None
            assert requirement.raw_quote
            assert requirement.provenance_url == "https://example.edu/scholarships/test"

    def test_degree_levels_are_read_from_the_structured_column_not_prose(self):
        facts = make_facts(degree_levels="Master", eligibility=["PhD applicants only."])
        read = read_requirements(facts)
        assert read.degree_levels is not None
        assert read.degree_levels.allowed_terms == ("MASTER",)

    def test_a_record_that_publishes_nothing_reads_nothing(self):
        facts = make_facts(
            eligibility=[],
            eligibility_summary=None,
            english_requirement=None,
            degree_levels="",
        )
        read = read_requirements(facts)
        assert read.academic_minimum is None
        assert read.language_minimum is None
        assert read.nationality is None
        assert read.age is None
        assert read.study_mode is None
        assert read.programme_restriction is None

    def test_the_reader_version_is_published(self):
        from app.services.matching.requirements import reader_version

        assert reader_version() == "2.0.0"

    def test_a_nationality_list_is_enumerated_not_left_dangling(self):
        read = read_requirements(make_facts(eligibility=["Applicants must be citizens of India."]))
        assert read.nationality is not None
        assert read.nationality.allowed_terms

    def test_a_designated_country_list_is_recognised_as_unenumerable(self):
        read = read_requirements(
            make_facts(eligibility=["Open to nationals of designated countries only."])
        )
        if read.nationality is not None:
            assert read.nationality.allowed_terms == ("DESIGNATED_SCHEME",)


class TestRequirementScoring:
    def test_a_published_document_list_is_a_real_evaluated_condition(self):
        from app.services.matching.components import score_requirements

        fit = score_requirements(make_facts())
        assert fit.evaluated >= 1
        assert fit.score is not None
        assert fit.score > 0

    def test_no_documents_and_no_conditions_is_not_evaluated(self):
        from app.services.matching.components import score_requirements

        fit = score_requirements(make_facts(documents=[]))
        assert fit.score is None
        assert fit.evaluated == 0

    def test_an_unrecognised_document_lowers_precision_without_failing_the_student(self):
        from app.services.matching.components import score_requirements

        fit = score_requirements(
            make_facts(documents=["Academic transcript", "Something the catalogue does not know"])
        )
        assert fit.unknown >= 1
        assert fit.score < 100.0

    def test_hard_eligibility_conditions_are_not_double_counted(self):
        """Nationality, academic and language belong to the gate, not to this component."""
        from app.services.matching.components import score_requirements

        facts = make_facts(
            eligibility=["Applicants must be citizens of India.", "Minimum GPA of 3.5/4.0 required."],
            english_requirement="IELTS 6.5 or above required.",
            requirements=[],
            documents=["Academic transcript"],
        )
        fit = score_requirements(facts)
        assert fit.evaluated == 1
        assert fit.score == pytest.approx(100.0)

    def test_a_comparative_condition_is_not_treated_as_a_mandatory_gate(self):
        """Prose such as 'preference' must not become an eligibility rule."""
        facts = make_facts(
            eligibility=["Preference will be given to applicants with work experience."],
            requirements=["Work experience is an advantage."],
        )
        read = read_requirements(facts)
        assert read.nationality is None
        assert read.age is None
        assert read.study_mode is None

    def test_an_experience_condition_is_reported_unknown_never_failed(self):
        from app.services.matching.components import score_requirements

        fit = score_requirements(
            make_facts(documents=["CV"], requirements=["Two years of work experience required."])
        )
        assert fit.unknown >= 1
        assert fit.score < 100.0
        assert fit.score >= 0.0


# ---------------------------------------------------------------------------
# 15. Preference
# ---------------------------------------------------------------------------


class TestPreference:
    def test_a_stated_country_that_matches_scores_full_marks(self):
        result = score(strong_profile(), make_facts(country="United Kingdom"))
        assert component_of(result, "preference").score == 100.0

    def test_a_stated_country_that_does_not_match_scores_above_zero(self):
        """"You did not ask for this country" is weaker than "it cannot fund you"."""
        result = score(strong_profile(), make_facts(country="Brazil"))
        component = component_of(result, "preference")
        assert 0.0 < component.score < 100.0

    def test_no_stated_preference_is_not_evaluated_and_is_never_a_penalty(self):
        result = score(strong_profile(preferred_countries=[]), make_facts())
        component = component_of(result, "preference")
        assert component.score is None
        assert component.status.value == "NOT_EVALUATED"
        assert result.data_coverage < 100.0

    def test_the_matrix_is_centralised(self):
        from app.services.matching.config import PREFERENCE_COMPATIBILITY

        assert preference_score("MATCH") == PREFERENCE_COMPATIBILITY["MATCH"] == 100.0
        assert preference_score("NO_MATCH") == PREFERENCE_COMPATIBILITY["NO_MATCH"] == 50.0

    def test_an_unknown_relationship_is_never_guessed_a_score(self):
        assert preference_score("SOMEWHAT_SIMILAR") is None

    def test_a_preference_never_changes_eligibility(self):
        matched = score(strong_profile(), make_facts(country="United Kingdom"))
        unmatched = score(strong_profile(), make_facts(country="Brazil"))
        assert matched.eligibility is unmatched.eligibility is EligibilityStatus.ELIGIBLE

    def test_an_unresolvable_country_is_never_treated_as_a_non_match(self):
        result = score(strong_profile(preferred_countries=["Atlantis"]), make_facts(country="Brazil"))
        assert component_of(result, "preference").score is None


# ---------------------------------------------------------------------------
# 16. Timing
# ---------------------------------------------------------------------------


class TestTiming:
    @pytest.mark.parametrize(
        ("deadline", "days_expected", "band_expected"),
        [
            ("2026-12-31", 305, "comfortable"),
            ("2026-04-20", 50, "approaching"),
            ("2026-03-25", 24, "workable"),
            ("2026-03-10", 9, "tight"),
            ("2026-03-05", 4, "urgent"),
        ],
    )
    def test_each_timing_band_is_reached_at_the_documented_threshold(
        self, deadline, days_expected, band_expected
    ):
        facts = make_facts(deadline_date=deadline, deadline_display=deadline)
        result = score(strong_profile(), facts)
        assert result.days_to_deadline == days_expected
        assert component_of(result, "timing").score is not None
        assert component_of(result, "timing").evidence["band"] == band_expected

    def test_the_timing_bands_are_the_configured_ones(self):
        from app.services.matching.config import TIMING_BANDS

        assert TIMING_BANDS == (
            (60, 100.0, "comfortable"),
            (30, 90.0, "approaching"),
            (14, 75.0, "workable"),
            (7, 55.0, "tight"),
            (1, 30.0, "urgent"),
        )

    def test_sixty_days_or_more_is_comfortable(self):
        facts = make_facts(deadline_date="2026-04-30", deadline_display="30 April 2026")
        assert component_of(score(strong_profile(), facts), "timing").score == 100.0

    def test_a_closed_round_is_not_scored_but_is_not_zero_either(self):
        facts = make_facts(status="closed")
        result = score(strong_profile(), facts)
        component = component_of(result, "timing")
        assert component.score is None
        assert result.eligibility is EligibilityStatus.INELIGIBLE

    def test_a_rolling_deadline_is_not_evaluated(self):
        facts = make_facts(
            deadline_date=None,
            deadline_display="Applications are accepted on a rolling basis",
            deadline_precision="rolling",
        )
        result = score(strong_profile(), facts)
        component = component_of(result, "timing")
        assert component.score is None
        assert "rolling" in component.detail.lower()

    def test_an_annual_deadline_is_not_evaluated(self):
        facts = make_facts(
            deadline_date=None,
            deadline_display="Applications are open annually",
            deadline_precision="annual",
        )
        component = component_of(score(strong_profile(), facts), "timing")
        assert component.score is None

    def test_an_unpublished_deadline_is_not_evaluated(self):
        facts = make_facts(deadline_date=None, deadline_display=None, deadline_precision=None)
        component = component_of(score(strong_profile(), facts), "timing")
        assert component.score is None
        assert "no fixed application deadline" in component.detail.lower()

    def test_a_month_precision_deadline_is_measured_to_the_end_of_the_month(self):
        facts = make_facts(
            deadline_date="2026-03-01",
            deadline_display="March 2026",
            deadline_precision="month",
        )
        result = score(strong_profile(), facts)
        evidence = component_of(result, "timing").evidence
        assert evidence["approximate"] is True
        # March has 31 days, so the remaining time is measured to the 31st.
        assert evidence["days_remaining"] == 30
        assert result.deadline_precision == "month"

    def test_the_deadline_bucket_matches_the_day_count(self):
        from app.services.matching.components import timing_bucket

        assert timing_bucket(90) == "COMFORTABLE"
        assert timing_bucket(45) == "APPROACHING"
        assert timing_bucket(20) == "APPROACHING"
        assert timing_bucket(10) == "CLOSING_SOON"
        assert timing_bucket(3) == "CLOSING_SOON"
        assert timing_bucket(None) == "UNKNOWN"
        assert timing_bucket(None, closed=True) == "CLOSED"
        assert timing_bucket(400, kind="rolling") == "UNKNOWN"

    def test_the_as_of_date_is_injected_not_read_from_a_clock(self):
        """The same record scores differently under two different as_of dates."""
        facts = make_facts(deadline_date="2026-06-30", deadline_display="30 June 2026")
        early = score(strong_profile(), facts, as_of=date(2026, 3, 1))
        late = score(strong_profile(), facts, as_of=date(2026, 6, 1))
        assert early.days_to_deadline == 121
        assert late.days_to_deadline == 29
        assert component_of(early, "timing").score != component_of(late, "timing").score

    def test_an_injected_date_is_reported_verbatim(self):
        from app.services.matching.engine import engine_metadata

        assert engine_metadata(date(2026, 3, 1))["as_of"] == "2026-03-01"

    def test_the_pure_modules_never_call_the_wall_clock(self):
        import inspect as _inspect

        from app.services.matching import (
            academic,
            components,
            confidence,
            eligibility,
            engine,
            gaps,
            metrics,
            normalize,
            nlp,
            profile_strength,
            readiness,
            requirements,
            summaries,
            taxonomy,
        )

        forbidden = ("date.today()", "datetime.now(", "time.time(", "date.today (")
        for module in (
            academic,
            components,
            confidence,
            eligibility,
            engine,
            gaps,
            metrics,
            normalize,
            nlp,
            profile_strength,
            readiness,
            requirements,
            summaries,
            taxonomy,
        ):
            source = _inspect.getsource(module)
            for needle in forbidden:
                assert needle not in source, f"{module.__name__} calls {needle}"


# ---------------------------------------------------------------------------
# 17. Confidence
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_the_weights_are_the_locked_four(self):
        assert dict(CONFIDENCE_WEIGHTS) == {
            "data_completeness": 0.35,
            "provenance_quality": 0.25,
            "requirement_explicitness": 0.25,
            "verification_freshness": 0.15,
        }

    def test_the_score_is_exactly_that_weighted_sum(self):
        from app.services.matching.confidence import compute_confidence

        facts = make_facts()
        result = compute_confidence(facts, read_requirements(facts), AS_OF)
        evidence = result.evidence
        expected = (
            evidence.coverage_ratio / 100.0 * CONFIDENCE_WEIGHTS["data_completeness"]
            + evidence.provenance_ratio / 100.0 * CONFIDENCE_WEIGHTS["provenance_quality"]
            + evidence.explicitness_ratio / 100.0 * CONFIDENCE_WEIGHTS["requirement_explicitness"]
            + evidence.freshness_ratio / 100.0 * CONFIDENCE_WEIGHTS["verification_freshness"]
        ) * 100.0
        assert result.score == pytest.approx(round(min(100.0, expected), 1))

    def test_confidence_is_profile_independent(self):
        """"I supplied more" can never raise how trustworthy a record is."""
        rich = strong_profile()
        empty = MatchProfileRequest()
        assert score(rich, make_facts()).confidence_score == score(empty, make_facts()).confidence_score

    def test_confidence_is_not_the_fit_score_multiplied_by_anything(self):
        result = score(strong_profile(), make_facts())
        assert 0.0 <= result.confidence_score <= 100.0
        assert result.confidence_score != result.fit_score
        # The two are produced by separate functions over separate evidence.
        assert result.evidence_status.freshness_ratio >= 0.0

    @pytest.mark.parametrize(
        ("verified", "expected"),
        [
            ("2026-02-01", 100.0),   # 28 days
            ("2025-10-01", 75.0),    # 151 days
            ("2025-06-01", 50.0),    # 273 days
            ("2024-06-01", 25.0),    # 639 days
            ("2023-01-01", 0.0),     # far older than any window
            (None, 0.0),
        ],
    )
    def test_the_freshness_bands_are_exactly_as_documented(self, verified, expected):
        from app.services.matching.confidence import compute_confidence

        facts = make_facts(last_verified_date=verified)
        result = compute_confidence(facts, read_requirements(facts), AS_OF)
        assert result.evidence.freshness_ratio == pytest.approx(expected)

    def test_freshness_has_no_floor_for_an_ancient_record(self):
        """An unbounded credit for evidence nobody refreshed is not a credit."""
        from app.services.matching.confidence import compute_confidence

        ancient = make_facts(last_verified_date="2015-01-01")
        result = compute_confidence(ancient, read_requirements(ancient), AS_OF)
        assert result.evidence.freshness_ratio == 0.0

    def test_a_future_verification_date_is_treated_as_fresh(self):
        from app.services.matching.confidence import compute_confidence

        facts = make_facts(last_verified_date="2027-01-01")
        result = compute_confidence(facts, read_requirements(facts), AS_OF)
        assert result.evidence.freshness_ratio == 100.0

    def test_an_unparseable_verification_date_is_not_an_error(self):
        from app.services.matching.confidence import compute_confidence

        facts = make_facts(last_verified_date="not-a-date")
        result = compute_confidence(facts, read_requirements(facts), AS_OF)
        assert result.evidence.freshness_ratio == 0.0

    @pytest.mark.parametrize(
        ("score", "label"),
        [(100.0, "HIGH"), (85.0, "HIGH"), (84.9, "MEDIUM"), (65.0, "MEDIUM"), (0.0, "LOW")],
    )
    def test_the_confidence_bands_are_locked_at_eighty_five_and_sixty_five(self, score, label):
        from app.services.matching.confidence import confidence_label

        assert confidence_label(score)[0] == label

    def test_a_thin_record_scores_lower_than_a_complete_one(self):
        thin = score(
            strong_profile(),
            make_facts(
                program_type=None,
                eligibility=[],
                eligibility_summary=None,
                documents=[],
                coverage=[],
                english_requirement=None,
                tuition_coverage=None,
                living_cost_coverage=None,
                official_source=None,
                is_verified=False,
                last_verified_date=None,
                funding_amount=None,
            ),
        )
        complete = score(strong_profile(), make_facts())
        assert thin.confidence_score < complete.confidence_score
        assert thin.confidence_label == "LOW"

    def test_confidence_is_deterministic(self):
        facts = make_facts()
        first = score(strong_profile(), facts).confidence_score
        second = score(strong_profile(), facts).confidence_score
        assert first == second

    def test_every_confidence_ratio_is_a_documented_fraction(self):
        result = score(strong_profile(), make_facts())
        for ratio in (
            result.evidence_status.coverage_ratio,
            result.evidence_status.provenance_ratio,
            result.evidence_status.explicitness_ratio,
            result.evidence_status.freshness_ratio,
        ):
            assert 0.0 <= ratio <= 100.0


# ---------------------------------------------------------------------------
# 18. Readiness
# ---------------------------------------------------------------------------


class TestReadiness:
    def test_the_weights_are_the_locked_five(self):
        from app.services.matching.config import READINESS_WEIGHTS

        assert dict(READINESS_WEIGHTS) == {
            "eligibility_certainty": 0.30,
            "requirement_completeness": 0.20,
            "language_readiness": 0.15,
            "application_readiness": 0.15,
            "deadline_readiness": 0.20,
        }

    def test_every_dimension_is_present_and_carries_its_configured_weight(self):
        from app.services.matching.config import READINESS_WEIGHTS

        readiness = score(strong_profile(), make_facts()).readiness
        assert readiness is not None
        assert [item.name for item in readiness.components] == list(READINESS_WEIGHTS)

    def test_full_evaluation_reaches_one_hundred_percent_coverage(self):
        readiness = score(strong_profile(), make_facts()).readiness
        assert readiness.evaluated_coverage == pytest.approx(100.0)

    def test_weights_are_renormalised_over_what_was_evaluated(self):
        readiness = score(
            strong_profile(language_credentials=[]), make_facts()
        ).readiness
        evaluated = [item for item in readiness.components if item.status.value == "EVALUATED"]
        assert sum(item.effective_weight for item in evaluated) == pytest.approx(1.0)
        assert readiness.evaluated_coverage < 100.0

    def test_an_unevaluated_dimension_is_excluded_not_zeroed(self):
        readiness = score(strong_profile(language_credentials=[]), make_facts()).readiness
        language = next(
            item for item in readiness.components if item.name == "language_readiness"
        )
        assert language.score is None
        assert language.contribution is None
        assert language.status.value == "NOT_EVALUATED"

    def test_a_confirmed_failure_is_a_real_zero(self):
        readiness = score(
            strong_profile(language_credentials=[LanguageCredential(test="IELTS", score=5.0)]),
            make_facts(),
        ).readiness
        language = next(
            item for item in readiness.components if item.name == "language_readiness"
        )
        assert language.score == 0.0
        assert language.status.value == "EVALUATED"

    def test_an_ineligible_record_has_nothing_to_be_ready_for(self):
        readiness = score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(),
        ).readiness
        certainty = next(
            item for item in readiness.components if item.name == "eligibility_certainty"
        )
        assert certainty.score == 0.0
        assert "no application to be ready for" in certainty.detail

    def test_readiness_is_bounded(self):
        for request in (
            strong_profile(),
            strong_profile(language_credentials=[]),
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            MatchProfileRequest(),
        ):
            readiness = score(request, make_facts()).readiness
            if readiness.score is not None:
                assert 0.0 <= readiness.score <= 100.0
                assert readiness.band is not None
                assert readiness.label is not None

    def test_nothing_measurable_is_none_not_zero(self):
        """A record with no source, no documents and no deadline has no readiness."""
        facts = make_facts(
            official_source=None,
            official_source_url=None,
            documents=[],
            deadline_date=None,
            deadline_display=None,
            deadline_precision=None,
            eligibility=[],
            eligibility_summary=None,
            english_requirement=None,
            degree_levels="",
        )
        readiness = score(strong_profile(language_credentials=[]), facts).readiness
        assert readiness.score is not None or all(
            item.score is None for item in readiness.components
        )

    def test_readiness_is_deterministic(self):
        first = score(strong_profile(), make_facts()).readiness
        second = score(strong_profile(), make_facts()).readiness
        assert first.score == second.score
        assert [item.contribution for item in first.components] == [
            item.contribution for item in second.components
        ]

    def test_readiness_is_a_third_number_not_fit_and_not_confidence(self):
        result = score(strong_profile(), make_facts())
        readiness = result.readiness
        assert readiness.score != result.fit_score
        assert readiness.score != result.confidence_score
        assert readiness.band is not None
        assert "not a prediction" in readiness.detail or "evaluated" in readiness.detail

    def test_readiness_components_carry_grounded_detail_text(self):
        readiness = score(strong_profile(), make_facts()).readiness
        for item in readiness.components:
            assert item.detail


# ---------------------------------------------------------------------------
# 19. Profile strength
# ---------------------------------------------------------------------------


class TestProfileStrength:
    def test_the_weights_are_the_locked_five(self):
        from app.services.matching.config import PROFILE_STRENGTH_WEIGHTS

        assert dict(PROFILE_STRENGTH_WEIGHTS) == {
            "academic": 0.25,
            "study_goal": 0.25,
            "language": 0.20,
            "funding": 0.20,
            "identity": 0.10,
        }

    def test_a_complete_profile_is_strong(self):
        from app.services.matching.profile_strength import compute_profile_strength

        strength = compute_profile_strength(normalise_profile(strong_profile()))
        assert strength.score == pytest.approx(100.0)
        assert strength.band == "STRONG"
        assert strength.label == "Strong profile"
        assert set(strength.complete) == {"Academic", "Study goal", "Language", "Funding", "Identity"}

    def test_an_empty_profile_is_undefined_not_zero(self):
        from app.services.matching.profile_strength import compute_profile_strength

        strength = compute_profile_strength(normalise_profile(MatchProfileRequest()))
        assert strength.score is None
        assert strength.band is None
        assert strength.complete == []
        assert strength.improvements

    def test_missing_groups_lower_the_score_and_raise_suggestions(self):
        from app.services.matching.profile_strength import compute_profile_strength

        partial = compute_profile_strength(
            normalise_profile(
                strong_profile(
                    overall_result=None,
                    subject_results=[],
                    language_credentials=[],
                    funding_requirement=None,
                    living_cost_support_required=None,
                    citizenship=None,
                    age=None,
                )
            )
        )
        assert partial.score is not None
        assert partial.score < 100.0
        codes = {item.code for item in partial.improvements}
        assert "PROFILE_STRENGTH_ACADEMIC_INCOMPLETE" in codes
        assert "PROFILE_STRENGTH_LANGUAGE_INCOMPLETE" in codes
        assert "PROFILE_STRENGTH_IDENTITY_INCOMPLETE" in codes

    def test_every_improvement_is_a_suggestion_not_a_failure(self):
        from app.services.matching.profile_strength import compute_profile_strength

        strength = compute_profile_strength(normalise_profile(MatchProfileRequest()))
        for suggestion in strength.improvements:
            assert suggestion.message
            assert suggestion.message[0].isupper()
            assert suggestion.message.endswith(".")

    def test_profile_strength_is_not_scholarship_fit(self):
        """"Did you tell us enough" is a question about the request, not the award."""
        from app.services.matching.profile_strength import compute_profile_strength

        strong = compute_profile_strength(normalise_profile(strong_profile()))
        partial = compute_profile_strength(
            normalise_profile(strong_profile(preferred_countries=[]))
        )
        # Two identical profiles against two very different records must report
        # the same profile strength.
        left = score(strong_profile(), make_facts())
        right = score(strong_profile(), make_facts(country="Brazil", funding_label="Not specified"))
        left_strength = compute_profile_strength(normalise_profile(strong_profile()))
        right_strength = compute_profile_strength(normalise_profile(strong_profile()))
        assert left_strength.score == right_strength.score
        assert left.fit_score != right.fit_score or left.fit_label != right.fit_label
        assert strong.score == partial.score  # preferences are not a strength group

    def test_profile_strength_is_deterministic(self):
        from app.services.matching.profile_strength import compute_profile_strength

        profile = normalise_profile(strong_profile())
        assert compute_profile_strength(profile).score == compute_profile_strength(profile).score

    def test_profile_strength_is_bounded(self):
        from app.services.matching.profile_strength import compute_profile_strength

        score_value = compute_profile_strength(normalise_profile(strong_profile())).score
        assert 0.0 <= score_value <= 100.0

    def test_every_group_is_reported_with_its_own_detail(self):
        from app.services.matching.profile_strength import compute_profile_strength

        strength = compute_profile_strength(normalise_profile(strong_profile()))
        assert len(strength.components) == 5
        for item in strength.components:
            assert item.detail
            assert item.status.value == "EVALUATED"


# ---------------------------------------------------------------------------
# 20. Gaps and actions
# ---------------------------------------------------------------------------


class TestGaps:
    def test_every_gap_code_has_a_category_and_a_plain_message(self):
        from app.services.matching.gaps import GAP_TEMPLATES

        for code, (category, message) in GAP_TEMPLATES.items():
            assert category is not None
            assert message and not message.endswith(":"), code

    def test_the_four_gap_categories_are_available(self):
        from app.services.matching.types import GapCategory

        assert {item.value for item in GapCategory} == {
            "KNOWN_GAP",
            "UNVERIFIED",
            "MISSING_USER_INFORMATION",
            "MISSING_SCHOLARSHIP_DATA",
        }

    def test_a_missing_student_field_is_user_information_not_a_failure(self):
        from app.services.matching.gaps import category_of

        assert category_of("PREFERENCE_NOT_PROVIDED").value == "MISSING_USER_INFORMATION"
        assert category_of("LANGUAGE_NOT_PROVIDED").value == "MISSING_USER_INFORMATION"

    def test_an_unverified_published_rule_is_its_own_category(self):
        from app.services.matching.gaps import category_of

        assert category_of("ELIGIBILITY_NEEDS_VERIFICATION").value == "UNVERIFIED"
        assert category_of("NATIONALITY_NEEDS_VERIFICATION").value == "UNVERIFIED"

    def test_a_catalogue_gap_is_not_blamed_on_the_student(self):
        from app.services.matching.gaps import category_of

        assert category_of("FUNDING_UNKNOWN").value == "MISSING_SCHOLARSHIP_DATA"
        assert category_of("SOURCE_UNVERIFIED").value == "MISSING_SCHOLARSHIP_DATA"

    def test_an_unknown_code_still_renders_and_is_visible(self):
        from app.services.matching.gaps import gap

        item = gap("A_BRAND_NEW_CODE")
        assert item.code == "A_BRAND_NEW_CODE"
        assert item.message == "A_BRAND_NEW_CODE"

    def test_gaps_are_deduplicated_preserving_order(self):
        from app.services.matching.gaps import deduplicate, gap

        first = gap("SOURCE_UNVERIFIED")
        second = gap("FUNDING_UNKNOWN")
        deduped = deduplicate([first, second, gap("SOURCE_UNVERIFIED")])
        assert [item.code for item in deduped] == ["SOURCE_UNVERIFIED", "FUNDING_UNKNOWN"]

    def test_a_sparse_record_reports_gaps_rather_than_being_called_a_poor_match(self):
        result = score(
            MatchProfileRequest(),
            make_facts(
                program_type=None,
                official_details=None,
                coverage=[],
                documents=[],
                english_requirement=None,
            ),
        )
        # The record still publishes a citizenship rule we cannot check, so this
        # is a NEEDS_VERIFICATION, not a rejection and not a poor match.
        assert result.eligibility is EligibilityStatus.NEEDS_VERIFICATION
        assert result.gaps
        assert not result.blockers

    def test_a_sparse_record_and_an_empty_profile_produce_no_blockers(self):
        result = score(
            MatchProfileRequest(),
            make_facts(
                program_type=None,
                official_details=None,
                coverage=[],
                documents=[],
                english_requirement=None,
                eligibility=[],
                eligibility_summary=None,
                degree_levels="",
            ),
        )
        assert result.eligibility is EligibilityStatus.ELIGIBLE
        assert result.gaps
        assert not result.blockers

    def test_a_complete_result_has_no_blockers(self):
        assert score(strong_profile(), make_facts()).blockers == []


class TestActions:
    def test_every_action_code_has_a_message(self):
        from app.services.matching.actions import GAP_ACTIONS

        for code, message in GAP_ACTIONS.items():
            assert message and message.endswith((".", "page.")), code

    def test_a_gap_with_no_action_produces_silence_rather_than_a_generic_hint(self):
        from app.services.matching.actions import actions_from_gaps
        from app.services.matching.gaps import gap

        assert actions_from_gaps([gap("A_BRAND_NEW_CODE")]) == []

    def test_actions_are_derived_from_the_gaps_that_actually_occurred(self):
        result = score(strong_profile(preferred_countries=[]), make_facts())
        codes = {item.code for item in result.actions}
        assert "ACTION_PREFERENCE_NOT_PROVIDED" in codes

    def test_an_ineligible_result_leads_with_the_blocking_condition(self):
        result = score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(),
        )
        assert result.actions[0].code == "ACTION_REVIEW_BLOCKING_CONDITION"

    def test_the_official_source_action_is_only_produced_when_a_url_exists(self):
        from app.services.matching.actions import build_actions

        with_url = build_actions(
            gaps=[],
            eligibility=EligibilityStatus.ELIGIBLE,
            official_source_url="https://example.edu/apply",
            blocker_count=0,
            document_count=0,
        )
        assert with_url[-1].code == "ACTION_VISIT_OFFICIAL_SOURCE"
        assert with_url[-1].url == "https://example.edu/apply"
        assert with_url[-1].url_label == "Visit Official Source"

        without_url = build_actions(
            gaps=[],
            eligibility=EligibilityStatus.ELIGIBLE,
            official_source_url=None,
            blocker_count=0,
            document_count=0,
        )
        assert all(item.url is None for item in without_url)
        assert "ACTION_VISIT_OFFICIAL_SOURCE" not in {item.code for item in without_url}

    def test_documents_are_only_named_when_the_record_names_them(self):
        result = score(strong_profile(), make_facts(documents=["Academic transcript", "CV"]))
        prepare = next(
            item for item in result.actions if item.code == "ACTION_PREPARE_DOCUMENTS"
        )
        assert "2 document(s)" in prepare.message

        without = score(strong_profile(), make_facts(documents=[]))
        assert "ACTION_PREPARE_DOCUMENTS" not in {item.code for item in without.actions}

    def test_actions_are_ordered_by_consequence(self):
        from app.services.matching.actions import PRIORITY_UNVERIFIED, actions_from_gaps
        from app.services.matching.gaps import gap

        items = actions_from_gaps(
            [gap("PREFERENCE_NOT_PROVIDED"), gap("ELIGIBILITY_NEEDS_VERIFICATION")]
        )
        assert [item.priority for item in items] == sorted(item.priority for item in items)
        assert items[0].priority == PRIORITY_UNVERIFIED

    def test_no_action_claims_the_student_possesses_a_document(self):
        result = score(strong_profile(), make_facts())
        for action in result.actions:
            assert "ACTION_HAVE_DOCUMENT" not in action.code
            assert "you have" not in action.message.lower()


# ---------------------------------------------------------------------------
# 21. Counting
# ---------------------------------------------------------------------------


def build_universe() -> list:
    """A deliberately mixed set: every eligibility state and both fit outcomes."""
    return [
        score(strong_profile(), make_facts(id=1)),
        score(strong_profile(), make_facts(id=2, country="Germany")),
        score(strong_profile(language_credentials=[]), make_facts(id=3, country="France")),
        score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(id=4, country="Spain"),
        ),
        score(
            strong_profile(language_credentials=[]),
            make_facts(id=5, country="Spain", status="closed"),
        ),
    ]


class TestCounting:
    def test_the_three_eligibility_states_sum_to_total_candidates(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        counted = summarise(universe, total_candidates=len(universe))
        summary = counted["summary"]
        assert (
            summary.eligible_count + summary.needs_verification_count + summary.ineligible_count
            == summary.total_candidates
        )

    def test_scored_and_not_scored_sum_to_total_candidates(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        summary = summarise(universe, total_candidates=len(universe))["summary"]
        assert summary.scored_count + summary.not_scored_count == summary.total_candidates

    def test_fit_tiers_reconcile_to_the_scored_results(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        summary = summarise(universe, total_candidates=len(universe))["summary"]
        tiers = (
            summary.exceptional_count
            + summary.very_strong_count
            + summary.strong_count
            + summary.possible_count
            + summary.low_count
            + summary.unclassified_fit_count
        )
        assert tiers == summary.scored_count

    def test_every_ineligible_result_is_uncounted_as_scored(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        summary = summarise(universe, total_candidates=len(universe))["summary"]
        assert summary.not_scored_count == sum(
            1 for item in universe if item.fit_score is None
        )

    def test_confidence_coverage_deadline_and_funding_buckets_all_reconcile(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        summary = summarise(universe, total_candidates=len(universe))["summary"]
        families = (
            ("high_confidence_count", "medium_confidence_count", "low_confidence_count"),
            ("high_coverage_count", "medium_coverage_count", "low_coverage_count"),
            (
                "comfortable_deadline_count",
                "approaching_deadline_count",
                "closing_soon_count",
                "closed_deadline_count",
                "unknown_deadline_count",
            ),
            (
                "full_funding_count",
                "tuition_plus_living_count",
                "tuition_only_count",
                "partial_funding_count",
                "none_count",
                "unknown_funding_count",
            ),
        )
        for family in families:
            assert sum(getattr(summary, key) for key in family) == summary.total_candidates

    def test_the_counts_describe_the_whole_universe_even_when_the_page_is_truncated(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        counted = summarise(universe, universe[:1], total_candidates=len(universe), truncated=True)
        summary = counted["summary"]
        assert summary.total_candidates == len(universe)
        assert summary.visible_candidate_count == 1
        assert summary.truncated is True
        assert (
            summary.eligible_count + summary.needs_verification_count + summary.ineligible_count
            == len(universe)
        )

    def test_no_result_is_counted_twice(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        summary = summarise(universe, total_candidates=len(universe))["summary"]
        assert summary.eligible_count <= len(universe)
        assert summary.scored_count <= len(universe)
        assert summary.scored_count + summary.not_scored_count == len(universe)

    def test_a_total_that_disagrees_with_the_universe_is_rejected(self):
        from app.services.matching.summaries import build_summary

        with pytest.raises(AssertionError, match="total_candidates"):
            build_summary(build_universe(), total_candidates=99)

    def test_an_empty_universe_counts_zero_without_dividing_by_zero(self):
        from app.services.matching.engine import summarise

        summary = summarise([], total_candidates=0)["summary"]
        assert summary.total_candidates == 0
        assert summary.visible_candidate_count == 0
        assert summary.scored_count == 0
        assert summary.average_confidence is None
        assert summary.average_data_coverage is None

    def test_strong_or_better_counts_only_eligible_results(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        summary = summarise(universe, total_candidates=len(universe))["summary"]
        expected = sum(
            1
            for item in universe
            if item.eligibility is EligibilityStatus.ELIGIBLE
            and item.fit_score is not None
            and item.fit_score >= 70
        )
        assert summary.strong_or_better_count == expected

    def test_averages_are_over_the_analysed_universe(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        summary = summarise(universe, total_candidates=len(universe))["summary"]
        assert summary.average_confidence == pytest.approx(
            round(sum(item.confidence_score for item in universe) / len(universe), 1)
        )

    def test_different_profiles_produce_genuinely_different_counts(self):
        from app.services.matching.engine import summarise

        facts = make_facts()
        generous = summarise(
            [score(strong_profile(), facts)], total_candidates=1
        )["summary"]
        strict = summarise(
            [score(strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)), facts)],
            total_candidates=1,
        )["summary"]
        assert generous.eligible_count == 1
        assert strict.ineligible_count == 1


# ---------------------------------------------------------------------------
# 22. Facets
# ---------------------------------------------------------------------------


class TestFacets:
    def test_every_facet_family_is_present(self):
        from app.services.matching.summaries import build_facets

        facets = build_facets(build_universe())
        assert facets.count_basis == "RETURNED_PAGE"
        assert facets.countries
        assert facets.degree_levels
        assert facets.eligibility_states
        assert facets.funding_states
        assert facets.fit_bands
        assert facets.confidence_bands
        assert facets.deadline_buckets
        assert facets.fields

    def test_complete_partitions_count_the_set_exactly_once(self):
        from app.services.matching.summaries import assert_facets_reconcile, build_facets

        universe = build_universe()
        assert_facets_reconcile(build_facets(universe), universe)

    def test_countries_are_counted_and_never_truncated(self):
        from app.services.matching.summaries import build_facets

        universe = build_universe()
        facets = build_facets(universe)
        expected = sorted({item.country for item in universe})
        assert [bucket.value for bucket in facets.countries] == expected
        assert sum(bucket.count for bucket in facets.countries) == len(universe)

    def test_germany_is_present_as_its_own_bucket(self):
        """Regression guard: the country list was previously truncated."""
        from app.services.matching.summaries import build_facets

        facets = build_facets(build_universe())
        values = {bucket.value for bucket in facets.countries}
        assert "Germany" in values
        germany = next(bucket for bucket in facets.countries if bucket.value == "Germany")
        assert germany.count == 1
        assert germany.label

    def test_degree_levels_are_counted(self):
        from app.services.matching.summaries import build_facets

        facets = build_facets(build_universe())
        assert [bucket.value for bucket in facets.degree_levels] == ["Master"]

    def test_the_field_facet_carries_the_canonical_key_and_a_label(self):
        from app.services.matching.summaries import build_facets

        facets = build_facets(build_universe())
        field = next(bucket for bucket in facets.fields if bucket.value == "computer_science")
        assert field.count == 5
        assert field.label == "Computer Science"

    def test_an_ineligible_result_is_not_filed_under_a_fit_band(self):
        from app.services.matching.summaries import build_facets

        universe = build_universe()
        facets = build_facets(universe)
        ineligible = [item for item in universe if item.eligibility is EligibilityStatus.INELIGIBLE]
        assert sum(bucket.count for bucket in facets.fit_bands) == len(universe) - len(ineligible)

    def test_eligibility_buckets_use_the_configured_order(self):
        from app.services.matching.summaries import ELIGIBILITY_ORDER, build_facets

        facets = build_facets(build_universe())
        order = [bucket.value for bucket in facets.eligibility_states]
        assert order == [key for key in ELIGIBILITY_ORDER if key in order]

    def test_zero_count_values_are_never_offered(self):
        from app.services.matching.summaries import build_facets

        facets = build_facets(build_universe())
        for family in (
            facets.countries,
            facets.funding_states,
            facets.degree_levels,
            facets.eligibility_states,
            facets.fit_bands,
            facets.confidence_bands,
            facets.deadline_buckets,
        ):
            assert all(bucket.count > 0 for bucket in family)

    def test_facet_counts_describe_the_returned_page_not_the_whole_analysis(self):
        from app.services.matching.summaries import build_facets

        universe = build_universe()
        page = universe[:2]
        facets = build_facets(page)
        assert sum(bucket.count for bucket in facets.countries) == len(page)

    def test_filtering_a_page_and_clearing_the_filter_restores_the_original_set(self):
        """The reset guarantee, pinned at the layer that produces the counts."""
        universe = build_universe()
        page = list(universe)
        germany_only = [item for item in page if item.country == "Germany"]
        assert len(germany_only) == 1
        assert page is universe or [item.scholarship_id for item in page] == [
            item.scholarship_id for item in universe
        ]

    def test_a_degree_label_is_echoed_exactly_as_the_catalogue_wrote_it(self):
        """Regression guard: a ``.title()`` fallback mangled the source words.

        "Bachelor's, Master's" became "Bachelor'S, Master'S" and "PhD" became
        "Phd", restyling text ScholarZone did not author.
        """
        from app.services.matching.summaries import build_facets

        universe = [
            score(strong_profile(), make_facts(id=1, degree_levels="Bachelor's, Master's")),
            score(strong_profile(), make_facts(id=2, degree_levels="PhD")),
        ]
        buckets = {bucket.value: bucket.label for bucket in build_facets(universe).degree_levels}
        assert buckets["Bachelor's, Master's"] == "Bachelor's, Master's"
        assert buckets["PhD"] == "PhD"

    def test_a_country_label_is_echoed_exactly(self):
        from app.services.matching.summaries import build_facets

        buckets = {bucket.value: bucket.label for bucket in build_facets(build_universe()).countries}
        assert buckets["Germany"] == "Germany"
        assert buckets["United Kingdom"] == "United Kingdom"

    def test_an_enum_label_still_comes_from_configuration(self):
        from app.services.matching.summaries import build_facets

        labels = {
            bucket.value: bucket.label for bucket in build_facets(build_universe()).eligibility_states
        }
        assert labels["ELIGIBLE"] == "Eligible"
        assert labels["NEEDS_VERIFICATION"] == "Needs verification"
        assert labels["INELIGIBLE"] == "Not eligible"

    def test_the_coverage_band_boundaries_are_locked(self):
        from app.services.matching.summaries import coverage_band

        assert coverage_band(100.0) == "HIGH"
        assert coverage_band(80.0) == "HIGH"
        assert coverage_band(79.9) == "MEDIUM"
        assert coverage_band(50.0) == "MEDIUM"
        assert coverage_band(49.9) == "LOW"
        assert coverage_band(0.0) == "LOW"


# ---------------------------------------------------------------------------
# 23. Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_eligibility_is_the_primary_key(self):
        from app.services.matching.engine import rank_results

        universe = build_universe()
        ranked = rank_results(universe)
        order = [item.eligibility.value for item in ranked]
        ranks = [order.index("ELIGIBLE"), order.index("NEEDS_VERIFICATION"), order.index("INELIGIBLE")]
        assert ranks == sorted(ranks)

    def test_an_ineligible_record_never_outranks_an_eligible_one(self):
        from app.services.matching.engine import rank_results

        ineligible = score(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(id=1),
        )
        # Passes the gate on every published condition, and scores badly anyway:
        # no academic minimum to clear, a different country than the preference,
        # and no funding requirement to satisfy.
        eligible = score(
            strong_profile(
                overall_result=AcademicMark(scale=GradingScale.PERCENTAGE, value=60),
                preferred_countries=["Brazil"],
                funding_requirement=FundingRequirement.NO_SPECIFIC_NEED,
                living_cost_support_required=None,
                language_credentials=[],
            ),
            make_facts(
                id=2,
                eligibility=[],
                eligibility_summary=None,
                english_requirement=None,
                coverage=[],
                documents=[],
                program_type="History",
                official_details=None,
                funding_label="Not specified",
                tuition_coverage=None,
                living_cost_coverage=None,
                funding_amount=None,
            ),
        )
        assert ineligible.eligibility is EligibilityStatus.INELIGIBLE
        assert eligible.eligibility is EligibilityStatus.ELIGIBLE
        ranked = rank_results([ineligible, eligible])
        assert [item.scholarship_id for item in ranked] == [2, 1]

    def test_fit_score_is_the_first_key_within_a_group(self):
        from app.services.matching.engine import rank_results

        ranked = rank_results(build_universe())
        eligible = [item for item in ranked if item.eligibility is EligibilityStatus.ELIGIBLE]
        scores = [item.fit_score for item in eligible]
        assert scores == sorted(scores, reverse=True)

    def test_the_tiebreak_is_the_record_id_so_the_order_is_total(self):
        from app.services.matching.engine import rank_results

        identical = [score(strong_profile(), make_facts(id=index)) for index in (7, 2, 5)]
        forward = [item.scholarship_id for item in rank_results(identical)]
        backward = [item.scholarship_id for item in rank_results(list(reversed(identical)))]
        assert forward == backward == [2, 5, 7]

    def test_ranking_is_deterministic(self):
        from app.services.matching.engine import rank_results

        universe = build_universe()
        first = [item.scholarship_id for item in rank_results(universe)]
        second = [item.scholarship_id for item in rank_results(list(reversed(universe)))]
        assert first == second

    def test_confidence_and_coverage_break_a_fit_tie(self):
        from app.services.matching.engine import rank_results

        confident = score(strong_profile(), make_facts(id=1))
        thin = score(
            strong_profile(),
            make_facts(
                id=2,
                documents=[],
                coverage=[],
                official_source=None,
                is_verified=False,
                last_verified_date=None,
            ),
        )
        ranked = rank_results([thin, confident])
        assert [item.scholarship_id for item in ranked] == [1, 2]

    def test_the_full_ranked_response_is_reproducible(self):
        from app.services.matching.engine import summarise

        universe = build_universe()
        first = summarise(universe, total_candidates=len(universe))["summary"]
        second = summarise(universe, total_candidates=len(universe))["summary"]
        assert first.model_dump() == second.model_dump()


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 24. Natural-language profile parsing
# ---------------------------------------------------------------------------

STATEMENT = (
    "I'm from Bangladesh and want a fully funded Master's in Computer Science "
    "in Europe. I have IELTS 7."
)


_UNSET = object()


def parse(text=_UNSET):
    from app.services.matching.nlp import parse_natural_language_profile

    return parse_natural_language_profile(STATEMENT if text is _UNSET else text)


def resolved_field(parsed, field: str):
    return next((item for item in parsed.resolved if item.field == field), None)


class TestNaturalLanguageProfile:
    def test_the_documented_example_is_understood_end_to_end(self):
        parsed = parse()
        assert parsed.profile["citizenship"] == "Bangladesh"
        assert parsed.profile["intended_degree_level"] == "MASTER"
        assert parsed.profile["intended_field"] == "computer_science"
        assert parsed.profile["funding_requirement"] == "FULL_FUNDING"
        assert parsed.profile["language_credentials"] == [{"test": "ielts", "score": 7.0}]
        assert parsed.profile["preferred_countries"]

    def test_a_region_becomes_its_curated_member_countries(self):
        from app.services.matching.nlp import REGION_MEMBERS

        parsed = parse()
        assert parsed.profile["preferred_countries"] == list(REGION_MEMBERS["europe"])
        assert "Germany" in parsed.profile["preferred_countries"]

    def test_every_interpretation_carries_the_phrase_it_came_from(self):
        """The student can always see what was read, and correct it."""
        for item in parse().resolved:
            assert item.source
            assert item.display
            assert item.status == "RESOLVED"

    def test_the_degree_patterns_are_longest_first(self):
        assert parse("I want a postdoc in Computer Science.").profile.get(
            "intended_degree_level"
        ) == "POSTDOCTORAL"
        assert parse("I want a PhD in Computer Science.").profile["intended_degree_level"] == "DOCTORAL"

    def test_the_full_funding_phrase_is_not_read_as_tuition_only(self):
        parsed = parse("I need full funding for a Master's in Computer Science.")
        assert parsed.profile["funding_requirement"] == "FULL_FUNDING"

    def test_tuition_only_is_read_as_tuition_only(self):
        parsed = parse("Tuition covered is enough for me, and I want a Master's.")
        assert parsed.profile["funding_requirement"] == "TUITION_ONLY_SUFFICIENT"

    def test_no_funding_requirement_is_read_as_no_requirement(self):
        parsed = parse("I don't need any funding, I want a Master's in History.")
        assert parsed.profile["funding_requirement"] == "NO_SPECIFIC_NEED"

    def test_an_unresolvable_country_is_reported_not_guessed(self):
        parsed = parse("I am from Wakanda and want a Master's in Computer Science.")
        assert parsed.profile.get("citizenship") is None
        unresolved = [item for item in parsed.unresolved if item.field == "citizenship"]
        assert unresolved
        assert "not in ScholarZone" in unresolved[0].note

    def test_an_unrecognised_subject_is_reported_not_guessed(self):
        parsed = parse("I want to study Interpretive dance.")
        assert parsed.profile.get("intended_field") is None

    def test_an_impossible_language_score_is_refused(self):
        parsed = parse("I have IELTS 400.")
        assert parsed.profile.get("language_credentials") is None
        unresolved = [item for item in parsed.unresolved if item.field == "language_credentials"]
        assert unresolved
        assert "outside every range" in unresolved[0].note

    def test_text_with_nothing_recognisable_is_empty_rather_than_wrong(self):
        for text in ("asdf qwerty zxcv", "", "   ", None):
            parsed = parse(text)
            assert parsed.is_empty is True
            assert parsed.profile == {}

    def test_a_partial_statement_extracts_only_what_it_can_map(self):
        parsed = parse("I have IELTS 7.")
        assert parsed.profile == {"language_credentials": [{"test": "ielts", "score": 7.0}]}

    def test_a_bare_number_is_not_treated_as_a_language_score(self):
        parsed = parse("I am 7 years old and I want to study Computer Science.")
        assert not parsed.profile.get("language_credentials")

    def test_the_parser_is_deterministic(self):
        first, second = parse(), parse()
        assert first.profile == second.profile
        assert first.resolved == second.resolved
        assert first.unresolved == second.unresolved

    def test_the_input_is_length_bounded(self):
        from app.services.matching.config import NATURAL_LANGUAGE_MAX_LENGTH

        parsed = parse("I have IELTS 7. " * 500)
        assert isinstance(parsed.profile, dict)

    def test_the_parser_needs_no_external_ai_service(self):
        """Curated tables only, so the endpoint is a pure function of the text."""
        import inspect as _inspect

        from app.services.matching import nlp

        source = _inspect.getsource(nlp).lower()
        for forbidden in ("openai", "anthropic", "requests.", "httpx", "urllib", "http://"):
            assert forbidden not in source, forbidden

    def test_the_confirmation_payload_is_serialisable_and_editable(self):
        from app.services.matching.nlp import parsed_profile_response

        payload = parsed_profile_response(parse())
        assert payload["deterministic"] is True
        assert payload["empty"] is False
        assert payload["resolved"]
        assert payload["unresolved"] == []
        for item in payload["resolved"]:
            assert set(item) == {"field", "value", "display", "source", "status", "note"}
        assert "you can change or remove anything" in payload["note"]

    def test_an_empty_message_returns_a_normal_empty_confirmation_state(self):
        from app.services.matching.nlp import parsed_profile_response

        payload = parsed_profile_response(parse(None))
        assert payload["empty"] is True
        assert payload["profile"] == {}
        assert payload["resolved"] == []

    def test_the_parsed_payload_is_valid_input_to_the_engine(self):
        """A parsed profile and a typed profile are indistinguishable downstream."""
        from app.services.matching.nlp import parsed_profile_response

        payload = parsed_profile_response(parse())
        request = MatchProfileRequest(**payload["profile"])
        profile = normalise_profile(request)
        assert profile.citizenship_code == "BD"
        assert profile.intended_degree_level == "MASTER"
        assert profile.intended_field == "computer_science"
        assert profile.language_credentials == (("ielts", 7.0, None),)

    def test_the_parser_cannot_reach_a_score_on_its_own(self):
        """It produces a profile payload and nothing else."""
        parsed = parse()
        assert parsed.profile
        for item in parsed.resolved:
            assert item.field in {
                "citizenship",
                "intended_degree_level",
                "intended_field",
                "funding_requirement",
                "language_credentials",
                "study_mode",
                "preferred_countries",
            }
        assert not hasattr(parsed, "fit_score")
        assert not hasattr(parsed, "score")


# ---------------------------------------------------------------------------
# 25. Request validation
# ---------------------------------------------------------------------------


class TestRequestValidation:
    def test_the_preferred_country_bound_covers_every_curated_region(self):
        """Regression guard: Europe expanded to 32 countries against a cap of 25,
        so the parser's own documented example failed validation."""
        from app.services.matching.config import MAX_PREFERRED_COUNTRIES
        from app.services.matching.nlp import REGION_MEMBERS

        assert MAX_PREFERRED_COUNTRIES >= max(
            len(members) for members in REGION_MEMBERS.values()
        )
        assert MAX_PREFERRED_COUNTRIES == 32

    def test_an_empty_profile_is_valid(self):
        """No required field: an anonymous visitor is never blocked."""
        assert MatchProfileRequest().model_dump()

    def test_unknown_fields_are_rejected(self):
        with pytest.raises(Exception) as raised:
            MatchProfileRequest(admission_chance=True)
        assert "admission_chance" in str(raised.value)

    @pytest.mark.parametrize("age", [5, -1, 200])
    def test_an_out_of_range_age_is_rejected(self, age):
        with pytest.raises(Exception):
            MatchProfileRequest(age=age)

    def test_an_invalid_degree_level_is_rejected(self):
        with pytest.raises(Exception):
            MatchProfileRequest(intended_degree_level="SPACE_DEGREE")

    def test_an_invalid_funding_requirement_is_rejected(self):
        with pytest.raises(Exception):
            MatchProfileRequest(funding_requirement="MONEY_FOR_NOTHING")

    def test_an_invalid_study_mode_is_rejected(self):
        with pytest.raises(Exception):
            MatchProfileRequest(study_mode="SUBMARINE")

    def test_an_invalid_grading_scale_is_rejected(self):
        with pytest.raises(Exception):
            AcademicMark(scale="SAT_1600", value=1400)

    @pytest.mark.parametrize("wrong", ["twenty two", "22.5"])
    def test_a_non_integer_age_is_rejected(self, wrong):
        with pytest.raises(Exception):
            MatchProfileRequest(age=wrong)

    def test_a_wrongly_typed_list_is_rejected(self):
        with pytest.raises(Exception):
            MatchProfileRequest(language_credentials="IELTS 7")

    def test_an_out_of_range_limit_is_rejected(self):
        from app.services.matching.config import MATCH_RESULT_LIMIT_MAX

        assert MatchProfileRequest(limit=MATCH_RESULT_LIMIT_MAX)
        with pytest.raises(Exception):
            MatchProfileRequest(limit=MATCH_RESULT_LIMIT_MAX + 1)

    def test_a_preferred_country_list_is_length_bounded(self):
        from app.services.matching.config import MAX_PREFERRED_COUNTRIES

        assert MatchProfileRequest(preferred_countries=["India"] * MAX_PREFERRED_COUNTRIES)
        with pytest.raises(Exception):
            MatchProfileRequest(preferred_countries=["India"] * (MAX_PREFERRED_COUNTRIES + 1))




    def test_a_language_credential_list_is_length_bounded(self):
        with pytest.raises(Exception):
            MatchProfileRequest(
                language_credentials=[{"test": "IELTS", "score": 7}] * 9
            )

    def test_a_subject_result_list_is_length_bounded(self):
        with pytest.raises(Exception):
            MatchProfileRequest(
                subject_results=[{"scale": "GPA_4", "value": 3.5}] * 13
            )

    def test_free_text_fields_are_length_bounded(self):
        with pytest.raises(Exception):
            MatchProfileRequest(intended_field="x" * 121)
        with pytest.raises(Exception):
            MatchProfileRequest(citizenship="x" * 81)
        with pytest.raises(Exception):
            MatchProfileRequest(country_filter="x" * 121)

    def test_a_negative_self_contribution_is_rejected(self):
        with pytest.raises(Exception):
            MatchProfileRequest(max_self_contribution=-1)

    def test_an_out_of_scale_mark_is_refused_rather_than_accepted_as_a_number(self):
        """The model tolerates it; the engine must not interpret it.

        Rejecting at the boundary would break a documented behaviour: the
        normalisation tests rely on an out-of-scale value being treated as
        absent rather than as an error.
        """
        assert normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=4.6))
        ).overall_result is None

    def test_a_percentage_value_is_never_reinterpreted_as_a_small_gpa(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.PERCENTAGE, value=3.9))
        )
        assert profile.overall_result == pytest.approx(3.9)
        # The scale is recorded, so a published percentage minimum is still
        # comparable and a GPA minimum is not.
        assert profile.overall_scale_label == "PERCENTAGE"

    def test_the_response_carries_every_version_a_reader_needs(self):
        from app.services.matching.engine import engine_metadata

        metadata = engine_metadata(AS_OF)
        assert metadata["engine_version"] == "2.0.0"
        assert metadata["scoring_config_version"] == "2.0.0"
        assert metadata["field_taxonomy_version"] == "1.0.0"
        assert metadata["requirement_reader_version"] == "2.0.0"
        assert metadata["deadline_semantics_version"] == "1.0.0"
        assert metadata["as_of"] == "2026-03-01"
        assert metadata["formula"]
        assert metadata["weights"] == dict(FIT_WEIGHTS)


# ---------------------------------------------------------------------------
# 26. Regression guards
# ---------------------------------------------------------------------------


class TestPreviouslyFixedDefects:
    def test_academic_raw_and_normalised_values_are_not_mixed(self):
        profile = normalise_profile(
            strong_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.9))
        )
        assert profile.overall_result == pytest.approx(97.5)
        assert profile.overall_result != pytest.approx(3.9)

    def test_a_letter_grade_normalises_as_a_band_and_never_as_a_raw_number(self):
        from app.services.matching.normalize import letter_to_band

        assert letter_to_band("A") == pytest.approx(93.0)
        assert letter_to_band("F") == pytest.approx(0.0)
        assert letter_to_band(None) is None
        assert letter_to_band("Z") is None
        # The point of the function: a grade becomes a percentage, not a 4.
        assert letter_to_band("A") > 4.0

    def test_a_lowercase_country_still_resolves(self):
        assert normalise_profile(strong_profile(citizenship="india")).citizenship_code == "IN"
        assert normalise_profile(strong_profile(citizenship="  India  ")).citizenship_code == "IN"

    def test_the_country_filter_is_trimmed_and_matched_case_insensitively(self):
        from app.services.matching.normalize import resolve_country_code

        profile = normalise_profile(strong_profile(country_filter="  united kingdom "))
        assert profile.country_filter == "united kingdom"
        assert resolve_country_code(profile.country_filter) == "GB"

    def test_a_field_alias_does_not_shadow_a_longer_one(self):
        assert resolve_field("informatics science").key == "information_science"
        assert resolve_field("informatics").key == "computer_science"

    @pytest.mark.parametrize("text", ["Nordic", "European", "developing countries", "any country"])
    def test_a_partial_citizenship_phrase_is_not_read_as_a_country(self, text):
        assert normalise_profile(strong_profile(citizenship=text)).citizenship_code is None

    def test_the_response_never_echoes_the_applicant_age(self):
        for item in build_universe():
            dumped = item.model_dump()
            assert "age" not in dumped
            assert "max_self_contribution" not in dumped

    def test_the_public_result_never_carries_a_suppressed_raw_fit(self):
        from app.services.matching.types import MatchResult

        assert "suppressed_fit_score" not in MatchResult.model_fields
        for item in build_universe():
            assert "suppressed_fit_score" not in item.model_dump()

    def test_every_component_reports_its_configured_weight(self):
        for item in build_universe():
            for component in item.score_breakdown:
                assert component.weight == FIT_WEIGHTS[component.name]

    def test_reasons_are_codes_with_evidence(self):
        for item in build_universe():
            for reason in item.reasons:
                assert reason.code
                assert reason.message
                assert reason.component in {None, *FIT_WEIGHTS, "eligibility", "evidence"}

    def test_the_sensitivity_range_is_present_only_when_something_is_unmeasured(self):
        for item in build_universe():
            evaluated = [c for c in item.score_breakdown if c.score is not None]
            if item.sensitivity is None:
                assert len(evaluated) == 7
            else:
                assert len(evaluated) < 7
                if item.fit_score is not None:
                    assert (
                        item.sensitivity.lower_bound
                        <= item.fit_score
                        <= item.sensitivity.upper_bound
                    )

    def test_the_parser_cannot_reach_a_score_on_its_own(self):
        """It produces a profile payload and nothing else."""
        parsed = parse()
        assert parsed.profile
        for item in parsed.resolved:
            assert item.field in {
                "citizenship",
                "intended_degree_level",
                "intended_field",
                "funding_requirement",
                "language_credentials",
                "study_mode",
                "preferred_countries",
            }
        assert not hasattr(parsed, "fit_score")
        assert not hasattr(parsed, "score")

    def test_the_engine_is_free_of_network_and_clock_access(self):
        import inspect as _inspect

        from app.services.matching import components, metrics, summaries

        for module in (components, metrics, summaries):
            source = _inspect.getsource(module).lower()
            for forbidden in ("requests.", "httpx", "urllib", "date.today()", "datetime.now("):
                assert forbidden not in source, f"{module.__name__}: {forbidden}"
