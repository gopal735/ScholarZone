#!/usr/bin/env python3
"""Validate manifest stability for PR #107 automatic purge using read-only connection."""

import sys
import json
import hashlib
from datetime import date

sys.path.insert(0, 'backend')
from app.database_readonly import get_readonly_session_factory, init_readonly_database
from app.services.closed_deletion import build_deletion_manifest

def main():
    init_readonly_database()
    sf = get_readonly_session_factory()
    with open('artifacts/manifest_metadata.json', 'r') as f:
        metadata = json.load(f)
    ref_date_str = metadata.get('reference_date')
    if not ref_date_str:
        print('ERROR: missing reference_date'); sys.exit(1)
    try:
        reference_date = date.fromisoformat(ref_date_str)
    except (ValueError, TypeError):
        print('ERROR: invalid reference_date'); sys.exit(1)

    with sf() as db:
        current_manifest = build_deletion_manifest(db, reference_date=reference_date)

        with open('artifacts/deletion_manifest.json', 'r') as f:
            original_manifest = json.load(f)

        original_ids = {m['scholarship_id'] for m in original_manifest}
        if len(original_manifest) != len(original_ids):
            print('ERROR: duplicate scholarship_id in saved manifest')
            sys.exit(1)
        current_ids = {m.scholarship_id for m in current_manifest}
        if len(current_manifest) != len(current_ids):
            print('ERROR: duplicate scholarship_id in current manifest')
            sys.exit(1)

        if original_ids != current_ids:
            added = current_ids - original_ids
            removed = original_ids - current_ids
            print('ERROR: Manifest target set changed!')
            if added:
                print('  Added IDs: ' + str(sorted(added)))
            if removed:
                print('  Removed IDs: ' + str(sorted(removed)))
            sys.exit(1)

        expected_hash = metadata['manifest_hash']

        with open('artifacts/deletion_manifest.json', 'rb') as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()

        if actual_hash != expected_hash:
            print('ERROR: Manifest hash mismatch: expected ' + expected_hash + ', got ' + actual_hash)
            sys.exit(1)

        if metadata.get('manifest_target_count') != len(original_ids):
            print('ERROR: manifest target count mismatch'); sys.exit(1)

        print('OK: Manifest stable - ' + str(len(original_ids)) + ' CLOSED scholarships confirmed')
        print('Manifest hash: ' + actual_hash)

if __name__ == '__main__':
    main()
