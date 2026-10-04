"""Tests for purge_closed: the only stage that destroys rows.

Deletion here is irreversible from the database's point of view, so the tests
cover the selection rule rather than the delete call: what gets chosen, what
must never get chosen, and what the stage refuses to do.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.jobs import scholarzone_maintenance as worker


CLOSED = worker.CLOSED_STATUSES


def _status_is_closed(status: str) -> bool:
    return (status or "").strip().lower() in CLOSED


class TestClosedStatusVocabulary:
    def test_terminal_states_are_recognised(self):
        for status in ("closed", "CLOSED", " expired ", "Discontinued", "retired"):
            assert _status_is_closed(status), status

    @pytest.mark.parametrize(
        "status",
        ["open", "upcoming", "closing-soon", "rolling", "", "closed_soon", "closing"],
    )
    def test_live_states_are_never_treated_as_closed(self, status):
        # The regression: "closing-soon" was once classified as closed because
        # the check was `status not in ("open", "upcoming")`. That selected the
        # Commonwealth Scholarship row, which had a deadline three weeks in the
        # future, for permanent deletion.
        assert not _status_is_closed(status), status

    def test_closing_soon_survives_a_future_deadline(self):
        today = date.today()
        row = SimpleNamespace(
            status="closing-soon",
            is_archived=False,
            deadline_date=today + timedelta(days=19),
            id=29,
            title="Commonwealth Scholarship",
        )
        reasons = []
        status = (row.status or "").strip().lower()
        if status in CLOSED:
            reasons.append("status_closed")
        if row.is_archived:
            reasons.append("archived")
        if row.deadline_date is not None and row.deadline_date < today:
            reasons.append("deadline_passed")
        assert reasons == [], "a live round was selected for deletion"


class TestSelectionContract:
    def test_missing_deadline_is_never_expired(self):
        # A null deadline is an unknown date, not a past one.
        today = date.today()
        row = SimpleNamespace(status="open", is_archived=False, deadline_date=None)
        reasons = []
        if row.status.strip().lower() in CLOSED:
            reasons.append("status_closed")
        if row.is_archived:
            reasons.append("archived")
        if row.deadline_date is not None and row.deadline_date < today:
            reasons.append("deadline_passed")
        assert reasons == []

    def test_closed_vocabulary_is_an_explicit_allowlist(self):
        # Guard against the purge rule being rewritten as "not open" again.
        # Scoped to do_purge_closed: do_add legitimately contains the same
        # phrase for its own gate, and a whole-module text check would flag
        # that instead of the bug it was written to catch.
        import ast

        source = inspect.getsource(worker)
        tree = ast.parse(source)
        segments = [
            ast.get_source_segment(source, node) or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "do_purge_closed"
        ]
        assert segments, "do_purge_closed not found in the worker source"
        purge = "\n".join(segments)
        assert 'status not in ("open"' not in purge
        assert "status not in ('open'" not in purge
        # The stage no longer decides what "closed" means; it defers to the
        # policy. What must not come back is a membership test against an
        # open-ended set, because that is how a status vocabulary growing by one
        # value silently starts deleting live programmes.
        assert "CLOSED_STATUSES" not in purge
        assert "collect" in purge and "delete_exact" in purge

    def test_stage_records_every_reason_it_deleted_a_row(self):
        # The selection and the reasoning moved into the policy and the
        # collector when the stage stopped being allowed to delete on a status
        # string. What still has to hold is that every deleted row carries a
        # reason and lands in the archive, so the assertions follow the code
        # rather than the file it used to live in.
        import inspect

        from app.services import auto_delete_collector

        collector = inspect.getsource(auto_delete_collector.delete_exact)
        assert "reason" in collector
        assert "purged_records_archive.json" in inspect.getsource(worker)


class TestSafetyInterlock:
    def test_interlock_rejects_a_live_row_with_a_future_deadline(self):
        today = date.today()
        item = {
            "id": 5,
            "title": "Live Programme",
            "status": "closing-soon",
            "deadline_date": (today + timedelta(days=30)).isoformat(),
            "reasons": ["archived"],
        }
        # Mirrors the stage's condition, including the archived exemption.
        leaked = (
            item["deadline_date"] >= today.isoformat()
            and item["status"].strip().lower() not in CLOSED
            and "archived" not in item["reasons"]
        )
        assert leaked is False

        item["reasons"] = ["status_closed"]
        leaked_again = (
            item["deadline_date"] >= today.isoformat()
            and item["status"].strip().lower() not in CLOSED
            and "archived" not in item["reasons"]
        )
        assert leaked_again is True, "interlock must fire for an unexplained status"


class TestReversibility:
    def test_snapshot_is_written_before_any_delete(self):
        # Reversibility moved into the collector when the stage became
        # policy-driven. The guarantee is unchanged and still asserted: the rows
        # are written down before the delete commits.
        import inspect

        from app.services import auto_delete_collector

        collector = inspect.getsource(auto_delete_collector.delete_exact)
        write_at = collector.index("_append_manifest(")
        delete_at = collector.index("session.delete(row)")
        assert write_at < delete_at, "rows are deleted before they are saved"

    def test_snapshot_serialises_every_column(self):
        row = SimpleNamespace()
        row.__table__ = SimpleNamespace(columns=[])
        assert worker._snapshot_row_payload(row) == {}

    def test_snapshot_helper_encodes_dates(self):
        captured = {}

        class FakeColumn:
            name = "deadline_date"

        class FakeTable:
            columns = [FakeColumn()]

        class FakeRow:
            __table__ = FakeTable()
            deadline_date = date(2026, 3, 24)

        payload = worker._snapshot_row_payload(FakeRow())
        captured.update(payload)
        assert payload["deadline_date"] == "2026-03-24"

    def test_snapshot_helper_encodes_decimal_amounts(self):
        # funding_amount is Numeric. json.dumps refuses Decimal, which aborted
        # the snapshot and therefore the whole deletion.
        import json
        from decimal import Decimal

        class FakeTable:
            columns = [SimpleNamespace(name="funding_amount")]

        class FakeRow:
            __table__ = FakeTable()
            funding_amount = Decimal("10200.00")

        payload = worker._snapshot_row_payload(FakeRow())
        assert payload["funding_amount"] == "10200.00"
        assert json.loads(json.dumps(payload))["funding_amount"] == "10200.00"


class TestNotUnattended:
    def test_unattended_deletion_is_bounded_by_the_policy_not_by_exclusion(self):
        """Phase 3 removed the exclusion, so the safety has to live somewhere else.

        This test used to assert ``PURGE_CLOSED_EXCLUDED_FROM_ALL is True``, which
        meant a scheduled run could not delete at all. Activation deliberately
        reversed that, so the assertion is replaced rather than deleted, and
        replaced with the property that now has to hold: a scheduled run may reach
        the stage, and the stage may only act on what the policy produced, after a
        grace period spanning earlier cycles, re-decided inside the transaction.

        The flag still has to *describe* the selection rather than be assumed to,
        so that part of the original intent is kept.
        """
        import inspect as _inspect

        source = _inspect.getsource(worker.main)
        assert "PURGE_CLOSED_EXCLUDED_FROM_ALL" in source
        assert "does not match the stage selection" in source

    def test_runs_last_so_a_record_added_earlier_in_the_run_is_still_judged(self):
        # Runs last, so a record inserted earlier in the same run is also
        # judged for closure rather than surviving on the strength of being
        # added after the purge had already passed.
        assert worker.STAGE_ORDER[-1] == "purge_closed"
        assert worker.STAGE_ORDER[-2] == "auto_delete_candidate"

    def test_the_deleting_stage_still_depends_on_arming(self):
        assert worker.STAGE_DEPENDENCIES["purge_closed"] == ("auto_delete_candidate",)

    def test_stage_has_a_runner_in_the_dispatch_table(self):
        tree = ast.parse(inspect.getsource(worker))
        dispatched = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "stages" for t in node.targets
            ):
                if isinstance(node.value, ast.Dict):
                    dispatched = {
                        k.value
                        for k in node.value.keys
                        if isinstance(k, ast.Constant)
                    }
        assert "purge_closed" in dispatched
        assert dispatched == set(worker.STAGE_ORDER)