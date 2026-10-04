"""Concurrency tests for the logical maintenance slot.

These tests really execute: eight OS threads, each with its own database
connection and its own session, released simultaneously by a
:class:`threading.Barrier` so they contend on the same statement. Nothing here is
simulated with a mock or a sleep, and a pass means one row was created by exactly
one caller and one caller won each claim.

Database backend, stated plainly
--------------------------------
The engine these tests run against is **SQLite**, configured for WAL and a busy
timeout. That is enough to prove the *logic* - uniqueness collapses the insert
race, and the guarded conditional ``UPDATE`` elects a single winner - because both
guarantees come from the database rather than from application timing.

It is **not** enough to claim PostgreSQL equivalence. SQLite serialises all
writers with a single database-wide lock and re-evaluates a statement's ``WHERE``
clause inside that lock, which is a real defence but a different one from
PostgreSQL's MVCC snapshot isolation. Under PostgreSQL two writers really do read
the same row version concurrently, so the ``WHERE`` clause on the ``UPDATE`` is
what rejects the loser rather than a lock it waited on. The guarded-update shape
is the reason to expect that to hold, but "expect" is not "proven".

So: ``CONCURRENCY = SQLite-proven``, ``POSTGRESQL-EQUIVALENCE = UNKNOWN``.
Proving it on PostgreSQL needs a disposable PostgreSQL instance; Neon production
is not a test target and was not touched.
"""

from __future__ import annotations

import os
import threading
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.database import _upgrade_maintenance_slot_schema
from app.maintenance_slots import SlotState, due_at_for, slot_id as canonical_slot_id
from app.models import Base
from app.services.maintenance_slot_store import (
    claim_slot,
    ensure_slot,
    expire_stale_claims,
    read_slot,
    recover_slot,
    to_utc,
)

#: Honest record of what was actually executed. See the module docstring.
BACKEND = "sqlite"
CONCURRENCY_CONCLUSION = "SQLite-proven"
POSTGRESQL_EQUIVALENCE = "UNKNOWN"

#: The ambient repository database. Must be untouched by this module.
PRODUCTION_SQLITE = Path(__file__).resolve().parents[1] / "scholarzone.db"

CONTENDERS = 8
LEASE = timedelta(minutes=90)
BASE_DUE = due_at_for(datetime(2026, 10, 4, tzinfo=timezone.utc), 12)


def _fingerprint(path: Path) -> tuple[bool, int | None, int | None]:
    if not path.exists():
        return (False, None, None)
    stat = path.stat()
    return (True, stat.st_size, stat.st_mtime_ns)


@pytest.fixture(autouse=True)
def _ambient_database_is_never_touched():
    before = _fingerprint(PRODUCTION_SQLITE)
    yield
    after = _fingerprint(PRODUCTION_SQLITE)
    assert after == before, (
        f"{PRODUCTION_SQLITE} changed during a maintenance-slot concurrency test"
    )


class Racing:
    """A database eight threads can genuinely write through at once.

    Deliberately a plain object rather than a pytest fixture: the contender
    threads call :meth:`session` directly, and pytest refuses to let a fixture be
    called as a function.
    """

    def __init__(self, sessions):
        self._sessions = sessions

    def session(self):
        """A fresh session on a fresh pooled connection."""
        return self._sessions()

    def run(self, work: Callable):
        """``work(session)`` on a session this helper closes itself."""
        with self._sessions() as session:
            return work(session)

    def count_slots(self) -> int:
        with self._sessions() as session:
            return session.execute(text("SELECT COUNT(*) FROM maintenance_slots")).scalar_one()

    def active_owners(self, slot: str) -> list[str]:
        """Every non-null owner recorded against one slot.

        More demanding than reading the single row: if a lost update had written a
        second owner anywhere, this is what would expose it.
        """
        with self._sessions() as session:
            rows = session.execute(
                text(
                    "SELECT owner FROM maintenance_slots "
                    "WHERE slot_id = :slot AND owner IS NOT NULL"
                ),
                {"slot": slot},
            ).scalars().all()
        return list(rows)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'race.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _configure(dbapi_connection, _record):  # pragma: no cover - driver callback
        cursor = dbapi_connection.cursor()
        # WAL lets all eight readers proceed while one writer holds the write
        # lock; the busy timeout makes the other seven writers wait their turn
        # instead of failing. Without both, this test would measure SQLite lock
        # errors rather than the claim logic.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=FULL")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    _upgrade_maintenance_slot_schema(engine)
    sessions = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    assert engine.dialect.name == BACKEND
    yield Racing(sessions)
    engine.dispose()


