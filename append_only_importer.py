#!/usr/bin/env python3
"""
Append-Only Scholarship Importer for ScholarZone

This importer safely inserts NEW scholarship records without updating existing ones.
It performs comprehensive duplicate detection and validation before insertion.

Usage:
    python append_only_importer.py --dry-run
    python append_only_importer.py --execute
    python append_only_importer.py --execute --backup-check
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import select, func
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_engine
from app.core.config import get_settings
from app.models import Scholarship
from app.services.scholarship_ingestion import (
    ScholarshipIngestionRecord,
    validate_catalogue,
    _find_existing_scholarship,
    _fit_columns,
)


class ImportReport:
    """Tracks import statistics and results."""

    def __init__(self):
        self.inserted: list[dict[str, Any]] = []
        self.skipped_duplicates: list[dict[str, Any]] = []
        self.failed: list[dict[str, Any]] = []
        self.rolled_back: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.start_time = datetime.utcnow()
        self.end_time: datetime | None = None
        self.commit_succeeded: bool = False

    def record_inserted(self, record: ScholarshipIngestionRecord, db_id: int, candidate_id: str | None = None):
        self.inserted.append({
            "candidate_id": candidate_id or getattr(record, "candidate_id", "unknown"),
            "name": record.name,
            "official_source_url": record.official_source_url,
            "db_id": db_id,
        })

    def record_skipped(self, record: ScholarshipIngestionRecord, reason: str, existing_id: int | None = None, candidate_id: str | None = None):
        self.skipped_duplicates.append({
            "candidate_id": candidate_id or getattr(record, "candidate_id", "unknown"),
            "name": record.name,
            "official_source_url": record.official_source_url,
            "reason": reason,
            "existing_db_id": existing_id,
        })

    def record_failed(self, record: ScholarshipIngestionRecord, error: str, candidate_id: str | None = None):
        self.failed.append({
            "candidate_id": candidate_id or getattr(record, "candidate_id", "unknown"),
            "name": record.name,
            "official_source_url": record.official_source_url,
            "error": error,
        })

    def record_rolled_back(self, record: ScholarshipIngestionRecord, error: str, candidate_id: str | None = None):
        """Record a record that was rolled back due to batch failure."""
        self.rolled_back.append({
            "candidate_id": getattr(record, "candidate_id", "unknown"),
            "name": record.name,
            "official_source_url": record.official_source_url,
            "error": error,
        })

    def record_error(self, error: str):
        self.errors.append(error)

    def finalize(self, commit_succeeded: bool = False):
        self.end_time = datetime.utcnow()
        self.commit_succeeded = commit_succeeded

    def summary(self) -> dict[str, Any]:
        return {
            "inserted_count": len(self.inserted),
            "skipped_duplicates_count": len(self.skipped_duplicates),
            "failed_count": len(self.failed),
            "rolled_back_count": len(self.rolled_back),
            "error_count": len(self.errors),
            "commit_succeeded": self.commit_succeeded,
            "inserted": self.inserted,
            "skipped_duplicates": self.skipped_duplicates,
            "failed": self.failed,
            "rolled_back": self.rolled_back,
            "errors": self.errors,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else None,
        }


def load_candidates(json_path: Path) -> list[tuple[ScholarshipIngestionRecord, str | None]]:
    """Load import-ready candidates from JSON file. Returns list of (record, candidate_id)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    # Get valid field names from the model
    valid_fields = set(ScholarshipIngestionRecord.model_fields.keys())

    for item in data.get("import_ready_records", []):
        # Filter to only valid fields
        filtered = {k: v for k, v in item.items() if k in valid_fields}
        candidate_id = item.get("candidate_id")
        record = ScholarshipIngestionRecord(**filtered)
        records.append((record, candidate_id))

    return records


