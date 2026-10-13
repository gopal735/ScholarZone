"""All-scholarship supervisor discovery: bounded, resumable, auditable, dry-run.

The one-scholarship proof workflow stays exactly as it is - one route, one id,
one run, ``app.routers.supervisor_internal``. This module is the *catalogue*
batch that the proof workflow cannot be, and it is built around one question
being asked honestly: what does ScholarZone actually know about supervisors for
**every** public scholarship?

The answer is not "every scholarship has a professor". Most records do not, and
most never will: a government scheme, a language course or a professional
development award has no research supervisor. What every record gets is an
explicit, truthful state - verified supervisors, a completed negative, blocked,
pending, rendering-required, or not applicable with a quoted reason - plus, for
records where supervision genuinely does not apply, the official office that
administers the award.

Seven properties, each of which is an absence of code as much as a feature:

**Manual.** Nothing imports this module on a request path and nothing schedules
it. The entry point is a CLI script an operator runs on purpose, and the
one-scholarship trigger is untouched.

**Bounded.** ``limit`` caps one run, the worker's own page and candidate budgets
cap each scholarship, and the run stops at the limit rather than working
through the night.

**Resumable.** Selection is coverage-driven - records that have never been
searched, plus any inconclusive states the operator asks to retry - ordered by
id, with an ``after_id`` cursor persisted after every item. An interrupted run
resumes from the last completed id, and re-processing an item is a no-op.

**Idempotent.** Every write is an upsert keyed on a unique constraint and the
coverage row is recomputed from the links that exist, so a second run of the
same scholarship updates rows rather than multiplying them.

**Rate-limited.** All network traffic goes through
:func:`app.services.supervisor_discovery.polite_fetch`, which enforces robots
and a per-host delay. The batch adds no fetch path of its own, and defaults to
a single worker so one university is not approached from several threads at
once. The per-host limiter is lock-protected, so the optional workers above one
serialise rather than burst.

**Auditable.** Every item appends one JSON line - run id, scholarship, previous
status, outcome, counts, detail - so a run can be reconstructed from the log
without querying the database.

**Dry-run.** ``dry_run=True`` collects and reports everything and persists
nothing: no professor, no link, no evidence, no availability, no contact, no
coverage change, no cursor, no audit line. The report names the status each
record *would* move to, so a reviewer can approve a run before it spends a
request.
"""

from __future__ import annotations

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .supervisor_coverage import mark_not_applicable
from .supervisor_discovery import collect_supervisor_plan, persist_supervisor_plan
from .supervisor_status import SupervisorCoverageStatus

logger = logging.getLogger(__name__)

#: Default selection: records discovery has never examined. The states that
#: *were* examined are opt-in through ``include_statuses`` so a routine run
#: cannot silently burn its request budget re-reading universities that are
#: blocked or client-side until an operator decides to retry them.
DEFAULT_INCLUDE_STATUSES: frozenset[str] = frozenset(
    {str(SupervisorCoverageStatus.SEARCH_PENDING)}
)

#: How many records one run touches by default. Bounded so a run finishes and
#: reports; a catalogue is finished by repeated runs, not by one long one.
DEFAULT_LIMIT = 25

#: Workers. One by default: politeness is a correctness property here, and the
#: per-host delay inside ``polite_fetch`` already serialises requests to the
#: same university. Higher values spread *different* universities across
#: threads; they never increase the rate against one university.
DEFAULT_WORKERS = 1
MAX_WORKERS = 8


class _Scholarship(Protocol):
    """The shape the batch reads; satisfied by :class:`app.models.Scholarship`."""

    id: int
    title: str
    degree: str | None
    program_type: str | None
    is_archived: bool


@dataclass(frozen=True)
class BatchOptions:
    """Everything one batch run is allowed to be told."""

    limit: int = DEFAULT_LIMIT
    dry_run: bool = False
    include_archived: bool = False
    #: Extra coverage states to (re)process, beyond the never-searched default.
    include_statuses: frozenset[str] = frozenset()
    #: Resume strictly after this scholarship id. Normally read from the state
    #: file rather than passed by hand.
    after_id: int | None = None
    workers: int = DEFAULT_WORKERS
    #: Whether to look for an official administrative contact on records that
    #: end with no supervisor. One extra polite read of the awarding page,
    #: only for records where it is the honest answer.
    collect_contacts: bool = True
    audit_path: Path | None = None
    state_path: Path | None = None

    def selected_statuses(self) -> frozenset[str]:
        return DEFAULT_INCLUDE_STATUSES | frozenset(self.include_statuses)


