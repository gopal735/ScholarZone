"""Global Study-to-Career Strategist tests.

These tests exist to hold the seven data-integrity rules that the feature states
as non-negotiable, so each is asserted against fixtures with missing, stale,
conflicting and partial data. The API tests follow the established in-memory
StaticPool + ``dependency_overrides`` pattern, and the flag-off behaviour of the
real app is asserted so a default deployment never exposes the feature.
"""

from __future__ import annotations

import os

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")
os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")  # noqa: E402

import json  # noqa: E402
import tempfile  # noqa: E402
from datetime import date  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app as main_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.routers.strategist import router as strategist_router  # noqa: E402
from app.services.country_intelligence import fx  # noqa: E402
from app.services.country_intelligence.occupation_salary import (  # noqa: E402
    OccupationSalaryError,
    get_verified_occupation_salary,
    reload_verified_cells,
)
from app.services.strategist.service import (  # noqa: E402
    ValidationError,
    coverage_matrix,
    pathway_timeline,
    plan,
)


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db():
        yield session

    test_app = FastAPI()
    test_app.include_router(strategist_router)
    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as test_client:
        yield test_client
    session.close()


# --------------------------------------------------------------------------
# Rule 1: UNKNOWN/missing is never 0, never averaged, never sorted as lowest/highest.
# --------------------------------------------------------------------------

def test_missing_tuition_is_insufficient_not_zero():
    res = plan(None, subject_key="civil_engineering", degree="master")
    ca = next(c for c in res["comparison"] + res["insufficient_data"] if c["iso2"] == "CA")
    tuition = ca["cells"]["tuition"]
    assert tuition["status"] == "insufficient"
    assert tuition["value"] is None, "a missing tuition must never be published as 0"
    assert (tuition.get("bdt") or {}).get("value") is None
    assert tuition["reason"], "insufficient cells must carry the reason"


def test_insufficient_cells_never_render_a_number():
    res = plan(None, subject_key="computer_science", degree="master", iso2s=["US"])
    us = (res["comparison"] + res["insufficient_data"])[0]
    for key, cell in us["cells"].items():
        if cell["status"] != "sourced":
            assert cell["value"] is None, f"{key} published a value while insufficient"
            assert (cell.get("bdt") or {}).get("value") is None


# --------------------------------------------------------------------------
# Rule 2: essential missing => no overall rank; never claim a universal best.
# --------------------------------------------------------------------------

def test_essential_missing_country_is_not_ranked():
    # US is the best-covered for salary but the corpus holds no post-study-work
    # step, so it must fall to insufficient_data, not be ranked or called best.
    res = plan(None, subject_key="computer_science", degree="master", iso2s=["US"])
    assert [c["iso2"] for c in res["comparison"]] == []
    us = res["insufficient_data"][0]
    assert us["ranked"] is False
    assert us["not_ranked_reason"]
    # No country object may carry a "best"/"recommended-overall" badge.
    for c in res["comparison"] + res["insufficient_data"]:
        assert "best" not in {k for k in c} and "top_country" not in c


def test_no_single_magic_score_is_published():
    res = plan(None, subject_key="civil_engineering", degree="master")
    for c in res["comparison"]:
        assert "score" not in c and "overall_score" not in c
    assert res["ranking_rule"]
    # The weights the user controls are echoed back unchanged and visibly.
    assert set(res["request"]["weights"]) == {"cost", "funding", "career", "pathway"}


# --------------------------------------------------------------------------
# Rule 3: tuition/living/scholarship/stipend/gross/net kept separate.
# --------------------------------------------------------------------------

def test_money_dimensions_are_separate_cells_not_summed():
    res = plan(None, subject_key="civil_engineering", degree="master", iso2s=["CA"])
    cells = res["insufficient_data"][0]["cells"] if not res["comparison"] else res["comparison"][0]["cells"]
    keys = set(cells)
    assert {"tuition", "living_cost", "subject_salary"} <= keys
    # No cell is a merged total of these; each is its own criterion.
    for key in ("tuition", "living_cost", "subject_salary"):
        assert cells[key]["criterion"] == key
    # Subject salary is gross and never presented as net/take-home.
    sal = cells["subject_salary"]
    assert sal["basis"] == "gross"
    assert "take-home" not in json.dumps(sal).lower() or "not" in json.dumps(sal).lower()


def test_subject_salary_bdt_is_a_scaled_copy_not_a_sum():
    res = plan(None, subject_key="civil_engineering", degree="master", iso2s=["CA"])
    chosen = res["comparison"][0] if res["comparison"] else res["insufficient_data"][0]
    sal = chosen["cells"]["subject_salary"]
    assert sal["status"] == "sourced"
    assert sal["bdt"]["value"] is not None
    assert sal["bdt"]["from_currency"] == "CAD"


