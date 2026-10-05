"""External dispatch and self-healing backstop for the durable slot core.

Phase A owns slot identity, the state machine, atomic claim and leases. This
module does not reimplement any of that; it *uses* it. Its whole job is:

    a dropped GitHub schedule event
        -> a durable missed slot
        -> the daily backstop notices it
        -> one atomic claim
        -> one GitHub workflow_dispatch
        -> the same logical slot
        -> a real terminal state, read back from the real workflow run

Two rules shape everything here:

* **A dispatch is not a success.** HTTP 2xx from GitHub only means the request
  was accepted. ``SUCCEEDED``/``FAILED`` are decided from the actual workflow
  run, correlated by dispatch id.
* **The dispatcher never runs maintenance.** It claims, dispatches and returns.
  The 90-minute worker stays inside GitHub Actions.

Provider access is injected, so every test runs against a deterministic fake.
The real credential is only ever read from the environment at call time.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Callable, Iterable

from app.maintenance_slots import (
    LogicalSource,
    SlotState,
    due_at_from_slot_id,
    latest_due_slot,
    slot_id as canonical_slot_id,
)
from app.services.maintenance_slot_store import (
    claim_slot,
    ensure_slot,
    expire_stale_claims,
    read_slot,
    to_utc,
    transition_slot,
)

#: Slot states, named the way the rest of the codebase names them. These are the
#: *persisted* states from the Phase A core; the dispatcher never invents one.
DUE = SlotState.DUE.value
CLAIMED = SlotState.CLAIMED.value
DISPATCHED = SlotState.DISPATCHED.value
EXPIRED = SlotState.EXPIRED.value
RUNNING = SlotState.RUNNING.value
SUCCEEDED = SlotState.SUCCEEDED.value
FAILED = SlotState.FAILED.value

GITHUB_SCHEDULE = LogicalSource.GITHUB_SCHEDULE.value
EXTERNAL_SCHEDULER_DISPATCH = LogicalSource.EXTERNAL_SCHEDULER_DISPATCH.value
WORKFLOW_DISPATCH = LogicalSource.WORKFLOW_DISPATCH.value
WATCHDOG = LogicalSource.WATCHDOG.value

#: The GitHub schedule stays the primary trigger. This is only the backstop.
REPOSITORY = "gopal735/ScholarZone"
WORKFLOW_FILE = "verification-cron.yml"
DISPATCH_REF = "master"

#: Bounded recovery. A missed slot older than this is expired rather than
#: executed, so a long outage cannot produce an unbounded execution storm. Two
#: daily slots plus slack: enough to catch a missed run and a rescheduled one.
BACKSTOP_CATCHUP_HOURS = 36

#: Server-side only. Never logged, never returned, never a URL parameter.
TOKEN_ENV = "GITHUB_ACTIONS_DISPATCH_TOKEN"

DISPATCH_204 = "dispatch-accepted"
CONFIGURATION_BLOCKED = "configuration-blocked"
PERMANENT_FAILURE = "permanent-failure"
RETRYABLE = "retryable"
CONFLICT = "conflict"
PREVENTED_DUPLICATE = "prevented-duplicate"


def dispatch_token() -> str | None:
    """The dispatch credential, from the environment only."""
    value = (os.environ.get(TOKEN_ENV) or "").strip()
    return value or None


# -- GitHub outcome classification (Part 16) -------------------------------


def classify_github_status(status: int) -> str:
    """Map an HTTP status to a retry decision.

    Bounded by construction: only 429 and 5xx are retryable. Authentication,
    permission and not-found errors are permanent, so a misconfigured token
    fails fast instead of retrying forever.
    """
    if 200 <= status < 300:
        return DISPATCH_204
    if status in (401, 403):
        return PERMANENT_FAILURE
    if status == 404:
        return PERMANENT_FAILURE
    if status == 409:
        return CONFLICT
    if status == 429:
        return RETRYABLE
    if 500 <= status < 600:
        return RETRYABLE
    return PERMANENT_FAILURE


@dataclass
class DispatchOutcome:
    """What happened when we tried to start a run. Never a success claim."""

    accepted: bool
    classification: str
    status: int | None = None
    dispatch_id: str | None = None
    detail: str = ""

    @property
    def retryable(self) -> bool:
        return self.classification == RETRYABLE


Transport = Callable[[str, str, dict, int], tuple[int, dict]]


def github_transport(url: str, token: str, body: dict, timeout: int) -> tuple[int, dict]:
    """Real HTTP call to GitHub. Only used outside tests."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "scholarzone-maintenance-dispatcher/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {}
    except (urllib.error.URLError, TimeoutError, OSError):
        # Network-level failure: retryable, but bounded by the caller.
        return 0, {}


