#!/usr/bin/env python3
import sys, os, json, hashlib
from datetime import datetime, timezone
sys.path.insert(0, 'backend')
from app.database_readonly import get_readonly_session_factory, init_readonly_database
from app.services.closed_deletion import build_deletion_manifest, save_manifest
SCHEMA_VERSION = "1.0"
def main():
    os.makedirs('artifacts', exist_ok=True)
    init_readonly_database()
    sf = get_readonly_session_factory()
    reference_date = datetime.now(timezone.utc).date()
    with sf() as db:
        manifest = build_deletion_manifest(db, reference_date=reference_date)
        total = len(manifest)
        output_path = 'artifacts/deletion_manifest.json'
        save_manifest(manifest, output_path)
        with open(output_path, 'rb') as f:
            manifest_hash = hashlib.sha256(f.read()).hexdigest()
        print(f'total_closed={total}')
        print(f'manifest_path={output_path}')
        print(f'manifest_hash={manifest_hash}')
        metadata = {'schema_version': SCHEMA_VERSION, 'total_closed': total,
            'manifest_hash': manifest_hash, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'reference_date': reference_date.isoformat(), 'manifest_target_count': total}
        with open('artifacts/manifest_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
if __name__ == '__main__':
    main()
