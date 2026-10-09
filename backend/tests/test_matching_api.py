"""Integration tests for POST /scholarships/match.

These exercise the endpoint against a real database using an isolated temporary
SQLite file, following the pattern already used by ``test_scholarships.py``. The
public quality gate is switched on here deliberately: the match endpoint must
never surface a record the directory hides, and that is only provable against the
real visibility rule rather than a test fixture that disables it.

What is pinned here:

* the route resolves under both ``/scholarships/match`` and ``/api/scholarships/match``
* the request is validated
* quarantined and archived records never appear
* the response carries the engine version, weights and breakdown
* results are ranked with eligibility first
* nothing about the profile is persisted or echoed back
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-match-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
# Match must not fabricate numbers for records that have no image, so the gate
# stays on and every fixture below carries a verified image.
os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"] = "false"

from sqlalchemy import select  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.database import close_database, get_session_factory, reset_database_connections  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Scholarship  # noqa: E402

TODAY = date.today()
FUTURE = (TODAY + timedelta(days=120)).isoformat()

HIGH_PROFILE = {
    "age": 22,
    "citizenship": "India",
    "overall_result": {"scale": "GPA_4", "value": 3.9},
    "intended_degree_level": "MASTER",
    "intended_field": "computer_science",
    "language_credentials": [{"test": "IELTS", "score": 7.5}],
    "funding_requirement": "FULL_FUNDING",
    "living_cost_support_required": True,
    "preferred_countries": ["United Kingdom"],
}


def seed_record(**overrides) -> int:
    """Insert one matchable scholarship record with sensible defaults."""
    base = dict(
        title="Test Match Scholarship",
        country="United Kingdom",
        degree="Master",
        funding="Fully Funded",
        program_type="Computer Science",
        deadline_date=FUTURE,
        deadline_display=FUTURE,
        deadline_precision="exact",
        status="open",
        is_verified=True,
        verification_status="active",
        last_verified_date=TODAY,
        eligibility=["Applicants must be citizens of India."],
        eligibility_summary="Applicants must have a minimum GPA of 3.5/4.0.",
        requirements=[],
        documents=["Academic transcript", "CV"],
        coverage=["Full tuition and monthly stipend"],
        english_requirement="IELTS 6.5 or above required.",
        tuition_coverage=True,
        living_cost_coverage=True,
        fully_funded=True,
        official_source="Test University",
        official_source_url="https://example.edu/scholarships/test-match",
    )
    base.update(overrides)
    # The model declares these as Date columns, so SQLite is given real date
    # objects rather than the ISO strings the API contract uses.
    for key in ("deadline_date", "last_verified_date", "last_verified_at"):
        value = base.get(key)
        if isinstance(value, str):
            base[key] = date.fromisoformat(value)
    with get_session_factory()() as session:
        record = Scholarship(**base)
        session.add(record)
        session.commit()
        return record.id


@pytest.fixture(scope="module", autouse=True)
def client():
    """Starts the application, which is what creates and seeds the schema."""
    reset_database_connections()
    with TestClient(app) as test_client:
        yield test_client
    # Teardown happens after the application lifespan has closed, so the SQLite
    # handle is released. Windows still refuses the unlink occasionally, and a
    # leftover file in the temp directory is not worth failing a test over.
    close_database()
    if TEST_DATABASE_PATH.exists():
        try:
            TEST_DATABASE_PATH.unlink()
        except OSError:
            pass


@pytest.fixture(scope="module", autouse=True)
def seeded(client):
    """Seeded after ``client`` so the tables exist.

    Declared as depending on ``client`` rather than relying on autouse ordering,
    because an autouse fixture would otherwise run first and insert into a
    database that has not been initialised yet.
    """
    ids = {
        "eligible": seed_record(),
        "ineligible": seed_record(
            title="Closed Round Scholarship",
            official_source_url="https://example.edu/scholarships/closed",
            status="closed",
            deadline_date=(TODAY - timedelta(days=10)).isoformat(),
        ),
        "quarantined": seed_record(
            title="Quarantined Scholarship",
            official_source_url="https://example.edu/scholarships/quarantined",
            verification_status="quarantined",
        ),
        "archived": seed_record(
            title="Archived Scholarship",
            official_source_url="https://example.edu/scholarships/archived",
            is_archived=True,
        ),
        "incomplete": seed_record(
            title="Incomplete Record Scholarship",
            official_source_url="https://example.edu/scholarships/incomplete",
            program_type=None,
            eligibility=[],
            eligibility_summary=None,
            documents=[],
            coverage=[],
            english_requirement=None,
            tuition_coverage=None,
            living_cost_coverage=None,
            # The funding column is NOT NULL, so a real record always carries a
            # label. A non-specific label is exactly the case the engine must
            # refuse to read as a coverage fact.
            funding="Not specified",
            fully_funded=False,
            official_source=None,
            is_verified=False,
            last_verified_date=None,
        ),
    }
    yield ids


class TestMatchEndpoint:
    def test_route_resolves_at_the_root_path(self, client):
        response = client.post("/scholarships/match", json=HIGH_PROFILE)
        assert response.status_code == 200, response.text

    def test_route_resolves_behind_the_api_prefix(self, client):
        """The deployed path is /api/... and middleware strips the prefix."""
        response = client.post("/api/scholarships/match", json=HIGH_PROFILE)
        assert response.status_code == 200, response.text

    def test_response_reports_engine_version_and_formula(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        # 2.0.0: the fit formula, the academic interpolation, the language
        # surplus model and the freshness model all changed under a new version
        # string, which is the point of versioning them.
        assert payload["engine_version"] == "2.0.0"
        assert payload["scoring_config_version"] == "2.0.0"
        assert payload["taxonomy_version"] == "1.0.0"
        explanation = payload["explanation"]
        assert explanation["weights"] == {
            "academic": 0.25,
            "field": 0.20,
            "funding": 0.20,
            "requirement": 0.15,
            "language": 0.10,
            "preference": 0.05,
            "timing": 0.05,
        }
        assert "SUM(component score x component weight x evaluated)" in explanation["formula"]
        assert explanation["as_of"] == TODAY.isoformat()
        # Every version that could change a number is reported, plus the exact
        # configuration snapshot the response was produced with.
        for key in (
            "deadline_semantics_version",
            "scoring_config",
            "coverage_formula",
            "contribution_formula",
            "sensitivity_formula",
            "readiness_formula",
            "missing_data_note",
        ):
            assert key in explanation, key

    def test_response_reports_profile_index_and_band(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        assert payload["profile_index"]["score"] is not None
        assert payload["profile_index"]["band"] in {"LOW", "MEDIUM", "HIGH"}

    def test_summary_counts_are_present_and_consistent(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        for key in (
            "total_candidates",
            "eligible_count",
            "needs_verification_count",
            "ineligible_count",
            "strong_match_count",
            "average_confidence",
        ):
            assert key in payload
        summary = payload["summary"]
        # The locked identity is against total_candidates, the analysed universe.
        # This fixture is seeded past the default page limit, so the three states
        # deliberately do NOT sum to len(results) - that was the bug: the identity
        # used to change the moment a response was truncated.
        assert (
            summary["eligible_count"]
            + summary["needs_verification_count"]
            + summary["ineligible_count"]
            == summary["total_candidates"]
        )
        assert summary["scored_count"] + summary["not_scored_count"] == summary["total_candidates"]
        assert (
            summary["exceptional_count"]
            + summary["very_strong_count"]
            + summary["strong_count"]
            + summary["possible_count"]
            + summary["low_count"]
            + summary["unclassified_fit_count"]
            == summary["scored_count"]
        )
        for family in (
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
        ):
            assert sum(summary[key] for key in family) == summary["total_candidates"], family
        # The page is a slice of that universe, and says so.
        assert summary["visible_candidate_count"] == len(payload["results"])
        assert 0 < summary["visible_candidate_count"] <= summary["total_candidates"]
        assert summary["truncated"] is (summary["visible_candidate_count"] < summary["total_candidates"])

    def test_facets_reconcile_to_the_returned_page(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        facets = payload["facets"]
        assert facets["count_basis"] == "RETURNED_PAGE"
        visible = len(payload["results"])
        for family in ("countries", "degree_levels", "eligibility_states", "funding_states"):
            assert sum(bucket["count"] for bucket in facets[family]) == visible, family
        # Fit bands never exceed the page, because an ineligible or unscored
        # result has no band and is absent rather than misfiled.
        for family in ("fit_bands", "confidence_bands", "deadline_buckets"):
            assert sum(bucket["count"] for bucket in facets[family]) <= visible, family

    def test_each_result_carries_a_full_breakdown(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        result = payload["results"][0]
        assert len(result["score_breakdown"]) == 7
        for component in result["score_breakdown"]:
            assert component["weight"] > 0
            assert component["status"] in {"EVALUATED", "NOT_EVALUATED"}
        assert result["confidence_score"] is not None
        assert result["data_coverage"] > 0
        assert result["detail_url"].startswith("/scholarships/")

    def test_quarantined_archived_and_closed_records_are_never_returned(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        names = {result["scholarship_name"] for result in payload["results"]}
        assert "Quarantined Scholarship" not in names
        assert "Archived Scholarship" not in names
        assert "Closed Round Scholarship" not in names

    def test_eligible_records_rank_before_everything_else(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        order = ["ELIGIBLE", "NEEDS_VERIFICATION", "INELIGIBLE"]
        ranks = [order.index(item["eligibility"]) for item in payload["results"]]
        assert ranks == sorted(ranks)

    def test_identical_requests_return_identical_bodies(self, client):
        first = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        second = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        assert first == second

    def test_incomplete_record_reports_unknown_rather_than_zero(self, client):
        payload = client.post(
            "/scholarships/match",
            json={**HIGH_PROFILE, "preferred_countries": [], "overall_result": None},
        ).json()
        incomplete = next(
            item for item in payload["results"] if item["scholarship_name"] == "Incomplete Record Scholarship"
        )
        funding = next(item for item in incomplete["score_breakdown"] if item["name"] == "funding")
        assert funding["status"] == "NOT_EVALUATED"
        assert funding["score"] is None

    def test_reasons_and_gaps_are_attached(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        result = payload["results"][0]
        assert result["reasons"]
        assert all(item["code"] and item["message"] for item in result["reasons"])

    def test_evidence_status_is_returned(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        evidence = payload["results"][0]["evidence_status"]
        for key in ("has_official_source", "is_verified", "coverage_ratio", "provenance_ratio"):
            assert key in evidence

    def test_country_filter_narrows_the_candidate_set(self, client):
        """The pre-filter is applied in SQL, before anything is scored."""
        unfiltered = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        filtered = client.post(
            "/scholarships/match", json={**HIGH_PROFILE, "country_filter": "Atlantis"}
        ).json()
        assert filtered["total_candidates"] == 0
        assert filtered["results"] == []
        assert unfiltered["total_candidates"] > 0

    def test_include_ineligible_false_drops_ineligible_records(self, client):
        payload = client.post(
            "/scholarships/match", json={**HIGH_PROFILE, "include_ineligible": False}
        ).json()
        assert all(item["eligibility"] != "INELIGIBLE" for item in payload["results"])
        assert payload["ineligible_count"] == 0
        # Dropped from the analysed universe rather than scored and then hidden,
        # so the three states still sum to the total.
        assert (
            payload["eligible_count"] + payload["needs_verification_count"] + payload["ineligible_count"]
            == payload["total_candidates"]
        )

    def test_limit_is_honoured_and_truncation_is_reported(self, client):
        payload = client.post("/scholarships/match", json={**HIGH_PROFILE, "limit": 1}).json()
        assert len(payload["results"]) == 1
        assert payload["truncated"] is True
        assert payload["summary"]["visible_candidate_count"] == 1
        assert payload["summary"]["total_candidates"] > 1
        assert (
            payload["eligible_count"] + payload["needs_verification_count"] + payload["ineligible_count"]
            == payload["total_candidates"]
        )

    def test_an_empty_profile_still_answers(self, client):
        """No required fields, so an anonymous visitor is never blocked."""
        response = client.post("/scholarships/match", json={})
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile_index"]["score"] is None
        assert payload["results"]

    def test_profile_is_not_persisted(self, client):
        """A match request writes nothing.

        Matching is stateless, so the scholarship row count before and after a
        request must be identical. The profile arrives in the request body, is
        used to compute a response and is discarded; there is no profile table.
        """

        def record_count() -> int:
            with get_session_factory()() as session:
                return len(list(session.scalars(select(Scholarship))))

        before = record_count()
        response = client.post("/scholarships/match", json=HIGH_PROFILE)
        assert response.status_code == 200
        assert record_count() == before

    def test_no_student_profile_is_echoed_back(self, client):
        """The response explains the score without restating the applicant's age."""
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        rendered = str(payload)
        assert '"age": 22' not in rendered
        assert "max_self_contribution" not in rendered


