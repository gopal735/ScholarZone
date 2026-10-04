"""Tests for the student dashboard and the authentication it depends on.

Three things are being defended here, and they are different in kind.

**Ownership.** Every route resolves the caller from the session cookie, and the
tests assert that a second student cannot see, save, or move anything belonging
to the first - including by guessing an id, because the dashboard exposes ids in
its own responses.

**Trust.** The legacy ``is_verified`` column and the authoritative
``verification_status`` disagree on real records. These tests pin the rule that
the dashboard follows the status, so a record needing confirmation is never
rendered as "Verified".

**Honesty.** An absent deadline, an unevaluated fit score and a profile with
nothing in it are all reported as ``None``. The tests exist because turning any
of those into ``0`` would look like a measurement and would quietly become the
product's claim.
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
    ApplicationRecord,
    Base,
    SavedScholarship,
    Scholarship,
    ScholarshipReview,
    User,
    UserSession,
)
from app.services.auth import hash_password, token_fingerprint
from app.services.dashboard import build_dashboard, profile_is_empty, select_matches

#: Pinned so every deadline assertion in this file is exact and reproducible.
AS_OF = date(2026, 6, 1)

PASSWORD = "correct-horse-9"


# --------------------------------------------------------------------------- setup


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
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
    user = User(email=email, password_hash=hash_password(PASSWORD), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


#: ``official_source_url`` carries a unique constraint on the real schema, so
#: every fixture row gets its own. Two fixtures sharing one URL is a data error,
#: not a shortcut, and the resulting IntegrityError would look like a product bug.
_scholarship_sequence = itertools.count(1)


def make_scholarship(db, **overrides) -> Scholarship:
    """A publicly visible scholarship.

    The default fields satisfy ``public_visibility_conditions`` with the gates
    both off (as conftest sets them) and on, so a fixture row behaves like a
    real catalogue record rather than a special test-only shape.
    """
    sequence = next(_scholarship_sequence)
    values = {
        "title": f"Sample Scholarship {sequence}",
        "country": "Germany",
        "degree": "Master",
        "funding": "Full",
        "official_source": f"Sample University {sequence}",
        "official_source_url": f"https://sample.example/scholarship/{sequence}",
        "verification_status": "active",
        "is_verified": True,
        "status": "open",
        "deadline_date": date(2026, 9, 1),
        "deadline_display": "Applications close 1 September 2026",
        "deadline_precision": "exact",
    }
    values.update(overrides)
    record = Scholarship(**values)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def save_profile(db, user: User, **fields) -> None:
    from app.models import StudentProfile
    from app.services.matching.types import MatchProfileRequest

    validated = MatchProfileRequest.model_validate(fields)
    db.add(StudentProfile(user_id=user.id, payload=validated.model_dump(mode="json", exclude_none=True)))
    db.commit()


# ------------------------------------------------------------------- 1. auth


class TestAuthentication:
    def test_unauthenticated_dashboard_is_blocked(self, client, db):
        make_user(db, "student@example.com")
        response = client.get("/dashboard")
        assert response.status_code == 401

    def test_register_creates_account_and_signs_in(self, client, db):
        response = client.post(
            "/auth/register", json={"email": "New.Student@Example.com", "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        assert response.json()["user"]["email"] == "new.student@example.com"

        # The response already carries the session cookie, so the dashboard is
        # reachable without a second round trip to /auth/login.
        assert client.get("/dashboard").status_code == 200

    def test_password_is_never_stored_in_the_clear(self, client, db):
        client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
        stored = db.execute(select(User)).scalar_one()
        assert PASSWORD not in stored.password_hash
        assert stored.password_hash.startswith("pbkdf2_sha256$")

    def test_wrong_password_is_rejected_without_revealing_the_account_exists(self, client, db):
        make_user(db, "known@example.com")
        wrong = client.post("/auth/login", json={"email": "known@example.com", "password": "nope-nope-9"})
        missing = client.post("/auth/login", json={"email": "nobody@example.com", "password": "nope-nope-9"})

        assert wrong.status_code == 401
        assert missing.status_code == 401
        # Identical wording: the endpoint must not be an account-enumeration oracle.
        assert wrong.json()["detail"] == missing.json()["detail"]

    def test_session_endpoint_reports_signed_out_as_null_user(self, client, db):
        response = client.get("/auth/session")
        assert response.status_code == 200
        assert response.json() == {"user": None}

    def test_logout_revokes_the_session_server_side(self, client, db):
        user = make_user(db, "leaver@example.com")
        login(client, "leaver@example.com")
        assert client.get("/dashboard").status_code == 200

        assert client.post("/auth/logout").status_code == 204

        # Revoked, not merely forgotten: the row survives and is marked.
        record = db.execute(select(UserSession)).scalar_one()
        assert record.user_id == user.id
        assert record.revoked_at is not None

        # Clearing the cookie in the test client means the browser no longer
        # offers it; the point of the revoke is that restoring it would not help.
        assert client.get("/dashboard").status_code == 401

    def test_forged_session_cookie_is_refused(self, client, db):
        make_user(db, "real@example.com")
        client.cookies.set("scholarzone_session", "made-up-token")
        assert client.get("/dashboard").status_code == 401

    def test_expired_session_is_refused(self, client, db):
        user = make_user(db, "expired@example.com")
        db.add(
            UserSession(
                user_id=user.id,
                token_hash=token_fingerprint("valid-format-token"),
                expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()
        client.cookies.set("scholarzone_session", "valid-format-token")
        assert client.get("/dashboard").status_code == 401

    def test_deactivated_account_cannot_use_a_live_session(self, client, db):
        user = make_user(db, "disabled@example.com")
        login(client, "disabled@example.com")
        user.is_active = False
        db.commit()
        assert client.get("/dashboard").status_code == 401


# ------------------------------------------------------------- 2. ownership


class TestOwnership:
    def test_student_sees_only_their_own_shortlist(self, client, db):
        alice = make_user(db, "alice@example.com")
        bob = make_user(db, "bob@example.com")
        record = make_scholarship(db)

        db.add(SavedScholarship(user_id=alice.id, scholarship_id=record.id))
        db.add(SavedScholarship(user_id=bob.id, scholarship_id=record.id))
        db.commit()

        login(client, "alice@example.com")
        response = client.get("/dashboard/saved")
        assert response.status_code == 200
        # Both saved the same scholarship, so the id alone cannot distinguish
        # them; what must differ is that neither sees the other's row.
        assert response.json()["count"] == 1
        assert response.json()["scholarship_ids"] == [record.id]

    def test_a_second_student_cannot_remove_another_students_save(self, client, db):
        alice = make_user(db, "alice2@example.com")
        bob = make_user(db, "bob2@example.com")
        record = make_scholarship(db)
        db.add(SavedScholarship(user_id=alice.id, scholarship_id=record.id))
        db.commit()

        login(client, "bob2@example.com")
        response = client.delete(f"/dashboard/saved/{record.id}")
        assert response.status_code == 200
        assert response.json()["saved_count"] == 0

        # Alice's row is untouched.
        assert db.execute(select(SavedScholarship)).scalars().all() == [
            db.execute(select(SavedScholarship)).scalars().first()
        ]
        remaining = db.execute(select(SavedScholarship)).scalar_one()
        assert remaining.user_id == alice.id

    def test_mutations_reject_a_client_supplied_user_id(self, client, db):
        """A forged owner in the body must not widen access.

        The endpoints take no user id at all, so the payload is simply ignored
        by the schema's ``extra="forbid"`` - and, critically, the request is
        still evaluated against the session owner.
        """
        alice = make_user(db, "alice3@example.com")
        bob = make_user(db, "bob3@example.com")
        record = make_scholarship(db)

        login(client, "alice3@example.com")
        response = client.post(
            "/dashboard/saved", params={"scholarship_id": record.id}, json={"user_id": bob.id}
        )
        assert response.status_code == 200

        rows = db.execute(select(SavedScholarship)).scalars().all()
        assert len(rows) == 1
        assert rows[0].user_id == alice.id

    def test_query_string_cannot_name_another_user(self, client, db):
        alice = make_user(db, "alice4@example.com")
        record = make_scholarship(db)
        db.add(SavedScholarship(user_id=alice.id, scholarship_id=record.id))
        db.commit()

        login(client, "alice4@example.com")
        response = client.get("/dashboard/saved", params={"user_id": 999})
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_hidden_scholarship_cannot_be_saved(self, client, db):
        """A storage-only record is refused exactly as the directory hides it."""
        make_user(db, "alice5@example.com")
        hidden = make_scholarship(db, is_archived=True)
        login(client, "alice5@example.com")

        response = client.post("/dashboard/saved", params={"scholarship_id": hidden.id})
        # 404, not 403: a 403 would confirm the record exists.
        assert response.status_code == 404
        assert db.execute(select(SavedScholarship)).scalars().all() == []


# ------------------------------------------------------- 3/4. profile + strength


class TestProfileSnapshotAndStrength:
    def test_no_profile_yields_an_explicit_empty_state(self, client, db):
        make_user(db, "fresh@example.com")
        login(client, "fresh@example.com")

        payload = client.get("/dashboard").json()
        assert payload["has_profile"] is False
        assert payload["profile"]["is_empty"] is True
        assert payload["matches"] == []
        assert payload["saved"] == []
        assert payload["applications"] == []
        # With nothing supplied the engine returns score=None, not 0. A zero here
        # would read as "you scored zero on completeness" rather than "we were
        # not told anything".
        assert payload["profile_strength"]["score"] is None

    def test_snapshot_reports_supplied_and_missing_fields(self, client, db):
        user = make_user(db, "partial@example.com")
        save_profile(
            db,
            user,
            citizenship="Bangladesh",
            intended_degree_level="MASTER",
            overall_result={"scale": "PERCENTAGE", "value": 82.0},
        )
        login(client, "partial@example.com")

        fields = {item["key"]: item for item in client.get("/dashboard").json()["profile"]["fields"]}
        assert fields["citizenship"]["value"] == "Bangladesh"
        assert fields["citizenship"]["is_supplied"] is True
        assert fields["intended_degree_level"]["value"] == "Master"
        assert fields["overall_result"]["is_supplied"] is True
        # Absent fields are present in the payload with a null value, so the
        # snapshot and the "missing" list cannot describe different fields.
        assert fields["language_credentials"]["is_supplied"] is False
        assert fields["language_credentials"]["value"] is None

    def test_profile_strength_is_the_engines_deterministic_measure(self, client, db):
        user = make_user(db, "strong@example.com")
        save_profile(
            db,
            user,
            citizenship="Bangladesh",
            age=19,
            highest_qualification="Higher Secondary Certificate",
            graduation_year=2027,
            overall_result={"scale": "PERCENTAGE", "value": 85.0},
            intended_degree_level="MASTER",
            intended_field="Computer Science",
            funding_requirement="FULL_FUNDING",
            language_credentials=[{"test": "IELTS", "score": 7.5}],
        )
        login(client, "strong@example.com")

        strength = client.get("/dashboard").json()["profile_strength"]
        assert strength["score"] == 100.0
        # The engine's own locked weights, echoed rather than invented. These are
        # the fractions the engine divides by, which sum to 1.
        weights = {component["name"]: component["weight"] for component in strength["components"]}
        assert weights == {
            "academic": 0.25,
            "study_goal": 0.25,
            "language": 0.20,
            "funding": 0.20,
            "identity": 0.10,
        }
        assert sum(weights.values()) == pytest.approx(1.0)
        assert strength["complete"]

    def test_unknown_profile_field_is_rejected_not_silently_dropped(self, client, db):
        make_user(db, "typo@example.com")
        login(client, "typo@example.com")

        response = client.put("/dashboard/profile", json={"profile": {"citizenship": "Nepal", "gpa": 3.9}})
        assert response.status_code == 422

    def test_profile_round_trips_through_the_engine_schema(self, client, db):
        user = make_user(db, "round@example.com")
        login(client, "round@example.com")

        assert client.put(
            "/dashboard/profile", json={"profile": {"citizenship": "Nepal", "age": 20}}
        ).status_code == 200

        stored = client.get("/dashboard/profile").json()
        assert stored["profile"]["citizenship"] == "Nepal"
        assert stored["is_empty"] is False
        # The stored payload is exactly what the engine will score.
        assert build_dashboard(db, user, as_of=AS_OF).has_profile is True


# ------------------------------------------------------------- 5/6/7. match


class TestMatchIntegration:
    @pytest.fixture()
    def seeded(self, db):
        make_scholarship(
            db,
            title="Strong Local Match",
            deadline_date=date(2026, 7, 10),
            eligibility=["Bachelor's degree completed"],
            degree="Master",
            official_details={"eligibility": ["Bachelor's degree completed"]},
        )
        make_scholarship(
            db,
            title="Closing Very Soon",
            deadline_date=date(2026, 6, 5),
            official_source_url="https://soon.example/x",
        )
        return db

    def test_matches_carry_engine_scores_and_structured_evidence(self, client, seeded):
        user = make_user(seeded, "matcher@example.com")
        save_profile(
            seeded,
            user,
            citizenship="Germany",
            age=20,
            intended_degree_level="MASTER",
            intended_field="Computer Science",
            overall_result={"scale": "PERCENTAGE", "value": 80.0},
        )
        login(client, "matcher@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        assert payload["has_profile"] is True
        assert payload["matches"], "expected at least one recommendation"

        card = payload["matches"][0]
        # Scores come from Match, so they are present and in range; the test does
        # not recompute them.
        assert card["confidence_score"] is not None
        assert 0 <= card["confidence_score"] <= 100
        assert card["fit_label"]
        assert card["detail_url"].startswith("/scholarships/")
        # Evidence is structured: codes, never generated prose.
        for line in card["why"]:
            assert line["code"] and line["message"]

    def test_summary_counts_come_from_the_authoritative_engines(self, client, seeded):
        user = make_user(seeded, "counter@example.com")
        save_profile(seeded, user, citizenship="Germany", age=20, intended_degree_level="MASTER")
        login(client, "counter@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        summary = payload["summary"]

        # The universe is named on the object, not left for a reader to infer.
        assert summary["universe"] == "match_analysed"
        # The three eligibility states partition the analysed universe.
        assert (
            summary["eligible_count"]
            + summary["needs_verification_count"]
            + summary["ineligible_count"]
            == summary["total_candidates"]
        )
        assert summary["scored_count"] + summary["not_scored_count"] == summary["total_candidates"]

        consistency = payload["consistency"]
        assert consistency["counts_agree"] is True
        assert consistency["match_total_candidates"] == consistency["count_total_candidates"]

    def test_summary_never_disagrees_with_the_list_it_describes(self, client, seeded):
        """The failure this guards: a header count contradicting its own list."""
        user = make_user(seeded, "agree@example.com")
        save_profile(seeded, user, citizenship="Germany", age=20, intended_degree_level="MASTER")
        login(client, "agree@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        cards = payload["matches"]
        # Cards exclude INELIGIBLE records by design, so the assertion is that
        # the card set is a subset of the eligible + needs-verification set -
        # never larger.
        assert len(cards) <= payload["summary"]["eligible_count"] + payload["summary"][
            "needs_verification_count"
        ]
        assert all(card["eligibility"] != "INELIGIBLE" for card in cards)

    def test_ineligible_records_are_not_presented_as_recommendations(self, db):
        from app.services.matching.types import EligibilityStatus

        class FakeResult:
            def __init__(self, eligibility, scholarship_id):
                self.eligibility = eligibility
                self.scholarship_id = scholarship_id

        eligible = FakeResult(EligibilityStatus.ELIGIBLE, 1)
        refused = FakeResult(EligibilityStatus.INELIGIBLE, 2)

        assert select_matches([refused, eligible]) == [eligible]

        # Nothing survived the gate, so the section is empty rather than padded
        # with what the student cannot have.
        assert select_matches([refused]) == []

    def test_unverified_record_is_reported_not_resolved(self, client, seeded):
        """A published rule the engine could not settle stays visibly unsettled.

        The dashboard must not turn an open question into a recommendation: the
        record is still offered, but its trust state is presented as needing
        confirmation and the outstanding work is surfaced as a gap.
        """
        record = seeded.execute(select(Scholarship)).scalars().first()
        seeded.add(
            ScholarshipReview(
                scholarship_id=record.id,
                field_name="eligibility",
                decision="pending",
                conflict_reason="two official pages disagree",
                verification_state="needs_review",
                source_urls=[],
            )
        )
        record.verification_status = "needs_review"
        record.is_verified = True
        seeded.commit()

        user = make_user(seeded, "conflict@example.com")
        save_profile(seeded, user, citizenship="Germany", age=20, intended_degree_level="MASTER")
        login(client, "conflict@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        # Outstanding work is visible rather than silently resolved.
        assert payload["gaps"]
        for card in payload["matches"]:
            if card["scholarship_id"] == record.id:
                assert card["verified"] is False
                assert card["verification_display"] == "Confirm with provider"


# --------------------------------------------------------------- 8. saved


class TestSavedScholarships:
    def test_save_and_remove_round_trip(self, client, db):
        make_user(db, "saver@example.com")
        record = make_scholarship(db)
        login(client, "saver@example.com")

        saved = client.post("/dashboard/saved", params={"scholarship_id": record.id})
        assert saved.status_code == 200
        assert saved.json() == {"scholarship_id": record.id, "saved": True, "saved_count": 1}

        listed = client.get("/dashboard/saved").json()
        assert listed == {"scholarship_ids": [record.id], "count": 1}

        removed = client.delete(f"/dashboard/saved/{record.id}")
        assert removed.json() == {"scholarship_id": record.id, "saved": False, "saved_count": 0}

    def test_saving_twice_is_idempotent(self, client, db):
        make_user(db, "double@example.com")
        record = make_scholarship(db)
        login(client, "double@example.com")

        client.post("/dashboard/saved", params={"scholarship_id": record.id})
        response = client.post("/dashboard/saved", params={"scholarship_id": record.id})

        assert response.status_code == 200
        assert response.json()["saved_count"] == 1
        assert len(db.execute(select(SavedScholarship)).scalars().all()) == 1

    def test_header_count_always_matches_the_list(self, client, db):
        make_user(db, "counted@example.com")
        records = [make_scholarship(db, title=f"S{index}") for index in range(3)]
        login(client, "counted@example.com")

        for record in records[:2]:
            client.post("/dashboard/saved", params={"scholarship_id": record.id})

        payload = client.get("/dashboard").json()
        # The shortlist section and the shortlist count endpoint describe the
        # same set. A header that disagrees with its own list is the exact
        # inconsistency this guards against.
        listed = client.get("/dashboard/saved").json()
        assert len(payload["saved"]) == listed["count"] == 2

    def test_saved_items_appear_on_the_dashboard(self, client, db):
        user = make_user(db, "dash@example.com")
        record = make_scholarship(db)
        db.add(SavedScholarship(user_id=user.id, scholarship_id=record.id))
        db.commit()
        login(client, "dash@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        assert len(payload["saved"]) == 1
        assert payload["saved"][0]["scholarship"]["scholarship_id"] == record.id

    def test_unknown_scholarship_is_a_404(self, client, db):
        make_user(db, "ghost@example.com")
        login(client, "ghost@example.com")
        assert client.post("/dashboard/saved", params={"scholarship_id": 987654}).status_code == 404


# ------------------------------------------------- 9. deadline ordering


class TestDeadlineWatch:
    def test_ordering_is_nearest_then_readiness_then_id(self, client, db):
        user = make_user(db, "deadline@example.com")
        far = make_scholarship(db, title="Far", deadline_date=date(2026, 12, 1))
        near = make_scholarship(db, title="Near", deadline_date=date(2026, 6, 10))
        middle = make_scholarship(db, title="Middle", deadline_date=date(2026, 7, 1))

        for record in (far, near, middle):
            db.add(SavedScholarship(user_id=user.id, scholarship_id=record.id))
        db.commit()
        login(client, "deadline@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        days = [entry["days_remaining"] for entry in payload["deadlines"]]
        # Nearest actionable deadline first, computed by the engine.
        assert days == sorted(days)
        assert payload["deadlines"][0]["name"] == "Near"

    def test_record_without_a_published_date_reports_none_and_sorts_last(self, client, db):
        user = make_user(db, "nodate@example.com")
        dated = make_scholarship(db, title="Dated", deadline_date=date(2026, 6, 20))
        undated = make_scholarship(
            db,
            title="Rolling",
            deadline_date=None,
            deadline_display="Applications are reviewed on a rolling basis",
            deadline_precision="rolling",
        )
        for record in (dated, undated):
            db.add(SavedScholarship(user_id=user.id, scholarship_id=record.id))
        db.commit()
        login(client, "nodate@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        entries = payload["deadlines"]
        assert entries[0]["name"] == "Dated"
        assert entries[0]["days_remaining"] == 19

        rolling = entries[1]
        # None, never 0: an open round with no fixed date is not "zero days left".
        assert rolling["days_remaining"] is None
        assert rolling["is_actionable"] is False

    def test_identical_states_produce_identical_order(self, client, db):
        user = make_user(db, "stable@example.com")
        records = [
            make_scholarship(db, title=f"T{index}", deadline_date=date(2026, 8, 1))
            for index in range(4)
        ]
        for record in records:
            db.add(SavedScholarship(user_id=user.id, scholarship_id=record.id))
        db.commit()
        login(client, "stable@example.com")

        first = [entry["scholarship_id"] for entry in client.get("/dashboard").json()["deadlines"]]
        second = [entry["scholarship_id"] for entry in client.get("/dashboard").json()["deadlines"]]
        # Equal deadlines, so the scholarship id decides - deterministically.
        assert first == second
        assert first == sorted(first)


# --------------------------------------------------------- 10. application state


class TestApplicationState:
    def test_state_is_recorded_and_validated(self, client, db):
        make_user(db, "applicant@example.com")
        record = make_scholarship(db)
        login(client, "applicant@example.com")

        for state in ("planning", "in_progress", "submitted", "withdrawn", "saved"):
            response = client.put(
                f"/dashboard/applications/{record.id}", json={"state": state}
            )
            assert response.status_code == 200, response.text
            assert response.json()["state"] == state

    def test_unknown_state_is_rejected_before_reaching_the_database(self, client, db):
        make_user(db, "bad-state@example.com")
        record = make_scholarship(db)
        login(client, "bad-state@example.com")

        response = client.put(
            f"/dashboard/applications/{record.id}", json={"state": "accepted-with-congratulations"}
        )
        assert response.status_code == 422
        assert db.execute(select(ApplicationRecord)).scalars().all() == []

    def test_any_state_may_follow_any_other(self, client, db):
        """No workflow engine in 1.0: the dashboard records, it does not gate."""
        make_user(db, "jumper@example.com")
        record = make_scholarship(db)
        login(client, "jumper@example.com")

        client.put(f"/dashboard/applications/{record.id}", json={"state": "submitted"})
        response = client.put(f"/dashboard/applications/{record.id}", json={"state": "planning"})
        assert response.status_code == 200
        assert response.json()["state"] == "planning"

    def test_application_item_reports_deadline_and_updated_at(self, client, db):
        user = make_user(db, "detail@example.com")
        record = make_scholarship(db)
        db.add(ApplicationRecord(user_id=user.id, scholarship_id=record.id, state="in_progress"))
        db.commit()
        login(client, "detail@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        assert len(payload["applications"]) == 1
        item = payload["applications"][0]
        assert item["state"] == "in_progress"
        assert item["state_label"] == "In progress"
        assert item["updated_at"]

    def test_application_state_cannot_be_written_for_a_hidden_record(self, client, db):
        make_user(db, "hidden-app@example.com")
        hidden = make_scholarship(db, is_archived=True)
        login(client, "hidden-app@example.com")

        response = client.put(f"/dashboard/applications/{hidden.id}", json={"state": "planning"})
        assert response.status_code == 404
        assert db.execute(select(ApplicationRecord)).scalars().all() == []


# ------------------------------------------------------------ 11/12. gaps


class TestGapsAndNextActions:
    def test_gaps_come_from_the_engine_and_resolve_to_a_real_page(self, client, db):
        user = make_user(db, "gappy@example.com")
        make_scholarship(db)
        save_profile(db, user, citizenship="Germany")
        login(client, "gappy@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        assert payload["gaps"]
        for gap in payload["gaps"]:
            # Engine codes, not invented deficiencies. Profile-level codes come
            # from profile_strength; per-result codes come from Match's own gap
            # builder. Both are student-actionable and both resolve to the one
            # page that collects missing input.
            assert gap["code"]
            assert gap["message"]
            assert gap["href"] == "/match"
            assert gap["category"] == "MISSING_USER_INFORMATION"

    def test_next_actions_are_deterministic_and_ordered(self, client, db):
        user = make_user(db, "actions@example.com")
        record = make_scholarship(db)
        save_profile(db, user, citizenship="Germany")
        db.add(ApplicationRecord(user_id=user.id, scholarship_id=record.id, state="in_progress"))
        db.commit()
        login(client, "actions@example.com")

        first = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()["next_actions"]
        second = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()["next_actions"]

        assert [item["code"] for item in first] == [item["code"] for item in second]
        assert [item["priority"] for item in first] == sorted(item["priority"] for item in first)
        codes = [item["code"] for item in first]
        # An application in motion outranks starting something new.
        assert codes.index("improve_profile") < next(
            index for index, code in enumerate(codes) if code.startswith("continue_application_")
        )

    def test_first_run_action_is_to_build_a_profile(self, client, db):
        make_user(db, "empty@example.com")
        login(client, "empty@example.com")

        actions = client.get("/dashboard").json()["next_actions"]
        assert len(actions) == 1
        assert actions[0]["code"] == "complete_profile"
        assert actions[0]["href"] == "/match"

    def test_no_urgency_is_invented_when_nothing_is_pending(self, client, db):
        user = make_user(db, "settled@example.com")
        make_scholarship(db, deadline_date=date(2027, 6, 1))
        save_profile(
            db,
            user,
            citizenship="Germany",
            age=20,
            highest_qualification="Secondary",
            graduation_year=2027,
            overall_result={"scale": "PERCENTAGE", "value": 80.0},
            intended_degree_level="MASTER",
            intended_field="Computer Science",
            funding_requirement="FULL_FUNDING",
            language_credentials=[{"test": "IELTS", "score": 7.5}],
        )
        login(client, "settled@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        assert payload["profile_strength"]["score"] == 100.0
        # A complete profile with nothing in flight gets the browse action, not
        # an invented deadline.
        assert [item["code"] for item in payload["next_actions"]] == ["explore"]


# --------------------------------------------------- 15. trust semantics


class TestTrustPresentation:
    def test_needs_review_is_never_rendered_as_verified(self, client, db):
        make_user(db, "trust@example.com")
        record = make_scholarship(
            db,
            verification_status="needs_review",
            # Deliberately disagreeing with the status. The legacy column claims
            # verified; the status does not. The status wins.
            is_verified=True,
        )
        db.add(SavedScholarship(user_id=db.execute(select(User)).scalar_one().id, scholarship_id=record.id))
        db.commit()
        login(client, "trust@example.com")

        payload = client.get("/dashboard").json()
        saved = payload["saved"][0]["scholarship"]
        assert saved["verification_status"] == "needs_review"
        assert saved["verified"] is False
        assert saved["verification_display"] == "Confirm with provider"

    def test_active_status_is_the_only_source_of_a_verified_claim(self, client, db):
        make_user(db, "verified@example.com")
        record = make_scholarship(db, verification_status="active", is_verified=False)
        user = db.execute(select(User)).scalar_one()
        db.add(SavedScholarship(user_id=user.id, scholarship_id=record.id))
        db.commit()
        login(client, "verified@example.com")

        saved = client.get("/dashboard").json()["saved"][0]["scholarship"]
        # is_verified=False here, and the dashboard still reports the record as
        # verified - because the authoritative status says so.
        assert saved["verified"] is True
        assert saved["verification_display"] == "Verified"

    def test_match_card_trust_uses_the_status_not_the_legacy_column(self, client, db):
        user = make_user(db, "card-trust@example.com")
        make_scholarship(db, verification_status="needs_review", is_verified=True)
        save_profile(db, user, citizenship="Germany", age=20, intended_degree_level="MASTER")
        login(client, "card-trust@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        for card in payload["matches"]:
            assert card["verified"] is (card["verification_status"] == "active")
            if card["verification_status"] != "active":
                assert card["verification_display"] == "Confirm with provider"


# ------------------------------------------------------ 13. empty states


class TestEmptyStates:
    def test_dashboard_with_nothing_set_reports_every_section_as_empty(self, client, db):
        make_user(db, "void@example.com")
        login(client, "void@example.com")

        payload = client.get("/dashboard").json()
        assert payload["has_profile"] is False
        assert payload["matches"] == []
        assert payload["saved"] == []
        assert payload["deadlines"] == []
        assert payload["applications"] == []
        assert payload["profile"]["is_empty"] is True
        # One actionable suggestion, not a dead end.
        assert payload["next_actions"]

    def test_profile_but_no_saved_or_applications(self, client, db):
        user = make_user(db, "half@example.com")
        make_scholarship(db)
        save_profile(db, user, citizenship="Germany", age=20, intended_degree_level="MASTER")
        login(client, "half@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        assert payload["has_profile"] is True
        assert payload["saved"] == []
        assert payload["applications"] == []
        assert payload["deadlines"] == []

    def test_profile_payload_is_absent_for_a_student_who_never_saved_one(self, client, db):
        make_user(db, "nopayload@example.com")
        login(client, "nopayload@example.com")

        payload = client.get("/dashboard/profile").json()
        assert payload == {"profile": {}, "is_empty": True}


# ------------------------------------------------------------ 14. contract


class TestApiContract:
    def test_response_contains_every_documented_section(self, client, db):
        make_user(db, "shape@example.com")
        login(client, "shape@example.com")

        payload = client.get("/dashboard").json()
        assert {
            "as_of",
            "has_profile",
            "profile",
            "profile_strength",
            "summary",
            "consistency",
            "matches",
            "saved",
            "deadlines",
            "applications",
            "gaps",
            "next_actions",
        } <= set(payload)

    def test_as_of_is_echoed_so_a_response_is_reproducible(self, client, db):
        user = make_user(db, "clock@example.com")
        record = make_scholarship(db, deadline_date=date(2026, 6, 15))
        db.add(SavedScholarship(user_id=user.id, scholarship_id=record.id))
        db.commit()
        login(client, "clock@example.com")

        payload = client.get("/dashboard", params={"as_of": AS_OF.isoformat()}).json()
        assert payload["as_of"] == AS_OF.isoformat()
        assert payload["deadlines"][0]["days_remaining"] == 14

    def test_an_invalid_as_of_is_rejected(self, client, db):
        make_user(db, "bad-clock@example.com")
        login(client, "bad-clock@example.com")
        assert client.get("/dashboard", params={"as_of": "not-a-date"}).status_code == 422

    def test_profile_payload_is_not_disclosed_to_the_public_api(self, client, db):
        user = make_user(db, "leaky@example.com")
        save_profile(db, user, citizenship="Bangladesh", age=19)
        record = make_scholarship(db)
        login(client, "leaky@example.com")

        # The public catalogue carries no student data at all.
        public = client.get("/scholarships", params={"limit": 100}).json()
        assert "profile" not in public
        assert "citizenship" not in str(public)
        assert user.id not in [item.get("user_id") for item in public.get("items", [])]

        # And an anonymous caller sees no profile even though one exists.
        client.cookies.clear()
        assert client.get("/dashboard/profile").status_code == 401
        assert client.get("/scholarships", params={"limit": 100}).status_code == 200


class TestServiceUnitBehaviour:
    def test_profile_is_empty_ignores_request_only_options(self, db):
        from app.services.matching.types import MatchProfileRequest

        # limit and country_filter are request options, not facts about a
        # student, so a profile holding only those is still empty.
        assert profile_is_empty(MatchProfileRequest(limit=10, country_filter="Germany")) is True
        assert profile_is_empty(MatchProfileRequest(citizenship="Germany")) is False

    def test_deadline_facts_come_from_the_matching_engine(self, db):
        from app.services.dashboard import deadline_facts
        from app.services.matching.repository import CandidateRow

        row = CandidateRow(
            id=1,
            title="Rolling Programme",
            country="Ireland",
            degree="Master",
            funding="Full",
            program_type=None,
            status="open",
            deadline_date=None,
            deadline_display="Applications are reviewed on a rolling basis",
            deadline_precision="rolling",
            eligibility=[],
            eligibility_summary=None,
            requirements=[],
            documents=[],
            coverage=[],
            english_requirement=None,
            funding_amount=None,
            funding_currency=None,
            funding_period=None,
            tuition_coverage=None,
            living_cost_coverage=None,
            travel_coverage=None,
            fully_funded=False,
            official_source="Institute",
            official_source_url="https://rolling.example/x",
            official_details=None,
            is_verified=True,
            verification_status="active",
            last_verified_date=date(2026, 1, 1),
            next_verification_due=None,
            image_url=None,
            image_alt_text=None,
        )

        facts = deadline_facts(row, AS_OF)
        # No fixed date to count down to, reported as an open round rather than a
        # countdown that would read as zero.
        assert facts.days_remaining is None
        assert facts.closed is False

    def test_todays_date_is_never_implicit(self):
        """``as_of`` is injected, matching how the matching engine takes its clock."""
        import inspect

        from app.services.dashboard import build_dashboard

        signature = inspect.signature(build_dashboard)
        assert "as_of" in signature.parameters
        assert signature.parameters["as_of"].default is None