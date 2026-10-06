"""The net-income contract as ingestion enforces it.

The reference-profile tests in ``test_country_intelligence_net_income_contract.py``
cover the profile object. These cover the two things that actually protect the
break-even number, and both are failures that are silent in production:

1. **A gross figure must never occupy the net slot.** In most European countries
   the gross-to-net gap is around 40%, so a gross salary used as take-home pay
   roughly halves the months to repay. The number looks entirely reasonable.
2. **A net figure without its circumstances must not ship.** Not a rejected
   artifact - a demoted claim and a published gap, so the evidence survives and
   the defect is visible.

Both are tested through the real ingester, because testing the validator alone
would not catch a caller that skips it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_spec = importlib.util.spec_from_file_location(
    "ingest_country_intelligence", BACKEND / "scripts" / "ingest_country_intelligence.py"
)
assert _spec and _spec.loader
ingest = importlib.util.module_from_spec(_spec)
sys.modules["ingest_country_intelligence"] = ingest
_spec.loader.exec_module(ingest)

COMPLETE_ASSUMPTIONS = {
    "marital_status": "single",
    "dependents": "none",
    "residency": "resident",
    "employee_social_contributions": "included",
    "population": "median take-home pay, all employees",
}


def _artifact(**overrides):
    artifact = {
        "country": "DE",
        "topic": "net_monthly_income",
        "source_id": "de-statistik-net-001",
        "source_url": "https://www.destatis.de/DE/Themen/Gesellschaft-Umwelt/Personen-Einkommen.html",
        "source_type": "OFFICIAL_STATISTICS",
        "publisher": "Statistisches Bundesamt",
        "retrieved_at": "2026-10-05",
        "as_of": "2025",
        "raw_extract": "Bruttomonatslohn 4.217 EUR, Nettoeinkommen nach Steuern und Sozialabgaben.",
        "claims": [
            {
                "claim_id": "de-net-monthly-001",
                "value": 2750,
                "unit": "EUR per month",
                "as_of": "2025",
                "statement": "Median take-home pay, all employees, 2025.",
            }
        ],
        "assumptions": dict(COMPLETE_ASSUMPTIONS),
        # Rule 3: a derived net must cite a gross somebody else published. Without
        # this the claim is a tax-model evaluation at a chosen salary, which is a
        # fact about the tax system rather than about the country.
        #
        # Shaped like a real derivation, so the ingester recognises it as one: a
        # fixture with an empty dict would look like a directly published net.
        "derivation": {
            "method": "DERIVED from published tax parameters",
            "gross_input_eur_per_month": 2750,
            "gross_input_sourced": True,
            "gross_input_note": "Median gross published by the national statistics office.",
        },
    }
    artifact.update(overrides)
    return artifact


def _ingest(tmp_path, artifact):
    raw = tmp_path / "research_raw" / "DE"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "001_net.json").write_text(json.dumps(artifact), encoding="utf-8")
    return ingest.ingest_country_from_raw("DE", corpus_dir=tmp_path, raw_dir=raw)


def _net_claim(tmp_path):
    """The claim filed under the net-income topic.

    Matched by prefix because the ingester appends the period to the canonical
    path (``career.net_monthly_income.month``), and the test cares about the slot,
    not about how the period is spelled in the key.
    """
    from app.services.country_intelligence.corpus import load_corpus

    corpus = load_corpus(tmp_path)
    record = next(r for r in corpus.records if r.iso2 == "DE")
    matches = [
        claim
        for key, claim in record.claims.items()
        if key.startswith("career.net_monthly_income")
    ]
    return matches[0] if matches else None


class TestAValidNetFigureIsPublished:
    def test_it_ingests(self, tmp_path):
        assert _ingest(tmp_path, _artifact()).written

    def test_the_value_survives(self, tmp_path):
        _ingest(tmp_path, _artifact())
        claim = _net_claim(tmp_path)
        assert claim is not None
        assert claim.value == 2750
        assert claim.currency == "EUR"
        assert claim.per == "month"

    def test_it_is_marked_net(self, tmp_path):
        """The basis travels with the value, so a later reader cannot mistake it
        for gross."""
        _ingest(tmp_path, _artifact())
        assert _net_claim(tmp_path).basis == "net"

    def test_it_carries_its_profile(self, tmp_path):
        _ingest(tmp_path, _artifact())
        published = _net_claim(tmp_path).to_dict()["net_income_profile"]
        assert published["tax_year"] == "2025"
        assert published["per"] == "month"
        assert published["assumptions"]["marital_status"] == "single"

    def test_the_profile_is_not_a_nested_claim(self, tmp_path):
        """The walker must skip it, or each assumption dict is validated as a
        standalone claim - the same defect that made every conflict unpublishable."""
        assert _ingest(tmp_path, _artifact()).written
        from app.services.country_intelligence.corpus import load_corpus

        corpus = load_corpus(tmp_path)
        assert not any("net_income_profile." in p.reason for p in corpus.problems)


class TestGrossCanNeverOccupyTheNetSlot:
    """The failure this prevents is silent: a gross salary used as take-home pay
    produces a plausible, confident, roughly 2x-too-fast break-even."""

    def test_a_gross_statement_is_demoted(self, tmp_path):
        artifact = _artifact()
        artifact["claims"][0]["statement"] = (
            "Median gross monthly earnings before taxes and social contributions."
        )
        _ingest(tmp_path, artifact)
        claim = _net_claim(tmp_path)
        assert claim.value is None
        assert claim.value_status == "UNKNOWN"

    def test_the_demotion_says_why(self, tmp_path):
        artifact = _artifact()
        artifact["claims"][0]["statement"] = "Gross monthly earnings before tax."
        _ingest(tmp_path, artifact)
        note = _net_claim(tmp_path).note
        assert "gross" in note.lower()
        assert "take-home" in note.lower()

    def test_a_gross_basis_is_demoted(self, tmp_path):
        _ingest(tmp_path, _artifact(basis="gross"))
        assert _net_claim(tmp_path).value is None

    def test_the_german_word_for_gross_is_caught(self, tmp_path):
        artifact = _artifact()
        artifact["claims"][0]["statement"] = "Bruttomonatslohn 4.217 EUR."
        _ingest(tmp_path, artifact)
        assert _net_claim(tmp_path).value is None

    def test_a_gross_figure_is_not_thrown_away(self, tmp_path):
        """It is filed as a gap, not deleted: the evidence is real even when its
        placement is wrong, and a reviewer needs to see it to fix the mapping."""
        artifact = _artifact()
        artifact["claims"][0]["statement"] = "Gross monthly earnings before tax."
        report = _ingest(tmp_path, artifact)
        assert report.income_gaps
        assert "gross" in report.income_gaps[0]["reason"].lower()

    def test_gross_on_the_gross_topic_is_fine(self, tmp_path):
        """The rule is about the slot, not a blanket ban. A gross figure filed as
        gross is correct data and must survive."""
        artifact = _artifact(
            topic="gross_monthly_income",
            claims=[
                {
                    "claim_id": "de-gross-001",
                    "value": 4217,
                    "unit": "EUR per month",
                    "as_of": "2025",
                    "statement": "Median gross monthly earnings.",
                }
            ],
        )
        _ingest(tmp_path, artifact)
        from app.services.country_intelligence.corpus import load_corpus

        record = next(r for r in load_corpus(tmp_path).records if r.iso2 == "DE")
        gross = [
            claim
            for key, claim in record.claims.items()
            if key.startswith("career.average_starting_salary.gross_monthly")
        ]
        assert gross, "a gross figure filed on the gross topic must survive"
        assert gross[0].value == 4217
        assert not [
            key for key in record.claims if key.startswith("career.net_monthly_income")
        ]


class TestANetFigureWithoutItsCircumstancesIsDemoted:
    @pytest.mark.parametrize("drop", sorted(COMPLETE_ASSUMPTIONS))
    def test_each_missing_assumption_demotes_the_claim(self, tmp_path, drop):
        artifact = _artifact()
        artifact["assumptions"].pop(drop, None)
        _ingest(tmp_path, artifact)
        claim = _net_claim(tmp_path)
        assert claim.value is None
        assert claim.value_status == "UNKNOWN"

    def test_the_demotion_names_what_is_missing(self, tmp_path):
        artifact = _artifact()
        artifact["assumptions"].pop("marital_status", None)
        _ingest(tmp_path, artifact)
        assert "marital_status" in _net_claim(tmp_path).note

    def test_an_empty_assumptions_block_demotes(self, tmp_path):
        _ingest(tmp_path, _artifact(assumptions={}))
        assert _net_claim(tmp_path).value is None

    def test_a_secondary_estimate_is_labelled_an_estimate(self, tmp_path):
        """Not official, whatever the artifact's own source_type claims."""
        _ingest(tmp_path, _artifact(estimate=True))
        claim = _net_claim(tmp_path)
        assert claim.value == 2750
        assert claim.value_status == "ESTIMATE"
        assert claim.estimate_basis

    def test_an_official_figure_keeps_its_official_status(self, tmp_path):
        _ingest(tmp_path, _artifact())
        assert _net_claim(tmp_path).value_status == "OFFICIAL_STATISTICS"


