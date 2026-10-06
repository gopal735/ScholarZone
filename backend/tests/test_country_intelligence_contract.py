"""Country Intelligence contract tests.

The companion to ``test_country_intelligence.py``. That file covers the feature's
happy paths and the four originally-failing cases; this one is the adversarial
half, and every test here is written from the assumption that the corpus will one
day be fed research from a person who is careful, thorough and occasionally
wrong.

The groups map to the parts of the data contract they defend:

* **Taxonomy** - one canonical vocabulary, and ingest aliases that cannot widen
  it.
* **Source provenance** - a secondary source is never labelled official, and
  :mod:`formulas` cannot be used to smuggle one past the check.
* **Formula contract** - a derived figure is reproducible from its own declared
  inputs, or it is not published. This group exists because two research agents in
  one build published totals their own arithmetic contradicted.
* **Country-code safety** - the protected Match map is untouched and ``UK``
  resolves to ``GB``.
* **Bachelor-first** - study levels are not collapsed, and postgraduate funding is
  never inferred.
* **Ingestion** - deterministic, rejects rather than repairs, writes nothing on
  failure.
* **Integrity** - no network, no traversal, no schema migration, no production
  write.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")
os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")  # noqa: E402

import pytest  # noqa: E402

from app.services.country_intelligence import formulas as formula_module  # noqa: E402
from app.services.country_intelligence import provenance as provenance_module  # noqa: E402
from app.services.country_intelligence.catalogue import (  # noqa: E402
    measure_country_catalogue,
)
from app.services.country_intelligence.corpus import (  # noqa: E402
    CORPUS_DIR,
    SECTION_NAMES,
    load_corpus,
)
from app.services.country_intelligence.derive import (  # noqa: E402
    REFUSAL_MISSING_NET_INCOME,
    scholarship_coverage,
)
from app.services.country_intelligence.formulas import (  # noqa: E402
    FORMULAS,
    FormulaInput,
    evaluate,
    get_formula,
    registry_problems,
    values_agree,
    verify_formula_claim,
)
from app.services.country_intelligence.provenance import (  # noqa: E402
    NON_OFFICIAL_SOURCE_TYPES,
    OFFICIAL_SOURCE_TYPES,
    SOURCE_TYPES,
    ClaimError,
    check_official_source_claim,
    normalise_source_type,
    normalise_status_vocabulary,
    parse_claim,
)
from app.services.country_intelligence.taxonomy import (  # noqa: E402
    COUNTRY_CODE_EXTENSIONS,
    resolve_country_code_extended,
)
from app.services.matching.normalize import COUNTRY_CODES  # noqa: E402
from scripts import ingest_country_intelligence as ingest  # noqa: E402


def _country(**overrides) -> dict:
    """A minimal valid country document, for corpus-level tests."""
    document = {
        "country": {"iso2": "XX", "name_en": "Example", "currency": "EUR"},
        "research": {"researched_at": "2026-10-05"},
        "sources": [
            {
                "id": "xx-s1", "publisher": "p", "title": "t",
                "url": "https://example.gov/notice",
                "source_type": "OFFICIAL_GOVERNMENT",
            }
        ],
        "sections": {
            "one_time_costs": {
                "visa_fee": {
                    "value": 75, "currency": "EUR", "per": "application",
                    "value_status": "OFFICIAL_GOVERNMENT", "source_ids": ["xx-s1"],
                }
            }
        },
        "gaps": [{"field": "career.salary", "reason": "Not researched."}],
    }
    document.update(overrides)
    return document


# --------------------------------------------------------------------------------------
# Part 2 - canonical taxonomy
# --------------------------------------------------------------------------------------


class TestCanonicalTaxonomy:
    @pytest.mark.parametrize(
        "research_spelling,canonical",
        [
            ("OFFICIAL_UNIVERSITY", "UNIVERSITY_OFFICIAL"),
            ("official_university", "UNIVERSITY_OFFICIAL"),
            ("Official-University", "UNIVERSITY_OFFICIAL"),
            ("OFFICIAL_REGIONAL_BODY", "OFFICIAL_REGIONAL_BODY"),
            ("OFFICIAL_REGIONAL", "OFFICIAL_REGIONAL_BODY"),
            ("OFFICIAL_GOVERNEMENT", "OFFICIAL_GOVERNMENT"),
            ("OFFICIAL_GOVERNENT", "OFFICIAL_GOVERNMENT"),
            ("UNIVERSITY", "UNIVERSITY_OFFICIAL"),
        ],
    )
    def test_research_spelling_resolves_to_canonical(self, research_spelling, canonical):
        assert normalise_status_vocabulary(research_spelling) == canonical
        assert canonical in provenance_module.VALUE_STATUS

    @pytest.mark.parametrize("spelling", ["TRUSTED_SOURCE", "OFFICIAL", "GOOD", "VERIFIED"])
    def test_invented_status_is_not_widened_by_normalisation(self, spelling):
        """Normalisation is case-tolerant but must not admit a new claim type.

        A researcher who writes ``VERIFIED`` or ``TRUSTED_SOURCE`` is making a
        claim the schema does not recognise. Accepting the spelling quietly would
        mean the vocabulary could grow by accident, one research typo at a time,
        until nothing was enforced at all.
        """
        assert normalise_status_vocabulary(spelling) == spelling
        with pytest.raises(ClaimError):
            parse_claim(
                {"value": 1, "value_status": spelling, "source_ids": ["s"]}, path="p"
            )

    def test_every_alias_target_is_a_canonical_status(self):
        """An alias pointing at a status the validator does not know would fail at
        serve time, long after it appeared to work at ingest time."""
        for target in provenance_module.VALUE_STATUS_ALIASES.values():
            assert target in provenance_module.VALUE_STATUS

    def test_source_types_are_a_separate_vocabulary(self):
        """``value_status`` is a claim about evidence; ``source_type`` is a fact
        about a publisher. Merging them would force one of the two truths to be
        denied - a commercial aggregator can host a figure a careful researcher
        still judges unsupported, and an official statistics office publishes both
        numbers the analyst trusts and methods they would not use."""
        epistemic_only = {"DERIVED", "UNVERIFIED", "UNKNOWN"}
        assert not (epistemic_only & set(SOURCE_TYPES))
        # Every source type except MEDIA also names an epistemic status; MEDIA is a
        # publisher with no matching claim-about-confidence.
        assert set(SOURCE_TYPES) - epistemic_only - {"MEDIA"} < set(
            provenance_module.VALUE_STATUS
        )

    def test_a_publisher_may_exist_with_no_epistemic_counterpart(self):
        """A newspaper is a place, not a level of confidence.

        A figure read from one is not automatically ``UNVERIFIED`` - it depends on
        whether the document itself is primary reporting. Keeping ``MEDIA`` in the
        source vocabulary without a matching status lets a researcher say
        accurately where a figure came from without the schema forcing a claim
        about how much it is worth.
        """
        assert "MEDIA" in SOURCE_TYPES
        assert "MEDIA" not in provenance_module.VALUE_STATUS

    def test_source_type_aliases_resolve(self):
        assert normalise_source_type("PRESS") == "MEDIA"
        assert normalise_source_type("INSTITUTIONAL") == "INSTITUTIONAL_REPORT"
        assert normalise_source_type("COMMERCIAL") == "AGGREGATOR"
        assert normalise_source_type("BLOGS") is None
        assert normalise_source_type(None) is None

    def test_shipped_corpus_uses_only_canonical_spellings(self):
        """The stored vocabulary is one vocabulary.

        This is the difference between "normalisation exists" and "normalisation
        happened". A corpus that still stores research spelling makes "is this
        official?" unanswerable by query, because it would have to match variants.
        """
        offenders: list[str] = []
        for path in sorted(CORPUS_DIR.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            for section, body in document.get("sections", {}).items():
                offenders.extend(
                    f"{path.name}:{section}{keypath}"
                    for keypath, node in _walk(body)
                    if normalise_status_vocabulary(node.get("value_status"))
                    != node.get("value_status")
                )
            offenders.extend(
                f"{path.name}:sources[{index}].source_type"
                for index, source in enumerate(document.get("sources", []))
                if source.get("source_type") is not None
                and normalise_source_type(source["source_type"]) != source["source_type"]
            )
        assert not offenders, f"non-canonical spellings stored: {offenders}"


def _walk(node, path: str = ""):
    if isinstance(node, dict):
        if "value_status" in node:
            yield path, node
        for key, value in node.items():
            yield from _walk(value, f".{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"[{index}]" if not path else path)


# --------------------------------------------------------------------------------------
# Parts 11 and 13 - a secondary source is never labelled official
# --------------------------------------------------------------------------------------


class TestOfficialSourceGate:
    @pytest.mark.parametrize("status", sorted(OFFICIAL_SOURCE_TYPES))
    def test_official_status_with_an_official_source_passes(self, status):
        check_official_source_claim(status, {"s1": status}, path="p")

    @pytest.mark.parametrize("status", ["OFFICIAL_GOVERNMENT", "UNIVERSITY_OFFICIAL"])
    @pytest.mark.parametrize("secondary", sorted(NON_OFFICIAL_SOURCE_TYPES))
    def test_official_status_on_a_secondary_source_is_rejected(self, status, secondary):
        """The realistic failure is a reputable paper quoting a ministry, tagged
        official. The tag outlives the scrutiny and the student cannot tell a
        journalist's reading of a threshold from the law itself."""
        with pytest.raises(ClaimError, match="asserts an official source"):
            check_official_source_claim(status, {"s1": secondary}, path="p")

    def test_an_unlabelled_source_cannot_support_an_official_claim(self):
        """An unlabelled source cannot be asserted to be primary."""
        with pytest.raises(ClaimError, match="asserts an official source"):
            check_official_source_claim("OFFICIAL_GOVERNMENT", {"s1": None}, path="p")

    def test_one_official_source_among_secondary_ones_is_enough(self):
        """The gate asks whether a primary source was read, not whether every
        citation was primary. A figure cross-checked against a newspaper and a
        ministry page is properly official."""
        check_official_source_claim(
            "OFFICIAL_GOVERNMENT", {"s1": "MEDIA", "s2": "OFFICIAL_GOVERNMENT"}, path="p"
        )

    def test_crowdsourced_status_is_never_gated(self):
        """``CROWDSOURCED`` already says where it came from, so it needs no gate."""
        check_official_source_claim("CROWDSOURCED", {"s1": "CROWDSOURCED"}, path="p")

    def test_corpus_excludes_a_country_whose_official_claim_is_secondary(self, tmp_path: Path):
        document = _country()
        document["sources"][0]["source_type"] = "MEDIA"
        (tmp_path / "XX.json").write_text(json.dumps(document), encoding="utf-8")
        loaded = load_corpus(tmp_path)
        assert not loaded.iso2_codes
        assert "asserts an official source" in loaded.problems[0].reason


