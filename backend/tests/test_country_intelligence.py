"""Country Intelligence tests.

The suite is built around one idea: the feature's value depends entirely on a
reader being able to trust each number, so the tests assert refusals and
provenance as first-class behaviour rather than only checking that happy paths
return something.

Three properties are protected here that nothing else in the repository does:

* **Normalisation cannot invent or lose a country.** The catalogue stores 82
  distinct country strings for 63 real countries. Aliases must merge, genuine
  multi-country records must be counted under each member, and an unrecognised
  value must stay unrecognised.
* **A figure with no provenance does not ship.** A researched number without a
  ``value_status``, or with an evidence status and no source, must be rejected -
  and the country excluded, with the reason published.
* **Derivation refuses rather than approximates.** Break-even from a gross salary
  and any cross-currency total are the two shortcuts that would produce confident
  wrong answers, so both are asserted to be refused.

The API tests follow the established pattern in ``test_counting_api.py``: a
module-scoped in-memory SQLite engine with ``StaticPool``, seeded through the ORM,
and ``app.dependency_overrides[get_db]`` pinned and restored.
"""

from __future__ import annotations

import os

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")
os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")  # noqa: E402

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.country_intelligence import corpus as corpus_module  # noqa: E402
from app.services.country_intelligence import service as service_module  # noqa: E402
from app.services.country_intelligence.catalogue import (  # noqa: E402
    measure_country_catalogue,
)
from app.services.country_intelligence.derive import (  # noqa: E402
    REFUSAL_GROSS_INCOME,
    REFUSAL_MISSING_FX_RATE,
    REFUSAL_MISSING_NET_INCOME,
    Derivation,
    derive_break_even,
    derive_living,
    derive_one_time_total,
    derive_tuition,
    scholarship_coverage,
)
from app.services.country_intelligence.provenance import (  # noqa: E402
    ClaimError,
    parse_claim,
)
from app.services.country_intelligence.taxonomy import (  # noqa: E402
    classify_country_value,
    display_name,
    flag_emoji,
    resolve_country_code_extended,
)

# --------------------------------------------------------------------------------------
# Taxonomy
# --------------------------------------------------------------------------------------


class TestTaxonomy:
    def test_alias_merges_into_one_country(self):
        """The catalogue stores both "UK" and "United Kingdom".

        resolve_country_code contains a shortcut that uppercases any two-letter
        input before the alias map is consulted, so "UK" used to resolve to "UK" -
        which is not an ISO 3166-1 code - and the United Kingdom was counted twice.
        """
        assert resolve_country_code_extended("UK") == "GB"
        assert resolve_country_code_extended("United Kingdom") == "GB"

    def test_us_aliases_merge(self):
        assert resolve_country_code_extended("USA") == "US"
        assert resolve_country_code_extended("United States") == "US"

    def test_official_name_with_diacritic_resolves(self):
        """The catalogue stores the precomposed spelling of Türkiye."""
        assert resolve_country_code_extended("T\u00fcrkiye") == "TR"

    def test_combining_and_precomposed_forms_are_equal(self):
        composed = resolve_country_code_extended("T\u00fcrkiye")
        decomposed = resolve_country_code_extended("Tu\u0308rkiye")
        assert composed == decomposed == "TR"

    def test_never_guesses(self):
        for value in ("Atlantis", "", None, "Freedonia"):
            assert classify_country_value(value).kind == "UNRESOLVED"

    def test_multi_country_enumeration_resolves_every_member(self):
        resolution = classify_country_value("Czechia, Hungary, Poland, Slovakia")
        assert resolution.kind == "MULTI_COUNTRY"
        assert resolution.members == ("CZ", "HU", "PL", "SK")
        assert not resolution.is_partially_resolved

    def test_partial_enumeration_is_reported_not_hidden(self):
        """A record naming two countries, one unknown, must not look complete."""
        resolution = classify_country_value(
            "United Kingdom, Republic of Ireland, low- or middle-income countries"
        )
        assert resolution.members == ("GB",)
        assert resolution.is_partially_resolved

    def test_scope_wording_is_not_reported_as_a_missing_country(self):
        """"low- or middle-income countries" is an eligibility scope.

        Reporting it as an unresolved host country would pad the gap report with
        text that never claimed to name a country.
        """
        resolution = classify_country_value("United Kingdom, Republic of Ireland")
        assert "united kingdom" not in resolution.unresolved_members

    @pytest.mark.parametrize(
        "value,kind",
        [
            ("Global", "GLOBAL"),
            ("EU (multiple)", "GLOBAL"),
            ("International", "GLOBAL"),
            ("Fiji", "COUNTRY"),
            ("Hong Kong", "COUNTRY"),
            ("Brunei Darussalam", "COUNTRY"),
        ],
    )
    def test_classification_table(self, value, kind):
        assert classify_country_value(value).kind == kind

    def test_every_published_country_has_a_display_name(self):
        for value in ("Japan", "Kenya", "Brazil", "Peru", "Indonesia"):
            code = resolve_country_code_extended(value)
            assert display_name(code) != code, f"{code} has no display name"


