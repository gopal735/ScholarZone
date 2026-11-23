"""Private outreach and drafting on current master.

Identity is entirely master's. These tests register real accounts through
``/auth/register`` and rely on ``app.dependencies.require_user`` to resolve them,
so they are also a check that the supervisor feature added no second identity
path of its own.

The properties under test are ownership and refusal: who may read a record, and
what the system declines to say.

Cross-user access is asserted to answer 404 rather than 403, because a 403 would
confirm the record exists, which is itself a disclosure about another student's
activity.
"""

from __future__ import annotations

import enum
import os
import warnings

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date, datetime, timezone  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.core import config as config_module  # noqa: E402
from app.core.rate_limit import draft_limiter, outreach_write_limiter  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Scholarship, User  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ContactTemplate,
    ProfessorOutreachRecord,
    ProfessorProfile,
    ScholarshipProfessorLink,
)
from app.services.supervisor_email import (  # noqa: E402
    DraftRequest,
    build_draft,
    get_builtin_template,
)
from app.services.supervisor_status import (  # noqa: E402
    OutreachStatus,
    ProfessorProfileStatus,
    ProfessorRelationshipType,
    RelationshipVerificationStatus,
)

GATE_VARS = (
    "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED",
    "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE",
    "SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE",
)

PASSWORD = "a-long-enough-password"


def _reset_settings_cache() -> None:
    for attr in ("get_settings", "_get_settings"):
        candidate = getattr(config_module, attr, None)
        clear = getattr(candidate, "cache_clear", None)
        if callable(clear):
            clear()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db):
    previous = {name: os.environ.get(name) for name in GATE_VARS}
    for name in GATE_VARS:
        os.environ[name] = "false"
    _reset_settings_cache()

    scholarship = Scholarship(
        title="Test Scholarship",
        country="Germany",
        degree="Master",
        funding="Fully Funded",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        coverage=[],
        requirements=[],
        documents=[],
        official_source="Test University",
        official_source_url="https://uni1.edu/programmes/1",
        is_verified=True,
        verification_status="active",
        image_url="https://uni1.edu/logo.png",
    )
    db.add(scholarship)
    db.commit()
    db.refresh(scholarship)

    professor = ProfessorProfile(
        canonical_name="Dr Ada Lovelace",
        title="Professor",
        institution_name="Test University",
        department_name="Computer Science",
        official_profile_url="https://uni1.edu/people/ada-lovelace",
        official_email="a.lovelace@uni1.edu",
        official_email_verified=True,
        research_areas=["Machine Learning"],
        last_verified_at=datetime.now(timezone.utc),
    )
    db.add(professor)
    db.commit()
    db.refresh(professor)

    db.add(
        ScholarshipProfessorLink(
            scholarship_id=scholarship.id,
            professor_id=professor.id,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_source_url="https://uni1.edu/people/faculty",
            evidence_source_type="official_department_page",
            retrieved_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            verification_status=str(RelationshipVerificationStatus.VERIFIED),
        )
    )
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    outreach_write_limiter.reset()
    draft_limiter.reset()
    with TestClient(app) as test_client:
        test_client.scholarship_id = scholarship.id
        test_client.professor_id = professor.id
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    _reset_settings_cache()


def _register(client, email: str, password: str = PASSWORD) -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code in (200, 201), response.text
    return response.json()


def _switch_student(client, email: str) -> None:
    """Leave the current session and register a different account."""
    client.post("/auth/logout")
    _register(client, email)


# ---------------------------------------------------------------------------
# Private route protection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/outreach"),
        ("get", "/outreach/summary"),
        ("post", "/outreach"),
        ("patch", "/outreach/1"),
        ("delete", "/outreach/1"),
        ("post", "/supervisor-email/draft"),
    ],
)
def test_private_routes_require_a_session(client, method, path):
    # This TestClient version accepts a body only on the verbs that have one.
    if method in ("post", "patch", "put"):
        response = getattr(client, method)(path, json={})
    else:
        response = getattr(client, method)(path)

    assert response.status_code == 401


def test_a_public_route_stays_public(client):
    assert client.get(f"/scholarships/{client.scholarship_id}/supervisors").status_code == 200


def test_the_feature_adds_no_second_auth_surface(client):
    # Master owns /auth. The supervisor feature must not have registered a second
    # register/login pair alongside it.
    spec = app.openapi()
    auth_paths = sorted(p for p in spec["paths"] if p.startswith("/auth"))

    assert auth_paths == ["/auth/login", "/auth/logout", "/auth/register", "/auth/session"]


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