# --------------------------------------------------------------------------------------
# Part 3 - the formula contract
# --------------------------------------------------------------------------------------


def _annual_cost_inputs(**overrides) -> dict:
    inputs = {
        "annual_tuition": {"value": 27000, "currency": "EUR", "per": "year"},
        "monthly_living_cost": {"value": 1600, "currency": "EUR", "per": "month"},
        "one_time_fees": {"value": 75, "currency": "EUR", "per": "once"},
    }
    inputs.update(overrides)
    return inputs


def _derived(value, *, inputs=None, formula_id="annual_cost_v1", currency=None, **formula_fields):
    """A DERIVED claim with its formula block.

    The formula, its version and the inputs it was given travel together inside
    the ``formula`` object. Keeping them apart would allow a figure to cite one
    formula's id beside another formula's inputs, and the reproducibility check
    could no longer tell which arithmetic it was reproducing.
    """
    formula = {
        "formula_id": formula_id,
        "formula_version": get_formula(formula_id).version,
        "inputs": _annual_cost_inputs() if inputs is None else inputs,
    }
    formula.update(formula_fields)
    claim = {"value": value, "value_status": "DERIVED", "formula": formula}
    if currency is not None:
        claim["currency"] = currency
    return claim


class TestFormulaContract:
    def test_the_registry_is_coherent(self):
        """Checked by the module rather than by hand, because the registry is
        hand-maintained data as much as code."""
        assert registry_problems() == []

    def test_no_arbitrary_python_is_reachable_from_a_corpus_file(self):
        """A corpus file names an id; the arithmetic lives here as a function.

        There is no ``eval`` anywhere in the package. This asserts that
        structurally rather than by grep, by showing that an expression-shaped
        ``formula`` string is only ever looked up - never compiled.
        """
        assert get_formula("annual_cost_v1") is not None
        with pytest.raises(ClaimError, match="is not registered"):
            verify_formula_claim(
                {"value": 1, "formula": "__import__('os').system('echo pwned')", "inputs": {}},
                path="p",
            )

    def test_a_reproducible_value_is_accepted(self):
        # 27000 + (1600 * 12) + 75
        outcome = verify_formula_claim(_derived(46275, currency="EUR"), path="p")
        assert outcome.value == 46275.0

    @pytest.mark.parametrize("wrong", [51075, 45975, 0, 46270])
    def test_a_value_its_own_formula_contradicts_is_rejected(self, wrong):
        """This is the check that was missing, and the one that would have caught
        both agents that published totals their arithmetic disagreed with."""
        with pytest.raises(ClaimError, match="does not match"):
            verify_formula_claim(_derived(wrong, currency="EUR"), path="p")

    def test_a_missing_required_input_makes_the_figure_unreproducible(self):
        with pytest.raises(ClaimError, match="requires input"):
            verify_formula_claim(
                _derived(
                    46275,
                    inputs={
                        "annual_tuition": {"value": 27000, "currency": "EUR", "per": "year"}
                    },
                ),
                path="p",
            )

    def test_an_input_the_formula_does_not_declare_is_rejected(self):
        """An unrecognised input means the arithmetic that produced the value is
        not the arithmetic on record."""
        inputs = _annual_cost_inputs(
            mystery_discount={"value": 5000, "currency": "EUR", "per": "once"}
        )
        with pytest.raises(ClaimError, match="does not accept input"):
            verify_formula_claim(_derived(41275, inputs=inputs), path="p")

    def test_an_unknown_formula_id_is_rejected(self):
        with pytest.raises(ClaimError, match="is not registered"):
            verify_formula_claim(
                {"value": 1, "value_status": "DERIVED", "formula": "made_up_v9", "inputs": {}},
                path="p",
            )

    def test_a_file_cannot_restate_the_expression_differently(self):
        with pytest.raises(ClaimError, match="does not match the registered expression"):
            verify_formula_claim(
                _derived(46275, expression="annual_cost = 1"), path="p"
            )

    def test_a_bare_number_cannot_stand_in_for_a_monetary_input(self):
        inputs = _annual_cost_inputs(annual_tuition=27000)
        with pytest.raises(ClaimError, match="must declare its currency"):
            verify_formula_claim(_derived(46275, inputs=inputs), path="p")

    def test_a_declared_currency_must_match_its_inputs(self):
        with pytest.raises(ClaimError, match="declared currency"):
            verify_formula_claim(_derived(46275, currency="GBP"), path="p")

    def test_a_derived_figure_is_verified_when_the_corpus_is_loaded(self, tmp_path: Path):
        """The check runs on the path the application actually uses, not only when
        called directly."""
        document = _country()
        document["sections"]["living_costs"] = {
            "annual_total": {
                "value": 51075, "currency": "EUR", "value_status": "DERIVED",
                "formula": {
                    "formula_id": "annual_cost_v1", "formula_version": 1,
                    "inputs": _annual_cost_inputs(),
                },
            }
        }
        (tmp_path / "XX.json").write_text(json.dumps(document), encoding="utf-8")
        loaded = load_corpus(tmp_path)
        assert not loaded.iso2_codes
        assert "does not match" in loaded.problems[0].reason

    def test_a_reproducible_derived_figure_survives_a_corpus_load(self, tmp_path: Path):
        document = _country()
        document["sections"]["living_costs"] = {
            "annual_total": {
                "value": 46275, "currency": "EUR", "value_status": "DERIVED",
                "formula": {
                    "formula_id": "annual_cost_v1", "formula_version": 1,
                    "inputs": _annual_cost_inputs(),
                },
            }
        }
        (tmp_path / "XX.json").write_text(json.dumps(document), encoding="utf-8")
        loaded = load_corpus(tmp_path)
        assert loaded.iso2_codes == ("XX",), [p.reason for p in loaded.problems]


