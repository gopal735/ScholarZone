#!/usr/bin/env python3
"""Gate 6 CLI Wrapper: Application Cycle Validation - Dynamic Manifest Version."""

import sys
import os
import json

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.purge_preflight.gate6_cycle_validation import run_gate6
from app.services.purge_preflight.config import load_config
from app.services.purge_preflight.database import create_accessor
from app.services.purge_preflight.metadata import save_result_with_metadata

def main() -> int:
    """CLI entry point for Gate 6 - Dynamic Manifest Version."""
    print("=== GATE 6: APPLICATION CYCLE VALIDATION (Dynamic Manifest) ===")

    # Load target IDs from dynamic manifest artifact
    manifest_path = os.environ.get('MANIFEST_PATH', 'artifacts/deletion_manifest.json')
    if not os.path.exists(manifest_path):
        print(f"ERROR: Manifest file not found at {manifest_path}", file=sys.stderr)
        return 1

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    target_ids = [m['scholarship_id'] for m in manifest]

    print(f"Target IDs from dynamic manifest: {target_ids}")
    print(f"Count: {len(target_ids)}")
    print()

    try:
        config = load_config(gates_to_run={"gate6"})
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    result = run_gate6(accessor, target_ids)

    # Save results with metadata
    save_result_with_metadata(result.to_dict(), "gate6", "gate6_result.json")

    print("\n=== GATE 6 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print(f"\nGATE 6 PASSED: All {result.expired_cycles} records have verified expired cycles with full evidence")
        return 0
    else:
        print(f"\nGATE 6 {result.status}: {result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())