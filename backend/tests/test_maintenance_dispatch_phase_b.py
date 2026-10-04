"""Phase B: dispatch integration, provider-mocked and fully isolated.

Every provider interaction is a deterministic fake. There is no real GitHub
call, no real Vercel mutation, no Neon write, and no reliance on the ambient
``backend/scholarzone.db`` - the isolation defect an earlier audit found.

The fake token is a literal in this file precisely because it is a fake: the
real credential is read only from the environment at call time and is never
logged, returned, or placed in a URL.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
AMBIENT = BACKEND / "scholarzone.db"
UTC = dt.timezone.utc
FAKE_TOKEN = "test-token-not-a-real-credential"
SECRET = "test-cron-secret"


def at(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    was_present = AMBIENT.exists()
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL",
                       f"sqlite:///{(tmp_path / 'phaseb.db').as_posix()}")
    # The dispatcher reads exactly this variable name (TOKEN_ENV). The fake
    # value lives only here; the real credential is never in a fixture.
    monkeypatch.setenv("GITHUB_ACTIONS_DISPATCH_TOKEN", FAKE_TOKEN)
    import importlib

    import app.database as database

    importlib.reload(database)
    database.init_database()
    yield database.get_session_factory()
    assert AMBIENT.exists() is was_present, "a test touched the ambient database"


@pytest.fixture()
def client(factory):
    """The app, rebound to the reloaded database engine.

    `factory` reloads app.database so the isolated engine is active; app.main
    captured `get_engine` at import time, so it is re-imported here rather than
    served from a stale module reference.
    """
    import importlib

    import app.main as main

    importlib.reload(main)
    from fastapi.testclient import TestClient

    return TestClient(main.app)


def fake_transport(status: int, payload: dict | None = None):
    """A deterministic stand-in for the GitHub dispatch endpoint."""

    def call(url, token, body, timeout):
        calls.append({"url": url, "token": token, "body": body})
        return status, (payload or {})

    calls: list[dict] = []
    call.calls = calls
    return call


# -- Part 8/23: authentication ------------------------------------------------


class TestCronAuthentication:
    def test_valid_cron_auth_reaches_the_dispatcher(self, client, factory, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", SECRET)
        monkeypatch.setenv("GITHUB_ACTIONS_DISPATCH_TOKEN", FAKE_TOKEN)
        response = client.post("/internal/maintenance/dispatch",
                               headers={"Authorization": f"Bearer {SECRET}"})
        assert response.status_code == 200
        assert "dispatched" in response.json()

    def test_missing_auth_is_not_discoverable(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", SECRET)
        assert client.post("/internal/maintenance/dispatch").status_code == 404

    def test_invalid_auth_is_refused(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", SECRET)
        response = client.post("/internal/maintenance/dispatch",
                               headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 404

    def test_a_public_arbitrary_caller_cannot_dispatch(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", SECRET)
        monkeypatch.setenv("GITHUB_ACTIONS_DISPATCH_TOKEN", FAKE_TOKEN)
        assert client.get("/internal/maintenance/dispatch").status_code == 405
        assert client.post("/internal/maintenance/dispatch").status_code == 404

    def test_without_a_secret_nothing_is_authorised(self, client, monkeypatch):
        monkeypatch.delenv("CRON_SECRET", raising=False)
        assert client.post("/internal/maintenance/dispatch",
                           headers={"Authorization": "Bearer anything"}).status_code == 404

    def test_missing_dispatch_token_is_configuration_blocked(self, factory, monkeypatch):
        from app.services.maintenance_dispatch import (
            CONFIGURATION_BLOCKED,
            dispatch_workflow,
        )

        monkeypatch.delenv("SCHOLARZONE_DISPATCH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS_DISPATCH_TOKEN", raising=False)
        outcome = dispatch_workflow(slot_id="maint-slot-20261004T1207Z", dispatch_id="d1")
        assert outcome.accepted is False
        assert outcome.classification == CONFIGURATION_BLOCKED
        assert FAKE_TOKEN not in json.dumps(outcome.__dict__)

    def test_the_token_is_never_returned_or_url_born(self, factory, monkeypatch):
        from app.services.maintenance_dispatch import dispatch_workflow

        transport = fake_transport(204)
        outcome = dispatch_workflow(
            slot_id="maint-slot-20261004T1207Z", dispatch_id="d1", transport=transport
        )
        assert outcome.accepted is True
        assert FAKE_TOKEN not in json.dumps(outcome.__dict__)
        assert FAKE_TOKEN not in transport.calls[0]["url"]
        assert transport.calls[0]["token"] == FAKE_TOKEN


# -- Part 24: source attribution ---------------------------------------------


class TestSourceAttribution:
    def test_external_dispatch_is_not_recorded_as_a_schedule_event(self, factory):
        from app.services.maintenance_dispatch import (
            EXTERNAL_SCHEDULER_DISPATCH,
            run_backstop_once,
        )
        from app.services.maintenance_slot import GITHUB_SCHEDULE, slot_state

        transport = fake_transport(204)
        report = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=transport
        )
        assert report.dispatched, "a missed slot should have been dispatched"
        from app.models import MaintenanceRun

        session = factory()
        rows = session.query(MaintenanceRun).filter(
            MaintenanceRun.slot_id == report.dispatched[0]).all()
        assert rows[0].logical_source == EXTERNAL_SCHEDULER_DISPATCH
        assert rows[0].logical_source != GITHUB_SCHEDULE
        assert rows[0].transport_event == "workflow_dispatch"
        session.close()

    def test_a_schedule_run_stays_a_schedule_run(self, factory):
        from app.services.maintenance_slot import (
            GITHUB_SCHEDULE,
            get_or_create_slot,
        )

        row, _ = get_or_create_slot(
            factory, at("2026-10-04T12:07:00"), transport_event="schedule"
        )
        assert row.logical_source == GITHUB_SCHEDULE

    def test_worker_maps_event_and_source_independently(self, factory, monkeypatch):
        """The worker's mapping is the integration point that must not collapse
        workflow_dispatch into a schedule or manual origin."""
        from app.jobs.scholarzone_maintenance import _slot_metadata

        monkeypatch.setenv("SCHOLARZONE_TRANSPORT_EVENT", "workflow_dispatch")
        monkeypatch.setenv("SCHOLARZONE_LOGICAL_SOURCE", "external_scheduler_dispatch")
        monkeypatch.setenv("SCHOLARZONE_SLOT_ID", "maint-slot-20261004T1207Z")
        meta = _slot_metadata()
        assert meta["logical_source"] == "external_scheduler_dispatch"
        assert meta["transport_event"] == "workflow_dispatch"
        assert meta["slot_id"] == "maint-slot-20261004T1207Z"

        # With no explicit origin a bare workflow_dispatch must NOT collapse to
        # a GitHub schedule event; an explicit manual request stays manual.
        monkeypatch.delenv("SCHOLARZONE_LOGICAL_SOURCE")
        meta = _slot_metadata()
        assert meta["logical_source"] != "github_schedule"
        monkeypatch.setenv("SCHOLARZONE_LOGICAL_SOURCE", "manual")
        assert _slot_metadata()["logical_source"] == "manual"


# -- Parts 11, 25, 26: missed slot, duplicate dispatch -----------------------


class TestMissedSlotRecovery:
    def test_a_due_slot_with_no_run_is_claimed_and_dispatched(self, factory):
        from app.services.maintenance_dispatch import run_backstop_once
        from app.services.maintenance_slot import DISPATCHED, slot_state

        transport = fake_transport(204)
        report = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=transport
        )
        assert report.claimed and report.dispatched
        assert slot_state(factory, report.dispatched[0]) == DISPATCHED
        body = transport.calls[0]["body"]
        assert body["inputs"]["logical_source"] == "external_scheduler_dispatch"
        assert body["inputs"]["slot_id"] == report.dispatched[0]
        assert "dispatch_id" in body["inputs"]
        # repository / workflow / ref are server-controlled
        assert "gopal735/ScholarZone" in transport.calls[0]["url"]
        assert body["ref"] == "master"

    def test_running_the_backstop_twice_dispatches_once(self, factory):
        from app.services.maintenance_dispatch import run_backstop_once
        from app.services.maintenance_slot import DISPATCHED, slot_state

        transport = fake_transport(204)
        first = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=transport
        )
        second = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=transport
        )
        # Catch-up is bounded and may legitimately dispatch several recent
        # slots; the contract is that the SECOND pass adds nothing.
        assert first.dispatched
        assert second.dispatched == []
        assert second.claimed == []
        assert len(transport.calls) == len(first.dispatched)
        for slot in first.dispatched:
            assert slot_state(factory, slot) == DISPATCHED

    def test_duplicate_is_prevented_rather_than_reported_as_failure(self, factory):
        from app.services.maintenance_dispatch import (
            PREVENTED_DUPLICATE,
            claim_slot,
            run_backstop_once,
        )

        claim = claim_slot(factory, at("2026-10-04T12:07:00"), "github-schedule",
                           lease_seconds=900)
        transport = fake_transport(204)
        report = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=transport
        )
        # The slot the schedule already owns must be prevented, and must never
        # be dispatched a second time.
        assert claim.slot_id in report.prevented_duplicates
        assert report.classifications[claim.slot_id] == PREVENTED_DUPLICATE
        assert claim.slot_id not in report.dispatched
        assert all(
            call["body"]["inputs"]["slot_id"] != claim.slot_id
            for call in transport.calls
        )


# -- Part 13/27: the real race ----------------------------------------------


class TestScheduleVersusBackstopRace:
    def test_one_winner_when_both_paths_target_the_same_slot(self, factory):
        from app.services.maintenance_dispatch import run_backstop_once
        from app.services.maintenance_slot import claim_slot

        transport = fake_transport(204)
        when = at("2026-10-04T12:07:00")
        outcomes: list[dict] = []
        lock = threading.Lock()

        def from_schedule():
            outcome = {"claim": claim_slot(factory, when, "github-schedule",
                                          lease_seconds=900,
                                          logical_source="github_schedule")}
            with lock:
                outcomes.append(outcome)

        def from_backstop():
            report = run_backstop_once(factory, as_of=when, transport=transport)
            with lock:
                outcomes.append({"report": report})

        threads = [threading.Thread(target=from_schedule),
                   threading.Thread(target=from_backstop)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        shared = "maint-slot-20261004T1207Z"
        claims = [o["claim"].claimed for o in outcomes if "claim" in o]
        dispatched = [
            d for o in outcomes if "report" in o for d in o["report"].dispatched
        ]
        winners = sum(claims) + sum(1 for d in dispatched if d == shared)
        assert winners == 1, (
            f"exactly one active execution for the shared slot, got {winners} "
            f"(claims={claims}, dispatched={dispatched})")
        # and the shared slot was never dispatched twice
        assert sum(1 for c in transport.calls
                   if c["body"]["inputs"]["slot_id"] == shared) <= 1


# -- Part 12/29: bounded catch-up -------------------------------------------


class TestBoundedCatchUp:
    def test_the_window_is_a_documented_constant(self):
        from app.services.maintenance_dispatch import BACKSTOP_CATCHUP_HOURS

        assert isinstance(BACKSTOP_CATCHUP_HOURS, int)
        assert 0 < BACKSTOP_CATCHUP_HOURS <= 72

    def test_only_a_bounded_number_of_slots_is_considered(self, factory):
        from app.services.maintenance_dispatch import (
            BACKSTOP_CATCHUP_HOURS,
            missed_slot_ids,
        )

        recoverable, _expired = missed_slot_ids(
            factory, as_of=at("2026-10-04T12:07:00")
        )
        assert len(recoverable) <= BACKSTOP_CATCHUP_HOURS // 12 + 2

    def test_an_old_gap_does_not_produce_a_storm(self, factory):
        from app.services.maintenance_dispatch import run_backstop_once

        transport = fake_transport(204)
        report = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=transport, window_hours=36
        )
        assert len(report.dispatched) <= 4

    def test_a_long_outage_stays_bounded(self, factory):
        from app.services.maintenance_dispatch import missed_slot_ids

        recoverable, _ = missed_slot_ids(
            factory, as_of=at("2026-11-04T12:07:00"), window_hours=36
        )
        assert len(recoverable) <= 5


# -- Part 15/19/28: outcome classification and reconciliation ---------------


class TestWorkflowOutcomeClassification:
    @pytest.mark.parametrize(
        "status,expected",
        [(204, "dispatch-accepted"), (401, "permanent-failure"),
         (403, "permanent-failure"), (404, "permanent-failure"),
         (409, "conflict"), (429, "retryable"), (500, "retryable"),
         (503, "retryable"), (302, "permanent-failure")],
    )
    def test_github_status_classification(self, factory, status, expected):
        from app.services.maintenance_dispatch import classify_github_status

        assert classify_github_status(status) == expected

    def test_network_failure_is_retryable_but_not_accepted(self, factory, monkeypatch):
        from app.services.maintenance_dispatch import (
            RETRYABLE,
            dispatch_workflow,
        )

        def boom(url, token, body, timeout):
            return 0, {}

        outcome = dispatch_workflow(
            slot_id="maint-slot-20261004T1207Z", dispatch_id="d",
            transport=boom,
        )
        assert outcome.accepted is False
        assert outcome.classification == RETRYABLE

    @pytest.mark.parametrize(
        "conclusion,status,expected",
        [(None, "queued", "DISPATCHED"), (None, "in_progress", "RUNNING"),
         ("completed", None, "SUCCEEDED"), ("failure", None, "FAILED"),
         ("timed_out", None, "FAILED"), ("cancelled", None, "FAILED")],
    )
    def test_workflow_run_maps_to_slot_state(self, factory, conclusion, status, expected):
        from app.services.maintenance_dispatch import state_for_workflow_run

        assert state_for_workflow_run(conclusion, status) == expected

    def test_accepted_dispatch_is_never_called_success(self, factory):
        from app.services.maintenance_dispatch import dispatch_workflow
        from app.services.maintenance_slot import DISPATCHED

        transport = fake_transport(204)
        outcome = dispatch_workflow(
            slot_id="maint-slot-20261004T1207Z", dispatch_id="d", transport=transport
        )
        assert outcome.accepted is True
        assert outcome.classification == "dispatch-accepted"

    def test_a_failed_workflow_becomes_failed_and_is_not_reset(self, factory):
        from app.services.maintenance_dispatch import reconcile_run
        from app.services.maintenance_dispatch import run_backstop_once
        from app.services.maintenance_slot import FAILED, slot_state

        transport = fake_transport(204)
        report = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=transport
        )
        slot = report.dispatched[0]
        reconcile_run(factory, slot, conclusion="failure", status="completed",
                      as_of=at("2026-10-04T13:00:00"))
        assert slot_state(factory, slot) == FAILED

    def test_a_succeeded_slot_is_never_rewritten(self, factory):
        from app.services.maintenance_dispatch import reconcile_run, run_backstop_once
        from app.services.maintenance_slot import SUCCEEDED, slot_state

        report = run_backstop_once(
            factory, as_of=at("2026-10-04T12:07:00"), transport=fake_transport(204)
        )
        slot = report.dispatched[0]
        reconcile_run(factory, slot, conclusion="completed", status="completed",
                      as_of=at("2026-10-04T13:00:00"))
        again = reconcile_run(factory, slot, conclusion="failure", status="completed",
                              as_of=at("2026-10-04T14:00:00"))
        assert again is None
        assert slot_state(factory, slot) == SUCCEEDED


# -- Parts 18, 20, 21: recovery and observability ----------------------------


class TestRecoveryAndObservability:
    def test_an_expired_lease_is_recovered_by_a_later_pass(self, factory):
        from app.services.maintenance_dispatch import run_backstop_once
        from app.services.maintenance_dispatch import claim_slot

        claim_slot(factory, at("2026-10-04T12:07:00"), "vercel-cron", lease_seconds=60)
        later = at("2026-10-04T13:00:00")
        report = run_backstop_once(factory, as_of=later, transport=fake_transport(204))
        assert report.expired_leases, "a crashed dispatcher must not block the slot"
        assert report.dispatched, "and the slot must become recoverable"

    def test_observability_is_derived_from_persisted_state(self, factory):
        from app.services.maintenance_dispatch import observability, run_backstop_once

        run_backstop_once(factory, as_of=at("2026-10-04T12:07:00"),
                         transport=fake_transport(204))
        report = observability(factory, as_of=at("2026-10-04T13:00:00"))
        assert report["as_of"].startswith("2026-10-04T13:00")
        assert isinstance(report["by_state"], dict)
        assert isinstance(report["by_source"], dict)
        assert report["by_source"].get("external_scheduler_dispatch", 0) >= 1
        assert report["overdue_slot_count"] >= 0

    def test_dispatcher_never_runs_the_worker(self, factory, client, monkeypatch):
        """The endpoint must only reconcile, claim and dispatch."""
        monkeypatch.setenv("CRON_SECRET", SECRET)
        monkeypatch.setenv("GITHUB_ACTIONS_DISPATCH_TOKEN", FAKE_TOKEN)
        import app.jobs.scholarzone_maintenance as worker

        called = []
        original = worker.main
        worker.main = lambda *a, **k: called.append(True)
        try:
            response = client.post("/internal/maintenance/dispatch",
                                   headers={"Authorization": f"Bearer {SECRET}"})
            assert response.status_code == 200
            assert called == [], "the dispatcher must not run the maintenance worker"
        finally:
            worker.main = original


# -- Part 31: isolation ------------------------------------------------------


class TestIsolation:
    def test_no_ambient_database_is_created(self, factory):
        assert not AMBIENT.exists()

    def test_only_the_configured_cron_exists(self):
        import json as _json

        config = _json.loads(
            (BACKEND.parent / "vercel.json").read_text(encoding="utf-8")
        )
        crons = config["crons"]
        assert len(crons) == 1, "exactly one daily backstop"
        assert crons[0]["schedule"].count("*") >= 2
        assert crons[0]["path"].endswith("/internal/maintenance/dispatch")

    def test_existing_services_are_preserved(self):
        import json as _json

        config = _json.loads(
            (BACKEND.parent / "vercel.json").read_text(encoding="utf-8")
        )
        assert sorted(config["services"]) == ["backend", "frontend"]

