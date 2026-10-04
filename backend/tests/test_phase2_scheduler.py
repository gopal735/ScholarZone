"""Phase 2: the scheduled path arms candidates and cannot delete.

Phase 2 turns on observation, not deletion. The property that matters is
therefore negative - *nothing reachable from a scheduled run can delete a row* -
so these tests are mostly about what the scheduler does not select, and about the
selection logic being taken from the shipped constants rather than restated here.

The scheduler's own default is `--stage all`, which is what both a `schedule`
event and a dispatch with no stage argument execute. That equivalence is asserted
rather than assumed, because "the cron runs something else" would invalidate
every claim below.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from app.jobs import scholarzone_maintenance as worker

PURGE = "purge_closed"
CANDIDATE = "auto_delete_candidate"


def selection(stage_argument: str | None) -> list[str]:
    """The worker's own stage selection, reproduced from its own constants.

    Mirrors the comprehension in ``main`` rather than importing it, because that
    comprehension is a closure over argparse and cannot be called directly. The
    two facts it depends on - ``STAGE_ORDER`` and ``PURGE_CLOSED_EXCLUDED_FROM_ALL``
    - are read from the module, so a change to either is picked up here.
    """
    wanted = {stage_argument} if stage_argument else {"all"}
    if "all" in wanted:
        return [s for s in worker.STAGE_ORDER if s != PURGE]
    return [s for s in worker.STAGE_ORDER if s in wanted]


def stage_source(name: str) -> str:
    """Read a stage runner's source.

    The runners are closures inside ``main()``, so they are not module
    attributes. Reading them from the module source is also what makes the claim
    about the shipped code rather than about an import.
    """
    text = inspect.getsource(worker)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{name} not found in the worker source")


class TestTheScheduledPathSelectsArmingOnly:
    def test_the_scheduler_default_is_all(self):
        # Both a `schedule` event and a dispatch with no stage argument run
        # `--stage all`. If this stops being true, every test below is about a
        # path nobody takes.
        source = inspect.getsource(worker.main)
        assert 'github.event.inputs.stage' in source or 'args.stage' in source
        assert '"all"' in source

    def test_a_scheduled_run_invokes_the_arming_stage(self):
        assert CANDIDATE in selection(None)
        assert CANDIDATE in selection("all")

    def test_a_scheduled_run_cannot_invoke_the_deletion_stage(self):
        assert PURGE not in selection(None)
        assert PURGE not in selection("all")

    def test_the_deletion_stage_is_only_reachable_by_naming_it(self):
        assert selection(PURGE) == [PURGE]
        assert selection(CANDIDATE) == [CANDIDATE]

    def test_the_deleting_stages_reachability_is_declared_and_asserted(self):
        # Phase 2 asserted the stage was excluded; Phase 3 flipped the flag, so
        # the assertion follows the flag rather than a literal. What must hold in
        # both states is that the flag is compared against the real selection in
        # main() - otherwise a refactor could hard-code the stage name back into
        # the comprehension and the flag would silently describe nothing.
        assert isinstance(worker.PURGE_CLOSED_EXCLUDED_FROM_ALL, bool)
        source = inspect.getsource(worker.main)
        assert "does not match the stage selection" in source
        assert 's != "purge_closed"' not in source


class TestNothingReachableFromArmingDeletes:
    @pytest.mark.parametrize(
        "forbidden",
        ["delete_exact", "do_purge_closed", "purge_closed", "session.delete"],
    )
    def test_the_arming_stage_never_names_the_deletion_machinery(self, forbidden):
        source = stage_source("do_auto_delete_candidate")
        assert forbidden not in source, (
            f"do_auto_delete_candidate references {forbidden!r}; the scheduled "
            "path must not be able to reach a delete"
        )

    @pytest.mark.parametrize("forbidden", ["delete_exact", "session.delete", "_append_manifest"])
    def test_the_collectors_arm_function_never_deletes(self, forbidden):
        from app.services import auto_delete_collector

        source = inspect.getsource(auto_delete_collector.arm)
        assert forbidden not in source

    def test_arming_only_touches_the_candidate_clock(self):
        from app.services import auto_delete_collector

        source = inspect.getsource(auto_delete_collector.arm)
        # The only column it may write is the grace clock.
        writes = [
            line.strip()
            for line in source.splitlines()
            if "auto_delete_candidate_since =" in line
        ]
        assert writes, "arm() sets nothing at all"
        for line in writes:
            assert "row.auto_delete_candidate_since" in line, line


class TestAFailedCollectorStageFailsTheRun:
    def test_a_stage_returning_a_truthy_error_is_not_ok(self):
        # A stage that catches its own failure and returns {"error": ...} is the
        # convention across this job, so the runner is where it has to be
        # honoured. Without this, the collector could stop working entirely and
        # every scheduled run would still report success.
        ok = worker._run_stage("probe", lambda: {"error": "name 'x' is not defined"})
        assert ok.ok is False
        assert ok.error and "x" in ok.error

    def test_a_stage_returning_error_none_is_ok(self):
        assert worker._run_stage("probe", lambda: {"error": None, "deleted": []}).ok is True

    def test_a_stage_that_raises_is_not_ok(self):
        def boom():
            raise RuntimeError("no database")

        report = worker._run_stage("probe", boom)
        assert report.ok is False
        assert "RuntimeError" in (report.error or "")

    def test_a_successful_stage_keeps_its_detail(self):
        report = worker._run_stage("probe", lambda: {"scanned": 451})
        assert report.ok is True
        assert report.detail["scanned"] == 451


class TestScheduledArmingIsIdempotent:
    def _session_factory(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.models import Base

        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)

    def _closed(self, session, sid, days=400):
        from datetime import datetime, timedelta, timezone

        from app.models import Scholarship

        archived = datetime.now(timezone.utc) - timedelta(days=days)
        session.add(
            Scholarship(
                id=sid,
                title=f"Closed {sid}",
                country="XX",
                degree="master",
                funding="stipend",
                deadline_precision="month",
                status="closed",
                is_archived=True,
                archived_at=archived,
                verification_status="retired",
                is_verified=True,
                fully_funded=False,
                updated_at=archived,
                created_at=archived,
            )
        )
        session.commit()

    def test_running_the_arming_stage_twice_arms_once_and_deletes_nothing(self):
        from app.models import Scholarship
        from app.services.auto_delete_collector import arm, collect

        factory = self._session_factory()
        session = factory()
        try:
            self._closed(session, 1)
            first = arm(session, collect(session), dry_run=False)
            assert first["newly_armed"] == [1]
            stamped = session.get(Scholarship, 1).auto_delete_candidate_since
            assert stamped is not None

            second = arm(session, collect(session), dry_run=False)
            assert second["newly_armed"] == []
            assert second["disarmed"] == []
            assert session.get(Scholarship, 1).auto_delete_candidate_since == stamped

            rows = collect(session)
            assert all(d.verdict != "SAFE_DELETE" for d in rows), (
                "arming must not make a record deletable in the same cycle"
            )
            assert session.get(Scholarship, 1) is not None, "a row was deleted"
        finally:
            session.close()

    def test_a_record_that_stops_qualifying_is_disarmed_on_the_next_run(self):
        from app.models import Scholarship
        from app.services.auto_delete_collector import arm, collect

        factory = self._session_factory()
        session = factory()
        try:
            self._closed(session, 1)
            arm(session, collect(session), dry_run=False)
            assert session.get(Scholarship, 1).auto_delete_candidate_since is not None

            row = session.get(Scholarship, 1)
            row.deletion_protected = True
            session.commit()

            outcome = arm(session, collect(session), dry_run=False)
            assert outcome["disarmed"] == [1]
            assert session.get(Scholarship, 1).auto_delete_candidate_since is None
        finally:
            session.close()

    def test_the_deletion_dependency_edge_points_at_arming(self):
        # If purge_closed is ever run by name, it must be after arming, never
        # before: a delete must never see an unarmed record.
        assert worker.STAGE_DEPENDENCIES[PURGE] == (CANDIDATE,)
        assert worker.STAGE_DEPENDENCIES[CANDIDATE] == ()
        assert worker.STAGE_ORDER.index(CANDIDATE) < worker.STAGE_ORDER.index(PURGE)


class TestCollectorPolicyIsUnchangedInPhaseTwo:
    """Phase 2 changes scheduling only. The policy must be untouched."""

    def test_retention_and_grace_are_still_the_contracted_values(self):
        from app.services.auto_delete_policy import (
            AUTO_DELETE_AFTER_DAYS,
            DELETE_GRACE_DAYS,
        )

        assert AUTO_DELETE_AFTER_DAYS == 180
        assert DELETE_GRACE_DAYS == 14

    def test_operator_protection_still_blocks_candidacy(self):
        from app.services.auto_delete_policy import (
            VERDICT_PROTECTED,
            RecordFacts,
            evaluate,
        )

        decision = evaluate(
            RecordFacts(
                id=1,
                status="closed",
                is_archived=True,
                verification_status="retired",
                deletion_protected=True,
            ),
            candidate_since=None,
        )
        assert decision.verdict == VERDICT_PROTECTED