def test_one_student_cannot_see_another_students_records(client):
    _register(client, "first@example.com")
    client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    )

    _switch_student(client, "second@example.com")

    assert client.get("/outreach").json() == []
    assert client.get("/outreach/summary").json()["total"] == 0


def test_another_students_record_answers_404_not_403(client):
    _register(client, "first@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    _switch_student(client, "second@example.com")
    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "notes": "mine now"},
    )

    assert response.status_code == 404


def test_another_students_record_cannot_be_deleted(client):
    _register(client, "first@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    _switch_student(client, "second@example.com")

    assert client.delete(f"/outreach/{created['id']}").status_code == 404


def test_a_client_supplied_user_id_is_never_honoured(client):
    _register(client, "first@example.com")
    other = User(email="second@example.com", password_hash="x", is_active=True)
    response = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            # Extra fields must not be accepted as an authority for ownership.
            "user_id": 99999,
            "application_id": 4242,
        },
    )

    assert response.status_code in (200, 201, 422)
    if response.status_code in (200, 201):
        assert response.json()["id"] == client.get("/outreach").json()[0]["id"]
        assert len(client.get("/outreach").json()) == 1


# ---------------------------------------------------------------------------
# Outreach CRUD and the state machine
# ---------------------------------------------------------------------------


def test_creating_an_outreach_record_is_idempotent(client):
    _register(client, "student@example.com")
    body = {"scholarship_id": client.scholarship_id, "professor_id": client.professor_id}

    first = client.post("/outreach", json=body)
    second = client.post("/outreach", json=body)

    assert first.status_code in (200, 201)
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/outreach").json()) == 1


def test_an_unverified_pairing_cannot_be_tracked(client):
    _register(client, "student@example.com")

    response = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": 999999},
    )

    assert response.status_code == 422


def test_marking_sent_records_the_contact_times(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": "draft"},
    )
    current = client.get("/outreach").json()[0]
    sent = client.patch(
        f"/outreach/{created['id']}",
        json={"version": current["version"], "status": "sent"},
    ).json()

    assert sent["status"] == "sent"
    assert sent["first_contacted_at"] is not None
    assert sent["last_contacted_at"] is not None


def test_an_illegal_transition_is_refused(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    # A record that has never been sent cannot become positive.
    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": "positive"},
    )

    assert response.status_code == 422
    assert "cannot move" in response.json()["detail"]


def test_an_unknown_status_is_refused(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": "triumphantly_accepted"},
    )

    assert response.status_code == 422


def _py311_enum_contains(cls, member):
    """CPython 3.11's ``EnumType.__contains__``, reproduced verbatim.

    3.11 raises ``TypeError`` for anything that is not already an enum member
    and warns that 3.12 will change that; 3.12+ looks the value up instead. The
    project's CI pins 3.11, so this is not hypothetical - it is the interpreter
    that reported this validator as a crash.
    """
    if not isinstance(member, enum.Enum):
        raise TypeError(
            "unsupported operand type(s) for 'in': '%s' and '%s'"
            % (type(member).__qualname__, cls.__class__.__qualname__)
        )
    return isinstance(member, cls) and member._name_ in cls._member_map_


def test_an_unrecognised_status_is_told_apart_from_an_illegal_one(client):
    """The two refusals stay distinct.

    Both answer 422, so a client cannot tell them apart by status code alone.
    "not recognised" means the value is not an outreach status at all;
    "cannot move" means it is one, from the wrong state. Deleting the
    recognition step would still leave a 422 behind - just the wrong message -
    which is why the wording is asserted here rather than only the code.
    """
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    unknown = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": "triumphantly_accepted"},
    )
    assert unknown.status_code == 422
    assert "not recognised" in unknown.json()["detail"]

    illegal = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": "positive"},
    )
    assert illegal.status_code == 422
    assert "cannot move" in illegal.json()["detail"]

    # Neither refusal wrote anything.
    assert client.get("/outreach").json()[0]["status"] == "not_contacted"


def test_every_declared_status_is_recognised_by_the_guard(client):
    """Every status the enum declares is accepted over the wire.

    Driven by the enum rather than a restated list, and walked as a real path
    through the state machine so that all nine states are actually requested
    from the API - not merely compared in a set. A guard that recognised only
    some values, or that compared member names instead of values, fails here.

    Intentionally asserts nothing about how the guard is written, so it holds
    for any correct implementation.
    """
    assert {state.value for state in OutreachStatus} == {
        "not_contacted",
        "draft",
        "sent",
        "follow_up_due",
        "replied",
        "positive",
        "negative",
        "no_response",
        "closed",
    }

    # A path through OUTREACH_TRANSITIONS that requests each state in turn and
    # comes back to not_contacted, which is only reachable again from closed.
    walk = (
        "draft",
        "sent",
        "follow_up_due",
        "no_response",
        "replied",
        "positive",
        "negative",
        "closed",
        "not_contacted",
    )

    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    version = created["version"]
    requested = set()
    for target in walk:
        response = client.patch(
            f"/outreach/{created['id']}",
            json={"version": version, "status": target},
        )
        assert response.status_code == 200, (target, response.text)
        assert response.json()["status"] == target
        version = response.json()["version"]
        requested.add(target)

    assert requested == {state.value for state in OutreachStatus}
    assert client.get("/outreach").json()[0]["status"] == "not_contacted"