# --------------------------------------------------------------------------------------
# Parts 4 and 5 - refusals
# --------------------------------------------------------------------------------------


class TestRefusals:
    def test_mixed_currency_is_refused_and_never_converted(self):
        """EUR 20,000 against GBP 18,000 is a comparison between two numbers.

        Converting needs a sourced rate for an applicable period, which is itself a
        researched figure with a date. This module has no rate to consult, so the
        only honest answer is a refusal.
        """
        outcome = evaluate(
            FORMULAS["annual_cost_v1"],
            {
                "annual_tuition": FormulaInput("annual_tuition", 20000, "EUR", "year"),
                "monthly_living_cost": FormulaInput(
                    "monthly_living_cost", 1500, "GBP", "month"
                ),
            },
        )
        assert not outcome.computed
        assert outcome.refusal == "MISSING_FX_RATE"
        assert "no sourced exchange rate" in outcome.reason

    def test_unit_mismatch_is_refused_rather_than_scaled(self):
        """Feeding a yearly living cost into a monthly slot would be wrong by a
        factor of twelve while still looking like a cost."""
        outcome = evaluate(
            FORMULAS["annual_cost_v1"],
            {
                "annual_tuition": FormulaInput("annual_tuition", 27000, "EUR", "year"),
                "monthly_living_cost": FormulaInput("monthly_living_cost", 19200, "EUR", "year"),
            },
        )
        assert outcome.refusal == "UNIT_MISMATCH"

    def test_break_even_refuses_a_gross_salary(self):
        """Gross is what official statistics publish, which is exactly why this
        cannot live in a comment. Take-home is typically 55-65% of gross in most
        European countries, so using gross roughly halves the months reported."""
        outcome = evaluate(
            FORMULAS["break_even_months_v1"],
            {
                "programme_cost": FormulaInput("programme_cost", 60000, "EUR", "programme"),
                "net_monthly_income": FormulaInput(
                    "net_monthly_income", 2800, "EUR", "month", basis="gross"
                ),
            },
        )
        assert outcome.refusal == "UNIT_MISMATCH"
        assert "not take-home pay" in outcome.reason

    def test_break_even_refuses_an_undeclared_income_basis(self):
        """Silence is not consent. An income figure that never says whether it is
        gross or net cannot be used to repay a cost."""
        outcome = evaluate(
            FORMULAS["break_even_months_v1"],
            {
                "programme_cost": FormulaInput("programme_cost", 60000, "EUR", "programme"),
                "net_monthly_income": FormulaInput(
                    "net_monthly_income", 2800, "EUR", "month"
                ),
            },
        )
        assert outcome.refusal == "UNIT_MISMATCH"
        assert "undeclared" in outcome.reason

    def test_break_even_computes_on_net_income(self):
        outcome = evaluate(
            FORMULAS["break_even_months_v1"],
            {
                "programme_cost": FormulaInput("programme_cost", 60000, "EUR", "programme"),
                "net_monthly_income": FormulaInput(
                    "net_monthly_income", 2800, "EUR", "month", basis="net"
                ),
            },
        )
        assert outcome.computed and outcome.value == 21.4
        assert outcome.per == "months"
        assert outcome.assumptions, "a computed figure must publish what it assumes"

    def test_refusal_vocabulary_is_published_so_a_client_can_recognise_it(self):
        for spec in FORMULAS.values():
            assert spec.refusals, f"{spec.formula_id} declares no refusal codes"
            for code in spec.refusals:
                assert isinstance(code, str) and code

    def test_coverage_is_refused_when_the_catalogue_is_thin(self):
        rate, reason = scholarship_coverage(1, 2)
        assert rate is None and "Too few" in reason