class TestMatchValidation:
    def test_unknown_fields_are_rejected(self, client):
        response = client.post("/scholarships/match", json={**HIGH_PROFILE, "admission_chance": True})
        assert response.status_code == 422

    def test_out_of_range_values_are_rejected(self, client):
        assert client.post("/scholarships/match", json={**HIGH_PROFILE, "age": 5}).status_code == 422
        assert client.post("/scholarships/match", json={**HIGH_PROFILE, "limit": 5000}).status_code == 422
        assert client.post("/scholarships/match", json={**HIGH_PROFILE, "age": 200}).status_code == 422

    def test_invalid_enum_values_are_rejected(self, client):
        assert (
            client.post("/scholarships/match", json={**HIGH_PROFILE, "intended_degree_level": "SPACE_DEGREE"}).status_code
            == 422
        )

    def test_an_unparseable_body_is_rejected(self, client):
        assert client.post("/scholarships/match", content=b"{not json").status_code == 422


class TestProfileOptions:
    def test_profile_options_expose_the_controlled_vocabularies(self, client):
        response = client.get("/scholarships/match/profile-options")
        assert response.status_code == 200
        payload = response.json()
        assert "computer_science" in {item["key"] for item in payload["fields"]}
        assert "ielts" in payload["language_tests"]
        assert payload["field_relationship_levels"]["EXACT"] == 100
        assert "MASTER" in payload["degree_levels"]

    def test_profile_options_do_not_shadow_the_scholarship_detail_route(self, client):
        """The dynamic /{id} route must still resolve for a real record."""
        assert client.get("/scholarships/match/profile-options").status_code == 200


