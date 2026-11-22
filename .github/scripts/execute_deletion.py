#!/usr/bin/env python3
"""Execute production deletion for PR #107 automatic purge using validated manifest with atomic idempotency."""

import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, 'backend')
from app.database import get_session_factory
from app.services.closed_deletion import execute_deletion, save_report, ClosedScholarshipManifest
from app.models import DeletedClosedScholarship
from sqlalchemy import select

def main():
    sf = get_session_factory()
    merge_sha = os.environ.get('MERGE_COMMIT_SHA', '')
    if not merge_sha:
        print('ERROR: MERGE_COMMIT_SHA not set')
        sys.exit(1)

    # Load the validated manifest artifact
    with open('artifacts/deletion_manifest.json', 'r') as f:
        manifest_data = json.load(f)

    # Convert manifest data to ClosedScholarshipManifest objects
    manifest = [ClosedScholarshipManifest(**m) for m in manifest_data]

    with sf() as db:
        # Check idempotency within the same transaction
        existing = db.execute(
            select(DeletedClosedScholarship)
            .where(DeletedClosedScholarship.reason.like('%' + merge_sha + '%'))
        ).first()
        if existing:
            print('ALREADY_EXECUTED: Purge already executed for merge commit ' + merge_sha)
            sys.exit(2)

        # Execute deletion
        report = execute_deletion(db, manifest, dry_run=False, reference_date=datetime.now(timezone.utc))

        # Add idempotency marker in the same transaction
        ts = DeletedClosedScholarship(
            official_source_url=None,
            application_link=None,
            title='PR #107 PURGE MERGE COMMIT ' + merge_sha,
            reason='pr107_purge_merge_commit_' + merge_sha
        )
        db.add(ts)

        report_path = 'deletion_report.json'
        save_report(report, report_path)

        with open(report_path, 'r') as f:
            report_data = json.load(f)
        report_data['merge_commit_sha'] = os.environ.get('MERGE_COMMIT_SHA', '')
        report_data['executed_at'] = datetime.now(timezone.utc).isoformat()
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        print('deleted_count=' + str(report.deleted_scholarships))
        print('report_path=' + report_path)

        if report.errors:
            print('ERRORS: ' + str(report.errors))
            sys.exit(1)

        if report.deleted_scholarships == 0:
            print('WARNING: No scholarships deleted - verify target set')

if __name__ == '__main__':
    main()