# --------------------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------------------


class TestProvenance:
    def test_bare_number_is_rejected(self):
        with pytest.raises(ClaimError):
            parse_claim({"value": 500}, path="p")

    def test_evidence_status_requires_a_source(self):
        with pytest.raises(ClaimError, match="source"):
            parse_claim({"value": 1, "value_status": "OFFICIAL_GOVERNMENT"}, path="p")

    def test_unknown_cannot_carry_a_value(self):
        with pytest.raises(ClaimError):
            parse_claim({"value": 1, "value_status": "UNKNOWN", "note": "x"}, path="p")

    def test_evidence_status_requires_a_value(self):
        """An absent figure is UNKNOWN. It is not a zero under an evidence status."""
        with pytest.raises(ClaimError):
            parse_claim({"value": None, "value_status": "CROWDSOURCED", "source_ids": ["s"]}, path="p")

    def test_derived_requires_a_formula(self):
        with pytest.raises(ClaimError, match="formula"):
            parse_claim({"value": 1, "value_status": "DERIVED", "source_ids": ["s"]}, path="p")

    def test_reversed_range_is_rejected(self):
        with pytest.raises(ClaimError, match="greater than"):
            parse_claim(
                {
                    "min": 1500, "max": 900, "value": 1200,
                    "value_status": "CROWDSOURCED", "source_ids": ["s"],
                },
                path="p",
            )

    def test_average_outside_its_own_range_is_rejected(self):
        with pytest.raises(ClaimError, match="outside"):
            parse_claim(
                {
                    "min": 100, "max": 200, "value": 500,
                    "value_status": "CROWDSOURCED", "source_ids": ["s"],
                },
                path="p",
            )

    def test_mangled_status_spelling_is_aliased(self):
        """A typo is a typo; it should not be treated as an invented claim type."""
        claim = parse_claim(
            {"value": 10, "value_status": "OFFICIAL_GOVERNUMENT", "source_ids": ["s"]},
            path="p",
        )
        assert claim.value_status == "OFFICIAL_GOVERNMENT"

    def test_genuinely_unknown_status_is_still_rejected(self):
        with pytest.raises(ClaimError, match="not one of"):
            parse_claim({"value": 10, "value_status": "TRUSTED_SOURCE", "source_ids": ["s"]}, path="p")

    def test_range_publishes_its_span(self):
        claim = parse_claim(
            {
                "min": 900, "max": 1500, "value": 1200, "currency": "EUR", "per": "month",
                "value_status": "CROWDSOURCED", "source_ids": ["s"], "sample_size": 210,
            },
            path="p",
        )
        published = claim.to_dict()
        assert published["range"] == {"min": 900, "max": 1500, "average": 1200}
        assert published["sample_size"] == 210


# --------------------------------------------------------------------------------------
# Corpus loading
# --------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_corpus():
    """Drop the process-cached corpus around every test in this module.

    ``get_corpus`` is an ``lru_cache``d singleton so the curated files are read
    once per process, which is right in production and wrong in a test suite: a
    module that also writes corpus fixtures into temporary directories would
    otherwise observe whichever load happened first. Clearing it per test means
    each test reads the repository's real corpus.
    """
    corpus_module.reload_corpus()
    yield
    corpus_module.reload_corpus()


