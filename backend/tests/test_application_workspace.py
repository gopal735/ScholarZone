"""Application Workspace 1.0: auth, ownership, lifecycle, progress and privacy.

The failures these guard are not hypothetical. Each one corresponds to a way this
workspace could quietly lie to a student: showing them another person's
application, reporting progress they never made, turning an unknown deadline into
zero days, claiming a document is required on ScholarZone's own authority, or
silently overwriting an edit made in another tab.

The deadline tests are the strictest here. The workspace contains no date
arithmetic at all, so any test that passes a specific day count is verifying that
``evaluate_deadline`` is genuinely being called rather than reimplemented.
"""

from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import (
    ApplicationChecklistItem,
    ApplicationRecord,
    Base,
    Scholarship,
    User,
)
from app.services.application_workspace import (
    STATE_TRANSITIONS,
    compute_progress,
    derive_checklist,
)

AS_OF = date(2026, 6, 1)
PASSWORD = "workspace-test-9"
_sequence = itertools.count(1)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workspace.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(db, email: str) -> User:
    from app.services.auth import hash_password

    user = User(email=email, password_hash=hash_password(PASSWORD), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


def make_scholarship(db, **overrides) -> Scholarship:
    index = next(_sequence)
    values = {
        "title": f"Workspace Scholarship {index}",
        "country": "Netherlands",
        "degree": "Master",
        "funding": "Full",
        "official_source": f"Provider {index}",
        "official_source_url": f"https://provider{index}.example/programme",
        "verification_status": "active",
        "is_verified": True,
        "status": "open",
        "deadline_date": date(2026, 8, 1),
        "deadline_display": "Applications close 1 August 2026",
        "deadline_precision": "exact",
    }
    values.update(overrides)
    record = Scholarship(**values)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def start(client, scholarship_id: int):
    return client.post("/api/applications", json={"scholarship_id": scholarship_id})


# ------------------------------------------------------------------- 1. auth


class TestAuthentication:
    def test_every_private_route_is_blocked_when_signed_out(self, client, db):
        record = make_scholarship(db)
        routes = [
            ("get", "/api/applications", None),
            ("post", "/api/applications", {"scholarship_id": record.id}),
            ("get", "/api/applications/1", None),
            ("patch", "/api/applications/1", {"expected_version": 1, "state": "planning"}),
            ("patch", "/api/applications/1/checklist/review_eligibility", {"expected_version": 1, "completed": True}),
            ("delete", "/api/applications/1", None),
        ]
        for method, path, body in routes:
            response = client.request(method, path, json=body)
            assert response.status_code == 401, f"{method} {path} -> {response.status_code}"

    def test_a_revoked_session_loses_access(self, client, db):
        make_user(db, "leaver@example.com")
        scholarship = make_scholarship(db)
        login(client, "leaver@example.com")
        start(client, scholarship.id)
        assert client.get("/api/applications").status_code == 200

        client.post("/auth/logout")
        client.cookies.clear()
        assert client.get("/api/applications").status_code == 401


# ---------------------------------------------------- 2. ownership / isolation


class TestOwnership:
    def test_a_second_student_cannot_see_the_first_students_application(self, client, db):
        alice = make_user(db, "alice@example.com")
        make_user(db, "mallory@example.com")
        scholarship = make_scholarship(db)

        login(client, "alice@example.com")
        created = start(client, scholarship.id).json()
        application_id = created["id"]

        login(client, "mallory@example.com")
        response = client.get(f"/api/applications/{application_id}")
        # 404, not 403: a 403 would confirm the record exists.
        assert response.status_code == 404
        assert client.get("/api/applications").json()["applications"] == []

    def test_cross_user_mutation_is_refused(self, client, db):
        make_user(db, "alice2@example.com")
        make_user(db, "mallory2@example.com")
        scholarship = make_scholarship(db)

        login(client, "alice2@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        version = client.get(f"/api/applications/{application_id}").json()["version"]

        login(client, "mallory2@example.com")
        assert client.patch(
            f"/api/applications/{application_id}", json={"expected_version": version, "state": "planning"}
        ).status_code == 404
        assert client.delete(f"/api/applications/{application_id}").status_code == 404
        assert client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": version, "completed": True},
        ).status_code == 404

        # Alice's record is untouched.
        login(client, "alice2@example.com")
        assert client.get(f"/api/applications/{application_id}").json()["state"] == "saved"

    def test_forged_owner_fields_are_refused_not_obeyed(self, client, db):
        alice = make_user(db, "alice3@example.com")
        mallory = make_user(db, "mallory3@example.com")
        scholarship = make_scholarship(db)

        login(client, "alice3@example.com")
        created = start(client, scholarship.id).json()

        # No owner field exists in the request schema, so naming one is a 422
        # rather than a silently ignored extra.
        assert client.post(
            "/api/applications", json={"scholarship_id": scholarship.id, "user_id": mallory.id}
        ).status_code == 422

        assert client.get(f"/api/applications/{created['id']}").json()["id"] == created["id"]

    def test_list_is_scoped_to_the_caller_with_no_parameter_to_widen_it(self, client, db):
        alice = make_user(db, "alice4@example.com")
        make_user(db, "bob4@example.com")
        first = make_scholarship(db)
        second = make_scholarship(db)

        login(client, "alice4@example.com")
        start(client, first.id)
        start(client, second.id)

        login(client, "bob4@example.com")
        # A user_id in the query string has no effect: the route takes no owner.
        response = client.get("/api/applications", params={"user_id": alice.id})
        assert response.status_code == 200
        assert response.json()["count"] == 0


# ------------------------------------------------------------- 3. CRUD + dedupe


class TestCreateAndLifecycle:
    def test_creating_an_application_seeds_a_bounded_generic_checklist(self, client, db):
        make_user(db, "creator@example.com")
        scholarship = make_scholarship(db)
        login(client, "creator@example.com")

        response = start(client, scholarship.id)
        assert response.status_code == 201, response.text
        body = response.json()

        assert body["state"] == "saved"
        assert body["outcome"] == "pending"
        assert body["version"] == 1
        assert body["availability"]["is_available"] is True

        keys = [item["key"] for item in body["checklist"]]
        assert "review_eligibility" in keys
        assert "review_official_requirements" in keys
        assert "verify_language_requirement" in keys
        assert "prepare_application_materials" in keys
        assert "submit_application" in keys
        # Bounded: a checklist is a preparation aid, not a document vault.
        assert len(keys) <= 24
        # Every generic task declares itself generic, so none of them can be read
        # as a claim about what this provider requires.
        for item in body["checklist"]:
            if item["key"].startswith(("review_", "verify_", "prepare_", "submit_")):
                assert item["source"] == "generic"

    def test_creating_twice_is_idempotent_not_duplicated(self, client, db):
        make_user(db, "dupe@example.com")
        scholarship = make_scholarship(db)
        login(client, "dupe@example.com")

        first = start(client, scholarship.id).json()
        second = start(client, scholarship.id).json()
        assert first["id"] == second["id"]
        assert client.get("/api/applications").json()["count"] == 1

    def test_starting_an_application_leaves_the_saved_shortlist_alone(self, client, db):
        make_user(db, "saved@example.com")
        scholarship = make_scholarship(db)
        login(client, "saved@example.com")

        assert client.post(f"/api/dashboard/saved?scholarship_id={scholarship.id}").status_code == 200
        start(client, scholarship.id)

        # The saved item must survive: starting an application is a new fact, not
        # a reason to discard an earlier one.
        assert client.get("/api/dashboard/saved").json()["count"] == 1

    def test_submitted_application_cannot_be_deleted(self, client, db):
        make_user(db, "keeper@example.com")
        scholarship = make_scholarship(db)
        login(client, "keeper@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 1, "state": "in_progress"}
        )
        client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 2, "state": "submitted"}
        )

        response = client.delete(f"/api/applications/{application_id}")
        assert response.status_code == 409
        # Still readable: the record of what happened is the point.
        assert client.get(f"/api/applications/{application_id}").status_code == 200

    def test_discard_removes_an_application_started_by_accident(self, client, db):
        make_user(db, "discard@example.com")
        scholarship = make_scholarship(db)
        login(client, "discard@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        assert client.delete(f"/api/applications/{application_id}").status_code == 204
        assert client.get("/api/applications").json()["count"] == 0


# ------------------------------------------------------------ 4. state machine


class TestStateMachine:
    def test_the_documented_transitions_are_exactly_what_the_code_enforces(self):
        assert STATE_TRANSITIONS["saved"] == frozenset({"planning", "in_progress", "withdrawn"})
        assert STATE_TRANSITIONS["planning"] == frozenset({"saved", "in_progress", "withdrawn"})
        assert STATE_TRANSITIONS["in_progress"] == frozenset({"planning", "submitted", "withdrawn"})
        assert STATE_TRANSITIONS["withdrawn"] == frozenset({"saved", "planning"})
        # A submitted application has been seen by the provider. Reopening it
        # would let a student believe it is live when it is not.
        assert STATE_TRANSITIONS["submitted"] == frozenset({"withdrawn"})
        assert "in_progress" not in STATE_TRANSITIONS["submitted"]

    def test_the_happy_path_walks_forward(self, client, db):
        make_user(db, "walk@example.com")
        scholarship = make_scholarship(db)
        login(client, "walk@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        for expected_version, state in ((1, "planning"), (2, "in_progress"), (3, "submitted")):
            response = client.patch(
                f"/api/applications/{application_id}",
                json={"expected_version": expected_version, "state": state},
            )
            assert response.status_code == 200, response.text
            assert response.json()["state"] == state

    def test_submitted_cannot_be_reopened(self, client, db):
        make_user(db, "reopen@example.com")
        scholarship = make_scholarship(db)
        login(client, "reopen@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 1, "state": "planning"})
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 2, "state": "in_progress"})
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 3, "state": "submitted"})

        for illegal in ("in_progress", "planning", "saved"):
            response = client.patch(
                f"/api/applications/{application_id}",
                json={"expected_version": 4, "state": illegal},
            )
            assert response.status_code == 409, f"{illegal} should be refused"
            assert "cannot move to" in response.json()["detail"]

    def test_submitted_can_be_withdrawn_and_withdrawn_can_be_reopened(self, client, db):
        make_user(db, "reverse@example.com")
        scholarship = make_scholarship(db)
        login(client, "reverse@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 1, "state": "planning"})
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 2, "state": "in_progress"})
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 3, "state": "submitted"})

        withdrawn = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 4, "state": "withdrawn"}
        )
        assert withdrawn.status_code == 200
        reopened = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 5, "state": "saved"}
        )
        assert reopened.status_code == 200

    def test_repeating_the_current_state_is_accepted(self, client, db):
        """A retried PATCH must not fail, or network uncertainty loses work."""
        make_user(db, "retry@example.com")
        scholarship = make_scholarship(db)
        login(client, "retry@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        first = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 1, "state": "planning"}
        )
        assert first.status_code == 200
        # Same state again, now at version 2.
        again = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 2, "state": "planning"}
        )
        assert again.status_code == 200

    def test_an_unknown_state_is_a_422_not_a_500(self, client, db):
        make_user(db, "bogus@example.com")
        scholarship = make_scholarship(db)
        login(client, "bogus@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        response = client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "state": "accepted-with-congratulations"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------- 5. outcomes


class TestOutcomes:
    def _submitted(self, client, db, email):
        make_user(db, email)
        scholarship = make_scholarship(db)
        login(client, email)
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 1, "state": "planning"})
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 2, "state": "in_progress"})
        client.patch(f"/api/applications/{application_id}", json={"expected_version": 3, "state": "submitted"})
        return application_id

    def test_an_outcome_requires_a_submitted_application(self, client, db):
        """ScholarZone may not record an acceptance the provider never sent."""
        make_user(db, "early@example.com")
        scholarship = make_scholarship(db)
        login(client, "early@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        response = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 1, "outcome": "accepted"}
        )
        assert response.status_code == 409
        assert "submitted" in response.json()["detail"]

    def test_a_submitted_application_accepts_an_outcome(self, client, db):
        application_id = self._submitted(client, db, "outcome@example.com")
        login(client, "outcome@example.com")

        response = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 4, "outcome": "accepted"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "accepted"
        assert body["outcome_label"] == "Accepted"
        # The lifecycle state is untouched: submitted is what the student did.
        assert body["state"] == "submitted"

    def test_a_final_outcome_cannot_change(self, client, db):
        application_id = self._submitted(client, db, "terminal@example.com")
        login(client, "terminal@example.com")
        client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 4, "outcome": "rejected"}
        )

        response = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 5, "outcome": "accepted"}
        )
        assert response.status_code == 409
        assert "final outcome" in response.json()["detail"]

    def test_an_unknown_outcome_is_refused(self, client, db):
        application_id = self._submitted(client, db, "unknown-outcome@example.com")
        login(client, "unknown-outcome@example.com")
        response = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 4, "outcome": "probably-fine"}
        )
        assert response.status_code == 422


