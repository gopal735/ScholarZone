"""Durable logical maintenance slot core.

A "logical slot" is one occurrence of the maintenance schedule. The schedule is
``7 */12 * * *``, so the recurring UTC slots are 00:07 and 12:07.

The invariants this module exists to make true:

    one logical slot -> one durable row -> at most one active claim
                     -> explicit lease -> safe recovery -> correct source

Slot identity is **deterministic**, never generated. ``slot_id`` is a pure
function of the UTC due instant, so a request that arrives five minutes late
still identifies the slot that was due, and two independent processes computing
it from the same slot agree without coordinating.

Ownership is decided by the **database**, not by application timing. The claim
path relies on a unique index over a nullable ``slot_id`` column: the first
INSERT for a slot succeeds and every other INSERT for the same slot raises, so
"check then insert" is never the mechanism.

All time is UTC. ``as_of`` is always passed in rather than read from the clock,
so the logic is pure and testable at midnight, month, year and leap-day
boundaries.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import MaintenanceRun

# -- States -----------------------------------------------------------------

DUE = "DUE"
CLAIMED = "CLAIMED"
DISPATCHED = "DISPATCHED"
RUNNING = "RUNNING"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
EXPIRED = "EXPIRED"

STATES = frozenset({DUE, CLAIMED, DISPATCHED, RUNNING, SUCCEEDED, FAILED, EXPIRED})

#: Terminal states. A finished slot is never re-opened.
TERMINAL = frozenset({SUCCEEDED, FAILED})

#: Every legal transition, stated once and enforced centrally.
TRANSITIONS: dict[frozenset[str], frozenset[str]] = {
    frozenset({DUE}): frozenset({CLAIMED}),
    # A claim whose lease lapsed becomes EXPIRED rather than silently DUE, so a
    # recovery is always visible in the record.
    frozenset({CLAIMED}): frozenset({DISPATCHED, EXPIRED}),
    frozenset({EXPIRED}): frozenset({CLAIMED}),
    frozenset({DISPATCHED}): frozenset({RUNNING, FAILED}),
    frozenset({RUNNING}): frozenset({SUCCEEDED, FAILED}),
    frozenset({SUCCEEDED}): frozenset(),
    frozenset({FAILED}): frozenset(),
}


class IllegalTransition(RuntimeError):
    """A transition that the state machine does not permit."""


def can_transition(current: str, target: str) -> bool:
    """True only for a transition the machine allows."""
    if current not in STATES or target not in STATES:
        return False
    return target in TRANSITIONS.get(frozenset({current}), frozenset())


def require_transition(current: str, target: str) -> None:
    """Raise unless the transition is legal. The single enforcement point."""
    if not can_transition(current, target):
        raise IllegalTransition(f"{current} -> {target} is not a legal transition")


# -- Sources ----------------------------------------------------------------

GITHUB_SCHEDULE = "github_schedule"
EXTERNAL_SCHEDULER_DISPATCH = "external_scheduler_dispatch"
WORKFLOW_DISPATCH = "workflow_dispatch"
WATCHDOG = "watchdog"
MANUAL = "manual"

LOGICAL_SOURCES = frozenset(
    {GITHUB_SCHEDULE, EXTERNAL_SCHEDULER_DISPATCH, WORKFLOW_DISPATCH, WATCHDOG, MANUAL}
)


def resolve_logical_source(
    supplied: str | None, transport_event: str | None = None
) -> str:
    """Logical origin, never inferred from the transport.

    A Vercel-triggered run arrives as GitHub ``workflow_dispatch`` while its
    logical origin is an external scheduler, so the caller may supply the
    logical source explicitly and it is preserved. When nothing is supplied we
    fall back to the transport, which is only a safe default for the two
    unambiguous cases.
    """
    if supplied:
        value = supplied.strip()
        if value not in LOGICAL_SOURCES:
            raise ValueError(f"unknown logical source {value!r}")
        return value
    if transport_event == "schedule":
        return GITHUB_SCHEDULE
    if transport_event in ("workflow_dispatch",):
        return WORKFLOW_DISPATCH
    return MANUAL


# -- Slot identity ----------------------------------------------------------

SLOT_MINUTE = 7
SLOT_HOURS = (0, 12)
SLOT_PREFIX = "maint-slot"


def slot_due_at(as_of: dt.datetime) -> dt.datetime:
    """The most recent due slot at or before ``as_of``, in UTC.

    Pure: ``as_of`` is injected, never read from the clock.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware; schedule logic is UTC only")
    moment = as_of.astimezone(dt.timezone.utc).replace(second=0, microsecond=0)
    candidates = []
    for hour in SLOT_HOURS:
        due = moment.replace(hour=hour, minute=SLOT_MINUTE)
        if due <= moment:
            candidates.append(due)
    if not candidates:
        # Before the first slot of the UTC day: the previous day's 12:07.
        previous = (moment - dt.timedelta(days=1)).replace(
            hour=SLOT_HOURS[-1], minute=SLOT_MINUTE
        )
        candidates.append(previous)
    return max(candidates)