def _valid_file() -> dict:
    return {
        "country": {"iso2": "XX", "name_en": "Example", "currency": "EUR"},
        "research": {"researched_at": "2026-10-05"},
        "sources": [
            {
                "id": "xx-s1", "publisher": "p", "title": "t",
                "url": "https://example.test", "source_type": "OFFICIAL_GOVERNENT",
            }
        ],
        "sections": {
            "one_time_costs": {
                "visa_fee": {
                    "value": 75, "currency": "EUR", "per": "application",
                    "value_status": "OFFICIAL_GOVERNEMENT", "source_ids": ["xx-s1"],
                }
            }
        },
        "gaps": [{"field": "career.salary", "reason": "Not researched."}],
    }


class TestCorpus:
    def test_valid_file_publishes(self, tmp_path: Path):
        (tmp_path / "XX.json").write_text(json.dumps(_valid_file()), encoding="utf-8")
        loaded = corpus_module.load_corpus(tmp_path)
        assert loaded.iso2_codes == ("XX",)
        assert not loaded.problems

    def test_one_broken_file_does_not_exclude_the_good_one(self, tmp_path: Path):
        (tmp_path / "XX.json").write_text(json.dumps(_valid_file()), encoding="utf-8")
        (tmp_path / "YY.json").write_text("{ not json", encoding="utf-8")
        loaded = corpus_module.load_corpus(tmp_path)
        assert loaded.iso2_codes == ("XX",)
        assert [p.iso2 for p in loaded.problems] == ["YY"]

    def test_dangling_citation_is_rejected(self, tmp_path: Path):
        data = _valid_file()
        data["sections"]["one_time_costs"]["visa_fee"]["source_ids"] = ["xx-s99"]
        (tmp_path / "XX.json").write_text(json.dumps(data), encoding="utf-8")
        loaded = corpus_module.load_corpus(tmp_path)
        assert not loaded.iso2_codes
        assert "cite a source not defined" in loaded.problems[0].reason

    def test_context_node_metadata_is_inherited(self, tmp_path: Path):
        """A block declaring currency, period and evidence strength once.

        Research is written this way - one ``"currency": "EUR"`` at the top of a
        block rather than repeated on every line - and the inherited figure must
        remain usable. The assertion is made against the **validated** claim
        rather than the stored body, because those are different things: the body
        is the research as written, for a reviewer to check the transcription,
        and the claim is the same data with block metadata merged in. Asserting
        against the body would be asserting that loading rewrites the file's
        content, which is not the contract and would make a reviewer's diff
        misleading.
        """
        data = _valid_file()
        data["sections"]["living_costs"] = {
            "monthly_costs": {
                "high": {
                    "currency": "EUR", "per": "month", "value_status": "CROWDSOURCED",
                    "total": {"value": 1600, "source_ids": ["xx-s1"]},
                }
            }
        }
        (tmp_path / "XX.json").write_text(json.dumps(data), encoding="utf-8")
        record = corpus_module.load_corpus(tmp_path).get("XX")
        assert record is not None

        claim = record.claim("living_costs", "monthly_costs", "high", "total")
        assert claim is not None
        assert claim.value == 1600
        assert claim.currency == "EUR"
        assert claim.per == "month"
        assert claim.source_ids == ("xx-s1",)
        # The status is inherited too. Without it the child would fall back to
        # UNKNOWN while still carrying a value, which excludes the whole country
        # with an error about a figure nobody questioned.
        assert claim.value_status == "CROWDSOURCED"

    def test_explicit_child_metadata_overrides_the_block(self, tmp_path: Path):
        """Inheritance is a default, not an override of the figure itself."""
        data = _valid_file()
        data["sections"]["living_costs"] = {
            "monthly_costs": {
                "high": {
                    "currency": "EUR", "per": "month", "value_status": "CROWDSOURCED",
                    "total": {"value": 1600, "source_ids": ["xx-s1"]},
                    # Declared locally, so it must not pick up the block's
                    # currency or evidence strength.
                    "survey_fee": {
                        "value": 12, "currency": "USD", "per": "once",
                        "value_status": "OFFICIAL_STATISTICS", "source_ids": ["xx-s1"],
                    },
                }
            }
        }
        (tmp_path / "XX.json").write_text(json.dumps(data), encoding="utf-8")
        record = corpus_module.load_corpus(tmp_path).get("XX")
        assert record is not None

        inherited = record.claim("living_costs", "monthly_costs", "high", "total")
        overridden = record.claim("living_costs", "monthly_costs", "high", "survey_fee")
        assert (inherited.currency, inherited.per, inherited.value_status) == (
            "EUR", "month", "CROWDSOURCED",
        )
        assert (overridden.currency, overridden.per, overridden.value_status) == (
            "USD", "once", "OFFICIAL_STATISTICS",
        )

    def test_inherited_status_is_not_a_licence_to_mislabel_a_source(self, tmp_path: Path):
        """Inheritance can stamp a status down; the source check still holds.

        A block declaring ``OFFICIAL_GOVERNMENT`` over a figure that cites a
        crowdsourced pool would otherwise be accepted on the strength of the
        block alone. The cross-check closes that: an official status needs an
        official source behind it.
        """
        data = _valid_file()
        data["sources"][0]["source_type"] = "CROWDSOURCED"
        data["sections"]["living_costs"] = {
            "monthly_costs": {
                "high": {
                    "currency": "EUR", "per": "month", "value_status": "OFFICIAL_GOVERNMENT",
                    "total": {"value": 1600, "source_ids": ["xx-s1"]},
                }
            }
        }
        (tmp_path / "XX.json").write_text(json.dumps(data), encoding="utf-8")
        loaded = corpus_module.load_corpus(tmp_path)
        assert not loaded.iso2_codes
        assert "asserts an official source" in loaded.problems[0].reason

    def test_missing_directory_is_empty_not_an_error(self, tmp_path: Path):
        loaded = corpus_module.load_corpus(tmp_path / "absent")
        assert len(loaded) == 0 and not loaded.problems

    def test_shipped_corpus_is_valid(self):
        """Every country file in the repo must load.

        If this fails, a country is being served with a broken figure, or the file
        was edited into an invalid state. The problems list says which and why.
        """
        loaded = corpus_module.load_corpus()
        assert not loaded.problems, [p.to_dict() for p in loaded.problems]