# -------------------------------------------------------------- 6. checklist


class TestChecklist:
    def test_completion_persists_and_bumps_the_version(self, client, db):
        make_user(db, "check@example.com")
        scholarship = make_scholarship(db)
        login(client, "check@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        response = client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 1, "completed": True},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == 2

        item = next(i for i in body["checklist"] if i["key"] == "review_eligibility")
        assert item["completed"] is True
        assert item["completed_at"] is not None

        # Survives a reload, which is the property that matters.
        again = client.get(f"/api/applications/{application_id}").json()
        assert next(i for i in again["checklist"] if i["key"] == "review_eligibility")["completed"] is True

    def test_completing_twice_is_idempotent_and_does_not_lose_the_timestamp(self, client, db):
        make_user(db, "idem@example.com")
        scholarship = make_scholarship(db)
        login(client, "idem@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        first = client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 1, "completed": True},
        ).json()
        stamp = next(i for i in first["checklist"] if i["key"] == "review_eligibility")["completed_at"]

        # Retried with the now-current version: accepted, and nothing changes, so
        # the parent version must not move either.
        second = client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 2, "completed": True},
        )
        assert second.status_code == 200
        assert second.json()["version"] == 2
        assert next(i for i in second.json()["checklist"] if i["key"] == "review_eligibility")["completed_at"] == stamp

    def test_a_timestamp_read_back_from_the_database_serialises_identically(
        self, client, db
    ):
        """The representation must not depend on where the value came from.

        A timestamp is written aware and read back naive, because SQLite has no
        timezone type. If the API passes whichever form it happened to receive
        straight through, then the instant a client saves and the instant it sees
        after a reload are the same moment written two different ways - and a
        client cannot compare them. Which form a given request sees depends on
        whether the value is still sitting in the session or has been reloaded,
        so this has to be pinned deliberately rather than left to chance.

        Dropping the identity map forces the reloaded path. Without that, the
        session may still hold the object that was assigned and the test would
        pass whether or not the API normalised anything.
        """
        make_user(db, "reload@example.com")
        scholarship = make_scholarship(db)
        login(client, "reload@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        written = client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 1, "completed": True},
        ).json()
        stamp = next(
            i for i in written["checklist"] if i["key"] == "review_eligibility"
        )["completed_at"]
        assert stamp.endswith("Z"), f"expected a UTC-aware instant, got {stamp!r}"

        # Forget everything held in memory so the next read genuinely comes from
        # the database rather than from the object that was assigned.
        db.expunge_all()

        reloaded = client.get(f"/api/applications/{application_id}").json()
        assert (
            next(i for i in reloaded["checklist"] if i["key"] == "review_eligibility")[
                "completed_at"
            ]
            == stamp
        ), "the same instant must serialise the same way after a reload"

        # The other two timestamps this module emits come off the same columns.
        assert reloaded["created_at"].endswith("Z")
        assert reloaded["updated_at"].endswith("Z")

    def test_uncompleting_clears_the_timestamp(self, client, db):
        make_user(db, "undo@example.com")
        scholarship = make_scholarship(db)
        login(client, "undo@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 1, "completed": True},
        )
        undone = client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 2, "completed": False},
        ).json()
        item = next(i for i in undone["checklist"] if i["key"] == "review_eligibility")
        assert item["completed"] is False
        assert item["completed_at"] is None

    def test_an_unknown_task_key_is_a_404(self, client, db):
        make_user(db, "ghost-task@example.com")
        scholarship = make_scholarship(db)
        login(client, "ghost-task@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        response = client.patch(
            f"/api/applications/{application_id}/checklist/no_such_task",
            json={"expected_version": 1, "completed": True},
        )
        assert response.status_code == 404

    def test_a_missing_expected_version_is_refused(self, client, db):
        make_user(db, "noversion@example.com")
        scholarship = make_scholarship(db)
        login(client, "noversion@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        response = client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility", json={"completed": True}
        )
        assert response.status_code == 422


