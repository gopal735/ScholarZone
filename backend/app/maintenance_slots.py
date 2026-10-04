"""Deterministic maintenance schedule slots (Phase A core).

Pure logic only. Nothing here touches the database, the network, or the wall
clock. Every function that needs "now" takes an explicit ``as_of``.

Why this exists
---------------
``MaintenanceRun`` records *executions*. It cannot record a slot that became
due and never ran -- and if the GitHub trigger is dropped, no execution row is
ever written. A ledger created only by the thing that ran is empty in exactly
the case we need to detect. So the logical schedule is modelled separately, and
this module is the deterministic half of that model.

The schedule is ``7 */12 * * *`` UTC, which means the logical due instants are
00:07 and 12:07 UTC. Slot identity is derived from the *due instant*, never
from the moment of observation, so a trigger that arrives five minutes late
still identifies the slot it belongs to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

#: The authoritative schedule: minute 7 of every 12th hour, UTC.
SLOT_HOURS_UTC = (0, 12)
SLOT_MINUTE_UTC = 7

#: Canonical slot id, e.g. ``maintenance:2026-10-04T00:07:00Z``.
SLOT_ID_RE = re.compile(r"\Amaintenance:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class SlotState(str, Enum):
    DUE = "DUE"
    CLAIMED = "CLAIMED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


#: The only transitions the system permits. Centralised on purpose: scattered
#: state rules are how a terminal slot quietly reverts to DUE.
LEGAL_TRANSITIONS: dict[SlotState, frozenset[SlotState]] = {
    SlotState.DUE: frozenset({SlotState.CLAIMED}),
    SlotState.CLAIMED: frozenset({SlotState.DISPATCHED, SlotState.EXPIRED}),
    SlotState.DISPATCHED: frozenset({SlotState.RUNNING}),
    SlotState.RUNNING: frozenset({SlotState.SUCCEEDED, SlotState.FAILED}),
    SlotState.SUCCEEDED: frozenset(),
    SlotState.FAILED: frozenset(),
    SlotState.EXPIRED: frozenset({SlotState.CLAIMED}),
}

#: A terminal state never silently reverts, so recovery has to be explicit.
TERMINAL_STATES = frozenset({SlotState.SUCCEEDED, SlotState.FAILED})


class InvalidTransition(ValueError):
    """A transition that is not in :data:`LEGAL_TRANSITIONS` was attempted."""


class LogicalSource(str, Enum):
    """Where the *intent* came from.

    Deliberately distinct from the GitHub transport event. A Vercel Cron will
    reach the workflow as ``event=workflow_dispatch`` while its logical origin
    is ``external_scheduler_dispatch``; collapsing the two would make a
    backstop-dispatched run indistinguishable from a real GitHub schedule, and
    would corrupt the historical Phase 6 analysis.
    """

    GITHUB_SCHEDULE = "github_schedule"
    EXTERNAL_SCHEDULER_DISPATCH = "external_scheduler_dispatch"
    WORKFLOW_DISPATCH = "workflow_dispatch"
    WATCHDOG = "watchdog"
    MANUAL = "manual"


def _require_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("naive datetime rejected; maintenance slots are UTC-only")
    return moment.astimezone(timezone.utc)


def due_at_for(day: datetime, hour: int) -> datetime:
    """The logical due instant for ``hour`` on the UTC day of ``day``."""
    day_utc = _require_utc(day)
    return datetime(
        day_utc.year, day_utc.month, day_utc.day, hour, SLOT_MINUTE_UTC, tzinfo=timezone.utc
    )


def slot_id(due_at: datetime) -> str:
    """Canonical, stable identity for a logical slot.

    Depends only on the due instant. Never on randomness, process, host or the
    time of observation.
    """
    return "maintenance:" + _require_utc(due_at).strftime("%Y-%m-%dT%H:%M:%SZ")


def due_at_from_slot_id(value: str) -> datetime:
    """Inverse of :func:`slot_id`, so a stored identity can be reasoned about."""
    if not SLOT_ID_RE.match(value or ""):
        raise ValueError(f"not a maintenance slot id: {value!r}")
    return datetime.strptime(value.split(":", 1)[1], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def latest_due_slot(as_of: datetime) -> datetime:
    """The latest logical slot due at or before ``as_of``.

    ``13:00`` maps back to the ``12:07`` slot: a 13:07 slot does not exist, and
    inventing one would let an hourly misfire fabricate maintenance periods
    that were never scheduled.
    """
    moment = _require_utc(as_of)
    candidate = due_at_for(moment, SLOT_HOURS_UTC[-1])
    if moment < candidate:
        candidate = due_at_for(moment, SLOT_HOURS_UTC[0])
        if moment < candidate:
            # before today's first slot: fall back to yesterday's 12:07
            candidate = candidate - timedelta(days=1) + timedelta(
                hours=SLOT_HOURS_UTC[-1]
            )
    return candidate


def is_legal_transition(current: SlotState, target: SlotState) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, frozenset())


def validate_transition(current: SlotState, target: SlotState) -> None:
    """Raise unless ``current -> target`` is permitted."""
    if current == target:
        raise InvalidTransition(f"{current.value} -> {target.value} is a no-op, not a transition")
    if not is_legal_transition(current, target):
        allowed = ", ".join(sorted(s.value for s in LEGAL_TRANSITIONS.get(current, ())))
        raise InvalidTransition(
            f"{current.value} -> {target.value} is not a legal transition "
            f"(allowed from {current.value}: {allowed or 'none'})"
        )


@dataclass(frozen=True)
class ClaimOutcome:
    """Result of attempting to claim a slot."""

    claimed: bool
    owner: str | None = None
    lease_until: datetime | None = None
    reason: str = ""