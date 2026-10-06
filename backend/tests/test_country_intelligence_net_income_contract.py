"""The net-income reference contract.

Take-home pay is not a property of a salary. It is a property of a salary *and* a
tax year, a household, a residency status and a set of employee deductions. These
tests hold the line that a net figure cannot ship without them, because the failure
this guards is specific and quiet: a number that looks exactly as trustworthy as
one read off a tax table, for a household nobody described.

They also pin the behaviour the corpus depends on elsewhere - that a net figure
never arrives as a naked scalar, and that ``ESTIMATE`` never becomes official.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.country_intelligence.net_income import (  # noqa: E402
    OPTIONAL_ASSUMPTIONS,
    REQUIRED_ASSUMPTIONS,
    NetIncomeError,
    NetIncomeProfile,
    profile_from_raw,
    validate_profile,
)

#: A complete, defensible profile: single adult, resident, contributions deducted.
COMPLETE_ASSUMPTIONS = {
    "marital_status": "single",
    "dependents": "none",
    "residency": "resident",
    "employee_social_contributions": "included",
}


def _profile(**overrides) -> NetIncomeProfile:
    base = {
        "assumptions": dict(COMPLETE_ASSUMPTIONS),
        "population": "median take-home pay, all employees",
        "tax_year": "2026",
        "currency": "EUR",
        "per": "month",
    }
    base.update(overrides)
    return NetIncomeProfile(**base)


class TestAValidProfileIsAccepted:
    def test_complete_profile_passes(self):
        validate_profile(_profile(), path="de.career.net_monthly_income")

    def test_it_reports_nothing_missing(self):
        assert _profile().missing_required() == []

    def test_it_describes_itself_for_a_reader(self):
        """A number with no sentence beside it is a naked scalar, which is the
        thing this contract exists to prevent."""
        text = _profile().describe()
        assert "2026" in text
        assert "single" in text
        assert "contributions included" in text

    def test_it_round_trips_to_a_dict(self):
        payload = _profile().to_dict()
        assert payload["tax_year"] == "2026"
        assert payload["per"] == "month"
        assert "marital_status" in payload["assumptions"]
        assert list(REQUIRED_ASSUMPTIONS) == payload["required_assumptions"]


class TestNakedScalarsAreRejected:
    """The central guard. Every one of these is a number a reader would trust."""

    def test_a_bare_scalar_cannot_be_a_profile(self):
        with pytest.raises(NetIncomeError):
            validate_profile(NetIncomeProfile(), path="de.career.net_monthly_income")

    def test_missing_marital_status_is_rejected(self):
        profile = _profile(assumptions={k: v for k, v in COMPLETE_ASSUMPTIONS.items() if k != "marital_status"})
        assert "marital_status" in profile.missing_required()
        with pytest.raises(NetIncomeError):
            validate_profile(profile, path="t")

    def test_missing_dependents_is_rejected(self):
        profile = _profile(assumptions={k: v for k, v in COMPLETE_ASSUMPTIONS.items() if k != "dependents"})
        with pytest.raises(NetIncomeError):
            validate_profile(profile, path="t")

    def test_missing_social_contributions_is_rejected(self):
        """The difference between a salary and what reaches the worker."""
        profile = _profile(
            assumptions={
                k: v for k, v in COMPLETE_ASSUMPTIONS.items()
                if k != "employee_social_contributions"
            }
        )
        with pytest.raises(NetIncomeError):
            validate_profile(profile, path="t")

    def test_missing_tax_year_is_rejected(self):
        """A net amount from a superseded year still looks entirely plausible."""
        with pytest.raises(NetIncomeError):
            validate_profile(_profile(tax_year=None), path="t")

    def test_missing_population_is_rejected(self):
        """A median across all graduates is not a median for a first-job graduate."""
        with pytest.raises(NetIncomeError):
            validate_profile(_profile(population=None), path="t")

    def test_missing_period_is_rejected(self):
        """A net figure with no period cannot be compared with a cost figure."""
        with pytest.raises(NetIncomeError):
            validate_profile(_profile(per=None), path="t")

    def test_empty_string_counts_as_missing(self):
        profile = _profile(assumptions={**COMPLETE_ASSUMPTIONS, "marital_status": "   "})
        assert "marital_status" in profile.missing_required()
        with pytest.raises(NetIncomeError):
            validate_profile(profile, path="t")


class TestInventedAssumptionsAreRejected:
    """A value outside the source's own vocabulary means the reader was not
    actually looking at the source."""

    @pytest.mark.parametrize("status", ["partnered", "engaged", "civil union", "complicated"])
    def test_invented_marital_status_is_rejected(self, status):
        with pytest.raises(NetIncomeError):
            validate_profile(
                _profile(assumptions={**COMPLETE_ASSUMPTIONS, "marital_status": status}), path="t"
            )

    @pytest.mark.parametrize("residency", ["temporary", "on a visa", "in transit"])
    def test_invented_residency_is_rejected(self, residency):
        with pytest.raises(NetIncomeError):
            validate_profile(
                _profile(assumptions={**COMPLETE_ASSUMPTIONS, "residency": residency}), path="t"
            )

    @pytest.mark.parametrize(
        "answer",
        ["some of it", "most", "yes", "partly deducted", "varies by the month"],
    )
    def test_vague_social_contributions_are_rejected(self, answer):
        """"Some" is not an answer to a question worth several thousand euros a
        year."""
        with pytest.raises(NetIncomeError):
            validate_profile(
                _profile(
                    assumptions={**COMPLETE_ASSUMPTIONS, "employee_social_contributions": answer}
                ),
                path="t",
            )

    def test_singapores_cpf_answer_is_allowed(self):
        """CPF is a real and large deduction that never reaches the worker, so it
        needs its own answer rather than being forced into included/excluded."""
        validate_profile(
            _profile(
                assumptions={**COMPLETE_ASSUMPTIONS, "employee_social_contributions": "cpf_included_as_saving"}
            ),
            path="sg.career.net_monthly_income",
        )

    def test_both_residencies_may_be_reported(self):
        validate_profile(
            _profile(assumptions={**COMPLETE_ASSUMPTIONS, "residency": "both_reported"}), path="t"
        )


class TestBasisKindIsHonest:
    @pytest.mark.parametrize("kind", ["OFFICIAL", "DERIVED", "ESTIMATE"])
    def test_the_three_honest_routes_are_allowed(self, kind):
        validate_profile(_profile(basis_kind=kind), path="t")

    @pytest.mark.parametrize("kind", ["official", "estimated", "guess", "computed", "STALE"])
    def test_anything_else_is_rejected(self, kind):
        with pytest.raises(NetIncomeError):
            validate_profile(_profile(basis_kind=kind), path="t")


class TestProfilesFromResearchOutput:
    def test_a_full_artifact_profile_parses(self):
        profile = profile_from_raw(
            {
                "assumptions": COMPLETE_ASSUMPTIONS,
                "population": "median take-home, new graduates",
                "tax_year": "2025",
                "currency": "GBP",
                "per": "month",
                "basis_kind": "OFFICIAL",
                "limitations": "excludes London weighting",
            }
        )
        validate_profile(profile, path="gb.career.net_monthly_income")
        assert profile.tax_year == "2025"
        assert "excludes London" in profile.limitations

    def test_it_falls_back_to_as_of_for_the_tax_year(self):
        """Research output usually writes ``as_of``. Treating that as the tax year
        is only safe when the writer meant it that way, so it is the declared
        field that wins and ``as_of`` is the fallback."""
        profile = profile_from_raw({"assumptions": COMPLETE_ASSUMPTIONS, "population": "x", "as_of": "2024"})
        assert profile.tax_year == "2024"

    def test_an_empty_mapping_yields_an_invalid_profile_not_a_crash(self):
        """A missing assumption is a finding to report, not an exception to
        swallow somewhere deeper."""
        profile = profile_from_raw(None)
        assert profile.missing_required()

    def test_a_partial_artifact_reports_exactly_what_is_missing(self):
        profile = profile_from_raw(
            {"assumptions": {"marital_status": "single"}, "population": "all employees"}
        )
        missing = profile.missing_required()
        assert "dependents" in missing
        assert "residency" in missing
        assert "employee_social_contributions" in missing
        assert "tax_year" in missing
        assert "per" in missing
        assert "marital_status" not in missing


class TestNetIncomeAloneDoesNotUnblockBreakEven:
    """The finding that shapes this whole track, pinned as a test.

    Break-even is refused in all 17 countries. The obvious assumption is that
    supplying a net income figure fixes it. It does not, and it is worth being
    explicit about why: ``break_even = total_investment / net_monthly_income``, and
    the denominator being correct changes nothing when the numerator cannot be
    computed. 16 of 17 countries have no researched tuition and 17 of 17 have no
    living costs, so ``total_investment`` refuses and break-even refuses with it.

    These tests exist so that a future change which makes break-even computable
    from a net figure alone has to be a deliberate, visible decision rather than an
    accident of a reordered guard.
    """

    def _net_claim(self):
        from app.services.country_intelligence.provenance import parse_claim

        return parse_claim(
            {
                "value": 2750,
                "currency": "EUR",
                "per": "month",
                "basis": "net",
                "value_status": "OFFICIAL_STATISTICS",
                "source_ids": ["s1"],
                "as_of": "2025",
                "net_income_profile": {
                    "tax_year": "2025",
                    "per": "month",
                    "assumptions": {
                        "marital_status": "single",
                        "dependents": "none",
                        "residency": "resident",
                        "employee_social_contributions": "included",
                        "population": "all employees",
                    },
                },
            },
            path="t",
        )

    def _investment(self, value=None):
        from app.services.country_intelligence.derive import Derivation

        if value is None:
            # What the corpus actually produces today: a refusal, not a number.
            from app.services.country_intelligence.derive import (
                derive_living,
                derive_one_time_total,
                derive_total_investment,
                derive_tuition,
            )

            empty: dict = {}
            return derive_total_investment(
                derive_tuition(empty, "bachelor", 0.0),
                derive_living(empty, "high"),
                derive_one_time_total(empty),
                2,
            )
        return Derivation(
            key="total_investment",
            formula="test fixture",
            value=value,
            currency="EUR",
            per="programme",
        )

    def test_a_valid_net_claim_is_accepted_by_the_provenance_layer(self):
        claim = self._net_claim()
        assert claim.value == 2750
        assert claim.basis == "net"
        assert claim.net_income_profile is not None

    def test_net_figure_plus_missing_costs_still_refuses(self):
        from app.services.country_intelligence.derive import derive_break_even

        result = derive_break_even(self._investment(), self._net_claim())
        assert result.computed is False
        assert result.refusal

    def test_net_figure_plus_real_costs_computes(self):
        """So the guard is refusing for the right reason, not refusing everything.
        60000 / 2750 = 21.8 months."""
        from app.services.country_intelligence.derive import derive_break_even

        result = derive_break_even(self._investment(60000.0), self._net_claim())
        assert result.computed is True
        assert result.value == pytest.approx(21.8, abs=0.05)
        assert result.per == "months"

    def test_gross_still_refuses_even_with_real_costs(self):
        """The gate was not loosened to let the net figures through."""
        from app.services.country_intelligence.derive import REFUSAL_GROSS_INCOME
        from app.services.country_intelligence.derive import derive_break_even
        from app.services.country_intelligence.provenance import parse_claim

        gross = parse_claim(
            {
                "value": 4217,
                "currency": "EUR",
                "per": "month",
                "basis": "gross",
                "value_status": "OFFICIAL_STATISTICS",
                "source_ids": ["s1"],
                "as_of": "2025",
            },
            path="t",
        )
        result = derive_break_even(self._investment(60000.0), gross)
        assert result.computed is False
        assert result.refusal == REFUSAL_GROSS_INCOME


class TestTheErrorMessageSaysWhatToDo:
    def test_it_names_the_missing_keys(self):
        with pytest.raises(NetIncomeError) as caught:
            validate_profile(NetIncomeProfile(), path="de")
        message = str(caught.value)
        for key in REQUIRED_ASSUMPTIONS:
            assert key in message

    def test_it_explains_why_defaulting_is_wrong(self):
        with pytest.raises(NetIncomeError) as caught:
            validate_profile(NetIncomeProfile(), path="de")
        assert "nobody stated" in str(caught.value)

    def test_optional_assumptions_do_not_block(self):
        """Missing jurisdiction is not fatal - a national average can say it is a
        national average - but it is still recorded as worth having."""
        assert "jurisdiction" in OPTIONAL_ASSUMPTIONS
        assert "jurisdiction" not in REQUIRED_ASSUMPTIONS
        validate_profile(_profile(), path="t")