# -------------------------------------------------------------- 7. progress


def _item(weight=1, completed=False):
    return type("Row", (), {"weight": weight, "completed": completed})()


class TestProgressMath:
    def test_progress_is_completed_weight_over_total_weight(self):
        assert compute_progress([_item(1, True), _item(1, False)]) == 50.0
        assert compute_progress([_item(1, True), _item(3, True)]) == 100.0
        assert compute_progress([_item(1, False), _item(1, False)]) == 0.0

    def test_an_unmeasurable_application_is_null_never_zero_and_never_full(self):
        assert compute_progress([]) is None
        # Every task weighted zero means nothing counts towards the total.
        assert compute_progress([_item(0, False), _item(0, True)]) is None

    def test_zero_weight_tasks_are_excluded_from_both_sides(self):
        # A zero-weight task cannot drag the number down...
        assert compute_progress([_item(1, True), _item(0, False)]) == 100.0
        # ...nor count as completed.
        assert compute_progress([_item(1, False), _item(0, True)]) == 0.0

    def test_progress_is_always_within_bounds(self):
        cases = [
            [_item(1, True)],
            [_item(1, False)],
            [_item(2, True), _item(7, False)],
            [_item(5, True), _item(5, True)],
        ]
        for items in cases:
            value = compute_progress(items)
            assert value is None or 0.0 <= value <= 100.0

    def test_progress_cannot_rise_when_a_task_is_marked_incomplete(self):
        before = compute_progress([_item(1, True), _item(1, True)])
        after = compute_progress([_item(1, False), _item(1, True)])
        assert after < before

    def test_submit_task_is_excluded_because_submission_is_a_state(self, client, db):
        """Otherwise an application submitted by changing state reads as incomplete."""
        make_user(db, "submit-weight@example.com")
        scholarship = make_scholarship(db)
        login(client, "submit-weight@example.com")
        body = start(client, scholarship.id).json()

        submit_task = next(i for i in body["checklist"] if i["key"] == "submit_application")
        assert submit_task["weight"] == 0
        assert submit_task["is_counted"] is False


