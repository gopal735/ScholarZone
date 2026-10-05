"""Run the retention classifier, and only ever delete what it has proved.

The command has two modes and they are not symmetric. ``--dry-run`` is the
default and is the only mode that can run without an explicit acknowledgement;
``--execute-delete`` is reachable only when the policy enables it *and* the caller
names why recovery is available, because Phase 12 of the contract found none.

    python scripts/retention_dry_run.py
    python scripts/retention_dry_run.py --json
    python scripts/retention_dry_run.py --execute-delete \
        --recovery-path "neon-pitr-verified-2026-10-05" --confirm-ids 123,456

The default run touches exactly one row in the database: the ``maintenance_runs``
entry that records the run. It deletes nothing, and it changes no scholarship.

Deleting is not scheduled, not wired into the maintenance worker, and not
reachable from ``--stage all``. It is invoked by hand, against a named set of ids,
with a recovery path on the command line - so the authorisation is part of the
command's history rather than a value in a configuration file that could have been
set months ago by somebody who meant something narrower.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.database import get_session_factory  # noqa: E402
from app.services.retention_contract import RetentionPolicy  # noqa: E402
from app.services.retention_engine import (  # noqa: E402
    CleanupAborted,
    delete_bounded,
    dry_run,
)


def _parse_ids(raw: str) -> list[int]:
    return [int(part) for part in raw.replace(" ", "").split(",") if part]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify scholarship storage, and delete only what is proven.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Deletion is held by default because no verified recovery path has been\n"
            "established. Proving one is a prerequisite, not a formality."
        ),
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--trigger", default="manual", help="recorded in the audit row")
    parser.add_argument(
        "--sample-size", type=int, default=25, help="candidates to print in full"
    )
    parser.add_argument(
        "--max-delete-per-run", type=int, default=None, help="override the per-run cap"
    )
    parser.add_argument(
        "--max-delete-percentage", type=float, default=None, help="override the share cap"
    )
    parser.add_argument(
        "--execute-delete",
        action="store_true",
        help="attempt a bounded deletion; refused unless the recovery path is named",
    )
    parser.add_argument(
        "--recovery-path",
        default=None,
        help="the verified recovery path that authorises irreversible deletion",
    )
    parser.add_argument(
        "--confirm-ids",
        default=None,
        help="comma-separated ids, which must match the classified candidates exactly",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    policy = RetentionPolicy()
    if args.max_delete_per_run is not None:
        policy = policy.with_overrides(max_delete_per_run=args.max_delete_per_run)
    if args.max_delete_percentage is not None:
        policy = policy.with_overrides(max_delete_percentage=args.max_delete_percentage)

    if not args.execute_delete:
        factory = get_session_factory()
        session = factory()
        try:
            report = dry_run(
                session,
                as_of=datetime.now(timezone.utc),
                policy=policy,
                trigger=args.trigger,
                sample_size=args.sample_size,
            )
        finally:
            session.close()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            _print_dry_run(report, settings.environment)
        # A blocked dry run is a finding, not a crash: the report is still the
        # answer to the question that was asked.
        return 0 if report["status"] == "ok" else 1

    # ---- Deleting mode. Every precondition is checked before anything runs. ----
    if not args.recovery_path:
        print(
            "REFUSED: --execute-delete requires --recovery-path.\n"
            "An audit ledger is not a backup. Without a verified way to restore a "
            "deleted row,\nhard deletion is not something this tool will perform.",
            file=sys.stderr,
        )
        return 2
    if not args.confirm_ids:
        print(
            "REFUSED: --execute-delete requires --confirm-ids naming the exact "
            "records to remove.",
            file=sys.stderr,
        )
        return 2

    ids = _parse_ids(args.confirm_ids)
    deleting = policy.with_overrides(cleanup_enabled=True, dry_run=False)
    factory = get_session_factory()
    session = factory()
    try:
        report = delete_bounded(
            session,
            ids,
            as_of=datetime.now(timezone.utc),
            policy=deleting,
            trigger=f"{args.trigger}:{args.recovery_path}",
        )
    except CleanupAborted as exc:
        print(f"ABORTED, nothing was deleted: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"deleted        : {report['summary']['deleted']}")
        print(f"aborted        : {report['summary']['aborted']}")
        print(f"reconciliation : {report['reconciliation']['detail']}")
    return 0


def _print_dry_run(report: dict, environment: str) -> None:
    summary = report["summary"]
    print("=" * 68)
    print("SCHOLARZONE RETENTION ENGINE - DRY RUN")
    print("=" * 68)
    print(f"run_id      : {report['run_id']}")
    print(f"environment : {environment}")
    print(f"contract    : {report['contract_version']}")
    print(f"trigger     : {report['trigger']}")
    print(f"status      : {report['status']}")
    print("-" * 68)
    print("CLASSIFICATION")
    print(f"  total scanned        : {summary['scanned']}")
    print(f"  live     (KEEP)      : {summary['live_kept']}")
    print(f"  admin review (KEEP)  : {summary['admin_review_kept']}")
    print(f"  protected            : {summary['protected']}")
    print(f"  ambiguous            : {summary['ambiguous']}")
    print(f"  conflicting          : {summary['conflicting']}")
    print(f"  delete candidates    : {summary['delete_candidates']}")
    print(f"  arithmetic reconciles: {summary['reconciles']}")
    print("-" * 68)
    print("PUBLIC CATALOGUE (before)")
    for key in ("row_total", "public_total", "archived", "quarantined"):
        if key in report["counts_before"]:
            print(f"  {key:22s}: {report['counts_before'][key]}")
    print("-" * 68)
    print("DELETE CANDIDATES")
    for candidate in report["delete_candidates"]:
        print(f"  {candidate['scholarship_id']:>8}  {candidate['reason']}")
        print(f"            {candidate['detail']}")
    if report["delete_candidates_truncated"]:
        print(f"  ... and {report['delete_candidates_truncated']} more")
    if not report["delete_candidates"]:
        print("  none - the retention rule is holding every record")
    print("-" * 68)
    print("GUARDS")
    for name, passed in report["guards"].items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    for failure in report["guard_failures"]:
        print(f"  ! {failure}")
    print("-" * 68)
    integrity = report["reference_integrity"]
    print(f"REFERENCE INTEGRITY: {integrity['verdict']}")
    for relationship in integrity["relationships"]:
        print(
            f"  {relationship['model']:32s} {relationship['disposition']:24s}"
            f" {relationship['database_enforcement']}"
        )
    print("-" * 68)
    recovery = report["recovery"]
    print(f"RECOVERY: {recovery['verdict']}")
    print(f"  {recovery['consequence']}")
    print("-" * 68)
    print(report["note"])


if __name__ == "__main__":
    raise SystemExit(main())