# --------------------------------------------------------------------------
# Rule 4: subject salary only from occupation-level source; country average never
# presented as subject-level.
# --------------------------------------------------------------------------

def test_missing_subject_salary_is_not_backfilled_from_country_average():
    # Ireland has no occupation-level pay; the cell must say so, with a reason
    # that refuses the country-average substitution.
    res = plan(None, subject_key="computer_science", degree="master", iso2s=["IE"])
    ie = (res["comparison"] + res["insufficient_data"])[0]
    cell = ie["cells"]["subject_salary"]
    assert cell["status"] == "insufficient"
    assert "not a subject-level figure" in cell["reason"] or "country average" in cell["reason"]
    assert cell["value"] is None


def test_subject_salary_carries_granularity_and_source():
    res = plan(None, subject_key="computer_science", degree="master", iso2s=["US"])
    us = (res["comparison"] + res["insufficient_data"])[0]
    sal = us["cells"]["subject_salary"]
    assert sal["status"] == "sourced"
    assert sal["granularity"] in {"occupation", "occupation-class"}
    assert sal["sources"][0]["url"].startswith("http")
    assert sal["occupation_code"]


# --------------------------------------------------------------------------
# Rule 5: scholarship/subject linkage (funding stays degree-level count, never a
# currency, never claimed subject-specific).
# --------------------------------------------------------------------------

def test_funding_is_a_count_not_currency_and_not_subject_labelled():
    res = plan(None, subject_key="computer_science", degree="master", iso2s=["CA"])
    chosen = res["comparison"][0] if res["comparison"] else res["insufficient_data"][0]
    funding = chosen["cells"]["funding_opportunities"]
    assert funding["currency"] is None
    assert funding["per"] in (None, "fully-funded listings")


# --------------------------------------------------------------------------
# Rule 6: no fabricated admission/visa/citizenship outcomes.
# --------------------------------------------------------------------------

def test_pathway_steps_have_source_or_reason_and_disclaimer():
    timeline = pathway_timeline("DE")
    assert timeline["disclaimer"]
    for step in timeline["steps"]:
        assert step["status"] in {"sourced", "informational", "insufficient"}
        if step["status"] == "insufficient":
            assert step["reason"]
        else:
            # A sourced/informational step either links to an official source or
            # records, per rule 7, that no source link is attached.
            assert (step["official_link"] or step["sources"]
                    or step.get("source_missing_reason"))


def test_no_visa_or_admission_probability_is_fabricated():
    res = plan(None, subject_key="computer_science", degree="master", iso2s=["CA"])
    blob = json.dumps(res).lower()
    for forbidden in ("approval probability", "chance of", "admission likelihood", "guaranteed visa"):
        assert forbidden not in blob, f"strategist must not fabricate {forbidden!r}"


# --------------------------------------------------------------------------
# Rule 7: every fact carries source/date/status; stale data warns.
# --------------------------------------------------------------------------

def test_facts_carry_source_date_and_status():
    res = plan(None, subject_key="computer_science", degree="master", iso2s=["US"])
    us = (res["comparison"] + res["insufficient_data"])[0]
    sal = us["cells"]["subject_salary"]
    assert sal["value_status"] == "OFFICIAL_STATISTICS"
    assert sal["sources"] and sal["sources"][0]["url"]
    assert sal["as_of"]


def test_stale_cell_warns_when_reference_date_is_far_future():
    res = plan(
        None, subject_key="computer_science", degree="master", iso2s=["US"],
        reference_date=date(2099, 1, 1), stale_after_days=730,
    )
    us = (res["comparison"] + res["insufficient_data"])[0]
    sal = us["cells"]["subject_salary"]
    assert sal["freshness"] == "STALE"
    assert sal["stale_warning"] is True


# --------------------------------------------------------------------------
# Occupation-salary loader guards (gross-only, official-only, PENDING excluded).
# --------------------------------------------------------------------------

def _write_verified(directory: Path, cells: dict) -> None:
    target = directory / "occupation_salary"
    target.mkdir(parents=True, exist_ok=True)
    (target / "verified.json").write_text(
        json.dumps({"by_country": cells}), encoding="utf-8"
    )


def test_net_basis_is_refused_by_the_loader():
    reload_verified_cells()
    with tempfile.TemporaryDirectory() as tmp:
        _write_verified(Path(tmp), {"XX": {"computer_science": {
            "occupation_label": "x", "occupation_code": "c", "granularity": "occupation",
            "value": 100, "currency": "USD", "per": "year", "basis": "net",
            "metric": "median", "as_of": "2025", "verification": "PRIMARY_VERIFIED",
            "source": {"id": "x", "publisher": "x", "source_type": "OFFICIAL_STATISTICS", "url": "https://x"}
        }}})
        assert get_verified_occupation_salary("XX", "computer_science", directory=Path(tmp)) is None


