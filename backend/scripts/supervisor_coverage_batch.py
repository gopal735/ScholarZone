"""Manual, bounded supervisor-coverage pass over every public scholarship.

Run by an operator, on purpose, against a named database. Nothing schedules
this, no router imports it, and it cannot enable browser rendering: it passes no
render budget, so a client-side directory remains SOURCE_REQUIRES_RENDERING
exactly as in the one-scholarship proof workflow.

    # What would happen? Nothing. This is the default posture.
    python scripts/supervisor_coverage_batch.py --dry-run --limit 25

    # Do it, bounded, resumable, audited.
    python scripts/supervisor_coverage_batch.py --limit 25 --resume \\
        --audit backend/reports/supervisor_batch_audit.jsonl \\
        --state backend/reports/supervisor_batch_state.json

Every flag that could widen the work - the record limit, an archived-record
inclusion, retrying previously examined states, more workers - is off by default
and must be named on the command line.

The write scope is the database in SCHOLARZONE_DATABASE_URL. Point it at a copy
or a copy of the file before a first run; the coverage gates never write to a
scholarship, but the supervisor tables in the target database are what this
script populates.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

from app.database import get_session_factory  # noqa: E402
from app.services.supervisor_batch import (  # noqa: E402
    DEFAULT_LIMIT,
    MAX_WORKERS,
    BatchOptions,
    read_state,
    run_supervisor_batch,
)
from app.services.supervisor_status import (  # noqa: E402
    INCONCLUSIVE_COVERAGE_STATUSES,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supervisor_coverage_batch.py",
        description=(
            "One bounded supervisor-discovery pass over public scholarships. "
            "Reads only the database in SCHOLARZONE_DATABASE_URL. Writes nothing "
            "unless --dry-run is omitted."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum records this run processes (default {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the proposed changes and write nothing at all.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue after the scholarship id recorded in --state.",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("backend/reports/supervisor_batch_state.json"),
        help="Where the resume cursor is kept (default: %(default)s).",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("backend/reports/supervisor_batch_audit.jsonl"),
        help="Where one JSON line per processed record is appended (default: %(default)s).",
    )
    parser.add_argument(
        "--include-status",
        action="append",
        default=[],
        choices=sorted(INCONCLUSIVE_COVERAGE_STATUSES),
        help=(
            "Also process records whose last pass ended in this state. Repeatable. "
            "Only inconclusive states are offered: a completed negative is never "
            "re-run implicitly."
        ),
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived records. Off by default: they are not public.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=f"Universities in flight (1..{MAX_WORKERS}, default 1). One by default.",
    )
    parser.add_argument(
        "--no-contacts",
        action="store_true",
        help="Do not look for an official administrative contact.",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="Also write the machine-readable report to this path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.workers < 1 or args.workers > MAX_WORKERS:
        parser.error(f"--workers must be between 1 and {MAX_WORKERS}")
    if args.limit < 1:
        parser.error("--limit must be at least 1")

    # Rendering is a separate operator decision with a separate flag. This
    # script neither reads it nor sets it, and it passes no render budget, so a
    # browser-rendered directory stays SOURCE_REQUIRES_RENDERING.
    if os.environ.get("SCHOLARZONE_SUPERVISOR_RENDER_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        print(
            "Note: SCHOLARZONE_SUPERVISOR_RENDER_ENABLED is set in this shell. "
            "This script does not use it and does not unset it; batch outcomes "
            "are unaffected either way.",
            file=sys.stderr,
        )

    after_id = None
    if args.resume:
        after_id = read_state(args.state).get("last_scholarship_id")
        print(f"Resuming after scholarship id: {after_id!r}", file=sys.stderr)

    options = BatchOptions(
        limit=args.limit,
        dry_run=args.dry_run,
        include_archived=args.include_archived,
        include_statuses=frozenset(args.include_status),
        after_id=after_id,
        workers=args.workers,
        collect_contacts=not args.no_contacts,
        audit_path=None if args.dry_run else args.audit,
        state_path=None if args.dry_run else args.state,
    )

    session = get_session_factory()()
    try:
        report = run_supervisor_batch(session, options)
    finally:
        session.close()

    print(json.dumps(report.to_dict(), indent=2))
    if args.report_out is not None:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    totals = report.totals
    print(
        "\n"
        f"{'DRY RUN - nothing written' if report.dry_run else 'Completed'}: "
        f"processed={totals['processed']} "
        f"verified={totals['verified_supervisors']} "
        f"not_applicable={totals['not_applicable']} "
        f"professors_written={totals['professors_written']} "
        f"contacts={totals['contacts_collected']}"
    )
    for key, value in sorted(totals.items()):
        if key.startswith("status:"):
            print(f"  {key[len('status:'):]}: {value}")
    if not args.dry_run:
        print(f"Resume cursor: {report.next_cursor} (selection_exhausted={report.selection_exhausted})")
        print(f"Audit log: {args.audit}")
        print(f"State file: {args.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