@dataclass
class BatchItemResult:
    """What one item did, or would do in a dry run."""

    scholarship_id: int
    title: str
    previous_status: str
    outcome_status: str
    detail: str | None = None
    pages_fetched: int = 0
    examined: int = 0
    approved: int = 0
    professors_written: int = 0
    not_applicable: bool = False
    contact_collected: bool = False
    contact_url: str | None = None


@dataclass
class BatchReport:
    """The complete result of one run, dry or real."""

    run_id: str
    started_at: str
    finished_at: str
    dry_run: bool
    requested_limit: int
    items: list[BatchItemResult] = field(default_factory=list)
    #: The id to resume after, or ``None`` when the selection was exhausted.
    next_cursor: int | None = None
    selection_exhausted: bool = True

    @property
    def totals(self) -> dict[str, int]:
        by_status: dict[str, int] = {}
        for item in self.items:
            by_status[item.outcome_status] = by_status.get(item.outcome_status, 0) + 1
        return {
            "processed": len(self.items),
            "professors_written": sum(item.professors_written for item in self.items),
            "verified_supervisors": sum(
                1
                for item in self.items
                if item.outcome_status == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
            ),
            "not_applicable": sum(1 for item in self.items if item.not_applicable),
            "contacts_collected": sum(1 for item in self.items if item.contact_collected),
            **{f"status:{key}": value for key, value in sorted(by_status.items())},
        }

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "requested_limit": self.requested_limit,
            "next_cursor": self.next_cursor,
            "selection_exhausted": self.selection_exhausted,
            "totals": self.totals,
            "items": [
                {
                    "scholarship_id": item.scholarship_id,
                    "title": item.title,
                    "previous_status": item.previous_status,
                    "outcome_status": item.outcome_status,
                    "detail": item.detail,
                    "pages_fetched": item.pages_fetched,
                    "examined": item.examined,
                    "approved": item.approved,
                    "professors_written": item.professors_written,
                    "not_applicable": item.not_applicable,
                    "contact_collected": item.contact_collected,
                    "contact_url": item.contact_url,
                }
                for item in self.items
            ],
        }


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def select_batch_candidates(db, options: BatchOptions) -> list:
    """Return the scholarships this run should process, in id order.

    Coverage-driven: a record is selected when it has no coverage row at all,
    or when its row carries one of the selected statuses. Records that were
    examined and reached a conclusive state are skipped unless the operator
    names their status explicitly, which is what keeps a re-run from burning
    its request budget on universities that were already read.
    """
    from sqlalchemy import select

    from ..models import Scholarship
    from ..models_supervisor import ScholarshipSupervisorCoverage

    has_coverage = select(ScholarshipSupervisorCoverage.scholarship_id)
    selected = select(ScholarshipSupervisorCoverage.scholarship_id).where(
        ScholarshipSupervisorCoverage.status.in_(sorted(options.selected_statuses()))
    )

    query = select(Scholarship).where(
        Scholarship.id.not_in(has_coverage) | Scholarship.id.in_(selected)
    )
    if not options.include_archived:
        query = query.where(Scholarship.is_archived.is_(False))
    if options.after_id is not None:
        query = query.where(Scholarship.id > options.after_id)

    return list(db.execute(query.order_by(Scholarship.id).limit(max(1, options.limit))).scalars().all())


def _current_status(db, scholarship_id: int) -> str:
    from sqlalchemy import select

    from ..models_supervisor import ScholarshipSupervisorCoverage

    row = db.execute(
        select(ScholarshipSupervisorCoverage.status).where(
            ScholarshipSupervisorCoverage.scholarship_id == scholarship_id
        )
    ).scalar_one_or_none()
    return row or "uncovered"


# ---------------------------------------------------------------------------
# One item
# ---------------------------------------------------------------------------