def test_non_official_source_is_refused_by_the_loader():
    reload_verified_cells()
    with tempfile.TemporaryDirectory() as tmp:
        _write_verified(Path(tmp), {"XX": {"computer_science": {
            "occupation_label": "x", "occupation_code": "c", "granularity": "occupation",
            "value": 100, "currency": "USD", "per": "year", "basis": "gross",
            "metric": "median", "as_of": "2025", "verification": "PRIMARY_VERIFIED",
            "source": {"id": "x", "publisher": "Employer survey", "source_type": "AGGREGATOR", "url": "https://x"}
        }}})
        assert get_verified_occupation_salary("XX", "computer_science", directory=Path(tmp)) is None


def test_pending_cell_is_excluded():
    reload_verified_cells()
    with tempfile.TemporaryDirectory() as tmp:
        _write_verified(Path(tmp), {"XX": {"computer_science": {
            "occupation_label": "x", "occupation_code": "c", "granularity": "occupation",
            "value": 100, "currency": "USD", "per": "year", "basis": "gross",
            "metric": "median", "as_of": "2025", "verification": "PENDING",
            "source": {"id": "x", "publisher": "x", "source_type": "OFFICIAL_STATISTICS", "url": "https://x"}
        }}})
        assert get_verified_occupation_salary("XX", "computer_science", directory=Path(tmp)) is None
    reload_verified_cells()


# --------------------------------------------------------------------------
# BDT FX wiring: composed sourced legs; refused when a leg is missing.
# --------------------------------------------------------------------------

def test_bdt_conversion_publishes_both_sourced_legs():
    result = fx.convert_to_bdt(100, "USD")
    steps = {leg["step"] for leg in result["legs"]}
    assert result["value"] > 0
    assert "bdt" in steps  # Bangladesh Bank leg
    bdt_leg = next(leg for leg in result["legs"] if leg["step"] == "bdt")
    assert bdt_leg["rate_date"] == "2026-10-11"
    assert "bb.org.bd" in bdt_leg["source_url"]


def test_bdt_conversion_bridges_via_ecb_from_a_non_usd_currency():
    result = fx.convert_to_bdt(200, "EUR")
    steps = {leg["step"] for leg in result["legs"]}
    assert "bridge" in steps and "bdt" in steps
    bridge = next(leg for leg in result["legs"] if leg["step"] == "bridge")
    assert bridge["rate_date"] == "2026-10-02"  # the ECB leg keeps its own date
    assert result["value"] > 0


def test_bdt_conversion_refuses_unsourced_currency():
    with pytest.raises(fx.FxUnavailable):
        fx.convert_to_bdt(100, "ZZZ")


def test_bdt_passthrough_does_not_invent_a_rate():
    result = fx.convert_to_bdt(500, "BDT")
    assert result["value"] == 500


# --------------------------------------------------------------------------
# Input validation.
# --------------------------------------------------------------------------

def test_plan_rejects_unknown_subject():
    with pytest.raises(ValidationError):
        plan(None, subject_key="underwater_basket_weaving", degree="master")


def test_plan_rejects_unknown_degree():
    with pytest.raises(ValidationError):
        plan(None, subject_key="computer_science", degree="doctorate")


# --------------------------------------------------------------------------
# API layer.
# --------------------------------------------------------------------------

def test_api_subjects(client):
    body = client.get("/v2/strategist/subjects").json()
    assert {"computer_science", "data_science", "civil_engineering"} <= {s["key"] for s in body["subjects"]}


def test_api_plan_happy(client):
    body = client.post("/v2/strategist/plan", json={
        "subject_key": "civil_engineering", "degree": "master",
        "budget_bdt": 3000000, "weights": {"career": 40, "cost": 20},
    }).json()
    assert body["criteria"] and body["request"]["subject_key"] == "civil_engineering"
    assert "disclaimer" in body


def test_api_plan_rejects_bad_subject(client):
    assert client.post("/v2/strategist/plan", json={
        "subject_key": "nope", "degree": "master",
    }).status_code == 422


def test_api_pathway(client):
    body = client.get("/v2/strategist/pathway/DE").json()
    assert body["iso2"] == "DE" and body["steps"]


def test_api_gaps_reports_matrix(client):
    body = client.get("/v2/strategist/gaps").json()
    assert any(gap["country_iso2"] == "IE" and gap["subject_key"] == "data_science" for gap in body["gaps"])


# --------------------------------------------------------------------------
# The real app must NOT expose the strategist unless the flag is on (default OFF).
# --------------------------------------------------------------------------

def test_strategist_routes_absent_by_default():
    paths = {getattr(route, "path", "") for route in main_app.routes}
    assert not any(p.startswith("/v2/strategist") for p in paths), (
        "the strategist must not be registered while the flag defaults OFF"
    )