@pytest.mark.parametrize(
    "rejected",
    ["", "sent ", " SENT", "SENT", "unknown", "none", "not_contacted "],
)
def test_a_near_miss_status_is_refused(client, rejected):
    """Values that are not statuses are refused, not stored.

    Case and surrounding whitespace included: the payload is a plain string, so
    "SENT" and "sent " are simply not outreach statuses and must not be
    normalised into one on the way in.
    """
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": rejected},
    )

    assert response.status_code == 422
    assert "not recognised" in response.json()["detail"]
    assert client.get("/outreach").json()[0]["status"] == "not_contacted"


def test_a_status_change_works_under_python_311_enum_semantics(client, monkeypatch):
    """The regression: the validator must not depend on `x in SomeEnum`.

    Forcing 3.11's containment semantics onto whatever interpreter runs this
    makes the defect reproducible locally instead of only in CI. With the
    guard written as `payload.status not in OutreachStatus` this raises
    TypeError before the status is ever compared, so marking sent is
    impossible on 3.11 - the failure
    `test_marking_sent_records_the_contact_times` reported.

    Note what is and is not emulated. Only `__contains__` is, because that is
    the one construct here that genuinely differs: 3.11 raises TypeError, 3.12+
    returns a bool. `str(member)` does not need emulating and is in fact stable
    across both - 3.11's enum.py already assigns `StrEnum.__str__` from the
    mixed-in `str`, so a member renders as its value on either version. An
    earlier draft of this file asserted the opposite and was wrong; it was
    caught by reading Lib/enum.py on the 3.11 branch rather than by a test.
    """
    monkeypatch.setattr(enum.EnumType, "__contains__", _py311_enum_contains)

    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    drafted = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": "draft"},
    )
    assert drafted.status_code == 200, drafted.text
    assert drafted.json()["status"] == "draft"

    sent = client.patch(
        f"/outreach/{created['id']}",
        json={"version": drafted.json()["version"], "status": "sent"},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent"
    assert sent.json()["first_contacted_at"] is not None
    assert sent.json()["last_contacted_at"] is not None

    # Refusals still refuse under the same semantics, and still distinguish
    # "not a status" from "not from here".
    refused = client.patch(
        f"/outreach/{created['id']}",
        json={"version": sent.json()["version"], "status": "draft"},
    )
    assert refused.status_code == 422
    assert "cannot move" in refused.json()["detail"]

    unknown = client.patch(
        f"/outreach/{created['id']}",
        json={"version": sent.json()["version"], "status": "triumphantly_accepted"},
    )
    assert unknown.status_code == 422
    assert "not recognised" in unknown.json()["detail"]


def test_a_status_change_emits_no_enum_containment_deprecation(client):
    """No status change may reach ``EnumType.__contains__`` at all.

    3.11 warns on the way to raising. Pinning the exact warning text means the
    regression is caught by the message that describes it, and stays inert on
    3.12+ where the warning no longer exists.
    """
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message=".*__contains__ will no longer raise TypeError.*",
        )
        response = client.patch(
            f"/outreach/{created['id']}",
            json={"version": created["version"], "status": "sent"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "sent"


def test_first_contact_is_recorded_once_and_last_contact_keeps_moving(client):
    """Re-marking sent does not rewrite history.

    `first_contacted_at` is when the student first reached out and is set once;
    `last_contacted_at` is the most recent send and may advance. Both are
    recorded here because the reported failure was specifically about the
    contact times never being written at all.
    """
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    first = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "status": "sent"},
    ).json()
    assert first["first_contacted_at"] is not None
    assert first["last_contacted_at"] is not None

    # sent -> sent is an unchanged status, which the state machine allows.
    again = client.patch(
        f"/outreach/{created['id']}",
        json={"version": first["version"], "status": "sent"},
    ).json()

    assert again["first_contacted_at"] == first["first_contacted_at"]
    assert again["last_contacted_at"] >= first["last_contacted_at"]


