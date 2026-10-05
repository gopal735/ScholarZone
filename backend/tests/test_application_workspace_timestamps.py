"""One instant, one representation - the timestamp contract at the API boundary.

Every timestamp in the application workspace is written as
``datetime.now(timezone.utc)``. Reading it back does not always return that, and
the difference was visible to clients.

SQLite's ``DateTime`` has no timezone type. A value that has made a round trip
through the database comes back **naive**; the same value still held in memory
arrives **aware**. Both describe the same instant, so the API published one field
in two different formats depending on whether the row happened to have been
refreshed - ``...618155Z`` on one response, ``...618155`` on the next, for a value
that never moved. PostgreSQL returns aware values already, which is why this only
surfaced under the test database and stayed invisible in production.

The cost was not cosmetic. ``test_completing_twice_is_idempotent_and_does_not_lose_the_timestamp``
asserts that a retried completion does not change the timestamp, and it was
failing for a reason that had nothing to do with idempotency: the two responses
disagreed about the format of one unchanged value. A real client comparing them
would have concluded the task had been re-completed.

What these tests hold:

    The same instant reaches the wire the same way whether it came from memory or
    from a database round trip, the instant itself is never moved, and nothing
    else about the response changes.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.schemas_application import (  # noqa: E402
    ApplicationDetail,
    ApplicationSummary,
    ChecklistItemResponse,
    ScholarshipAvailability,
)
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

# A value that is deliberately not round, so a truncation to seconds or to
# milliseconds would be visible rather than hidden by a lucky microsecond.
INSTANT = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=timezone.utc)


# The workspace suite keeps its ``db``/``client`` fixtures local rather than in
# conftest, so they are repeated here rather than refactored: a shared fixture
# would touch a file the other suite depends on, and this change is meant to stay
# in one place. The bodies are identical.
@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'timestamps.db'}")
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


def _normaliser():
    from app.schemas_application import _as_utc

    return _as_utc


def _wire(value):
    """The string a client actually receives for ``value``."""
    return ChecklistItemResponse(
        key="review_eligibility",
        label="Review eligibility",
        source="generic",
        position=0,
        weight=1,
        completed=True,
        completed_at=value,
    ).model_dump(mode="json")["completed_at"]


# ---------------------------------------------------------------------------
# 1. a fresh in-memory UTC timestamp
# ---------------------------------------------------------------------------


def test_a_fresh_utc_timestamp_reaches_the_wire_as_utc():
    serialized = _wire(INSTANT)
    assert serialized == "2026-03-14T15:09:26.535897Z"
    assert serialized.endswith("Z"), "a UTC instant must be marked as UTC"


# ---------------------------------------------------------------------------
# 2. the SQLite round trip
# ---------------------------------------------------------------------------


def test_a_naive_datetime_from_a_database_round_trip_serialises_identically():
    """The exact value SQLite hands back for a stored aware datetime.

    Reproduced rather than assumed: SQLAlchemy's SQLite ``DateTime`` drops
    ``tzinfo`` on read, so this is what the ORM really returns.
    """
    naive_from_sqlite = datetime(2026, 3, 14, 15, 9, 26, 535897)  # tzinfo is None

    assert naive_from_sqlite.tzinfo is None, "precondition: this is the naive form"
    assert _wire(naive_from_sqlite) == _wire(INSTANT)
    assert _wire(naive_from_sqlite) == "2026-03-14T15:09:26.535897Z"


def test_the_round_trip_is_reproduced_through_a_real_database(tmp_path):
    """Not a synthetic value: written by the ORM, read back through the driver.

    The behavioural claim is that a value the application stores comes back
    serialised the same way, so the test stores one and reads it back rather than
    hand-writing the naive form.

    A throwaway table declared here rather than a new model in ``app.models``:
    the point is the driver's ``DateTime`` behaviour, and adding a model would
    change the production schema, which this fix must not do.
    """
    from sqlalchemy import Column, DateTime, Integer, MetaData, Table, create_engine, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    metadata = MetaData()
    probe = Table(
        "utc_probe",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("moment", DateTime(timezone=True), nullable=True),
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'probe.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.execute(probe.insert().values(id=1, moment=INSTANT))
        db.commit()

    with Session() as db:
        row = db.execute(select(probe.c.moment)).scalar_one()
        assert row.tzinfo is None, "precondition: SQLite dropped tzinfo"
        assert _wire(row) == _wire(INSTANT)


# ---------------------------------------------------------------------------
# 3. idempotency
# ---------------------------------------------------------------------------


def test_repeated_completion_is_idempotent_and_the_timestamp_is_stable(client, db):
    """The property the failing test was actually written to check.

    Asserted as instants, not as strings, so the check keeps its meaning if the
    wire format ever changes: what must not move is the moment, not its
    punctuation.
    """
    from test_application_workspace import (
        login,
        make_scholarship,
        make_user,
        start,
    )

    make_user(db, "utc-idem@example.com")
    scholarship = make_scholarship(db)
    login(client, "utc-idem@example.com")
    application_id = start(client, scholarship.id).json()["id"]

    def completed_at():
        body = client.patch(
            f"/api/applications/{application_id}/checklist/review_eligibility",
            json={"expected_version": 1, "completed": True},
        ).json()
        return next(i for i in body["checklist"] if i["key"] == "review_eligibility")["completed_at"]

    first = completed_at()
    second = completed_at()

    assert first is not None
    # The exact form the API publishes is now stable across the two responses.
    assert first == second
    assert first.endswith("Z")
    # And the instant behind it is unmoved.
    assert _parse(first) == _parse(second) == _parse(first)


def test_uncompleting_still_clears_the_timestamp(client, db):
    from test_application_workspace import (
        login,
        make_scholarship,
        make_user,
        start,
    )

    make_user(db, "utc-clear@example.com")
    scholarship = make_scholarship(db)
    login(client, "utc-clear@example.com")
    application_id = start(client, scholarship.id).json()["id"]

    client.patch(
        f"/api/applications/{application_id}/checklist/review_eligibility",
        json={"expected_version": 1, "completed": True},
    )
    undone = client.patch(
        f"/api/applications/{application_id}/checklist/review_eligibility",
        json={"expected_version": 2, "completed": False},
    )
    item = next(i for i in undone.json()["checklist"] if i["key"] == "review_eligibility")
    assert item["completed"] is False
    assert item["completed_at"] is None


def _parse(value: str) -> datetime:
    """Parse a wire timestamp back into an aware datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# 4 and 5. the instant is preserved and never shifted
