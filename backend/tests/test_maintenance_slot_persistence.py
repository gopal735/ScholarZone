"""Persistence tests for the logical maintenance slot.

Every test here runs against an isolated SQLite file created under ``tmp_path``.
Nothing in this module may read, create or depend on ``backend/scholarzone.db``:
that file is the developer's local catalogue and, in production, the live Neon
mirror, so a test that quietly opened it would be writing to real data while
appearing to pass. The autouse guard below fingerprints the ambient file and
fails if any test in this module changed it, which holds whether or not it
exists at all.

The database backend is recorded honestly rather than assumed: these tests prove
SQLite behaviour, and SQLite's write serialisation is not PostgreSQL's. See
``test_maintenance_slot_concurrency.py`` for what that does and does not license.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import _upgrade_maintenance_slot_schema, reset_database_connections
from app.maintenance_slots import (
    InvalidTransition,
    LogicalSource,
    SlotState,
    due_at_for,
    latest_due_slot,
    slot_id as canonical_slot_id,
)
from app.models import Base, MaintenanceRun
from app.services.maintenance_slot_store import (
    SlotNotFound,
    claim_slot,
    ensure_slot,
    expire_stale_claims,
    read_slot,
    recover_slot,
    to_utc,
    transition_slot,
)

#: The ambient repository database. Must be untouched by this module.
PRODUCTION_SQLITE = Path(__file__).resolve().parents[1] / "scholarzone.db"

DUE = due_at_for(datetime(2026, 10, 4, tzinfo=timezone.utc), 12)
SLOT = canonical_slot_id(DUE)
LEASE = timedelta(minutes=90)


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
        f"{PRODUCTION_SQLITE} changed during a maintenance-slot persistence test; "
        "these tests must only ever touch their own tmp_path database"
    )


def _make_engine(db_path: Path):
    """An isolated SQLite engine configured for genuine concurrent writers.

    ``journal_mode=WAL`` lets readers proceed while a writer holds the write lock,
    and ``busy_timeout`` makes a second writer wait for the lock instead of
    failing immediately. Without both, a contention test measures SQLite lock
    errors rather than the claim logic under test.
    """
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _configure(dbapi_connection, _record):  # pragma: no cover - driver callback
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


@pytest.fixture
def engine(tmp_path):
    db_path = tmp_path / "slots.db"
    engine = _make_engine(db_path)
    Base.metadata.create_all(bind=engine)
    _upgrade_maintenance_slot_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as active:
        yield active


@pytest.fixture
def initialized_database(tmp_path, monkeypatch):
    """Point the application's real ``init_database()`` at an isolated file.

    The env var and the engine caches are both process-wide, so both are restored
    afterwards. Without that, one test would silently re-point every later test's
    database.
    """
    db_path = tmp_path / "initialized.db"
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    reset_database_connections()
    try:
        yield db_path
    finally:
        reset_database_connections()


def _row_count(session, table: str) -> int:
    return session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def _row_count_sqlite(engine, table: str) -> int:
    with engine.connect() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_maintenance_slots_table_is_created(self, engine):
        assert inspect(engine).has_table("maintenance_slots")

    def test_every_required_column_exists(self, engine):
        columns = {c["name"] for c in inspect(engine).get_columns("maintenance_slots")}
        assert {
            "id",
            "slot_id",
            "due_at",
            "state",
            "logical_source",
            "transport_event",
            "owner",
            "lease_until",
            "workflow_run_id",
            "attempt",
            "failure_classification",
            "created_at",
            "updated_at",
        } <= columns

    def test_required_columns_are_not_null(self, engine):
        inspector = inspect(engine)
        required = {
            c["name"] for c in inspector.get_columns("maintenance_slots") if not c["nullable"]
        }
        assert {"slot_id", "due_at", "state", "attempt", "created_at", "updated_at"} <= required

    def test_slot_id_is_unique_in_the_schema(self, engine):
        """The guarantee that eight concurrent ensure_slot calls collapse to one row.

        SQLite reports a table-level UNIQUE as an anonymous auto-index that
        ``get_indexes`` hides, so the DDL itself is inspected rather than trusting
        the dialect's metadata to name it.
        """
        with engine.connect() as connection:
            ddl = connection.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='maintenance_slots'")
            ).scalar_one()
        assert re.search(r"UNIQUE\s*\(\s*slot_id\s*\)", ddl, re.IGNORECASE), ddl

    def test_duplicate_slot_id_is_rejected_by_the_database(self, engine):
        """Proof by behaviour, not by metadata: the constraint actually bites."""
        from sqlalchemy.exc import IntegrityError

        def _insert(slot_id_value: str, attempt: int = 0) -> None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO maintenance_slots "
                        "(slot_id, due_at, state, logical_source, attempt, created_at, updated_at) "
                        "VALUES (:slot_id, '2026-10-04 12:07:00', 'DUE', 'github_schedule', "
                        ":attempt, '2026-10-04 00:00:00', '2026-10-04 00:00:00')"
                    ),
                    {"slot_id": slot_id_value, "attempt": attempt},
                )

        _insert(SLOT)
        with pytest.raises(IntegrityError):
            _insert(SLOT)
        assert _row_count_sqlite(engine, "maintenance_slots") == 1

    def test_attempt_cannot_be_negative(self, engine):
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO maintenance_slots "
                        "(slot_id, due_at, state, logical_source, attempt, created_at, updated_at) "
                        "VALUES ('maintenance:2026-10-05T00:07:00Z', '2026-10-05 00:07:00', 'DUE', "
                        "'github_schedule', -1, '2026-10-05 00:00:00', '2026-10-05 00:00:00')"
                    )
                )
        assert _row_count_sqlite(engine, "maintenance_slots") == 0

    def test_maintenance_runs_slot_id_column_and_index_exist(self, engine):
        inspector = inspect(engine)
        assert "slot_id" in {c["name"] for c in inspector.get_columns("maintenance_runs")}
        assert "ix_maintenance_runs_slot_id" in {
            i["name"] for i in inspector.get_indexes("maintenance_runs")
        }

    def test_maintenance_run_slot_id_is_nullable(self, session):
        """An old row with no slot stays valid; run_id remains execution identity."""
        session.add(MaintenanceRun(run_id="legacy-run", worker="legacy", status="ok"))
        session.commit()
        row = session.query(MaintenanceRun).filter(MaintenanceRun.run_id == "legacy-run").one()
        assert row.slot_id is None
        assert row.run_id == "legacy-run"

    def test_initialization_is_idempotent(self, initialized_database):
        """Running the real init twice must not duplicate anything or raise."""
        from app.database import init_database

        init_database()
        init_database()
        init_database()

        from app.database import get_engine

        engine = get_engine()
        inspector = inspect(engine)
        assert inspector.has_table("maintenance_slots")
        assert "slot_id" in {c["name"] for c in inspector.get_columns("maintenance_runs")}
        assert "ix_maintenance_runs_slot_id" in {
            i["name"] for i in inspector.get_indexes("maintenance_runs")
        }
        names = [i["name"] for i in inspector.get_indexes("maintenance_slots")]
        assert len(names) == len(set(names))
        get_engine().dispose()

    def test_initialization_preserves_rows(self, initialized_database):
        from app.database import get_engine, init_database

        init_database()
        factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
        with factory() as seed:
            seed.add(MaintenanceRun(run_id="kept-across-init", worker="w", status="ok"))
            seed.commit()
        init_database()
        with factory() as verify:
            assert verify.query(MaintenanceRun).filter_by(run_id="kept-across-init").count() == 1
        get_engine().dispose()


class TestOldSchemaUpgrade:
    """A database created before logical slots existed must gain the column in place."""

    def _build_old_database(self, db_path: Path):
        engine = _make_engine(db_path)
        with engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE maintenance_runs (
                    id INTEGER PRIMARY KEY,
                    run_id VARCHAR(64) NOT NULL UNIQUE,
                    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at DATETIME,
                    worker VARCHAR(64) NOT NULL,
                    status VARCHAR(16) NOT NULL,
                    stages JSON NOT NULL,
                    counts JSON NOT NULL,
                    error_summary TEXT,
                    dry_run BOOLEAN NOT NULL DEFAULT 0,
                    duration_ms FLOAT
                )
            """))
            connection.execute(
                text(
                    "INSERT INTO maintenance_runs "
                    "(run_id, worker, status, stages, counts, dry_run) "
                    "VALUES ('pre-slot-run', 'worker/1.0', 'ok', '[]', '{}', 0)"
                )
            )
        return engine

    def test_old_database_gains_slot_id_without_data_loss(self, initialized_database):
        from app.database import get_engine, init_database

        old_engine = self._build_old_database(initialized_database)
        assert "slot_id" not in {
            c["name"] for c in inspect(old_engine).get_columns("maintenance_runs")
        }
        old_engine.dispose()

        init_database()

        engine = get_engine()
        inspector = inspect(engine)
        assert "slot_id" in {c["name"] for c in inspector.get_columns("maintenance_runs")}
        assert "ix_maintenance_runs_slot_id" in {
            i["name"] for i in inspector.get_indexes("maintenance_runs")
        }
        assert inspector.has_table("maintenance_slots")

        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as verify:
            rows = verify.query(MaintenanceRun).all()
            assert len(rows) == 1
            assert rows[0].run_id == "pre-slot-run"
            assert rows[0].worker == "worker/1.0"
            assert rows[0].status == "ok"
            # Not backfilled: inventing a slot for a run would assert an
            # attribution that was never recorded.
            assert rows[0].slot_id is None
        engine.dispose()

    def test_upgrade_does_not_recreate_the_table(self, initialized_database):
        """A recreation would drop the table; an ALTER keeps it."""
        from app.database import get_engine, init_database

        old_engine = self._build_old_database(initialized_database)
        old_rows = old_engine.connect().execute(
            text("SELECT id, run_id FROM maintenance_runs")
        ).all()
        old_engine.dispose()

        init_database()

        engine = get_engine()
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT id, run_id FROM maintenance_runs")).all()
        assert rows == old_rows
        engine.dispose()


