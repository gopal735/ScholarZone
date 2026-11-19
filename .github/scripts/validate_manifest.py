#!/usr/bin/env python3
"""Validate manifest stability for PR #107 automatic purge."""

import sys
import json
import hashlib

sys.path.insert(0, 'backend')
from app.database import get_session_factory, init_database
from app.services.closed_deletion import build_deletion_manifest, save_manifest

def main():
    init_database()
    sf = get_session_factory()
    with sf() as db:
        current_manifest = build_deletion_manifest(db)

        with open('artifacts/deletion_manifest.json', 'r') as f:
            original_manifest = json.load(f)

        original_ids = {m['scholarship_id'] for m in original_manifest}
        current_ids = {m.scholarship_id for m in current_manifest}

        if original_ids != current_ids:
            added = current_ids - original_ids
            removed = original_ids - current_ids
            print('ERROR: Manifest target set changed!')
            if added:
                print('  Added IDs: ' + str(sorted(added)))
            if removed:
                print('  Removed IDs: ' + str(sorted(removed)))
            sys.exit(1)

        with open('artifacts/manifest_metadata.json', 'r') as f:
            metadata = json.load(f)
        expected_hash = metadata['manifest_hash']

        with open('artifacts/deletion_manifest.json', 'rb') as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()

        if actual_hash != expected_hash:
            print('ERROR: Manifest hash mismatch: expected ' + expected_hash + ', got ' + actual_hash)
            sys.exit(1)

        print('OK: Manifest stable - ' + str(len(original_ids)) + ' CLOSED scholarships confirmed')
        print('Manifest hash: ' + actual_hash)

if __name__ == '__main__':
    main()