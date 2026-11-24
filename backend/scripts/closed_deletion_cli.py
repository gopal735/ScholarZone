#!/usr/bin/env python
"""Closed scholarship permanent deletion CLI.

Usage:
    python scripts/closed_deletion_cli.py --dry-run
    python scripts/closed_deletion_cli.py --execute --confirm-production

This script implements the product rule: ALL scholarship records whose
effective lifecycle status is CLOSED must be permanently deleted.

SAFETY: By default, runs in dry-run mode. Live deletion requires
explicit --execute flag and confirmation.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import get_engine
from app.services.closed_deletion import (
    build_deletion_manifest,
    execute_deletion,
    save_manifest,
    save_report,
)
from sqlalchemy.orm import Session


def check_schema_ready(engine):
    """Read-only schema readiness check; never mutates schema."""
    from sqlalchemy import text
    required = {"scholarships", "purge_execution_ledger"}
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).fetchall()
    present = {r[0] for r in rows}
    missing = required - present
    if missing:
        print("ERROR: Required schema is not ready. Missing tables: " + ", ".join(sorted(missing)))
        print("Run the authorized migration process before executing this CLI.")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Closed scholarship permanent deletion")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Dry run (default)")
    group.add_argument("--execute", action="store_true", help="Execute actual deletion")
    parser.add_argument("--confirm-production", action="store_true", help="Confirm production target")
    parser.add_argument("--output-dir", default=".", help="Output directory for manifest/report")
    args = parser.parse_args()

    dry_run = not args.execute

    if args.execute and not args.confirm_production:
        print("ERROR: --execute requires --confirm-production")
        print("This is a safety gate. You must explicitly confirm the production target.")
        sys.exit(1)

    engine = get_engine()
    if not check_schema_ready(engine):
        sys.exit(1)
    print(f"Database dialect: {engine.dialect.name}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE DELETION'}")
    print()

    with Session(engine) as db:
        manifest = build_deletion_manifest(db)
        print(f"Found {len(manifest)} CLOSED scholarships for deletion")
        print()

        manifest_path = os.path.join(args.output_dir, "closed_deletion_manifest.json")
        save_manifest(manifest, manifest_path)
        print(f"Manifest saved to: {manifest_path}")

        report = execute_deletion(db, manifest, dry_run=dry_run)

        if report.errors or report.skipped_scholarship_ids:
            db.rollback()
            print(f"Errors: {report.errors}")
            sys.exit(1)

        committed = False
        if not dry_run:
            try:
                db.commit()
                committed = True
            except Exception as e:
                db.rollback()
                print(f"ERROR: Database commit failed: {e}")
                print("No deletion was committed. Committed deletion count: 0.")
                sys.exit(1)

        report_path = os.path.join(args.output_dir, "closed_deletion_report.json")
        try:
            save_report(report, report_path)
        except Exception as e:
            if committed:
                print(f"WARNING: Database commit succeeded, but report publication failed: {e}")
                print("Database changes are committed; artifact publication failed. Preserve execution identity for recovery.")
            else:
                print(f"ERROR: Report publication failed: {e}")
            # Still attempt to print summary
        else:
            print(f"Report saved to: {report_path}")

        print()

        print(f"Total closed: {report.total_closed}")
        print(f"Deleted scholarships: {report.deleted_scholarships}")
        print(f"Deleted professor links: {report.deleted_professor_links}")
        print(f"Deleted coverage rows: {report.deleted_coverage_rows}")
        print(f"Deleted source evidence: {report.deleted_source_evidence}")
        print(f"Preserved Gate 6 evidence (archived): {report.preserved_gate6_evidence}")
        print(f"Deleted official contacts: {report.deleted_official_contacts}")
        print(f"Tombstones created: {report.tombstones_created}")
        print(f"Preserved application records: {report.preserved_application_records}")

        if dry_run:
            db.rollback()
            print()
            print("DRY RUN COMPLETE. No records were deleted.")
            print("To execute deletion, run with --execute --confirm-production")
        elif not committed:
            sys.exit(1)


if __name__ == "__main__":
    main()