# ----------------------------------------------------------------- 8. notes


class TestNotes:
    def test_notes_round_trip_and_are_bounded(self, client, db):
        make_user(db, "notes@example.com")
        scholarship = make_scholarship(db)
        login(client, "notes@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        written = client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "notes": "Panel interview in March; referee is Dr Okafor."},
        )
        assert written.status_code == 200
        assert "Okafor" in written.json()["notes"]
        assert "Okafor" in client.get(f"/api/applications/{application_id}").json()["notes"]

        oversized = client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 2, "notes": "x" * 5001},
        )
        assert oversized.status_code == 422

    def test_notes_never_appear_on_a_public_response(self, client, db):
        make_user(db, "private@example.com")
        scholarship = make_scholarship(db)
        login(client, "private@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "notes": "SECRET-REF-12345"},
        )

        client.cookies.clear()
        public = client.get("/api/scholarships", params={"limit": 50}).text
        stats = client.get("/api/scholarships/stats").text
        detail = client.get(f"/api/scholarships/{scholarship.id}").text
        for payload in (public, stats, detail):
            # By value, not by field name: the public catalogue has an editorial
            # `notes` field of its own, and asserting on the name would pass for
            # the wrong reason while the real check went unrun.
            assert "SECRET-REF-12345" not in payload

    def test_notes_are_not_reachable_from_match_or_count(self, client, db):
        make_user(db, "engines@example.com")
        scholarship = make_scholarship(db)
        login(client, "engines@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "notes": "SECRET-ENGINE-LEAK"},
        )

        match = client.post(
            "/api/scholarships/match",
            json={"citizenship": "Netherlands", "intended_degree_level": "MASTER"},
        ).text
        counts = client.post("/api/v2/counts/intelligence", json={"capabilities": ["summary"]}).text
        assert "SECRET-ENGINE-LEAK" not in match
        assert "SECRET-ENGINE-LEAK" not in counts

    def test_control_characters_are_stripped_from_notes(self, client, db):
        make_user(db, "ctrl@example.com")
        scholarship = make_scholarship(db)
        login(client, "ctrl@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        body = client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "notes": "line one\nline two\x00\x07"},
        ).json()
        assert "\x00" not in body["notes"]
        assert "\x07" not in body["notes"]
        assert "line one" in body["notes"]


# ------------------------------------------------------------- 9. deadlines


class TestDeadlineSemantics:
    def test_days_remaining_comes_from_the_engine(self, client, db):
        make_user(db, "deadline@example.com")
        scholarship = make_scholarship(db, deadline_date=date(2026, 6, 15))
        login(client, "deadline@example.com")
        body = client.post(
            "/api/applications",
            json={"scholarship_id": scholarship.id},
            params={"as_of": AS_OF.isoformat()},
        ).json()

        # evaluate_deadline computes (2026-06-15 - 2026-06-01).days == 14.
        assert body["days_remaining"] == 14
        assert body["is_actionable"] is True
        assert body["is_overdue"] is False

    def test_a_rolling_deadline_is_never_zero_days(self, client, db):
        """An open round with no fixed date must not read as overdue or zero."""
        make_user(db, "rolling@example.com")
        scholarship = make_scholarship(
            db,
            deadline_date=None,
            deadline_display="Applications are reviewed on a rolling basis",
            deadline_precision="rolling",
        )
        login(client, "rolling@example.com")
        body = start(client, scholarship.id).json()

        assert body["days_remaining"] is None
        assert body["is_overdue"] is False
        assert body["is_actionable"] is False
        assert body["deadline_text"] == "Applications are reviewed on a rolling basis"

    def test_an_unpublished_deadline_reports_none(self, client, db):
        make_user(db, "unknown@example.com")
        scholarship = make_scholarship(
            db, deadline_date=None, deadline_display=None, deadline_precision="unknown"
        )
        login(client, "unknown@example.com")
        body = start(client, scholarship.id).json()
        assert body["days_remaining"] is None
        assert body["deadline_text"] is None

    def test_a_passed_deadline_is_overdue_not_negative_days_shown_as_open(self, client, db):
        make_user(db, "past@example.com")
        scholarship = make_scholarship(db, deadline_date=date(2026, 5, 1))
        login(client, "past@example.com")
        body = client.post(
            "/api/applications",
            json={"scholarship_id": scholarship.id},
            params={"as_of": AS_OF.isoformat()},
        ).json()

        assert body["days_remaining"] == -31
        assert body["is_overdue"] is True
        assert body["is_actionable"] is False

    def test_a_closed_round_is_not_available_for_application(self, client, db):
        make_user(db, "closed@example.com")
        scholarship = make_scholarship(db, status="closed", deadline_date=date(2027, 1, 1))
        login(client, "closed@example.com")
        response = start(client, scholarship.id)

        # Closed scholarships are excluded from the public catalogue and cannot
        # be applied to. The endpoint returns 404 to avoid being an existence
        # oracle for hidden records.
        assert response.status_code == 404

    def test_month_precision_is_reported_as_month(self, client, db):
        make_user(db, "month@example.com")
        scholarship = make_scholarship(
            db,
            deadline_date=date(2026, 6, 1),
            deadline_display="Applications close in June 2026",
            deadline_precision="month",
        )
        login(client, "month@example.com")
        body = start(client, scholarship.id).json()
        assert body["deadline_precision"] == "month"


