#!/usr/bin/env python3
"""Generate final execution report for PR #107 automatic purge."""

import json
import os
from datetime import datetime

def main():
    print('='*60)
    print('PR #107 AUTOMATIC PRODUCTION PURGE - FINAL REPORT')
    print('='*60)
    print('Workflow run: ' + os.environ.get('GITHUB_RUN_ID', 'N/A'))
    print('Run number: ' + os.environ.get('GITHUB_RUN_NUMBER', 'N/A'))
    print('Triggered by PR #107 merge')
    print('Timestamp: ' + datetime.utcnow().isoformat() + 'Z')
    print()

    manifest_path = 'artifacts/deletion_manifest.json'
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        print('MANIFEST: ' + str(len(manifest)) + ' CLOSED scholarships identified')
        for m in manifest[:5]:
            print('  - ID ' + str(m['scholarship_id']) + ': ' + m['title'][:50] + ' (' + m['country'] + ')')
        if len(manifest) > 5:
            print('  ... and ' + str(len(manifest)-5) + ' more')
    else:
        print('MANIFEST: Not found')

    report_path = 'artifacts/deletion_report.json'
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            report = json.load(f)
        print()
        print('DELETION REPORT:')
        print('  Total closed: ' + str(report.get('total_closed', 0)))
        print('  Deleted scholarships: ' + str(report.get('deleted_scholarships', 0)))
        print('  Deleted professor links: ' + str(report.get('deleted_professor_links', 0)))
        print('  Deleted coverage rows: ' + str(report.get('deleted_coverage_rows', 0)))
        print('  Deleted source evidence: ' + str(report.get('deleted_source_evidence', 0)))
        print('  Deleted official contacts: ' + str(report.get('deleted_official_contacts', 0)))
        print('  Tombstones created: ' + str(report.get('tombstones_created', 0)))
        print('  Preserved application records: ' + str(report.get('preserved_application_records', 0)))
        print('  Skipped scholarship IDs: ' + str(report.get('skipped_scholarship_ids', [])))
        if report.get('errors'):
            print('  ERRORS: ' + str(report['errors']))
        print('  Merge commit SHA: ' + str(report.get('merge_commit_sha', 'N/A')))
        print('  Executed at: ' + str(report.get('executed_at', 'N/A')))
    else:
        print()
        print('DELETION REPORT: Not found')

    meta_path = 'artifacts/manifest_metadata.json'
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        print()
        print('Manifest hash: ' + meta.get('manifest_hash', 'N/A'))
        print('Generated at: ' + meta.get('generated_at', 'N/A'))

    print()
    print('='*60)
    print('PURGE EXECUTION COMPLETE')
    print('='*60)

if __name__ == '__main__':
    main()