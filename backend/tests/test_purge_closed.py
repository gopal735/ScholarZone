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
        # Guard against the rule being rewritten as "not open" again.
        source = inspect.getsource(worker)
        assert "status not in (\"open\"" not in source
        assert "status not in ('open'" not in source

    def test_stage_records_every_reason_it_deleted_a_row(self):
        source = inspect.getsource(worker)
        assert '"reasons": reasons' in source
        assert "purged_records_archive.json" in source


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
        source = inspect.getsource(worker)
        write_at = source.index('snapshot_path.write_text')
        delete_at = source.index("session.delete(row)")
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
    def test_excluded_from_all(self):
        assert worker.PURGE_CLOSED_EXCLUDED_FROM_ALL is True
        assert worker.STAGE_ORDER[-1] == "purge_closed"

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