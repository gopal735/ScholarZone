#!/usr/bin/env python3
"""Execute production deletion for PR #107 automatic purge."""

import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, 'backend')
from app.database import get_session_factory, init_database
from app.services.closed_deletion import build_deletion_manifest, execute_deletion, save_report

def main():
    init_database()
    sf = get_session_factory()

    with sf() as db:
        manifest = build_deletion_manifest(db, reference_date=datetime.now(timezone.utc))
        report = execute_deletion(db, manifest, dry_run=False)

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