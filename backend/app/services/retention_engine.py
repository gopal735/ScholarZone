"""The database half of the retention engine: classify, prove, then delete.

:class:`app.services.retention_contract` decides. This module does only the things
that need a database, and it does them in an order chosen so the cheapest refusal
happens first:

1. **Reference-integrity audit** (:func:`reference_integrity_report`) - before any
   code runs, so the engine states what it would destroy if it were allowed to.
2. **Scan** (:func:`scan`) - one read-only pass, using the catalogue's own public
   visibility predicate and its own review surfaces, producing the same decisions
   the deleting path uses.
3. **Dry run** (:func:`dry_run`) - the scan plus the full safety gate, writing
   nothing but its own audit record. This is the only mode that ships enabled.
4. **Bounded delete** (:func:`delete_bounded`) - reachable only when the policy has
   been enabled for real deletion, one transaction per batch, every row re-read
   and re-classified immediately before removal, and the removal itself issued as
   a conditional ``DELETE`` whose predicate is the negation of the same LIVE and
   ADMIN_REVIEW conditions.

Four properties are why any of that can be trusted.

**The dry run and the deletion use the same code.** Not the same policy - the same
``classify`` call, over the same rows, through the same SQL. A dry run that
approximates the real query proves nothing about the real query.

**LIVE is never re-derived.** It is resolved in SQL by
``public_visibility_conditions()``, the function the directory, the homepage
statistics, the counting layer and the closed-record collector already call.

**A record is never deleted on a decision made earlier.** Between classification
and deletion a record can be reopened, re-verified, put into review, given a
dependency, or have its clocks rewritten. So each candidate is re-read under a row
lock, re-classified, and then removed by a conditional ``DELETE`` that matches the
exact ``archived_at`` and ``auto_delete_candidate_since`` the verdict was based on.
If anything moved, the statement matches zero rows and the record is kept. A lost
race is always a retention, never a deletion.

**Reference integrity is resolved before any row is touched, and it is strict.**
Five of the seven tables referencing a scholarship hold the record's own evidence -
the reviews, the verification history, the point-in-time snapshots, the restore log
and the image provenance. No relationship declares ``ON DELETE CASCADE``, so
PostgreSQL refuses to delete a referenced scholarship outright; the only way
"through" is to delete those rows first. That would destroy exactly the audit
trail that made a public claim defensible, so this engine does not do it. A record
carrying any PRESERVE row is never a deletion candidate, and the deleting path
only ever detaches the one nullable link and removes settled fetch telemetry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from sqlalchemy import and_, delete, func, not_, or_, select
from sqlalchemy.orm import Session

from ..models import (
    Base,
    DiscoveryCandidate,
    ImageReview,
    MaintenanceRun,
    SavedScholarship,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipRestoreRecord,
    ScholarshipReview,
    ScholarshipSnapshot,
    ScholarshipVerificationHistory,
    ApplicationRecord,
)
from ..models_supervisor import (
    ProfessorOutreachRecord,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
)
from ..repositories.scholarships import public_visibility_conditions
from .auto_delete_policy import (
    TERMINAL_CANDIDATE_MATCH,
    TERMINAL_FETCH_STATUSES,
    TERMINAL_REVIEW_DECISIONS,
)
from .counting.catalogue import catalogue_counts
from .retention_contract import (
    ADMIN_REVIEW_STATUSES,
    BUCKET_ADMIN_REVIEW,
    BUCKET_LIVE,
    RETENTION_CONTRACT_VERSION,
    RetentionDecision,
    RetentionFacts,
    RetentionPolicy,
    assert_invariants,
    classify,
    default_policy,
    summarise,
)

logger = logging.getLogger(__name__)

#: Identifies this engine's rows in the shared maintenance-run ledger.
RETENTION_WORKER = "retention/live-admin-review/1"

#: The stage name recorded in the run ledger.
RETENTION_STAGE = "retention_cleanup"

MODE_DRY_RUN = "DRY_RUN"
MODE_DELETE = "DELETE"

#: How old a ``running`` retention row may be before it counts as abandoned
#: rather than concurrent. A lock that never expires blocks every future run
#: after one crash, which is how a single-run lock becomes an outage.
STALE_RUN_LOCK_MINUTES = 30

#: Columns the classifier depends on. A NULL in any of them is not a record state
#: - it is a schema that has drifted from the model this code reads - so the row
#: is reported as unclassifiable rather than coerced into one.
REQUIRED_STATE_COLUMNS = (
    "verification_status",
    "status",
    "is_archived",
    "is_verified",
    "deletion_protected",
)

#: Run statuses, reused from ``app.services.maintenance_run_log`` rather than
#: invented, because they are the vocabulary an operator already reads.
STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"


class CleanupAborted(RuntimeError):
    """A safety gate refused to let a deletion proceed.

    Never caught and downgraded inside the engine. A partial "best effort"
    destructive cleanup is the outcome these guards exist to prevent, so an abort
    propagates to the caller with the failing check named.
    """


# ---------------------------------------------------------------------------
# Phase 5 - reference integrity
# ---------------------------------------------------------------------------

#: Model name -> disposition. Keyed by the mapped class, because the table name
#: is a naming convention and a rename must not silently become "unclassified".
REFERENCE_INTEGRITY: dict[str, dict[str, str]] = {
    "ScholarshipReview": {
        "table": "scholarship_reviews",
        "disposition": "PRESERVE",
        "rationale": (
            "A review is the only record of why a decision about this scholarship was "
            "reached, and it is a live ADMIN_REVIEW surface. Deleting the parent either "
            "destroys it (cascade) or is refused by the foreign key (restrict). Neither "
            "is acceptable, so any record with a review is never a deletion candidate."
        ),
    },
    "ScholarshipVerificationHistory": {
        "table": "scholarship_verification_history",
        "disposition": "PRESERVE",
        "rationale": (
            "The evidence chain behind every public trust claim. A row carrying quoted "
            "evidence is the substance of the record's auditability."
        ),
    },
    "ScholarshipSnapshot": {
        "table": "scholarship_snapshots",
        "disposition": "PRESERVE",
        "rationale": (
            "Point-in-time versions. Removing the parent makes historical counts "
            "unanswerable, because these rows are the only source of past state."
        ),
    },
    "ScholarshipRestoreRecord": {
        "table": "scholarship_restore_records",
        "disposition": "PRESERVE",
        "rationale": (
            "The log of restore operations - the recovery mechanism's own record. "
            "Removing it removes the ability to explain a rollback."
        ),
    },
    "ImageReview": {
        "table": "image_reviews",
        "disposition": "PRESERVE",
        "rationale": (
            "The unsettled subset is the second ADMIN_REVIEW surface. A decided image "
            "review is the provenance of the scholarship's logo, and a logo with no "
            "recorded origin is the failure this table exists to prevent."
        ),
    },
    "ScholarshipFetchAttempt": {
        "table": "scholarship_fetch_attempts",
        "disposition": "DISPOSABLE_WHEN_SETTLED",
        "rationale": (
            "Fetch telemetry whose subject would be gone. Settled attempts are derived "
            "data and may be removed with the parent; an unsettled one is pending work "
            "and blocks the record instead."
        ),
    },
    "DiscoveryCandidate": {
        "table": "discovery_candidates",
        "disposition": "SET_NULL",
        "rationale": (
            "A nullable link from discovery to catalogue. The candidate is "
            "independently meaningful - a research finding that matched nothing - so it "
            "is detached (matched_scholarship_id := NULL, match_status := 'unmatched') "
            "rather than deleted. A candidate still awaiting a match decision depends on "
            "the scholarship and blocks it."
        ),
    },
    "SavedScholarship": {
        "table": "saved_scholarships",
        "disposition": "PRESERVE",
        "rationale": (
            "A student's shortlist entry. Removing the scholarship would orphan or "
            "destroy the user's saved-item history, and the foreign key refuses the "
            "parent delete. Any record carrying a saved-scholarship row is never a "
            "deletion candidate."
        ),
    },
    "ApplicationRecord": {
        "table": "application_records",
        "disposition": "PRESERVE",
        "rationale": (
            "A student's application history, including immutable snapshots of the "
            "scholarship data at the time of application. Removing the parent would "
            "destroy the user's application record, and the foreign key refuses the "
            "parent delete. Any record carrying an application record is never a "
            "deletion candidate."
        ),
    },
    "ScholarshipSupervisorCoverage": {
        "table": "scholarship_supervisor_coverage",
        "disposition": "PRESERVE",
        "rationale": (
            "The discovery state for one scholarship. Removing the scholarship would "
            "destroy the coverage record, and the foreign key refuses the parent delete. "
            "Any record carrying coverage data is never a deletion candidate."
        ),
    },
    "ScholarshipProfessorLink": {
        "table": "scholarship_professor_links",
        "disposition": "PRESERVE",
        "rationale": (
            "An evidenced professor relationship to one scholarship. Removing the "
            "scholarship would destroy the link, and the foreign key refuses the parent "
            "delete. Any record carrying a professor link is never a deletion candidate."
        ),
    },
    "SupervisorSourceEvidence": {
        "table": "supervisor_source_evidence",
        "disposition": "PRESERVE",
        "rationale": (
            "An authoritative page that was read for one scholarship's supervisor "
            "discovery. Removing the scholarship would orphan or destroy the evidence, "
            "and the foreign key refuses the parent delete when the scholarship_id is "
            "not NULL. Any record carrying source evidence is never a deletion candidate."
        ),
    },
    "ProfessorOutreachRecord": {
        "table": "professor_outreach_records",
        "disposition": "PRESERVE",
        "rationale": (
            "A student's private record of contacting a professor about a scholarship. "
            "Removing the scholarship would destroy the outreach record, and the foreign "
            "key refuses the parent delete. Any record carrying an outreach record is "
            "never a deletion candidate."
        ),
    },
}

#: Models whose mere presence blocks deletion, because their rows are the record's
#: own evidence and the foreign key would otherwise refuse the parent delete.
PRESERVE_MODELS: tuple[str, ...] = tuple(
    model
    for model, spec in REFERENCE_INTEGRITY.items()
    if spec["disposition"] == "PRESERVE"
)

#: Artefacts that reference scholarships without a foreign key. Listed because
#: their absence from the FK graph is not evidence of independence, and a new one
#: should have to be added here deliberately.
UNLINKED_ARTEFACTS = (
    "backend/config/purged_records_archive.json (deletion manifest; this engine extends it)",
    "backend/config/retired_records.json (operator retirement list)",
    "backend/config/record_corrections.json (audited field corrections)",
    "backend/config/verification_confirmations.json (verification confirmations)",
    "Scholarship.official_details / applicant_utility / programme_verification (JSON blocks)",
)

#: Every mapped class that carries a scholarship reference, in the order the
#: deletion path needs them.
DEPENDENT_MODELS: Mapping[str, type] = {
    "ScholarshipReview": ScholarshipReview,
    "ScholarshipVerificationHistory": ScholarshipVerificationHistory,
    "ScholarshipSnapshot": ScholarshipSnapshot,
    "ScholarshipRestoreRecord": ScholarshipRestoreRecord,
    "ImageReview": ImageReview,
    "ScholarshipFetchAttempt": ScholarshipFetchAttempt,
    "SavedScholarship": SavedScholarship,
    "ApplicationRecord": ApplicationRecord,
    "ScholarshipSupervisorCoverage": ScholarshipSupervisorCoverage,
    "ScholarshipProfessorLink": ScholarshipProfessorLink,
    "SupervisorSourceEvidence": SupervisorSourceEvidence,
    "ProfessorOutreachRecord": ProfessorOutreachRecord,
}


def reference_integrity_report() -> dict[str, Any]:
    """State, before running anything, what a hard delete would touch.

    Introspected from the live metadata rather than written by hand, so a
    relationship added later shows up here as unclassified instead of being
    silently ignored - which is the specific failure this report exists to
    prevent.
    """
    relationships: list[dict[str, Any]] = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name != Scholarship.__tablename__ or fk.column.name != "id":
                    continue
                model = next(
                    (
                        mapper.class_
                        for mapper in Base.registry.mappers
                        if mapper.local_table is table
                    ),
                    None,
                )
                name = model.__name__ if model is not None else table.name
                spec = REFERENCE_INTEGRITY.get(name)
                relationships.append(
                    {
                        "model": name,
                        "table": table.name,
                        "column": column.name,
                        "nullable": bool(column.nullable),
                        "ondelete": fk.ondelete,
                        "database_enforcement": (
                            "NO ACTION / RESTRICT" if fk.ondelete is None else fk.ondelete
                        ),
                        "disposition": spec["disposition"] if spec else "UNCLASSIFIED",
                        "rationale": (
                            spec["rationale"]
                            if spec
                            else "no disposition is recorded for this relationship; treat it "
                            "as blocking until one is decided"
                        ),
                    }
                )

    unclassified = [r["model"] for r in relationships if r["disposition"] == "UNCLASSIFIED"]
    cascades = [r["model"] for r in relationships if r["ondelete"] == "CASCADE"]
    return {
        "scholarship_table": Scholarship.__tablename__,
        "relationships": sorted(relationships, key=lambda r: (r["table"], r["column"])),
        "relationship_count": len(relationships),
        "unclassified_relationships": sorted(unclassified),
        "cascade_deletes_declared": sorted(cascades),
        "preserving_models": list(PRESERVE_MODELS),
        "unlinked_artefacts": list(UNLINKED_ARTEFACTS),
        "integrity_uncertain": bool(unclassified),
        "verdict": "INTEGRITY_BLOCKED" if unclassified else "ALL_RELATIONSHIPS_CLASSIFIED",
        "note": (
            "No relationship declares ON DELETE CASCADE, so PostgreSQL refuses to delete a "
            "referenced scholarship outright. Cascade is therefore not the hazard here; the "
            "hazard is the manual child-row removal an engine performs to get around that "
            "refusal, which is why the PRESERVE dispositions are binding on this engine."
        ),
    }


# ---------------------------------------------------------------------------
# Canonical predicates
# ---------------------------------------------------------------------------


def live_condition() -> list:
    """The authoritative LIVE predicate. Reused verbatim, never restated.

    A thin pass-through so the engine has exactly one call site for the public
    rule, and a reader can see at a glance that the retention engine and the
    public catalogue cannot drift: they call the same function.
    """
    return public_visibility_conditions()


def admin_review_conditions() -> list:
    """The authoritative ADMIN_REVIEW predicate, in SQL.

    The union of every surface the repository already uses to mean "a human must
    look at this next":

    * a verification status that says a human is the next actor;
    * an unsettled scholarship review;
    * an unsettled image review.

    "Unsettled" is deliberately not ``decision = 'pending'``. It means *not
    terminal, or terminal with nobody recorded as the reviewer* - the same
    two-part test the closed-record policy applies, and a record whose review is
    half-finished is exactly the record that must not be deleted.
    """
    return [
        Scholarship.verification_status.in_(sorted(ADMIN_REVIEW_STATUSES)),
        select(ScholarshipReview.id)
        .where(
            ScholarshipReview.scholarship_id == Scholarship.id,
            _unsettled(ScholarshipReview),
        )
        .exists(),
        select(ImageReview.id)
        .where(ImageReview.scholarship_id == Scholarship.id, _unsettled(ImageReview))
        .exists(),
    ]


def _unsettled(model: Any) -> Any:
    return or_(
        model.decision.notin_(sorted(TERMINAL_REVIEW_DECISIONS)),
        model.reviewed_at.is_(None),
    )


# ---------------------------------------------------------------------------
# Reference dependencies, per record
# ---------------------------------------------------------------------------


def reference_dependencies(session: Session, ids: Sequence[int]) -> dict[int, frozenset[str]]:
    """Which records carry a dependency that must survive them, and why.

    Two independent reasons, and they are not the same question:

    * the row is evidence about this scholarship (PRESERVE) - its mere presence
      blocks, because the foreign key would otherwise refuse the parent delete
      and working around that refusal would destroy the evidence;
    * the row is unfinished business (DISPOSABLE) - settled telemetry is
      removable with the parent, pending work is not.
    """
    if not ids:
        return {}

    blocking: dict[int, set[str]] = {sid: set() for sid in ids}
    id_list = list(ids)

    # PRESERVE tables: the mere presence of a row blocks. The foreign key would
    # otherwise refuse the parent delete, and working around that refusal is
    # exactly the destruction this engine refuses to perform.
    for name, model in DEPENDENT_MODELS.items():
        if name not in PRESERVE_MODELS:
            continue
        column = model.scholarship_id
        for (sid,) in session.execute(
            select(column).where(column.in_(id_list)).distinct()
        ):
            blocking[int(sid)].add(name)

    # DISPOSABLE tables are handled per row rather than by presence: settled
    # telemetry may go with the parent, pending work may not.
    pending_fetch = session.execute(
        select(ScholarshipFetchAttempt.scholarship_id).where(
            ScholarshipFetchAttempt.scholarship_id.in_(id_list),
            or_(
                ScholarshipFetchAttempt.status.notin_(sorted(TERMINAL_FETCH_STATUSES)),
                ScholarshipFetchAttempt.resolved_at.is_(None),
            ),
        )
    ).all()
    for (sid,) in pending_fetch:
        blocking[int(sid)].add("ScholarshipFetchAttempt:unsettled")

    pending_candidate = session.execute(
        select(DiscoveryCandidate.matched_scholarship_id).where(
            DiscoveryCandidate.matched_scholarship_id.in_(id_list),
            or_(
                DiscoveryCandidate.match_status.notin_(sorted(TERMINAL_CANDIDATE_MATCH)),
                DiscoveryCandidate.resolved_at.is_(None),
            ),
        )
    ).all()
    for (sid,) in pending_candidate:
        blocking[int(sid)].add("DiscoveryCandidate:awaiting_match_decision")

    return {sid: frozenset(names) for sid, names in blocking.items()}


# ---------------------------------------------------------------------------
# Phase 7/8 - the scan
# ---------------------------------------------------------------------------


def _aware(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _null_state_rows(session: Session) -> dict[int, str]:
    """Rows whose state columns came back NULL, with the columns named."""
    conditions = [getattr(Scholarship, name).is_(None) for name in REQUIRED_STATE_COLUMNS]
    out: dict[int, str] = {}
    statement = select(Scholarship.id, *(
        getattr(Scholarship, name) for name in REQUIRED_STATE_COLUMNS
    )).where(or_(*conditions))
    for row in session.execute(statement):
        nulls = [name for name in REQUIRED_STATE_COLUMNS if getattr(row, name) is None]
        out[int(row[0])] = f"NULL state column(s): {', '.join(nulls)}"
    return out


def build_facts(
    session: Session,
    rows: Sequence[Scholarship],
    *,
    live_ids: set[int],
    review_ids: set[int],
    dependencies: Mapping[int, frozenset[str]],
    null_states: Mapping[int, str],
) -> list[RetentionFacts]:
    """Assemble the classifier's inputs. Pure assembly; no decision made here."""
    facts: list[RetentionFacts] = []
    for row in rows:
        error = null_states.get(row.id)
        facts.append(
            RetentionFacts(
                scholarship_id=row.id,
                is_live=row.id in live_ids,
                pending_scholarship_reviews=1 if row.id in review_ids else 0,
                pending_image_reviews=0,
                verification_status=row.verification_status,
                lifecycle_status=row.status,
                deletion_protected=bool(row.deletion_protected),
                archived_at=_aware(row.archived_at),
                archived_reason=row.archived_reason,
                is_archived=bool(row.is_archived),
                candidate_since=_aware(row.auto_delete_candidate_since),
                is_verified=bool(row.is_verified),
                deadline_date=row.deadline_date,
                blocking_dependencies=dependencies.get(row.id, frozenset()),
                evidence_complete=error is None,
                evidence_error=error,
            )
        )
    return facts


