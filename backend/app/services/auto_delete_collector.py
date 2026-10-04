"""Gathering the facts the SAFE_DELETE policy needs, and executing a deletion.

The policy in :mod:`app.services.auto_delete_policy` decides. This module does
the two things that need a database:

* assemble :class:`RecordFacts` for every candidate, using the canonical
  ``public_visibility_conditions()`` rather than a second copy of the visibility
  rule;
* delete an exact set of ids, re-deciding each one inside the transaction.

The re-decision is the point. The candidate list is a snapshot taken earlier -
possibly a day ago, possibly seconds ago. Between deciding and deleting, a record
can be reopened, re-verified, reviewed, referenced, or have its deadline
corrected. Deleting on a stale decision is how a collector destroys a record that
came back to life, so every id is re-read under a row lock and re-evaluated, and
any record whose verdict is no longer ``SAFE_DELETE`` is aborted individually
rather than deleted alongside the others.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select

from app.repositories.scholarships import public_visibility_conditions
from app.services.auto_delete_policy import (
    AUTO_DELETE_AFTER_DAYS,
    DELETE_GRACE_DAYS,
    VERDICT_SAFE_DELETE,
    AutoDeleteDecision,
    DependencySummary,
    RecordFacts,
    always_blocking,
    classify_candidates,
    classify_fetch_attempts,
    classify_history,
    classify_image_reviews,
    classify_reviews,
    evaluate,
    merge,
)

#: Bumped when the policy's meaning changes, so a manifest says which contract
#: produced a deletion rather than only that one happened.
CONTRACT_VERSION = "auto-delete/1"

#: The tables whose rows must not disappear with a parent, and why. Anything not
#: listed here is either detached or carried into the manifest first.
DEPENDENT_MODELS = (
    "ScholarshipReview",
    "ScholarshipVerificationHistory",
    "ScholarshipSnapshot",
    "ScholarshipRestoreRecord",
    "ScholarshipFetchAttempt",
    "ImageReview",
    "DiscoveryCandidate",
)


def _aware(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _public_ids(session) -> set[int]:
    """The canonical public set. Never re-implemented here."""
    from app.models import Scholarship

    return set(
        session.scalars(
            select(Scholarship.id).where(*public_visibility_conditions())
        ).all()
    )


def _rows_for(session, model, column_name: str, ids: list[int]) -> list[Any]:
    if not ids:
        return []
    column = getattr(model, column_name)
    return list(session.scalars(select(model).where(column.in_(ids))).all())


def _snapshot_row_payload(row: Any) -> dict[str, Any]:
    from sqlalchemy import inspect as sa_inspect

    return {attr.key: attr.value for attr in sa_inspect(row).attrs}


def dependencies_for(session, ids: list[int]) -> dict[int, DependencySummary]:
    """Classify every dependent row for each id.

    Each table is classified on its own terms rather than counted, because
    "five fetch attempts" is not the same as "one fetch attempt that never
    settled": the first is telemetry, the second is pending work.
    """
    from app.models import (
        DiscoveryCandidate,
        ImageReview,
        ScholarshipFetchAttempt,
        ScholarshipRestoreRecord,
        ScholarshipReview,
        ScholarshipSnapshot,
        ScholarshipVerificationHistory,
    )

    per_model: dict[str, dict[int, list[Any]]] = {
        "ScholarshipReview": {},
        "ScholarshipVerificationHistory": {},
        "ScholarshipSnapshot": {},
        "ScholarshipRestoreRecord": {},
        "ScholarshipFetchAttempt": {},
        "ImageReview": {},
    }
    for model, key in (
        (ScholarshipReview, "ScholarshipReview"),
        (ScholarshipVerificationHistory, "ScholarshipVerificationHistory"),
        (ScholarshipSnapshot, "ScholarshipSnapshot"),
        (ScholarshipRestoreRecord, "ScholarshipRestoreRecord"),
        (ScholarshipFetchAttempt, "ScholarshipFetchAttempt"),
        (ImageReview, "ImageReview"),
    ):
        for row in _rows_for(session, model, "scholarship_id", ids):
            per_model[key].setdefault(row.scholarship_id, []).append(row)

    candidates: dict[int, list[Any]] = {}
    for row in _rows_for(session, DiscoveryCandidate, "matched_scholarship_id", ids):
        candidates.setdefault(row.matched_scholarship_id, []).append(row)

    out: dict[int, DependencySummary] = {}
    for sid in ids:
        out[sid] = merge(
            classify_reviews(per_model["ScholarshipReview"].get(sid, [])),
            classify_history(per_model["ScholarshipVerificationHistory"].get(sid, [])),
            always_blocking(
                "ScholarshipSnapshot",
                per_model["ScholarshipSnapshot"].get(sid, []),
                "snapshot row(s); a snapshot is the record's own history",
            ),
            always_blocking(
                "ScholarshipRestoreRecord",
                per_model["ScholarshipRestoreRecord"].get(sid, []),
                "restore record(s)",
            ),
            classify_fetch_attempts(per_model["ScholarshipFetchAttempt"].get(sid, [])),
            classify_image_reviews(per_model["ImageReview"].get(sid, [])),
            classify_candidates(candidates.get(sid, [])),
        )
    return out


def collect(
    session,
    *,
    now: datetime | None = None,
    retention_days: int = AUTO_DELETE_AFTER_DAYS,
    grace_days: int = DELETE_GRACE_DAYS,
) -> list[AutoDeleteDecision]:
    """Evaluate every row. Read-only: this function never writes."""
    from app.models import Scholarship

    now = now or datetime.now(timezone.utc)
    rows = list(session.scalars(select(Scholarship)).all())
    public = _public_ids(session)
    deps = dependencies_for(session, [row.id for row in rows])

    decisions: list[AutoDeleteDecision] = []
    for row in rows:
        facts = RecordFacts(
            id=row.id,
            title=row.title or "",
            status=row.status or "",
            is_archived=bool(row.is_archived),
            archived_at=_aware(row.archived_at),
            verification_status=row.verification_status or "",
            is_public=row.id in public,
            deadline_date=row.deadline_date,
            updated_at=_aware(row.updated_at),
            deletion_protected=bool(getattr(row, "deletion_protected", False)),
            dependencies=deps.get(row.id, DependencySummary()),
        )
        decisions.append(
            evaluate(
                facts,
                now=now,
                candidate_since=_aware(getattr(row, "auto_delete_candidate_since", None)),
                retention_days=retention_days,
                grace_days=grace_days,
            )
        )
    return decisions


def arm(
    session,
    decisions: list[AutoDeleteDecision],
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage one: record which records currently hold every condition.

    The grace clock starts here, and it is cleared the moment any condition stops
    holding. That is the whole point of persisting it: a record that reopens and
    re-closes between two cycles must serve the full grace period again, and
    nothing already on the row can tell that happened.
    """
    from app.models import Scholarship

    now = now or datetime.now(timezone.utc)
    armed: list[int] = []
    cleared: list[int] = []
    unchanged = 0

    for decision in decisions:
        qualifies = decision.verdict in ("SAFE_DELETE", "AUTO_DELETE_CANDIDATE")
        row = session.get(Scholarship, decision.id)
        if row is None:
            continue
        current = _aware(getattr(row, "auto_delete_candidate_since", None))

        if qualifies and current is None:
            armed.append(decision.id)
            if not dry_run:
                row.auto_delete_candidate_since = now
        elif qualifies:
            unchanged += 1
        elif current is not None:
            cleared.append(decision.id)
            if not dry_run:
                row.auto_delete_candidate_since = None
        else:
            unchanged += 1

    if not dry_run and (armed or cleared):
        session.commit()
    elif dry_run:
        session.rollback()

    return {
        "mode": "DRY RUN" if dry_run else "LIVE",
        "newly_armed": sorted(armed),
        "disarmed": sorted(cleared),
        "already_armed": unchanged,
        "note": (
            "grace clock starts now for every newly armed record; nothing is deleted "
            "by this stage"
        ),
    }