# ------------------------------------------------- 10. concurrency / 409


class TestOptimisticConcurrency:
    def test_a_stale_update_is_refused_and_newer_data_survives(self, client, db):
        make_user(db, "race@example.com")
        scholarship = make_scholarship(db)
        login(client, "race@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        # Tab A reads version 1.
        tab_a = client.get(f"/api/applications/{application_id}").json()
        assert tab_a["version"] == 1

        # Tab B moves it to version 2.
        tab_b = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 1, "state": "planning"}
        )
        assert tab_b.status_code == 200
        assert tab_b.json()["version"] == 2

        # Tab A writes against the version it read.
        stale = client.patch(
            f"/api/applications/{application_id}", json={"expected_version": 1, "state": "in_progress"}
        )
        assert stale.status_code == 409
        assert "changed somewhere else" in stale.json()["detail"]

        # B's data is intact and A's write did not land.
        current = client.get(f"/api/applications/{application_id}").json()
        assert current["state"] == "planning"
        assert current["version"] == 2

    def test_a_stale_checklist_write_is_refused(self, client, db):
        make_user(db, "race2@example.com")
        scholarship = make_scholarship(db)
        login(client, "race2@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 1, "completed": True},
        )
        stale = client.patch(
            f"/api/applications/{application_id}/checklist/review_official_requirements",
            json={"expected_version": 1, "completed": True},
        )
        assert stale.status_code == 409

    def test_the_version_advances_on_every_accepted_write(self, client, db):
        make_user(db, "monotonic@example.com")
        scholarship = make_scholarship(db)
        login(client, "monotonic@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        versions = [1]
        for state in ("planning", "in_progress"):
            body = client.patch(
                f"/api/applications/{application_id}",
                json={"expected_version": versions[-1], "state": state},
            ).json()
            versions.append(body["version"])
        assert versions == [1, 2, 3]


# ------------------------------------------------------------ 11. visibility


class TestVisibility:
    def test_a_hidden_scholarship_cannot_be_applied_to(self, client, db):
        make_user(db, "hidden@example.com")
        hidden = make_scholarship(db, is_archived=True)
        login(client, "hidden@example.com")
        # 404, not 403: the endpoint must not confirm the record exists.
        assert start(client, hidden.id).status_code == 404

    def test_an_unlisted_application_is_still_readable_by_its_owner(self, client, db):
        """Archiving a round must not erase the student's history of it."""
        make_user(db, "history@example.com")
        scholarship = make_scholarship(db, deadline_date=date(2026, 12, 1))
        login(client, "history@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "notes": "Applied before the round closed."},
        )

        # The round closes and the record leaves the public universe.
        scholarship.is_archived = True
        db.commit()

        body = client.get(f"/api/applications/{application_id}").json()
        assert body["availability"]["is_available"] is False
        assert "no longer listed" in body["availability"]["reason"]
        # Snapshot keeps the history intelligible rather than blanking it.
        assert body["name"] == scholarship.title
        assert body["country"] == scholarship.country
        assert body["notes"] == "Applied before the round closed."
        # Trust is not claimed for a record that is no longer listed.
        assert body["verified"] is False
        assert body["verification_display"] == "No longer listed"

    def test_an_unlisted_application_offers_no_apply_cta(self, client, db):
        make_user(db, "nocta@example.com")
        scholarship = make_scholarship(db)
        login(client, "nocta@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        scholarship.is_archived = True
        db.commit()

        body = client.get(f"/api/applications/{application_id}").json()
        assert body["availability"]["is_available"] is False
        # The detail_url is the canonical location and remains valid; what must
        # not happen is a live-looking action for a closed round.
        assert body["state"] == "saved"
        assert body["is_actionable"] is False

    def test_unlisting_must_not_expose_internal_catalogue_fields(self, client, db):
        make_user(db, "internal@example.com")
        scholarship = make_scholarship(db)
        login(client, "internal@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        scholarship.is_archived = True
        scholarship.verification_notes = "INTERNAL-ONLY-REVIEW-NOTE"
        db.commit()

        body = client.get(f"/api/applications/{application_id}").json()
        serialized = str(body)
        assert "INTERNAL-ONLY-REVIEW-NOTE" not in serialized
        assert "verification_notes" not in serialized
        assert "verified_by" not in serialized


# ------------------------------------------------ 12. match / count agreement


class TestCanonicalEngineAgreement:
    def test_displayed_fit_equals_the_canonical_match_result(self, client, db):
        from app.services.auth import hash_password
        from app.models import StudentProfile
        from app.services.matching.types import MatchProfileRequest

        user = make_user(db, "engine@example.com")
        scholarship = make_scholarship(db)
        profile = MatchProfileRequest(
            citizenship="Netherlands",
            age=20,
            intended_degree_level="MASTER",
            intended_field="Computer Science",
            overall_result={"scale": "PERCENTAGE", "value": 80},
        )
        db.add(StudentProfile(user_id=user.id, payload=profile.model_dump(mode="json", exclude_none=True)))
        db.commit()

        login(client, "engine@example.com")
        body = start(client, scholarship.id).json()

        canonical = client.post(
            "/api/scholarships/match", json=profile.model_dump(mode="json", exclude_none=True)
        ).json()
        match_row = next((r for r in canonical["results"] if r["scholarship_id"] == scholarship.id), None)

        if match_row is None:
            pytest.skip("record not in the match result set for this fixture")
        # Copied, never recomputed.
        assert body["fit_score"] == match_row["fit_score"]
        assert body["fit_label_display"] == match_row["fit_label_display"]
        assert body["confidence_score"] == match_row["confidence_score"]
        assert body["readiness_label"] == (
            match_row["readiness"]["label"] if match_row.get("readiness") else None
        )

    def test_progress_is_never_the_match_score(self, client, db):
        """The two answer different questions and must not be conflated."""
        make_user(db, "separate@example.com")
        scholarship = make_scholarship(db)
        login(client, "separate@example.com")
        body = start(client, scholarship.id).json()

        # No profile means no match score, yet progress is still meaningful.
        assert body["progress_label"] == "Tasks completed"
        assert body["progress_percent"] is not None
        assert body["fit_score"] is None

    def test_the_workspace_does_not_change_count_mathematics(self, client, db):
        make_user(db, "counts@example.com")
        make_scholarship(db)
        login(client, "counts@example.com")
        start(client, 1)

        report = client.post("/api/v2/counts/intelligence", json={"capabilities": ["summary"]}).json()
        # Count Intelligence still reconciles itself against its own universe.
        for reconciliation in report["integrity"]["reconciliations"]:
            assert reconciliation["holds"] is True

    def test_workspace_vocabulary_is_published_so_a_client_cannot_drift(self, client, db):
        make_user(db, "vocab@example.com")
        login(client, "vocab@example.com")
        body = client.get("/api/applications").json()
        assert body["states"] == ["in_progress", "planning", "saved", "submitted", "withdrawn"]
        assert body["outcomes"] == ["accepted", "pending", "rejected", "waitlisted", "withdrawn"]
        assert body["universe"] == "user_applications"


# -------------------------------------------------------- 13. checklist origin


class TestChecklistProvenance:
    def test_derivation_never_names_a_document_without_published_evidence(self, db):
        from app.services.application_workspace import ScholarshipContext
        from app.services.matching.repository import CandidateRow

        # A record with no published documents must produce no document task.
        row = CandidateRow(
            id=1, title="No Documents", country="Ireland", degree="Master", funding="Full",
            program_type=None, status="open", deadline_date=None, deadline_display=None,
            deadline_precision="unknown", eligibility=[], eligibility_summary=None,
            requirements=[], documents=[], coverage=[], english_requirement=None,
            funding_amount=None, funding_currency=None, funding_period=None,
            tuition_coverage=None, living_cost_coverage=None, travel_coverage=None,
            fully_funded=False, official_source="Institute",
            official_source_url="https://x.example", official_details=None,
            is_verified=True, verification_status="active",
            last_verified_date=date(2026, 1, 1), next_verification_due=None,
            image_url=None, image_alt_text=None,
        )
        context = ScholarshipContext(row, True)
        items = derive_checklist("saved", context, None)

        document_tasks = [i for i in items if i["source"] == "published_requirement"]
        assert document_tasks == []

    def test_a_published_document_becomes_a_task_that_names_its_source(self, db):
        from app.services.application_workspace import ScholarshipContext
        from app.services.matching.repository import CandidateRow

        row = CandidateRow(
            id=2, title="With Documents", country="Ireland", degree="Master", funding="Full",
            program_type=None, status="open", deadline_date=None, deadline_display=None,
            deadline_precision="unknown", eligibility=[], eligibility_summary=None,
            requirements=[], documents=["Personal statement", "Two references"], coverage=[],
            english_requirement=None, funding_amount=None, funding_currency=None,
            funding_period=None, tuition_coverage=None, living_cost_coverage=None,
            travel_coverage=None, fully_funded=False, official_source="Institute",
            official_source_url="https://y.example", official_details=None,
            is_verified=True, verification_status="active",
            last_verified_date=date(2026, 1, 1), next_verification_due=None,
            image_url=None, image_alt_text=None,
        )
        items = derive_checklist("saved", ScholarshipContext(row, True), None)
        published = [i for i in items if i["source"] == "published_requirement"]

        assert len(published) == 2
        assert "Personal statement" in published[0]["label"]
        assert published[0]["source_detail"] == "documents"

    def test_derivation_is_deterministic(self, db):
        from app.services.application_workspace import ScholarshipContext
        from app.services.matching.repository import CandidateRow

        row = CandidateRow(
            id=3, title="Deterministic", country="Ireland", degree="Master", funding="Full",
            program_type=None, status="open", deadline_date=None, deadline_display=None,
            deadline_precision="unknown", eligibility=[], eligibility_summary=None,
            requirements=[], documents=["Transcript"], coverage=[], english_requirement=None,
            funding_amount=None, funding_currency=None, funding_period=None,
            tuition_coverage=None, living_cost_coverage=None, travel_coverage=None,
            fully_funded=False, official_source="Institute",
            official_source_url="https://z.example", official_details=None,
            is_verified=True, verification_status="active",
            last_verified_date=date(2026, 1, 1), next_verification_due=None,
            image_url=None, image_alt_text=None,
        )
        context = ScholarshipContext(row, True)
        first = [(i["key"], i["position"], i["weight"]) for i in derive_checklist("saved", context, None)]
        second = [(i["key"], i["position"], i["weight"]) for i in derive_checklist("saved", context, None)]
        assert first == second

    def test_submitted_applications_do_not_carry_a_submit_task(self, db):
        from app.services.application_workspace import ScholarshipContext
        from app.services.matching.repository import CandidateRow

        row = CandidateRow(
            id=4, title="Done", country="Ireland", degree="Master", funding="Full",
            program_type=None, status="open", deadline_date=None, deadline_display=None,
            deadline_precision="unknown", eligibility=[], eligibility_summary=None,
            requirements=[], documents=[], coverage=[], english_requirement=None,
            funding_amount=None, funding_currency=None, funding_period=None,
            tuition_coverage=None, living_cost_coverage=None, travel_coverage=None,
            fully_funded=False, official_source="Institute",
            official_source_url="https://w.example", official_details=None,
            is_verified=True, verification_status="active",
            last_verified_date=date(2026, 1, 1), next_verification_due=None,
            image_url=None, image_alt_text=None,
        )
        items = derive_checklist("submitted", ScholarshipContext(row, True), None)
        assert "submit_application" not in {item["key"] for item in items}


# ------------------------------------------------------------ 14. ordering


class TestDeterministicOrdering:
    def test_identical_state_produces_identical_order(self, client, db):
        make_user(db, "order@example.com")
        login(client, "order@example.com")
        for _ in range(3):
            scholarship = make_scholarship(db, deadline_date=date(2027, 1, 1))
            start(client, scholarship.id)

        first = [a["scholarship_id"] for a in client.get("/api/applications").json()["applications"]]
        second = [a["scholarship_id"] for a in client.get("/api/applications").json()["applications"]]
        assert first == second
        # Equal deadlines, so the id is the stable tiebreaker.
        assert first == sorted(first)

    def test_nearest_actionable_deadline_comes_first(self, client, db):
        make_user(db, "order2@example.com")
        login(client, "order2@example.com")
        far = make_scholarship(db, deadline_date=date(2026, 12, 1))
        near = make_scholarship(db, deadline_date=date(2026, 6, 10))
        rolling = make_scholarship(
            db, deadline_date=None, deadline_display="Rolling basis", deadline_precision="rolling"
        )
        for record in (far, rolling, near):
            start(client, record.id)

        body = client.get("/api/applications", params={"as_of": AS_OF.isoformat()}).json()
        assert [a["scholarship_id"] for a in body["applications"]][0] == near.id


# ------------------------------------------------------------ 15. migration


class TestMigrationIsSafeAndIdempotent:
    #: application_records exactly as it exists in production today, before this
    #: feature: no outcome, version, notes or snapshot columns.
    LEGACY_APPLICATION_RECORDS = """
        CREATE TABLE application_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scholarship_id INTEGER NOT NULL,
            state VARCHAR(16) NOT NULL DEFAULT 'saved',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """

    @staticmethod
    def _legacy_database(path):
        """A database in its pre-migration shape: the real upgrade scenario."""
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE scholarships (id INTEGER PRIMARY KEY AUTOINCREMENT, title VARCHAR(255))")
            conn.exec_driver_sql(TestMigrationIsSafeAndIdempotent.LEGACY_APPLICATION_RECORDS)
        return engine

    def test_a_fresh_database_gets_the_complete_shape_from_the_models(self, tmp_path):
        """A fresh install is created by ``create_all``, not by the upgrader.

        Production never runs ``create_all`` on startup, so this path is dev and
        test only. It is asserted because it is how every local environment gets
        the schema, and a model that disagreed with the migration would make the
        two environments behave differently.
        """
        from app.models import ApplicationChecklistItem, ApplicationRecord

        engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
        Base.metadata.create_all(engine)

        inspector = __import__("sqlalchemy").inspect(engine)
        columns = {c["name"] for c in inspector.get_columns(ApplicationRecord.__tablename__)}
        for expected in (
            "outcome", "version", "notes", "scholarship_name_snapshot",
            "scholarship_deadline_date_snapshot",
        ):
            assert expected in columns, expected
        assert "application_checklist_items" in inspector.get_table_names()
        assert ApplicationChecklistItem.__tablename__ in inspector.get_table_names()

    def test_upgrading_an_existing_database_is_additive_and_non_destructive(self, tmp_path):
        from migrate_schema import column_exists, run_migration, table_exists

        engine = self._legacy_database(tmp_path / "existing.db")
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO application_records (id, user_id, scholarship_id, state) VALUES (1, 7, 42, 'in_progress')"
            )

        run_migration(engine)

        assert table_exists(engine, "application_checklist_items")
        assert column_exists(engine, "application_records", "outcome")
        assert column_exists(engine, "application_records", "version")

        with engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT state, outcome, version, notes FROM application_records WHERE id = 1"
            ).fetchone()
        # The pre-existing application is still valid and still says in_progress.
        assert row[0] == "in_progress"
        assert row[1] == "pending"
        assert row[2] == 1
        assert row[3] is None

    def test_running_the_upgrade_twice_changes_nothing(self, tmp_path):
        from migrate_schema import run_migration

        engine = self._legacy_database(tmp_path / "twice.db")
        first = run_migration(engine)
        second = run_migration(engine)
        assert first
        assert second == [], "a second run must be a no-op"

    def test_the_upgrade_preserves_a_withdrawn_application_verbatim(self, tmp_path):
        """A destructive migration is the failure that loses a student's work."""
        from migrate_schema import run_migration

        engine = self._legacy_database(tmp_path / "preserve.db")
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO application_records (id, user_id, scholarship_id, state) "
                "VALUES (2, 7, 99, 'withdrawn')"
            )

        run_migration(engine)
        run_migration(engine)

        with engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT state, outcome, version FROM application_records WHERE id = 2"
            ).fetchone()
        assert row == ("withdrawn", "pending", 1)


