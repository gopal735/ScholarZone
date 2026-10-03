"""Fail the audit run if any record was classified SAFE_DELETE.

A deletion decision is never automatic. This turns a non-empty SAFE_DELETE
result into a loud failure so it cannot scroll past unnoticed in a green run -
which is precisely the shape of accident this whole audit exists to prevent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "closed_record_audit.json"


def main() -> int:
    if not REPORT.exists():
        print(f"::error::no audit report at {REPORT}")
        return 1

    data = json.loads(REPORT.read_text(encoding="utf-8"))
    buckets = data.get("buckets", {})
    safe = sorted(buckets.get("SAFE_DELETE", []))

    print("Closed record audit summary")
    print(f"  storage rows        : {data.get('storage_rows')}")
    print(f"  public universe     : {data.get('public_universe')}")
    print(f"  storage only        : {data.get('storage_only')}")
    print(f"  status=closed rows  : {data.get('closed_status_count')}")
    print(f"  past-deadline rows  : {data.get('past_deadline_count')}")
    for label in sorted(buckets):
        print(f"  {label:<22}: {len(buckets[label])}")

    if safe:
        print(f"\n::error::{len(safe)} record(s) classified SAFE_DELETE: {safe}")
        print(
            "This workflow does not delete anything. Each of these needs an "
            "explicit, reviewed decision - confirm the dependencies really are "
            "empty and that no product surface reads the row - before any "
            "removal is considered."
        )
        return 1

    print("\nSAFE_DELETE: 0. Nothing to delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