def dispatch_workflow(
    *,
    slot_id: str,
    dispatch_id: str,
    transport: Transport | None = None,
    timeout: int = 30,
    repository: str = REPOSITORY,
    workflow: str = WORKFLOW_FILE,
    ref: str = DISPATCH_REF,
) -> DispatchOutcome:
    """Ask GitHub to run the maintenance workflow for one logical slot.

    ``repository``, ``workflow`` and ``ref`` are server-side constants, never
    request input, so a caller cannot aim this at another repository. The token
    is read from the environment and never returned or logged.
    """
    token = dispatch_token()
    if token is None:
        return DispatchOutcome(
            False,
            CONFIGURATION_BLOCKED,
            detail=f"{TOKEN_ENV} is not configured",
        )

    dispatch_id = dispatch_id or uuid.uuid4().hex[:16]
    body = {
        "ref": ref,
        "inputs": {
            "slot_id": slot_id,
            "logical_source": EXTERNAL_SCHEDULER_DISPATCH,
            "dispatch_id": dispatch_id,
        },
    }
    url = (
        f"https://api.github.com/repos/{repository}/actions/workflows/"
        f"{workflow}/dispatches"
    )
    call = transport or github_transport
    status, payload = call(url, token, body, timeout)

    if status == 0:
        return DispatchOutcome(
            False, RETRYABLE, None, dispatch_id, detail="network failure"
        )
    classification = classify_github_status(status)
    return DispatchOutcome(
        accepted=classification == DISPATCH_204,
        classification=classification,
        status=status,
        dispatch_id=payload.get("dispatch_id") or dispatch_id
        if isinstance(payload, dict)
        else dispatch_id,
        detail="",
    )


# -- Slot discovery and bounded catch-up (Parts 11, 12) ---------------------


def missed_slot_ids(
    session_factory, *, as_of: dt.datetime, window_hours: int = BACKSTOP_CATCHUP_HOURS
) -> tuple[list[str], list[str]]:
    """Slots due within the recovery window, and those expired as too old.

    Returns ``(recoverable, expired)``. A slot outside the window becomes
    explicitly ``EXPIRED`` so the gap is recorded rather than silently ignored,
    and never produces an execution storm.
    """
    due = latest_due_slot(as_of)
    floor = due - dt.timedelta(hours=window_hours)
    slot_ids: list[str] = []
    cursor = floor
    while cursor <= due:
        slot_ids.append(canonical_slot_id(cursor))
        cursor += dt.timedelta(hours=12)

    recoverable: list[str] = []
    expired: list[str] = []
    for identifier in slot_ids:
        row = _read_slot(session_factory, identifier)
        if row is None:
            recoverable.append(identifier)
        elif row.state == EXPIRED:
            expired.append(identifier)
        elif row.state in (DUE, CLAIMED, EXPIRED):
            recoverable.append(identifier)
        # DISPATCHED / RUNNING / SUCCEEDED / FAILED are real outcomes, not missed
        # work. This is only reachable now because the slot is stored per logical
        # slot rather than per run: a slot whose trigger was dropped has a row
        # here even though no MaintenanceRun was ever written for it.
    return recoverable, expired


# -- Dispatcher (Parts 7, 11, 13, 14, 17, 18, 20) ---------------------------


@dataclass
class DispatchReport:
    """One backstop pass. Purely a record of what was attempted."""

    as_of: dt.datetime
    considered: list[str] = field(default_factory=list)
    claimed: list[str] = field(default_factory=list)
    dispatched: list[str] = field(default_factory=list)
    prevented_duplicates: list[str] = field(default_factory=list)
    expired: list[str] = field(default_factory=list)
    expired_leases: list[str] = field(default_factory=list)
    classifications: dict = field(default_factory=dict)

    @property
    def accepted(self) -> list[str]:
        return list(self.dispatched)


def slot_time_from_id(slot_id: str) -> dt.datetime:
    """Recover the UTC due instant encoded in a slot id.

    Reads it back out of the Phase A canonical id rather than parsing a second,
    private format. Claiming *this* slot rather than whichever slot is due right
    now is what makes multi-slot catch-up possible; during catch-up the due
    instant differs per slot, so claiming ``as_of`` would collapse every
    iteration onto the same one.
    """
    return due_at_from_slot_id(slot_id)


