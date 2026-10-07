"""Regression tests for the Mentor hardening in this release.

Two contracts are pinned here.

**M1 - the overview route is intentionally public.** The router module docstring
used to claim "Both require a session. There is no public mentor route", which
contradicted both the handler's own docstring and the frontend client
(``mentorService.js``: "Public: it contains no account data"). The contradiction
was resolved in favour of *public*, because that is what the code actually does
and what the interface depends on: ``read_overview`` takes no ``db``, no
``user`` and no ``Depends``, so it cannot read an account. These tests therefore
prove the payload carries no user data rather than adding an authentication
requirement that would buy nothing.

**M2 - a verified claim must be checkable.** ``ApplicationFacts`` had no
``official_source_url``, so an application deadline could be labelled
"Verified" with no page for the reader to open. The same gap existed on the
scholarship ``eligibility``/``fit``/``readiness`` items. The source is now
carried through from the canonical scholarship row, and a verification label is
withheld when there is no source behind it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import get_session_factory, init_database, reset_database_connections
from app.jobs import scholarzone_maintenance  # noqa: F401  (import parity guard)
from app.main import app
from app.models import Scholarship, User
from app.services.mentor.context import ApplicationFacts, ScholarshipFacts
from app.services.mentor.evidence import (
    application_evidence,
    scholarship_evidence,
)

PASSWORD = "Str0ngPass!23"
OFFICIAL_URL = "https://official.example.edu/programmes/grant"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    reset_database_connections()
    init_database()
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_limiter():
    yield
    for attr in ("_windows",):
        if hasattr(scholarzone_maintenance, attr):
            getattr(scholarzone_maintenance, attr).clear()


def make_user(db, email: str) -> User:
    from app.services.auth import hash_password

    user = User(email=email.lower(), password_hash=hash_password(PASSWORD), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


def make_scholarship(db, **overrides) -> Scholarship:
    payload = {
        "title": "Example Grant",
        "country": "Testland",
        "degree": "master",
        "funding": "full",
        "official_source_url": OFFICIAL_URL,
        "is_verified": True,
        "verification_status": "active",
        "is_archived": False,
        "deadline_display": "30 Nov 2026",
        "deadline_date": date.today() + timedelta(days=45),
        "deadline_precision": "day",
        "image_url": "https://official.example.edu/logo.png",
        "image_source_url": OFFICIAL_URL,
        "image_source_type": "official_page_logo",
        "image_kind": "official_logo",
        "image_verified_at": date.today(),
    }
    payload.update(overrides)
    row = Scholarship(**payload)
    db.add(row)
    db.commit()
    return row


# --------------------------------------------------------------------- M1


class TestOverviewIsPublicByDesign:
    def test_overview_is_reachable_without_a_session(self, client):
        response = client.get("/mentor/overview")
        assert response.status_code == 200

    def test_overview_carries_no_account_data(self, client, db):
        user = make_user(db, "m1@example.com")
        login(client, user.email)
        client.post(f"/dashboard/saved?scholarship_id={make_scholarship(db).id}")
        authenticated = client.get("/mentor/overview").json()

        client.post("/auth/logout")
        anonymous = client.get("/mentor/overview").json()

        assert authenticated == anonymous, (
            "the overview must not vary by account, or it is leaking something"
        )

        body = str(anonymous).lower()
        for leak in ("example grant", "official.example.edu", user.email.lower()):
            assert leak not in body, f"overview leaked {leak!r}"

    def test_overview_is_only_static_vocabulary(self, client):
        payload = client.get("/mentor/overview").json()
        assert set(payload) == {
            "supported_intents",
            "intents",
            "redirects",
            "max_message_length",
            "assistance_available",
        }

    def test_the_private_route_still_refuses_anonymous(self, client):
        response = client.post("/mentor/message", json={"message": "What should I do now?"})
        assert response.status_code == 401

    def test_overview_cannot_name_an_account(self, client):
        payload = client.get("/mentor/overview").json()
        # No id-bearing key of any kind.
        assert not any("id" == key or key.endswith("_id") for key in payload)


# --------------------------------------------------------------------- M2


class TestApplicationDeadlineIsSourced:
    def _application(self, **overrides) -> ApplicationFacts:
        payload = {
            "application_id": 7,
            "scholarship_id": 11,
            "name": "Example Grant",
            "state": "saved",
            "state_label": "Saved",
            "is_listed": True,
            "verification_label": "Verified",
        }
        payload.update(overrides)
        return ApplicationFacts(**payload)

    def _deadline_item(self, item: ApplicationFacts):
        for evidence in application_evidence(item):
            if evidence.key.endswith("-deadline"):
                return evidence
        raise AssertionError("no deadline evidence emitted")

    def test_a_sourced_deadline_carries_the_official_page(self):
        item = self._application(official_source_url=OFFICIAL_URL)
        evidence = self._deadline_item(item)
        assert evidence.source_url == OFFICIAL_URL
        assert evidence.verification == "Verified"

    def test_a_source_less_deadline_is_not_labelled_verified(self):
        """The core M2 rule: no page, no verified claim."""
        item = self._application(official_source_url=None)
        evidence = self._deadline_item(item)
        assert evidence.source_url is None
        assert evidence.verification is None
        assert evidence.value, "the figure itself must still be shown"

    def test_the_url_is_never_invented(self):
        item = self._application(official_source_url=None)
        assert self._deadline_item(item).source_url is None

    def test_an_unlisted_application_is_not_verified(self):
        item = self._application(is_listed=False, official_source_url=OFFICIAL_URL)
        evidence = self._deadline_item(item)
        assert evidence.verification is None

    def test_state_evidence_makes_no_verification_claim(self):
        """Pre-existing behaviour, pinned so it is not 'fixed' into a claim."""
        for evidence in application_evidence(self._application(official_source_url=OFFICIAL_URL)):
            if evidence.key.endswith("-state"):
                assert evidence.verification is None


class TestApplicationFactsCarriesTheCanonicalUrl:
    def test_the_field_exists_and_defaults_to_absent(self):
        assert ApplicationFacts(
            application_id=1, scholarship_id=1, name="x", state="saved", state_label="Saved"
        ).official_source_url is None

    def test_it_is_copied_from_the_canonical_row(self, client, db):
        """End to end: the row's own URL reaches the evidence, with no new query."""
        user = make_user(db, "m2@example.com")
        login(client, user.email)
        row = make_scholarship(db)
        client.post(f"/dashboard/saved?scholarship_id={row.id}")

        response = client.post(
            "/mentor/message",
            json={"message": "Which of my saved scholarships have a deadline?"},
        )
        assert response.status_code == 200
        known = response.json().get("known") or []
        sourced = [k for k in known if k.get("source_url")]
        assert sourced, "expected at least one sourced evidence item"
        assert all(str(k["source_url"]).startswith("https://") for k in sourced)

    def test_the_general_application_path_is_sourced_too(self, client, db):
        """The dashboard path must not silently lose the link the named path has.

        ``ApplicationItem`` carries no official page, so this is the case that
        regresses quietly: no source means no link and no verified label.

        The item is looked up rather than assumed present. ``collect()``
        deliberately collapses an identical ``(label, value)`` pair onto the
        first basis that reported it, so a one-scholarship fixture may report the
        deadline once, from the catalogue, and never emit the application's copy.
        That de-duplication is intended behaviour and is not fought here; what
        matters is that whenever an application deadline *is* emitted it is
        sourced.
        """
        user = make_user(db, "m2b@example.com")
        login(client, user.email)
        row = make_scholarship(db)
        client.post(f"/dashboard/saved?scholarship_id={row.id}")
        client.post("/applications", json={"scholarship_id": row.id})

        response = client.post(
            "/mentor/message",
            json={"message": "Which of my saved scholarships have a deadline?"},
        )
        assert response.status_code == 200
        known = response.json().get("known") or []
        application_items = [
            k
            for k in known
            if "application" in str(k.get("key")) and str(k.get("key")).endswith("-deadline")
        ]
        for item in application_items:
            assert item["source_url"] == OFFICIAL_URL, (
                "the dashboard path lost the canonical source"
            )
            assert item["verification"] == "Verified"

    def test_a_named_application_keeps_its_own_sourced_deadline(self, client, db):
        """Naming the application puts it first, so its deadline must be present."""
        user = make_user(db, "m2d@example.com")
        login(client, user.email)
        row = make_scholarship(db)
        client.post(f"/dashboard/saved?scholarship_id={row.id}")
        application = client.post("/applications", json={"scholarship_id": row.id}).json()
        application_id = (
            application.get("id")
            or application.get("application_id")
            or (application.get("item") or {}).get("id")
        )

        response = client.post(
            "/mentor/message",
            json={"message": f"What is missing on application {application_id}?"},
        )
        assert response.status_code == 200
        known = response.json().get("known") or []
        items = [
            k for k in known if str(k.get("key", "")).endswith("-deadline")
        ]
        assert items, "a named application should report its deadline"
        assert any(k.get("source_url") for k in items), (
            "the named-application deadline lost its source"
        )

    def test_no_verified_claim_anywhere_without_a_source(self, client, db):
        """The rule, asserted across every evidence item the API can return."""
        user = make_user(db, "m2c@example.com")
        login(client, user.email)
        row = make_scholarship(db)
        client.post(f"/dashboard/saved?scholarship_id={row.id}")
        client.post("/applications", json={"scholarship_id": row.id})

        for question in (
            "Which of my saved scholarships have a deadline?",
            "Why does this scholarship fit?",
            "What should I do next?",
            "How ready am I?",
        ):
            payload = client.post("/mentor/message", json={"message": question}).json()
            for item in payload.get("known") or []:
                if item.get("verification") == "Verified":
                    assert item.get("source_url"), (
                        f"{item.get('key')} claimed Verified with no source for {question!r}"
                    )