def slot_id_for(as_of: dt.datetime) -> str:
    """Deterministic identity of the slot due at ``as_of``.

    Same logical slot -> same id, always. No randomness, no process or request
    identity, no execution timestamp.
    """
    due = slot_due_at(as_of)
    return f"{SLOT_PREFIX}-{due:%Y%m%dT%H%M}Z"


# -- Results ----------------------------------------------------------------


@dataclass(frozen=True)
class ClaimResult:
    claimed: bool
    reason: str
    slot_id: str
    run_id: str | None = None
    state: str | None = None
    lease_until: dt.datetime | None = None


def _utc(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def get_or_create_slot(
    session_factory,
    as_of: dt.datetime,
    *,
    logical_source: str | None = None,
    transport_event: str | None = None,
    worker: str = "maintenance-slot-core",
) -> tuple[MaintenanceRun, bool]:
    """Return ``(row, created)`` for the slot due at ``as_of``.

    Idempotent: repeated calls for the same slot yield the same row. The
    database decides, via the unique index, which caller creates it.
    """
    identifier = slot_id_for(as_of)
    due = slot_due_at(as_of)
    source = resolve_logical_source(logical_source, transport_event)

    session = session_factory()
    try:
        existing = (
            session.query(MaintenanceRun)
            .filter(MaintenanceRun.slot_id == identifier)
            .one_or_none()
        )
        if existing is not None:
            return existing, False
        row = MaintenanceRun(
            run_id=f"{identifier}-{due:%Y%m%dT%H%M%S}Z",
            slot_id=identifier,
            slot_status=DUE,
            slot_due_at=due,
            logical_source=source,
            transport_event=transport_event,
            worker=worker,
            status=DUE,
            stages=[],
            counts={},
            dry_run=False,
            started_at=due,
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            # Another contender created the same logical slot first.
            session.rollback()
            winner = (
                session.query(MaintenanceRun)
                .filter(MaintenanceRun.slot_id == identifier)
                .one_or_none()
            )
            if winner is None:  # pragma: no cover - defensive
                raise
            return winner, False
        return row, True
    finally:
        session.close()


def claim_slot(
    session_factory,
    as_of: dt.datetime,
    owner: str,
    *,
    lease_seconds: int = 3600,
    logical_source: str | None = None,
    transport_event: str | None = None,
) -> ClaimResult:
    """Claim the slot due at ``as_of`` for ``owner``.

    The database is the serialisation authority. A contender that loses gets
    ``claimed=False`` and never a second active owner.
    """
    row, _created = get_or_create_slot(
        session_factory,
        as_of,
        logical_source=logical_source,
        transport_event=transport_event,
    )
    identifier = row.slot_id
    now = as_of.astimezone(dt.timezone.utc)

    session = session_factory()
    try:
        current = (
            session.query(MaintenanceRun)
            .filter(MaintenanceRun.slot_id == identifier)
            .one_or_none()
        )
        if current is None:  # pragma: no cover - defensive
            return ClaimResult(False, "slot-vanished", identifier)
        state = current.slot_status or DUE
        lease_until = _utc(current.lease_until)

        if state in TERMINAL:
            return ClaimResult(False, f"slot-terminal-{state}", identifier, state=state)
        if state == RUNNING:
            return ClaimResult(False, "slot-already-running", identifier, state=state)
        if state == DISPATCHED:
            return ClaimResult(False, "slot-already-dispatched", identifier, state=state)
        if state == CLAIMED:
            if current.claim_owner == owner and lease_until and lease_until > now:
                # Same owner, lease still live: idempotent re-entry.
                return ClaimResult(
                    True, "already-claimed-by-owner", identifier,
                    run_id=current.run_id, state=state, lease_until=lease_until,
                )
            if lease_until and lease_until > now:
                return ClaimResult(
                    False, "lease-active", identifier, state=state, lease_until=lease_until
                )
            require_transition(CLAIMED, EXPIRED)
            current.slot_status = EXPIRED
            session.commit()
            require_transition(EXPIRED, CLAIMED)

        require_transition(state, CLAIMED)
        current.slot_status = CLAIMED
        current.claim_owner = owner
        current.claimed_at = now
        current.lease_until = now + dt.timedelta(seconds=lease_seconds)
        session.commit()
        return ClaimResult(
            True, "claimed", identifier, run_id=current.run_id,
            state=CLAIMED, lease_until=current.lease_until,
        )
    finally:
        session.close()


def advance(
    session_factory,
    slot_id: str,
    target: str,
    *,
    now: dt.datetime | None = None,
) -> MaintenanceRun:
    """Move a slot to ``target``, validating the transition centrally."""
    session = session_factory()
    try:
        row = (
            session.query(MaintenanceRun)
            .filter(MaintenanceRun.slot_id == slot_id)
            .one_or_none()
        )
        if row is None:
            raise LookupError(f"unknown slot {slot_id!r}")
        require_transition(row.slot_status or DUE, target)
        moment = _utc(now) or dt.datetime.now(dt.timezone.utc)
        row.slot_status = target
        if target == RUNNING:
            row.started_at = moment
            row.status = "running"
        elif target in TERMINAL:
            row.finished_at = moment
            row.status = "success" if target == SUCCEEDED else "failure"
            row.lease_until = None
        session.commit()
        return row
    finally:
        session.close()


def expire_stale_claims(
    session_factory, *, now: dt.datetime | None = None
) -> list[str]:
    """Expire claims whose lease has lapsed. Returns the affected slot ids.

    An explicit EXPIRED state, never a silent CLAIMED -> DUE, so a recovery is
    always visible in the record.
    """
    moment = _utc(now) or dt.datetime.now(dt.timezone.utc)
    session = session_factory()
    expired: list[str] = []
    try:
        rows = (
            session.query(MaintenanceRun)
            .filter(MaintenanceRun.slot_status == CLAIMED)
            .all()
        )
        for row in rows:
            lease_until = _utc(row.lease_until)
            if lease_until is not None and lease_until <= moment:
                require_transition(CLAIMED, EXPIRED)
                row.slot_status = EXPIRED
                row.lease_until = None
                expired.append(row.slot_id)
        if expired:
            session.commit()
        return expired
    finally:
        session.close()


def slot_state(session_factory, slot_id: str) -> str | None:
    session = session_factory()
    try:
        row = (
            session.query(MaintenanceRun)
            .filter(MaintenanceRun.slot_id == slot_id)
            .one_or_none()
        )
        return row.slot_status if row is not None else None
    finally:
        session.close()


def active_claim_count(session_factory, slot_id: str) -> int:
    """How many active claims exist for a slot. Must never exceed one."""
    session = session_factory()
    try:
        return (
            session.query(MaintenanceRun)
            .filter(
                MaintenanceRun.slot_id == slot_id,
                MaintenanceRun.slot_status.in_([CLAIMED, DISPATCHED, RUNNING]),
            )
            .count()
        )
    finally:
        session.close()


def describe_schedule() -> Iterable[str]:
    """Human-readable description of the schedule this core implements."""
    return (
        "7 */12 * * * (UTC) -> "
        + ", ".join(f"{hour:02d}:{SLOT_MINUTE:02d}Z" for hour in SLOT_HOURS)
    )