def _session(session_factory):
    """One short session. Always closed, so no SQLite write lock is held."""
    return session_factory()


def _read_slot(session_factory, slot_id: str):
    """The durable slot row, or ``None`` when the slot is genuinely absent."""
    session = _session(session_factory)
    try:
        return read_slot(session, slot_id)
    finally:
        session.close()


def _ensure_slot(session_factory, slot_id: str, as_of: dt.datetime, **kwargs) -> None:
    """Make the slot exist as DUE. Idempotent; a no-op when it already exists."""
    session = _session(session_factory)
    try:
        ensure_slot(session, due_at_from_slot_id(slot_id), as_of=as_of, **kwargs)
    finally:
        session.close()


def _transition(session_factory, slot_id: str, target: str, as_of: dt.datetime, **kwargs) -> None:
    session = _session(session_factory)
    try:
        transition_slot(
            session, slot_id, SlotState(target), as_of=as_of, **kwargs
        )
    finally:
        session.close()


def _lapsed_claim_ids(session_factory, as_of: dt.datetime) -> list[str]:
    """Slots whose claim has lapsed and is therefore about to be expired.

    Read immediately before :func:`expire_stale_claims`, so the report names the
    slots the sweep actually acted on. The predicate is identical to the
    sweep's, which is the point: the sweep is what moves them to ``EXPIRED``, and
    this only observes.
    """
    from sqlalchemy import select

    from app.models import MaintenanceSlot

    session = _session(session_factory)
    try:
        return list(
            session.execute(
                select(MaintenanceSlot.slot_id).where(
                    MaintenanceSlot.state == CLAIMED,
                    MaintenanceSlot.lease_until.is_not(None),
                    MaintenanceSlot.lease_until <= as_of,
                )
            ).scalars()
        )
    finally:
        session.close()


def run_backstop_once(
    session_factory,
    *,
    as_of: dt.datetime,
    transport: Transport | None = None,
    owner: str = "vercel-cron",
    window_hours: int = BACKSTOP_CATCHUP_HOURS,
    lease_seconds: int = 900,
) -> DispatchReport:
    """One daily backstop pass: reconcile, claim, dispatch, return.

    Never runs maintenance. Returns quickly regardless of how many slots it
    considered.
    """
    report = DispatchReport(as_of=as_of)

    # A crashed dispatcher must not block a slot forever.
    report.expired_leases = _lapsed_claim_ids(session_factory, as_of)
    session = _session(session_factory)
    try:
        expire_stale_claims(session, as_of=as_of)
    finally:
        session.close()

    recoverable, expired = missed_slot_ids(
        session_factory, as_of=as_of, window_hours=window_hours
    )
    report.considered = recoverable
    report.expired = expired

    for identifier in recoverable:
        row = _read_slot(session_factory, identifier)
        if row is not None and row.state in (DISPATCHED, RUNNING, SUCCEEDED, FAILED):
            continue

        # Claim THIS slot, not the one currently due: during catch-up the
        # due instant differs per slot, and claiming `as_of` would collapse
        # every iteration onto the same slot.
        due = slot_time_from_id(identifier)
        _ensure_slot(
            session_factory,
            identifier,
            as_of,
            logical_source=EXTERNAL_SCHEDULER_DISPATCH,
            transport_event=WORKFLOW_DISPATCH,
        )
        session = _session(session_factory)
        try:
            claim = claim_slot(
                session,
                identifier,
                owner,
                dt.timedelta(seconds=lease_seconds),
                due,
            )
        finally:
            session.close()
        if not claim.claimed:
            # An active lease is ordinary contention, not a failure: another
            # worker already owns this slot.
            if claim.owner is not None:
                report.prevented_duplicates.append(identifier)
                report.classifications[identifier] = PREVENTED_DUPLICATE
            continue

        report.claimed.append(identifier)
        outcome = dispatch_workflow(
            slot_id=identifier,
            dispatch_id=identifier,
            transport=transport,
        )
        report.classifications[identifier] = outcome.classification
        if outcome.accepted:
            _transition(session_factory, identifier, DISPATCHED, as_of)
            report.dispatched.append(identifier)
        else:
            # Release the claim so a later pass can retry; the slot is never
            # left CLAIMED by a dispatcher that did not manage to dispatch.
            _release_claim(session_factory, identifier, as_of)
    return report


