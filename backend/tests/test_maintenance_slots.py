"""Phase A core: deterministic slot identity and the slot state machine.

Isolated by construction: this suite imports one pure module, opens no database
engine, and never reads the repository's ambient ``backend/scholarzone.db``.
Every timestamp is injected, so nothing here can pass or fail depending on the
wall clock or on test ordering.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.maintenance_slots import (
    InvalidTransition,
    LogicalSource,
    SLOT_ID_RE,
    SlotState,
    due_at_from_slot_id,
    is_legal_transition,
    latest_due_slot,
    slot_id,
    validate_transition,
)

BACKEND = Path(__file__).resolve().parents[1]
AMBIENT_DB = BACKEND / "scholarzone.db"


def utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def test_no_ambient_database_is_created_or_touched():
    """The scheduler suite must be blind to the repository's dev database."""
    assert not AMBIENT_DB.exists(), (
        "ambient backend/scholarzone.db must not exist for these tests to be "
        "meaningful; if it exists, these results are not trustworthy"
    )


class TestSlotIdentity:
    @pytest.mark.parametrize(
        "due,expected",
        [
            ("2026-10-04T00:07:00Z", "maintenance:2026-10-04T00:07:00Z"),
            ("2026-10-04T12:07:00Z", "maintenance:2026-10-04T12:07:00Z"),
        ],
    )
    def test_canonical_form(self, due, expected):
        assert slot_id(utc(due)) == expected

    def test_identity_is_stable_across_repeated_calculation(self):
        """The same logical slot always yields the same id."""
        moment = utc("2026-10-04T12:07:00Z")
        assert len({slot_id(moment) for _ in range(20)}) == 1

    def test_round_trip(self):
        moment = utc("2026-02-28T00:07:00Z")
        assert due_at_from_slot_id(slot_id(moment)) == moment

    def test_naive_datetime_is_rejected(self):
        with pytest.raises(ValueError, match="UTC-only"):
            slot_id(datetime(2026, 10, 4, 0, 7))

    def test_non_utc_input_is_normalised_not_rejected(self):
        """An offset-aware instant is converted, so 12:07Z == 12:07+02:00."""
        offset = datetime(
            2026, 10, 4, 14, 7, tzinfo=timezone(__import__("datetime").timedelta(hours=2))
        )
        assert slot_id(offset) == "maintenance:2026-10-04T12:07:00Z"


class TestLatestDueSlot:
    @pytest.mark.parametrize(
        "as_of,expected",
        [
            # just before the first slot -> previous day's 12:07
            ("2026-10-04T00:06:00Z", "maintenance:2026-10-03T12:07:00Z"),
            ("2026-10-04T00:07:00Z", "maintenance:2026-10-04T00:07:00Z"),
            ("2026-10-04T00:08:00Z", "maintenance:2026-10-04T00:07:00Z"),
            ("2026-10-04T12:06:00Z", "maintenance:2026-10-04T00:07:00Z"),
            ("2026-10-04T12:07:00Z", "maintenance:2026-10-04T12:07:00Z"),
            ("2026-10-04T12:08:00Z", "maintenance:2026-10-04T12:07:00Z"),
            # 13:00 must NOT invent a 13:07 slot
            ("2026-10-04T13:00:00Z", "maintenance:2026-10-04T12:07:00Z"),
            # month boundary
            ("2026-11-01T00:06:00Z", "maintenance:2026-10-31T12:07:00Z"),
            # year boundary
            ("2027-01-01T00:06:00Z", "maintenance:2026-12-31T12:07:00Z"),
            # leap day
            ("2028-02-29T12:07:00Z", "maintenance:2028-02-29T12:07:00Z"),
            ("2028-03-01T00:06:00Z", "maintenance:2028-02-29T12:07:00Z"),
        ],
    )
    def test_boundaries(self, as_of, expected):
        assert slot_id(latest_due_slot(utc(as_of))) == expected

    def test_result_is_always_a_valid_slot_id(self):
        for text in (
            "2026-10-04T00:07:00Z",
            "2026-10-04T13:00:00Z",
            "2027-01-01T00:00:00Z",
            "2028-02-29T23:59:00Z",
        ):
            assert SLOT_ID_RE.match(slot_id(latest_due_slot(utc(text))))

    def test_repeated_calls_are_identical(self):
        moment = utc("2026-10-04T13:00:00Z")
        assert len({slot_id(latest_due_slot(moment)) for _ in range(20)}) == 1


class TestStateMachine:
    @pytest.mark.parametrize(
        "current,target",
        [
            (SlotState.DUE, SlotState.CLAIMED),
            (SlotState.CLAIMED, SlotState.DISPATCHED),
            (SlotState.CLAIMED, SlotState.EXPIRED),
            (SlotState.DISPATCHED, SlotState.RUNNING),
            (SlotState.RUNNING, SlotState.SUCCEEDED),
            (SlotState.RUNNING, SlotState.FAILED),
            (SlotState.EXPIRED, SlotState.CLAIMED),
        ],
    )
    def test_legal_transitions(self, current, target):
        assert is_legal_transition(current, target)
        validate_transition(current, target)

    @pytest.mark.parametrize(
        "current,target",
        [
            (SlotState.DUE, SlotState.SUCCEEDED),
            (SlotState.DUE, SlotState.RUNNING),
            (SlotState.DUE, SlotState.DISPATCHED),
            (SlotState.SUCCEEDED, SlotState.RUNNING),
            (SlotState.SUCCEEDED, SlotState.CLAIMED),
            (SlotState.FAILED, SlotState.RUNNING),
            (SlotState.FAILED, SlotState.CLAIMED),
            (SlotState.EXPIRED, SlotState.SUCCEEDED),
            (SlotState.EXPIRED, SlotState.RUNNING),
            (SlotState.RUNNING, SlotState.CLAIMED),
        ],
    )
    def test_illegal_transitions_are_refused(self, current, target):
        assert not is_legal_transition(current, target)
        with pytest.raises(InvalidTransition):
            validate_transition(current, target)

    def test_terminal_states_have_no_exits(self):
        """A finished slot must never silently revert to DUE."""
        for terminal in (SlotState.SUCCEEDED, SlotState.FAILED):
            for target in SlotState:
                if target is terminal:
                    continue
                assert not is_legal_transition(terminal, target), f"{terminal}->{target}"

    def test_no_op_is_not_a_transition(self):
        with pytest.raises(InvalidTransition, match="no-op"):
            validate_transition(SlotState.DUE, SlotState.DUE)

    def test_every_state_is_reachable_from_due(self):
        seen, frontier = set(), [SlotState.DUE]
        while frontier:
            current = frontier.pop()
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(LEGAL := [t for t in SlotState if is_legal_transition(current, t)])
        assert seen == set(SlotState)


class TestSourceAttribution:
    def test_external_dispatch_is_not_a_github_schedule(self):
        """Transport and logical origin must stay separable."""
        assert (
            LogicalSource.EXTERNAL_SCHEDULER_DISPATCH
            != LogicalSource.GITHUB_SCHEDULE
        )
        assert LogicalSource("external_scheduler_dispatch").value == (
            "external_scheduler_dispatch"
        )

    def test_all_required_sources_exist(self):
        names = {source.value for source in LogicalSource}
        assert names == {
            "github_schedule",
            "external_scheduler_dispatch",
            "workflow_dispatch",
            "watchdog",
            "manual",
        }


def test_ambient_database_still_absent_after_suite():
    assert not AMBIENT_DB.exists(), "the slot core must never create the dev database"