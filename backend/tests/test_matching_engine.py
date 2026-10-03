"""Unit tests for the ScholarZone Match engine.

These tests are deliberately free of any database. The engine is pure, so its
behaviour can be pinned exactly with hand-built facts, and a failure here names a
scoring rule rather than a query.

Every fact used below is a plausible shape of a real catalogue record. None of
them invents a scholarship: the records are constructed to exercise one scoring
rule each, and the requirement strings they carry are quoted from the kind of
wording awarding bodies actually publish.

The properties asserted here are the ones the feature promises:
determinism, monotonic academic scoring, UNKNOWN-is-not-zero, weight
normalisation, hard-gate precedence and confidence being independent of fit.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.matching.academic import compare_to_minimum
from app.services.matching.components import (
    normalise_funding_state,
    score_language,
    score_preference,
    score_requirements,
    score_timing,
)
from app.services.matching.confidence import compute_confidence
from app.services.matching.constants import FIT_BAND_KEYS, FIT_WEIGHTS
from app.services.matching.eligibility import evaluate, evaluate_deadline
from app.services.matching.engine import rank_results, score_record, summarise
from app.services.matching.normalize import build_profile_index, normalise_profile
from app.services.matching.requirements import (
    read_academic_minimum,
    read_age,
    read_language_minimum,
    read_nationality,
)
from app.services.matching.taxonomy import relate_fields, resolve_field
from app.services.matching.types import (
    AcademicMark,
    EligibilityStatus,
    FundingRequirement,
    FundingState,
    GradingScale,
    LanguageCredential,
    MatchProfileRequest,
    MatchResult,
    ScholarshipFacts,
    StudyMode,
)

AS_OF = date(2026, 3, 1)


# ---------------------------------------------------------------------------
# Fact builders
# ---------------------------------------------------------------------------


def make_facts(**overrides) -> ScholarshipFacts:
    """A record with every scoring-relevant field populated.

    Defaults describe a fully documented, tuition-and-living funded scholarship
    that publishes an IELTS minimum and a citizenship restriction. Individual
    tests override one or two fields to isolate a rule.
    """
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
        documents=["Academic transcript", "CV", "Recommendation letter"],
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


def high_profile(**overrides) -> MatchProfileRequest:
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


def medium_profile(**overrides) -> MatchProfileRequest:
    """A profile that lands in the MEDIUM band: 2.8/4.0 normalises to 70.0."""
    base = dict(
        age=24,
        citizenship="Nigeria",
        country_of_residence="Nigeria",
        overall_result=AcademicMark(scale=GradingScale.GPA_4, value=2.8),
        intended_degree_level="MASTER",
        intended_field="computer_science",
        language_credentials=[LanguageCredential(test="IELTS", score=6.7)],
        funding_requirement=FundingRequirement.TUITION_ONLY_SUFFICIENT,
        max_self_contribution=8000.0,
    )
    base.update(overrides)
    return MatchProfileRequest(**base)


def low_profile(**overrides) -> MatchProfileRequest:
    """A profile that lands in the LOW band: 1.9/4.0 normalises to 47.5."""
    base = dict(
        age=29,
        overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.9),
        intended_degree_level="BACHELOR",
        intended_field="history",
        language_credentials=[],
        funding_requirement=FundingRequirement.FULL_FUNDING,
        living_cost_support_required=True,
    )
    base.update(overrides)
    return MatchProfileRequest(**base)


def score(request: MatchProfileRequest, facts: ScholarshipFacts):
    return score_record(normalise_profile(request), facts, AS_OF)


def component(result, name):
    return next(item for item in result.score_breakdown if item.name == name)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


class TestNormalisation:
    def test_gpa_is_rescaled_within_its_own_scale(self):
        profile = normalise_profile(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.5))
        )
        assert profile.overall_result == pytest.approx(87.5)
        assert profile.overall_scale_label == "GPA_4"

    def test_five_point_scale_is_rescaled_without_claiming_equivalence(self):
        profile = normalise_profile(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_5, value=4.5))
        )
        assert profile.overall_result == pytest.approx(90.0)
        assert profile.overall_scale_label == "GPA_5"

    def test_percentage_is_rescaled_within_itself(self):
        profile = normalise_profile(
            high_profile(overall_result=AcademicMark(scale=GradingScale.PERCENTAGE, value=88))
        )
        assert profile.overall_result == pytest.approx(88.0)

    def test_value_outside_its_declared_scale_is_not_interpreted(self):
        profile = normalise_profile(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=4.6))
        )
        assert profile.overall_result is None

    def test_missing_mark_stays_missing(self):
        profile = normalise_profile(high_profile(overall_result=None))
        assert profile.overall_result is None
        assert profile.overall_scale_label == "unavailable"

    def test_unknown_country_is_not_guessed(self):
        profile = normalise_profile(high_profile(citizenship="Atlantis"))
        assert profile.citizenship_code is None

    def test_known_country_resolves_to_iso_code(self):
        profile = normalise_profile(high_profile(citizenship="India"))
        assert profile.citizenship_code == "IN"


# ---------------------------------------------------------------------------
# Requirement readers
# ---------------------------------------------------------------------------


class TestRequirementReaders:
    def test_explicit_minimum_is_read_with_its_scale_and_quote(self):
        requirement, absent = read_academic_minimum(
            ["Applicants must have a minimum GPA of 3.5/4.0."], "https://example.edu"
        )
        assert requirement is not None
        assert requirement.minimum_value == 3.5
        assert requirement.scale is GradingScale.GPA_4
        assert requirement.provenance_url == "https://example.edu"
        assert "3.5/4.0" in requirement.raw_quote
        assert absent is False

    def test_hedged_wording_produces_no_threshold(self):
        requirement, absent = read_academic_minimum(
            ["No fixed CGPA requirement - selection weighs motivation more heavily than grades."],
            None,
        )
        assert requirement is None
        assert absent is True

    def test_bare_gpa_without_a_denominator_is_not_converted(self):
        requirement, _ = read_academic_minimum(["Applicants must have a minimum GPA of 3.5."], None)
        assert requirement is None

    def test_language_threshold_requires_a_mandatory_qualifier(self):
        requirement, _ = read_language_minimum("IELTS 6.5 or above required.", None)
        assert requirement is not None
        assert requirement.test_name == "ielts"
        assert requirement.minimum_value == 6.5

    def test_optional_language_is_not_a_requirement(self):
        requirement, not_required = read_language_minimum(
            "Not mandatory. TOPIK or TOEFL/IELTS scores may provide additional evaluation advantage.",
            None,
        )
        assert requirement is None
        assert not_required is True

    def test_nationality_restriction_by_named_country(self):
        requirement = read_nationality(["Applicants must be citizens of the European Union."], None)
        assert requirement is not None
        assert "IN" not in requirement.allowed_terms
        assert "DE" in requirement.allowed_terms

    def test_designated_country_scheme_yields_no_comparable_set(self):
        requirement = read_nationality(
            ["Citizen of an NIIED-designated country; parents must not hold Korean citizenship."], None
        )
        assert requirement is None

    def test_explicit_age_bound(self):
        requirement = read_age(["Applicants must be under 30 years of age."], None)
        assert requirement is not None
        assert requirement.age_max == 29

    def test_explicit_no_age_limit_produces_no_gate(self):
        assert read_age(["No general age limit applies."], None) is None


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


class TestTaxonomy:
    def test_exact_relationship(self):
        assert relate_fields("computer_science", "computer_science").score == 100

    def test_close_specialization(self):
        relationship = relate_fields("computer_science", "software_engineering")
        assert relationship.level == "CLOSE_SPECIALIZATION"
        assert relationship.score == 85

    def test_related_field(self):
        relationship = relate_fields("computer_science", "mathematics")
        assert relationship.level == "RELATED_FIELD"
        assert relationship.score == 65

    def test_broad_field(self):
        relationship = relate_fields("software_engineering", "engineering")
        assert relationship.level == "BROAD_FIELD"
        assert relationship.score == 40

    def test_unrelated_disciplines(self):
        assert relate_fields("computer_science", "business").score == 0

    def test_unknown_programme_text_is_unresolved_not_unrelated(self):
        assert resolve_field("Interstellar Basket Weaving").key is None

    def test_alias_matching_respects_word_boundaries(self):
        assert resolve_field("MSc Computer Science").key == "computer_science"
        assert resolve_field("Scholarship Studies").key is None


# ---------------------------------------------------------------------------
# Academic fit
# ---------------------------------------------------------------------------


class TestAcademicFit:
    def _requirement(self, value=3.5, scale=GradingScale.GPA_4, preferred=None):
        from app.services.matching.types import NormalisedRequirement, RequirementKind

        return NormalisedRequirement(
            kind=RequirementKind.ACADEMIC_MINIMUM,
            raw_quote="Minimum GPA of 3.5/4.0 required.",
            provenance_url="https://example.edu",
            minimum_value=value,
            scale=scale,
            preferred_value=preferred,
        )

    def test_meeting_the_minimum_scores_the_configured_value(self):
        profile = normalise_profile(high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.5)))
        comparison = compare_to_minimum(profile, self._requirement())
        assert comparison.state == "MEETS_MINIMUM"
        assert comparison.score == 85.0

    def test_a_published_benchmark_interpolates_between_the_two_anchors(self):
        # The locked formula for the both-anchors case is
        # 100 x (student - minimum) / (preferred - minimum), so sitting exactly
        # on the published minimum is 0 and reaching the published benchmark is
        # 100. Meeting a floor and reaching a stated standard are different
        # achievements; the awarding body published both numbers.
        profile = normalise_profile(high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.5)))
        comparison = compare_to_minimum(profile, self._requirement(preferred=4.0))
        assert comparison.state == "MEETS_MINIMUM"
        assert comparison.score == pytest.approx(0.0)

        profile_mid = normalise_profile(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.75))
        )
        comparison_mid = compare_to_minimum(profile_mid, self._requirement(preferred=4.0))
        assert comparison_mid.score == pytest.approx(50.0)

        profile_high = normalise_profile(high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=4.0)))
        comparison_high = compare_to_minimum(profile_high, self._requirement(preferred=4.0))
        assert comparison_high.state == "ABOVE_PREFERRED"
        assert comparison_high.score == 100.0

    def test_scale_mismatch_is_incomparable_not_converted(self):
        profile = normalise_profile(high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_5, value=4.5)))
        comparison = compare_to_minimum(profile, self._requirement())
        assert comparison.state == "INCOMPARABLE"
        assert comparison.score is None

    def test_missing_student_mark_is_unknown_not_a_failure(self):
        profile = normalise_profile(high_profile(overall_result=None))
        comparison = compare_to_minimum(profile, self._requirement())
        assert comparison.state == "STUDENT_MARK_UNKNOWN"
        assert comparison.score is None

    @pytest.mark.parametrize("value", [2.9, 3.0, 3.4, 3.49])
    def test_monotonic_academic_scoring_across_the_minimum(self, value):
        """Raising a mark from below the minimum to above it never lowers fit."""
        below = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=value)),
            make_facts(),
        )
        assert below.eligibility is EligibilityStatus.INELIGIBLE

        above = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.6)),
            make_facts(),
        )
        assert above.eligibility is EligibilityStatus.ELIGIBLE
        assert component(above, "academic").score > 0

    def test_monotonicity_holds_across_the_whole_range(self):
        scores = []
        for value in [3.0, 3.2, 3.4, 3.5, 3.6, 3.8, 4.0]:
            profile = normalise_profile(
                high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=value))
            )
            comparison = compare_to_minimum(profile, self._requirement())
            scores.append(comparison.score if comparison.score is not None else 0.0)
        assert scores == sorted(scores)


# ---------------------------------------------------------------------------
# Profile index
# ---------------------------------------------------------------------------


class TestProfileIndex:
    def test_high_profile_classifies_as_high(self):
        index = build_profile_index(normalise_profile(high_profile()))
        assert index.score is not None
        assert index.score >= 75

    def test_medium_profile_classifies_as_medium(self):
        index = build_profile_index(normalise_profile(medium_profile()))
        assert index.score is not None
        assert 50 <= index.score < 75

    def test_low_profile_classifies_as_low(self):
        index = build_profile_index(normalise_profile(low_profile()))
        assert index.score is not None
        assert index.score < 50

    def test_no_academic_data_yields_no_index_rather_than_zero(self):
        index = build_profile_index(normalise_profile(high_profile(overall_result=None, subject_results=[])))
        assert index.score is None

    def test_weights_are_renormalised_over_supplied_components_only(self):
        index = build_profile_index(normalise_profile(high_profile(subject_results=[])))
        total = sum(component.weight for component in index.components)
        assert total == pytest.approx(1.0)

    def test_optional_missing_components_do_not_drag_the_index_down(self):
        """When the remaining component agrees, dropping one changes nothing.

        The subject component here matches the overall result exactly, so the
        renormalised index is identical. That is the point: an absent optional
        component must not act as a penalty.
        """
        matching = high_profile(
            subject_results=[AcademicMark(scale=GradingScale.GPA_4, value=3.9, field="computer_science")]
        )
        full = build_profile_index(normalise_profile(matching))
        partial = build_profile_index(normalise_profile(high_profile(subject_results=[])))
        assert partial.score == pytest.approx(full.score)


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


class TestFunding:
    def test_fully_covered_funds_is_full(self):
        state, _, _ = normalise_funding_state(make_facts())
        assert state is FundingState.FULL

    def test_tuition_only_is_not_full(self):
        state, _, _ = normalise_funding_state(make_facts(living_cost_coverage=False))
        assert state is FundingState.TUITION_ONLY

    def test_unverified_coverage_is_unknown_not_partial(self):
        state, _, _ = normalise_funding_state(
            make_facts(
                tuition_coverage=None,
                living_cost_coverage=None,
                funding_amount=None,
                funding_label=None,
                coverage=[],
            )
        )
        assert state is FundingState.UNKNOWN

    def test_fully_funded_false_alone_does_not_prove_a_partial_award(self):
        """The column defaults to false, so false means "not established"."""
        state, _, _ = normalise_funding_state(
            make_facts(
                tuition_coverage=None,
                living_cost_coverage=None,
                funding_amount=None,
                funding_label="Fully Funded",
                fully_funded=False,
                coverage=[],
            )
        )
        assert state is FundingState.UNKNOWN

    def test_full_funding_need_prefers_full_over_tuition_only(self):
        profile = normalise_profile(high_profile())
        full_state, full_detail, _ = normalise_funding_state(make_facts())
        tuition_state, tuition_detail, _ = normalise_funding_state(
            make_facts(living_cost_coverage=False)
        )
        from app.services.matching.components import score_funding

        full_score = score_funding(profile, full_state, full_detail)[0]
        tuition_score = score_funding(profile, tuition_state, tuition_detail)[0]
        assert full_score > tuition_score

    def test_unknown_funding_is_not_evaluated_rather_than_zero(self):
        profile = normalise_profile(high_profile())
        from app.services.matching.components import score_funding

        score = score_funding(profile, FundingState.UNKNOWN, "No verified detail.")[0]
        assert score is None

    @pytest.mark.parametrize(
        "coverage,expected",
        [
            (["Full tuition and monthly stipend"], FundingState.FULL),
            (["Full tuition fees", "Monthly stipend for living expenses"], FundingState.FULL),
            (["100% tuition waiver plus accommodation"], FundingState.FULL),
            (["Full tuition only; living costs are not covered"], FundingState.TUITION_ONLY),
            (["Tuition fees are waived"], FundingState.TUITION_PLUS_LIVING),
            (["No financial support is offered"], FundingState.NONE),
            (["Travel allowance"], FundingState.UNKNOWN),
            ([], FundingState.UNKNOWN),
        ],
    )
    def test_published_coverage_text_is_read_when_columns_are_absent(self, coverage, expected):
        """Official benefit text is evidence, and is available on most records."""
        facts = make_facts(
            coverage=coverage,
            tuition_coverage=None,
            living_cost_coverage=None,
            funding_amount=None,
        )
        state, _, evidence = normalise_funding_state(facts)
        assert state is expected
        if expected is not FundingState.UNKNOWN:
            assert evidence["published_coverage_quote"]

    def test_structured_columns_take_precedence_over_published_text(self):
        """A recorded coverage flag is stronger evidence than prose."""
        facts = make_facts(
            coverage=["No financial support is offered"],
            tuition_coverage=True,
            living_cost_coverage=False,
        )
        state, _, _ = normalise_funding_state(facts)
        assert state is FundingState.TUITION_ONLY

    def test_a_non_specific_label_alone_never_becomes_a_coverage_fact(self):
        """The funding column is NOT NULL, so a vague label must stay unknown."""
        facts = make_facts(
            coverage=[],
            tuition_coverage=None,
            living_cost_coverage=None,
            funding_amount=None,
            funding_label="Varies",
        )
        state, detail, _ = normalise_funding_state(facts)
        assert state is FundingState.UNKNOWN
        assert "could not be established" in detail


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------


class TestLanguage:
    def _requirement(self):
        from app.services.matching.types import NormalisedRequirement, RequirementKind

        return NormalisedRequirement(
            kind=RequirementKind.LANGUAGE_MINIMUM,
            raw_quote="IELTS 6.5 or above required.",
            provenance_url="https://example.edu",
            minimum_value=6.5,
            test_name="ielts",
        )

    def test_meeting_the_threshold_is_evaluated(self):
        profile = normalise_profile(high_profile())
        score, detail, _ = score_language(profile, self._requirement(), False)
        assert score is not None
        assert "6.5" in detail

    def test_different_test_is_unknown_and_never_converted(self):
        profile = normalise_profile(
            high_profile(language_credentials=[LanguageCredential(test="TOEFL", score=100)])
        )
        score, detail, _ = score_language(profile, self._requirement(), False)
        assert score is None
        assert "does not convert" in detail

    def test_no_requirement_is_not_evaluated(self):
        profile = normalise_profile(high_profile())
        score, _, _ = score_language(profile, None, False)
        assert score is None

    def test_explicitly_not_required_is_not_evaluated(self):
        profile = normalise_profile(high_profile())
        score, _, _ = score_language(profile, None, True)
        assert score is not None

    def test_unrecognised_test_is_dropped_rather_than_guessed(self):
        profile = normalise_profile(
            high_profile(language_credentials=[LanguageCredential(test="Martian Standard", score=99)])
        )
        assert profile.language_credentials == ()


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


class TestTiming:
    def _facts(self, **overrides):
        return make_facts(**overrides)

    def _score(self, facts):
        deadline = evaluate_deadline(facts, AS_OF)
        return score_timing(facts, deadline)

    @pytest.mark.parametrize(
        "days,expected",
        [
            (120, 100.0),
            (60, 100.0),
            (45, 90.0),
            (30, 90.0),
            (20, 75.0),
            (14, 75.0),
            (10, 55.0),
            (7, 55.0),
            (5, 30.0),
            (1, 30.0),
        ],
    )
    def test_exact_deadline_bands(self, days, expected):
        from datetime import timedelta

        target = (AS_OF + timedelta(days=days)).isoformat()
        score, _, evidence = self._score(self._facts(deadline_date=target))
        assert score == expected
        assert evidence["approximate"] is False

    def test_closed_round_is_reported_as_closed(self):
        deadline = evaluate_deadline(self._facts(deadline_date="2020-01-01"), AS_OF)
        assert deadline.closed is True

    def test_closed_status_without_a_date_is_still_closed(self):
        deadline = evaluate_deadline(self._facts(deadline_date=None, status="closed"), AS_OF)
        assert deadline.closed is True

    def test_rolling_deadline_is_not_evaluated(self):
        facts = self._facts(
            deadline_date=None,
            deadline_display="Applications are accepted on a rolling basis",
            deadline_precision="rolling",
        )
        score, detail, evidence = self._score(facts)
        assert score is None
        assert evidence["deadline_kind"] == "rolling"

    def test_annual_deadline_is_not_evaluated(self):
        facts = self._facts(
            deadline_date=None,
            deadline_display="Applications close on 30 November every year",
            deadline_precision="recurring",
        )
        score, _, _ = self._score(facts)
        assert score is None

    def test_no_deadline_at_all_is_not_evaluated(self):
        facts = self._facts(deadline_date=None, deadline_display=None, deadline_precision="unknown")
        score, detail, _ = self._score(facts)
        assert score is None
        assert "No fixed application deadline" in detail

    def test_month_precision_is_scored_to_the_end_of_the_month_and_flagged(self):
        # As-of 1 March, published as "April 2026" and stored as 1 April.
        # Counting to the stored date would say 31 days; the published statement
        # actually leaves the whole of April, so the measurement runs to the
        # 30th: 31 + 29 = 60 days, and the figure is labelled approximate.
        facts = self._facts(deadline_date="2026-04-01", deadline_display="April 2026", deadline_precision="month")
        score, detail, evidence = self._score(facts)
        assert score is not None
        assert evidence["approximate"] is True
        assert evidence["days_remaining"] == 60
        assert "approximate" in detail


# ---------------------------------------------------------------------------
# Preference
# ---------------------------------------------------------------------------


class TestPreference:
    def test_matching_country_scores_full(self):
        facts = make_facts(country="United Kingdom")
        score, _, _ = score_preference(normalise_profile(high_profile()), facts)
        assert score == 100

    def test_non_matching_country_is_not_zero_but_is_scored(self):
        facts = make_facts(country="Germany")
        score, _, _ = score_preference(normalise_profile(high_profile()), facts)
        assert score == 50

    def test_absent_preference_is_not_evaluated(self):
        profile = normalise_profile(medium_profile(preferred_countries=[]))
        score, _, _ = score_preference(profile, make_facts())
        assert score is None

    def test_multi_country_record_is_not_scored(self):
        facts = make_facts(country="EU (multiple)")
        score, detail, _ = score_preference(normalise_profile(high_profile()), facts)
        assert score is None
        assert "rather than a single country" in detail


# ---------------------------------------------------------------------------
# Requirements and confidence
# ---------------------------------------------------------------------------


class TestRequirementsAndConfidence:
    def test_documented_documents_produce_an_evaluated_component(self):
        fit = score_requirements(make_facts())
        assert fit.score is not None
        assert fit.evaluated >= 1

    def test_no_published_conditions_is_not_evaluated(self):
        fit = score_requirements(
            make_facts(documents=[], requirements=[], eligibility_summary=None, eligibility=[])
        )
        assert fit.score is None

    def test_confidence_is_higher_for_a_documented_record(self):
        from app.services.matching.requirements import read_requirements

        rich = make_facts()
        poor = make_facts(
            eligibility_summary=None,
            eligibility=[],
            requirements=[],
            documents=[],
            english_requirement=None,
            tuition_coverage=None,
            living_cost_coverage=None,
            funding_amount=None,
            funding_currency=None,
            funding_period=None,
            program_type=None,
            official_source=None,
            official_source_url=None,
            is_verified=False,
            last_verified_date=None,
            deadline_date=None,
            deadline_display=None,
            deadline_precision="unknown",
            coverage=[],
        )
        rich_confidence = compute_confidence(rich, read_requirements(rich), AS_OF)
        poor_confidence = compute_confidence(poor, read_requirements(poor), AS_OF)
        assert rich_confidence.score > poor_confidence.score

    def test_never_verified_record_loses_freshness_credit(self):
        from app.services.matching.requirements import read_requirements

        facts = make_facts(last_verified_date=None)
        result = compute_confidence(facts, read_requirements(facts), AS_OF)
        assert result.evidence.freshness_ratio == 0.0

    def test_confidence_is_independent_of_the_student_profile(self):
        """Confidence describes the record, so two profiles must agree."""
        low = score(low_profile(), make_facts())
        high = score(high_profile(), make_facts())
        assert low.confidence_score == high.confidence_score


# ---------------------------------------------------------------------------
# The hard gate
# ---------------------------------------------------------------------------


class TestHardEligibility:
    def test_all_conditions_met_is_eligible(self):
        result = score(high_profile(), make_facts())
        assert result.eligibility is EligibilityStatus.ELIGIBLE

    def test_academic_below_published_minimum_is_ineligible(self):
        result = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=3.0)),
            make_facts(),
        )
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        assert any("ACADEMIC_MINIMUM" in blocker.code for blocker in result.blockers)

    def test_nationality_outside_the_published_set_is_ineligible(self):
        facts = make_facts(eligibility=["Applicants must be citizens of India."])
        result = score(high_profile(citizenship="Nigeria"), facts)
        assert result.eligibility is EligibilityStatus.INELIGIBLE

    def test_missing_nationality_with_a_published_gate_needs_verification(self):
        facts = make_facts(eligibility=["Applicants must be citizens of India."])
        result = score(high_profile(citizenship=None), facts)
        assert result.eligibility is EligibilityStatus.NEEDS_VERIFICATION
        assert result.eligibility_detail.unverified

    def test_missing_language_with_a_published_gate_needs_verification(self):
        result = score(high_profile(language_credentials=[]), make_facts())
        assert result.eligibility is EligibilityStatus.NEEDS_VERIFICATION

    def test_closed_round_is_ineligible_even_with_a_perfect_profile(self):
        result = score(high_profile(), make_facts(status="closed"))
        assert result.eligibility is EligibilityStatus.INELIGIBLE

    def test_incomparable_academic_scale_needs_verification_not_ineligible(self):
        result = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_5, value=4.5)),
            make_facts(),
        )
        assert result.eligibility is EligibilityStatus.NEEDS_VERIFICATION

    def test_a_high_fit_score_cannot_rescue_an_ineligible_record(self):
        """The core separation. Soft fit is excellent and the gate still refuses."""
        result = score(
            high_profile(
                overall_result=AcademicMark(scale=GradingScale.GPA_4, value=2.5),
                language_credentials=[LanguageCredential(test="IELTS", score=9.0)],
                preferred_countries=["United Kingdom"],
                funding_requirement=FundingRequirement.NO_SPECIFIC_NEED,
                living_cost_support_required=None,
            ),
            make_facts(),
        )
        assert result.eligibility is EligibilityStatus.INELIGIBLE
        assert result.fit_label == "INELIGIBLE"
        assert "fit_label_display" in result.model_dump()

    def test_ineligible_records_report_no_fit_classification(self):
        result = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(),
        )
        assert result.fit_label_display == "Not eligible"
        assert result.fit_score is None

    def test_ineligible_records_never_publish_a_raw_fit_score(self):
        """The suppressed arithmetic stays inside the engine.

        A raw number on a refused result invites a client to keep ranking on it,
        which is exactly what the gate exists to prevent. It is not in the public
        contract at all.
        """
        ineligible = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(),
        )
        assert "suppressed_fit_score" not in ineligible.model_dump()
        assert "suppressed_fit_score" not in MatchResult.model_fields

    def test_needs_verification_keeps_its_fit_score_and_band(self):
        """The gate verdict is about our evidence, not about the student's fit.

        A NEEDS_VERIFICATION result is still a deterministic measurement, so it
        keeps both its score and its band. Eligibility is reported separately on
        the same result, and that is where the reader is told about it. Rewriting
        the band into a second key used to hide the score and break fit-tier and
        facet lookup at the same time.
        """
        result = score(high_profile(language_credentials=[]), make_facts())
        assert result.eligibility is EligibilityStatus.NEEDS_VERIFICATION
        assert result.fit_score is not None
        assert result.fit_label in FIT_BAND_KEYS
        assert result.fit_label_display not in {"Not eligible", "Not evaluated"}
        assert "needs verification" not in result.fit_label_display.lower()

    def test_a_band_label_is_never_composed_from_the_eligibility_state(self):
        """One deterministic label vocabulary, no string hacks."""
        from app.services.matching.metrics import (
            FIT_LABEL_INELIGIBLE,
            FIT_LABEL_NOT_EVALUATED,
        )

        allowed = set(FIT_BAND_KEYS) | {FIT_LABEL_INELIGIBLE, FIT_LABEL_NOT_EVALUATED}
        profiles = {
            "eligible": high_profile(),
            "unverified": high_profile(language_credentials=[]),
            "ineligible": high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
        }
        for result in (score(profile, make_facts(id=index + 1)) for index, profile in enumerate(profiles.values())):
            assert result.fit_label in allowed, result.fit_label

    def test_no_published_mandatory_conditions_is_eligible(self):
        facts = make_facts(
            eligibility=[],
            eligibility_summary=None,
            english_requirement="Not mandatory.",
        )
        result = score(high_profile(language_credentials=[]), facts)
        assert result.eligibility is EligibilityStatus.ELIGIBLE


# ---------------------------------------------------------------------------
# Weight normalisation
# ---------------------------------------------------------------------------


class TestWeightNormalisation:
    def test_all_dimensions_evaluated_gives_full_data_coverage(self):
        result = score(high_profile(), make_facts())
        assert result.data_coverage == pytest.approx(100.0)

    def test_removing_a_dimension_excludes_only_its_weight(self):
        baseline = score(high_profile(), make_facts())
        without_preference = score(high_profile(preferred_countries=[]), make_facts())

        assert component(without_preference, "preference").score is None
        assert component(without_preference, "preference").weight == FIT_WEIGHTS["preference"]
        assert without_preference.data_coverage == pytest.approx(
            (1.0 - FIT_WEIGHTS["preference"]) * 100.0, abs=0.2
        )
        assert without_preference.data_coverage < baseline.data_coverage

    def test_unknown_dimensional_scores_are_never_zero(self):
        result = score(high_profile(preferred_countries=[]), make_facts())
        unknown = component(result, "preference")
        assert unknown.score is None
        assert unknown.status.value == "NOT_EVALUATED"

    def test_excluding_a_component_does_not_change_the_others(self):
        baseline = score(high_profile(), make_facts())
        without_preference = score(high_profile(preferred_countries=[]), make_facts())
        for name in ("academic", "field", "funding", "language", "timing"):
            assert component(baseline, name).score == component(without_preference, name).score

    def test_a_genuine_zero_is_still_reported_as_evaluated(self):
        facts = make_facts(program_type="History", country="Germany")
        result = score(high_profile(preferred_countries=["Germany"]), facts)
        assert result.data_coverage > 0

    def test_nothing_evaluable_yields_no_score_rather_than_zero(self):
        bare = make_facts(
            program_type=None,
            degree_levels="Master",
            eligibility=[],
            eligibility_summary=None,
            requirements=[],
            documents=[],
            coverage=[],
            english_requirement=None,
            tuition_coverage=None,
            living_cost_coverage=None,
            funding_amount=None,
            funding_label=None,
            deadline_date=None,
            deadline_display=None,
            deadline_precision="unknown",
            country="Atlantis",
        )
        result = score(
            high_profile(
                overall_result=None,
                subject_results=[],
                preferred_countries=[],
                language_credentials=[],
                intended_field="undisclosed_field",
            ),
            bare,
        )
        assert result.data_coverage == 0.0


# ---------------------------------------------------------------------------
# Determinism and ranking
# ---------------------------------------------------------------------------


class TestDeterminismAndRanking:
    def test_identical_inputs_produce_identical_output(self):
        first = score(high_profile(), make_facts()).model_dump(mode="json")
        second = score(high_profile(), make_facts()).model_dump(mode="json")
        assert first == second

    def test_repeated_runs_of_the_engine_are_byte_identical(self):
        payloads = {
            score(high_profile(), make_facts()).model_dump_json(),
            score(high_profile(), make_facts()).model_dump_json(),
            score(high_profile(), make_facts()).model_dump_json(),
        }
        assert len(payloads) == 1

    def test_as_of_changes_timing_but_not_anything_else(self):
        # 121 days out and 26 days out straddle the 60-day band boundary, so
        # the timing score must differ while every other dimension is untouched.
        early = score_record(normalise_profile(high_profile()), make_facts(), date(2026, 3, 1))
        late = score_record(normalise_profile(high_profile()), make_facts(), date(2026, 5, 5))
        assert component(early, "timing").score != component(late, "timing").score
        assert component(early, "academic").score == component(late, "academic").score
        assert component(early, "funding").score == component(late, "funding").score
        assert early.eligibility is late.eligibility

    def test_ineligible_never_sorts_above_eligible(self):
        eligible = score(high_profile(), make_facts(id=1))
        ineligible = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)),
            make_facts(id=2),
        )
        ranked = rank_results([ineligible, eligible])
        assert [item.scholarship_id for item in ranked] == [1, 2]

    def test_needs_verification_sorts_below_eligible_and_above_ineligible(self):
        eligible = score(high_profile(), make_facts(id=1))
        unverified = score(high_profile(language_credentials=[]), make_facts(id=2))
        ranked = rank_results([unverified, eligible])
        assert [item.scholarship_id for item in ranked] == [1, 2]

    def test_ranking_is_a_total_order_with_a_stable_tiebreak(self):
        identical = [score(high_profile(), make_facts(id=index)) for index in (5, 3, 1)]
        first = [item.scholarship_id for item in rank_results(identical)]
        second = [item.scholarship_id for item in rank_results(list(reversed(identical)))]
        assert first == second == [1, 3, 5]

    def test_summary_counts_match_the_analysed_universe(self):
        results = [
            score(high_profile(), make_facts(id=1)),
            score(high_profile(language_credentials=[]), make_facts(id=2)),
            score(high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)), make_facts(id=3)),
        ]
        summary = summarise(results, total_candidates=3)
        assert summary["eligible_count"] == 1
        assert summary["needs_verification_count"] == 1
        assert summary["ineligible_count"] == 1
        assert summary["total_candidates"] == 3

    def test_summary_counts_reconcile_even_when_the_page_is_truncated(self):
        """The locked identity is against total_candidates, not the page size.

        Reconciling against the returned page used to make the identity change the
        moment a request was truncated, so the same analysis produced two
        different "correct" answers depending on the limit.
        """
        universe = [
            score(high_profile(), make_facts(id=1)),
            score(high_profile(language_credentials=[]), make_facts(id=2)),
            score(high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)), make_facts(id=3)),
            score(high_profile(), make_facts(id=4)),
        ]
        counted = summarise(universe, universe[:1], total_candidates=len(universe), truncated=True)
        summary = counted["summary"]
        assert summary.total_candidates == 4
        assert summary.visible_candidate_count == 1
        assert summary.truncated is True
        assert (
            summary.eligible_count + summary.needs_verification_count + summary.ineligible_count
            == summary.total_candidates
        )
        assert summary.scored_count + summary.not_scored_count == summary.total_candidates
        # Facets describe the returned page, so they can never over-report it.
        assert sum(bucket.count for bucket in counted["facets"].countries) == 1


# ---------------------------------------------------------------------------
# Explainability
# ---------------------------------------------------------------------------


class TestExplainability:
    def test_every_result_carries_engine_reasons(self):
        result = score(high_profile(), make_facts())
        codes = {item.code for item in result.reasons}
        assert "ACADEMIC_MEETS_MINIMUM" in codes
        assert "FIELD_EXACT" in codes
        assert "ELIGIBILITY_VERIFIED" in codes

    def test_unknown_components_produce_gaps_not_failures(self):
        result = score(high_profile(preferred_countries=[]), make_facts())
        gap_codes = {item.code for item in result.gaps}
        assert "PREFERENCE_NOT_PROVIDED" in gap_codes
        assert not result.blockers

    def test_blockers_only_appear_when_ineligible(self):
        assert not score(high_profile(), make_facts()).blockers
        ineligible = score(
            high_profile(overall_result=AcademicMark(scale=GradingScale.GPA_4, value=1.0)), make_facts()
        )
        assert ineligible.blockers

    def test_every_component_carries_its_weight(self):
        result = score(high_profile(), make_facts())
        for component_score in result.score_breakdown:
            assert component_score.weight == FIT_WEIGHTS[component_score.name]

    def test_evidence_status_is_attached_to_every_result(self):
        result = score(high_profile(), make_facts())
        assert result.evidence_status.has_official_source is True
        assert result.evidence_status.last_verified_date == "2026-02-01"

    def test_published_quotes_are_preserved_for_audit(self):
        result = score(high_profile(), make_facts())
        quotes = [outcome.raw_quote for outcome in result.requirements]
        assert any("IELTS" in quote for quote in quotes)
        assert all(outcome.provenance_url for outcome in result.requirements)