"""The UTC coercion in ``application_workspace``, pinned at the unit level.

``test_application_workspace`` already covers what a client actually receives:
the timestamp arrives as ``...Z``, survives a SQLite round trip unchanged, keeps
its instant on a retry, and is cleared by un-completing. Those are the
guarantees that matter and they are asserted through the real HTTP path.

What is not covered anywhere is the coercion helper itself. It is a five-line
function with one judgement call in it and two ways to get that call wrong, and
no existing test would notice either mistake:

- a naive value has to be *labelled* UTC rather than read as local time, which
  is only safe because nothing in the module writes local time; and
- an aware value in some other zone has to be *converted*, not relabelled.

Getting the second one wrong is the dangerous one. Relabelling a ``+02:00``
value as UTC publishes the same wall clock with a ``Z`` suffix, which silently
moves the instant two hours into the past while claiming not to. The behaviour
would look correct on a machine that only ever produces UTC, which is why it
needs a test rather than a code review.

These tests exercise ``_as_utc`` directly rather than through a response model.
The normalisation happens where the response is built, in
``application_workspace``, and that is the only place in the codebase that
constructs ``ApplicationSummary``, ``ApplicationDetail`` or
``ChecklistItemResponse`` - so pinning it here is pinning the real contract
rather than a schema's input handling.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

import pytest  # noqa: E402
from sqlalchemy import (  # noqa: E402
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    create_engine,
    select,
)
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.services.application_workspace import _as_utc  # noqa: E402

# Deliberately not round, so a truncation to whole seconds or to milliseconds
# would be visible rather than hidden by a lucky value.
INSTANT = datetime(2026, 3, 14, 15, 9, 26, 535897, tzinfo=timezone.utc)


def test_an_aware_utc_instant_passes_through_identically():
    """The already-correct case must not be disturbed.

    Everything here is written as aware UTC, so this is the shape the
    application itself produces. A normaliser that "helpfully" re-derives the
    value would be doing unnecessary work on the common path.
    """
    normalized = _as_utc(INSTANT)

    assert normalized == INSTANT
    assert normalized is not None
    assert normalized.tzinfo is timezone.utc


def test_a_naive_value_is_labelled_utc_and_its_wall_clock_is_left_alone():
    """A naive value is assumed UTC, not reinterpreted as local time.

    This is the judgement call in the fix, so it is stated rather than implied.
    SQLite has no timezone type, so an aware value written to disk comes back
    naive. Assuming UTC is only correct because nothing in this module writes
    local time; if that ever changes, the assumption has to change with it and
    this test is where that would show up.

    The wall clock must come out the other side unchanged - 15:09 stays 15:09.
    Reading it as local and converting would move it by this machine's offset,
    so the assertion on the hour is the point, not a detail.
    """
    naive = datetime(2026, 3, 14, 15, 9, 26, 535897)
    assert naive.tzinfo is None, "precondition: this is the naive form"

    normalized = _as_utc(naive)

    assert normalized == naive.replace(tzinfo=timezone.utc)
    assert normalized.hour == 15, "the wall clock must not be reinterpreted"
    assert normalized.utcoffset() == timedelta(0)


def test_an_aware_non_utc_offset_is_converted_rather_than_relabelled():
    """The half that would otherwise fail silently.

    A ``+02:00`` value describing 15:09 local describes 13:09 UTC. Converting
    moves the wall clock and keeps the instant; relabelling keeps the wall clock
    and moves the instant. Only the first is honest, and the difference is two
    hours of quiet data corruption on a machine that only ever sees UTC.
    """
    two_hours_ahead = timezone(timedelta(hours=2))
    local_equivalent = INSTANT.astimezone(two_hours_ahead)

    # Precondition: the two spellings really do describe different wall clocks.
    assert local_equivalent.hour == 17
    assert local_equivalent == INSTANT

    normalized = _as_utc(local_equivalent)

    assert normalized == INSTANT, "the instant must be the same moment"
    assert normalized.hour == 15, "and expressed in UTC, not left at 17:00"
    assert normalized.utcoffset() == timedelta(0)


def test_none_stays_none():
    """An unset timestamp stays unset.

    Worth pinning because the obvious way to write this coerces through a
    function that would raise or invent a value for ``None``.
    """
    assert _as_utc(None) is None


@pytest.mark.parametrize(
    "micros", [1, 999, 100000, 535897, 999999]
)
def test_microsecond_precision_is_never_truncated(micros):
    """Precision survives normalisation in both directions.

    Covers the aware case and the naive case, because they take different
    branches. A normaliser that truncated to seconds - or a serializer that
    formatted to milliseconds - would be indistinguishable from this on a
    round value and would silently lose ordering on a real one.
    """
    aware = datetime(2026, 3, 14, 15, 9, 26, micros, tzinfo=timezone.utc)

    assert _as_utc(aware).microsecond == micros

    naive = aware.replace(tzinfo=None)
    normalized_naive = _as_utc(naive)
    assert normalized_naive is not None
    assert normalized_naive.microsecond == micros


def test_sqlite_really_does_hand_back_a_naive_value(tmp_path):
    """The premise the whole normalisation rests on, checked against a real driver.

    Written by the ORM and read back through the driver rather than
    hand-constructing the naive form, so this fails if SQLite's behaviour ever
    changes - at which point every assumption above needs revisiting, and this
    is the test that would say so.

    Declares a throwaway table rather than adding a model to ``app.models``:
    the subject is the driver's ``DateTime`` handling, and the production schema
    has no reason to change for a test.
    """
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

    with Session() as session:
        session.execute(probe.insert().values(id=1, moment=INSTANT))
        session.commit()

    with Session() as session:
        stored = session.execute(select(probe.c.moment)).scalar_one()

    assert stored.tzinfo is None, "precondition: SQLite dropped tzinfo"
    assert _as_utc(stored) == INSTANT, "normalising must recover the original instant"