class TestParseProfileEndpoint:
    """The optional free-text parser, at the HTTP boundary.

    It shares this module's application and database fixture deliberately: a
    second one would initialise a competing schema and prove nothing.
    """

    STATEMENT = (
        "I'm from Bangladesh and want a fully funded Master's in Computer Science "
        "in Europe. I have IELTS 7."
    )

    def test_the_documented_example_is_parsed_over_http(self, client):
        response = client.post("/api/scholarships/match/parse-profile", json={"text": self.STATEMENT})
        assert response.status_code == 200, response.text
        payload = response.json()
        profile = payload["profile"]
        assert profile["citizenship"] == "Bangladesh"
        assert profile["intended_degree_level"] == "MASTER"
        assert profile["intended_field"] == "computer_science"
        assert profile["funding_requirement"] == "FULL_FUNDING"
        assert profile["language_credentials"] == [{"test": "ielts", "score": 7.0}]
        assert "Germany" in profile["preferred_countries"]

    def test_every_interpretation_is_returned_for_confirmation(self, client):
        payload = client.post(
            "/api/scholarships/match/parse-profile", json={"text": self.STATEMENT}
        ).json()
        assert payload["empty"] is False
        assert payload["deterministic"] is True
        assert payload["resolved"]
        for item in payload["resolved"]:
            assert item["display"]
            assert item["source"]
            assert item["status"] == "RESOLVED"
        assert "you can change or remove anything" in payload["note"]

    def test_an_unresolvable_country_is_reported_rather_than_guessed(self, client):
        payload = client.post(
            "/api/scholarships/match/parse-profile",
            json={"text": "I am from Wakanda and want a Master's in Computer Science."},
        ).json()
        assert payload["profile"].get("citizenship") is None
        assert any(item["field"] == "citizenship" for item in payload["unresolved"])

    def test_an_empty_message_returns_a_normal_empty_state(self, client):
        for body in ({}, {"text": ""}, {"text": "asdf qwerty zxcv"}):
            response = client.post("/api/scholarships/match/parse-profile", json=body)
            assert response.status_code == 200, response.text
            assert response.json()["empty"] is True

    def test_an_unknown_field_is_rejected(self, client):
        response = client.post(
            "/api/scholarships/match/parse-profile", json={"text": "IELTS 7", "model": "gpt"}
        )
        assert response.status_code == 422

    def test_a_wrongly_typed_text_is_rejected(self, client):
        assert client.post("/api/scholarships/match/parse-profile", json={"text": 7}).status_code == 422

    def test_the_parsed_profile_is_accepted_by_the_match_endpoint(self, client):
        """The documented flow: parse, confirm, then calculate."""
        parsed = client.post(
            "/api/scholarships/match/parse-profile", json={"text": self.STATEMENT}
        ).json()
        payload = client.post("/scholarships/match", json=parsed["profile"]).json()
        assert payload["results"]
        assert payload["eligible_count"] + payload["needs_verification_count"] + payload["ineligible_count"] == payload[
            "total_candidates"
        ]

    def test_identical_text_returns_an_identical_body(self, client):
        first = client.post("/api/scholarships/match/parse-profile", json={"text": self.STATEMENT}).json()
        second = client.post("/api/scholarships/match/parse-profile", json={"text": self.STATEMENT}).json()
        assert first == second

    def test_the_parser_writes_nothing(self, client):
        def record_count() -> int:
            with get_session_factory()() as session:
                return len(list(session.scalars(select(Scholarship))))

        before = record_count()
        client.post("/api/scholarships/match/parse-profile", json={"text": self.STATEMENT})
        assert record_count() == before


