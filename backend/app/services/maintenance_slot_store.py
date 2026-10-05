"""Durable persistence for logical maintenance slots.

The deterministic half of the model lives in :mod:`app.maintenance_slots` and
knows nothing about SQL. This module is the other half: it turns a due instant
into exactly one durable row, and it decides ownership with the database rather
than with application timing.

Two rules shape every function here.

**One statement per transaction.** Nothing does ``SELECT`` -> decide in Python
-> ``UPDATE``. Each mutation is a single conditional statement whose ``WHERE``
clause carries the precondition, and the row count is the verdict. A
read-then-write under concurrency is a lost update: two contenders both read
``DUE``, both decide they may claim, and both write. Moving the precondition
into the ``WHERE`` clause means the database re-evaluates it against the row
version it actually holds, so the second writer matches zero rows and loses.
That is also why a lapsed lease cannot be stolen, and why recovery reuses the
claim statement instead of introducing a second one.

**Uniqueness is the final authority.** ``slot_id`` is ``UNIQUE``, so eight
concurrent ``ensure_slot`` calls for the same due instant collapse to one row
by constraint, not by convention.

The state machine, the legal transitions and the canonical slot id all come from
the pure core. This module never re-declares them, so a change to the schedule
or to the transition table cannot drift from what is persisted here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..maintenance_slots import (
    LEGAL_TRANSITIONS,
    ClaimOutcome,
    InvalidTransition,
    LogicalSource,
    SlotState,
    due_at_from_slot_id,
    is_legal_transition,
    slot_id as canonical_slot_id,
)
from ..models import MaintenanceSlot

__all__ = [
    "SlotConflict",
    "SlotNotFound",
    "claim_slot",
    "ensure_slot",
    "expire_stale_claims",
    "read_slot",
    "recover_slot",
    "to_utc",
    "transition_slot",
]


class SlotNotFound(LookupError):
    """No durable row exists for the requested slot id."""


class SlotConflict(RuntimeError):
    """A guarded transition lost a race and changed nothing.

    Raised instead of silently re-reading and retrying: the caller has to decide
    whether the slot is still the one it thought it was.
    """


#: States a fresh claim may be taken from. ``DUE`` is a slot that has come due and
#: is unowned; ``EXPIRED`` is a slot whose previous owner's lease lapsed. A
#: ``CLAIMED`` slot is never in this set, which is what makes an active or merely
#: still-unexpired claim untouchable by a second owner.
CLAIMABLE_STATES: tuple[SlotState, ...] = (SlotState.DUE, SlotState.EXPIRED)

#: Every mutation in this module targets the Core ``Table``, not the ORM class.
#:
#: An ORM bulk update defaults to ``synchronize_session="auto"``, which makes
#: SQLAlchemy *re-evaluate the ``WHERE`` clause in Python* against objects already
#: loaded in the session. That is precisely the read-then-write this module exists
#: to avoid, and it is not merely slow: ``lease_until <= :as_of`` then compares a
#: naive datetime loaded from SQLite against an aware one and raises
#: ``TypeError``, so an expiry sweep could crash depending on what happened to be
#: in the session's identity map. Stating the statements against the Core table
#: removes the whole class of problem - the database evaluates the predicate,
#: nothing local does.
_SLOT_TABLE = MaintenanceSlot.__table__


def _guarded_claim(canonical: str, states: list[str]):
    """``UPDATE ... WHERE slot_id = :slot AND state IN (:states)``.

    One statement carrying the entire precondition, so the row count is the
    verdict and no local evaluation can overrule it.
    """
    return update(_SLOT_TABLE).where(
        _SLOT_TABLE.c.slot_id == canonical,
        _SLOT_TABLE.c.state.in_(states),
    )


def _utc(moment: datetime) -> datetime:
    """Normalise to UTC, refusing naive datetimes.

    SQLite has no timezone-aware storage, so SQLAlchemy writes the wall time of
    whatever is bound. A naive datetime would therefore be stored as a local time
    and then compared against UTC lease instants as if they were the same kind of
    value, which turns every lease comparison into a silent, plausible, wrong
    answer. Rejecting them is cheaper than detecting that later.
    """
    if not isinstance(moment, datetime):
        raise TypeError(f"expected a datetime, got {type(moment).__name__}")
    if moment.tzinfo is None:
        raise ValueError("naive datetime rejected; maintenance slot persistence is UTC-only")
    return moment.astimezone(timezone.utc)


def to_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC to a datetime read back from storage.

    SQLite returns naive datetimes because it has no timezone type. They were
    written as UTC by :func:`_utc`, so the offset is known rather than assumed.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical_slot_id(value: str) -> str:
    """Reject anything the pure core would not have produced."""
    due_at_from_slot_id(value)
    return value


def _positive(duration: timedelta) -> timedelta:
    if not isinstance(duration, timedelta):
        raise TypeError(f"lease_duration must be a timedelta, got {type(duration).__name__}")
    if duration <= timedelta(0):
        raise ValueError("lease_duration must be positive; a zero lease cannot protect anything")
    return duration


def _insert_if_absent(session: Session):
    """``INSERT ... ON CONFLICT DO NOTHING`` for the dialect in use.

    ``ON CONFLICT`` is native to both backends this project supports. Anything
    else is refused rather than approximated, because falling back to
    select-then-insert here would reintroduce exactly the race the ``UNIQUE``
    constraint exists to settle.
    """
    table = MaintenanceSlot.__table__
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return postgresql_insert(table).on_conflict_do_nothing(index_elements=["slot_id"])
    if dialect == "sqlite":
        return sqlite_insert(table).on_conflict_do_nothing(index_elements=["slot_id"])
    raise RuntimeError(
        f"maintenance slot persistence has no conflict-safe insert for {dialect!r}"
    )


def read_slot(session: Session, slot_id: str) -> MaintenanceSlot | None:
    """The durable row for ``slot_id``, or ``None``.

    ``populate_existing`` forces the returned instance to be refreshed from the
    database. Without it, a session holding a previously loaded slot would hand
    back its cached attributes and quietly disagree with what the guarded
    ``UPDATE`` just wrote.
    """
    canonical = _canonical_slot_id(slot_id)
    return session.execute(
        select(MaintenanceSlot)
        .where(MaintenanceSlot.slot_id == canonical)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def ensure_slot(
    session: Session,
    due_at: datetime,
    *,
    logical_source: LogicalSource | str = LogicalSource.GITHUB_SCHEDULE,
    transport_event: str | None = None,
    as_of: datetime | None = None,
) -> str:
    """Make the durable DUE row for ``due_at`` exist, and return its slot id.

    Idempotent by construction: the canonical ``slot_id`` is derived from the due
    instant alone, and the insert is a no-op against the ``UNIQUE`` constraint if
    the row already exists. Calling it repeatedly for the same slot therefore
    yields one row, and the caller cannot observe which of the concurrent calls
    actually inserted it - which is correct, because none of them owns the slot.
    Ownership is decided later, by :func:`claim_slot`.

    ``as_of`` only stamps ``created_at``/``updated_at``; it never influences the
    slot id. It defaults to the current UTC time so production callers do not
    have to supply it, and tests pass it to stay deterministic.
    """
    due = _utc(due_at)
    canonical = canonical_slot_id(due)
    moment = _utc(as_of) if as_of is not None else datetime.now(timezone.utc)
    source = logical_source.value if isinstance(logical_source, LogicalSource) else str(logical_source)

    try:
        session.execute(
            _insert_if_absent(session).values(
                slot_id=canonical,
                due_at=due,
                state=SlotState.DUE.value,
                logical_source=source,
                transport_event=transport_event,
                owner=None,
                lease_until=None,
                workflow_run_id=None,
                attempt=0,
                failure_classification=None,
                created_at=moment,
                updated_at=moment,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return canonical


def _classify_lost_claim(
    session: Session,
    canonical: str,
    target: SlotState,
    claimable_states: tuple[SlotState, ...],
) -> ClaimOutcome:
    """Explain a claim that matched no row, without mutating anything.

    Read only, and only after the guarded ``UPDATE`` has already reported zero
    rows - so this can never be the step that decides the winner. It exists to
    separate ordinary contention, which is normal and expected, from a
    transition the state machine forbids, which is a defect, and from a missing
    slot, which is a bug at the call site.
    """
    try:
        row = read_slot(session, canonical)
        session.commit()
    except Exception:
        session.rollback()
        raise

    if row is None:
        raise SlotNotFound(f"no maintenance slot row for {canonical!r}")
    current = SlotState(row.state)

    if current in claimable_states:
        # The guard should have matched, so zero rows means the row changed
        # underneath the statement. Reported as a lost race, not re-read-and-retried.
        return ClaimOutcome(claimed=False, reason=f"lost the race while {current.value}")
    if current is target:
        # Another owner already holds the slot. Contention, not misconfiguration:
        # CLAIMED -> CLAIMED is a no-op the pure core rejects as a *transition*,
        # which says nothing about whether a second claim attempt is legitimate.
        return ClaimOutcome(
            claimed=False,
            owner=row.owner,
            lease_until=to_utc(row.lease_until),
            reason=f"already claimed by {row.owner}",
        )
    if not is_legal_transition(current, target):
        raise InvalidTransition(
            f"{current.value} -> {target.value} is not a legal transition"
        )
    return ClaimOutcome(claimed=False, reason=f"slot is {current.value}, not claimable")


def claim_slot(
    session: Session,
    slot_id: str,
    owner: str,
    lease_duration: timedelta,
    as_of: datetime,
    *,
    claimable_states: tuple[SlotState, ...] = CLAIMABLE_STATES,
) -> ClaimOutcome:
    """Atomically move a slot to ``CLAIMED`` under ``owner``.

    One statement, and the ``WHERE`` clause carries the whole precondition:

        UPDATE maintenance_slots
           SET state = 'CLAIMED', owner = :owner, lease_until = :lease_until
         WHERE slot_id = :slot_id
           AND state IN ('DUE', 'EXPIRED')

    A row count of 1 means this caller owns the slot. A row count of 0 means it
    does not, and the row is untouched: no owner overwritten, no lease extended,
    no second active execution. Because ``CLAIMED`` is never in the claimable
    set, an active lease is structurally unreachable rather than merely
    unlikely, and a competing owner cannot shorten or steal it.

    ``as_of`` is explicit rather than read from the clock, which is what makes
    lease expiry and recovery testable without sleeping.
    """
    canonical = _canonical_slot_id(slot_id)
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("owner is required; an unowned claim cannot be protected")
    moment = _utc(as_of)
    lease_until = moment + _positive(lease_duration)
    states = [state.value for state in claimable_states]

    try:
        result = session.execute(
            _guarded_claim(canonical, states)
            .values(
                state=SlotState.CLAIMED.value,
                owner=owner,
                lease_until=lease_until,
                updated_at=moment,
                attempt=_SLOT_TABLE.c.attempt + 1,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    if result.rowcount == 1:
        return ClaimOutcome(
            claimed=True, owner=owner, lease_until=lease_until, reason="claimed"
        )
    return _classify_lost_claim(session, canonical, SlotState.CLAIMED, claimable_states)


def expire_stale_claims(session: Session, as_of: datetime) -> int:
    """Expire claims whose lease has lapsed. Returns how many were expired.

    ``CLAIMED AND lease_until <= as_of`` becomes ``EXPIRED`` - never a silent
    return to ``DUE``. That distinction is the whole point: a lapsed lease is a
    fact an operator needs to see, and recovery from it stays visible in the
    record instead of looking like a slot that never ran.

    Idempotent: once expired the row no longer matches, so a second call at the
    same ``as_of`` reports zero and changes nothing. A claim whose ``lease_until``
    is still in the future does not match either, so an active lease is never
    disturbed by a sweep running concurrently with real work.
    """
    moment = _utc(as_of)
    try:
        result = session.execute(
            update(_SLOT_TABLE)
            .where(
                _SLOT_TABLE.c.state == SlotState.CLAIMED.value,
                _SLOT_TABLE.c.lease_until.is_not(None),
                _SLOT_TABLE.c.lease_until <= moment,
            )
            .values(state=SlotState.EXPIRED.value, updated_at=moment)
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return max(int(result.rowcount or 0), 0)


def recover_slot(
    session: Session,
    slot_id: str,
    owner: str,
    lease_duration: timedelta,
    as_of: datetime,
) -> ClaimOutcome:
    """Recover an ``EXPIRED`` slot: ``EXPIRED -> CLAIMED``.

    Deliberately not a second claim mechanism. It is :func:`claim_slot` with the
    claimable set narrowed to ``EXPIRED``, so the same conditional ``UPDATE`` and
    the same single-winner guarantee apply, and a concurrent recovery produces one
    winner and seven losses exactly as a concurrent first claim does.

    A slot that is not ``EXPIRED`` reports ``claimed=False`` rather than raising.
    Recovery is typically run as a sweep over candidate slots, and a slot that is
    still legitimately owned must not abort the sweep; the caller decides from the
    outcome whether that is a problem. Only a state the core says can never reach
    ``CLAIMED`` - ``SUCCEEDED``, ``FAILED``, ``DISPATCHED``, ``RUNNING`` - raises
    ``InvalidTransition``.
    """
    return claim_slot(
        session,
        slot_id,
        owner,
        lease_duration,
        as_of,
        claimable_states=(SlotState.EXPIRED,),
    )


def transition_slot(
    session: Session,
    slot_id: str,
    target: SlotState,
    *,
    as_of: datetime,
    workflow_run_id: str | None = None,
    failure_classification: str | None = None,
) -> MaintenanceSlot:
    """Move a slot to ``target``, refusing any transition the core forbids.

    The permitted current states are read out of the pure core's
    ``LEGAL_TRANSITIONS`` rather than restated here, and they become the
    ``WHERE`` clause of a single conditional ``UPDATE``. So the database, not this
    function, decides whether the transition was legal, and two actors moving the
    same slot cannot both succeed.
    """
    canonical = _canonical_slot_id(slot_id)
    if not isinstance(target, SlotState):
        raise TypeError(f"target must be a SlotState, got {type(target).__name__}")
    moment = _utc(as_of)
    predecessors = [
        current.value for current, allowed in LEGAL_TRANSITIONS.items() if target in allowed
    ]
    if not predecessors:
        raise InvalidTransition(f"{target.value} is a terminal state; nothing follows it")

    values: dict = {"state": target.value, "updated_at": moment}
    if workflow_run_id is not None:
        values["workflow_run_id"] = workflow_run_id
    if failure_classification is not None:
        values["failure_classification"] = failure_classification

    try:
        result = session.execute(
            update(_SLOT_TABLE)
            .where(
                _SLOT_TABLE.c.slot_id == canonical,
                _SLOT_TABLE.c.state.in_(predecessors),
            )
            .values(values)
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    if result.rowcount != 1:
        row = read_slot(session, canonical)
        session.commit()
        if row is None:
            raise SlotNotFound(f"no maintenance slot row for {canonical!r}")
        current = SlotState(row.state)
        if current.value in predecessors:
            raise SlotConflict(
                f"{canonical} was still {current.value} but the guarded update matched "
                "no row; the statement lost a race and changed nothing"
            )
        raise InvalidTransition(
            f"{current.value} -> {target.value} is not a legal transition"
        )
    return read_slot(session, canonical)