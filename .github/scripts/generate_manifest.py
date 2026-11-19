#!/usr/bin/env python3
"""Generate dynamic deletion manifest for PR #107 automatic purge."""

import sys
import json
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, 'backend')
from app.database import get_session_factory, init_database
from app.services.closed_deletion import build_deletion_manifest, save_manifest

def main():
    init_database()
    sf = get_session_factory()
    with sf() as db:
        manifest = build_deletion_manifest(db)
        total = len(manifest)

        output_path = 'deletion_manifest.json'
        save_manifest(manifest, output_path)

        with open(output_path, 'rb') as f:
            manifest_hash = hashlib.sha256(f.read()).hexdigest()

        print(f'total_closed={total}')
        print(f'manifest_path={output_path}')
        print(f'manifest_hash={manifest_hash}')

        with open('manifest_metadata.json', 'w') as f:
            json.dump({
                'total_closed': total,
                'manifest_hash': manifest_hash,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'reference_date': datetime.now(timezone.utc).date().isoformat()
            }, f, indent=2)

if __name__ == '__main__':
    main()