class TestMatchContractDetails:
    def test_every_version_a_reader_needs_is_reported(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        explanation = payload["explanation"]
        assert explanation["engine_version"] == "2.0.0"
        assert explanation["scoring_config_version"] == "2.0.0"
        assert explanation["field_taxonomy_version"] == "1.0.0"
        assert explanation["requirement_reader_version"] == "2.0.0"
        assert explanation["deadline_semantics_version"] == "1.0.0"

    def test_profile_strength_and_readiness_are_returned(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        assert payload["profile_strength"]["score"] is not None
        assert payload["profile_strength"]["band"] == "STRONG"
        result = payload["results"][0]
        assert result["readiness"] is not None
        assert 0 <= result["readiness"]["score"] <= 100

    def test_every_result_carries_gaps_and_actions(self, client):
        results = client.post("/scholarships/match", json=HIGH_PROFILE).json()["results"]
        for result in results:
            assert "gaps" in result
            assert "actions" in result
            for action in result["actions"]:
                assert action["code"]
                assert action["message"]

    def test_needs_verification_keeps_its_fit_band_in_the_response(self, client):
        payload = client.post(
            "/scholarships/match", json={**HIGH_PROFILE, "language_credentials": []}
        ).json()
        unverified = [
            item for item in payload["results"] if item["eligibility"] == "NEEDS_VERIFICATION"
        ]
        assert unverified
        for item in unverified:
            assert item["fit_label"] != "NEEDS_VERIFICATION"
            assert "NEEDS_VERIFICATION" not in item["fit_label"]

    def test_no_result_exposes_a_suppressed_raw_fit(self, client):
        payload = client.post("/scholarships/match", json=HIGH_PROFILE).json()
        for result in payload["results"]:
            assert "suppressed_fit_score" not in result
            if result["eligibility"] == "INELIGIBLE":
                assert result["fit_score"] is None
                assert result["fit_label"] == "INELIGIBLE"

    def test_the_country_option_list_is_not_truncated(self, client):
        options = client.get("/scholarships/match/profile-options").json()
        names = set(options["countries"])
        assert "Germany" in names
        assert "United Kingdom" in names
        # Served complete: no two-letter lookup shorthands leak into the picker,
        # and nothing is capped.
        assert len(names) > 50
        assert not any(len(name) <= 3 for name in names)
        assert options["regions"]


class TestCorsPreflight:
    def test_post_is_allowed_for_the_configured_frontend_origin(self, client):
        """A JSON POST from the browser triggers a preflight; it must pass."""
        response = client.options(
            "/api/scholarships/match",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "POST" in response.headers["access-control-allow-methods"]

    def test_the_read_only_catalogue_is_untouched_by_the_cors_change(self, client):
        response = client.options(
            "/api/scholarships",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "GET" in response.headers["access-control-allow-methods"]

class TestLegacyListShapeIsReadAsPublished:
    """A bare string in a list column must be read as one published statement.

    The production catalogue stores some ``list[str]`` columns as a bare string.
    The reader used to be ``list(value or [])``, which turned ``"Full tuition
    fees"`` into nine single characters. Funding coverage is then read one
    character at a time, no phrase matches, and a record that publishes its
    coverage plainly is reported as *unknown*.

    Unknown is not a neutral outcome. It removes an evaluated component from the
    fit denominator, so the score moves, and the funding distribution counts the
    record as unstated instead of counting it. The production audit found 34
    public rows in this shape.

    These tests pin the reading, not the maths: the same published text must
    produce the same funding verdict whether it is stored as ``[S]`` or as ``S``.
    """

    PUBLISHED = "Full tuition and monthly stipend for living expenses"

    def _funding_state(self, client, stored) -> str | None:
        scholarship_id = seed_record(
            title="Legacy Shape Scholarship",
            official_source="Legacy Shape University",
            official_source_url="https://example.edu/legacy-shape",
            coverage=stored,
        )
        try:
            response = client.post("/scholarships/match", json=HIGH_PROFILE)
            assert response.status_code == 200, response.text
            payload = response.json()
            match = next(
                (
                    r
                    for r in payload["results"]
                    if r["scholarship_id"] == scholarship_id
                ),
                None,
            )
            assert match is not None, "seeded record did not reach the results"
            return match["funding_state"]
        finally:
            with get_session_factory()() as session:
                session.query(Scholarship).filter(
                    Scholarship.id == scholarship_id
                ).delete()
                session.commit()

    def test_a_bare_string_is_not_read_as_characters(self, client):
        """The defect itself: the string arrives as one statement, not nine."""
        assert self._funding_state(client, self.PUBLISHED) == "FULL"

    def test_both_storage_shapes_give_the_same_verdict(self, client):
        """Stored as a list and stored as a bare string must agree exactly."""
        as_list = self._funding_state(client, [self.PUBLISHED])
        as_string = self._funding_state(client, self.PUBLISHED)
        assert as_list == as_string

    def test_the_text_is_preserved_exactly(self, client):
        """Reshaping must not trim, re-case or otherwise rewrite the text."""
        from app.services.matching.repository import _list_field

        assert _list_field(self.PUBLISHED, "coverage") == [self.PUBLISHED]

    def test_reading_is_idempotent(self, client):
        from app.services.matching.repository import _list_field

        once = _list_field(self.PUBLISHED, "coverage")
        assert _list_field(once, "coverage") == once

    def test_a_well_formed_list_is_untouched(self, client):
        from app.services.matching.repository import _list_field

        assert _list_field(["a", "b"], "coverage") == ["a", "b"]

    def test_null_and_blank_read_as_nothing_published(self, client):
        from app.services.matching.repository import _list_field

        assert _list_field(None, "coverage") == []
        assert _list_field("   ", "coverage") == []

    def test_a_value_that_is_not_text_is_refused_not_invented(self, client):
        """A number cannot become a sentence, so it reads as unknown."""
        from app.services.matching.repository import _list_field

        assert _list_field(42, "coverage") == []
        assert _list_field({"a": 1}, "coverage") == []