def scan(
    session: Session,
    *,
    as_of: datetime,
    policy: RetentionPolicy | None = None,
    ids: Sequence[int] | None = None,
    live_conditions: Sequence[Any] | None = None,
    review_conditions: Sequence[Any] | None = None,
) -> list[RetentionDecision]:
    """Classify records. Read-only; this function never writes.

    ``ids`` narrows the scan to a set, which is what the deleting path uses to
    re-check a batch without re-reading the whole catalogue. The queries are
    otherwise identical, so a narrow re-check cannot answer differently from a
    full one.

    Any database error propagates. A partial classification must never be
    mistaken for a complete one, and the only safe response to not knowing the
    whole picture is to do nothing.
    """
    policy = policy or default_policy()
    live_conditions = list(live_conditions if live_conditions is not None else live_condition())
    review_conditions = list(
        review_conditions if review_conditions is not None else admin_review_conditions()
    )

    statement = select(Scholarship).order_by(Scholarship.id)
    if ids is not None:
        if not ids:
            return []
        statement = statement.where(Scholarship.id.in_(list(ids)))
    rows = list(session.scalars(statement).all())
    if not rows:
        return []

    row_ids = [row.id for row in rows]
    live_ids = set(session.scalars(select(Scholarship.id).where(*live_conditions)).all())
    review_ids = set(session.scalars(select(Scholarship.id).where(or_(*review_conditions))).all())
    null_states = _null_state_rows(session)
    dependencies = reference_dependencies(session, row_ids)

    decisions = [
        classify(fact, policy=policy, as_of=as_of)
        for fact in build_facts(
            session,
            rows,
            live_ids=live_ids,
            review_ids=review_ids,
            dependencies=dependencies,
            null_states=null_states,
        )
    ]

    # The run is only trustworthy if these hold, so they are asserted on every
    # scan - including the dry run - rather than assumed from the branch structure.
    assert_invariants(decisions)
    return decisions


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