def _process_one(db, scholarship, options: BatchOptions) -> BatchItemResult:
    """Process exactly one scholarship. The only place a batch item writes.

    Two stages, mirroring the one-scholarship proof workflow: classify and
    collect everything, then persist. In a dry run only the first stage runs
    and the second is reported rather than performed.
    """
    from .supervisor_applicability import classify_supervisor_applicability

    previous_status = _current_status(db, scholarship.id)
    applicability = classify_supervisor_applicability(scholarship)

    if applicability.is_not_applicable:
        if options.dry_run:
            result = BatchItemResult(
                scholarship_id=scholarship.id,
                title=scholarship.title,
                previous_status=previous_status,
                outcome_status=str(SupervisorCoverageStatus.NOT_APPLICABLE),
                detail=applicability.rationale,
                not_applicable=True,
            )
            # The contact is reported in a dry run exactly as in a live one, so
            # a reviewer sees the whole proposed change before spending a
            # request. ``_maybe_collect_contact`` writes nothing when the option
            # says dry_run.
            return _maybe_collect_contact(
                db, scholarship, options, previous_status, result=result
            )
        mark_not_applicable(db, scholarship.id, applicability.rationale or "not applicable")
        return _maybe_collect_contact(db, scholarship, options, previous_status)

    # Applicable: run the ordinary discovery pipeline. No render budget is
    # passed, exactly as in the bounded trigger - a client-side directory stays
    # SOURCE_REQUIRES_RENDERING rather than silently enabling a browser.
    plan = collect_supervisor_plan(scholarship)
    if options.dry_run:
        return BatchItemResult(
            scholarship_id=scholarship.id,
            title=scholarship.title,
            previous_status=previous_status,
            outcome_status=_derived_dry_run_status(plan),
            detail=plan.detail,
            pages_fetched=plan.pages_fetched,
            examined=plan.examined_count,
            approved=plan.approved_count,
        )

    outcome = persist_supervisor_plan(db, scholarship, plan)
    result = BatchItemResult(
        scholarship_id=scholarship.id,
        title=scholarship.title,
        previous_status=previous_status,
        outcome_status=outcome.status,
        detail=outcome.detail,
        pages_fetched=plan.pages_fetched,
        examined=plan.examined_count,
        approved=plan.approved_count,
        professors_written=outcome.professors_found,
    )
    if options.collect_contacts and outcome.status in (
        str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND),
        str(SupervisorCoverageStatus.SOURCE_BLOCKED),
    ):
        return _maybe_collect_contact(db, scholarship, options, previous_status, result=result)
    return result


def _derived_dry_run_status(plan) -> str:
    """Return the status persistence would derive for ``plan``.

    A dry run must report the status the database would hold afterwards, not
    the plan's own (frequently empty) status field. The derivation mirrors
    :func:`app.services.supervisor_coverage.recompute_coverage` exactly:
    publishable links first, then blocked, then unsearched, then the negative.
    """
    if plan.coverage_override is not None:
        return plan.coverage_override.status
    if plan.approved_count > 0:
        return str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    if plan.blocked:
        return str(SupervisorCoverageStatus.SOURCE_BLOCKED)
    if not plan.searched:
        return str(SupervisorCoverageStatus.SEARCH_PENDING)
    return str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)


def _maybe_collect_contact(
    db,
    scholarship,
    options: BatchOptions,
    previous_status: str,
    result: BatchItemResult | None = None,
) -> BatchItemResult:
    """Read and store one official contact for a record with no supervisor.

    Only ever called for a record whose supervisor answer is negative or not
    applicable - never for one with verified supervisors, where a contact would
    compete with the professor list and dilute it.
    """
    from .supervisor_contacts import collect_official_contact, upsert_official_contact

    result = result or BatchItemResult(
        scholarship_id=scholarship.id,
        title=scholarship.title,
        previous_status=previous_status,
        outcome_status=str(SupervisorCoverageStatus.NOT_APPLICABLE),
        not_applicable=True,
    )

    observation = collect_official_contact(scholarship)
    if observation is None:
        return result
    if options.dry_run:
        result.contact_collected = True
        result.contact_url = observation.contact_url
        return result

    upsert_official_contact(db, observation)
    db.commit()
    result.contact_collected = True
    result.contact_url = observation.contact_url
    return result


# ---------------------------------------------------------------------------
# Audit and state
# ---------------------------------------------------------------------------