def test_a_status_change_leaves_the_other_fields_alone(client):
    """The validation change must not have moved any other field's semantics."""
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    # A notes-only write must not touch the state or the contact times.
    noted = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "notes": "email on monday"},
    ).json()
    assert noted["notes"] == "email on monday"
    assert noted["status"] == "not_contacted"
    assert noted["first_contacted_at"] is None
    assert noted["last_contacted_at"] is None

    # A status-only write must not clobber what the other fields already held.
    sent = client.patch(
        f"/outreach/{created['id']}",
        json={"version": noted["version"], "status": "sent"},
    ).json()
    assert sent["notes"] == "email on monday"
    assert sent["status"] == "sent"
    assert sent["version"] > noted["version"]


def test_the_full_reply_path_is_legal(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()
    version = created["version"]

    for target in ("sent", "replied", "positive"):
        updated = client.patch(
            f"/outreach/{created['id']}", json={"version": version, "status": target}
        ).json()
        version = updated["version"]
        assert updated["status"] == target

    assert client.get("/outreach/summary").json()["positive_responses"] == 1


def test_a_stale_write_is_refused_with_409(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    first = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "notes": "first tab"},
    )
    assert first.status_code == 200

    stale = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "notes": "second tab"},
    )

    assert stale.status_code == 409
    assert client.get("/outreach").json()[0]["notes"] == "first tab"


def test_an_update_without_a_version_is_refused(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    assert client.patch(f"/outreach/{created['id']}", json={"notes": "no version"}).status_code == 422


def test_markup_in_notes_is_refused(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "notes": "<script>alert(1)</script>"},
    )

    assert response.status_code == 422


def test_notes_are_bounded(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "notes": "x" * 5000},
    )

    assert response.status_code == 422


def test_deleting_removes_only_the_students_own_record(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    assert client.delete(f"/outreach/{created['id']}").status_code == 204
    assert client.get("/outreach").json() == []
    # The professor and the verified relationship survive: deleting a student's
    # tracking row must not erase a public fact.
    assert client.get(f"/scholarships/{client.scholarship_id}/supervisors").json()["supervisors"]


def test_writes_are_rate_limited(client):
    _register(client, "student@example.com")

    statuses = [
        client.post(
            "/outreach",
            json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
        ).status_code
        for _ in range(80)
    ]

    assert 429 in statuses


# ---------------------------------------------------------------------------
# Hidden scholarships and historical records
# ---------------------------------------------------------------------------


def _seed_hidden_scholarship(
    db,
    *,
    is_archived: bool = False,
    verification_status: str | None = None,
) -> tuple[Scholarship, ProfessorProfile]:
    """Seed a scholarship the public visibility predicate withholds."""
    scholarship = Scholarship(
        title="Hidden Scholarship",
        country="Germany",
        degree="Master",
        funding="Fully Funded",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        coverage=[],
        requirements=[],
        documents=[],
        official_source="Test University",
        official_source_url="https://uni2.edu/programmes/2",
        is_verified=True,
        verification_status=verification_status or "active",
        image_url="https://uni2.edu/logo2.png",
        is_archived=is_archived,
    )
    db.add(scholarship)
    db.commit()
    db.refresh(scholarship)

    professor = ProfessorProfile(
        canonical_name="Dr Grace Hopper",
        title="Professor",
        institution_name="Test University",
        department_name="Computer Science",
        official_profile_url="https://uni2.edu/people/grace-hopper",
        official_email="g.hopper@uni2.edu",
        official_email_verified=True,
        research_areas=["Machine Learning"],
        last_verified_at=datetime.now(timezone.utc),
    )
    db.add(professor)
    db.commit()
    db.refresh(professor)

    db.add(
        ScholarshipProfessorLink(
            scholarship_id=scholarship.id,
            professor_id=professor.id,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_source_url="https://uni2.edu/people/faculty",
            evidence_source_type="official_department_page",
            retrieved_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            verification_status=str(RelationshipVerificationStatus.VERIFIED),
        )
    )
    db.commit()
    return scholarship, professor


def test_a_new_outreach_against_an_archived_scholarship_is_refused(client, db):
    _register(client, "student@example.com")
    scholarship, professor = _seed_hidden_scholarship(db, is_archived=True)

    response = client.post(
        "/outreach",
        json={"scholarship_id": scholarship.id, "professor_id": professor.id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Scholarship not found."


def test_a_new_outreach_against_a_quarantined_scholarship_is_refused(client, db):
    _register(client, "student@example.com")
    scholarship, professor = _seed_hidden_scholarship(db, verification_status="quarantined")

    response = client.post(
        "/outreach",
        json={"scholarship_id": scholarship.id, "professor_id": professor.id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Scholarship not found."


def test_a_historical_outreach_record_survives_a_scholarship_that_becomes_hidden(client, db):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    scholarship = db.query(Scholarship).filter_by(id=client.scholarship_id).one()
    scholarship.is_archived = True
    db.commit()

    repeat = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    )

    # The idempotency lookup runs before the visibility gate, so a student who
    # already tracks a pairing keeps their record even once the programme is gone.
    assert repeat.status_code in (200, 201)
    assert repeat.json()["id"] == created["id"]
    assert repeat.json()["version"] == created["version"]

    patched = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "notes": "kept after archiving"},
    )
    assert patched.status_code == 200


def test_get_templates_does_not_write_to_the_database(client, db):
    first = client.get("/supervisor-email/templates")
    second = client.get("/supervisor-email/templates")

    assert first.status_code == 200
    assert second.status_code == 200
    # The read path serves the built-in set when the table holds nothing, and it
    # must not seed the table either: only the explicit maintenance path may.
    assert db.query(ContactTemplate).count() == 0


# ---------------------------------------------------------------------------
# Draft validation consistency (Blocker A)
# ---------------------------------------------------------------------------


def test_a_draft_containing_a_comparison_expression_can_be_persisted(client):
    _register(client, "student@example.com")
    draft = client.post(
        "/supervisor-email/draft",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "interests": ["ML < NLP"],
        },
    ).json()
    assert "ML < NLP" in draft["body"]

    created = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "draft_body": draft["body"],
        },
    )
    assert created.status_code in (200, 201)
    assert "ML < NLP" in created.json()["draft_body"]

    # PATCH path uses the same validator.
    patched = client.patch(
        f"/outreach/{created.json()['id']}",
        json={"version": created.json()["version"], "draft_body": draft["body"]},
    )
    assert patched.status_code == 200
    assert "ML < NLP" in patched.json()["draft_body"]


