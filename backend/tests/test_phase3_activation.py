"""Phase 3: the scheduled lifecycle may delete, and only what has already earned it.

Activation is one flag. Everything that makes deletion safe lives in the policy
and the collector, and none of it is touched here. These tests exist because the
one-line change that enables a scheduled delete is exactly the kind of change
that needs more than one line of proof behind it.

Two families:

* **reachability** - what the scheduler can select, in what order, and what that
  implies when a future refactor changes the selection logic;
* **safety** - that reaching the delete stage still deletes nothing unless a
  record passed the policy, the retention period, a grace period spanning an
  earlier cycle, and a re-decision inside the deleting transaction.

The second family is deliberately mostly negative. A delete that happens when it
should not is the failure this whole feature exists to prevent, and every test
that can prove a *non*-deletion is doing more useful work here than another test
that proves a deletion.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.jobs import scholarzone_maintenance as worker
from app.services.auto_delete_policy import (
    AUTO_DELETE_AFTER_DAYS,
    DELETE_GRACE_DAYS,
    VERDICT_SAFE_DELETE,
    DependencySummary,
    RecordFacts,
)

PURGE = worker.DELETING_STAGE
CANDIDATE = worker.ARMING_STAGE


def selection(stage_argument: str | None) -> list[str]:
    """The worker's own selection, reproduced from its own constants.

    Mirrors the comprehension in ``main`` because that comprehension closes over
    argparse. Both inputs it reads - ``STAGE_ORDER`` and
    ``PURGE_CLOSED_EXCLUDED_FROM_ALL`` - come from the module, so a change to
    either is picked up here rather than silently passing a restated copy.
    """
    wanted = {stage_argument} if stage_argument else {"all"}
    run_all = "all" in wanted
    excluded = {PURGE} if worker.PURGE_CLOSED_EXCLUDED_FROM_ALL else set()
    return [s for s in worker.STAGE_ORDER if (run_all and s not in excluded) or s in wanted]


def nested_function_source(name: str) -> str:
    """Read a stage runner's source.

    The runners are closures inside ``main()`` and so are not module attributes.
    Reading them from the module source is also what makes the claim about the
    shipped code rather than about a stale import.
    """
    text = inspect.getsource(worker)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{name} not found in the worker source")


def nested_function_code(name: str) -> str:
    """A stage runner's source with its docstring removed.

    Several of these docstrings quote the expressions they are warning against -
    ``do_purge_closed`` describes the ``status == "closed"`` selection it no longer
    performs. A test that greps the raw source would match the warning and fail on
    the very documentation that makes the behaviour safe, so the prose is removed
    and only the executable body is inspected.
    """
    text = inspect.getsource(worker)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = list(node.body)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            clone = ast.FunctionDef(
                name=node.name,
                args=node.args,
                body=body or [ast.Pass()],
                decorator_list=node.decorator_list,
                returns=None,
                type_comment=None,
            )
            return ast.unparse(ast.fix_missing_locations(clone))
    raise AssertionError(f"{name} not found in the worker source")


# ---------------------------------------------------------------- 1-5, 19
class TestTheScheduledPathReachesBothStages:
    def test_1_all_includes_the_arming_stage(self):
        assert CANDIDATE in selection(None)
        assert CANDIDATE in selection("all")

    def test_2_all_includes_the_deleting_stage(self):
        # This is the activation. It was False two phases ago.
        assert worker.PURGE_CLOSED_EXCLUDED_FROM_ALL is False
        assert PURGE in selection(None)
        assert PURGE in selection("all")

    def test_3_arming_runs_before_deleting(self):
        scheduled = selection("all")
        assert scheduled.index(CANDIDATE) < scheduled.index(PURGE)

    def test_4_the_dependency_is_declared(self):
        assert worker.STAGE_DEPENDENCIES[PURGE] == (CANDIDATE,)
        assert worker.STAGE_DEPENDENCIES[CANDIDATE] == ()

    def test_5_deleting_cannot_be_selected_without_arming(self):
        # The schedule may only delete if it can also arm, and arming first.
        scheduled = selection("all")
        if PURGE in scheduled:
            assert CANDIDATE in scheduled
            assert scheduled.index(CANDIDATE) < scheduled.index(PURGE)

    def test_19_a_refactor_that_re_excludes_the_stage_fails_a_test(self):
        """The regression guard for the activation itself.

        Nothing about this feature stops a future edit from putting the stage back
        behind a hard-coded name. The two things that must then hold - the flag
        describes the selection, and the ordering is respected - are asserted, so
        the change cannot pass review by looking harmless in the diff.
        """
        source = inspect.getsource(worker.main)
        assert "PURGE_CLOSED_EXCLUDED_FROM_ALL" in source
        assert 's != "purge_closed"' not in source, (
            "the selection hard-codes the deleting stage again, so the flag no "
            "longer describes it"
        )
        # The flag is compared against the real selection, not merely read.
        assert "does not match the stage selection" in source
        assert "would run before the arming stage" in source


# ---------------------------------------------------------------- 6
class TestDeletingStageOnlySeesPolicyOutput:
    def test_6_deleting_stage_takes_its_ids_from_the_collector(self):
        source = nested_function_code("do_purge_closed")
        assert "collect(" in source
        assert "delete_exact(" in source
        # And it passes only what the policy marked eligible.
        assert "summary[\"eligible\"]" in source or "eligible_ids" in source
        # No stage-local selection of its own.
        for forbidden in ("CLOSED_STATUSES", "status ==", "is_archived ="):
            assert forbidden not in source, (
                f"do_purge_closed selects records itself ({forbidden!r}); it must "
                "consume the policy's output only"
            )


# ---------------------------------------------------------------- 7-17
@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    from app.models import Base

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


NOW = datetime(2026, 10, 4, 7, 0, tzinfo=timezone.utc)


def closed_row(session, sid, *, days=AUTO_DELETE_AFTER_DAYS + 30, **over):
    from app.models import Scholarship

    archived = NOW - timedelta(days=days)
    fields = dict(
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
    fields.update(over)
    session.add(Scholarship(id=sid, **fields))
    session.commit()


def arm_and_purge(session, archive, ids=None):
    """The real two-stage lifecycle, in the order the scheduler runs them."""
    from app.services.auto_delete_collector import arm, collect, delete_exact
    from app.services.auto_delete_policy import summarise

    decisions = collect(session, now=NOW)
    arm(session, decisions, now=NOW, dry_run=False)
    report = summarise(collect(session, now=NOW))
    return delete_exact(session, ids if ids is not None else report["eligible"],
                        now=NOW, archive_path=archive)


def backdate_grace(session, sid, days=DELETE_GRACE_DAYS):
    from app.models import Scholarship

    row = session.get(Scholarship, sid)
    row.auto_delete_candidate_since = NOW - timedelta(days=days)
    session.commit()


class TestGraceAndPolicyStillGate:
    def test_7_a_newly_armed_record_cannot_be_deleted_in_the_same_cycle(self, factory, tmp_path):
        from app.models import Scholarship

        session = factory()
        try:
            closed_row(session, 1)
            report = arm_and_purge(session, tmp_path / "a.json")
            assert report["deleted"] == [], (
                "a record armed in this cycle was deleted without serving the grace period"
            )
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    @pytest.mark.parametrize("days", [0, 1, 13])
    def test_8_grace_under_fourteen_days_cannot_be_deleted(self, factory, tmp_path, days):
        from app.models import Scholarship

        session = factory()
        try:
            closed_row(session, 1)
            backdate_grace(session, 1, days=days)
            report = arm_and_purge(session, tmp_path / "a.json")
            assert report["deleted"] == []
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    @pytest.mark.parametrize(
        "override",
        [
            {"verification_status": "needs_review"},
            {"verification_status": "active"},
            {"is_public_marker": True},
            {"deletion_protected": True},
            {"is_archived": False, "archived_at": None},
            {"status": "open"},
            {"days": 10},
        ],
    )
    def test_9_any_failed_condition_blocks_even_after_grace(
        self, factory, tmp_path, override
    ):
        from app.models import Scholarship

        session = factory()
        try:
            fields = {k: v for k, v in override.items() if k != "is_public_marker"}
            days = fields.pop("days", AUTO_DELETE_AFTER_DAYS + 30)
            closed_row(session, 1, days=days, **fields)
            if override.get("is_public_marker"):
                # Public visibility is read from the canonical predicate, so the
                # row is made public by keeping it unarchived and active.
                row = session.get(Scholarship, 1)
                row.is_archived = False
                row.status = "open"
                row.verification_status = "active"
                session.commit()
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)
            report = arm_and_purge(session, tmp_path / "a.json")
            assert report["deleted"] == [], f"{override} did not block deletion"
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_10_protected_records_cannot_be_deleted(self, factory, tmp_path):
        from app.models import Scholarship

        session = factory()
        try:
            closed_row(session, 1, deletion_protected=True)
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)
            report = arm_and_purge(session, tmp_path / "a.json")
            assert report["deleted"] == []
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_11_public_records_cannot_be_deleted(self, factory, tmp_path):
        from app.models import Scholarship

        session = factory()
        try:
            closed_row(session, 1, is_archived=False, status="open", verification_status="active")
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)
            report = arm_and_purge(session, tmp_path / "a.json")
            assert report["deleted"] == []
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_12_needs_review_records_cannot_be_deleted(self, factory, tmp_path):
        from app.models import Scholarship

        session = factory()
        try:
            closed_row(session, 1, verification_status="needs_review")
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)
            report = arm_and_purge(session, tmp_path / "a.json")
            assert report["deleted"] == []
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_13_a_concurrent_change_causes_revalidation_to_abort(self, factory, tmp_path):
        from app.models import Scholarship
        from app.services.auto_delete_collector import collect, delete_exact

        session = factory()
        try:
            closed_row(session, 1)
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)
            eligible = [d.id for d in collect(session, now=NOW) if d.verdict == VERDICT_SAFE_DELETE]
            assert eligible == [1], "the fixture is not exercising the eligible path"

            # Something changes the record between selection and deletion.
            row = session.get(Scholarship, 1)
            row.deletion_protected = True
            session.commit()

            report = delete_exact(session, eligible, now=NOW, archive_path=tmp_path / "a.json")
            assert report["deleted"] == []
            assert report["aborted"]
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_14_only_the_named_ids_are_deleted(self, factory, tmp_path):
        from app.models import Scholarship

        session = factory()
        try:
            closed_row(session, 1)
            closed_row(session, 2, deletion_protected=True)
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)
            backdate_grace(session, 2, DELETE_GRACE_DAYS + 5)
            report = arm_and_purge(session, tmp_path / "a.json")
            assert report["deleted"] == [1]
            assert session.get(Scholarship, 1) is None
            assert session.get(Scholarship, 2) is not None, "an ineligible id was deleted"
        finally:
            session.close()

    def test_15_the_manifest_is_written_before_the_delete_commits(self):
        from app.services import auto_delete_collector

        source = inspect.getsource(auto_delete_collector.delete_exact)
        assert source.index("_append_manifest(") < source.index("session.commit()"), (
            "the manifest is written after the delete commits, so a crash in "
            "between leaves rows gone and unaccounted"
        )

    def test_16_a_deletion_failure_rolls_back(self, factory, tmp_path, monkeypatch):
        from app.models import Scholarship
        from app.services import auto_delete_collector

        session = factory()
        try:
            closed_row(session, 1)
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)

            real_commit = type(session).commit

            def explode(self=None):
                raise RuntimeError("commit refused")

            monkeypatch.setattr(
                type(session), "commit", lambda self=None: (_ for _ in ()).throw(RuntimeError("boom"))
            )
            report = auto_delete_collector.delete_exact(
                session, [1], now=NOW, archive_path=tmp_path / "a.json"
            )
            monkeypatch.setattr(type(session), "commit", real_commit)
            assert report.get("error"), "a failed commit was reported as success"
            assert "rolled back" in report["error"]
            session.rollback()
            assert session.get(Scholarship, 1) is not None, "a row survived a rolled-back delete"
        finally:
            session.close()

    def test_17_a_second_run_is_idempotent(self, factory, tmp_path):
        import json

        from app.models import Scholarship

        session = factory()
        try:
            closed_row(session, 1)
            backdate_grace(session, 1, DELETE_GRACE_DAYS + 5)
            first = arm_and_purge(session, tmp_path / "a.json")
            assert first["deleted"] == [1]

            second = arm_and_purge(session, tmp_path / "a.json")
            assert second["deleted"] == []
            assert "NO SAFE DELETE TARGETS" in second["note"]

            doc = json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))
            ids = [r["id"] for b in doc["batches"] for r in b["records"]]
            assert ids == [1], "the same id was recorded as deleted twice"
        finally:
            session.close()

    def test_18_a_stage_error_fails_the_overall_run(self):
        report = worker._run_stage(PURGE, lambda: {"error": "commit refused"})
        assert report.ok is False
        assert report.error


# ------------------------------------------------------- policy unchanged
class TestThePolicyIsUntouchedByActivation:
    def test_retention_and_grace_are_still_the_contracted_values(self):
        assert AUTO_DELETE_AFTER_DAYS == 180
        assert DELETE_GRACE_DAYS == 14

    def test_safe_delete_is_still_structurally_impossible_when_a_check_fails(self):
        # One false check, with everything else satisfied and the grace served.
        decision = __import__(
            "app.services.auto_delete_policy", fromlist=["evaluate"]
        ).evaluate(
            RecordFacts(
                id=1,
                status="closed",
                is_archived=True,
                archived_at=NOW - timedelta(days=400),
                verification_status="retired",
                deadline_date=datetime(2027, 1, 1).date(),  # a future deadline
                dependencies=DependencySummary(counts={}),
            ),
            now=NOW,
            candidate_since=NOW - timedelta(days=40),
        )
        assert decision.verdict != VERDICT_SAFE_DELETE
        assert decision.checks["no_future_deadline"] is False
        assert "no_future_deadline" in decision.blocked_by

    def test_the_deleting_stage_still_named_the_collector_only(self):
        source = nested_function_code("do_purge_closed")
        for forbidden in ("delete(", "session.execute", "DELETE FROM"):
            assert forbidden not in source, (
                f"do_purge_closed reaches {forbidden!r}; deletion belongs to the collector"
            )