def _append_audit(path: Path, payload: dict) -> None:
    """Append one JSON line. Created on first write, appended to thereafter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def _write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def read_state(path: Path) -> dict:
    """Return the persisted cursor, or an empty dict when there is none."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A truncated or hand-edited state file must not stop a run; starting
        # from the beginning is safe because every write is an upsert.
        return {}


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def _process_with_own_session(scholarship, options: BatchOptions) -> BatchItemResult:
    """Process one scholarship on its own session.

    A worker thread must not share the caller's session, and one failing
    university must not roll back another's commit. Mirrors the worker's own
    ``_discover_one`` for the same reason.
    """
    from ..database import get_session_factory

    session = get_session_factory()()
    try:
        row = session.get(type(scholarship), scholarship.id)
        if row is None:
            return BatchItemResult(
                scholarship_id=scholarship.id,
                title=getattr(scholarship, "title", ""),
                previous_status="uncovered",
                outcome_status=str(SupervisorCoverageStatus.SEARCH_PENDING),
                detail="Scholarship row is not readable from this session.",
            )
        return _process_one(session, row, options)
    except Exception as exc:  # noqa: BLE001 - one institution must not stop the batch
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            logger.exception("Rollback failed after batch item error")
        logger.exception("Supervisor batch failed for scholarship %s", scholarship.id)
        return BatchItemResult(
            scholarship_id=scholarship.id,
            title=getattr(scholarship, "title", ""),
            previous_status="unknown",
            outcome_status=str(SupervisorCoverageStatus.SOURCE_BLOCKED),
            detail=f"{type(exc).__name__}: {exc}"[:500],
        )
    finally:
        session.close()


def _process_with_caller_session(db, scholarship, options: BatchOptions) -> BatchItemResult:
    """Process one scholarship on the caller's session, safely.

    Used for the default single-worker run. An exception is converted into the
    same blocked-item record the threaded path produces, so both paths report
    identically and one unreachable university never ends a catalogue pass.
    """
    try:
        return _process_one(db, scholarship, options)
    except Exception as exc:  # noqa: BLE001 - one institution must not stop the batch
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.exception("Rollback failed after batch item error")
        logger.exception("Supervisor batch failed for scholarship %s", scholarship.id)
        return BatchItemResult(
            scholarship_id=scholarship.id,
            title=getattr(scholarship, "title", ""),
            previous_status="unknown",
            outcome_status=str(SupervisorCoverageStatus.SOURCE_BLOCKED),
            detail=f"{type(exc).__name__}: {exc}"[:500],
        )


def run_supervisor_batch(db, options: BatchOptions) -> BatchReport:
    """Run one bounded batch and return its report. The batch entry point.

    The state file is advanced after every item, which is what makes an
    interrupted run resumable rather than merely restartable, and each item
    commits its own work so a failure cannot roll back the records that
    already succeeded.
    """
    started = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex
    report = BatchReport(
        run_id=run_id,
        started_at=started.isoformat(),
        finished_at=started.isoformat(),
        dry_run=options.dry_run,
        requested_limit=options.limit,
    )

    scholarships = select_batch_candidates(db, options)
    workers = max(1, min(options.workers, MAX_WORKERS))
    if workers == 1:
        items = [_process_with_caller_session(db, row, options) for row in scholarships]
    else:
        # pool.map preserves input order, so the report and the cursor remain
        # deterministic however many universities are in flight.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            items = list(
                pool.map(lambda row: _process_with_own_session(row, options), scholarships)
            )

    for item in items:
        report.items.append(item)
        if options.dry_run:
            continue
        if options.state_path is not None:
            _write_state(
                options.state_path,
                {
                    "run_id": run_id,
                    "last_scholarship_id": item.scholarship_id,
                    "completed": len(report.items),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if options.audit_path is not None:
            _append_audit(options.audit_path, {"run_id": run_id, **vars(item)})

    report.selection_exhausted = len(scholarships) < max(1, options.limit)
    report.next_cursor = (
        report.items[-1].scholarship_id if report.items else options.after_id
    )
    report.finished_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Supervisor batch %s (%s): processed=%s totals=%s",
        run_id,
        "dry run" if options.dry_run else "live",
        len(report.items),
        report.totals,
    )
    return report


__all__ = [
    "DEFAULT_INCLUDE_STATUSES",
    "DEFAULT_LIMIT",
    "DEFAULT_WORKERS",
    "MAX_WORKERS",
    "BatchItemResult",
    "BatchOptions",
    "BatchReport",
    "read_state",
    "run_supervisor_batch",
    "select_batch_candidates",
]