# --------------------------------------------------------------------------------------
# Derivation refusals
# --------------------------------------------------------------------------------------


_SECTIONS = {
    "education_costs": {
        "tuition_fees": {
            "public": {
                "bachelor": {
                    "value": 24000, "currency": "EUR", "per": "year",
                    "value_status": "INSTITUTIONAL_REPORT", "source_ids": ["s"],
                }
            }
        }
    },
    "living_costs": {
        "monthly_costs": {
            "high": {
                "total": {
                    "value": 1600, "currency": "EUR", "per": "month",
                    "value_status": "CROWDSOURCED", "source_ids": ["s"],
                }
            }
        }
    },
    "one_time_costs": {
        "visa_fee": {
            "value": 75, "currency": "EUR", "per": "application",
            "value_status": "OFFICIAL_GOVERNEMENT", "source_ids": ["s"],
        }
    },
    "career": {
        "net_monthly_income": {
            "basis": "net", "value": 2800, "currency": "EUR", "per": "month",
            "value_status": "OFFICIAL_STATISTICS", "source_ids": ["s"],
        }
    },
}


class TestDerivationRefusals:
    def test_coverage_is_refused_on_too_few_scholarships(self):
        """A rate from two records is noise, and dividing a tuition bill by it is a
        very precise answer to a very shaky question."""
        rate, reason = scholarship_coverage(1, 2)
        assert rate is None and "Too few" in reason

    def test_coverage_can_be_zero(self):
        """Finland, Denmark and Spain hold scholarships that are none of them fully
        funded. A model assuming postgraduate study is always funded would be wrong
        for exactly those countries."""
        assert scholarship_coverage(0, 12)[0] == 0.0

    def test_tuition_refused_without_coverage(self):
        tuition = derive_tuition(_SECTIONS, "bachelor", None)
        assert tuition.refusal == "MISSING_INPUT"

    def test_break_even_refuses_a_gross_salary(self):
        """The most tempting shortcut in the module, and the one that most reliably
        produces a confident wrong answer: take-home is roughly 55-65% of gross in
        most European countries, so using gross would roughly halve the months."""
        investment = Derivation(
            key="total_investment",
            formula="test fixture",
            value=60000.0,
            currency="EUR",
            per="programme",
        )
        gross = {
            "value": 52000, "currency": "EUR", "per": "year", "basis": "gross",
            "value_status": "OFFICIAL_STATISTICS", "source_ids": ["s"],
        }
        result = derive_break_even(investment, gross)
        # Gross income is refused under its own code, not the generic
        # MISSING_NET_INCOME. "You offered gross and I will not use it" and
        # "you offered no income at all" are different answers, and a caller
        # correcting the input needs to be told which one it was.
        assert result.refusal == REFUSAL_GROSS_INCOME
        assert result.refusal != REFUSAL_MISSING_NET_INCOME
        assert "net" in result.reason
        assert result.required_input
        # A refusal publishes REFUSED. Publishing UNKNOWN here would tell the
        # student nobody established their income, when in fact the system saw
        # the figure and declined it on purpose.
        assert result.to_dict()["value_status"] == "REFUSED"
        assert "value" not in result.to_dict()

    def test_break_even_refuses_when_income_basis_is_undeclared(self):
        investment = Derivation(
            key="total_investment", formula="test fixture", value=60000.0, currency="EUR"
        )
        undeclared = {
            "value": 2800, "currency": "EUR", "per": "month",
            "value_status": "OFFICIAL_STATISTICS", "source_ids": ["s"],
        }
        assert derive_break_even(investment, undeclared).refusal == REFUSAL_GROSS_INCOME
        # An undeclared basis is the same refusal as a declared gross one: the
        # system cannot repay a cost from a figure that does not say whether it
        # is take-home. It is NOT the missing-input case, because an income
        # figure was supplied.
        assert derive_break_even(investment, undeclared).required_input

    def test_break_even_refuses_across_currencies(self):
        """Silently comparing a EUR cost against a USD income is how a
        "break-even in 14 months" claim gets made."""
        from app.services.country_intelligence.derive import derive_total_investment

        tuition = derive_tuition(_SECTIONS, "bachelor", 0.0)
        living = derive_living(_SECTIONS, "high")
        one_time = derive_one_time_total(_SECTIONS)
        investment = derive_total_investment(tuition, living, one_time, 2)
        usd_income = {
            "basis": "net", "value": 3000, "currency": "USD", "per": "month",
            "value_status": "OFFICIAL_STATISTICS", "source_ids": ["s"],
        }
        assert derive_break_even(investment, usd_income).refusal == REFUSAL_MISSING_FX_RATE

    def test_total_refuses_while_a_component_is_missing(self):
        """A partial total understates the cost, which is the direction that gets a
        student caught out."""
        from app.services.country_intelligence.derive import derive_total_investment

        tuition = derive_tuition(_SECTIONS, "bachelor", 0.0)
        living = derive_living(_SECTIONS, "low")  # no low tier present
        one_time = derive_one_time_total(_SECTIONS)
        total = derive_total_investment(tuition, living, one_time, 2)
        assert not total.computed
        assert "living_annual" in total.reason