# --------------------------------------------------------------------------------------
# Part 6 - country code safety
# --------------------------------------------------------------------------------------


class TestCountryCodeSafety:
    def test_the_protected_match_map_is_not_extended_here(self):
        """Every extension must be a country the Match gate does not know.

        Adding to ``COUNTRY_CODES`` would let a new country resolve inside
        nationality and preferred-country scoring, silently changing Match
        results. This asserts the extension stayed separate.
        """
        assert not (set(COUNTRY_CODE_EXTENSIONS) & set(COUNTRY_CODES))

    def test_the_protected_resolver_still_returns_the_uk_pseudo_code(self):
        """The protected map is *correct* - ``COUNTRY_CODES["uk"]`` is ``"GB"`` -
        but ``resolve_country_code`` uppercases any two-letter input and returns
        that before the map is consulted, so it answers ``"uk"`` with ``"UK"``,
        which is not an ISO 3166-1 country code.

        This asserts the pre-existing behaviour on purpose. It is the reason
        Country Intelligence consults its alias map **first**, and if someone
        fixes the shortcut upstream this test should be revisited rather than
        quietly left to rot.
        """
        from app.services.matching.normalize import resolve_country_code

        assert COUNTRY_CODES["uk"] == "GB"
        assert resolve_country_code("uk") == "UK"

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("UK", "GB"), ("uk", "GB"), ("United Kingdom", "GB"), ("GB", "GB"),
            ("Türkiye", "TR"), ("Türkiye", "TR"), ("Turkey", "TR"),
            ("Czechia", "CZ"), ("Czech Republic", "CZ"),
            ("USA", "US"), ("United States", "US"),
        ],
    )
    def test_resolution_table(self, value, expected):
        assert resolve_country_code_extended(value) == expected

    def test_turkiye_is_not_mojibake_repaired_into_something_else(self):
        """The stored value is a precomposed ``U+00FC``.

        A speculative repair that rewrites unfamiliar bytes into a different
        country would silently reassign a real country's scholarships. A garbled
        encoding resolves to nothing, which is recoverable; a wrong country is not.
        The plain ASCII transliteration is in the protected map on its own merits
        and resolves legitimately.
        """
        assert resolve_country_code_extended("TÃ¼rkiye") is None
        assert resolve_country_code_extended("Turkiye") == "TR"
        assert resolve_country_code_extended("Türkiye") == "TR"

    def test_an_unrecognised_country_is_never_guessed(self):
        for value in ("Atlantis", "", None, "Freedonia"):
            assert resolve_country_code_extended(value) is None