# ---------------------------------------------------------------------------


def test_the_instant_is_preserved_exactly():
    assert _normaliser()(INSTANT) == INSTANT
    assert _normaliser()(INSTANT).microsecond == INSTANT.microsecond


def test_a_non_utc_offset_is_converted_not_relabelled():
    """The important half of the contract: a +02:00 instant becomes 13:09 UTC.

    Attaching UTC to a local-labelled value would move the instant by two hours
    while claiming not to. ``astimezone`` is what makes the conversion honest.
    """
    berlin = INSTANT.astimezone(timezone(timedelta(hours=2)))

    normalized = _normaliser()(berlin)

    assert normalized == INSTANT, "the instant must be the same moment"
    assert normalized.hour == 15, "and it must be expressed in UTC"
    assert normalized.utcoffset() == timedelta(0)
    assert _wire(berlin) == "2026-03-14T15:09:26.535897Z"


def test_a_naive_value_is_labelled_utc_not_converted_from_local_time():
    """A naive value is assumed UTC, not read as this machine's local time.

    Stated explicitly because it is the one judgement call in the fix: assuming
    UTC is only safe because nothing in the module writes local time.
    """
    naive = datetime(2026, 3, 14, 15, 9, 26, 535897)

    normalized = _normaliser()(naive)

    assert normalized == naive.replace(tzinfo=timezone.utc)
    assert normalized.hour == 15, "the wall clock must not be reinterpreted"
    assert normalized.utcoffset() == timedelta(0)


def test_none_stays_none():
    assert _normaliser()(None) is None
    assert (
        ChecklistItemResponse(
            key="k", label="l", source="generic", position=0, weight=1,
            completed=False, completed_at=None,
        ).model_dump(mode="json")["completed_at"]
        is None
    )