# ------------------------------------------------------- 16. public separation


class TestPublicPrivateSeparation:
    def test_public_scholarship_schema_carries_no_application_fields(self, client, db):
        from app.schemas import ScholarshipDetailResponse, ScholarshipResponse

        public_fields = set(ScholarshipResponse.model_fields) | set(ScholarshipDetailResponse.model_fields)
        for private in (
            "state",
            "outcome",
            "version",
            "progress_percent",
            "checklist",
            "user_id",
            "completed_at",
            "checklist_total",
            "next_open_task",
        ):
            assert private not in public_fields

    def test_the_public_notes_field_is_the_scholarships_own_not_a_students(self):
        """The catalogue has an editorial ``notes`` field; it is a different thing.

        Asserting on the name alone would be misleading: the collision is real and
        harmless precisely because the two are unrelated. What must never happen
        is a student's note appearing in a public payload, and that is asserted by
        value elsewhere in this file.
        """
        from app.schemas import ScholarshipDetailResponse
        from app.schemas_application import ApplicationDetail

        assert "notes" in ScholarshipDetailResponse.model_fields
        assert "notes" in ApplicationDetail.model_fields

    def test_the_public_schema_does_not_inherit_from_the_application_schema(self):
        from app.schemas import ScholarshipDetailResponse, ScholarshipResponse
        from app.schemas_application import ApplicationDetail, ApplicationSummary

        # A private field reaching a public schema would leak through every public
        # surface at once. Inheritance is how that usually happens.
        for public in (ScholarshipResponse, ScholarshipDetailResponse):
            mro = set(public.__mro__)
            assert ApplicationDetail not in mro
            assert ApplicationSummary not in mro
        # And the private resource inherits only from its own private base.
        assert ApplicationDetail.__mro__[1] is ApplicationSummary