def race(db: Racing, work: Callable, *per_thread: object) -> list:
    """Run ``work`` in ``CONTENDERS`` threads released simultaneously.

    Each thread opens its own session and closes it, so there are ``CONTENDERS``
    real connections. The barrier is what makes this a race rather than eight
    sequential calls: without it the first thread could finish before the last one
    is even scheduled.

    ``per_thread`` holds one argument per contender - the distinct owner names in
    the claim race, the contender index where every caller is identical - so
    thread *i* receives ``work(session, per_thread[i])``. Always exactly
    ``CONTENDERS`` arguments, so no caller can accidentally be handed another's
    work.
    """
    assert len(per_thread) == CONTENDERS, "give every contender its own argument"
    barrier = threading.Barrier(CONTENDERS, timeout=60)
    results: list = [None] * CONTENDERS
    errors: list[str] = []

    def worker(index: int) -> None:
        session = db.session()
        try:
            barrier.wait()
            results[index] = work(session, per_thread[index])
        except BaseException:  # noqa: BLE001 - surfaced as a test failure
            # The full traceback, not just the exception: a failure inside a
            # thread is otherwise undiagnosable, because pytest never sees it.
            errors.append(f"contender {index}:\n{traceback.format_exc()}")
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(CONTENDERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert not any(thread.is_alive() for thread in threads), "a contender deadlocked"
    assert not errors, "a contender raised:\n" + "\n".join(errors)
    return results


def seed_slot(db: Racing, due: datetime) -> str:
    return db.run(lambda session: ensure_slot(session, due, as_of=due))


def expire(db: Racing, slot: str, due: datetime):
    """Walk a slot to EXPIRED, the state recovery starts from."""
    db.run(lambda session: claim_slot(session, slot, "worker-original", LEASE, due))
    after_lapse = due + LEASE + timedelta(seconds=1)
    assert db.run(lambda session: expire_stale_claims(session, after_lapse)) == 1
    assert (
        db.run(lambda session: read_slot(session, slot)).state == SlotState.EXPIRED.value
    )
    return after_lapse


class TestBackendIsHonest:
    def test_the_executed_backend_is_sqlite(self, db):
        assert db.run(lambda session: session.get_bind().dialect.name) == BACKEND

    def test_no_production_database_url_is_in_play(self):
        """Neon production is never a test target."""
        url = os.getenv("SCHOLARZONE_DATABASE_URL", "")
        assert not url.startswith("postgres"), (
            "these concurrency tests are SQLite-only; pointing them at PostgreSQL "
            "would silently change what the results prove"
        )

    def test_the_module_records_what_it_did_not_prove(self):
        assert CONCURRENCY_CONCLUSION == "SQLite-proven"
        assert POSTGRESQL_EQUIVALENCE == "UNKNOWN"


class TestEnsureSlotRace:
    """Test A: eight concurrent ensure_slot calls for the same due instant."""

    def test_exactly_one_row_exists_after_eight_callers(self, db):
        due = BASE_DUE
        slot = seed_slot(db, due)
        assert db.count_slots() == 1

        results = race(
            db, lambda session, _index: ensure_slot(session, due, as_of=due), *range(CONTENDERS)
        )

        assert db.count_slots() == 1
        assert results == [slot] * CONTENDERS
        row = db.run(lambda session: read_slot(session, slot))
        assert row.state == SlotState.DUE.value
        assert row.attempt == 0
        assert row.owner is None

    def test_the_row_is_created_by_the_race_itself(self, db):
        """No pre-seeded row: the eight callers together produce exactly one."""
        assert db.count_slots() == 0
        slot = canonical_slot_id(BASE_DUE)

        results = race(
            db,
            lambda session, _index: ensure_slot(session, BASE_DUE, as_of=BASE_DUE),
            *range(CONTENDERS),
        )

        assert set(results) == {slot}
        assert db.count_slots() == 1

    @pytest.mark.parametrize("round_index", [1, 2, 3])
    def test_repeated_races_keep_producing_one_row(self, db, round_index):
        """A single pass could be luck; the guarantee has to repeat."""
        due = BASE_DUE + timedelta(days=round_index)
        slot = seed_slot(db, due)
        ensure = lambda session, _index: ensure_slot(session, due, as_of=due)
        race(db, ensure, *range(CONTENDERS))
        race(db, ensure, *range(CONTENDERS))
        assert db.count_slots() == 1
        assert db.run(lambda session: read_slot(session, slot)) is not None


class TestClaimRace:
    """Test B: eight concurrent claim_slot calls with eight distinct owners."""

    def test_exactly_one_winner_and_seven_losers(self, db):
        due = BASE_DUE
        slot = seed_slot(db, due)
        owners = [f"worker-{index}" for index in range(CONTENDERS)]
        assert len(set(owners)) == CONTENDERS

        outcomes = race(db, lambda session, owner: claim_slot(session, slot, owner, LEASE, due), *owners)

        winners = [o for o in outcomes if o.claimed]
        losers = [o for o in outcomes if not o.claimed]
        assert len(winners) == 1, outcomes
        assert len(losers) == CONTENDERS - 1
        assert winners[0].owner in owners

    def test_exactly_one_active_owner_is_recorded(self, db):
        due = BASE_DUE
        slot = seed_slot(db, due)
        owners = [f"worker-{index}" for index in range(CONTENDERS)]

        outcomes = race(db, lambda session, owner: claim_slot(session, slot, owner, LEASE, due), *owners)
        winner = next(o for o in outcomes if o.claimed)

        assert db.active_owners(slot) == [winner.owner]
        row = db.run(lambda session: read_slot(session, slot))
        assert row.state == SlotState.CLAIMED.value
        assert row.owner == winner.owner
        assert to_utc(row.lease_until) == winner.lease_until
        assert row.attempt == 1

    def test_a_loser_neither_shortens_nor_overwrites_the_lease(self, db):
        due = BASE_DUE
        slot = seed_slot(db, due)
        owners = [f"worker-{index}" for index in range(CONTENDERS)]

        outcomes = race(db, lambda session, owner: claim_slot(session, slot, owner, LEASE, due), *owners)
        winner = next(o for o in outcomes if o.claimed)

        row = db.run(lambda session: read_slot(session, slot))
        assert to_utc(row.lease_until) == due + LEASE == winner.lease_until

    def test_repeated_races_keep_producing_one_winner(self, db):
        """Eight slots, eight races: the guarantee is not a one-off."""
        for round_number in range(8):
            due = BASE_DUE + timedelta(days=round_number)
            slot = seed_slot(db, due)
            owners = [f"r{round_number}-worker-{index}" for index in range(CONTENDERS)]

            outcomes = race(
                db, lambda session, owner: claim_slot(session, slot, owner, LEASE, due), *owners
            )

            winners = [o for o in outcomes if o.claimed]
            assert len(winners) == 1, (round_number, outcomes)
            assert db.active_owners(slot) == [winners[0].owner]


class TestRecoveryRace:
    """Test C: eight concurrent recovery attempts on one EXPIRED slot."""

    def test_exactly_one_recovery_wins(self, db):
        slot = seed_slot(db, BASE_DUE)
        after_lapse = expire(db, slot, BASE_DUE)
        owners = [f"recoverer-{index}" for index in range(CONTENDERS)]

        outcomes = race(
            db,
            lambda session, owner: recover_slot(session, slot, owner, LEASE, after_lapse),
            *owners,
        )

        winners = [o for o in outcomes if o.claimed]
        assert len(winners) == 1, outcomes
        assert len(outcomes) - len(winners) == CONTENDERS - 1

    def test_exactly_one_active_owner_after_recovery(self, db):
        slot = seed_slot(db, BASE_DUE)
        after_lapse = expire(db, slot, BASE_DUE)
        owners = [f"recoverer-{index}" for index in range(CONTENDERS)]

        outcomes = race(
            db,
            lambda session, owner: recover_slot(session, slot, owner, LEASE, after_lapse),
            *owners,
        )
        winner = next(o for o in outcomes if o.claimed)

        assert db.active_owners(slot) == [winner.owner]
        row = db.run(lambda session: read_slot(session, slot))
        assert row.state == SlotState.CLAIMED.value
        assert row.owner == winner.owner
        assert row.attempt == 2

    def test_a_recovery_race_does_not_reopen_the_slot(self, db):
        """Seven losses must not have left anything claimable behind."""
        slot = seed_slot(db, BASE_DUE)
        after_lapse = expire(db, slot, BASE_DUE)
        owners = [f"recoverer-{index}" for index in range(CONTENDERS)]

        race(
            db,
            lambda session, owner: recover_slot(session, slot, owner, LEASE, after_lapse),
            *owners,
        )

        assert db.count_slots() == 1
        row = db.run(lambda session: read_slot(session, slot))
        assert row.state == SlotState.CLAIMED.value
        assert row.owner in owners


class TestClaimRacingTheExpirySweep:
    """A sweep running alongside the claimants must not create a second owner."""

    def test_sweep_does_not_overtake_an_active_claim(self, db):
        due = BASE_DUE
        slot = seed_slot(db, due)
        owners = [f"worker-{index}" for index in range(CONTENDERS)]

        def claim_then_sweep(session, index):
            outcome = claim_slot(session, slot, owners[index], LEASE, due)
            expire_stale_claims(session, due + timedelta(seconds=1))
            return outcome

        outcomes = race(db, claim_then_sweep, *range(CONTENDERS))

        winners = [o for o in outcomes if o.claimed]
        assert len(winners) == 1, outcomes
        assert db.active_owners(slot) == [winners[0].owner]
        row = db.run(lambda session: read_slot(session, slot))
        assert row.state == SlotState.CLAIMED.value
        assert row.attempt == 1