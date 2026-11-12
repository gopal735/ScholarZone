#!/usr/bin/env python3
"""
Append-Only Scholarship Importer for ScholarZone

This importer safely inserts NEW scholarship records without updating existing ones.
It performs comprehensive duplicate detection and validation before insertion.

Production Safety Gates:
- Requires explicit expected database identifier (--expected-db-id)
- Verifies exact PostgreSQL database identity
- Validates the expected endpoint/host
- Requires explicit operator attestation with evidence reference
- Mandatory backup/PITR attestation (manual operator or provider verification)
- All-or-nothing batch transaction semantics
- Fails closed on missing or mismatched identity
- Dry-run is non-mutating and never writes

Transaction Contract:
- All-or-nothing batch transaction semantics
- Any VALIDATION failure aborts the whole batch (funding_type missing, data truncation, etc.)
- DUPLICATES are skipped but do NOT abort the batch
- Any insert/flush failure aborts the whole batch
- Any commit failure rolls back the whole batch
- No rolled-back row may appear in inserted
- Correctly populate rolled_back and failed
- inserted must only contain committed rows

Usage:
    python append_only_importer.py --dry-run
    python append_only_importer.py --execute --expected-db-id scholarzone-prod --expected-endpoint host.example.com:5432 --backup-attestation manual --operator-attestation "I confirm backup verified" --evidence-ref "backup-2026-11-12"
    python append_only_importer.py --execute --expected-db-id scholarzone-prod --expected-endpoint host.example.com:5432 --backup-attestation provider --provider-backup-id bkup_abc123 --operator-attestation "I confirm provider backup verified" --evidence-ref "provider-backup-2026-11-12"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import select, func, text
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
        self.start_time = datetime.now(timezone.utc)
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
            "candidate_id": candidate_id or getattr(record, "candidate_id", "unknown"),
            "name": record.name,
            "official_source_url": record.official_source_url,
            "error": error,
        })

    def record_error(self, error: str):
        self.errors.append(error)

    def finalize(self):
        self.end_time = datetime.now(timezone.utc)

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


def get_database_identity(engine) -> dict[str, str]:
    """Get database identity for verification. Does not expose credentials."""
    try:
        with engine.connect() as conn:
            # Get database name, host, port - use dialect-specific queries
            dialect = engine.dialect.name
            if dialect == "postgresql":
                result = conn.execute(text("SELECT current_database(), inet_server_addr(), inet_server_port()")).first()
                db_name = result[0] if result else "unknown"
                host = result[1] if result and result[1] else "unknown"
                port = result[2] if result and result[2] else "unknown"
            elif dialect == "sqlite":
                # SQLite doesn't have database name/host/port in the same way
                db_name = "sqlite"
                host = "localhost"
                port = "0"
            else:
                db_name = "unknown"
                host = "unknown"
                port = "unknown"
            
            # Sanitized URL
            url = str(engine.url)
            if "@" in url:
                parts = url.split("@")
                sanitized = parts[0].split("://")[0] + "://***@" + parts[1]
            else:
                sanitized = url
                
            return {
                "database": db_name,
                "host": str(host),
                "port": str(port),
                "endpoint": f"{host}:{port}",
                "sanitized_url": sanitized,
            }
    except Exception as e:
        return {"error": str(e)}


def verify_database_identity(engine, expected_db_id: str, expected_endpoint: str) -> tuple[bool, str]:
    """Verify database identity matches expected values."""
    identity = get_database_identity(engine)
    
    if "error" in identity:
        return False, f"Failed to get database identity: {identity['error']}"
    
    # Check database identifier
    if identity["database"] != expected_db_id:
        return False, f"Database ID mismatch: expected '{expected_db_id}', got '{identity['database']}'"
    
    # Check endpoint (host:port)
    if identity["endpoint"] != expected_endpoint:
        return False, f"Endpoint mismatch: expected '{expected_endpoint}', got '{identity['endpoint']}'"
    
    return True, f"Database identity verified: {identity['database']}@{identity['endpoint']}"


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
    ALL-OR-NOTHING batch transaction semantics:
    - Any VALIDATION failure aborts the whole batch (funding_type missing, data truncation, etc.)
    - DUPLICATES are skipped but do NOT abort the batch
    - Any insert/flush failure aborts the whole batch
    - Any commit failure rolls back the whole batch
    Returns list of (record, db_id, candidate_id) for successfully committed records.
    """
    # Validate catalogue (checks for duplicate URLs within the import set)
    try:
        validated = validate_catalogue([r for r, _ in record_pairs])
    except ValueError as e:
        report.record_error(f"Catalogue validation failed: {e}")
        report.commit_succeeded = False
        return []

    # Create mapping from validated records back to candidate_ids
    # Use official_source_url as key since it's unique and hashable
    validated_dict = {r.official_source_url: cid for r, cid in record_pairs}
    # Also map by name as fallback
    validated_by_name = {r.name: cid for r, cid in record_pairs}

    # Get existing URLs for fast duplicate check
    existing_urls = get_existing_urls(session)

    # PHASE 1: Validate ALL records first - any VALIDATION failure aborts entire batch
    # Track which records should be inserted (not duplicates)
    records_to_insert: list[ScholarshipIngestionRecord] = []
    candidate_ids: dict[str, str] = {}  # key: official_source_url

    for record in validated:
        candidate_id = validated_dict.get(record.official_source_url) or validated_by_name.get(record.name)

        # Check 1: URL already in database - this is a DUPLICATE, skip but don't abort batch
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

        # Check 3: Validate required fields for new insert - VALIDATION FAILURE aborts batch
        if record.funding_type is None:
            report.record_failed(record, "funding_type is required for new records", candidate_id)
            report.commit_succeeded = False
            return []

        # Prepare persistence fields
        try:
            persistence_fields = record.to_persistence_fields(date.today())
            persistence_fields, dropped = _fit_columns(persistence_fields)

            if dropped:
                report.record_error(f"Record {record.name}: dropped over-long values: {', '.join(dropped)}")
                report.commit_succeeded = False
                return []

        except Exception as e:
            report.record_failed(record, f"Insert preparation failed: {e}", candidate_id)
            report.commit_succeeded = False
            return []

        # Record is valid and not a duplicate - add to insert list
        records_to_insert.append(record)
        candidate_ids[record.official_source_url] = candidate_id

    # PHASE 2: If dry-run, report what would be inserted
    if dry_run:
        for record in records_to_insert:
            report.record_inserted(record, db_id=-1, candidate_id=candidate_ids[record.official_source_url])
        report.commit_succeeded = False
        return [(r, -1, candidate_ids[r.official_source_url]) for r in records_to_insert]

    # PHASE 3: Execute inserts - all-or-nothing
    pending_inserts: list[tuple[ScholarshipIngestionRecord, int, str | None]] = []
    
    try:
        for record in records_to_insert:
            candidate_id = candidate_ids[record.official_source_url]
            
            # Check for duplicates again at insert time (race condition protection)
            source_url = record.official_source_url.rstrip("/")
            if source_url in existing_urls or f"{source_url}/" in existing_urls:
                existing = session.scalars(
                    select(Scholarship).where(Scholarship.official_source_url.in_((source_url, f"{source_url}/")))
                ).first()
                report.record_skipped(record, "Official source URL already exists in database", existing.id if existing else None, candidate_ids[record.official_source_url])
                continue
                
            existing, reason = find_duplicates(session, record)
            if existing:
                report.record_skipped(record, reason, existing.id, candidate_ids[record.official_source_url])
                continue
            
            # Insert new record
            persistence_fields = record.to_persistence_fields(date.today())
            persistence_fields, dropped = _fit_columns(persistence_fields)
            
            scholarship = Scholarship(**persistence_fields)
            session.add(scholarship)
            session.flush()  # Get the ID
            pending_inserts.append((record, scholarship.id, candidate_ids[record.official_source_url]))
        
        # Commit the entire batch
        session.commit()
        
    except Exception as e:
        # Rollback entire batch - no records committed
        session.rollback()
        error_msg = f"Transaction failed: {e}"
        report.record_error(error_msg)
        # Mark all pending as rolled back
        for record, db_id, candidate_id in pending_inserts:
            report.record_rolled_back(record, error_msg, candidate_ids.get(record.official_source_url))
        report.commit_succeeded = False
        return []
    
    # Commit succeeded - record all as inserted
    for record, db_id, candidate_id in pending_inserts:
        report.record_inserted(record, db_id, candidate_ids[record.official_source_url])
    
    report.commit_succeeded = True
    return [(r, db_id, candidate_ids[r.official_source_url]) for r, db_id, _ in pending_inserts]


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
    parser = argparse.ArgumentParser(description="Append-only scholarship importer with production safety gates")
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
        help="Execute actual import (requires --execute flag and safety gates)",
    )
    parser.add_argument(
        "--expected-db-id",
        required=False,
        help="Expected database identifier (required for --execute)",
    )
    parser.add_argument(
        "--expected-endpoint",
        required=False,
        help="Expected database endpoint host:port (required for --execute)",
    )
    parser.add_argument(
        "--backup-attestation",
        choices=["manual", "provider"],
        required=False,
        help="Backup attestation type: manual (operator) or provider (cloud provider)",
    )
    parser.add_argument(
        "--provider-backup-id",
        required=False,
        help="Provider backup ID (required for provider attestation)",
    )
    parser.add_argument(
        "--operator-attestation",
        required=False,
        help="Operator attestation text (required for --execute, must be descriptive)",
    )
    parser.add_argument(
        "--evidence-ref",
        required=False,
        help="Evidence reference for backup/PITR verification (required for --execute)",
    )
    parser.add_argument(
        "--environment",
        required=False,
        help="Target environment (required for --execute, must be 'production')",
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

    # Safety gates for --execute
    if args.execute:
        # Require expected DB identifier
        if not args.expected_db_id:
            parser.error("--execute requires --expected-db-id (or SCHOLARZONE_EXPECTED_DB_ID)")
        # Require expected endpoint
        if not args.expected_endpoint:
            parser.error("--execute requires --expected-endpoint (or SCHOLARZONE_EXPECTED_ENDPOINT)")
        # Require explicit production environment
        if not args.environment or args.environment.lower() != "production":
            parser.error("--execute requires --environment production")
        # Require backup attestation
        if not args.backup_attestation:
            parser.error("--execute requires --backup-attestation (manual|provider) or SCHOLARZONE_BACKUP_ATTESTATION")
        # Require provider backup ID for provider attestation
        if args.backup_attestation == "provider" and not args.provider_backup_id:
            parser.error("--backup-attestation provider requires --provider-backup-id (or SCHOLARZONE_PROVIDER_BACKUP_ID)")
        # Require operator attestation
        if not args.operator_attestation:
            parser.error("--execute requires --operator-attestation (or SCHOLARZONE_OPERATOR_ATTESTATION)")
        # Require evidence reference
        if not args.evidence_ref:
            parser.error("--execute requires --evidence-ref (or SCHOLARZONE_EVIDENCE_REF)")
        # Validate operator attestation is not just "yes" or similar
        if args.operator_attestation.strip().lower() in ("y", "yes", "true", "1", "confirm"):
            parser.error("Operator attestation must be a descriptive statement, not just 'yes'")

    print("=" * 70)
    print("ScholarZone Append-Only Scholarship Importer")
    print("=" * 70)
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    print(f"Input: {args.input}")
    print(f"Report: {args.report}")
    if args.execute:
        print(f"Expected DB ID: {args.expected_db_id}")
        print(f"Expected Endpoint: {args.expected_endpoint}")
        print(f"Environment: {args.environment}")
        print(f"Backup Attestation: {args.backup_attestation}")
        if args.backup_attestation == "provider":
            print(f"Provider Backup ID: {args.provider_backup_id}")
        print(f"Operator Attestation: {args.operator_attestation}")
        print(f"Evidence Reference: {args.evidence_ref}")
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
    engine = get_engine()
    connected, msg = check_database_connection()
    print(f"  {msg}")
    if not connected:
        print("ERROR: Cannot connect to database")
        sys.exit(1)

    # Verify database identity for --execute
    if args.execute:
        print("\nVerifying database identity...")
        identity_ok, identity_msg = verify_database_identity(engine, args.expected_db_id, args.expected_endpoint)
        print(f"  {identity_msg}")
        if not identity_ok:
            print("ERROR: Database identity verification failed. Aborting.")
            sys.exit(1)

        # Backup attestation details
        print("\nBackup Attestation:")
        if args.backup_attestation == "manual":
            print("  Type: Manual operator attestation")
            print("  NOTE: This is a MANUAL operator attestation, NOT an automated provider verification.")
            print("  Operator must have independently verified backup/PITR capability.")
        else:
            print("  Type: Provider backup verification")
            print(f"  Provider Backup ID: {args.provider_backup_id}")
            print("  NOTE: This attestation relies on cloud provider's automated backup verification.")
        
        print(f"\nOperator Attestation: {args.operator_attestation}")
        print(f"Evidence Reference: {args.evidence_ref}")
        
        # Final confirmation
        print("\n" + "=" * 70)
        print("FINAL CONFIRMATION REQUIRED")
        print("=" * 70)
        print("You are about to execute a PRODUCTION DATABASE WRITE.")
        print(f"Target Database: {args.expected_db_id}@{args.expected_endpoint}")
        print(f"Backup Attestation: {args.backup_attestation}" + (f" (Provider Backup ID: {args.provider_backup_id})" if args.backup_attestation == "provider" else " (Manual operator attestation)"))
        print("This operation uses ALL-OR-NOTHING transaction semantics.")
        print("If any record fails, the ENTIRE BATCH will be rolled back.")
        print()
        confirm = input("Type 'I CONFIRM PRODUCTION WRITE' to proceed: ")
        if confirm != "I CONFIRM PRODUCTION WRITE":
            print("Aborted: confirmation text did not match exactly.")
            sys.exit(0)

    print("\nLoading candidates...")
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    print("Loading candidates...")
    record_pairs = load_candidates(input_path)
    print(f"Loaded {len(record_pairs)} import-ready records")
    print()

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Pre-import state
        existing_count = get_existing_usa_count(session)
        print(f"Existing USA records in database: {existing_count}")

        # Run import
        report = ImportReport()
        print("\nStarting import...")
        committed = import_records(record_pairs, session, report, dry_run=args.dry_run)
        report.finalize()

        # Post-import state
        if not args.dry_run:
            new_count = get_existing_usa_count(session)
            print(f"USA records after import: {new_count} (delta: +{new_count - existing_count})")

        # Print summary
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY")
        print("=" * 70)
        print(f"Inserted (committed):     {len(report.inserted)}")
        print(f"Skipped (duplicates):     {len(report.skipped_duplicates)}")
        print(f"Failed (validation):      {len(report.failed)}")
        print(f"Rolled back (batch fail): {len(report.rolled_back)}")
        print(f"Errors:                   {len(report.errors)}")
        print(f"Commit succeeded:         {report.commit_succeeded}")

        if report.inserted:
            print("\nCOMMITTED RECORDS:")
            for item in report.inserted:
                print(f"  - {item['name']} (DB ID: {item['db_id']})")

        if report.skipped_duplicates:
            print("\nSKIPPED DUPLICATES:")
            for item in report.skipped_duplicates:
                print(f"  - {item['name']}: {item['reason']}")

        if report.failed:
            print("\nFAILED (VALIDATION):")
            for item in report.failed:
                print(f"  - {item['name']}: {item['error']}")

        if report.rolled_back:
            print("\nROLLED BACK (BATCH FAILURE):")
            for item in report.rolled_back:
                print(f"  - {item['name']}: {item['error']}")

        if report.errors:
            print("\nERRORS:")
            for err in report.errors:
                print(f"  - {err}")

        # Write report
        write_import_report(report, Path(args.report))
        print(f"\nImport report written to: {args.report}")

        # Exit with error code if commit failed or there were errors
        if not report.commit_succeeded or report.errors:
            sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()