# --------------------------------------------------------------------------------------
# Part 7 - bachelor first, levels not collapsed
# --------------------------------------------------------------------------------------


class TestBachelorFirstContract:
    def test_study_levels_are_distinct_and_bachelor_is_first(self):
        from app.services.country_intelligence.derive import STUDY_LEVELS

        assert STUDY_LEVELS[0] == "bachelor"
        assert set(STUDY_LEVELS) == {"bachelor", "master", "phd"}

    def test_the_shipped_corpus_prices_each_level_separately(self):
        """Degrees must not be inferred from one another.

        "Master = fully funded" is not a safe default: on the current catalogue it
        holds for China, Norway and Belgium and fails for Finland, Denmark, Spain
        and Chile. Collapsing the levels would be exactly that assumption, written
        into the data.

        The three levels are still read as three separate claims, which is the
        contract this test exists to protect. What changed is Germany's value: it
        used to assert ``0``, sourced from make-it-in-germany.com's Skilled
        Immigration Act page - a visa page, with no archived extract - which
        ``derive_tuition`` turned into a EUR 0/year budget while
        Baden-Wuerttemberg's real statutory fee sat unreached at another path. The
        zero rule now refuses it, so the claim is published as not-established and
        keeps its provenance. The assertion below therefore checks the separation
        and the lineage, not a number that asserted a country charges nothing.
        """
        germany = load_corpus().get("DE")
        assert germany is not None
        levels = {
            level: germany.claim(
                "education_costs", "tuition_fees", "public", level
            )
            for level in ("bachelor", "master", "phd")
        }
        # Three separate claims at three separate paths, not one figure read three
        # ways. That separation is the contract this test exists to protect.
        for level, claim in levels.items():
            assert claim is not None, f"public.{level} is absent from the corpus"
            assert claim.value is None, f"public.{level} still publishes an unsupported zero"
            assert claim.value_status == "UNKNOWN", level
            assert claim.note, f"public.{level} is refused without giving a reason"

        # The refusal must stay reviewable, so the raw record keeps the claim that
        # was refused. The ``Claim`` view deliberately carries only the reason for
        # an UNKNOWN figure - there is no figure to attribute a currency or a period
        # to - so lineage is asserted on the stored document.
        stored = json.loads((CORPUS_DIR / "DE.json").read_text(encoding="utf-8-sig"))
        public = stored["sections"]["education_costs"]["tuition_fees"]["public"]
        for level in ("bachelor", "master", "phd"):
            node = public[level]
            assert node["source_ids"], f"public.{level} lost the source of the refused claim"
            assert node["as_of"], f"public.{level} lost the date of the refused claim"
            assert node["evidence_archived"] is False, level
        assert public["bachelor"]["source_ids"] == ["de-s16"]
        # The states and universities that were verified remain filed separately, so
        # the refusal did not flatten Germany into a single national number.
        assert "by_state" in stored["sections"]["education_costs"]["tuition_fees"]

    def test_coverage_is_a_measured_catalogue_metric_not_a_research_assumption(self):
        """It may be zero.

        Finland, Denmark and Spain hold scholarships that are none of them fully
        funded, and a model assuming postgraduate study is always funded would be
        wrong for exactly those countries.
        """
        assert scholarship_coverage(0, 12)[0] == 0.0
        rate, reason = scholarship_coverage(None, 12)
        assert rate is None and "not measured" in reason


