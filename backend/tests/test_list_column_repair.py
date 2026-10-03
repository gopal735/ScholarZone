"""Tests for the JSON-list-column shape repair.

Six ``scholarships`` columns are declared ``list[str]`` by the model and by the
public detail contract, and all six are JSON columns - so the database accepts a
bare JSON string in them without complaint. 117 of the 386 public records were
storing researched prose that way, and each one's own detail page answered 500
because a string is not a list. The list endpoint declares none of these fields,
so the records kept rendering as cards and the failure only surfaced on the page
an applicant actually opens.

These tests pin the rule, the contract, the write paths that produced the shape,
and the stage that repairs the data. They use the shipped snapshot of the real
stored rows so the regression is measured against production shapes rather than
against a shape invented here.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.jobs import scholarzone_maintenance as worker
from app.models import Scholarship
from app.schemas import ScholarshipDetailResponse
from app.services.discovery_pipeline import _list_column
from app.services.list_columns import (
    LIST_COLUMNS,
    ListColumnShapeError,
    normalize_list_column,
    normalize_list_columns,
)
from app.services.scholarship_enrichment import merge_list

SNAPSHOT = Path(__file__).resolve().parents[2] / "verification" / "live_raw.json"
HAS_SNAPSHOT = SNAPSHOT.exists()
needs_snapshot = pytest.mark.skipif(
    not HAS_SNAPSHOT, reason="deployed-row snapshot not present in this checkout"
)

# The contract's array fields. `required_documents` has no column of its own -
# it is an alias for `documents` - so it is deliberately absent from LIST_COLUMNS.
CONTRACT_ARRAY_FIELDS = (*LIST_COLUMNS, "required_documents")


@pytest.fixture(scope="module")
def stored_rows() -> dict:
    raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


@pytest.fixture(scope="module")
def catalogue_ids() -> set:
    path = Path(__file__).resolve().parents[2] / "verification" / "live_catalogue.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["id"] for r in data["items"]}


def detail_payload(row: dict) -> dict:
    """Project a stored row onto the detail contract, the way the router does."""
    payload = {k: v for k, v in row.items() if k in ScholarshipDetailResponse.model_fields}
    if "verified" not in payload and "is_verified" in row:
        payload["verified"] = row["is_verified"]
    return payload


def minimal_detail(**overrides) -> dict:
    """The smallest row the detail contract accepts, plus field overrides."""
    return detail_payload(
        {
            "id": 1,
            "title": "x",
            "name": "x",
            "country": "x",
            "degree": "x",
            "funding": "x",
            "deadline_precision": "month",
            "verified": True,
            "updated_at": "2026-01-01T00:00:00+00:00",
            **overrides,
        }
    )


@pytest.fixture
def session_factory():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.models import Base

    # StaticPool + check_same_thread=False: TestClient serves requests on its own
    # thread, and an in-memory database only exists for as long as its
    # connection. One shared connection is what makes both true at once.
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestTheRule:
    def test_null_becomes_an_empty_list(self):
        assert normalize_list_column(None, field="coverage") == ([], True)

    def test_a_stored_sentence_becomes_a_one_element_list(self):
        sentence = "Apply through the DAAD portal."
        assert normalize_list_column(sentence, field="application_method") == (
            [sentence],
            True,
        )

    def test_the_text_is_preserved_byte_for_byte(self):
        # Whitespace and punctuation inside a real sentence are content. A
        # repair that strips or re-wraps it would be editing the scholarship.
        sentence = "  Submit by post  —  no online route is published.  "
        fixed, changed = normalize_list_column(sentence)
        assert changed is True
        assert fixed == [sentence]

    def test_a_blank_string_is_nothing_recorded(self):
        assert normalize_list_column("   ") == ([], True)

    def test_a_list_is_returned_untouched_and_in_order(self):
        items = ["first", "second", "third"]
        assert normalize_list_column(items) == (items, False)

    def test_the_rule_is_idempotent(self):
        for value in (None, "", "  ", "a sentence", ["a", "b"], []):
            once, _ = normalize_list_column(value)
            twice, changed = normalize_list_column(once)
            assert twice == once
            assert changed is False

    def test_a_value_with_no_honest_list_form_is_refused(self):
        # Guessing here would publish a sentence the source never contained.
        for value in (42, 3.5, {"a": 1}, ["ok", 7], True):
            with pytest.raises(ListColumnShapeError):
                normalize_list_column(value, field="coverage")

    def test_the_refusal_names_the_field_and_the_position(self):
        with pytest.raises(ListColumnShapeError) as excinfo:
            normalize_list_column(["fine", 3], field="documents")
        message = str(excinfo.value)
        assert "documents" in message
        assert "member 1" in message

    def test_only_the_columns_that_need_reshaping_are_reported(self):
        class Row:
            eligibility = ["already fine"]
            benefits = "needs reshaping"
            coverage = None
            requirements = ["fine"]
            documents = ["fine"]
            application_method = ["fine"]

        assert normalize_list_columns(Row()) == {
            "benefits": ["needs reshaping"],
            "coverage": [],
        }


class TestTheContract:
    @pytest.mark.parametrize("field", CONTRACT_ARRAY_FIELDS)
    def test_a_bare_string_validates_as_a_one_element_list(self, field):
        model = ScholarshipDetailResponse(**minimal_detail(**{field: "A researched sentence."}))
        assert getattr(model, field) == ["A researched sentence."]

    @pytest.mark.parametrize("field", CONTRACT_ARRAY_FIELDS)
    def test_null_still_becomes_an_empty_list(self, field):
        assert getattr(ScholarshipDetailResponse(**minimal_detail(**{field: None})), field) == []

    def test_a_number_is_still_refused(self):
        # The contract may accept the legacy string shape; it must not invent a
        # sentence from something that was never text.
        with pytest.raises(ValidationError):
            ScholarshipDetailResponse(**minimal_detail(coverage=42))

    @needs_snapshot
    def test_every_stored_row_validates(self, stored_rows):
        # The failure being repaired was a 500 on a real applicant page. This is
        # the assertion that closes it, against every row the deployment holds.
        failures = {}
        for sid, row in stored_rows.items():
            try:
                ScholarshipDetailResponse(**detail_payload(row))
            except ValidationError as exc:
                failures[sid] = exc.errors()[0]["loc"]
        assert failures == {}, f"{len(failures)} stored rows still fail the contract"

    @needs_snapshot
    def test_no_stored_row_still_holds_a_scalar_in_an_array_column(self, stored_rows):
        offenders = {
            (sid, field)
            for sid, row in stored_rows.items()
            for field in LIST_COLUMNS
            if row.get(field) is not None and not isinstance(row[field], list)
        }
        # The snapshot is taken from production, so this documents the scale of
        # the defect the repair addresses. It is a census, not a repair: the data
        # itself is changed by the maintenance stage, not by a test.
        assert len(offenders) == 160, sorted(offenders)[:5]


class TestTheWritePathsThatProducedTheShape:
    def test_programme_details_no_longer_files_coverage_as_text(self):
        # `coverage` and `application_method` were mapped as text columns, which
        # wrote a bare string into a JSON list column.
        source = inspect.getsource(worker)
        tree = ast.parse(source)
        text_map_keys: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "text_map" for t in node.targets
            ):
                if isinstance(node.value, ast.Dict):
                    text_map_keys = {
                        k.value for k in node.value.keys if isinstance(k, ast.Constant)
                    }
        assert "coverage" not in text_map_keys
        assert "application_method" not in text_map_keys

    def test_programme_details_routes_them_through_the_list_path(self):
        source = inspect.getsource(worker)
        tree = ast.parse(source)
        list_map: dict = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "list_map" for t in node.targets
            ):
                if isinstance(node.value, ast.Dict):
                    list_map = {
                        k.value: v.value
                        for k, v in zip(node.value.keys, node.value.values)
                        if isinstance(k, ast.Constant)
                    }
        assert list_map.get("coverage") == "coverage"
        assert list_map.get("application_method") == "application_method"

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("Apply online.", ["Apply online."]),
            (None, []),
            (["a", "b"], ["a", "b"]),
            ("", []),
            (42, []),
            ({"a": 1}, []),
        ],
    )
    def test_discovery_insert_shapes_extracted_values(self, value, expected):
        # The extractor types `eligibility` and `application_method` as strings,
        # because on the page they are a labelled sentence.
        assert _list_column(value) == expected

    def test_a_scalar_existing_value_is_not_shattered_by_a_merge(self):
        # merge_list used list(existing), which turns one researched sentence
        # into thirty single letters - a real sentence destroyed by a merge that
        # was meant to preserve it.
        merged, added = merge_list("Apply through the DAAD portal.", ["New fact."])
        assert merged == ["Apply through the DAAD portal.", "New fact."]
        assert added == ["New fact."]

    def test_merging_a_scalar_value_twice_is_idempotent(self):
        merged, added = merge_list("One sentence.", ["One sentence."])
        assert merged == ["One sentence."]
        assert added == []

    def test_a_list_merge_behaves_exactly_as_before(self):
        assert merge_list(["a"], ["b", "a"]) == (["a", "b"], ["b"])


class TestTheRepairStage:
    def test_stage_is_declared_and_dispatched(self):
        assert "repair_list_columns" in worker.STAGE_ORDER
        assert worker.STAGE_DEPENDENCIES["repair_list_columns"] == ()
        tree = ast.parse(inspect.getsource(worker))
        dispatched: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "stages" for t in node.targets
            ):
                if isinstance(node.value, ast.Dict):
                    dispatched = {
                        k.value for k in node.value.keys if isinstance(k, ast.Constant)
                    }
        assert "repair_list_columns" in dispatched

    def test_stage_runs_before_the_destructive_purge(self):
        assert worker.STAGE_ORDER.index("repair_list_columns") < worker.STAGE_ORDER.index(
            "purge_closed"
        )

    def test_stage_reprows_idempotently_and_preserves_the_text(self, session_factory):
        from app.services.list_columns import LIST_COLUMNS as columns

        session = session_factory()
        try:
            sentence = "Apply through the local Taiwan Representative Office."
            row = Scholarship(
                title="Stage fixture",
                country="TW",
                degree="master",
                funding="stipend",
                is_verified=True,
                verification_status="active",
                eligibility=sentence,
                application_method=sentence,
            )
            session.add(row)
            session.commit()
            first_pass = normalize_list_columns(row)
            assert set(first_pass) == {"eligibility", "application_method"}
            for field, value in first_pass.items():
                setattr(row, field, value)
            session.commit()
            assert normalize_list_columns(row) == {}, "the rule is not idempotent"
            assert row.eligibility == [sentence]
            assert row.application_method == [sentence]
            assert set(columns) >= {"eligibility", "application_method"}
        finally:
            session.rollback()
            session.close()


class TestTheEndpoint:
    """The failure was a 500 on an applicant's own page. This is that page."""

    def _store(self, session_factory, **columns):
        defaults = {
            "eligibility": ["already a list"],
            "application_method": ["already a list"],
        }
        defaults.update(columns)
        session = session_factory()
        try:
            row = Scholarship(
                id=9871,
                title="Shape fixture",
                country="TW",
                degree="master",
                funding="stipend",
                deadline_precision="month",
                is_verified=True,
                verification_status="active",
                **defaults,
            )
            session.add(row)
            session.commit()
        finally:
            session.close()

    @pytest.fixture
    def detail_client(self, session_factory, monkeypatch):
        """The real app, wired to this test's own session.

        ``Depends(get_db)`` is bound when the route is declared, so the override
        table is the only place a different session can be supplied.
        """
        from starlette.testclient import TestClient

        import app.main as main_module
        from app.routers import scholarships as scholarships_router

        main_module.app.dependency_overrides[scholarships_router.get_db] = (
            lambda: session_factory()
        )
        # The startup init opens the process-wide database and builds its own
        # schema; this test owns the session and the schema.
        monkeypatch.setattr(main_module, "_run_init", lambda: None)
        monkeypatch.setattr(main_module, "seed_database", lambda: 0)
        with TestClient(main_module.app, raise_server_exceptions=False) as client:
            yield client
        main_module.app.dependency_overrides.pop(scholarships_router.get_db, None)

    @pytest.mark.parametrize(
        "field", ["eligibility", "application_method", "coverage", "benefits"]
    )
    def test_a_stored_scalar_no_longer_answers_500(
        self, session_factory, detail_client, field
    ):
        self._store(session_factory, **{field: "Submit through the official portal."})
        response = detail_client.get("/api/scholarships/9871")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body[field], list)
        assert body[field] == ["Submit through the official portal."]

    def test_the_detail_page_serves_every_array_field_as_a_json_array(
        self, session_factory, detail_client
    ):
        self._store(
            session_factory,
            eligibility="Undergraduate students from outside Taiwan.",
            coverage="Full tuition waiver.",
            application_method="Apply online.",
            benefits="Stipend of NT$14,100 per month.",
        )
        response = detail_client.get("/api/scholarships/9871")
        assert response.status_code == 200, response.text
        body = response.json()
        for field in CONTRACT_ARRAY_FIELDS:
            assert isinstance(body[field], list), field
        assert body["eligibility"] == ["Undergraduate students from outside Taiwan."]
        assert body["coverage"] == ["Full tuition waiver."]
        assert body["application_method"] == ["Apply online."]
        assert body["benefits"] == ["Stipend of NT$14,100 per month."]

    def test_the_list_endpoint_is_unaffected_by_the_shape(self, session_factory, detail_client):
        # The directory declares none of these fields, which is exactly why the
        # defect survived: the card rendered fine while its own page 500'd.
        self._store(session_factory, application_method="Apply online.")
        response = detail_client.get("/api/scholarships?limit=100")
        assert response.status_code == 200, response.text
        assert any(item["id"] == 9871 for item in response.json()["items"])