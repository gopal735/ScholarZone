"""Durable round-robin cursor for autonomous maintenance stages.

The scheduled worker used to ask the catalogue for ``ORDER BY id LIMIT 60`` with
no notion of where the previous run stopped. Because selection was deterministic
and there was no cursor, every twelve-hour run re-enriched the same first sixty
records and the remaining four hundred never advanced. The job reported success
while making no cumulative progress - the worst possible combination, because
the metrics looked healthy.

This module replaces that with a one-row-per-stream cursor held in the same
PostgreSQL database as the work itself.

Why the database and not the Actions cache
-----------------------------------------
A cache is scoped to a branch, is evicted without warning, and is not written
on a failed run. Any of those would rewind the cursor and silently re-do work
that has already been paid for. The database survives runner replacement,
workflow cancellation, manual dispatch, and a crash mid-run, and it is the same
transaction boundary as the data being maintained.

Round-robin, not "never again"
------------------------------
``last_id`` moves forward and wraps to zero when it reaches the end of the
catalogue. That makes a fixed number of consecutive runs cover the whole
catalogue exactly once, so every record is revisited on a bounded cadence
rather than starved forever. Records that genuinely need revisiting sooner are
handled by the verification stage, which selects by staleness priority rather
than by position.

Idempotency
-----------
Selection is a pure function of ``(last_id, catalogue)``, and the caller only
commits the new cursor position after the work for that batch has finished. A
failed stage therefore re-selects the same batch on the next run instead of
skipping records that were never processed. Selection never mutates a
scholarship row, so calling it twice changes nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from ..models import MaintenanceCursor, Scholarship

logger = logging.getLogger(__name__)

# Quarantined rows are held back from the public catalogue, so maintenance
# should not spend fetches trying to enrich something the API will not serve.
QUARANTINED_STATUS = "quarantined"


@dataclass(frozen=True)
class CursorBatch:
    """A selected batch plus the cursor bookkeeping that produced it."""

    name: str
    ids: list[int]
    start_after: int
    last_id: int
    wrapped: bool
    cycles_completed: int
    total_visited: int
    skipped_complete: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.ids

    def as_dict(self) -> dict[str, object]:
        return {
            "cursor": self.name,
            "selected": len(self.ids),
            "start_after": self.start_after,
            "last_id": self.last_id,
            "wrapped": self.wrapped,
            "cycles_completed": self.cycles_completed,
            "total_visited": self.total_visited,
            "skipped_complete": self.skipped_complete,
        }


def _is_complete(session: Session, scholarship: Scholarship) -> bool:
    """True when every canonical fact field already holds a value.

    Used to avoid paying for a network fetch on a record that has nothing left
    to gain. The list mirrors the acceptance audit's canonical fields; if the
    two ever disagree the audit is the authority, so this stays a cheap
    best-effort filter rather than a source of truth.
    """
    checks = (
        scholarship.description,
        scholarship.deadline_display,
        scholarship.notes,
        scholarship.requirements,
        scholarship.program_type,
        scholarship.selection_notes,
        scholarship.application_period,
        scholarship.best_fit,
        scholarship.official_updates_url,
        scholarship.english_requirement,
        scholarship.catalogue_url,
        scholarship.eligibility_summary,
    )
    if any(not value for value in checks):
        return False
    return all(
        list(value or [])
        for value in (
            scholarship.eligibility,
            scholarship.benefits,
            scholarship.coverage,
            scholarship.documents,
            scholarship.application_method,
        )
    )


class MaintenanceCursorStore:
    """Read and advance the durable maintenance cursors."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    # -- cursor state -------------------------------------------------

    def get_state(self, name: str) -> MaintenanceCursor:
        """Return the cursor row, creating it on first use."""
        session = self._session_factory()
        try:
            cursor = session.get(MaintenanceCursor, name)
            if cursor is None:
                cursor = MaintenanceCursor(name=name, last_id=0, cycles_completed=0, total_visited=0)
                session.add(cursor)
                session.commit()
                session.refresh(cursor)
                session.expunge(cursor)
            return cursor
        finally:
            session.close()

    def state_as_dict(self, name: str) -> dict[str, object]:
        cursor = self.get_state(name)
        return {
            "cursor": cursor.name,
            "last_id": cursor.last_id,
            "cycles_completed": cursor.cycles_completed,
            "total_visited": cursor.total_visited,
            "cycle_started_at": (
                cursor.cycle_started_at.isoformat() if cursor.cycle_started_at else None
            ),
            "updated_at": cursor.updated_at.isoformat() if cursor.updated_at else None,
        }

    def reset(self, name: str) -> None:
        session = self._session_factory()
        try:
            cursor = session.get(MaintenanceCursor, name)
            if cursor is not None:
                cursor.last_id = 0
                cursor.cycles_completed = 0
                cursor.total_visited = 0
                cursor.cycle_started_at = None
                session.commit()
        finally:
            session.close()

    # -- selection ----------------------------------------------------

    def select_batch(
        self,
        name: str,
        *,
        limit: int,
        skip_complete: bool = True,
    ) -> CursorBatch:
        """Choose the next ``limit`` record ids for this stream.

        Pure with respect to scholarship rows: nothing is written here. The
        caller commits the new position with :meth:`advance` only after the work
        has actually run, so a crash re-selects the same batch instead of
        losing it.
        """
        limit = max(1, int(limit))
        cursor = self.get_state(name)
        start_after = cursor.last_id or 0
        cycles_completed = cursor.cycles_completed
        total_visited = cursor.total_visited
        wrapped = False

        session = self._session_factory()
        try:
            rows, skipped = self._fetch(session, start_after, limit, skip_complete)
            if not rows and start_after > 0:
                # The catalogue is exhausted: begin the next cycle rather than
                # returning an empty run forever. This is what turns repeated
                # scheduled runs into a full sweep instead of a single pass.
                wrapped = True
                cycles_completed += 1
                rows, wrapped_skipped = self._fetch(session, 0, limit, skip_complete)
                skipped += wrapped_skipped
                start_after = 0

            if not rows:
                return CursorBatch(
                    name=name,
                    ids=[],
                    start_after=start_after,
                    last_id=start_after,
                    wrapped=wrapped,
                    cycles_completed=cycles_completed,
                    total_visited=total_visited,
                    skipped_complete=skipped,
                )

            ids = [row.id for row in rows]
            return CursorBatch(
                name=name,
                ids=ids,
                start_after=start_after,
                last_id=ids[-1],
                wrapped=wrapped,
                cycles_completed=cycles_completed,
                total_visited=total_visited + len(ids),
                skipped_complete=skipped,
            )
        finally:
            session.close()

    def _fetch(
        self,
        session: Session,
        start_after: int,
        limit: int,
        skip_complete: bool,
    ) -> tuple[list[Scholarship], int]:
        """Load a bounded window of candidates above ``start_after``.

        Returns the records worth spending a fetch on, plus how many complete
        records were passed over. The window is deliberately wider than
        ``limit`` when complete records are filtered out, so a run still
        returns a full batch instead of shrinking towards zero as the
        catalogue fills in.
        """
        window = limit * 4 if skip_complete else limit
        stmt = (
            select(Scholarship)
            .where(Scholarship.id > start_after)
            .where(Scholarship.verification_status != QUARANTINED_STATUS)
            .order_by(Scholarship.id)
            .limit(window)
        )
        candidates = list(session.scalars(stmt).all())
        rows: list[Scholarship] = []
        skipped = 0
        for scholarship in candidates:
            if skip_complete and _is_complete(session, scholarship):
                skipped += 1
                continue
            rows.append(scholarship)
            if len(rows) >= limit:
                break
        return rows, skipped

    # -- commit -------------------------------------------------------

    def advance(
        self,
        name: str,
        batch: CursorBatch,
        *,
        started_at: datetime | None = None,
    ) -> None:
        """Persist the position after the batch has been processed."""
        if batch.is_empty:
            return
        session = self._session_factory()
        try:
            cursor = session.get(MaintenanceCursor, name)
            if cursor is None:
                cursor = MaintenanceCursor(name=name)
                session.add(cursor)
            cursor.last_id = batch.last_id
            cursor.cycles_completed = batch.cycles_completed
            cursor.total_visited = batch.total_visited
            if batch.wrapped or cursor.cycle_started_at is None:
                cursor.cycle_started_at = started_at or datetime.now(timezone.utc)
            cursor.updated_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def advance_to(self, name: str, last_id: int, *, cycles_completed: int | None = None) -> None:
        """Move the cursor to an explicit position (used by manual operators)."""
        session = self._session_factory()
        try:
            cursor = session.get(MaintenanceCursor, name)
            if cursor is None:
                cursor = MaintenanceCursor(name=name)
                session.add(cursor)
            cursor.last_id = int(last_id)
            if cycles_completed is not None:
                cursor.cycles_completed = cycles_completed
            cursor.updated_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def catalogue_size(self) -> int:
        session = self._session_factory()
        try:
            return int(
                session.scalar(
                    select(func.count(Scholarship.id)).where(
                        Scholarship.verification_status != QUARANTINED_STATUS
                    )
                )
                or 0
            )
        finally:
            session.close()