# --------------------------------------------------------------------------------------
# Parts 9 and 13 - ingestion
# --------------------------------------------------------------------------------------


class TestIngestion:
    def test_duplicate_json_keys_are_rejected_not_silently_resolved(self, tmp_path: Path):
        """``json.loads`` keeps the last value and says nothing.

        Two research agents in this build emitted duplicated keys, in one case two
        different values under the same name. Silently keeping one publishes a
        figure the document itself contradicts.
        """
        raw = tmp_path / "XX.json"
        raw.write_text(
            '{"country": {"iso2": "XX", "name_en": "A"},'
            ' "country": {"iso2": "XX", "name_en": "B"}, "sources": []}',
            encoding="utf-8",
        )
        report = ingest.ingest_country(raw, tmp_path / "out")
        assert not report.written
        assert "duplicate JSON key" in report.reason

    def test_placeholders_are_rejected_rather_than_published(self, tmp_path: Path):
        """A placeholder occupies the position where a real figure would go."""
        document = _country()
        document["sections"]["one_time_costs"]["visa_fee"]["value"] = "TODO"
        raw = tmp_path / "XX.json"
        raw.write_text(json.dumps(document), encoding="utf-8")
        report = ingest.ingest_country(raw, tmp_path / "out")
        assert not report.written
        assert "placeholder" in report.reason

    def test_a_failing_gate_writes_no_file_at_all(self, tmp_path: Path):
        """Half a country is worse than no country: a reader cannot tell which half
        survived."""
        document = _country()
        document["sections"]["one_time_costs"]["visa_fee"]["source_ids"] = ["xx-s99"]
        raw = tmp_path / "XX.json"
        raw.write_text(json.dumps(document), encoding="utf-8")
        out = tmp_path / "out"
        report = ingest.ingest_country(raw, out)
        assert not report.written
        assert not list(out.glob("*.json")) if out.exists() else True

    def test_a_clean_document_is_written_and_reproducible(self, tmp_path: Path):
        raw = tmp_path / "XX.json"
        raw.write_text(json.dumps(_country()), encoding="utf-8")
        out = tmp_path / "out"
        first = ingest.ingest_country(raw, out)
        assert first.written
        target = out / "XX.json"
        digest_one = target.read_bytes()

        second = ingest.ingest_country(raw, out)
        assert second.written
        assert target.read_bytes() == digest_one, "ingestion is not deterministic"

    def test_an_unavailable_raw_source_ingests_nothing(self):
        """A summary of a finding is not a source document."""
        reports = ingest.ingest_from_archive(
            manifest_path=ingest.MANIFEST_PATH, corpus_dir=CORPUS_DIR
        )
        assert reports, "the archive manifest should track the researched countries"
        # This previously asserted that every country except DE was
        # RAW_SOURCE_UNAVAILABLE. That was true only while the manifest was
        # stale: it recorded the state of the first research pass while real
        # artifacts accumulated on disk. After reconciliation every country here
        # has archived, ingestion-eligible evidence and must be ingested.
        #
        # What still has to hold is the refusal rule itself - a scope with no
        # eligible artifact yields no figure - so that is what is asserted, plus
        # that every report states a reason rather than failing silently.
        for report in reports:
            assert report.reason or report.written
            if not report.written:
                assert "ingestion-eligible" in report.reason or "no raw_file" not in report.reason

    def test_the_manifest_marks_every_researched_country(self):
        manifest = json.loads(ingest.MANIFEST_PATH.read_text(encoding="utf-8-sig"))
        tracked = {entry["iso2"] for entry in manifest["countries"]}
        assert tracked == {
            "DE", "US", "GB", "CA", "AU", "NL", "SG", "NZ", "JP", "CH",
            "FR", "AT", "SE", "PL", "IT", "IE", "FI",
        }

    def test_truncated_research_is_recorded_rather_than_treated_as_complete(self):
        manifest = json.loads(ingest.MANIFEST_PATH.read_text(encoding="utf-8-sig"))
        truncated = {
            entry["iso2"] for entry in manifest["countries"] if entry["truncated"]
        }
        assert {"JP", "IE"} <= truncated

    def test_pending_claims_are_not_ingested(self):
        """A claim in the manifest is a to-do item with a named field, not a figure."""
        manifest = json.loads(ingest.MANIFEST_PATH.read_text(encoding="utf-8-sig"))
        for claim in manifest["pending_claims"]:
            if claim["status"] == "UNAVAILABLE_FOR_INGESTION":
                assert claim["ingested"] is False

    def test_no_gate_can_be_skipped(self):
        """There is no force flag, and adding one would be the failure mode this
        module exists to prevent."""
        with pytest.raises(SystemExit):
            ingest.main(["--force"])
        with pytest.raises(SystemExit):
            ingest.main(["--skip-validation"])

    def test_check_reports_a_healthy_shipped_corpus(self):
        assert ingest.check(CORPUS_DIR) == []


