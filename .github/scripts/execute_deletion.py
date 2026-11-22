#!/usr/bin/env python3
import sys, os, json
from datetime import datetime, timezone, date
sys.path.insert(0, 'backend')
from app.database import get_session_factory
from app.services.closed_deletion import execute_deletion, save_report, ClosedScholarshipManifest
from app.models import PurgeExecutionLedger
from sqlalchemy import select

def _verify_write_identity(db):
    required = ["EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID",
                "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME"]
    for var in required:
        if not os.environ.get(var):
            print('ERROR: missing required env ' + var); sys.exit(1)
    try:
        row = db.execute(__import__('sqlalchemy').text("SELECT current_database(), current_user")).first()
    except Exception as e:
        print('ERROR: cannot read DB identity: ' + str(e)); sys.exit(1)
    if row[0] != os.environ["EXPECTED_DATABASE_NAME"]:
        print('ERROR: database mismatch'); sys.exit(1)

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