def _revalidate(session, sid: int, *, now: datetime) -> AutoDeleteDecision | None:
    """Re-read one row under a lock and re-decide it.

    ``with_for_update`` is honoured on Postgres and ignored on SQLite, which is
    why the caller still compares the row's own timestamps afterwards: the
    re-decision is the guarantee, and the lock only narrows the window.
    """
    from app.models import Scholarship

    row = session.get(Scholarship, sid, with_for_update=True)
    if row is None:
        return None
    deps = dependencies_for(session, [sid])
    facts = RecordFacts(
        id=row.id,
        title=row.title or "",
        status=row.status or "",
        is_archived=bool(row.is_archived),
        archived_at=_aware(row.archived_at),
        verification_status=row.verification_status or "",
        is_public=row.id in _public_ids(session),
        deadline_date=row.deadline_date,
        updated_at=_aware(row.updated_at),
        deletion_protected=bool(getattr(row, "deletion_protected", False)),
        dependencies=deps.get(sid, DependencySummary()),
    )
    return evaluate(facts, now=now, candidate_since=_aware(row.auto_delete_candidate_since))


def _append_manifest(path: Path, entry: dict[str, Any]) -> None:
    """Persist what is about to disappear, before it does.

    The existing archive already holds full snapshots of purged records, so this
    extends that file rather than introducing a second audit trail.

    Called twice per deletion: once with ``confirmed: False`` before the delete
    commits, and once with ``confirmed: True`` afterwards. The order matters more
    than it looks. Writing only after the commit means a process that dies
    between the two leaves rows deleted and nothing written down - which is the
    one outcome that cannot be recovered from. Writing first can over-report a
    deletion that then fails, and an over-reported deletion is repaired by
    reading the id back out of the database.
    """
    existing: dict[str, Any] = {"purged_at": None, "count": 0, "records": [], "batches": []}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A corrupt archive must not silently absorb a new manifest.
            existing = {
                "purged_at": None,
                "count": 0,
                "records": [],
                "batches": [],
                "note": "previous archive was unreadable and has been preserved alongside",
            }
    batches = existing.setdefault("batches", [])
    # Replace the pending entry for this run rather than appending a second one,
    # so confirming a deletion cannot double-count it.
    batches[:] = [
        b
        for b in batches
        if not (
            b.get("confirmed") is False
            and b.get("run_token") == entry.get("run_token")
            and b.get("deleted_at") == entry.get("deleted_at")
        )
    ]
    batches.append(entry)
    existing["purged_at"] = entry["deleted_at"]
    # `count` only advances once a deletion is confirmed, so an unconfirmed
    # entry never inflates the total.
    existing["count"] = int(existing.get("count") or 0) + (
        entry["deleted"] if entry.get("confirmed") else 0
    )
    confirmed_records = [r for b in batches for r in b.get("records", []) if b.get("confirmed")]
    existing["records"] = confirmed_records
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def delete_exact(
    session,
    ids: Iterable[int],
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    archive_path: Path,
    system: str = "scholarzone_maintenance:auto_delete",
) -> dict[str, Any]:
    """Stage two: delete exactly these ids, or nothing at all.

    Every id is re-decided inside the transaction. One id failing to revalidate
    aborts that record only, so a single record that came back to life cannot
    stop the collector or, worse, be deleted on the stale decision.
    """
    from app.models import (
        DiscoveryCandidate,
        ImageReview,
        Scholarship,
        ScholarshipFetchAttempt,
        ScholarshipRestoreRecord,
        ScholarshipReview,
        ScholarshipSnapshot,
        ScholarshipVerificationHistory,
    )

    now = now or datetime.now(timezone.utc)
    ids = sorted(set(int(i) for i in ids))

    report: dict[str, Any] = {
        "mode": "DRY RUN" if dry_run else "LIVE",
        "contract_version": CONTRACT_VERSION,
        "system": system,
        "requested_ids": ids,
        "deleted": [],
        "aborted": [],
        "child_rows_removed": 0,
        "candidates_detached": 0,
        "records": [],
    }

    if not ids:
        report["note"] = "NO SAFE DELETE TARGETS"
        return report

    # The manifest is assembled before any delete so a failure part-way still
    # leaves a record of what was removed.
    verified: dict[int, AutoDeleteDecision] = {}
    for sid in ids:
        decision = _revalidate(session, sid, now=now)
        if decision is None:
            report["aborted"].append({"id": sid, "reason": "row disappeared before deletion"})
            continue
        if decision.verdict != VERDICT_SAFE_DELETE:
            report["aborted"].append(
                {"id": sid, "reason": decision.reason, "verdict": decision.verdict}
            )
            continue
        verified[sid] = decision

    report["eligible_after_revalidation"] = sorted(verified)

    if dry_run:
        session.rollback()
        for sid, decision in verified.items():
            report["records"].append(decision.as_dict())
        report["deleted"] = sorted(verified)
        report["note"] = (
            "DRY RUN: no rows were written. These ids would be deleted on a LIVE run."
        )
        return report

    if not verified:
        session.rollback()
        report["note"] = "NO SAFE DELETE TARGETS after revalidation"
        return report

    # Snapshot every row that is about to disappear, parents and children alike.
    children_snapshot: dict[str, list[dict[str, Any]]] = {}
    for model, column in (
        (ScholarshipReview, "scholarship_id"),
        (ScholarshipVerificationHistory, "scholarship_id"),
        (ScholarshipSnapshot, "scholarship_id"),
        (ScholarshipRestoreRecord, "scholarship_id"),
        (ScholarshipFetchAttempt, "scholarship_id"),
        (ImageReview, "scholarship_id"),
    ):
        children_snapshot[model.__name__] = [
            _snapshot_row_payload(r)
            for r in _rows_for(session, model, column, sorted(verified))
        ]
    children_snapshot["DiscoveryCandidate"] = [
        _snapshot_row_payload(r)
        for r in _rows_for(
            session, DiscoveryCandidate, "matched_scholarship_id", sorted(verified)
        )
    ]

    parent_snapshot = [
        _snapshot_row_payload(session.get(Scholarship, sid)) for sid in sorted(verified)
    ]

    deleted_ids: list[int] = []
    removed = 0
    detached = 0

    manifest_entry = {
        "deleted_at": now.isoformat(),
        "deleted": len(verified),
        "ids": sorted(verified),
        "run_token": f"{now.timestamp():.0f}-{sorted(verified)}",
        "confirmed": False,
        "contract_version": CONTRACT_VERSION,
        "system": system,
        "policy": {
            "auto_delete_after_days": AUTO_DELETE_AFTER_DAYS,
            "delete_grace_days": DELETE_GRACE_DAYS,
        },
        "child_rows_removed": removed,
        "candidates_detached": detached,
        "children_counts": {k: len(v) for k, v in children_snapshot.items()},
        "children": children_snapshot,
        "parents": parent_snapshot,
        "records": [verified[sid].as_dict() for sid in sorted(verified)],
    }

    # Written before the delete commits. If the process dies in the next few
    # lines the database still says what was about to go, and the ids can be
    # reconciled; the reverse order would leave a deletion nobody can account for.
    _append_manifest(archive_path, manifest_entry)

    try:
        for candidate in _rows_for(
            session, DiscoveryCandidate, "matched_scholarship_id", sorted(verified)
        ):
            candidate.matched_scholarship_id = None
            candidate.match_status = "unmatched"
            detached += 1
        session.flush()

        for model, column in (
            (ScholarshipReview, "scholarship_id"),
            (ScholarshipVerificationHistory, "scholarship_id"),
            (ScholarshipSnapshot, "scholarship_id"),
            (ScholarshipRestoreRecord, "scholarship_id"),
            (ScholarshipFetchAttempt, "scholarship_id"),
            (ImageReview, "scholarship_id"),
        ):
            for child in _rows_for(session, model, column, sorted(verified)):
                session.delete(child)
                removed += 1
        session.flush()

        for sid in sorted(verified):
            row = session.get(Scholarship, sid)
            if row is None:
                continue
            session.delete(row)
            deleted_ids.append(sid)

        if not deleted_ids:
            session.rollback()
            report["note"] = "nothing was deleted; the transaction was rolled back"
            manifest_entry["confirmed"] = False
            manifest_entry["rolled_back"] = True
            _append_manifest(archive_path, manifest_entry)
            return report

        session.commit()
    except Exception:
        session.rollback()
        report["error"] = "transaction rolled back; no partial deletion occurred"
        report["aborted"].append({"id": None, "reason": "transaction rolled back"})
        manifest_entry["confirmed"] = False
        manifest_entry["rolled_back"] = True
        _append_manifest(archive_path, manifest_entry)
        return report

    manifest_entry.update(
        {
            "deleted": len(deleted_ids),
            "ids": deleted_ids,
            "child_rows_removed": removed,
            "candidates_detached": detached,
            "records": [verified[sid].as_dict() for sid in deleted_ids],
            "confirmed": True,
        }
    )
    _append_manifest(archive_path, manifest_entry)

    report["deleted"] = deleted_ids
    report["child_rows_removed"] = removed
    report["candidates_detached"] = detached
    report["manifest"] = str(archive_path)
    report["records"] = [verified[sid].as_dict() for sid in deleted_ids]
    report["note"] = (
        "NO SAFE DELETE TARGETS" if not deleted_ids else f"deleted {len(deleted_ids)} record(s)"
    )
    return report