class TestADerivedNetNeedsASourcedGross:
    """The rule that emerged from the real research.

    Four countries came back with a tax model applied to a gross the researcher
    chose: EUR 4,000 for Ireland, EUR 2,000 for Italy, EUR 3,000 for the
    Netherlands, and Japan's NTA worked example at roughly twice a graduate
    salary. Every one of those is correct arithmetic on real official tax
    parameters - and not one of them is a fact about what someone in that country
    takes home. Publishing them would have produced four confident, plausible,
    entirely invented country income figures.

    The tax arithmetic is the valuable part and stays archived. The conclusion is
    refused, with the reason and the missing input named.
    """

    def test_an_unsourced_gross_is_refused(self, tmp_path):
        artifact = _artifact(derivation={"method": "tax model", "gross_input_eur_per_month": 4000, "gross_input_note": "A salary I chose myself."})
        _ingest(tmp_path, artifact)
        claim = _net_claim(tmp_path)
        assert claim.value is None
        assert claim.value_status == "REFUSED"

    def test_the_refusal_says_why(self, tmp_path):
        artifact = _artifact(derivation={"method": "tax model", "gross_input_eur_per_month": 4000, "gross_input_note": "A salary I chose myself."})
        _ingest(tmp_path, artifact)
        note = _net_claim(tmp_path).note
        assert "tax-model evaluation" in note
        assert "not an observed net income" in note

    def test_the_refusal_names_the_missing_input(self, tmp_path):
        _ingest(tmp_path, _artifact(derivation={"method": "tax model", "gross_input_eur_per_month": 3000}))
        refusal = _net_claim(tmp_path).to_dict()["refusal"]
        assert "gross" in refusal["reason"].lower()
        assert "gross salary" in refusal["required_input"]

    def test_the_researchers_own_words_are_quoted_back(self, tmp_path):
        """If the artifact explained where the gross came from, that explanation
        belongs in the refusal. It is the most useful part for a reviewer."""
        artifact = _artifact(
            derivation={
                "method": "tax model",
                "gross_input_eur_per_month": 2000,
                "gross_input_note": "EUR 2,000 is NOT a published graduate salary.",
            }
        )
        _ingest(tmp_path, artifact)
        note = _net_claim(tmp_path).to_dict()["refusal"]["reason"]
        assert "EUR 2,000 is NOT a published" in note

    def test_a_sourced_gross_is_accepted(self, tmp_path):
        _ingest(tmp_path, _artifact())
        assert _net_claim(tmp_path).value == 2750

    def test_the_gap_is_published(self, tmp_path):
        report = _ingest(tmp_path, _artifact(derivation={"method": "tax model", "gross_input_eur_per_month": 3000}))
        assert any(
            "tax-model evaluation" in str(gap.get("reason"))
            for gap in report.income_gaps
        ), report.income_gaps


class TestRebuildsAreIdempotent:
    def test_the_demoted_claim_does_not_reaccumulate(self, tmp_path):
        """A rebuild reads the previous output, so an unguarded annotation grows
        without bound."""
        raw = tmp_path / "research_raw" / "DE"
        for _ in range(3):
            _ingest(tmp_path, _artifact())
        claim = _net_claim(tmp_path)
        assert claim.note.count("gross") <= 1
        assert claim.note.count("demoted") <= 1