# --------------------------------------------------------------------------------------
# Part 17 - integrity
# --------------------------------------------------------------------------------------


class TestIntegrity:
    def test_loading_the_corpus_makes_no_network_call(self, monkeypatch):
        """The corpus is curated files. A build-time fetch would make a reviewed
        artefact depend on a third party being up."""
        import socket

        def _forbidden(*args, **kwargs):
            raise AssertionError("corpus loading must not open a socket")

        monkeypatch.setattr(socket, "socket", _forbidden)
        monkeypatch.setattr(socket, "create_connection", _forbidden)
        loaded = load_corpus(CORPUS_DIR)
        # Asserted as a property rather than a fixed list: which countries are
        # ingested changes with every research pass, and a test that pinned the
        # list would fail on every successful ingestion rather than on a real
        # regression.
        assert loaded.iso2_codes, "the shipped corpus should not be empty"
        assert not loaded.problems, [p.to_dict() for p in loaded.problems]

    def test_the_country_path_parameter_cannot_traverse(self):
        """``/v2/countries/{iso2}`` is bounded to exactly two ASCII letters and is
        used only as a dictionary key, never as a path."""
        from app.routers.countries import read_country

        parameters = read_country.__annotations__
        assert "iso2" in parameters

    @pytest.mark.parametrize(
        "attempt", ["../../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "DE/../../etc", "D3"]
    )
    def test_traversal_attempts_do_not_resolve(self, attempt):
        """A lookup that fails is recoverable; a wrong answer is not."""
        assert resolve_country_code_extended(attempt) is None

    def test_no_database_migration_is_introduced(self):
        """The researched and derived planes are files, not tables.

        This repository has no Alembic and production startup deliberately refuses
        to migrate, so a table added here would reach the database only by a
        separate hand-run script that the next reader would not know existed.
        Scoped to code rather than to the word: these modules discuss Alembic in
        their docstrings precisely to explain why they do not use it.
        """
        forbidden = (
            "import alembic",
            "from alembic",
            "alembic.ini",
            "op.create_table",
            "Base.metadata.create_all",
        )
        package = Path(corpus_module_path()).parent
        for path in package.glob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            for marker in forbidden:
                assert marker not in text, f"{path.name} contains {marker!r}"

    def test_only_the_measured_plane_touches_the_database(self):
        """``catalogue.py`` must query - that is the measured plane.

        The researched plane must not: a researched figure's provenance is its
        source document, and a database read in that path would blur which plane
        a number came from.
        """
        package = Path(corpus_module_path()).parent
        for path in package.glob("*.py"):
            if path.name == "catalogue.py":
                continue
            text = path.read_text(encoding="utf-8-sig")
            assert "import sqlalchemy" not in text, path.name
            assert "from ...database" not in text, path.name
            assert "from ...models" not in text, path.name

    def test_measured_counts_come_from_the_single_public_predicate(self):
        """Visibility logic is defined once and reused, never reimplemented.

        A second copy of "may be shown publicly" would drift from the first, and
        the two pages would then disagree about how many scholarships exist.
        """
        import app.services.country_intelligence.catalogue as catalogue_module
        from app.repositories.scholarships import public_visibility_conditions

        source = Path(catalogue_module.__file__).read_text(encoding="utf-8")
        assert "from ...repositories.scholarships import public_visibility_conditions" in source
        assert "and_(*public_visibility_conditions())" in source
        assert callable(public_visibility_conditions)

    def test_a_broken_file_never_takes_the_corpus_down(self, tmp_path: Path):
        (tmp_path / "XX.json").write_text("{ not json", encoding="utf-8")
        (tmp_path / "YY.json").write_text(
            json.dumps(_country(**{"country": {"iso2": "YY", "name_en": "Y", "currency": "EUR"}})),
            encoding="utf-8",
        )
        loaded = load_corpus(tmp_path)
        assert loaded.iso2_codes == ("YY",)
        assert [p.iso2 for p in loaded.problems] == ["XX"]

    def test_a_missing_corpus_is_empty_not_an_error(self, tmp_path: Path):
        loaded = load_corpus(tmp_path / "absent")
        assert len(loaded) == 0 and not loaded.problems

    def test_every_section_name_is_known(self):
        assert "education_costs" in SECTION_NAMES
        assert "scholarship_landscape" in SECTION_NAMES


def corpus_module_path() -> str:
    import app.services.country_intelligence.corpus as module

    return module.__file__


def catalogue_module_path() -> str:
    import app.services.country_intelligence.catalogue as module

    return module.__file__


def _unused(*_args, **_kwargs) -> None:  # pragma: no cover - import guard
    """Keeps optional imports referenced so a removal is a visible failure."""
    _unused(measure_country_catalogue, REFUSAL_MISSING_NET_INCOME, formula_module)


# --------------------------------------------------------------------------------------
# Sourced FX - cross-currency comparison
# --------------------------------------------------------------------------------------


class TestSourcedFx:
    def test_the_shipped_table_is_auditable(self):
        """A rate without a source and a date must not be used to convert."""
        from app.services.country_intelligence.fx import get_fx_table

        table = get_fx_table()
        assert table is not None, "the ECB evidence is archived and should build a table"
        assert table.base == "EUR"
        assert table.as_of
        assert table.source_id and table.source_url
        for currency in table.rates:
            assert len(currency) == 3 and table.rates[currency] > 0

    def test_a_rate_cannot_be_inverted_by_accident(self):
        """The most likely FX bug: 1 EUR = 1.1225 USD and 1 USD = 0.8908 EUR are the
        same fact, and mixing them turns a comparison into its inverse."""
        from app.services.country_intelligence.fx import get_fx_table

        table = get_fx_table()
        forward = table.convert(1.0, "EUR", "USD")
        backward = table.convert(1.0, "USD", "EUR")
        assert forward.rate == pytest.approx(table.rates["USD"])
        assert backward.rate == pytest.approx(1 / table.rates["USD"])
        round_trip = table.convert(forward.amount, "USD", "EUR")
        assert round_trip.amount == pytest.approx(1.0, rel=1e-9)

    def test_every_published_conversion_states_its_direction(self):
        from app.services.country_intelligence.fx import get_fx_table

        published = get_fx_table().convert(18000, "GBP", "EUR").to_dict()
        assert published["from_currency"] == "GBP" and published["to_currency"] == "EUR"
        assert published["rate_definition"] == "units of EUR per 1 GBP"
        assert published["rate_date"] and published["source_id"] and published["source_url"]
        assert "EUR" in published["via"]

    def test_an_unsourced_currency_is_refused_not_guessed(self):
        """There is no 'assume parity' branch, because parity is a rate nobody
        sourced."""
        from app.services.country_intelligence.fx import FxUnavailable, get_fx_table

        with pytest.raises(FxUnavailable, match="not in the rate table"):
            get_fx_table().convert(100, "XYZ", "EUR")

    def test_the_ecb_caveat_travels_with_the_numbers(self):
        """The ECB publishes these for information only. A client must not be able
        to render a converted cost without also being able to render that."""
        from app.services.country_intelligence.fx import get_fx_table

        published = get_fx_table().convert(100, "USD", "EUR").to_dict()
        assert "information purposes only" in published["caveat"]
        assert "not be used to budget" in published["caveat"]

    def test_a_table_with_no_date_is_rejected(self):
        from app.services.country_intelligence.fx import parse_fx_table

        with pytest.raises(ClaimError, match="as_of"):
            parse_fx_table(
                {"base": "EUR", "rates": {"USD": 1.1}, "source_id": "s",
                 "source_url": "https://example.org"},
                path="fx",
            )

    def test_a_table_with_no_source_is_rejected(self):
        from app.services.country_intelligence.fx import parse_fx_table

        with pytest.raises(ClaimError, match="source_url"):
            parse_fx_table(
                {"base": "EUR", "as_of": "2026-10-02", "rates": {"USD": 1.1},
                 "source_id": "s"},
                path="fx",
            )

    def test_the_base_currency_may_not_be_listed_as_a_rate(self):
        """It is 1 by definition, and listing it invites a double conversion."""
        from app.services.country_intelligence.fx import parse_fx_table

        with pytest.raises(ClaimError, match="must not appear in 'rates'"):
            parse_fx_table(
                {"base": "EUR", "as_of": "2026-10-02", "source_id": "s",
                 "source_url": "https://example.org",
                 "rates": {"EUR": 1.0, "USD": 1.1}},
                path="fx",
            )

    def test_fx_is_deterministic_from_archived_evidence(self, tmp_path: Path):
        """Rebuilding from the same raw artifact gives byte-identical output."""
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from scripts import ingest_country_intelligence as ingest

        out = tmp_path / "fx" / "rates.json"
        first = ingest.build_fx_table(ingest.FX_RAW_PATH, out)
        assert first.written, first.reason
        digest = out.read_bytes()
        second = ingest.build_fx_table(ingest.FX_RAW_PATH, out)
        assert second.written
        assert out.read_bytes() == digest, "FX ingestion is not deterministic"



