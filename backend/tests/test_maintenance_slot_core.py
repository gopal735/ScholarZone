"""Durable maintenance slot core: the invariants, proven.

Isolation is part of the contract. Every test uses an isolated SQLite file
created under ``tmp_path`` and asserts the repository's ambient
``backend/scholarzone.db`` is neither read nor created, because a previous
audit found release-relevant tests silently depending on it.

No test reads the wall clock: ``as_of`` is always injected, so slot identity and
state decisions are deterministic at midnight, month, year and leap-day
boundaries.
"""
from __future__ import annotations

import datetime as dt
import os
import threading
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
AMBIENT = BACKEND / "scholarzone.db"
UTC = dt.timezone.utc


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    """An isolated database per test, never the ambient development one."""
    was_present = AMBIENT.exists()
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "SCHOLARZONE_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'slot.db').as_posix()}",
    )
    import importlib

    import app.database as database

    importlib.reload(database)
    database.init_database()
    yield database.get_session_factory()
    assert AMBIENT.exists() is was_present, (
        "a scheduler test created or removed the ambient backend/scholarzone.db"
    )


def at(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


class TestUtcSlotIdentity:
    @pytest.mark.parametrize(
        "moment,expected",
        [
            ("2026-10-04T00:07:00", "maint-slot-20261004T0007Z"),
            ("2026-10-04T12:07:00", "maint-slot-20261004T1207Z"),
            ("2026-10-04T13:00:00", "maint-slot-20261004T1207Z"),
            ("2026-10-04T00:06:00", "maint-slot-20261003T1207Z"),
            ("2026-10-04T00:08:00", "maint-slot-20261004T0007Z"),
            ("2026-10-04T12:06:00", "maint-slot-20261004T0007Z"),
            ("2026-10-04T12:08:00", "maint-slot-20261004T1207Z"),
            ("2024-02-29T12:07:00", "maint-slot-20240229T1207Z"),
            ("2026-01-01T00:07:00", "maint-slot-20260101T0007Z"),
            ("2025-12-31T23:59:00", "maint-slot-20251231T1207Z"),
        ],
    )
    def test_known_moments_map_to_exact_slots(self, factory, moment, expected):
        from app.services.maintenance_slot import slot_due_at, slot_id_for

        when = at(moment)
        # The slot id is the contract. The due instant is the most recent slot at
        # or before `moment`, which equals `moment` only on an exact boundary -
        # so it is asserted separately below.
        assert slot_id_for(when) == expected

    @pytest.mark.parametrize("moment", ["2026-10-04T00:07:00", "2026-10-04T12:07:00"])
    def test_on_an_exact_boundary_the_due_instant_is_that_boundary(
        self, factory, moment
    ):
        from app.services.maintenance_slot import slot_due_at

        when = at(moment)
        assert slot_due_at(when).replace(tzinfo=None).isoformat() == moment

    def test_same_slot_repeated_computation_is_identical(self, factory):
        from app.services.maintenance_slot import slot_id_for

        when = at("2026-10-04T13:00:00")
        assert len({slot_id_for(when) for _ in range(50)}) == 1

    def test_a_late_request_identifies_the_original_slot(self, factory):
        from app.services.maintenance_slot import slot_id_for

        assert slot_id_for(at("2026-10-04T12:40:00")) == slot_id_for(at("2026-10-04T12:07:00"))

    def test_naive_timestamps_are_refused(self, factory):
        from app.services.maintenance_slot import slot_due_at

        with pytest.raises(ValueError):
            slot_due_at(dt.datetime(2026, 10, 4, 12, 7))

    def test_non_utc_input_is_normalised_by_instant(self, factory):
        from app.services.maintenance_slot import slot_id_for

        eastern = dt.timezone(dt.timedelta(hours=-4))
        aware = dt.datetime(2026, 10, 4, 8, 7, tzinfo=eastern)  # == 12:07Z
        assert slot_id_for(aware) == "maint-slot-20261004T1207Z"


class TestStateMachine:
    @pytest.mark.parametrize(
        "current,target",
        [
            ("DUE", "CLAIMED"),
            ("CLAIMED", "DISPATCHED"),
            ("CLAIMED", "EXPIRED"),
            ("EXPIRED", "CLAIMED"),
            ("DISPATCHED", "RUNNING"),
            ("DISPATCHED", "FAILED"),
            ("RUNNING", "SUCCEEDED"),
            ("RUNNING", "FAILED"),
        ],
    )
    def test_legal_transitions_are_permitted(self, factory, current, target):
        from app.services.maintenance_slot import can_transition

        assert can_transition(current, target) is True

    @pytest.mark.parametrize(
        "current,target",
        [
            ("SUCCEEDED", "RUNNING"), ("SUCCEEDED", "CLAIMED"),
            ("FAILED", "RUNNING"), ("FAILED", "CLAIMED"),
            ("EXPIRED", "SUCCEEDED"), ("EXPIRED", "RUNNING"),
            ("DUE", "SUCCEEDED"), ("DUE", "RUNNING"),
            ("DUE", "DISPATCHED"), ("DUE", "FAILED"),
            ("RUNNING", "CLAIMED"), ("RUNNING", "DISPATCHED"),
            ("CLAIMED", "SUCCEEDED"), ("CLAIMED", "RUNNING"),
            ("SUCCEEDED", "SUCCEEDED"), ("DUE", "DUE"),
        ],
    )
    def test_illegal_transitions_are_refused(self, factory, current, target):
        from app.services.maintenance_slot import IllegalTransition, require_transition

        with pytest.raises(IllegalTransition):
            require_transition(current, target)

    def test_unknown_states_are_not_transitionable(self, factory):
        from app.services.maintenance_slot import can_transition

        assert can_transition("NONSENSE", "CLAIMED") is False
        assert can_transition("DUE", "NONSENSE") is False


class TestAtomicClaim:
    def test_first_claim_wins_and_second_is_refused(self, factory):
        from app.services.maintenance_slot import active_claim_count, claim_slot

        when = at("2026-10-04T12:07:00")
        first = claim_slot(factory, when, "owner-A")
        second = claim_slot(factory, when, "owner-B")
        assert first.claimed is True
        assert second.claimed is False
        assert second.reason == "lease-active"
        assert active_claim_count(factory, first.slot_id) == 1

    def test_concurrent_contenders_produce_exactly_one_owner(self, factory):
        """Threads race on the same slot; the unique index decides."""
        from app.services.maintenance_slot import active_claim_count, claim_slot

        when = at("2026-10-04T12:07:00")
        results = []
        lock = threading.Lock()

        def contend(index: int) -> None:
            outcome = claim_slot(factory, when, f"owner-{index}")
            with lock:
                results.append(outcome)

        threads = [threading.Thread(target=contend, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        winners = [r for r in results if r.claimed]
        assert len(winners) == 1, f"expected exactly one winner, got {len(winners)}"
        assert active_claim_count(factory, winners[0].slot_id) == 1

    def test_repeated_claim_by_the_same_owner_is_idempotent(self, factory):
        from app.services.maintenance_slot import claim_slot

        when = at("2026-10-04T12:07:00")
        first = claim_slot(factory, when, "owner-A")
        again = claim_slot(factory, when, "owner-A")
        assert first.claimed is True and again.claimed is True
        assert again.reason == "already-claimed-by-owner"

    def test_get_or_create_is_idempotent(self, factory):
        from app.services.maintenance_slot import get_or_create_slot, slot_id_for

        when = at("2026-10-04T12:07:00")
        first, created_first = get_or_create_slot(factory, when)
        second, created_second = get_or_create_slot(factory, when)
        assert created_first is True and created_second is False
        assert first.slot_id == second.slot_id == slot_id_for(when)


class TestLeaseAndRecovery:
    def test_an_active_lease_cannot_be_stolen(self, factory):
        from app.services.maintenance_slot import claim_slot

        when = at("2026-10-04T12:07:00")
        assert claim_slot(factory, when, "A", lease_seconds=3600).claimed is True
        steal = claim_slot(factory, when, "B", lease_seconds=3600)
        assert steal.claimed is False and steal.reason == "lease-active"

    def test_an_expired_lease_is_recoverable_and_recorded_as_expired(self, factory):
        from app.services.maintenance_slot import (
            EXPIRED,
            claim_slot,
            expire_stale_claims,
            slot_state,
        )

        when = at("2026-10-04T12:07:00")
        first = claim_slot(factory, when, "A", lease_seconds=60)
        later = when + dt.timedelta(seconds=120)
        expired = expire_stale_claims(factory, now=later)
        assert first.slot_id in expired
        assert slot_state(factory, first.slot_id) == EXPIRED

        recovered = claim_slot(factory, later, "B", lease_seconds=60)
        assert recovered.claimed is True
        assert recovered.state == "CLAIMED"

    def test_two_recovery_attempts_after_expiry_yield_one_owner(self, factory):
        from app.services.maintenance_slot import (
            claim_slot,
            expire_stale_claims,
            slot_state,
        )

        when = at("2026-10-04T12:07:00")
        claim_slot(factory, when, "A", lease_seconds=60)
        later = when + dt.timedelta(seconds=300)
        expire_stale_claims(factory, now=later)
        first = claim_slot(factory, later, "B", lease_seconds=300)
        second = claim_slot(factory, later, "C", lease_seconds=300)
        assert first.claimed is True
        assert second.claimed is False
        assert slot_state(factory, first.slot_id) == "CLAIMED"

    def test_a_running_slot_is_not_reclaimable(self, factory):
        from app.services.maintenance_slot import advance, claim_slot

        when = at("2026-10-04T12:07:00")
        claimed = claim_slot(factory, when, "A", lease_seconds=3600)
        advance(factory, claimed.slot_id, "DISPATCHED")
        advance(factory, claimed.slot_id, "RUNNING", now=when)
        again = claim_slot(factory, when, "B", lease_seconds=3600)
        assert again.claimed is False
        assert again.reason == "slot-already-running"

    def test_a_succeeded_slot_is_terminal(self, factory):
        from app.services.maintenance_slot import SUCCEEDED, advance, claim_slot

        when = at("2026-10-04T12:07:00")
        claimed = claim_slot(factory, when, "A", lease_seconds=3600)
        advance(factory, claimed.slot_id, "DISPATCHED")
        advance(factory, claimed.slot_id, "RUNNING", now=when)
        advance(factory, claimed.slot_id, SUCCEEDED, now=when)
        again = claim_slot(factory, when, "B", lease_seconds=3600)
        assert again.claimed is False
        assert again.reason == f"slot-terminal-{SUCCEEDED}"


class TestSourceAttribution:
    def test_a_schedule_trigger_is_github_schedule(self, factory):
        from app.services.maintenance_slot import GITHUB_SCHEDULE, get_or_create_slot

        row, _ = get_or_create_slot(
            factory, at("2026-10-04T12:07:00"), transport_event="schedule"
        )
        assert row.logical_source == GITHUB_SCHEDULE

    def test_an_explicit_external_source_survives_a_workflow_dispatch_transport(self, factory):
        """A Vercel-triggered run arrives as workflow_dispatch; its logical
        origin is an external scheduler and must not be flattened."""
        from app.services.maintenance_slot import (
            EXTERNAL_SCHEDULER_DISPATCH,
            get_or_create_slot,
        )

        row, _ = get_or_create_slot(
            factory,
            at("2026-10-04T12:07:00"),
            logical_source=EXTERNAL_SCHEDULER_DISPATCH,
            transport_event="workflow_dispatch",
        )
        assert row.logical_source == EXTERNAL_SCHEDULER_DISPATCH
        assert row.transport_event == "workflow_dispatch"

    def test_manual_remains_distinguishable(self, factory):
        from app.services.maintenance_slot import MANUAL, get_or_create_slot

        row, _ = get_or_create_slot(
            factory, at("2026-10-04T12:07:00"), logical_source=MANUAL
        )
        assert row.logical_source == MANUAL

    def test_an_unknown_source_is_refused(self, factory):
        from app.services.maintenance_slot import resolve_logical_source

        with pytest.raises(ValueError):
            resolve_logical_source("something_else", "schedule")


class TestDeterminismAndIsolation:
    def test_repeated_identical_calls_are_identical(self, factory):
        from app.services.maintenance_slot import slot_id_for

        when = at("2026-10-04T12:07:00")
        assert len({slot_id_for(when) for _ in range(20)}) == 1

    def test_the_ambient_database_is_never_created(self, factory):
        assert not AMBIENT.exists()

    def test_the_schedule_is_described_as_the_existing_cron(self, factory):
        from app.services.maintenance_slot import describe_schedule

        described = describe_schedule()  # returns a string, not an iterable of parts
        assert "00:07Z" in described and "12:07Z" in described
