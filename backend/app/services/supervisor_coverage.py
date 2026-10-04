"""Coverage: guaranteeing every scholarship has a discovery state.

The product requirement is that every scholarship is connected to supervisor
discovery. The honest way to satisfy that is not to give every scholarship a
professor - it is to give every scholarship an *answer*. A record that has never
been searched and a record that was searched and found nothing are different
facts, and a system that stores only the second one will eventually present
"nothing found" as "nothing exists".

So a coverage row exists for every scholarship, is created before any search runs,
and defaults to ``search_pending``: a state that asserts nothing. The backfill
below is the operation that makes the invariant true, and it is idempotent, so
running it twice changes nothing and a partially completed run can simply be
re-run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..models_supervisor import ScholarshipProfessorLink, ScholarshipSupervisorCoverage
from .supervisor_status import (
    PUBLIC_RELATIONSHIP_STATUSES,
    RelationshipVerificationStatus,
    SupervisorCoverageStatus,
)

logger = logging.getLogger(__name__)

#: Bounded so a backfill over a large catalogue makes bounded progress per call
#: and can be interrupted without losing its place.
DEFAULT_BATCH_SIZE = 200


@dataclass
class CoverageBackfillResult:
    created: int
    already_present: int
    scanned: int
    total_scholarships: int

    @property
    def covered_everything(self) -> bool:
        return self.created + self.already_present >= self.total_scholarships


def ensure_coverage_row(
    db: Session,
    scholarship_id: int,
    status: str = str(SupervisorCoverageStatus.SEARCH_PENDING),
) -> tuple[ScholarshipSupervisorCoverage, bool]:
    """Return the coverage row for a scholarship, creating it if absent.

    Returns ``(row, created)`` so callers can tell a fresh insert from an existing
    row without a second query.

    The unique constraint on ``scholarship_id`` is the real guarantee here. The
    existence check is an optimisation; if two callers race, one insert fails and
    the caller retries against the row the winner created.
    """
    row = db.execute(
        select(ScholarshipSupervisorCoverage).where(
            ScholarshipSupervisorCoverage.scholarship_id == scholarship_id
        )
    ).scalar_one_or_none()
    if row is not None:
        return row, False
    row = ScholarshipSupervisorCoverage(
        scholarship_id=scholarship_id,
        status=status,
        verified_supervisor_count=0,
        evidence_state="not_collected",
    )
    db.add(row)
    db.flush()
    return row, True


def backfill_coverage(
    db: Session,
    batch_size: int = DEFAULT_BATCH_SIZE,
    include_archived: bool = True,
) -> CoverageBackfillResult:
    """Create a coverage row for every scholarship that lacks one.

    Archived records are included by default. A scholarship that leaves the
    catalogue keeps its coverage row, because coverage is a record of what was
    searched rather than of what is currently offered, and a row that disappeared
    would make the coverage count ambiguous against the catalogue count.

    Bounded by ``batch_size`` per call so a very large catalogue is backfilled by
    repeated calls instead of one long transaction, which is what has previously
    gone wrong on this database.
    """
    total = db.execute(select(func.count(Scholarship.id))).scalar_one()
    # Only rows that lack coverage. Selecting the lowest ids unconditionally
    # would re-read the same already-covered batch forever and never advance past
    # the first page, which is what makes a backfill look stuck.
    query = (
        select(Scholarship.id)
        .outerjoin(
            ScholarshipSupervisorCoverage,
            ScholarshipSupervisorCoverage.scholarship_id == Scholarship.id,
        )
        .where(ScholarshipSupervisorCoverage.id.is_(None))
        .order_by(Scholarship.id)
    )
    if not include_archived:
        query = query.where(Scholarship.is_archived.is_(False))
    ids = [row[0] for row in db.execute(query.limit(batch_size)).all()]

    created = 0
    already = 0
    for scholarship_id in ids:
        _, was_created = ensure_coverage_row(db, scholarship_id)
        if was_created:
            created += 1
        else:
            already += 1
    db.commit()

    logger.info(
        "Supervisor coverage backfill: scanned=%s created=%s already_present=%s total=%s",
        len(ids),
        created,
        already,
        total,
    )
    return CoverageBackfillResult(
        created=created,
        already_present=already,
        scanned=len(ids),
        total_scholarships=total,
    )


def count_publishable_links(db: Session, scholarship_id: int) -> int:
    """Count relationships that may be shown publicly for one scholarship."""
    return db.execute(
        select(func.count(ScholarshipProfessorLink.id)).where(
            ScholarshipProfessorLink.scholarship_id == scholarship_id,
            ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
        )
    ).scalar_one()


def recompute_coverage(
    db: Session,
    scholarship_id: int,
    searched: bool = True,
    blocked: bool = False,
) -> ScholarshipSupervisorCoverage:
    """Recompute a coverage row from its links and store the result.

    The status is derived, never set by the caller, so two runs that disagree
    about the outcome still converge on the same answer.

    ``searched=False`` means discovery did not get far enough to conclude
    anything, and the row is left ``search_pending`` no matter what the link count
    is. Deriving "no supervisors found" from a run that never reached a faculty
    page is the exact false negative this module exists to prevent.
    """
    row, _ = ensure_coverage_row(db, scholarship_id)
    publishable = count_publishable_links(db, scholarship_id)

    if publishable > 0:
        row.status = str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
        row.verified_supervisor_count = publishable
        row.evidence_state = "complete"
        row.last_error_summary = None
    elif blocked:
        # Checked before "not searched". A source that refused us is a more useful
        # answer than "pending": it says the search was attempted and is worth
        # retrying, which is what an operator needs in order to act.
        row.status = str(SupervisorCoverageStatus.SOURCE_BLOCKED)
        row.verified_supervisor_count = publishable
    elif not searched:
        row.status = str(SupervisorCoverageStatus.SEARCH_PENDING)
        row.verified_supervisor_count = publishable
    else:
        row.status = str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
        row.verified_supervisor_count = 0
        row.evidence_state = "complete"
        row.last_error_summary = None

    row.verified_supervisor_count = publishable
    db.commit()
    db.refresh(row)
    return row


def mark_not_applicable(db: Session, scholarship_id: int, reason: str) -> None:
    """Record that supervisor discovery cannot apply to this record.

    Reserved for scholarships with no supervising institution or degree programme
    attached - a pure funding award, for example. It is deliberately explicit
    rather than inferred, because "not applicable" and "we could not check" are
    different answers and conflating them would overstate what is known.
    """
    row, _ = ensure_coverage_row(db, scholarship_id)
    row.status = str(SupervisorCoverageStatus.NOT_APPLICABLE)
    row.verified_supervisor_count = 0
    row.evidence_state = "complete"
    row.last_error_summary = reason[:500]
    db.commit()


def supervisor_universe_report(db: Session) -> dict:
    """Measure coverage against the canonical public Supervisor universe.

    The universe is deliberately *not* "every row in the table". It is the
    catalogue universe Count Intelligence already defines - every record
    ``public_visibility_conditions()`` permits to be shown - so that "every
    scholarship has supervisor discovery" is a claim about the same population
    the catalogue total describes, and cannot quietly become a claim about
    archived or quarantined rows instead.

    Backfill covers a superset of this universe (every row, archived included),
    which is safe because coverage is not a publication decision. The public API
    applies the visibility predicate independently, so a coverage row can never
    make a hidden scholarship readable. That independence is asserted separately
    rather than assumed here.
    """
    from ..repositories.scholarships import public_visibility_conditions

    universe_ids = [
        row[0]
        for row in db.execute(
            select(Scholarship.id).where(*public_visibility_conditions()).order_by(Scholarship.id)
        ).all()
    ]
    covered_ids = {
        row[0]
        for row in db.execute(select(ScholarshipSupervisorCoverage.scholarship_id)).all()
    }

    uncovered = [sid for sid in universe_ids if sid not in covered_ids]
    covered_in_universe = sum(1 for sid in universe_ids if sid in covered_ids)
    # Coverage rows for records outside the universe are counted, not deleted:
    # they are historical facts about what was searched.
    outside_universe = sorted(covered_ids - set(universe_ids))

    return {
        "universe": "CATALOGUE",
        "universe_predicate_source": (
            "app.repositories.scholarships.public_visibility_conditions"
        ),
        "universe_size": len(universe_ids),
        "covered_in_universe": covered_in_universe,
        "uncovered_in_universe": uncovered,
        "coverage_rows_total": len(covered_ids),
        "coverage_rows_outside_universe": outside_universe,
        "invariant_holds": not uncovered,
    }


def coverage_invariant_report(db: Session) -> dict:
    """Measure the coverage invariant, for the data-quality report.

    Reports both totals and any scholarship that lacks a row, because a claim that
    "every scholarship is covered" is only worth what this function can prove.
    """
    total_scholarships = db.execute(select(func.count(Scholarship.id))).scalar_one()
    coverage_rows = db.execute(
        select(func.count(ScholarshipSupervisorCoverage.scholarship_id))
    ).scalar_one()
    missing_ids = [
        row[0]
        for row in db.execute(
            select(Scholarship.id)
            .outerjoin(
                ScholarshipSupervisorCoverage,
                ScholarshipSupervisorCoverage.scholarship_id == Scholarship.id,
            )
            .where(ScholarshipSupervisorCoverage.id.is_(None))
            .order_by(Scholarship.id)
        ).all()
    ]

    by_status: dict[str, int] = {}
    for status_value, count in db.execute(
        select(ScholarshipSupervisorCoverage.status, func.count(ScholarshipSupervisorCoverage.id)).group_by(
            ScholarshipSupervisorCoverage.status
        )
    ).all():
        by_status[str(status_value)] = count

    with_supervisors = db.execute(
        select(func.count(ScholarshipSupervisorCoverage.id)).where(
            ScholarshipSupervisorCoverage.verified_supervisor_count > 0
        )
    ).scalar_one()

    # A correlated subquery so the stored count is compared against the rows that
    # actually exist for the same scholarship, rather than being recomputed per
    # row in Python.
    publishable_for_row = (
        select(func.count(ScholarshipProfessorLink.id))
        .where(
            ScholarshipProfessorLink.scholarship_id
            == ScholarshipSupervisorCoverage.scholarship_id,
            ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
        )
        .correlate(ScholarshipSupervisorCoverage)
        .scalar_subquery()
    )
    drifted = [
        row[0]
        for row in db.execute(
            select(ScholarshipSupervisorCoverage.scholarship_id).where(
                ScholarshipSupervisorCoverage.verified_supervisor_count != publishable_for_row
            )
        ).all()
    ]

    return {
        "total_scholarships": total_scholarships,
        "coverage_rows": coverage_rows,
        "missing_coverage_ids": missing_ids,
        "by_status": by_status,
        "scholarships_with_verified_supervisors": with_supervisors,
        "scholarships_without_verified_supervisors": total_scholarships - with_supervisors,
        "count_drift_ids": drifted,
        "invariant_holds": not missing_ids and not drifted,
    }


def orphaned_links(db: Session) -> list[int]:
    """Return scholarship ids whose verified count disagrees with their links.

    Named separately because a count that has drifted from the rows behind it is a
    public-facing lie even when every individual row is correct.
    """
    drift: list[int] = []
    for (scholarship_id,) in db.execute(select(ScholarshipSupervisorCoverage.scholarship_id)).all():
        row = db.execute(
            select(ScholarshipSupervisorCoverage.verified_supervisor_count).where(
                ScholarshipSupervisorCoverage.scholarship_id == scholarship_id
            )
        ).scalar_one()
        if row != count_publishable_links(db, scholarship_id):
            drift.append(scholarship_id)
    return drift


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "CoverageBackfillResult",
    "backfill_coverage",
    "coverage_invariant_report",
    "count_publishable_links",
    "ensure_coverage_row",
    "mark_not_applicable",
    "orphaned_links",
    "recompute_coverage",
]