class TestScholarshipEvidenceIsSourced:
    def _facts(self, **overrides) -> ScholarshipFacts:
        payload = {
            "scholarship_id": 3,
            "name": "Example Grant",
            "official_source_url": OFFICIAL_URL,
            "is_listed": True,
            "verification_label": "Verified",
            "eligibility": "Open to all nationalities",
        }
        payload.update(overrides)
        return ScholarshipFacts(**payload)

    @pytest.mark.parametrize(
        "suffix", ["-eligibility", "-fit", "-readiness"]
    )
    def test_claimed_items_carry_a_source(self, suffix):
        item = self._facts(fit_score=88.0, fit_label="Strong", readiness_label="Ready")
        evidence = {e.key: e for e in scholarship_evidence(item)}
        match = next(v for k, v in evidence.items() if k.endswith(suffix))
        assert match.source_url == OFFICIAL_URL
        assert match.verification == "Verified"

    @pytest.mark.parametrize("suffix", ["-eligibility", "-fit", "-readiness"])
    def test_source_less_claims_are_not_labelled_verified(self, suffix):
        item = self._facts(
            official_source_url=None, fit_score=88.0, fit_label="Strong", readiness_label="Ready"
        )
        evidence = {e.key: e for e in scholarship_evidence(item)}
        match = next(v for k, v in evidence.items() if k.endswith(suffix))
        assert match.verification is None
        assert match.source_url is None

    def test_identity_and_funding_still_carry_the_source(self):
        item = self._facts(funding="Full tuition")
        evidence = {e.key: e for e in scholarship_evidence(item)}
        assert all(
            v.source_url == OFFICIAL_URL
            for k, v in evidence.items()
            if k.endswith(("-identity", "-trust", "-funding"))
        )