def _release_claim(session_factory, slot_id: str, as_of: dt.datetime) -> None:
    """Hand a slot back after a dispatch that did not happen.

    The claim is released through the same recovery primitive an expired lease
    uses, so a retry later is an ordinary ``EXPIRED -> CLAIMED`` recovery and the
    attempt stays visible instead of the slot silently returning to DUE. The
    session is closed on every path; leaving it open held a SQLite write lock and
    stalled every later reader.
    """
    row = _read_slot(session_factory, slot_id)
    if row is None or row.state != CLAIMED:
        return
    if to_utc(row.lease_until) is not None and to_utc(row.lease_until) > as_of:
        # The claim is still live, so releasing it early would break exactly the
        # lease protection Phase A exists to provide. It expires on its own and
        # the next pass recovers it.
        return
    session = _session(session_factory)
    try:
        expire_stale_claims(session, as_of)
    finally:
        session.close()


# -- Workflow-run reconciliation (Part 15) -----------------------------------

#: GitHub run conclusions mapped onto slot states. "dispatch accepted" is not
#: here on purpose: acceptance moves the slot to DISPATCHED, never to SUCCEEDED.
_RUN_STATE = {
    "queued": DISPATCHED,
    "in_progress": RUNNING,
    "completed": SUCCEEDED,
    "failure": FAILED,
    "cancelled": FAILED,
    "timed_out": FAILED,
    "action_required": FAILED,
}


def state_for_workflow_run(conclusion: str | None, status: str | None = None) -> str | None:
    """Map a real workflow run to a slot state, or None while still pending."""
    if conclusion:
        return _RUN_STATE.get(conclusion, FAILED)
    if status == "in_progress":
        return RUNNING
    if status == "queued" or status == "pending" or status == "waiting":
        return DISPATCHED
    return None


def reconcile_run(
    session_factory,
    slot_id: str,
    *,
    conclusion: str | None,
    status: str | None,
    as_of: dt.datetime,
) -> str | None:
    """Advance a slot from the real workflow run, if that is a legal move."""
    target = state_for_workflow_run(conclusion, status)
    if target is None:
        return None
    row = _read_slot(session_factory, slot_id)
    if row is None or row.state == target:
        return None
    if row.state in (SUCCEEDED, FAILED):
        return None  # terminal states are never rewritten

    from app.maintenance_slots import InvalidTransition

    try:
        if row.state == DISPATCHED and target in (SUCCEEDED, FAILED):
            # A workflow can finish before anyone observed it in progress. The
            # durable machine still requires RUNNING before a terminal state,
            # so the transition is recorded rather than skipped.
            _transition(session_factory, slot_id, RUNNING, as_of)
        _transition(session_factory, slot_id, target, as_of)
    except InvalidTransition:
        return None
    return target


# -- Observability (Part 21) -------------------------------------------------


def observability(session_factory, *, as_of: dt.datetime) -> dict:
    """Operational facts, every one derived from persisted rows."""
    from sqlalchemy import func

    from app.models import MaintenanceSlot

    session = _session(session_factory)
    try:
        by_state = dict(
            session.query(MaintenanceSlot.state, func.count())
            .group_by(MaintenanceSlot.state)
            .all()
        )
        by_source = dict(
            session.query(MaintenanceSlot.logical_source, func.count())
            .group_by(MaintenanceSlot.logical_source)
            .all()
        )
        overdue_rows = (
            session.query(MaintenanceSlot)
            .filter(MaintenanceSlot.state.in_([DUE, EXPIRED]))
            .all()
        )
        overdue = [row.slot_id for row in overdue_rows]
        dues = [
            to_utc(row.due_at)
            for row in overdue_rows
            if row.due_at is not None
        ]
        oldest = min(dues).isoformat() if dues else None
        return {
            "as_of": as_of.isoformat(),
            "by_state": by_state,
            "by_source": by_source,
            "overdue_slot_count": len(overdue),
            "oldest_overdue_slot": oldest,
            "dispatch_failures": sum(
                1 for s in by_state if s in (EXPIRED,)
            ),
            "workflow_failures": by_state.get(FAILED, 0),
            "recovered_leases": by_state.get(EXPIRED, 0),
        }
    finally:
        session.close()