# ------------------------------------------------------- 17. cross-cutting


class TestInvariants:
    def test_a_student_with_no_applications_gets_an_honest_empty_list(self, client, db):
        make_user(db, "empty@example.com")
        login(client, "empty@example.com")
        body = client.get("/api/applications").json()

        assert body["applications"] == []
        assert body["count"] == 0
        assert body["universe"] == "user_applications"

    def test_repeated_reads_do_not_change_anything(self, client, db):
        make_user(db, "readonly@example.com")
        scholarship = make_scholarship(db)
        login(client, "readonly@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        first = client.get("/api/applications").json()
        second = client.get("/api/applications").json()
        assert first == second

        detail = client.get(f"/api/applications/{application_id}").json()
        assert detail["version"] == 1, "reading must not bump the version"

    def test_a_cross_site_origin_is_refused_for_state_changes(self, client, db):
        make_user(db, "origin@example.com")
        scholarship = make_scholarship(db)
        login(client, "origin@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        response = client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "state": "planning"},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 400
        assert "allowed origin" in response.json()["detail"]

    def test_a_matching_origin_is_permitted(self, client, db):
        make_user(db, "origin2@example.com")
        scholarship = make_scholarship(db)
        login(client, "origin2@example.com")
        application_id = start(client, scholarship.id).json()["id"]

        response = client.patch(
            f"/api/applications/{application_id}",
            json={"expected_version": 1, "state": "planning"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200


# ------------------------------------------------------ 18. dashboard integration


class TestDashboardIntegration:
    """The dashboard must not contradict the workspace, or erase it."""

    def test_dashboard_shows_an_application_whose_round_has_closed(self, client, db):
        """The regression this guards: a closing round silently deleting work.

        The dashboard previously dropped any application whose scholarship had
        left the public universe, so an application count could shrink with no
        explanation the moment a provider archived a round. The student's own
        record has to survive that.
        """
        make_user(db, "dash@example.com")
        scholarship = make_scholarship(db, deadline_date=date(2027, 1, 1))
        login(client, "dash@example.com")
        application_id = start(client, scholarship.id).json()["id"]
        assert client.get("/dashboard").json()["applications"]

        # The round closes.
        scholarship.is_archived = True
        db.commit()

        payload = client.get("/dashboard").json()
        assert len(payload["applications"]) == 1
        reference = payload["applications"][0]["scholarship"]
        assert reference["scholarship_id"] == scholarship.id
        assert reference["is_listed"] is False
        assert reference["name"] == scholarship.title
        assert reference["verified"] is False
        assert reference["verification_display"] == "No longer listed"
        assert application_id  # the workspace row itself is untouched

    def test_dashboard_keeps_showing_a_listed_application_normally(self, client, db):
        make_user(db, "dash2@example.com")
        scholarship = make_scholarship(db)
        login(client, "dash2@example.com")
        start(client, scholarship.id)

        reference = client.get("/dashboard").json()["applications"][0]["scholarship"]
        assert reference["is_listed"] is True
        assert reference["verified"] is True

    def test_the_dashboard_and_the_workspace_agree_on_the_count(self, client, db):
        make_user(db, "dash3@example.com")
        login(client, "dash3@example.com")
        for _ in range(3):
            scholarship = make_scholarship(db)
            start(client, scholarship.id)

        assert client.get("/dashboard").json()["applications"].__len__() == 3
        assert client.get("/api/applications").json()["count"] == 3

    def test_a_saved_only_hidden_scholarship_is_still_omitted(self, client, db):
        """No application history means nothing honest to show, so nothing is shown.

        Reconstructing it from the id alone would confirm the existence of a
        record the visibility contract hides.
        """
        make_user(db, "dash4@example.com")
        hidden = make_scholarship(db, is_archived=True)
        login(client, "dash4@example.com")
        assert client.get("/dashboard").json()["saved"] == []


class TestListCarriesTrustState:
    """Regression: the list row rendered an empty "Verification" label.

    The trust fields were declared on the detail schema only, so pydantic dropped
    them from the list response and the card rendered a heading with nothing
    under it. An API assertion on the detail endpoint would never have seen it,
    because only the summary row was missing them.
    """

    def test_the_list_row_carries_a_verification_label(self, client, db):
        make_user(db, "trust-row@example.com")
        scholarship = make_scholarship(db)
        login(client, "trust-row@example.com")
        start(client, scholarship.id)

        row = client.get("/api/applications").json()["applications"][0]
        assert row["verification_status"] == "active"
        assert row["verified"] is True
        assert row["verification_display"] == "Verified"

    def test_an_unlisted_row_never_carries_a_verified_claim(self, client, db):
        make_user(db, "trust-unlisted@example.com")
        scholarship = make_scholarship(db)
        login(client, "trust-unlisted@example.com")
        start(client, scholarship.id)

        scholarship.is_archived = True
        db.commit()

        row = client.get("/api/applications").json()["applications"][0]
        assert row["availability"]["is_available"] is False
        assert row["verified"] is False
        assert row["verification_display"] == "No longer listed"