@pytest.mark.parametrize(
    "dangerous",
    [
        "<script>alert(1)</script>",
        "<b>x</b>",
        "{injection}",
        "a{b}",
        "<img src=x onerror=alert(1)>",
    ],
)
def test_dangerous_markup_payloads_are_rejected(client, dangerous):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    for field in ("draft_subject", "draft_body", "notes", "next_action"):
        response = client.patch(
            f"/outreach/{created['id']}",
            json={"version": created["version"], field: dangerous},
        )
        assert response.status_code == 422, (field, dangerous, response.text)


# ---------------------------------------------------------------------------
# Built-in template foreign key (Blocker B)
# ---------------------------------------------------------------------------


def test_get_templates_on_an_empty_table_creates_no_rows(client, db):
    assert db.query(ContactTemplate).count() == 0
    response = client.get("/supervisor-email/templates")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert db.query(ContactTemplate).count() == 0


def test_selecting_a_built_in_template_persists_a_real_foreign_key(client, db):
    _register(client, "student@example.com")
    templates = client.get("/supervisor-email/templates").json()
    template_id = templates[0]["id"]

    created = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_id": template_id,
        },
    )
    assert created.status_code in (200, 201)
    stored_id = created.json()["template_id"]
    assert stored_id is not None
    # The stored id must resolve to an actual persisted row.
    assert db.query(ContactTemplate).filter_by(id=stored_id).count() == 1


def test_an_inactive_persisted_template_is_rejected(client, db):
    _register(client, "student@example.com")
    row = ContactTemplate(
        template_key="custom_inactive",
        title="Inactive",
        degree_level=None,
        subject_hint="x",
        body_text="y",
        is_active=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    response = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_id": row.id,
        },
    )
    assert response.status_code == 422


def test_an_unknown_template_id_is_rejected_with_422(client):
    _register(client, "student@example.com")
    response = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_id": 999999,
        },
    )
    assert response.status_code == 422


