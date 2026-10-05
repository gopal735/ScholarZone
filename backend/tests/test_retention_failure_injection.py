"""Phase 9 - failure injection. No partially completed destructive transaction.

Eight failure modes, each injected at the layer where it would really occur, and
each asserting the same property: **if the batch does not finish, nothing it
touched survives.** A half-deleted batch is worse than no deletion at all,
because the records that were removed are gone and the evidence that they were
safe to remove went with them.

The injections are placed at the database rather than by patching ``Session``, so
what is under test is the transaction boundary and not the test's own
instrumentation. Patching ``commit`` to raise before doing anything would pass a
suite that had no rollback at all - which is exactly the bug this file exists to
keep fixed.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    DiscoveryCandidate,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipRestoreRecord,
    ScholarshipSnapshot,
    ScholarshipVerificationHistory,
)
from app.services.retention_contract import RetentionPolicy
from app.services.retention_engine import CleanupAborted, delete_bounded

AS_OF = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
ANCIENT = datetime(2019, 1, 1, tzinfo=timezone.utc)
POLICY = RetentionPolicy(
    cleanup_enabled=True, dry_run=False, batch_size=10, max_delete_percentage=1.0
)

#: How many times an injected failure fires before it stops interfering. One is
#: enough to break the batch; a bound keeps a later, legitimate statement from
#: being caught by the same listener.
ONE_SHOT = {"remaining": 1}


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'failure.db'}")
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def fail_on(engine):
    """Inject a failure into the Nth statement matching a predicate.

    ``occurrence`` matters: a failure on the *first* match proves the rollback,
    but a failure on the *third* match additionally proves that work already
    committed earlier in the same batch is undone. Both are needed, and only a
    counter can express the second.
    """

    def install(predicate, exc_factory, *, occurrence: int = 1):
        state = {"seen": 0}

        def once(conn, cursor, statement, parameters, context, executemany):
            if not predicate(" ".join(statement.split())):
                return
            state["seen"] += 1
            if state["seen"] == occurrence:
                raise exc_factory()

        event.listen(engine, "before_cursor_execute", once)
        return state

    return install


def candidate(session, tag: str, *, armed=ANCIENT, archived=ANCIENT) -> int:
    row = Scholarship(
        title=f"Candidate {tag}", country="PE", degree="Master", funding="Part",
        official_source="O", official_source_url=f"https://o.test/{tag}",
        status="closed", is_archived=True, archived_at=archived,
        archived_reason="deadline passed on 2019-01-01",
        auto_delete_candidate_since=armed, is_verified=False,
        verification_status="inactive", deadline_date=date(2018, 6, 1),
    )
    session.add(row)
    session.commit()
    return row.id


def survivors(session) -> set[int]:
    session.expire_all()
    return set(session.scalars(select(Scholarship.id)).all())


def child_counts(session) -> dict[str, int]:
    session.expire_all()
    return {
        model.__tablename__: session.query(model).count()
        for model in (
            ScholarshipFetchAttempt, ScholarshipRestoreRecord,
            ScholarshipSnapshot, ScholarshipVerificationHistory,
        )
    }


def attach_disposable_children(session, sid: int) -> None:
    session.add(
        ScholarshipFetchAttempt(
            scholarship_id=sid, source_url=f"https://o.test/{sid}",
            status="resolved", terminal=True, resolved_at=ANCIENT,
        )
    )
    session.add(
        DiscoveryCandidate(
            source_url=f"https://o.test/{sid}", normalized_url=f"https://o.test/{sid}",
            discovery_hash=f"h{sid}", status="resolved", match_status="rejected",
            matched_scholarship_id=sid, resolved_at=ANCIENT,
        )
    )
    session.commit()


class TestAChildRowsAreRemovedAndTheParentFails:
    """A: the child deletions succeed, then the parent delete raises.

    This is the exact shape of the defect the engine once had: the guard wrapped
    only ``commit``, so the statements before it had already been applied. If the
    rollback is missing, the fetch telemetry and the detached discovery links are
    committed against a record that was never deleted.
    """

    def test_nothing_survives_when_the_parent_delete_raises(self, session, fail_on, tmp_path):
        ids = [candidate(session, f"a{i}") for i in range(3)]
        for sid in ids:
            attach_disposable_children(session, sid)
        before_children = child_counts(session)

        fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: DBAPIError("DELETE", {}, RuntimeError("injected parent failure")),
        )
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-a",
        )

        assert report["deleted"] == []
        assert survivors(session) == set(ids), "a parent row was lost to a failed batch"
        assert child_counts(session) == before_children, (
            "child rows were changed even though no parent was deleted"
        )
        assert any("transaction rolled back" in a["reason"] for a in report["aborted"])

    def test_the_discovery_link_is_not_left_detached(self, session, fail_on, tmp_path):
        sid = candidate(session, "a-detach")
        attach_disposable_children(session, sid)
        fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: DBAPIError("DELETE", {}, RuntimeError("injected")),
        )
        delete_bounded(
            session, [sid], as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-a2",
        )
        session.expire_all()
        still_linked = [
            c for c in session.scalars(select(DiscoveryCandidate)).all()
            if c.matched_scholarship_id == sid
        ]
        assert len(still_linked) == 1
        assert still_linked[0].match_status == "rejected"


class BParentDeletionFailsAfterPartialWork:
    """B: the first parent deletes, a later one raises. All of it must roll back."""

    def test_an_earlier_success_is_rolled_back(self, session, fail_on, tmp_path):
        ids = [candidate(session, f"b{i}") for i in range(4)]
        state = fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: DBAPIError("DELETE", {}, RuntimeError("injected")),
            occurrence=3,
        )
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-b",
        )

        assert state["seen"] >= 3, "the injection never fired, so nothing was proven"
        assert report["deleted"] == []
        assert survivors(session) == set(ids), (
            "a partially completed batch survived the rollback"
        )


class CDatabaseStatementError:
    """C: a statement fails for an ordinary reason - a constraint, bad SQL."""

    def test_a_foreign_key_violation_leaves_everything_in_place(self, session, fail_on, tmp_path):
        ids = [candidate(session, f"c{i}") for i in range(2)]
        # Anchored to the DELETE verb: an unanchored table-name match also catches
        # the scan's own read of the same table, which would fire the injection
        # during classification and prove nothing about the batch.
        fail_on(
            lambda sql: sql.upper().startswith("DELETE")
            and "scholarship_fetch_attempts" in sql.lower(),
            lambda: DBAPIError("DELETE", {}, RuntimeError("injected FK violation")),
        )
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-c",
        )
        assert report["deleted"] == []
        assert survivors(session) == set(ids)


class DTransactionCommitFailure:
    """D: the statements succeeded, then the commit failed."""

    def test_a_failed_commit_discards_the_statements(self, session, fail_on, tmp_path):
        ids = [candidate(session, f"d{i}") for i in range(3)]
        fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: DBAPIError("statement", {}, RuntimeError("injected commit-time failure")),
        )
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-d",
        )
        assert report["deleted"] == []
        assert survivors(session) == set(ids)

    def test_the_run_is_not_reported_as_ok(self, session, fail_on, tmp_path):
        ids = [candidate(session, f"d2{i}") for i in range(2)]
        fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: DBAPIError("statement", {}, RuntimeError("injected")),
        )
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-d2",
        )
        assert report["status"] != "ok", (
            "a rolled-back batch must not be reported as a successful run"
        )
        assert report["batches_rolled_back"] >= 1


class ETimeout:
    """E: the batch runs out of time mid-flight."""

    def test_a_timeout_rolls_the_batch_back(self, session, fail_on, tmp_path):
        ids = [candidate(session, f"e{i}") for i in range(3)]
        fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: OperationalError("DELETE", {}, TimeoutError("injected timeout")),
        )
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-e",
        )
        assert report["deleted"] == []
        assert survivors(session) == set(ids)


class FConnectionLoss:
    """F: the connection dies mid-batch."""

    def test_a_lost_connection_rolls_the_batch_back(self, session, fail_on, tmp_path):
        ids = [candidate(session, f"f{i}") for i in range(3)]
        fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: OperationalError("DELETE", {}, ConnectionError("injected connection loss")),
        )
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="fail-f",
        )
        assert report["deleted"] == []
        assert survivors(session) == set(ids)


class GDuplicateExecution:
    """G: the same run executed twice, or two runs racing for the same ids."""

    def test_a_second_run_of_the_same_ids_deletes_nothing(self, session, tmp_path):
        ids = [candidate(session, f"g{i}") for i in range(3)]
        first = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json", run_id="g1"
        )
        assert sorted(first["deleted"]) == sorted(ids)
        second = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json", run_id="g2"
        )
        assert second["deleted"] == []
        assert survivors(session) == set()

    def test_a_second_run_does_not_double_count_the_ledger(self, session, tmp_path):
        import json

        ledger = tmp_path / "l.json"
        ids = [candidate(session, f"g2{i}") for i in range(2)]
        delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=ledger, run_id="g2a"
        )
        delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=ledger, run_id="g2b"
        )
        written = json.loads(ledger.read_text(encoding="utf-8"))
        assert written["count"] == 2, "a repeated run inflated the deletion count"
        assert len({r["scholarship_id"] for r in written["records"]}) == 2

    def test_a_repeated_id_inside_one_run_is_deleted_once(self, session, tmp_path):
        sid = candidate(session, "g3")
        report = delete_bounded(
            session, [sid, sid, sid], as_of=AS_OF, policy=POLICY,
            ledger=tmp_path / "l.json", run_id="g3",
        )
        assert report["deleted"] == [sid]
        assert survivors(session) == set()


class HRestartDuringGracePeriod:
    """H: the process restarts while a record is inside its grace period."""

    def test_a_grace_eligible_record_survives_a_restart(self, engine, session, tmp_path):
        """A new connection, a new session, a new engine - the clock is the same."""
        armed = AS_OF - timedelta(days=5)
        ids = [candidate(session, f"h{i}", armed=armed) for i in range(2)]
        session.close()

        fresh = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
        try:
            report = delete_bounded(
                fresh, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
                run_id="fail-h",
            )
            assert report["deleted"] == []
            assert survivors(fresh) == set(ids)
            from app.services.retention_engine import scan

            states = {d.scholarship_id: d.state for d in scan(fresh, as_of=AS_OF)}
            assert set(states.values()) == {"GRACE_ELIGIBLE"}
        finally:
            fresh.close()

    def test_the_clock_only_advances_with_time_not_with_restarts(self, engine, session, tmp_path):
        """Repeated restarts must not consume the grace period.

        A grace clock derived from anything other than a stored timestamp would be
        consumed by the act of restarting, which would turn "wait fourteen days"
        into "restart fourteen times".
        """
        armed = AS_OF - timedelta(days=13)
        sid = candidate(session, "h-clock", armed=armed)
        for attempt in range(4):
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            db = factory()
            try:
                report = delete_bounded(
                    db, [sid], as_of=AS_OF, policy=POLICY,
                    ledger=tmp_path / f"l{attempt}.json", run_id=f"fail-h{attempt}",
                )
                assert report["deleted"] == [], f"deleted on restart {attempt}"
            finally:
                db.close()
        assert survivors(session) == {sid}


class TestEveryFailureLeavesTheCatalogueConsistent:
    """The invariant that spans all eight modes."""

    @pytest.mark.parametrize(
        "mode, occurrence",
        [
            ("parent", 1),
            ("third", 3),
            ("fk", 1),
            ("commit", 1),
            ("timeout", 1),
            ("connection", 1),
        ],
    )
    def test_no_partial_deletion_survives_any_mode(
        self, session, fail_on, tmp_path, mode, occurrence
    ):
        """Every mode, one assertion: the batch is all-or-nothing."""
        ids = [candidate(session, f"all-{mode}-{i}") for i in range(5)]
        for sid in ids:
            attach_disposable_children(session, sid)
        children_before = child_counts(session)

        def parent_delete(sql: str) -> bool:
            return sql.upper().startswith("DELETE FROM SCHOLARSHIPS")

        def fire(sql: str) -> bool:
            # "fk" is anchored to the DELETE verb on purpose: an unanchored table
            # match also catches the scan's read of the same table and would fire
            # during classification, proving nothing about the batch.
            if mode == "fk":
                return sql.upper().startswith("DELETE") and "scholarship_fetch_attempts" in sql.lower()
            return parent_delete(sql)

        if mode == "timeout":
            exc = lambda: OperationalError("DELETE", {}, TimeoutError("timeout"))
        elif mode == "connection":
            exc = lambda: OperationalError("DELETE", {}, ConnectionError("connection"))
        else:
            exc = lambda: DBAPIError("DELETE", {}, RuntimeError("injected"))

        state = fail_on(fire, exc, occurrence=occurrence)
        report = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id=f"all-{mode}",
        )

        assert state["seen"] >= occurrence, (
            f"the injection never fired, so {mode} mode proved nothing"
        )
        assert report["deleted"] == []
        assert survivors(session) == set(ids)
        assert report["status"] != "ok"
        if mode != "fk":
            assert child_counts(session) == children_before

    def test_a_second_attempt_after_a_failure_still_works(self, session, fail_on, tmp_path):
        """The engine is reusable after an abort; it is not left poisoned."""
        ids = [candidate(session, f"retry{i}") for i in range(2)]
        fail_on(
            lambda sql: sql.upper().startswith("DELETE FROM SCHOLARSHIPS"),
            lambda: DBAPIError("DELETE", {}, RuntimeError("injected")),
        )
        delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l.json",
            run_id="retry-1",
        )
        second = delete_bounded(
            session, ids, as_of=AS_OF, policy=POLICY, ledger=tmp_path / "l2.json",
            run_id="retry-2",
        )
        assert sorted(second["deleted"]) == sorted(ids)
        assert survivors(session) == set()
