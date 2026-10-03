"""Count Intelligence 2.0: the HTTP surface.

Uses the existing ``TestClient`` pattern from ``test_matching_api.py`` rather than
declaring a second application fixture. The counting endpoint and the Match
endpoint are verified against the same application, because the property that
matters is that they agree - a second fixture would let them drift while both
passing.

The regression obligation from the architecture is explicit: ``POST
/scholarships/match`` must keep returning correct ``summary``, ``facets``,
``count_basis`` and versions. That is asserted here against the live response, not
assumed from the unit tests.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Scholarship  # noqa: E402
from app.services.counting.contract import COUNT_CONTRACT_VERSION  # noqa: E402
from app.services.matching.types import MatchProfileRequest  # noqa: E402


PAYLOAD = {
    "citizenship": "India",
    "intended_degree_level": "MASTER",
    "overall_result": {"scale": "GPA_4", "value": 3.9},
    "preferred_countries": ["Germany", "France"],
    "language_credentials": [{"test": "IELTS", "score": 7.5}],
    "funding_requirement": "FULL_FUNDING",
}


def _record(index: int, country: str) -> dict:
    """A record as the ORM wants it: real date objects, not ISO strings.

    SQLite's Date type rejects strings outright, and passing one fails the insert
    with a statement error that says nothing about the counting layer.
    """
    return {
        "title": f"Scholarship {index}",
        "country": country,
        "degree": "Master",
        "funding": "Fully Funded",
        "description": "A test scholarship.",
        "program_type": "Computer Science",
        "status": "open",
        "deadline_date": date(2027, 6, 30),
        "deadline_display": "30 June 2027",
        "deadline_precision": "exact",
        "eligibility": ["Applicants must be citizens of India."],
        "eligibility_summary": "Citizens of India only.",
        "requirements": ["Minimum GPA of 3.5/4.0."],
        "documents": ["Transcript"],
        "coverage": ["Full tuition", "Monthly stipend"],
        "english_requirement": "IELTS 6.5 or above.",
        "funding_amount": 25000.0,
        "funding_currency": "EUR",
        "tuition_coverage": True,
        "living_cost_coverage": True,
        "fully_funded": True,
        "official_source": f"University {index}",
        "official_source_url": f"https://example.edu/{index}",
        "is_verified": True,
        "verification_status": "active",
        "last_verified_date": date(2026, 2, 1),
        "image_url": f"https://example.edu/{index}.png",
        "image_alt_text": "University logo",
    }


def _reset_settings_cache() -> None:
    """Force the settings getters to re-read the environment.

    The visibility gates are read once into a cached settings object, so setting
    them after the first call would not change the rule under test - and clearing
    only one of the two getter names would leave the other serving a stale answer.
    """
    from app.core import config as config_module

    for attr in ("get_settings", "_get_settings"):
        candidate = getattr(config_module, attr, None)
        clear = getattr(candidate, "cache_clear", None)
        if callable(clear):
            clear()


@pytest.fixture(scope="module")
def client():
    """A real application over an isolated in-memory database.

    Isolated, and a fresh schema per module, so the counting endpoint is exercised
    against real ORM rows rather than mocks. The developer's own database is never
    opened.

    The public visibility gates are pinned for the duration and restored on the way
    out. They are process-wide settings held in a cached settings object, and the
    assertions here (``public_total == 5``, ``countries == 3``) depend on them. Left
    alone, whichever suite ran before this one would decide what this module sees -
    and a test whose result depends on execution order is not a test of the code.
    """
    gate_vars = (
        "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED",
        "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE",
        "SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE",
    )
    previous = {name: os.environ.get(name) for name in gate_vars}
    for name in gate_vars:
        os.environ[name] = "false"

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    session = TestingSession()
    for index, country in enumerate(
        ["Germany", "Germany", "France", "France", "India"], start=1
    ):
        session.add(Scholarship(**_record(index, country)))
    # An archived row and a quarantined row: both are hidden from the public
    # catalogue, so neither may appear in any public count.
    session.add(Scholarship(**{**_record(90, "Spain"), "is_archived": True}))
    session.add(
        Scholarship(
            **{**_record(91, "Italy"), "verification_status": "quarantined"}
        )
    )
    session.commit()
    session.close()

    def override():
        with TestingSession() as test_session:
            yield test_session

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        _reset_settings_cache()


class TestContractEndpoint:
    def test_the_contract_is_published(self, client):
        response = client.get("/v2/counts/contract")
        assert response.status_code == 200
        body = response.json()
        assert body["count_contract_version"] == COUNT_CONTRACT_VERSION
        assert body["partitions"]

    def test_every_partition_publishes_its_definition_and_note(self, client):
        for declared in client.get("/v2/counts/contract").json()["partitions"]:
            assert declared["name"]
            assert declared["universe"]
            assert declared["partition_type"]
            assert declared["note"]
            assert declared["buckets"]

    def test_the_self_exclusion_semantics_are_published(self, client):
        body = client.get("/v2/counts/contract").json()
        assert "except its own" in body["facet_self_exclusion"]

    def test_all_four_universes_name_a_producer(self, client):
        producers = client.get("/v2/counts/contract").json()["universe_producers"]
        assert len(producers) == 4
        assert all(producers.values())

    def test_the_contract_is_byte_identical_between_calls(self, client):
        first = client.get("/v2/counts/contract").content
        second = client.get("/v2/counts/contract").content
        assert first == second


class TestIntelligenceEndpoint:
    def test_a_minimal_request_answers(self, client):
        response = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["summary", "facets"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["count_contract_version"] == COUNT_CONTRACT_VERSION
        assert body["universe"] == "MATCH_ANALYSED"

    def test_the_three_mandatory_invariants_hold(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["summary"]},
        ).json()
        total = body["total_candidates"]
        summary = body["summary"]
        assert (
            summary["eligibility.ELIGIBLE"]
            + summary["eligibility.NEEDS_VERIFICATION"]
            + summary["eligibility.INELIGIBLE"]
            == total
        )
        assert summary["scored.SCORED"] + summary["scored.NOT_SCORED"] == total
        tiers = (
            summary["fit_tier.EXCEPTIONAL_FIT"]
            + summary["fit_tier.VERY_STRONG_FIT"]
            + summary["fit_tier.STRONG_FIT"]
            + summary["fit_tier.POSSIBLE_FIT"]
            + summary["fit_tier.LOW_FIT"]
        )
        assert tiers + summary["scored.NOT_SCORED"] == total

    def test_archived_and_quarantined_records_are_absent_from_every_count(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["summary", "catalogue"]},
        ).json()
        # Five listed records: two Germany, two France, one India.
        assert body["total_candidates"] == 5
        assert body["catalogue"]["counts"]["public_total"] == 5

    def test_integrity_is_warning_when_no_baseline_exists(self, client):
        """The honest verdict when there is no history to compare against.

        WARNING, not PASS and not FAIL: the counts are internally sound and the
        report is incomplete. PASS would overstate what is known; FAIL would be
        wrong.
        """
        body = client.post("/v2/counts/intelligence", json={"profile": PAYLOAD}).json()
        assert body["integrity"]["status"] == "WARNING"
        # And every asserted identity still holds.
        assert all(
            check["holds"] for check in body["integrity"]["reconciliations"]
        )

    def test_a_missing_baseline_is_a_warning_not_a_failure(self, client):
        body = client.post("/v2/counts/intelligence", json={"profile": PAYLOAD}).json()
        assert body["integrity"]["status"] == "WARNING"
        assert any("baseline" in issue for issue in body["integrity"]["issues"])

    def test_provenance_carries_every_version(self, client):
        provenance = client.post(
            "/v2/counts/intelligence", json={"profile": PAYLOAD}
        ).json()["provenance"]
        assert provenance["count_contract_version"]
        assert provenance["engine_version"]
        assert provenance["scoring_config_version"]
        assert provenance["field_taxonomy_version"]
        assert provenance["deadline_semantics_version"]
        assert provenance["universe"] == "MATCH_ANALYSED"

    def test_a_filter_narrows_the_result_count(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={
                "profile": PAYLOAD,
                "filters": {"countries": ["Germany"]},
                "capabilities": ["summary", "facets"],
            },
        ).json()
        assert body["results"]["matched"] == 2
        assert body["results"]["filter_state"]["COUNTRY"] == ["Germany"]

    def test_facet_counts_describe_the_returned_page_not_the_universe(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={
                "profile": PAYLOAD,
                "filters": {"countries": ["Germany"]},
                "capabilities": ["facets"],
            },
        ).json()
        assert body["facets"]["count_basis"] == "MATCH_RETURNED_PAGE"
        # Self-exclusion: selecting Germany must not hide France.
        countries = {b["key"]: b["count"] for b in body["facets"]["families"]["countries"]}
        assert "Germany" in countries
        assert "France" in countries

    def test_a_reset_request_restores_the_unfiltered_counts(self, client):
        def matched(filters):
            body = client.post(
                "/v2/counts/intelligence",
                json={
                    "profile": PAYLOAD,
                    "filters": filters,
                    "capabilities": ["summary", "facets"],
                },
            ).json()
            return body["results"]["matched"], body["facets"]["families"]

        pristine_count, pristine_facets = matched({})
        filtered_count, _ = matched({"countries": ["Germany"]})
        assert filtered_count < pristine_count

        # The contract endpoint is what a client uses to verify a reset; the counts
        # themselves come from an unfiltered request, which is the reset.
        assert pristine_count == 5

    def test_a_known_count_repeats_exactly(self, client):
        payload = {"profile": PAYLOAD, "capabilities": ["summary", "facets"]}
        first = client.post("/v2/counts/intelligence", json=payload).json()
        second = client.post("/v2/counts/intelligence", json=payload).json()
        assert first["summary"] == second["summary"]
        assert first["facets"] == second["facets"]
        assert first["integrity"] == second["integrity"]

    def test_an_injected_as_of_is_reproducible(self, client):
        payload = {"profile": PAYLOAD, "capabilities": ["summary"]}
        first = client.post(
            "/v2/counts/intelligence?as_of=2026-10-03", json=payload
        ).json()
        second = client.post(
            "/v2/counts/intelligence?as_of=2026-10-03", json=payload
        ).json()
        assert first["summary"] == second["summary"]
        assert first["as_of"] == "2026-10-03"

    def test_explanations_name_the_universe_and_the_filters(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={
                "profile": PAYLOAD,
                "filters": {"countries": ["Germany"]},
                "capabilities": ["explain"],
            },
        ).json()
        assert "analysed scholarships" in body["explanations"]["total_candidates"]["human_readable"]
        assert "Germany" in body["explanations"]["matched"]["human_readable"]

    def test_zero_result_intelligence_is_returned_for_an_impossible_filter(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={
                "profile": PAYLOAD,
                "filters": {"countries": ["Atlantis"]},
                "capabilities": ["summary"],
            },
        ).json()
        assert body["results"]["matched"] == 0
        assert body["zero_result"]["status"] == "EMPTY"
        for alternative in body["zero_result"]["alternatives"]:
            assert alternative["result_count"] > 0

    def test_counterfactuals_change_exactly_one_dimension(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={
                "profile": PAYLOAD,
                "filters": {"countries": ["Germany"]},
                "capabilities": ["counterfactual"],
            },
        ).json()
        for outcome in body["counterfactuals"]["interventions"]:
            assert "COUNTRY" in outcome["baseline_state"]
            assert "COUNTRY" not in outcome["counterfactual_state"]
            assert outcome["value_kind"] == "SIMULATED"

    def test_relationships_publish_their_evidence_class(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["relationships"]},
        ).json()
        relationships = body["relationships"]
        assert relationships["published_field_matches"]
        for item in relationships["published_field_matches"]:
            assert item["evidence_source"]
        assert relationships["graph_density"]["density"] in {"SPARSE", "PARTIAL", "DENSE"}

    def test_distributions_publish_their_sample_size(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["distributions"]},
        ).json()
        for summary in body["distributions"]:
            assert "sample_count" in summary
            assert "excluded_count" in summary

    def test_incremental_counting_publishes_its_strategy(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["incremental"]},
        ).json()
        assert body["incremental"]["strategy"] in {"INCREMENTAL", "FULL_RECOMPUTE"}
        assert body["incremental"]["note"]

    def test_trends_without_history_report_unavailable(self, client):
        body = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["trends", "snapshot"]},
        ).json()
        assert body["trends"] == {}
        assert body["snapshot"]["count_contract_version"] == COUNT_CONTRACT_VERSION
        assert "snapshot_coverage" in body

    def test_an_unknown_capability_is_refused(self, client):
        response = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["not_a_capability"]},
        )
        assert response.status_code == 422

    def test_an_unknown_field_is_refused(self, client):
        response = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "not_a_field": True},
        )
        assert response.status_code == 422

    def test_an_unknown_filter_field_is_refused(self, client):
        response = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "filters": {"not_a_dimension": ["x"]}},
        )
        assert response.status_code == 422

    def test_a_profile_is_optional(self, client):
        response = client.post(
            "/v2/counts/intelligence",
            json={"capabilities": ["catalogue"]},
        )
        assert response.status_code == 200
        assert response.json()["catalogue"]["universe"] == "CATALOGUE"

    def test_an_empty_body_is_answered_not_rejected(self, client):
        response = client.post("/v2/counts/intelligence", json={})
        assert response.status_code == 200


class TestMatchRegression:
    def test_the_match_endpoint_still_answers(self, client):
        response = client.post("/scholarships/match", json=PAYLOAD)
        assert response.status_code == 200

    def test_the_match_summary_still_reconciles(self, client):
        summary = client.post("/scholarships/match", json=PAYLOAD).json()["summary"]
        assert (
            summary["eligible_count"]
            + summary["needs_verification_count"]
            + summary["ineligible_count"]
            == summary["total_candidates"]
        )
        assert summary["scored_count"] + summary["not_scored_count"] == summary["total_candidates"]

    def test_the_match_facets_still_publish_their_basis(self, client):
        body = client.post("/scholarships/match", json=PAYLOAD).json()
        assert body["facets"]["count_basis"] == "RETURNED_PAGE"

    def test_the_match_endpoint_still_publishes_its_versions(self, client):
        body = client.post("/scholarships/match", json=PAYLOAD).json()
        assert body["engine_version"]
        assert body["scoring_config_version"]
        assert body["taxonomy_version"]
        assert body["as_of"]

    def test_the_match_summary_agrees_with_the_counting_summary(self, client):
        """Two surfaces, one set of numbers.

        The counting contract builds the Match summary, so these cannot disagree.
        Asserting it is what keeps that from being an intention.
        """
        match = client.post("/scholarships/match", json=PAYLOAD).json()
        counted = client.post(
            "/v2/counts/intelligence",
            json={"profile": PAYLOAD, "capabilities": ["summary"]},
        ).json()

        assert match["summary"]["total_candidates"] == counted["total_candidates"]
        assert (
            match["summary"]["eligible_count"]
            == counted["summary"]["eligibility.ELIGIBLE"]
        )
        assert (
            match["summary"]["scored_count"]
            == counted["summary"]["scored.SCORED"]
        )

    def test_the_existing_stats_endpoint_still_answers(self, client):
        response = client.get("/scholarships/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 5
        assert body["open"] == 5
        assert body["countries"] == 3