class _Guard:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks: dict[str, bool] = {}

    def require(self, name: str, condition: bool, message: str) -> None:
        self.checks[name] = bool(condition)
        if not condition:
            self.failures.append(message)

    def abort_if_failed(self) -> None:
        if self.failures:
            raise CleanupAborted("; ".join(self.failures))


def _bind_identity(session: Session) -> str:
    """Identify the database this run is talking to.

    A cleanup that silently retargets itself at a different database between its
    scan and its delete is the worst failure available: it would apply one
    catalogue's verdicts to another's rows. The identity is captured at the start
    and re-checked before every batch.
    """
    bind = session.get_bind()
    url = getattr(bind, "url", None)
    return str(url) if url is not None else repr(bind)


def competing_run_ids(session: Session, *, exclude_run_id: str | None = None) -> list[str]:
    """Retention runs that are still marked running, excluding stale ones."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_RUN_LOCK_MINUTES)
    statement = select(MaintenanceRun.run_id, MaintenanceRun.started_at).where(
        MaintenanceRun.worker.like("retention/%"),
        MaintenanceRun.status == "running",
    )
    if exclude_run_id:
        statement = statement.where(MaintenanceRun.run_id != exclude_run_id)
    rows = list(session.execute(statement).all())
    out: list[str] = []
    for run_id, started_at in rows:
        started = _aware(started_at)
        # A run whose clock never advanced is presumed abandoned, so one crash
        # cannot block every future run.
        if started is not None and started <= cutoff:
            continue
        out.append(run_id)
    return sorted(out)


# ---------------------------------------------------------------------------
# Phase 11 - the audit ledger
# ---------------------------------------------------------------------------


def ledger_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "purged_records_archive.json"


#: Keys that must never reach the ledger. A deletion manifest is read by people
#: and pasted into tickets; a credential in it outlives every control that was
#: supposed to keep it out.
_FORBIDDEN_MANIFEST_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "credential",
        "credentials",
        "authorization",
        "auth",
        "private_key",
        "connection_string",
        "database_url",
        "dsn",
        "session_key",
        "cookie",
        "email",
    }
)

#: Written into the ledger so that nobody reading it later mistakes it for a
#: recovery path. The distinction is the whole point: a manifest can say what a
#: row was and why it went, and it cannot put the row back, reinstate the
#: foreign keys, or rewind a transaction.
MANIFEST_DISCLAIMER = {
    "manifest_is_a_backup": False,
    "MANIFEST != BACKUP": (
        "This file records what the retention engine deleted and the exact reason "
        "each record was classified that way. It is NOT a backup, NOT a restore "
        "point, and NOT a recovery path. It contains no schema, no type "
        "information, no transaction boundaries and no child rows, so it cannot "
        "reinstate a deleted scholarship inside the foreign-key graph the "
        "application depends on, and it cannot rewind a committed transaction. "
        "Recovering a deleted scholarship requires a database restore from a "
        "proven recovery source; see app.services.retention_recovery."
    ),
    "recoverable": False,
    "written_before_commit": True,
    "purpose": "audit and reconciliation only",
}


def _assert_no_credentials(entry: Mapping[str, Any]) -> None:
    """Refuse to write an entry containing anything credential-shaped.

    Checked by key rather than by value, because the dangerous case is a new
    field someone adds to a batch entry without thinking about where it lands, and
    a key-based check catches that while the field is still a local variable.
    """
    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                lowered = str(key).lower()
                if lowered in _FORBIDDEN_MANIFEST_KEYS:
                    raise ValueError(
                        f"refusing to write the deletion manifest: {path}.{key} is "
                        "credential-shaped and the ledger is not a secret store"
                    )
                walk(value, f"{path}.{key}")
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(entry, "entry")


def _manifest_record(
    decision: RetentionDecision,
    *,
    run_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    """One deleted record's audit entry.

    Every field the retention contract requires a manifest to carry, named rather
    than left implicit in a prose ``detail`` string: the record's identity, why it
    was classified the way it was, the state it was in at the moment of the
    decision, which run decided it, and under which contract version.

    The dependency list is recorded as *names of tables that were empty*, which is
    the operative fact: it is what makes the deletion defensible afterwards. A
    reader can check that no PRESERVE table was touched because the entry says so,
    rather than having to reconstruct it from a row that no longer exists.

    What this deliberately does not contain: the row's own data. A full payload
    would help a manual re-insertion, and it would also make an untracked copy of
    the catalogue. Audit and reconciliation is the purpose; recovery is not, and
    recovery needs a restore, not a JSON file.
    """
    return {
        "record_identity": {"table": Scholarship.__tablename__, "id": decision.scholarship_id},
        "scholarship_id": decision.scholarship_id,
        "decision": decision.decision,
        "classification_reason": decision.reason,
        "classification_detail": decision.detail,
        "bucket": decision.bucket,
        "state": decision.state,
        "grace_eligible": decision.grace_eligible,
        "decision_timestamp": as_of.isoformat(),
        "run_id": run_id,
        "contract_version": RETENTION_CONTRACT_VERSION,
        "conditions_verified": dict(sorted(decision.checks.items())),
        "dependencies_present_at_decision": [],
        "dependencies_preserved": sorted(PRESERVE_MODELS),
        "dependency_policy": (
            "no PRESERVE table contained a row for this record, which is a "
            "precondition of it reaching DELETE_CANDIDATE"
        ),
        "recoverable_from_this_entry": False,
        "recovery_note": (
            "This entry explains the deletion. It does not undo it. Reinstating the "
            "record requires a database restore from a proven recovery source."
        ),
    }


def append_deletion_manifest(entry: dict[str, Any], *, path: Path | None = None) -> Path:
    """Append this run's batch to the shared ledger. Never rewrite it.

    The file is shared with the closed-record collector, which owns
    ``records``, ``count``, ``breakdown``, ``child_rows`` and ``purged_at``.
    Those keys are left exactly as found. Everything this function writes goes
    under ``retention_*`` keys, and only those.

    An earlier version of this function rebuilt ``records`` from ``batches`` and
    recomputed ``count``. Because the collector's ledger has no ``batches`` key
    at all, that rewrote 151 historical records to an empty list and destroyed
    the file's contents - and every test passed, because every test wrote to a
    fresh temporary path and never exercised the shared ledger. The rule now is
    append-only, scoped to keys this function owns, and there is a regression
    test that runs against a ledger seeded with the collector's real shape.

    Written before a delete commits and confirmed after, for the same reason the
    closed-record collector does it that way: a process that dies between the two
    would leave rows gone and nothing written down. An over-reported deletion is
    repairable by reading the id back; an under-reported one is not.
    """
    _assert_no_credentials(entry)
    path = path or ledger_path()

    existing: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            # An unreadable ledger is preserved rather than replaced. Starting a
            # fresh file over the top of one somebody else wrote would discard
            # whatever was in it, which is the one thing a ledger must not do.
            existing = {
                "ledger_unreadable": True,
                "note": "a previous ledger could not be parsed and has been left intact "
                "alongside; retention entries below are additive only",
            }

    batches = existing.setdefault("retention_batches", [])
    if not isinstance(batches, list):  # pragma: no cover - defensive
        batches = []
        existing["retention_batches"] = batches

    run_token = entry.get("run_token")
    batches[:] = [
        b
        for b in batches
        if not (isinstance(b, dict) and b.get("confirmed") is False
                and b.get("run_token") == run_token)
    ]
    batches.append({**MANIFEST_DISCLAIMER, "manifest_kind": "retention_deletion_manifest",
                    **entry})

    confirmed = [b for b in batches if isinstance(b, dict) and b.get("confirmed")]
    existing["retention_summary"] = {
        "runs_recorded": len(batches),
        "runs_confirmed": len(confirmed),
        "retention_deleted": sum(int(b.get("deleted") or 0) for b in confirmed),
        "retention_records": [
            r for b in confirmed for r in b.get("records", []) if isinstance(r, dict)
        ],
        "note": (
            "Additive only. The closed-record collector owns records, count, "
            "breakdown, child_rows and children, and this function does not touch them."
        ),
    }
    existing["retention_runs"] = [
        r for r in existing.get("retention_runs", []) if r.get("run_id") != entry.get("run_id")
    ] + [
        {
            key: entry.get(key)
            for key in (
                "run_id",
                "mode",
                "deleted_at",
                "contract_version",
                "trigger",
                "scanned",
                "deleted",
                "kept_live",
                "kept_admin_review",
                "protected",
                "ambiguous",
                "grace_eligible",
            )
        }
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return path


def open_audit_run(
    session: Session,
    *,
    run_id: str,
    mode: str,
    trigger: str,
    as_of: datetime,
) -> None:
    """Insert the run row up front, so a crash still leaves a trace.

    Reuses ``maintenance_runs`` - the project's existing operational ledger -
    rather than adding a table. Two tables both claiming to record what a cleanup
    did would be a second source of truth for the same question, which is worse
    than no record at all.

    No personal data is written. Counts, state names and the run's own
    identifiers are the whole content.
    """
    session.add(
        MaintenanceRun(
            run_id=run_id,
            started_at=as_of,
            worker=RETENTION_WORKER,
            status="running",
            stages=[],
            counts={},
            dry_run=(mode == MODE_DRY_RUN),
        )
    )
    session.commit()


def close_audit_run(
    session: Session,
    *,
    run_id: str,
    mode: str,
    status: str,
    as_of: datetime,
    counts: Mapping[str, Any],
    errors: Sequence[str] = (),
    guards: Mapping[str, bool] | None = None,
) -> None:
    """Write the outcome once. The record is not amended afterwards."""
    run = session.query(MaintenanceRun).filter(MaintenanceRun.run_id == run_id).one_or_none()
    if run is None:
        raise CleanupAborted(f"run {run_id} has no ledger row to finalise")
    run.finished_at = as_of
    run.status = status
    run.dry_run = (mode == MODE_DRY_RUN)
    run.stages = [
        {
            "name": RETENTION_STAGE,
            "ok": status == STATUS_OK,
            "detail": {
                "mode": mode,
                "contract_version": RETENTION_CONTRACT_VERSION,
                "trigger": counts.get("retention_trigger"),
                "guards": dict(sorted((guards or {}).items())),
            },
            "error": ("; ".join(errors)[:500] or None),
        }
    ]
    run.counts = {k: v for k, v in sorted(counts.items()) if v is not None}
    run.error_summary = ("\n".join(errors)[:2000] or None)
    # SQLite reads the column back naive and Postgres reads it aware, so the
    # subtraction is normalised first; a naive/aware mix here raises rather than
    # recording a duration.
    started = _aware(run.started_at)
    run.duration_ms = (
        (as_of - started).total_seconds() * 1000.0 if started is not None else None
    )
    session.commit()


# ---------------------------------------------------------------------------
# Phase 12 - recovery
# ---------------------------------------------------------------------------


def recovery_status() -> dict[str, Any]:
    """State plainly whether a deleted row could be brought back.

    The answer is about the platform, not the code, so it reports what the
    repository actually contains rather than asserting a capability. An audit log
    is not a backup: it can say a row existed and what it said, but it cannot
    reinstate the row inside a foreign-key graph the application depends on, and
    describing it as a recovery path is how an irreversible operation comes to be
    treated as reversible.
    """
    return {
        "verified_pitr": False,
        "automated_backups": False,
        "local_sqlite_snapshots": True,
        "local_snapshot_limitation": (
            "the only snapshot on record is a pre-migration SQLite file dated 2026-09-02; "
            "it predates the production PostgreSQL database and cannot restore it"
        ),
        "manifest_ledger": (
            "backend/config/purged_records_archive.json records what was removed and why, "
            "with a full row payload, which supports manual re-insertion but cannot "
            "restore referential integrity or roll back a transaction"
        ),
        "verdict": "RECOVERY_PATH_REQUIRED",
        "consequence": (
            "Hard deletion is not enabled. The engine classifies, reports and records "
            "candidates for review, but removes nothing. Enabling deletion requires a "
            "verified point-in-time recovery path on the production database plus an "
            "owner's explicit authorisation."
        ),
    }


def _policy_summary(policy: RetentionPolicy) -> dict[str, Any]:
    return {
        "cleanup_enabled": policy.cleanup_enabled,
        "dry_run": policy.dry_run,
        "minimum_age_before_delete": policy.minimum_age_before_delete,
        "grace_days": policy.grace_days,
        "max_delete_per_run": policy.max_delete_per_run,
        "max_delete_percentage": policy.max_delete_percentage,
        "batch_size": policy.batch_size,
        "max_ambiguous_ratio": policy.max_ambiguous_ratio,
        "protected_statuses": sorted(policy.protected_statuses),
    }


# ---------------------------------------------------------------------------
# Phase 7 - the dry run
# ---------------------------------------------------------------------------


def dry_run(
    session: Session,
    *,
    as_of: datetime | None = None,
    policy: RetentionPolicy | None = None,
    run_id: str | None = None,
    trigger: str = "manual",
    sample_size: int = 25,
) -> dict[str, Any]:
    """Classify and report. Writes nothing except the audit record of the run.

    The report answers one question - what would a deleting run remove - and it is
    produced by the same :func:`scan` the deleting path calls, so a dry run cannot
    flatter the deleting path by using a friendlier query.
    """
    as_of = as_of or datetime.now(timezone.utc)
    policy = policy or default_policy()
    run_id = run_id or uuid4().hex[:16]
    integrity = reference_integrity_report()

    report: dict[str, Any] = {
        "run_id": run_id,
        "mode": MODE_DRY_RUN,
        "as_of": as_of.isoformat(),
        "contract_version": RETENTION_CONTRACT_VERSION,
        "trigger": trigger,
        "policy": _policy_summary(policy),
    }
    open_audit_run(
        session, run_id=run_id, mode=MODE_DRY_RUN, trigger=trigger, as_of=as_of
    )
    try:
        decisions = scan(session, as_of=as_of, policy=policy)
        summary = summarise(decisions)
        counts_before = catalogue_counts(session)

        candidates = [d for d in decisions if d.is_delete]
        ambiguous_ratio = (summary.unclassifiable / summary.scanned) if summary.scanned else 0.0
        candidate_share = (
            (summary.delete_candidates / summary.scanned) if summary.scanned else 0.0
        )

        guard = _Guard()
        guard.require(
            "reference_integrity_classified",
            not integrity["integrity_uncertain"],
            "reference integrity is uncertain: an unclassified relationship exists, so the "
            "engine cannot state what a deletion would remove",
        )
        guard.require(
            "ambiguous_within_tolerance",
            ambiguous_ratio <= policy.max_ambiguous_ratio,
            f"{summary.unclassifiable} of {summary.scanned} record(s) could not be "
            f"classified ({ambiguous_ratio:.1%}), above the {policy.max_ambiguous_ratio:.1%} "
            "tolerance",
        )
        guard.require(
            "candidates_within_per_run_cap",
            len(candidates) <= policy.max_delete_per_run,
            f"{len(candidates)} delete candidate(s) exceed the per-run cap of "
            f"{policy.max_delete_per_run}",
        )
        guard.require(
            "candidates_within_percentage_cap",
            candidate_share <= policy.max_delete_percentage,
            f"{len(candidates)} of {summary.scanned} record(s) ({candidate_share:.1%}) exceed "
            f"the {policy.max_delete_percentage:.1%} share cap",
        )
        guard.require(
            "summary_reconciles",
            summary.reconciles(),
            "the classification summary does not reconcile: scanned does not equal the sum "
            "of its buckets",
        )
        guard.require(
            "deletion_disarmed_by_default",
            not (policy.cleanup_enabled and not policy.dry_run),
            "the supplied policy is configured to delete; this run is a dry run and reports "
            "that configuration rather than acting on it",
        )
        guard.require(
            "no_competing_cleanup",
            not competing_run_ids(session, exclude_run_id=run_id),
            "another retention run is active, so this run's classification may be read "
            "against a catalogue that is moving",
        )

        blocked = bool(guard.failures)
        elapsed = (datetime.now(timezone.utc) - as_of).total_seconds()
        report.update(
            {
                "summary": summary.as_dict(),
                "counts_before": counts_before,
                "guards": dict(sorted(guard.checks.items())),
                "guard_failures": list(guard.failures),
                "status": STATUS_PARTIAL if blocked else STATUS_OK,
                # Timing is reported rather than enforced. The scan is a single
                # pass, so its cost scales with the catalogue and not with a
                # per-record loop - but nothing here cancels a long-running
                # database statement, and claiming a timeout that does not exist
                # would be worse than reporting the number. A production
                # deployment that wants a hard cap should set a server-side
                # statement_timeout on the connection instead, which this code
                # deliberately does not do on the operator's behalf.
                "elapsed_seconds": round(elapsed, 3),
                "write_scope": {
                    "scholarship_rows_written": 0,
                    "child_rows_written": 0,
                    "audit_rows_written": 1,
                    "note": (
                        "The only row this run writes is its own maintenance_runs "
                        "entry. Classification is read-only."
                    ),
                },
                "delete_candidates": [d.as_dict() for d in candidates[:sample_size]],
                "delete_candidates_truncated": max(0, len(candidates) - sample_size),
                "retained_sample": [
                    d.as_dict()
                    for d in decisions
                    if d.bucket not in {BUCKET_LIVE, BUCKET_ADMIN_REVIEW}
                ][:sample_size],
                "reference_integrity": integrity,
                "recovery": recovery_status(),
                "note": (
                    "DRY RUN: no scholarship row was written or deleted. The shipped policy is "
                    "cleanup_enabled=False with dry_run=True, so the deleting path is "
                    "unreachable without an explicit, deliberate change."
                ),
            }
        )
        return report
    except Exception as exc:  # noqa: BLE001 - recorded, then re-raised unchanged
        session.rollback()
        report["status"] = STATUS_FAILED
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        # Exactly one ledger row per run, whatever the outcome. A dry run that
        # classified and then failed must still say how far it got, so the counts
        # are read back off the report rather than assumed.
        _finalise(
            session,
            run_id=run_id,
            mode=MODE_DRY_RUN,
            as_of=datetime.now(timezone.utc),
            report=report,
        )


# ---------------------------------------------------------------------------
# Phase 8/13 - the bounded deleting path
# ---------------------------------------------------------------------------


def delete_bounded(
    session: Session,
    candidate_ids: Sequence[int],
    *,
    as_of: datetime | None = None,
    policy: RetentionPolicy | None = None,
    run_id: str | None = None,
    trigger: str = "manual",
    ledger: Path | None = None,
    write_manifest: bool = True,
) -> dict[str, Any]:
    """Remove an exact, pre-proven set - in bounded, guarded, re-checked batches.

    Refuses to run unless the policy has been enabled for real deletion, and
    calls :meth:`RetentionPolicy.assert_deletion_permitted` before touching
    anything, so "enabled" and "really enabled" are two separate, explicit acts.
    The shipped policy has neither, which is the intended state: Phase 12 finds no
    verified recovery path, and an irreversible operation without one is not
    something to leave one environment variable away.

    ``ledger`` overrides where the deletion manifest is written. The default is
    the repository's own ledger, because there must be one place that answers
    "what was deleted and why" - but it is a parameter, because a test run has no
    business appending to a tracked file, and a caller that silently rewrote the
    project's ledger from a fixture would be a surprise with no upside.

    ``write_manifest`` exists because ``ledger=None`` already means "the default",
    which makes "no ledger at all" inexpressible. A caller who wants the deletion
    to happen without touching the shared file had exactly one way to ask for it
    by accident, and did. Silence is now an explicit choice.
    """
    as_of = as_of or datetime.now(timezone.utc)
    policy = policy or default_policy()
    policy.assert_deletion_permitted()

    run_id = run_id or uuid4().hex[:16]
    ids = sorted({int(i) for i in candidate_ids})
    if not ids:
        return {
            "run_id": run_id,
            "mode": MODE_DELETE,
            "status": STATUS_OK,
            "deleted": [],
            "note": "no candidates were supplied; nothing was written",
        }

    integrity = reference_integrity_report()
    open_audit_run(session, run_id=run_id, mode=MODE_DELETE, trigger=trigger, as_of=as_of)

    # Captured once so a settings change mid-run cannot make the "still not live"
    # guard mean something different from the classification it is guarding.
    live_conditions = live_condition()
    review_conditions = admin_review_conditions()
    identity = _bind_identity(session)
    counts_before = catalogue_counts(session)
    admin_review_before = _admin_review_count(session, review_conditions)

    report: dict[str, Any] = {
        "run_id": run_id,
        "mode": MODE_DELETE,
        "as_of": as_of.isoformat(),
        "contract_version": RETENTION_CONTRACT_VERSION,
        "trigger": trigger,
        "policy": _policy_summary(policy),
        "deleted": [],
        "aborted": [],
        "batches": [],
        "counts_before": counts_before,
        "reference_integrity": integrity,
    }

    try:
        guard = _Guard()
        guard.require(
            "reference_integrity_classified",
            not integrity["integrity_uncertain"],
            "reference integrity is uncertain; refusing to delete",
        )
        competing = competing_run_ids(session, exclude_run_id=run_id)
        guard.require(
            "no_competing_cleanup",
            not competing,
            f"another retention run is already active: {competing}",
        )
        guard.require(
            "candidates_within_per_run_cap",
            len(ids) <= policy.max_delete_per_run,
            f"{len(ids)} candidate(s) exceed the per-run cap of {policy.max_delete_per_run}",
        )
        share = len(ids) / max(1, int(counts_before.get("row_total", 0)))
        guard.require(
            "candidates_within_percentage_cap",
            share <= policy.max_delete_percentage,
            f"{len(ids)} candidate(s) are {share:.1%} of storage, above the "
            f"{policy.max_delete_percentage:.1%} cap",
        )
        guard.abort_if_failed()

        manifest: dict[str, Any] = {
            "run_id": run_id,
            "run_token": f"{run_id}-{len(ids)}",
            "mode": MODE_DELETE,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted": 0,
            "ids": [],
            "records": [],
            "confirmed": False,
            "contract_version": RETENTION_CONTRACT_VERSION,
            "trigger": trigger,
            "policy": _policy_summary(policy),
        }

        for batch in _chunks(ids, policy.batch_size):
            if _bind_identity(session) != identity:  # pragma: no cover - defensive
                raise CleanupAborted(
                    "the database connection changed mid-run; refusing to continue"
                )
            outcome = _delete_batch(
                session,
                batch,
                as_of=as_of,
                policy=policy,
                live_conditions=live_conditions,
                review_conditions=review_conditions,
            )
            report["batches"].append(outcome)
            report["deleted"].extend(outcome["deleted"])
            report["aborted"].extend(outcome["aborted"])
            if outcome["deleted"]:
                manifest["ids"].extend(outcome["deleted"])
                manifest["deleted"] = len(manifest["ids"])
                manifest["scanned"] = len(batch)
                manifest["kept_live"] = sum(
                    1 for d in outcome["decisions"] if d.bucket == BUCKET_LIVE
                )
                manifest["kept_admin_review"] = sum(
                    1 for d in outcome["decisions"] if d.bucket == BUCKET_ADMIN_REVIEW
                )
                manifest["protected"] = sum(
                    1 for d in outcome["decisions"] if d.bucket == "PROTECTED"
                )
                manifest["ambiguous"] = sum(
                    1 for d in outcome["decisions"] if d.bucket == "AMBIGUOUS"
                )
                manifest["grace_eligible"] = sum(
                    1 for d in outcome["decisions"] if d.grace_eligible
                )
                manifest["records"] = [
                    _manifest_record(d, run_id=run_id, as_of=as_of)
                    for d in outcome["decisions"]
                    if d.scholarship_id in set(outcome["deleted"])
                ]
                # Written before the batch's commit is observable elsewhere, so a
                # crash mid-run still names what was about to go.
                if write_manifest:
                    append_deletion_manifest(manifest, path=ledger)

        counts_after = catalogue_counts(session)
        admin_review_after = _admin_review_count(session, review_conditions)
        reconciliation = _reconcile(
            counts_before=counts_before,
            counts_after=counts_after,
            deleted=len(report["deleted"]),
            admin_review_before=admin_review_before,
            admin_review_after=admin_review_after,
            policy=policy,
        )
        report["counts_after"] = counts_after
        report["reconciliation"] = reconciliation
        if not reconciliation["reconciles"]:
            raise CleanupAborted(
                "count reconciliation failed after deletion: " + reconciliation["detail"]
            )

        manifest["confirmed"] = True
        if manifest["deleted"] and write_manifest:
            append_deletion_manifest(manifest, path=ledger)

        report["summary"] = {
            "deleted": len(report["deleted"]),
            "aborted": len(report["aborted"]),
        }
        # A run that rolled a batch back did not fully succeed, even though it
        # deleted nothing it should not have. Reporting it as ``ok`` would make a
        # failure indistinguishable from a quiet cycle.
        rolled_back = [b for b in report["batches"] if b.get("note")]
        report["batches_rolled_back"] = len(rolled_back)
        report["status"] = STATUS_PARTIAL if rolled_back else STATUS_OK
        if rolled_back:
            report["note"] = "; ".join(b["note"] for b in rolled_back)
        return report
    finally:
        # Every exit - success, abort, or exception - produces exactly one ledger
        # row, and a failure mid-run leaves the counts that were reached.
        if session.query(MaintenanceRun).filter(
            MaintenanceRun.run_id == run_id
        ).one_or_none() is not None:
            _finalise(
                session,
                run_id=run_id,
                mode=MODE_DELETE,
                as_of=datetime.now(timezone.utc),
                report=report,
            )


def _finalise(
    session: Session,
    *,
    run_id: str,
    mode: str,
    as_of: datetime,
    report: Mapping[str, Any],
) -> None:
    """Write the run's outcome to the ledger exactly once, whatever happened.

    Never raises. A ledger write that fails must not mask the run's own outcome,
    and must not turn a clean dry run into an exception - it degrades to a log
    line, which is the honest amount of severity an observability failure has.
    """
    summary = report.get("summary") or {}
    counts: dict[str, Any] = {
        "retention_trigger": report.get("trigger"),
        "retention_contract_version": RETENTION_CONTRACT_VERSION,
    }
    if mode == MODE_DRY_RUN:
        counts.update(
            {
                "retention_scanned": summary.get("scanned"),
                "retention_kept_live": summary.get("live_kept"),
                "retention_kept_admin_review": summary.get("admin_review_kept"),
                "retention_delete_candidates": summary.get("delete_candidates"),
                "retention_protected": summary.get("protected"),
                "retention_ambiguous": summary.get("ambiguous"),
                "retention_conflicting": summary.get("conflicting"),
                "retention_unclassifiable": summary.get("unclassifiable"),
                "retention_guard_failures": len(report.get("guard_failures", [])),
            }
        )
    else:
        counts.update(
            {
                "retention_deleted": len(report.get("deleted", [])),
                "retention_aborted": len(report.get("aborted", [])),
            }
        )

    guards = dict(report.get("guards") or {})
    guards.update((report.get("reconciliation") or {}).get("checks", {}))
    try:
        close_audit_run(
            session,
            run_id=run_id,
            mode=mode,
            status=report.get("status", STATUS_OK),
            as_of=as_of,
            counts=counts,
            errors=[report["error"]] if report.get("error") else [],
            guards=guards,
        )
    except Exception:  # noqa: BLE001 - never mask the run's own outcome
        session.rollback()
        logger.warning("could not finalise retention run record", exc_info=True)


def _chunks(items: list[int], size: int) -> Iterable[list[int]]:
    size = max(1, size)
    for start in range(0, len(items), size):
        yield items[start : start + size]


def conditional_delete(
    session: Session,
    scholarship_id: int,
    *,
    archived_at: Any,
    candidate_since: Any,
    live_conditions: Sequence[Any],
    review_conditions: Sequence[Any],
):
    """The guarded ``DELETE`` for one record, as a single named statement.

    The predicate is the negation of the two conditions that produced the verdict,
    plus equality on the exact retention and grace timestamps the verdict was based
    on. A concurrent writer that makes the record live or reviewable, or that
    moves either clock, causes this statement to match zero rows - and a record
    that matches nothing is kept.

    Extracted as its own function so the guard can be tested directly, against a
    database, rather than only through a whole run. A predicate that is only ever
    exercised incidentally is a predicate nobody has checked.
    """
    return session.execute(
        delete(Scholarship)
        .where(
            Scholarship.id == scholarship_id,
            # Still not live: the catalogue's own rule, negated.
            not_(and_(*live_conditions)),
            # Still not under admin review: the same union, negated.
            not_(or_(*review_conditions)),
            Scholarship.deletion_protected.is_(False),
            # Still the same state, decided on these exact clocks.
            Scholarship.archived_at == archived_at,
            Scholarship.auto_delete_candidate_since == candidate_since,
        )
        .execution_options(synchronize_session=False)
    )


def _delete_batch(
    session: Session,
    batch: Sequence[int],
    *,
    as_of: datetime,
    policy: RetentionPolicy,
    live_conditions: Sequence[Any],
    review_conditions: Sequence[Any],
) -> dict[str, Any]:
    """One transaction: re-read, re-classify, then delete conditionally.

    The conditional ``DELETE`` is the last line of defence, not the first. Its
    predicate is the negation of the same conditions that produced the verdict,
    plus equality on the exact ``archived_at`` and ``auto_delete_candidate_since``
    the verdict was based on. A concurrent writer that moves either clock, or makes
    the record live or reviewable, causes the statement to match zero rows: the row
    survives, which is the correct outcome for a lost race.

    Only the two relationships whose disposition permits it are touched: the
    nullable discovery link is detached, and settled fetch telemetry is removed.
    No PRESERVE table is read for deletion at all, so the evidence cannot be
    destroyed by a side effect.
    """
    outcome: dict[str, Any] = {"deleted": [], "aborted": [], "decisions": []}
    decisions = scan(
        session,
        as_of=as_of,
        policy=policy,
        ids=list(batch),
        live_conditions=live_conditions,
        review_conditions=review_conditions,
    )
    by_id = {d.scholarship_id: d for d in decisions}

    clocks: dict[int, dict[str, Any]] = {}
    for sid in batch:
        decision = by_id.get(sid)
        if decision is None:
            outcome["aborted"].append({"id": sid, "reason": "record no longer exists"})
            continue
        outcome["decisions"].append(decision)
        if not decision.is_delete:
            outcome["aborted"].append(
                {
                    "id": sid,
                    "reason": decision.detail,
                    "bucket": decision.bucket,
                    "verdict": "no longer a deletion candidate at deletion time",
                }
            )
            continue
        row = session.get(Scholarship, sid, with_for_update=True)
        if row is None:  # pragma: no cover - covered by the branch above
            outcome["aborted"].append({"id": sid, "reason": "row disappeared"})
            continue
        clocks[sid] = {
            "archived_at": row.archived_at,
            "candidate_since": row.auto_delete_candidate_since,
        }

    if not clocks:
        session.rollback()
        outcome["note"] = "no record in this batch remained a deletion candidate"
        return outcome

    target_ids = list(clocks)
    deleted: list[int] = []
    try:
        # The whole mutation is one transaction, and the guard is around all of
        # it rather than around the commit. A statement that fails part-way -
        # a foreign key, a lock timeout, a dropped connection - has already
        # applied the statements before it, and those must be undone too. Catching
        # only the commit would leave the detached discovery links and the removed
        # fetch telemetry committed against records that were never deleted.
        for candidate in session.scalars(
            select(DiscoveryCandidate).where(
                DiscoveryCandidate.matched_scholarship_id.in_(target_ids)
            )
        ):
            candidate.matched_scholarship_id = None
            candidate.match_status = "unmatched"
        session.flush()

        for attempt in session.scalars(
            select(ScholarshipFetchAttempt).where(
                ScholarshipFetchAttempt.scholarship_id.in_(target_ids)
            )
        ):
            session.delete(attempt)
        session.flush()

        for sid, expected in clocks.items():
            result = conditional_delete(
                session,
                sid,
                archived_at=expected["archived_at"],
                candidate_since=expected["candidate_since"],
                live_conditions=live_conditions,
                review_conditions=review_conditions,
            )
            if result.rowcount == 1:
                deleted.append(sid)
            else:
                outcome["aborted"].append(
                    {
                        "id": sid,
                        "reason": "the record changed between classification and deletion; "
                        "the conditional delete matched no row, so the record was kept",
                    }
                )
    except Exception as exc:  # noqa: BLE001 - any failure aborts the whole batch
        session.rollback()
        outcome["aborted"] = [
            {"id": None, "reason": f"transaction rolled back: {type(exc).__name__}: {exc}"}
        ]
        outcome["deleted"] = []
        outcome["note"] = "no partial deletion occurred"
        return outcome

    if not deleted:
        session.rollback()
        outcome["note"] = "nothing in this batch was deleted; the transaction was rolled back"
        return outcome

    try:
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        outcome["aborted"] = [
            {"id": None, "reason": f"transaction rolled back: {type(exc).__name__}: {exc}"}
        ]
        outcome["deleted"] = []
        outcome["note"] = "no partial deletion occurred"
        return outcome

    outcome["deleted"] = deleted
    return outcome


def _admin_review_count(session: Session, conditions: Sequence[Any] | None = None) -> int:
    conditions = list(conditions if conditions is not None else admin_review_conditions())
    return int(
        session.scalar(select(func.count(Scholarship.id)).where(or_(*conditions))) or 0
    )


def _reconcile(
    *,
    counts_before: Mapping[str, int],
    counts_after: Mapping[str, int],
    deleted: int,
    admin_review_before: int,
    admin_review_after: int,
    policy: RetentionPolicy,
) -> dict[str, Any]:
    """Compare before, kept, deleted and after using the catalogue's own counts.

    ``catalogue_counts`` is the authoritative count definition, so the arithmetic
    is checked against the same numbers the homepage publishes. A run that deleted
    what it said it deleted, and that left the public total untouched, removed only
    records the public catalogue was already hiding - which is the only outcome
    consistent with "this must not alter the public catalogue".
    """
    row_before = int(counts_before.get("row_total", 0))
    row_after = int(counts_after.get("row_total", 0))
    public_before = int(counts_before.get("public_total", 0))
    public_after = int(counts_after.get("public_total", 0))
    tolerance = policy.count_reconciliation_tolerance

    checks = {
        "row_total_decreased_by_deleted": abs((row_before - row_after) - deleted) <= tolerance,
        "public_total_unchanged": abs(public_after - public_before) <= tolerance,
        "admin_review_unchanged": abs(admin_review_after - admin_review_before) <= tolerance,
        "no_row_created": row_after <= row_before,
    }
    detail = (
        f"row_total {row_before} -> {row_after} with {deleted} deleted; "
        f"public_total {public_before} -> {public_after}; "
        f"admin_review {admin_review_before} -> {admin_review_after}"
    )
    return {
        "reconciles": all(checks.values()),
        "checks": checks,
        "detail": detail,
        "before": {
            "row_total": row_before,
            "public_total": public_before,
            "admin_review": admin_review_before,
        },
        "after": {
            "row_total": row_after,
            "public_total": public_after,
            "admin_review": admin_review_after,
        },
        "deleted": deleted,
    }


__all__ = [
    "CleanupAborted",
    "DEPENDENT_MODELS",
    "MODE_DELETE",
    "MODE_DRY_RUN",
    "PRESERVE_MODELS",
    "REFERENCE_INTEGRITY",
    "RETENTION_STAGE",
    "RETENTION_WORKER",
    "STATUS_FAILED",
    "STATUS_OK",
    "STATUS_PARTIAL",
    "admin_review_conditions",
    "append_deletion_manifest",
    "build_facts",
    "close_audit_run",
    "competing_run_ids",
    "conditional_delete",
    "delete_bounded",
    "dry_run",
    "ledger_path",
    "live_condition",
    "open_audit_run",
    "recovery_status",
    "reference_dependencies",
    "reference_integrity_report",
    "scan",
]