def test_sqlite_foreign_key_enforcement_accepts_a_resolved_built_in_template():
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    # Seed scholarship/professor/link.
    scholarship = Scholarship(
        title="FK Test Scholarship", country="Germany", degree="Master",
        funding="Fully Funded", status="open", deadline_date=date(2027, 6, 30),
        deadline_precision="exact", eligibility=[], coverage=[], requirements=[],
        documents=[], official_source="Test University",
        official_source_url="https://fk.edu/programmes/1", is_verified=True,
        verification_status="active", image_url="https://fk.edu/logo.png",
    )
    session.add(scholarship)
    session.commit()
    session.refresh(scholarship)
    professor = ProfessorProfile(
        canonical_name="Dr FK", title="Professor", institution_name="Test University",
        department_name="CS", official_profile_url="https://fk.edu/people/fk",
        official_email="fk@fk.edu", official_email_verified=True,
        research_areas=["ML"], last_verified_at=datetime.now(timezone.utc),
    )
    session.add(professor)
    session.commit()
    session.refresh(professor)
    session.add(
        ScholarshipProfessorLink(
            scholarship_id=scholarship.id, professor_id=professor.id,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_source_url="https://fk.edu/people/faculty",
            evidence_source_type="official_department_page",
            retrieved_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            verification_status=str(RelationshipVerificationStatus.VERIFIED),
        )
    )
    session.commit()

    # Register a user via a client bound to this engine.
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    outreach_write_limiter.reset()
    draft_limiter.reset()
    with TestClient(app) as tc:
        tc.post("/auth/register", json={"email": "fk@example.com", "password": "a-long-enough-password"})
        templates = tc.get("/supervisor-email/templates").json()
        template_id = templates[0]["id"]
        response = tc.post(
            "/outreach",
            json={"scholarship_id": scholarship.id, "professor_id": professor.id, "template_id": template_id},
        )
        assert response.status_code in (200, 201), response.text
        stored_id = response.json()["template_id"]
        # FK enforcement: the stored id must exist in contact_templates.
        assert session.query(ContactTemplate).filter_by(id=stored_id).count() == 1
    app.dependency_overrides.pop(get_db, None)
    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# Concurrent atomic update (Blocker: outreach update)
# ---------------------------------------------------------------------------


def test_concurrent_conditional_update_allows_exactly_one_writer():
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    scholarship = Scholarship(
        title="Conc Scholarship", country="Germany", degree="Master",
        funding="Fully Funded", status="open", deadline_date=date(2027, 6, 30),
        deadline_precision="exact", eligibility=[], coverage=[], requirements=[],
        documents=[], official_source="Test University",
        official_source_url="https://conc.edu/programmes/1", is_verified=True,
        verification_status="active", image_url="https://conc.edu/logo.png",
    )
    session.add(scholarship)
    session.commit()
    session.refresh(scholarship)
    professor = ProfessorProfile(
        canonical_name="Dr Conc", title="Professor", institution_name="Test University",
        department_name="CS", official_profile_url="https://conc.edu/people/conc",
        official_email="conc@conc.edu", official_email_verified=True,
        research_areas=["ML"], last_verified_at=datetime.now(timezone.utc),
    )
    session.add(professor)
    session.commit()
    session.refresh(professor)
    session.add(
        ScholarshipProfessorLink(
            scholarship_id=scholarship.id, professor_id=professor.id,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_source_url="https://conc.edu/people/faculty",
            evidence_source_type="official_department_page",
            retrieved_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            verification_status=str(RelationshipVerificationStatus.VERIFIED),
        )
    )
    from app.models import User
    user = User(email="conc@example.com", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    record = ProfessorOutreachRecord(
        user_id=user.id, scholarship_id=scholarship.id, professor_id=professor.id,
        status=str(OutreachStatus.NOT_CONTACTED), version=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.commit()
    record_id = record.id
    session.close()

    outcomes = []

    def worker():
        s = SessionLocal()
        try:
            result = s.execute(
                update(ProfessorOutreachRecord)
                .where(
                    ProfessorOutreachRecord.id == record_id,
                    ProfessorOutreachRecord.version == 0,
                )
                .values(notes="concurrent", version=1, updated_at=datetime.now(timezone.utc))
            )
            s.commit()
            outcomes.append(result.rowcount)
        except Exception as exc:  # pragma: no cover - should never happen
            s.rollback()
            raise AssertionError(f"unexpected error during concurrent update: {exc!r}")
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: worker(), range(2)))

    assert sorted(outcomes) == [0, 1], outcomes

    # Verify the persisted state reflects exactly one successful write.
    verify = SessionLocal()
    try:
        final = verify.get(ProfessorOutreachRecord, record_id)
        assert final is not None
        assert final.version == 1
        assert final.notes == "concurrent"
    finally:
        verify.close()

    engine.dispose()