# --------------------------------------------------------------------------------------
# Measured plane, against real seeded rows
# --------------------------------------------------------------------------------------


def _seed(session: Session, country: str, title: str, *, fully_funded: bool = True,
          verified: bool = True, source: str | None = "official.test"):
    from app.models import Scholarship

    session.add(
        Scholarship(
            title=title, country=country, degree="Bachelor's",
            funding="Fully funded" if fully_funded else "Partial funding",
            description="", deadline_precision="month", status="open",
            is_verified=verified, image_url="https://img.test/a.png",
            image_verified_at=__import__("datetime").datetime(2026, 1, 1),
            official_source=source,
        )
    )


@pytest.fixture
def seeded_session() -> Session:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    _seed(session, "Germany", "A")
    _seed(session, "Germany", "B")
    _seed(session, "Germany", "C", fully_funded=False)
    _seed(session, "USA", "D")
    _seed(session, "United States", "E")
    _seed(session, "Global", "F")
    _seed(session, "Czechia, Hungary, Poland, Slovakia", "G")
    _seed(session, "Atlantis", "H")
    _seed(session, "UK", "I")
    _seed(session, "United Kingdom", "J")
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestMeasuredPlane:
    def test_aliases_merge_into_one_country(self, seeded_session: Session):
        measured = measure_country_catalogue(seeded_session)
        assert measured.by_country["US"].scholarships == 2
        assert set(measured.by_country["US"].source_labels) == {"USA", "United States"}

    def test_uk_alias_merges_rather_than_becoming_a_country(self, seeded_session: Session):
        measured = measure_country_catalogue(seeded_session)
        assert "UK" not in measured.by_country
        assert measured.by_country["GB"].scholarships == 2

    def test_multi_country_record_counted_under_each_member(self, seeded_session: Session):
        measured = measure_country_catalogue(seeded_session)
        for code in ("CZ", "HU", "PL", "SK"):
            assert measured.by_country[code].scholarships == 1
            assert measured.by_country[code].shared_records == 1

    def test_unrecognised_value_is_published_as_a_gap_not_dropped(self, seeded_session: Session):
        measured = measure_country_catalogue(seeded_session)
        unresolved = [g for g in measured.unattributed if g.kind == "UNRESOLVED"]
        assert unresolved and "Atlantis" in unresolved[0].labels

    def test_global_value_is_not_attributed_to_a_country(self, seeded_session: Session):
        measured = measure_country_catalogue(seeded_session)
        assert all("Atlantis" not in f.source_labels for f in measured.by_country.values())
        globals_ = [g for g in measured.unattributed if g.kind == "GLOBAL"]
        assert globals_ and "Global" in globals_[0].labels

    def test_fully_funded_rate_is_measured(self, seeded_session: Session):
        measured = measure_country_catalogue(seeded_session)
        germany = measured.by_country["DE"]
        assert germany.scholarships == 3
        assert germany.fully_funded == 2

    def test_populations_reconcile_to_the_public_total(self, seeded_session: Session):
        """single + shared + unattributed == public_total.

        A shared record is counted once here even though it is counted under
        several countries, so this identity is exact.
        """
        reconciliation = measure_country_catalogue(seeded_session).reconciliation()
        assert reconciliation["populations_sum_to_public_total"] is True
        assert (
            reconciliation["single_country_records"]
            + reconciliation["shared_records"]
            + reconciliation["unattributed_records"]
        ) == reconciliation["public_total"]


