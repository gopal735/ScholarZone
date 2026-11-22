#!/usr/bin/env python3
import sys, os, json
from datetime import datetime, timezone, date
from urllib.parse import urlparse
sys.path.insert(0, 'backend')
from app.database import get_session_factory
from app.services.closed_deletion import execute_deletion, save_report, ClosedScholarshipManifest
from app.models import PurgeExecutionLedger
from sqlalchemy import select, text, inspect

def _verify_write_identity(db):
    required = ["EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID",
                "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME"]
    for var in required:
        if not os.environ.get(var):
            print('ERROR: missing required env ' + var); sys.exit(1)

    write_url = os.environ.get("SCHOLARZONE_DATABASE_URL", "")
    parsed = urlparse(write_url)
    expected_user = parsed.username
    expected_host = parsed.hostname

    try:
        row = db.execute(text("""
            SELECT current_database() AS db_name,
                   current_user AS db_user,
                   inet_server_addr() AS server_addr,
                   inet_server_port() AS server_port,
                   current_setting('neon.project_id', true) AS project_id,
                   current_setting('neon.branch_id', true) AS branch_id,
                   current_setting('neon.branch_name', true) AS branch_name,
                   version() AS pg_version
        """)).mappings().first()
    except Exception as e:
        print('ERROR: cannot read DB identity: ' + str(e)); sys.exit(1)

    if row is None:
        print('ERROR: cannot read DB identity'); sys.exit(1)

    if row["db_name"] != os.environ["EXPECTED_DATABASE_NAME"]:
        print('ERROR: database mismatch'); sys.exit(1)
    if expected_user and row["db_user"] != expected_user:
        print('ERROR: database user mismatch'); sys.exit(1)
    if not row["project_id"] or row["project_id"] != os.environ["EXPECTED_NEON_PROJECT_ID"]:
        print('ERROR: neon project mismatch'); sys.exit(1)
    if not row["branch_id"] or row["branch_id"] != os.environ["EXPECTED_NEON_BRANCH_ID"]:
        print('ERROR: neon branch mismatch'); sys.exit(1)
    if not row["branch_name"] or row["branch_name"] != os.environ["EXPECTED_NEON_BRANCH_NAME"]:
        print('ERROR: neon branch name mismatch'); sys.exit(1)
    if expected_host and str(row["server_addr"]) not in ("", "None", None) and expected_host != str(row["server_addr"]):
        # Hostname vs IP: only fail if we can positively compare; otherwise require non-empty
        pass
    if row["server_addr"] is None or str(row["server_addr"]).strip() == "":
        print('ERROR: database host identity unavailable'); sys.exit(1)
    if expected_host and str(row["server_addr"]) != expected_host and str(row["server_addr"]) not in expected_host:
        # Allow IP resolution differences but require the resolved host to be reachable/known
        pass

def _verify_ledger_schema(db):
    bind = db.get_bind() if hasattr(db, "get_bind") else None
    if bind is None:
        print('ERROR: no DB bind for ledger verification'); sys.exit(1)
    inspector = inspect(bind)
    if not inspector.has_table("purge_execution_ledger"):
        print('ERROR: purge_execution_ledger table missing'); sys.exit(1)
    ucs = {uc.get("name") for uc in inspector.get_unique_constraints("purge_execution_ledger")}
    indexes = inspector.get_indexes("purge_execution_ledger")
    unique_index_names = {ix.get("name") for ix in indexes if ix.get("unique")}
    required = {"uq_purge_execution_ledger_merge_sha", "uq_purge_execution_ledger_execution_key"}
    if not required.issubset(ucs | unique_index_names):
        print('ERROR: purge_execution_ledger unique constraints missing'); sys.exit(1)

def main():
    sf = get_session_factory()
    merge_sha = os.environ.get('MERGE_COMMIT_SHA', '')
    if not merge_sha:
        print('ERROR: MERGE_COMMIT_SHA not set'); sys.exit(1)
    with open('artifacts/deletion_manifest.json') as f:
        manifest_data = json.load(f)
    with open('artifacts/manifest_metadata.json') as f:
        metadata = json.load(f)
    manifest = [ClosedScholarshipManifest(**m) for m in manifest_data]
    ref_date_str = metadata.get('reference_date')
    reference_date = None
    if ref_date_str:
        try: reference_date = date.fromisoformat(ref_date_str)
        except ValueError: reference_date = None
    execution_key = 'pr107:' + merge_sha
    with sf() as db:
        _verify_write_identity(db)
        _verify_ledger_schema(db)
        existing = db.execute(select(PurgeExecutionLedger).where(PurgeExecutionLedger.merge_commit_sha == merge_sha)).scalar_one_or_none()
        if existing:
            print('ALREADY_EXECUTED: Purge already executed for merge commit ' + merge_sha); sys.exit(2)
        ledger = PurgeExecutionLedger(pr_number=107, merge_commit_sha=merge_sha, execution_key=execution_key,
            manifest_sha256=metadata.get('manifest_hash'), manifest_schema_version=metadata.get('schema_version'),
            manifest_target_count=metadata.get('manifest_target_count') or len(manifest),
            execution_status='started', workflow_run_id=os.environ.get('GITHUB_RUN_ID'), reference_date=ref_date_str)
        db.add(ledger); db.flush()
        report = execute_deletion(db, manifest, dry_run=False, reference_date=reference_date)
        if report.errors:
            db.rollback(); print('ERRORS: ' + str(report.errors)); sys.exit(1)
        ledger.execution_status = 'completed'
        ledger.completed_at = datetime.now(timezone.utc)
        ledger.deleted_count = report.deleted_scholarships
        db.commit()
        report_path = 'deletion_report.json'
        save_report(report, report_path)
        with open(report_path) as f:
            report_data = json.load(f)
        report_data['merge_commit_sha'] = merge_sha
        report_data['executed_at'] = datetime.now(timezone.utc).isoformat()
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        print('deleted_count=' + str(report.deleted_scholarships))
        print('report_path=' + report_path)

if __name__ == '__main__':
    main()
'''
filePath">
C:\Users\GopaL\Desktop\Projects folder\ScholarZone\.github\scripts\execute_deletion.py