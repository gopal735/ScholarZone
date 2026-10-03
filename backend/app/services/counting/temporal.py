"""Time-aware counts, built on the snapshot history that already exists.

ScholarZone already stores a bitemporal history of every scholarship:
``scholarship_snapshots`` carries ``valid_from``, ``valid_to``, ``is_current`` and a
``version_id``, and ``temporal_versioning`` owns the write and read paths. So
point-in-time counting needs **no schema change and no new table**. This module
reads what is there.

The governing rule is the strict one: if the historical state does not exist, the
answer is ``NOT_AVAILABLE``. Never a reconstructed history.

That rule is not cautiousness for its own sake. A snapshot table only contains rows
for records that were *changed* after the feature existed. Asking for the catalogue
as it stood in 2024 and finding nothing yields two possible truths - "the catalogue
was empty" and "we were not recording" - and they are indistinguishable. Publishing
a trend across them would be a straight line of invented history, presented with
the authority of a measurement. The only honest output is to say the data is not
available and name the coverage that would make it available.

Reconstruction is delegated to the existing
:mod:`app.services.temporal_versioning`, whose ``get_state_at`` is the single
definition of "what did this record look like at that moment". Reimplementing point
in time here would produce two answers for one question.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..matching.config import (
    DEADLINE_SEMANTICS_VERSION,
    FIELD_TAXONOMY_VERSION,
    FIT_ENGINE_VERSION,
    SCORING_CONFIG_VERSION,
)
from .contract import COUNT_CONTRACT_VERSION
from .types import CountSnapshot, CountTrend, CountTrendPoint


#: Statuses that mean "this figure could not be produced".
NOT_AVAILABLE = "NOT_AVAILABLE"
AVAILABLE = "AVAILABLE"

#: A trend needs at least this many real observations to be a trend. One point is a
#: measurement; two points are a change. Neither is a trend, and drawing a line
#: through them would read as a direction the data does not show.
MIN_TREND_POINTS = 3

#: The smallest period between snapshots that can be treated as a distinct
#: observation. Snapshots are written on change, so several can share a day; without
#: this floor a burst of edits on one day would render as a month of trend.
MIN_SNAPSHOT_INTERVAL_DAYS = 1


def _naive_utc(moment: datetime) -> datetime:
    """Convert to the naive UTC form the snapshot table stores.

    ``temporal_versioning`` strips tzinfo before writing, so an aware datetime
    compared against those rows silently matches nothing. Normalising here is what
    makes an as-of query return the versions that actually exist.
    """
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def snapshot_coverage(session: Session) -> dict[str, int]:
    """How much history actually exists.

    Published with every time-aware response so a reader can see the evidence
    behind any trend, rather than having to trust that one exists.
    """
    from ...models import Scholarship, ScholarshipSnapshot

    total_records = session.scalar(select(func.count(Scholarship.id))) or 0
    snapshot_rows = session.scalar(select(func.count(ScholarshipSnapshot.id))) or 0
    distinct_records = (
        session.scalar(select(func.count(func.distinct(ScholarshipSnapshot.scholarship_id))))
        or 0
    )
    earliest = session.scalar(select(func.min(ScholarshipSnapshot.valid_from)))
    latest = session.scalar(select(func.max(ScholarshipSnapshot.valid_from)))

    return {
        "records_without_any_snapshot": max(total_records - distinct_records, 0),
        "snapshot_rows": int(snapshot_rows),
        "records_with_history": int(distinct_records),
        "earliest_snapshot": earliest.isoformat() if earliest else None,
        "latest_snapshot": latest.isoformat() if latest else None,
    }


def current_snapshot(as_of: date, summary: dict | None = None) -> CountSnapshot:
    """A snapshot of the counts as they stand at ``as_of``.

    Reproducible by construction: the same date and the same stored data produce
    the same snapshot, because nothing here reads a clock of its own.
    """
    return CountSnapshot(
        availability=AVAILABLE,
        as_of=as_of.isoformat(),
        engine_version=FIT_ENGINE_VERSION,
        scoring_config_version=SCORING_CONFIG_VERSION,
        field_taxonomy_version=FIELD_TAXONOMY_VERSION,
        deadline_semantics_version=DEADLINE_SEMANTICS_VERSION,
        count_contract_version=COUNT_CONTRACT_VERSION,
        summary=summary,
        unavailable_reason="",
    )


def snapshot_as_of(session: Session, as_of: datetime) -> CountSnapshot:
    """The catalogue as it stood at ``as_of``, or ``NOT_AVAILABLE``.

    Delegates reconstruction to the existing temporal versioning service rather than
    re-deriving point-in-time state, so there is exactly one answer to "what did
    this record look like then".
    """
    from ..temporal_versioning import get_state_at

    from ...models import Scholarship

    moment = _naive_utc(as_of)

    from ...models import Scholarship

    scholarship_ids = list(
        session.scalars(select(Scholarship.id).order_by(Scholarship.id))
    )
    if not scholarship_ids:
        return CountSnapshot(
            availability=NOT_AVAILABLE,
            as_of=moment.isoformat(),
            count_contract_version=COUNT_CONTRACT_VERSION,
            unavailable_reason="The catalogue is empty, so there is no state to reconstruct.",
        )

    with_state = 0
    for scholarship_id in scholarship_ids:
        reconstruction = get_state_at(session, scholarship_id, moment)
        if reconstruction.found and reconstruction.state:
            with_state += 1

    if with_state == 0:
        coverage = snapshot_coverage(session)
        return CountSnapshot(
            availability=NOT_AVAILABLE,
            as_of=moment.isoformat(),
            count_contract_version=COUNT_CONTRACT_VERSION,
            unavailable_reason=(
                "No stored snapshot exists at or before this date. Snapshots are "
                "written when a record changes, so history begins at the first change "
                f"after the feature was enabled"
                + (
                    f" ({coverage['earliest_snapshot']})."
                    if coverage["earliest_snapshot"]
                    else "."
                )
                + " Reconstructing a catalogue from before that would be inventing history."
            ),
        )

    return CountSnapshot(
        availability=AVAILABLE,
        as_of=moment.isoformat(),
        engine_version=FIT_ENGINE_VERSION,
        scoring_config_version=SCORING_CONFIG_VERSION,
        field_taxonomy_version=FIELD_TAXONOMY_VERSION,
        deadline_semantics_version=DEADLINE_SEMANTICS_VERSION,
        count_contract_version=COUNT_CONTRACT_VERSION,
        summary={
            "records_total": len(scholarship_ids),
            "records_reconstructable_at_as_of": with_state,
        },
        facets=None,
        unavailable_reason="",
    )


def count_trend(
    observations: Sequence[tuple[datetime, int]],
    *,
    metric: str,
    dimension: str | None = None,
    min_points: int = MIN_TREND_POINTS,
) -> CountTrend:
    """A trend over real observations only.

    Every point must be a stored measurement. Snapshots written on the same day are
    collapsed to one, because a burst of edits is one moment in time, not a series
    of them. Fewer than :data:`MIN_TREND_POINTS` distinct observations yields
    ``NOT_AVAILABLE`` rather than a line through the points we happen to have: a
    two-point "trend" reads as a direction, and two measurements do not establish
    one.
    """
    collapsed: dict[str, int] = {}
    for moment, value in observations:
        key = moment.date().isoformat() if isinstance(moment, datetime) else str(moment)
        # Later observation on the same day wins, so the day's final value is used.
        collapsed[key] = value

    if len(collapsed) < min_points:
        return CountTrend(
            metric=metric,
            availability=NOT_AVAILABLE,
            dimension=dimension,
            unavailable_reason=(
                f"{len(collapsed)} distinct observation"
                f"{'' if len(collapsed) == 1 else 's'} available; a trend needs at least "
                f"{min_points}. Drawn from fewer points it would imply a direction the "
                "evidence does not show."
            ),
            note="Only real stored observations are used. No trend is interpolated.",
        )

    ordered = sorted(collapsed.items())
    points = [
        CountTrendPoint(as_of=key, value=value, is_historical=True)
        for key, value in ordered
    ]
    first = ordered[0][1]
    last = ordered[-1][1]
    change = last - first
    percent = round((change / first) * 100, 1) if first else None

    return CountTrend(
        metric=metric,
        availability=AVAILABLE,
        dimension=dimension,
        points=points,
        change=change,
        change_percent=percent,
        note=(
            "Every point is a stored measurement. Nothing is interpolated, smoothed "
            "or modelled."
        ),
    )


__all__ = [
    "AVAILABLE",
    "MIN_SNAPSHOT_INTERVAL_DAYS",
    "MIN_TREND_POINTS",
    "NOT_AVAILABLE",
    "count_trend",
    "current_snapshot",
    "snapshot_as_of",
    "snapshot_coverage",
]