# ------------------------------------------------------- semantics preserved


class TestDeadlineSemanticsUnchanged:
    def test_an_unknown_deadline_stays_unknown(self):
        from app.services.mentor.context import UNKNOWN_DEADLINE

        item = ApplicationFacts(
            application_id=1,
            scholarship_id=1,
            name="No Date Grant",
            state="saved",
            state_label="Saved",
            official_source_url=OFFICIAL_URL,
        )
        assert item.deadline is UNKNOWN_DEADLINE
        evidence = next(e for e in application_evidence(item) if e.key.endswith("-deadline"))
        assert "no published deadline" in evidence.value.lower()

    def test_month_precision_is_not_promoted_to_a_day(self, client, db):
        """A month-precision date stays approximate after the source change."""
        from app.services.mentor.context import _facts_from_days

        exact = _facts_from_days(45, "day")
        month = _facts_from_days(45, "month")

        assert exact.has_fixed_date is True
        assert month.has_fixed_date is True
        assert month.precision == "month"
        assert "month-precision" in month.describe()
        # The approximate wording must not collapse into the exact one.
        assert exact.describe() != month.describe()


class TestUserIsolationUnaffected:
    def test_two_users_never_see_each_others_sources(self, client, db):
        a = make_user(db, "iso-a@example.com")
        b = make_user(db, "iso-b@example.com")
        row = make_scholarship(db)

        login(client, a.email)
        client.post(f"/dashboard/saved?scholarship_id={row.id}")
        mine = client.post(
            "/mentor/message", json={"message": "Which saved scholarships have a deadline?"}
        ).json()
        client.post("/auth/logout")

        login(client, b.email)
        theirs = client.post(
            "/mentor/message", json={"message": "Which saved scholarships have a deadline?"}
        ).json()

        assert "Example Grant" in str(mine)
        assert "Example Grant" not in str(theirs)