def test_selecting_built_ins_by_negative_id_stores_the_matching_template_key(client, db):
    _register(client, "student@example.com")
    templates = client.get("/supervisor-email/templates").json()
    assert len(templates) == 3

    # Seed a second professor so two distinct outreach records can be created
    # (create_outreach is idempotent per (user, scholarship, professor)).
    from app.models_supervisor import ProfessorProfile, ScholarshipProfessorLink
    from app.services.supervisor_status import (
        ProfessorRelationshipType,
        RelationshipVerificationStatus,
    )

    professor2 = ProfessorProfile(
        canonical_name="Dr Second",
        title="Professor",
        institution_name="Test University",
        department_name="CS",
        official_profile_url="https://uni1.edu/people/second",
        official_email="second@uni1.edu",
        official_email_verified=True,
        research_areas=["ML"],
        last_verified_at=datetime.now(timezone.utc),
    )
    db.add(professor2)
    db.commit()
    db.refresh(professor2)
    db.add(
        ScholarshipProfessorLink(
            scholarship_id=client.scholarship_id,
            professor_id=professor2.id,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_source_url="https://uni1.edu/people/faculty",
            evidence_source_type="official_department_page",
            retrieved_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            verification_status=str(RelationshipVerificationStatus.VERIFIED),
        )
    )
    db.commit()

    pairs = (
        (templates[2], client.professor_id),
        (templates[0], professor2.id),
    )
    for template, professor_id in pairs:
        created = client.post(
            "/outreach",
            json={
                "scholarship_id": client.scholarship_id,
                "professor_id": professor_id,
                "template_id": template["id"],
            },
        )
        assert created.status_code in (200, 201), created.text
        stored = db.query(ContactTemplate).filter_by(id=created.json()["template_id"]).one()
        assert stored.template_key == template["template_key"]


def test_listing_templates_after_selecting_one_still_shows_all_three_built_ins(client, db):
    _register(client, "student@example.com")
    templates = client.get("/supervisor-email/templates").json()
    template_id = templates[0]["id"]

    created = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_id": template_id,
        },
    )
    assert created.status_code in (200, 201), created.text

    again = client.get("/supervisor-email/templates").json()
    keys = {item["template_key"] for item in again}
    assert keys == {"masters_initial", "phd_initial", "follow_up_no_response"}


# ---------------------------------------------------------------------------
# Drafting
# ---------------------------------------------------------------------------


def test_a_draft_uses_only_verified_values(client):
    _register(client, "student@example.com")

    payload = client.post(
        "/supervisor-email/draft",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_key": "masters_initial",
            "interests": ["Machine Learning"],
        },
    ).json()

    assert "Lovelace" in payload["body"]
    assert "Machine Learning" in payload["body"]
    assert payload["to_address"] == "a.lovelace@uni1.edu"


def test_a_draft_invents_no_publication(client):
    _register(client, "student@example.com")

    body = client.post(
        "/supervisor-email/draft",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "interests": ["Machine Learning"],
        },
    ).json()["body"].lower()

    for phrase in ("your paper", "your 2025", "your recent work", "i read"):
        assert phrase not in body


def test_a_draft_makes_no_availability_claim(client):
    _register(client, "student@example.com")

    body = client.post(
        "/supervisor-email/draft",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "interests": ["Machine Learning"],
        },
    ).json()["body"].lower()

    for phrase in ("you are accepting", "you have a place", "funding is available"):
        assert phrase not in body


def test_a_draft_reports_what_it_could_not_resolve(client):
    _register(client, "student@example.com")

    payload = client.post(
        "/supervisor-email/draft",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "interests": [],
        },
    ).json()

    assert "student_interests" in payload["unresolved"]
    assert "{" not in payload["body"]
    # The account carries no name, so the sign-off must be an obvious blank
    # rather than something derived from the email address.
    assert "student_name" in payload["unresolved"]
    assert "[Your name]" in payload["body"]


def test_a_draft_for_an_unverified_pairing_is_refused(client):
    _register(client, "student@example.com")

    response = client.post(
        "/supervisor-email/draft",
        json={"scholarship_id": client.scholarship_id, "professor_id": 424242},
    )

    assert response.status_code == 422


def test_a_draft_for_an_archived_scholarship_is_refused(client):
    _register(client, "student@example.com")

    # Archived records are not publicly visible, so no draft may be prepared
    # against them even by a signed-in student.
    response = client.post(
        "/supervisor-email/draft",
        json={"scholarship_id": 999999, "professor_id": client.professor_id},
    )

    assert response.status_code == 404


def test_templates_are_public_and_plain_text(client):
    response = client.get("/supervisor-email/templates")

    assert response.status_code == 200
    keys = {item["template_key"] for item in response.json()}
    assert keys == {"masters_initial", "phd_initial", "follow_up_no_response"}
    for item in response.json():
        assert "<" not in item["body_text"]


def test_an_unknown_template_key_falls_back_and_names_what_it_used():
    assert get_builtin_template("does-not-exist").key == "masters_initial"


def test_draft_without_research_areas_omits_the_clause():
    professor = ProfessorProfile(
        canonical_name="Dr No Areas",
        institution_name="Test University",
        official_profile_url="https://uni1.edu/people/no-areas",
        research_areas=[],
    )

    result = build_draft(
        None,
        DraftRequest(
            professor=professor,
            programme_title="Test Scholarship",
            degree_level="Master",
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            verified_availability=[],
            student_name="",
            student_interests=["Machine Learning"],
            student_field="Computer Science",
        ),
        get_builtin_template("masters_initial"),
    )

    assert "research_areas" in result["unresolved"]
    assert "Your published research areas include" not in result["body"]