def check_database_connection() -> tuple[bool, str]:
    """Verify database connection and return status."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(select(1))
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {e}"


def get_existing_usa_count(session: Session) -> int:
    """Get count of existing USA scholarships in database."""
    return session.scalar(
        select(func.count(Scholarship.id)).where(Scholarship.country == "United States")
    ) or 0


def get_existing_urls(session: Session) -> set[str]:
    """Get all existing official_source_urls for USA scholarships."""
    results = session.scalars(
        select(Scholarship.official_source_url).where(Scholarship.country == "United States")
    ).all()
    # Normalize URLs for comparison
    normalized = set()
    for url in results:
        normalized.add(url.rstrip("/"))
        normalized.add(f"{url.rstrip('/')}/")
    return normalized


def find_duplicates(session: Session, record: ScholarshipIngestionRecord) -> tuple[Scholarship | None, str]:
    """
    Comprehensive duplicate detection.
    Returns (existing_scholarship_or_none, reason_if_duplicate)
    """
    # 1. Exact official_source_url match (normalized)
    source_url = record.official_source_url.rstrip("/")
    variants = (source_url, f"{source_url}/")
    existing = session.scalars(
        select(Scholarship).where(Scholarship.official_source_url.in_(variants))
    ).first()
    if existing:
        return existing, f"Exact official_source_url match (ID: {existing.id})"

    # 2. Application link match (legacy)
    existing = session.scalars(
        select(Scholarship).where(Scholarship.application_link.in_(variants))
    ).first()
    if existing:
        return existing, f"Application link match (ID: {existing.id})"

    # 3. Institution + programme + award title fuzzy match
    # Build search from record
    search_terms = [
        record.name.lower(),
        record.official_source.lower() if record.official_source else "",
    ]
    search_terms = [t for t in search_terms if t]

    if search_terms:
        # Search by title similarity
        title_matches = session.scalars(
            select(Scholarship).where(
                Scholarship.country == "United States",
                func.lower(Scholarship.title).like(f"%{search_terms[0][:50]}%")
            )
        ).all()

        for match in title_matches:
            # Check if same institution
            if record.official_source and match.official_source:
                if record.official_source.lower() in match.official_source.lower() or \
                   match.official_source.lower() in record.official_source.lower():
                    return match, f"Institution + title similarity match (ID: {match.id})"

    return None, ""


def import_records(
    record_pairs: list[tuple[ScholarshipIngestionRecord, str | None]],
    session: Session,
    report: ImportReport,
    dry_run: bool = False,
) -> list[tuple[ScholarshipIngestionRecord, int, str | None]]:
    """
    Import records with duplicate detection and validation.
    Returns list of (record, db_id, candidate_id) for successfully committed records.
    """
    # Validate catalogue (checks for duplicate URLs within the import set)
    try:
        validated = validate_catalogue([r for r, _ in record_pairs])
    except ValueError as e:
        report.record_error(f"Catalogue validation failed: {e}")
        return []

    # Create mapping from validated records back to candidate_ids
    validated_dict = {r.official_source_url: cid for r, cid in record_pairs}
    # Also map by name as fallback
    validated_by_name = {r.name: cid for r, cid in record_pairs}

    # Get existing URLs for fast duplicate check
    existing_urls = get_existing_urls(session)

    verified_on = date.today()
    pending_inserts: list[tuple[ScholarshipIngestionRecord, str | None]] = []

    for record in validated:
        candidate_id = validated_dict.get(record.official_source_url) or validated_by_name.get(record.title)

        # Check 1: URL already in database
        source_url = record.official_source_url.rstrip("/")
        if source_url in existing_urls or f"{source_url}/" in existing_urls:
            existing = session.scalars(
                select(Scholarship).where(Scholarship.official_source_url.in_((source_url, f"{source_url}/")))
            ).first()
            report.record_skipped(record, "Official source URL already exists in database", existing.id if existing else None, candidate_id)
            continue

        # Check 2: Comprehensive duplicate detection
        existing, reason = find_duplicates(session, record)
        if existing:
            report.record_skipped(record, reason, existing.id, candidate_id)
            continue

        # Check 3: Validate required fields for new insert
        if record.funding_type is None:
            report.record_failed(record, "funding_type is required for new records", candidate_id)
            continue

        # Prepare persistence fields
        try:
            persistence_fields = record.to_persistence_fields(verified_on)
            persistence_fields, dropped = _fit_columns(persistence_fields)

            if dropped:
                report.record_error(f"Record {record.title}: dropped over-long values: {', '.join(dropped)}")

            if dry_run:
                # In dry-run, just track what would be inserted
                pending_inserts.append((record, candidate_id))
                continue

            # Insert new record (will be committed at end of batch)
            scholarship = Scholarship(**persistence_fields)
            session.add(scholarship)
            session.flush()  # Get the ID
            pending_inserts.append((record, scholarship.id, candidate_id))

        except Exception as e:
            report.record_failed(record, f"Insert preparation failed: {e}", candidate_id)

    if dry_run:
        # In dry-run, report all as "would be inserted" with db_id=-1
        for record, candidate_id in pending_inserts:
            report.record_inserted(record, db_id=-1, candidate_id=candidate_id)
        return [(r, -1, c) for r, c in pending_inserts]

    # All-or-nothing: commit the entire batch
    if pending_inserts:
        try:
            session.commit()
        except Exception as e:
            # Rollback entire batch - no records committed
            session.rollback()
            error_msg = f"Transaction commit failed: {e}"
            report.record_error(error_msg)
            # Mark all pending as rolled back
            for record, db_id, candidate_id in pending_inserts:
                report.record_rolled_back(record, error_msg, candidate_id)
            return []
    
    # Commit succeeded - record all as inserted
    for record, db_id, candidate_id in pending_inserts:
        report.record_inserted(record, db_id, candidate_id)
    
    report.commit_succeeded = True
    return [(r, db_id, c) for r, db_id, c in pending_inserts]


def write_import_report(report: ImportReport, output_path: Path) -> None:
    """Write import report to JSON."""
    summary = report.summary()
    summary["import_summary"] = {
        "total_candidates": len(report.inserted) + len(report.skipped_duplicates) + len(report.failed) + len(report.rolled_back),
        "inserted_count": len(report.inserted),
        "skipped_duplicates_count": len(report.skipped_duplicates),
        "failed_count": len(report.failed),
        "rolled_back_count": len(report.rolled_back),
    }
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Append-only scholarship importer")
    parser.add_argument(
        "--input",
        default="us_scholarships_import_ready.json",
        help="Path to import-ready JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry-run without database writes",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute actual import (requires --execute flag)",
    )
    parser.add_argument(
        "--backup-check",
        action="store_true",
        help="Verify backup/PITR capability before production write",
    )
    parser.add_argument(
        "--report",
        default="us_scholarship_import_report.json",
        help="Output path for import report",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Must specify either --dry-run or --execute")

    if args.execute and args.dry_run:
        parser.error("Cannot use both --dry-run and --execute")

    print("=" * 60)
    print("ScholarZone Append-Only Scholarship Importer")
    print("=" * 60)
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    print(f"Input: {args.input}")
    print(f"Report: {args.report}")
    print(f"Backup check: {args.backup_check}")
    print()

    # Load candidates
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    print("Loading candidates...")
    record_pairs = load_candidates(input_path)
    print(f"Loaded {len(record_pairs)} import-ready records")
    print()

    # Database connection
    print("Checking database connection...")
    connected, msg = check_database_connection()
    print(f"  {msg}")
    if not connected:
        print("ERROR: Cannot connect to database")
        sys.exit(1)

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Pre-import state
        existing_count = get_existing_usa_count(session)
        print(f"Existing USA records in database: {existing_count}")

        if args.backup_check and not args.dry_run:
            print("\nBackup/PITR check requested...")
            print("  WARNING: Ensure verified backup/PITR exists before production write")
            print("  This check is manual - verify your backup strategy")
            response = input("  Continue? (y/N): ")
            if response.lower() != "y":
                print("Aborted by user")
                sys.exit(0)

        # Run import
        report = ImportReport()
        print("\nStarting import...")
        import_records(record_pairs, session, report, dry_run=args.dry_run)
        report.finalize()

        # Post-import state
        if not args.dry_run:
            new_count = get_existing_usa_count(session)
            print(f"USA records after import: {new_count} (delta: +{new_count - existing_count})")

        # Print summary
        print("\n" + "=" * 60)
        print("IMPORT SUMMARY")
        print("=" * 60)
        print(f"Inserted:        {len(report.inserted)}")
        print(f"Skipped (dupes): {len(report.skipped_duplicates)}")
        print(f"Failed:          {len(report.failed)}")
        print(f"Errors:          {len(report.errors)}")

        if report.inserted:
            print("\nINSERTED RECORDS:")
            for item in report.inserted:
                print(f"  - {item['name']} (DB ID: {item['db_id']})")

        if report.skipped_duplicates:
            print("\nSKIPPED DUPLICATES:")
            for item in report.skipped_duplicates:
                print(f"  - {item['name']}: {item['reason']}")

        if report.failed:
            print("\nFAILED RECORDS:")
            for item in report.failed:
                print(f"  - {item['name']}: {item['error']}")

        if report.errors:
            print("\nERRORS:")
            for err in report.errors:
                print(f"  - {err}")

        # Write report
        write_import_report(report, Path(args.report))
        print(f"\nImport report written to: {args.report}")

    finally:
        session.close()


if __name__ == "__main__":
    main()