# --------------------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    _seed(session, "Germany", "API A")
    _seed(session, "Germany", "API B")
    # A third German row, and it is what makes the catalogue's fully-funded
    # proportion computable at all: scholarship_coverage refuses a rate derived
    # from fewer than three records, because a proportion from two rows is noise
    # and dividing a tuition bill by noise is a precise answer to a shaky
    # question. Without this row the calculator correctly refuses `tuition_expected`
    # and the calculator test below would be asserting a refusal as though it were
    # a figure. Germany really does hold far more than three listed scholarships,
    # so this brings the fixture closer to reality rather than bending the rule.
    _seed(session, "Germany", "API C", fully_funded=False)
    _seed(session, "USA", "API D")
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


class TestCountryApi:
    def test_meta_publishes_the_status_vocabulary(self, client: TestClient):
        payload = client.get("/v2/countries/meta").json()
        assert "UNKNOWN" in payload["value_status"]
        assert payload["value_status_labels"]["OFFICIAL_GOVERNMENT"]
        assert "bachelor" in payload["study_levels"]

    def test_list_returns_measured_and_researched(self, client: TestClient):
        payload = client.get("/v2/countries").json()
        codes = {c["iso2"] for c in payload["countries"]}
        assert {"DE", "US"} <= codes
        germany = next(c for c in payload["countries"] if c["iso2"] == "DE")
        assert germany["measured"]["scholarships"] == 3
        assert germany["flag"]

    def test_detail_exposes_both_planes_and_the_reconciliation(self, client: TestClient):
        payload = client.get("/v2/countries/DE").json()
        assert payload["known"] is True
        assert payload["country"]["name"] == "Germany"
        assert payload["measured"]["scholarships"] == 3
        assert payload["measured"]["fully_funded"] == 2
        assert payload["reconciliation"]["populations_sum_to_public_total"] is True
        # The tuition headline used to read 0 here. That zero came from
        # make-it-in-germany.com's Skilled Immigration Act page - a visa page, with
        # no archived extract - and it reached the reader as though Germany charged
        # nothing, while the statutory Baden-Wuerttemberg fee was filed elsewhere
        # and unread. A refused figure has to reach the reader as a refusal, with
        # its reason, exactly as a declared gap does; publishing it as 0 is the
        # failure this assertion used to lock in.
        tuition = payload["headline"]["tuition_bachelor"]
        assert tuition["value"] is None
        assert tuition["value_status"] == "UNKNOWN"
        assert tuition["note"]

    def test_detail_publishes_gaps_rather_than_hiding_them(self, client: TestClient):
        """Declared gaps are a published part of the record, not an absence.

        Germany records nine figures it could not establish. Each one must reach
        the reader with its reason, because a country that silently omits what it
        could not research reads exactly like a country where nothing is missing.
        """
        payload = client.get("/v2/countries/DE").json()
        assert payload["gaps"], "Germany records deliberate gaps; they must be published"
        for gap in payload["gaps"]:
            assert gap["field"] and gap["reason"], gap
        # A declared gap is not an implied zero: the affected headline figure is
        # published as not-established with a reason, never as 0.
        salary = payload["headline"]["starting_salary"]
        assert salary["value"] is None
        assert salary["value_status"] == "UNKNOWN"
        assert salary["note"]

    def test_gaps_and_missing_sections_are_different_facts(self, client: TestClient):
        """Germany has all seven sections researched and still declares nine gaps.

        ``missing_sections`` means "this block was never researched";
        ``gaps`` means "this block exists and something inside it could not be
        established". Collapsing the two would either hide gaps in researched
        sections or imply a whole section was unresearched when only one figure in
        it was.
        """
        payload = client.get("/v2/countries/DE").json()
        assert payload["missing_sections"] == []
        assert set(payload["researched_sections"]) == set(corpus_module.SECTION_NAMES)
        assert len(payload["gaps"]) >= 5

    def test_detail_of_a_researched_but_unmeasured_country(
        self, client: TestClient, monkeypatch, tmp_path: Path
    ):
        """Research and catalogue are separate planes; either may be absent alone.

        A country can be researched with no listed scholarships. That is a real
        state - the Netherlands holds scholarships we have not indexed - and it is
        not an error, so the country must stay visible with its research intact and
        its measured figures reported as absent rather than zero.

        The corpus is injected explicitly rather than relying on whatever files
        happen to be in the repository directory. A test that reads a directory
        another test writes to is not testing the case it names: it is testing
        whichever files existed when it ran.
        """
        researched_only = _valid_file()
        researched_only["country"] = {
            "iso2": "NL", "name_en": "Example Researched Only", "currency": "EUR",
        }
        (tmp_path / "NL.json").write_text(json.dumps(researched_only), encoding="utf-8")
        monkeypatch.setattr(
            service_module, "get_corpus", lambda: corpus_module.load_corpus(tmp_path)
        )

        payload = client.get("/v2/countries/NL").json()
        assert payload["known"] is True
        assert payload["country"]["iso2"] == "NL"
        # Measured figures must be absent, not zero.
        assert payload["measured"] is None
        # Research must still be served.
        assert payload["sources"]
        assert payload["sections"]["one_time_costs"]["visa_fee"]["value"] == 75
        assert payload["gaps"]

    def test_a_country_with_neither_plane_is_not_a_profile(
        self, client: TestClient, monkeypatch, tmp_path: Path
    ):
        """Neither researched nor measured means there is nothing to show.

        Rendering an empty card here would promise intelligence we do not have.
        """
        monkeypatch.setattr(
            service_module, "get_corpus", lambda: corpus_module.load_corpus(tmp_path / "absent")
        )
        payload = client.get("/v2/countries/ZZ").json()
        assert payload["known"] is False
        assert payload["country"] is None

    def test_unknown_country_is_not_an_error(self, client: TestClient):
        payload = client.get("/v2/countries/ZZ").json()
        assert payload["known"] is False and payload["country"] is None

    def test_calculate_returns_refusals_alongside_figures(self, client: TestClient):
        """The calculator returns figures *and* refusals in one response.

        Neither half is optional. Dropping the refusals would present an
        incomplete total as a complete one; dropping the figures would be no
        better than refusing the whole request over one missing component. A
        student budgeting from this needs to see which parts are known and which
        are not.
        """
        payload = client.post(
            "/v2/countries/calculate",
            json={"iso2": "DE", "study_level": "bachelor", "city_tier": "medium"},
        ).json()
        results = {r["key"]: r for r in payload["results"]}

        # Germany has no national public Bachelor tuition figure that its evidence
        # supports. The only national claim was a EUR 0/year sourced from a visa
        # page with no archived extract, and the zero rule now refuses it, so the
        # tuition derivation refuses too.
        #
        # This assertion used to require a DERIVED zero, and the reason it could
        # produce one is the defect: a zero looks like an answer, so an unearned
        # zero understates a budget instead of refusing one. Refusing here is the
        # safe direction. The test's actual claim - that a response carries real
        # figures *and* explicit refusals together - is now demonstrated by
        # ``one_time_total`` below, which is genuinely derived.
        tuition = results["tuition_expected"]
        assert tuition["status"] == "NOT_DERIVED"
        # A refusal omits the value key rather than publishing a null figure.
        assert tuition.get("value") is None
        assert tuition["refusal"]

        # The blocked account is sourced, so the one-time total computes.
        assert results["one_time_total"]["value_status"] == "DERIVED"

        # Germany's medium city-tier living cost is a declared gap, so living cost
        # must refuse rather than fall back to a number.
        living = results["living_annual"]
        assert living["status"] == "NOT_DERIVED"
        assert living["refusal"]

        # A partial total would understate the cost, so the programme total refuses.
        assert results["total_investment"]["status"] == "NOT_DERIVED"

        # Germany has no sourced net income, so break-even must refuse rather than
        # divide a gross salary into an after-tax cost.
        assert results["break_even_months"]["status"] == "NOT_DERIVED"
        assert results["break_even_months"]["reason"]

    def test_calculate_rejects_an_unknown_level(self, client: TestClient):
        response = client.post(
            "/v2/countries/calculate", json={"iso2": "DE", "study_level": "diploma"}
        )
        assert response.status_code == 422

    def test_calculate_rejects_unknown_fields(self, client: TestClient):
        response = client.post(
            "/v2/countries/calculate", json={"iso2": "DE", "university": "MIT"}
        )
        assert response.status_code == 422

    def test_compare_requires_two_countries(self, client: TestClient):
        assert client.post("/v2/countries/compare", json={"iso2": ["DE"]}).status_code == 422

    def test_compare_declares_no_winner(self, client: TestClient):
        """Countries are quoted in their own currencies, so ranking them would say
        something the data cannot support."""
        payload = client.post(
            "/v2/countries/compare", json={"iso2": ["DE", "US", "GB"]}
        ).json()
        assert "winner_policy" in payload
        assert not any("winner" in row for row in payload["rows"])

    def test_flag_is_derived_from_the_code(self):
        """X is the 23rd letter, so U+1F1E6 + 23 = U+1F1FD."""
        assert flag_emoji("DE") == "\U0001F1E9\U0001F1EA"
    assert flag_emoji("XX") == "\U0001F1FD\U0001F1FD"
    assert flag_emoji("DEU") is None