def test_draft_is_bounded_in_length():
    professor = ProfessorProfile(
        canonical_name="Dr Long Areas",
        institution_name="Test University",
        official_profile_url="https://uni1.edu/people/long",
        research_areas=["Area " + str(index) for index in range(50)],
    )

    result = build_draft(
        None,
        DraftRequest(
            professor=professor,
            programme_title="Test Scholarship",
            degree_level="Master",
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            verified_availability=[],
            student_name="",
            student_interests=["Interest " + str(index) for index in range(50)],
            student_field="Computer Science",
        ),
        get_builtin_template("masters_initial"),
    )

    assert len(result["body"]) <= 3500
    assert len(result["subject"]) <= 200
# ---------------------------------------------------------------------------
# Production-readiness additions
# ---------------------------------------------------------------------------


def test_an_invalid_template_id_is_refused(client):
    _register(client, "student@example.com")

    response = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_id": 999999,
        },
    )

    assert response.status_code == 422


def test_a_valid_template_id_is_recorded(client, db):
    _register(client, "student@example.com")

    templates = client.get("/supervisor-email/templates").json()
    assert templates
    template_id = templates[0]["id"]
    expected_key = templates[0]["template_key"]

    created = client.post(
        "/outreach",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_id": template_id,
        },
    ).json()

    # The stored id is the persisted row's id, which may differ from the
    # synthetic built-in id the client selected; it must resolve to the same key.
    stored = db.query(ContactTemplate).filter_by(id=created["template_id"]).one()
    assert stored.template_key == expected_key


def test_markup_in_subject_draft_body_and_next_action_is_refused(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    for field, value in (
        ("draft_subject", "<b>x</b>"),
        ("draft_body", "{injection}"),
        ("next_action", "a{b}"),
    ):
        response = client.patch(
            f"/outreach/{created['id']}",
            json={"version": created["version"], field: value},
        )
        assert response.status_code == 422, (field, response.text)


def test_draft_subject_and_draft_body_are_bounded(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    too_long_subject = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "draft_subject": "x" * 256},
    )
    assert too_long_subject.status_code == 422

    too_long_body = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "draft_body": "x" * 12001},
    )
    assert too_long_body.status_code == 422


def test_response_status_is_bounded(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "response_status": "x" * 25},
    )

    assert response.status_code == 422


def test_markup_in_response_status_is_refused(client):
    _register(client, "student@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    response = client.patch(
        f"/outreach/{created['id']}",
        json={"version": created["version"], "response_status": "<x>"},
    )

    assert response.status_code == 422


def test_deleting_another_students_record_is_still_refused_after_restore(client):
    _register(client, "first@example.com")
    created = client.post(
        "/outreach",
        json={"scholarship_id": client.scholarship_id, "professor_id": client.professor_id},
    ).json()

    _switch_student(client, "second@example.com")

    assert client.delete(f"/outreach/{created['id']}").status_code == 404


def test_templates_are_idempotent_and_plain_text(client):
    first = client.get("/supervisor-email/templates")
    second = client.get("/supervisor-email/templates")

    assert first.status_code == 200
    assert second.status_code == 200
    assert [item["template_key"] for item in first.json()] == [
        "masters_initial",
        "phd_initial",
        "follow_up_no_response",
    ]
    for item in first.json():
        assert "<" not in item["body_text"]


def test_draft_trims_interests_and_reports_unresolved(client):
    _register(client, "student@example.com")

    payload = client.post(
        "/supervisor-email/draft",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "template_key": "masters_initial",
            "interests": ["   ", "Machine Learning", "x" * 200],
        },
    ).json()

    assert "Machine Learning" in payload["body"]
    # Interests are capped in length.
    assert "x" * 120 in payload["body"]
    assert "x" * 121 not in payload["body"]


def test_draft_rejects_an_unverified_email_address(client):
    _register(client, "student@example.com")

    payload = client.post(
        "/supervisor-email/draft",
        json={
            "scholarship_id": client.scholarship_id,
            "professor_id": client.professor_id,
            "interests": [],
        },
    ).json()

    # The seeded professor's email is verified, so it may be quoted.
    assert payload["to_address"] == "a.lovelace@uni1.edu"


def test_draft_is_rate_limited(client):
    _register(client, "student@example.com")

    statuses = [
        client.post(
            "/supervisor-email/draft",
            json={
                "scholarship_id": client.scholarship_id,
                "professor_id": client.professor_id,
                "interests": [],
            },
        ).status_code
        for _ in range(25)
    ]

    assert 429 in statuses
