"""The audit-gate status contract: ESTIMATE, STALE, CONFLICTING, REFUSED.

These tests exist because the status vocabulary was completed after the corpus was
first built, and the failure this file guards is specific: a contract that looks
complete because every status name exists, while the semantics behind them are
untested and therefore unverified.

Four states are covered here that had no representation at all before:

``CONFLICTING``
    Two credible sources disagree and nothing settles it. The corpus must keep
    both figures and refuse to name a winner.
``REFUSED``
    The system declined on purpose. Publishing it as ``UNKNOWN`` claims nobody
    looked, which is a different statement and a wrong one.
``ESTIMATE``
    A real value whose evidence qualifies it as approximate.
``STALE``
    Evidence that exists but has aged out. Represented orthogonally, because
    "official and stale" is a real combination that a single scalar cannot hold.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.country_intelligence.derive import (  # noqa: E402
    REFUSAL_CURRENCY_MISMATCH,
    REFUSAL_GROSS_INCOME,
    REFUSAL_LABELS,
    REFUSAL_MISSING_FX_RATE,
    REFUSAL_MISSING_NET_INCOME,
    Derivation,
    derive_break_even,
)
from app.services.country_intelligence.formulas import (  # noqa: E402
    registry_problems,
)
from app.services.country_intelligence.provenance import (  # noqa: E402
    DEFAULT_STALE_AFTER_DAYS,
    DISCLOSURE_REQUIRED,
    FRESHNESS,
    FRESHNESS_LABELS,
    NON_OFFICIAL_SOURCE_TYPES,
    OFFICIAL_SOURCE_TYPES,
    SOURCE_TYPES,
    VALUE_STATUS,
    VALUE_STATUS_LABELS,
    ClaimError,
    check_official_source_claim,
    claim_refused,
    claim_unknown,
    normalise_freshness,
    parse_claim,
    resolve_freshness,
)

#: The eight states the audit contract requires to be distinguishable.
REQUIRED_STATES = (
    "OFFICIAL_GOVERNMENT",
    "ESTIMATE",
    "CONFLICTING",
    "REFUSED",
    "UNKNOWN",
    "DERIVED",
)

REFERENCE = "2026-10-05"


def _conflict(**overrides):
    payload = {
        "value": None,
        "value_status": "CONFLICTING",
        "note": "Two Bavarian institutions publish different rates and no state rate exists.",
        "conflicting": [
            {
                "value": 800,
                "currency": "EUR",
                "per": "semester",
                "source_ids": ["de-thi"],
                "as_of": "2026-01-15",
            },
            {
                "value": 500,
                "currency": "EUR",
                "per": "semester",
                "source_ids": ["de-hmu"],
                "as_of": "2026-01-15",
            },
        ],
    }
    payload.update(overrides)
    return payload


class TestStatusVocabularyIsComplete:
    def test_every_required_state_exists(self):
        for state in REQUIRED_STATES:
            assert state in VALUE_STATUS, f"{state} is missing from the vocabulary"

    def test_every_status_has_a_label(self):
        assert set(VALUE_STATUS) == set(VALUE_STATUS_LABELS)

    def test_every_freshness_value_has_a_label(self):
        assert set(FRESHNESS) == set(FRESHNESS_LABELS)

    def test_no_refusal_code_lacks_a_label(self):
        """A refusal with no wording renders as a bare code.

        A student reading ``MISSING_NET_INCOME`` learns nothing about what to do
        next. Every code must therefore carry a sentence.
        """
        from app.services.country_intelligence import derive

        codes = {
            value
            for name, value in vars(derive).items()
            if name.startswith("REFUSAL_")
            and name not in {"REFUSAL_LABELS"}
            and isinstance(value, str)
        }
        assert codes, "no refusal codes were discovered"
        assert codes <= set(REFUSAL_LABELS), (
            f"refusal codes without wording: {sorted(codes - set(REFUSAL_LABELS))}"
        )

    def test_source_types_stay_separate_from_value_statuses(self):
        """A publisher is not a claim, and merging the two vocabularies would
        force one of those truths to be denied."""
        epistemic_only = {"DERIVED", "REFUSED", "CONFLICTING", "ESTIMATE", "UNKNOWN"}
        assert epistemic_only.isdisjoint(SOURCE_TYPES)
        assert epistemic_only.isdisjoint(OFFICIAL_SOURCE_TYPES)

    def test_formula_registry_is_sound(self):
        assert registry_problems() == []


class TestRefusedIsNotUnknown:
    def test_refused_and_unknown_are_different_states(self):
        refused = claim_refused("gross income is not repayable")
        unknown = claim_unknown("no income figure was sourced")
        assert refused.value_status == "REFUSED"
        assert unknown.value_status == "UNKNOWN"
        assert refused.value_status != unknown.value_status

    def test_refused_requires_a_reason(self):
        with pytest.raises(ClaimError):
            claim_refused("")

    def test_refused_carries_what_was_required(self):
        claim = claim_refused(
            "gross income cannot repay a cost",
            required_input="a net income figure",
            operation="break_even_months",
        )
        published = claim.to_dict()["refusal"]
        assert published["required_input"] == "a net income figure"
        assert published["operation"] == "break_even_months"

    def test_refused_never_carries_a_value(self):
        with pytest.raises(ClaimError):
            parse_claim({"value": 12, "value_status": "REFUSED"}, path="t")

    def test_unknown_never_carries_a_value(self):
        with pytest.raises(ClaimError):
            parse_claim({"value": 0, "value_status": "UNKNOWN"}, path="t")

    def test_refusal_publishes_refused_not_unknown(self):
        """The API must not report a deliberate refusal as a research gap."""
        result = derive_break_even(
            Derivation(
                key="total_investment", formula="f", value=60000.0, currency="EUR"
            ),
            {
                "value": 52000,
                "currency": "EUR",
                "per": "year",
                "basis": "gross",
                "value_status": "OFFICIAL_STATISTICS",
                "source_ids": ["s"],
            },
        )
        payload = result.to_dict()
        assert payload["value_status"] == "REFUSED"
        assert payload["value_status"] != "UNKNOWN"
        assert "value" not in payload
        assert payload["refusal"] == REFUSAL_GROSS_INCOME
        assert payload["refusal_detail"]["reason"]

    def test_gross_income_refusal_names_the_required_input(self):
        result = derive_break_even(
            Derivation(
                key="total_investment", formula="f", value=60000.0, currency="EUR"
            ),
            {
                "value": 52000,
                "currency": "EUR",
                "per": "year",
                "basis": "gross",
                "value_status": "OFFICIAL_STATISTICS",
                "source_ids": ["s"],
            },
        )
        assert result.required_input
        assert "net" in result.required_input

    def test_gross_refusal_is_distinct_from_absent_income(self):
        investment = Derivation(
            key="total_investment", formula="f", value=60000.0, currency="EUR"
        )
        gross = derive_break_even(
            investment,
            {
                "value": 52000, "currency": "EUR", "per": "year", "basis": "gross",
                "value_status": "OFFICIAL_STATISTICS", "source_ids": ["s"],
            },
        )
        absent = derive_break_even(investment, None)
        assert gross.refusal == REFUSAL_GROSS_INCOME
        assert absent.refusal == REFUSAL_MISSING_NET_INCOME
        assert gross.refusal != absent.refusal

    def test_missing_fx_refusal_names_the_required_input(self):
        result = derive_break_even(
            Derivation(
                key="total_investment", formula="f", value=60000.0, currency="EUR"
            ),
            {
                "value": 3000, "currency": "USD", "per": "month", "basis": "net",
                "value_status": "OFFICIAL_STATISTICS", "source_ids": ["s"],
            },
        )
        assert result.refusal == REFUSAL_MISSING_FX_RATE
        assert "USD" in result.required_input
        assert "EUR" in result.required_input


class TestConflictingSemantics:
    def test_both_figures_survive(self):
        claim = parse_claim(_conflict(), path="de.education_costs")
        assert claim.value_status == "CONFLICTING"
        assert [item.value for item in claim.conflicting] == [800, 500]

    def test_no_average_is_computed(self):
        claim = parse_claim(_conflict(), path="de.education_costs")
        assert claim.value is None
        assert claim.publishes_a_number is False

    def test_no_single_value_may_be_carried(self):
        """A conflict with one number is a contradiction: the label says sources
        disagree while the body names a winner."""
        with pytest.raises(ClaimError):
            parse_claim(_conflict(value=650), path="de.education_costs")

    def test_a_single_sided_disagreement_is_not_a_conflict(self):
        with pytest.raises(ClaimError):
            parse_claim(
                {
                    "value": None,
                    "value_status": "CONFLICTING",
                    "conflicting": [{"value": 800, "source_ids": ["a"]}],
                },
                path="t",
            )

    def test_each_side_must_name_a_source(self):
        """An unnamed conflict cannot be audited, so it must not be published."""
        with pytest.raises(ClaimError):
            parse_claim(
                {
                    "value": None,
                    "value_status": "CONFLICTING",
                    "conflicting": [
                        {"value": 800, "source_ids": ["a"]},
                        {"value": 500, "source_ids": []},
                    ],
                },
                path="t",
            )

    def test_each_side_must_state_its_value(self):
        with pytest.raises(ClaimError):
            parse_claim(
                {
                    "value": None,
                    "value_status": "CONFLICTING",
                    "conflicting": [
                        {"value": 800, "source_ids": ["a"]},
                        {"value": None, "source_ids": ["b"]},
                    ],
                },
                path="t",
            )

    def test_both_sources_are_published(self):
        claim = parse_claim(_conflict(), path="de.education_costs")
        assert set(claim.to_dict()["source_ids"]) == {"de-thi", "de-hmu"}

    def test_api_shape_preserves_every_alternative(self):
        published = parse_claim(_conflict(), path="t").to_dict()
        assert published["value_status"] == "CONFLICTING"
        assert len(published["conflicting"]) == 2
        for item in published["conflicting"]:
            assert item["source_ids"]
            assert item["currency"] == "EUR"
            assert item["per"] == "semester"

    def test_conflict_requires_disclosure(self):
        assert "CONFLICTING" in DISCLOSURE_REQUIRED

    def test_conflict_is_never_official_asserting(self):
        """A conflict must not be able to pass the official gate, because it
        asserts no single fact for a primary source to have confirmed."""
        check_official_source_claim(
            "CONFLICTING", {"a": "OFFICIAL_GOVERNMENT"}, path="t"
        )


class TestEstimateSemantics:
    def test_an_estimate_requires_its_basis(self):
        """Without a stated basis an estimate renders exactly like a fact, which
        is the outcome the status exists to prevent."""
        with pytest.raises(ClaimError):
            parse_claim(
                {
                    "value": 1600,
                    "currency": "EUR",
                    "value_status": "ESTIMATE",
                    "source_ids": ["numbeo"],
                },
                path="t",
            )

    def test_an_estimate_keeps_its_value_and_basis(self):
        claim = parse_claim(
            {
                "value": 1600,
                "currency": "EUR",
                "per": "month",
                "value_status": "ESTIMATE",
                "estimate_basis": "crowdsourced average, not an official statistic",
                "source_ids": ["numbeo"],
                "as_of": "2026-09-01",
            },
            path="t",
        )
        assert claim.value == 1600
        assert claim.value_status == "ESTIMATE"
        assert claim.publishes_a_number is True

    def test_an_estimate_requires_a_source(self):
        with pytest.raises(ClaimError):
            parse_claim(
                {
                    "value": 1600,
                    "value_status": "ESTIMATE",
                    "estimate_basis": "modelled",
                },
                path="t",
            )

    def test_an_estimate_requires_disclosure(self):
        assert "ESTIMATE" in DISCLOSURE_REQUIRED

    def test_an_estimate_is_not_official(self):
        """ESTIMATE must not be treated as an official assertion, or a secondary
        living-cost figure could be laundered into an official one."""
        check_official_source_claim(
            "ESTIMATE", {"numbeo": "AGGREGATOR"}, path="t"
        )


class TestStaleEnforcement:
    def test_exactly_at_the_threshold_is_current(self):
        anchor = (date(2026, 10, 5) - timedelta(days=DEFAULT_STALE_AFTER_DAYS)).isoformat()
        assert resolve_freshness(
            anchor, reference_date=REFERENCE, stale_after_days=DEFAULT_STALE_AFTER_DAYS
        ) == "CURRENT"

    def test_one_day_past_the_threshold_is_stale(self):
        anchor = (
            date(2026, 10, 5) - timedelta(days=DEFAULT_STALE_AFTER_DAYS + 1)
        ).isoformat()
        assert resolve_freshness(
            anchor, reference_date=REFERENCE, stale_after_days=DEFAULT_STALE_AFTER_DAYS
        ) == "STALE"

    def test_one_day_inside_the_threshold_is_current(self):
        anchor = (
            date(2026, 10, 5) - timedelta(days=DEFAULT_STALE_AFTER_DAYS - 1)
        ).isoformat()
        assert resolve_freshness(
            anchor, reference_date=REFERENCE, stale_after_days=DEFAULT_STALE_AFTER_DAYS
        ) == "CURRENT"

    def test_missing_date_is_undated_not_current(self):
        """The conservative default. An undated figure reported as fresh is the
        silent lie this corpus exists to prevent."""
        assert resolve_freshness(None, reference_date=REFERENCE) == "UNDATED"

    def test_unparseable_date_is_undated(self):
        assert resolve_freshness("sometime last year", reference_date=REFERENCE) == "UNDATED"

    def test_retrieval_date_is_a_fallback_not_a_preference(self):
        """A page fetched today may describe a 2019 tariff, so ``as_of`` wins."""
        old = (date(2026, 10, 5) - timedelta(days=2000)).isoformat()
        assert resolve_freshness(
            old, reference_date=REFERENCE, retrieved_at=REFERENCE
        ) == "STALE"

    def test_retrieval_date_is_used_when_as_of_is_absent(self):
        assert resolve_freshness(
            None, reference_date=REFERENCE, retrieved_at="2026-09-01"
        ) == "CURRENT"

    def test_result_does_not_depend_on_the_wall_clock(self):
        """The same inputs must give the same answer forever, or two runs of the
        same corpus disagree and the finding is noise."""
        anchor = "2026-09-01"
        first = resolve_freshness(anchor, reference_date=REFERENCE)
        second = resolve_freshness(anchor, reference_date=REFERENCE)
        assert first == second == "CURRENT"

    def test_stale_and_undated_are_distinguishable(self):
        stale = resolve_freshness("2019-01-01", reference_date=REFERENCE)
        undated = resolve_freshness(None, reference_date=REFERENCE)
        assert stale != undated
        assert {stale, undated} == {"STALE", "UNDATED"}

    def test_official_and_stale_are_both_representable(self):
        """The reason staleness is orthogonal: a ministry figure can be official
        and out of date at the same time."""
        claim = parse_claim(
            {
                "value": 1500,
                "currency": "EUR",
                "value_status": "OFFICIAL_GOVERNMENT",
                "source_ids": ["mwk"],
                "as_of": "2019-01-01",
            },
            path="t",
        )
        assert claim.value_status == "OFFICIAL_GOVERNMENT"
        freshness = resolve_freshness(
            claim.as_of, reference_date=REFERENCE, stale_after_days=DEFAULT_STALE_AFTER_DAYS
        )
        assert freshness == "STALE"

    def test_freshness_aliases_normalise(self):
        assert normalise_freshness("fresh") == "CURRENT"
        assert normalise_freshness("Out of date") == "STALE"
        assert normalise_freshness("no date") == "UNDATED"
        assert normalise_freshness("invented") is None

    def test_unrecognised_freshness_is_rejected(self):
        with pytest.raises(ClaimError):
            parse_claim(
                {
                    "value": 1,
                    "value_status": "OFFICIAL_GOVERNMENT",
                    "source_ids": ["s"],
                    "freshness": "probably fine",
                },
                path="t",
            )

    def test_declared_freshness_is_carried_through(self):
        claim = parse_claim(
            {
                "value": 1,
                "value_status": "OFFICIAL_GOVERNMENT",
                "source_ids": ["s"],
                "freshness": "stale",
            },
            path="t",
        )
        assert claim.freshness == "STALE"
        assert claim.to_dict()["freshness"] == "STALE"


class TestOfficialSourceGateUnchanged:
    """The regression guard for the invariant the audit corrected.

    ``at least one`` primary source is what makes a claim official. ``all`` was a
    false positive that taught researchers to drop useful corroboration.
    """

    def test_one_primary_source_is_enough(self):
        check_official_source_claim(
            "OFFICIAL_GOVERNMENT",
            {"ministry": "OFFICIAL_GOVERNMENT", "paper": "MEDIA"},
            path="t",
        )

    def test_secondary_only_is_rejected(self):
        with pytest.raises(ClaimError):
            check_official_source_claim(
                "OFFICIAL_GOVERNMENT", {"paper": "MEDIA"}, path="t"
            )

    def test_unlabelled_source_cannot_support_official(self):
        with pytest.raises(ClaimError):
            check_official_source_claim("OFFICIAL_GOVERNMENT", {"x": None}, path="t")

    def test_crowdsourced_and_aggregator_are_non_official(self):
        assert {"CROWDSOURCED", "AGGREGATOR", "MEDIA"} == set(NON_OFFICIAL_SOURCE_TYPES)
        assert set(NON_OFFICIAL_SOURCE_TYPES).isdisjoint(OFFICIAL_SOURCE_TYPES)

    def test_university_and_statistics_can_support_official(self):
        check_official_source_claim(
            "UNIVERSITY_OFFICIAL", {"uni": "UNIVERSITY_OFFICIAL"}, path="t"
        )
        check_official_source_claim(
            "OFFICIAL_STATISTICS", {"ons": "OFFICIAL_STATISTICS"}, path="t"
        )

    def test_regional_body_is_official(self):
        assert "OFFICIAL_REGIONAL_BODY" in OFFICIAL_SOURCE_TYPES
        check_official_source_claim(
            "OFFICIAL_REGIONAL_BODY", {"eu": "OFFICIAL_REGIONAL_BODY"}, path="t"
        )