def test_microsecond_precision_is_not_truncated():
    for micros in (1, 999, 100000, 535897, 999999):
        moment = datetime(2026, 3, 14, 15, 9, 26, micros, tzinfo=timezone.utc)
        assert _normaliser()(moment).microsecond == micros
        assert _wire(moment).endswith(f".{micros:06d}Z")


# ---------------------------------------------------------------------------
# 6. unrelated fields are untouched
# ---------------------------------------------------------------------------


def test_the_non_timestamp_fields_of_the_response_are_unchanged():
    item = ChecklistItemResponse(
        key="review_eligibility",
        label="Review eligibility",
        description="Check the published requirements",
        action_target="/scholarships/12",
        source="published_requirement",
        source_detail="official_requirements",
        position=3,
        weight=2,
        completed=True,
        completed_at=INSTANT,
        is_counted=True,
    )
    payload = item.model_dump(mode="json")

    assert payload["key"] == "review_eligibility"
    assert payload["label"] == "Review eligibility"
    assert payload["description"] == "Check the published requirements"
    assert payload["action_target"] == "/scholarships/12"
    assert payload["source"] == "published_requirement"
    assert payload["source_detail"] == "official_requirements"
    assert payload["position"] == 3
    assert payload["weight"] == 2
    assert payload["completed"] is True
    assert payload["is_counted"] is True
    # The one field that is meant to have changed representation.
    assert payload["completed_at"] == "2026-03-14T15:09:26.535897Z"


def test_the_other_two_timestamps_in_the_module_are_normalised_too():
    """``updated_at`` and ``created_at`` are the same column type and the same bug.

    Fixing only ``completed_at`` would leave the detail response still publishing
    one field two ways, so the invariant has to hold for the whole module.
    """
    naive = datetime(2026, 3, 14, 15, 9, 26, 535897)

    summary = ApplicationSummary(
        id=1, scholarship_id=2, name="Example", detail_url="/x",
        state="in_progress", state_label="In progress",
        outcome="pending", outcome_label="Pending",
        availability=ScholarshipAvailability(is_available=True),
        verification_status="active", verified=True, verification_display="Verified",
        updated_at=naive, version=1,
    )
    assert summary.model_dump(mode="json")["updated_at"] == "2026-03-14T15:09:26.535897Z"

    detail = ApplicationDetail(
        id=1, scholarship_id=2, name="Example", detail_url="/x",
        state="in_progress", state_label="In progress",
        outcome="pending", outcome_label="Pending",
        availability=ScholarshipAvailability(is_available=True),
        verification_status="active", verified=True, verification_display="Verified",
        updated_at=naive, version=1, created_at=naive,
    )
    payload = detail.model_dump(mode="json")
    assert payload["updated_at"] == "2026-03-14T15:09:26.535897Z"
    assert payload["created_at"] == "2026-03-14T15:09:26.535897Z"


def test_a_whole_detail_response_serialises_consistently(client, db):
    """End to end, through the real endpoint, on a row that has been re-read."""
    from test_application_workspace import (
        login,
        make_scholarship,
        make_user,
        start,
    )

    make_user(db, "utc-detail@example.com")
    scholarship = make_scholarship(db)
    login(client, "utc-detail@example.com")
    application_id = start(client, scholarship.id).json()["id"]

    client.patch(
        f"/api/applications/{application_id}/checklist/review_eligibility",
        json={"expected_version": 1, "completed": True},
    )
    # A fresh GET, so every value comes from the database rather than memory.
    detail = client.get(f"/api/applications/{application_id}").json()

    stamps = [detail["updated_at"], detail["created_at"]]
    stamps += [
        item["completed_at"]
        for item in detail["checklist"]
        if item["completed_at"] is not None
    ]
    assert stamps, "the response must carry at least one timestamp"
    for stamp in stamps:
        assert stamp.endswith("Z"), f"{stamp!r} reached the wire without a UTC marker"
        assert _parse(stamp).utcoffset() == timedelta(0)