# ---------------------------------------------------------------------------
# ensure_slot
# ---------------------------------------------------------------------------


class TestEnsureSlot:
    def test_creates_one_due_row(self, session):
        assert ensure_slot(session, DUE, as_of=DUE) == SLOT
        row = read_slot(session, SLOT)
        assert row is not None
        assert row.state == SlotState.DUE.value
        assert row.owner is None
        assert row.lease_until is None
        assert row.attempt == 0
        assert to_utc(row.due_at) == DUE
        assert _row_count(session, "maintenance_slots") == 1

    def test_slot_id_is_derived_from_the_pure_core(self, session):
        assert ensure_slot(session, DUE, as_of=DUE) == canonical_slot_id(DUE)

    def test_slot_id_is_independent_of_observation_time(self, session):
        """A trigger that arrives late still identifies the slot it belongs to."""
        late = DUE + timedelta(minutes=17)
        observed = latest_due_slot(late)
        assert observed == DUE
        ensure_slot(session, observed, as_of=late)
        assert ensure_slot(session, observed, as_of=late + timedelta(minutes=1)) == SLOT
        assert _row_count(session, "maintenance_slots") == 1
        assert to_utc(read_slot(session, SLOT).due_at) == DUE

    def test_repeated_calls_produce_one_row(self, session):
        for _ in range(5):
            ensure_slot(session, DUE, as_of=DUE)
        assert _row_count(session, "maintenance_slots") == 1

    def test_distinct_due_instants_produce_distinct_rows(self, session):
        first = ensure_slot(session, due_at_for(DUE, 0), as_of=DUE)
        second = ensure_slot(session, due_at_for(DUE, 12), as_of=DUE)
        assert first != second
        assert _row_count(session, "maintenance_slots") == 2

    def test_source_attribution_is_recorded_separately_from_transport(self, session):
        ensure_slot(
            session,
            DUE,
            logical_source=LogicalSource.EXTERNAL_SCHEDULER_DISPATCH,
            transport_event="workflow_dispatch",
            as_of=DUE,
        )
        row = read_slot(session, SLOT)
        assert row.logical_source == "external_scheduler_dispatch"
        assert row.transport_event == "workflow_dispatch"

    def test_default_logical_source_is_the_github_schedule(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        assert read_slot(session, SLOT).logical_source == "github_schedule"

    def test_non_utc_input_is_normalised(self, session):
        """A due instant in another zone must not be stored as its local wall time."""
        from zoneinfo import ZoneInfo

        dhaka = DUE.astimezone(ZoneInfo("Asia/Dhaka"))
        ensure_slot(session, dhaka, as_of=DUE)
        assert _row_count(session, "maintenance_slots") == 1
        assert to_utc(read_slot(session, canonical_slot_id(DUE)).due_at) == DUE

    def test_naive_datetime_is_rejected(self, session):
        with pytest.raises(ValueError):
            ensure_slot(session, datetime(2026, 10, 4, 12, 7), as_of=DUE)
        assert _row_count(session, "maintenance_slots") == 0

    def test_latest_due_slot_round_trips_through_storage(self, session):
        as_of = datetime(2026, 10, 4, 13, 0, tzinfo=timezone.utc)
        expected = latest_due_slot(as_of)
        assert ensure_slot(session, expected, as_of=as_of) == canonical_slot_id(expected)
        assert canonical_slot_id(expected) == "maintenance:2026-10-04T12:07:00Z"


# ---------------------------------------------------------------------------
# claim_slot and lease protection
# ---------------------------------------------------------------------------


class TestClaimSlot:
    def test_claims_a_due_slot(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        outcome = claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        assert outcome.claimed is True
        assert outcome.owner == "worker-a"
        assert outcome.lease_until == DUE + LEASE
        row = read_slot(session, SLOT)
        assert row.state == SlotState.CLAIMED.value
        assert row.owner == "worker-a"
        assert to_utc(row.lease_until) == DUE + LEASE
        assert row.attempt == 1

    def test_losing_claim_leaves_the_row_untouched(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        winner = claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        loser = claim_slot(session, SLOT, "worker-b", LEASE, DUE)
        assert winner.claimed is True
        assert loser.claimed is False
        assert loser.owner == "worker-a"
        row = read_slot(session, SLOT)
        assert row.owner == "worker-a"
        assert to_utc(row.lease_until) == winner.lease_until
        assert row.attempt == 1

    def test_active_lease_cannot_be_taken(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        later = DUE + timedelta(minutes=1)
        attempt = claim_slot(session, SLOT, "worker-b", LEASE, later)
        assert attempt.claimed is False
        row = read_slot(session, SLOT)
        assert row.owner == "worker-a"
        assert to_utc(row.lease_until) == DUE + LEASE

    def test_active_lease_cannot_be_stolen_near_its_end(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        just_before_expiry = DUE + LEASE - timedelta(seconds=1)
        assert claim_slot(session, SLOT, "thief", LEASE, just_before_expiry).claimed is False
        assert read_slot(session, SLOT).owner == "worker-a"

    def test_active_lease_cannot_be_extended_by_another_owner(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        original = claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        claim_slot(session, SLOT, "worker-b", timedelta(hours=8), DUE)
        assert to_utc(read_slot(session, SLOT).lease_until) == original.lease_until

    def test_expire_sweep_does_not_disturb_an_active_lease(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        assert expire_stale_claims(session, DUE + LEASE - timedelta(seconds=1)) == 0
        row = read_slot(session, SLOT)
        assert row.state == SlotState.CLAIMED.value
        assert row.owner == "worker-a"

    def test_sweep_on_never_claimed_slot_is_a_no_op(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        assert expire_stale_claims(session, DUE + timedelta(days=400)) == 0
        assert read_slot(session, SLOT).state == SlotState.DUE.value

    def test_non_positive_lease_is_refused(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        with pytest.raises(ValueError):
            claim_slot(session, SLOT, "worker-a", timedelta(0), DUE)
        assert read_slot(session, SLOT).state == SlotState.DUE.value

    def test_empty_owner_is_refused(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        with pytest.raises(ValueError):
            claim_slot(session, SLOT, "", LEASE, DUE)
        with pytest.raises(ValueError):
            claim_slot(session, SLOT, "   ", LEASE, DUE)
        assert read_slot(session, SLOT).owner is None

    def test_claiming_a_missing_slot_raises(self, session):
        with pytest.raises(SlotNotFound):
            claim_slot(session, "maintenance:2099-01-01T00:07:00Z", "w", LEASE, DUE)

    def test_malformed_slot_id_is_refused(self, session):
        with pytest.raises(ValueError):
            claim_slot(session, "not-a-slot", "w", LEASE, DUE)


class TestTerminalStates:
    def _succeeded_slot(self, session, owner="worker-a"):
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, owner, LEASE, DUE)
        transition_slot(session, SLOT, SlotState.DISPATCHED, as_of=DUE, workflow_run_id="gh-1")
        transition_slot(session, SLOT, SlotState.RUNNING, as_of=DUE)
        transition_slot(session, SLOT, SlotState.SUCCEEDED, as_of=DUE)
        return session

    def test_full_lifecycle(self, session):
        self._succeeded_slot(session)
        row = read_slot(session, SLOT)
        assert row.state == SlotState.SUCCEEDED.value
        assert row.workflow_run_id == "gh-1"

    def test_succeeded_slot_cannot_be_claimed(self, session):
        self._succeeded_slot(session)
        with pytest.raises(InvalidTransition):
            claim_slot(session, SLOT, "late-comer", LEASE, DUE + timedelta(days=1))
        assert read_slot(session, SLOT).state == SlotState.SUCCEEDED.value

    def test_succeeded_slot_cannot_be_recovered(self, session):
        self._succeeded_slot(session)
        with pytest.raises(InvalidTransition):
            recover_slot(session, SLOT, "late-comer", LEASE, DUE + timedelta(days=1))
        assert read_slot(session, SLOT).state == SlotState.SUCCEEDED.value

    def test_terminal_state_rejects_any_follow_up(self, session):
        self._succeeded_slot(session)
        with pytest.raises(InvalidTransition):
            transition_slot(session, SLOT, SlotState.RUNNING, as_of=DUE)
        assert read_slot(session, SLOT).state == SlotState.SUCCEEDED.value

    def test_illegal_transition_leaves_no_partial_mutation(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        before = read_slot(session, SLOT)
        with pytest.raises(InvalidTransition):
            transition_slot(session, SLOT, SlotState.SUCCEEDED, as_of=DUE)
        after = read_slot(session, SLOT)
        assert after.state == before.state == SlotState.DUE.value
        assert after.owner == before.owner
        assert after.attempt == before.attempt


# ---------------------------------------------------------------------------
# Expiry and recovery
# ---------------------------------------------------------------------------


class TestExpiryAndRecovery:
    def _claimed(self, session, owner="worker-a", lease=LEASE):
        ensure_slot(session, DUE, as_of=DUE)
        return claim_slot(session, SLOT, owner, lease, DUE)

    def test_lapsed_lease_expires(self, session):
        self._claimed(session)
        after_lapse = DUE + LEASE + timedelta(seconds=1)
        assert expire_stale_claims(session, after_lapse) == 1
        row = read_slot(session, SLOT)
        assert row.state == SlotState.EXPIRED.value

    def test_lease_expiring_exactly_now_is_expired(self, session):
        self._claimed(session)
        assert expire_stale_claims(session, DUE + LEASE) == 1
        assert read_slot(session, SLOT).state == SlotState.EXPIRED.value

    def test_expiry_never_returns_a_slot_silently_to_due(self, session):
        """A lapsed lease is a fact to surface, not an invisible reset."""
        self._claimed(session)
        expire_stale_claims(session, DUE + LEASE + timedelta(seconds=1))
        row = read_slot(session, SLOT)
        assert row.state != SlotState.DUE.value
        assert row.state == SlotState.EXPIRED.value

    def test_expiry_is_idempotent(self, session):
        self._claimed(session)
        after_lapse = DUE + LEASE + timedelta(seconds=1)
        assert expire_stale_claims(session, after_lapse) == 1
        assert expire_stale_claims(session, after_lapse) == 0
        assert expire_stale_claims(session, after_lapse) == 0
        assert read_slot(session, SLOT).state == SlotState.EXPIRED.value

    def test_recovery_reclaims_the_slot(self, session):
        self._claimed(session, owner="worker-a")
        after_lapse = DUE + LEASE + timedelta(seconds=1)
        expire_stale_claims(session, after_lapse)
        outcome = recover_slot(session, SLOT, "worker-b", LEASE, after_lapse)
        assert outcome.claimed is True
        row = read_slot(session, SLOT)
        assert row.state == SlotState.CLAIMED.value
        assert row.owner == "worker-b"
        assert row.attempt == 2

    def test_recovery_uses_the_claim_primitive_not_a_second_mechanism(self, session):
        self._claimed(session)
        after_lapse = DUE + LEASE + timedelta(seconds=1)
        expire_stale_claims(session, after_lapse)
        winner = recover_slot(session, SLOT, "worker-b", LEASE, after_lapse)
        blocked = recover_slot(session, SLOT, "worker-c", LEASE, after_lapse)
        assert winner.claimed is True
        assert blocked.claimed is False
        assert blocked.owner == "worker-b"
        assert read_slot(session, SLOT).owner == "worker-b"

    def test_a_due_slot_is_not_recovered(self, session):
        """Recovery is EXPIRED -> CLAIMED; a DUE slot was never claimed.

        Reported as an ordinary loss rather than an exception: a recovery sweep
        that touches slots which are simply not expired must not crash, and a
        caller that ignores the outcome changes nothing.
        """
        ensure_slot(session, DUE, as_of=DUE)
        assert recover_slot(session, SLOT, "worker-b", LEASE, DUE).claimed is False
        assert read_slot(session, SLOT).state == SlotState.DUE.value
        assert read_slot(session, SLOT).attempt == 0

    def test_a_claimed_slot_is_not_recovered(self, session):
        self._claimed(session, owner="worker-a")
        assert recover_slot(session, SLOT, "worker-b", LEASE, DUE).claimed is False
        assert read_slot(session, SLOT).owner == "worker-a"
        assert read_slot(session, SLOT).attempt == 1

    def test_recovery_after_recovery_is_possible_once_expired_again(self, session):
        self._claimed(session, owner="worker-a", lease=timedelta(minutes=5))
        first_lapse = DUE + timedelta(minutes=5, seconds=1)
        expire_stale_claims(session, first_lapse)
        recover_slot(session, SLOT, "worker-b", timedelta(minutes=5), first_lapse)
        second_lapse = first_lapse + timedelta(minutes=5, seconds=1)
        expire_stale_claims(session, second_lapse)
        assert recover_slot(session, SLOT, "worker-c", LEASE, second_lapse).claimed is True
        row = read_slot(session, SLOT)
        assert row.owner == "worker-c"
        assert row.attempt == 3


class TestAlreadyLoadedSessions:
    """Regression: the guard must never be re-evaluated in Python.

    An ORM bulk update defaults to ``synchronize_session="auto"``, which makes
    SQLAlchemy evaluate the ``WHERE`` clause against objects already in the
    session's identity map. ``lease_until <= as_of`` then compares a naive
    datetime loaded from SQLite against an aware one and raises ``TypeError``.

    This only fires when the slot happens to be loaded already, which is why it
    surfaced in a full-suite run and not in isolation - and it would have surfaced
    in production as an expiry sweep that crashed depending on session contents.
    Every helper below is therefore called *after* loading the slot, and a
    TypeError here fails the test.
    """

    def test_sweep_after_the_slot_is_loaded(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        assert read_slot(session, SLOT) is not None

        assert expire_stale_claims(session, DUE + LEASE + timedelta(seconds=1)) == 1
        assert read_slot(session, SLOT).state == SlotState.EXPIRED.value

    def test_claim_after_the_slot_is_loaded(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        assert read_slot(session, SLOT) is not None

        assert claim_slot(session, SLOT, "worker-a", LEASE, DUE).claimed is True
        assert read_slot(session, SLOT).owner == "worker-a"

    def test_transition_after_the_slot_is_loaded(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        assert read_slot(session, SLOT) is not None

        transition_slot(session, SLOT, SlotState.DISPATCHED, as_of=DUE, workflow_run_id="gh-1")
        assert read_slot(session, SLOT).workflow_run_id == "gh-1"

    def test_read_slot_never_hands_back_a_cached_value(self, session):
        """A re-read must reflect the guarded update, not the identity map.

        The mutation is a Core statement, so it deliberately does not touch
        loaded ORM instances. ``read_slot`` is what has to guarantee freshness:
        asking again returns the committed state, even though the row was already
        in this session.
        """
        ensure_slot(session, DUE, as_of=DUE)
        first = read_slot(session, SLOT)
        assert first.state == SlotState.DUE.value

        claim_slot(session, SLOT, "worker-a", LEASE, DUE)

        assert read_slot(session, SLOT).state == SlotState.CLAIMED.value
        assert read_slot(session, SLOT).owner == "worker-a"
        assert first.state == SlotState.CLAIMED.value


# ---------------------------------------------------------------------------
# Transaction safety
# ---------------------------------------------------------------------------


class TestNoPartialMutation:
    def test_losing_claim_commits_nothing(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        before = read_slot(session, SLOT)
        claim_slot(session, SLOT, "worker-b", LEASE, DUE)
        after = read_slot(session, SLOT)
        assert (after.state, after.owner, after.attempt) == (
            before.state,
            before.owner,
            before.attempt,
        )
        assert to_utc(after.lease_until) == to_utc(before.lease_until)

    def test_duplicate_slot_race_commits_nothing_extra(self, session):
        ensure_slot(session, DUE, as_of=DUE)
        ensure_slot(session, DUE, as_of=DUE + timedelta(minutes=30))
        assert _row_count(session, "maintenance_slots") == 1
        row = read_slot(session, SLOT)
        assert row.state == SlotState.DUE.value
        assert row.attempt == 0
        assert row.owner is None

    def test_failed_insert_leaves_no_partial_row(self, session):
        with pytest.raises(ValueError):
            ensure_slot(session, datetime(2026, 10, 4, 12, 7), as_of=DUE)
        assert _row_count(session, "maintenance_slots") == 0

    def test_session_is_usable_after_a_refused_claim(self, session):
        """A rejected call must not leave the session mid-transaction."""
        ensure_slot(session, DUE, as_of=DUE)
        with pytest.raises(ValueError):
            claim_slot(session, SLOT, "worker-a", timedelta(minutes=-1), DUE)
        assert claim_slot(session, SLOT, "worker-a", LEASE, DUE).claimed is True
        assert read_slot(session, SLOT).owner == "worker-a"

    def test_ensure_slot_does_not_reset_an_advanced_slot(self, session):
        """Idempotent means no-op, not reset: a completed slot stays completed."""
        ensure_slot(session, DUE, as_of=DUE)
        claim_slot(session, SLOT, "worker-a", LEASE, DUE)
        transition_slot(session, SLOT, SlotState.DISPATCHED, as_of=DUE, workflow_run_id="gh-9")
        ensure_slot(session, DUE, as_of=DUE + timedelta(hours=6))
        row = read_slot(session, SLOT)
        assert row.state == SlotState.DISPATCHED.value
        assert row.owner == "worker-a"
        assert row.workflow_run_id == "gh-9"
        assert row.attempt == 1

    def test_durable_state_survives_a_reopened_connection(self, engine):
        """The row is committed, not merely visible in the writing session."""
        ensure_slot(sessionmaker(bind=engine, expire_on_commit=False)(), DUE, as_of=DUE)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as first:
            canonical = ensure_slot(first, DUE, as_of=DUE)
            claim_slot(first, canonical, "worker-a", LEASE, DUE)
        with factory() as second:
            row = read_slot(second, canonical)
            assert row.state == SlotState.CLAIMED.value
            assert row.owner == "worker-a"
            assert to_utc(row.lease_until) == DUE + LEASE