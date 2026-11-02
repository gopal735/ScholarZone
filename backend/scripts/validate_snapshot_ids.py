"""Validate exact equality of scholarship IDs across snapshot, sitemap, and ledger.

This script ensures that the three canonical sources of public scholarship IDs
are perfectly in sync:
  - snapshot IDs: frontend/public/scholarships-snapshot.json
  - sitemap IDs: frontend/public/sitemap.xml
  - ledger IDs: backend/verification/research_ledger.jsonl

Any mismatch fails the CI build.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "frontend" / "public" / "scholarships-snapshot.json"
SITEMAP_PATH = REPO_ROOT / "frontend" / "public" / "sitemap.xml"
LEDGER_PATH = REPO_ROOT / "backend" / "verification" / "research_ledger.jsonl"


def load_snapshot_ids() -> set[int]:
    """Extract scholarship IDs from the snapshot JSON."""
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found at {SNAPSHOT_PATH}")
    with SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    scholarships = data.get("scholarships", [])
    # Check for duplicate IDs before converting to set
    ids_list = [item["id"] for item in scholarships]
    seen = set()
    duplicates = set()
    for id_val in ids_list:
        if id_val in seen:
            duplicates.add(id_val)
        seen.add(id_val)
    if duplicates:
        raise ValueError(f"Snapshot contains duplicate IDs: {sorted(duplicates)}")
    return set(ids_list)


def load_sitemap_ids() -> set[int]:
    """Extract scholarship IDs from the sitemap XML."""
    if not SITEMAP_PATH.exists():
        raise FileNotFoundError(f"Sitemap not found at {SITEMAP_PATH}")
    content = SITEMAP_PATH.read_text(encoding="utf-8")
    pattern = r"/scholarships/(\d+)"
    ids_list = [int(match) for match in re.findall(pattern, content)]
    # Check for duplicate IDs before converting to set
    seen = set()
    duplicates = set()
    for id_val in ids_list:
        if id_val in seen:
            duplicates.add(id_val)
        seen.add(id_val)
    if duplicates:
        raise ValueError(f"Sitemap contains duplicate IDs: {sorted(duplicates)}")
    return set(ids_list)


def load_ledger_ids() -> set[int]:
    """Extract scholarship IDs from the research ledger JSONL."""
    if not LEDGER_PATH.exists():
        raise FileNotFoundError(f"Research ledger not found at {LEDGER_PATH}")
    ids = set()
    with LEDGER_PATH.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                # Accept both 'scholarship_id' and 'id' for compatibility
                scholarship_id = record.get("scholarship_id") or record.get("id")
                if scholarship_id is None:
                    raise ValueError(f"Line {line_num}: missing 'scholarship_id' or 'id' field")
                if not isinstance(scholarship_id, int):
                    raise ValueError(f"Line {line_num}: 'scholarship_id' must be an integer, got {type(scholarship_id).__name__}")
                if scholarship_id in ids:
                    raise ValueError(f"Line {line_num}: duplicate scholarship_id {scholarship_id}")
                ids.add(scholarship_id)
            except json.JSONDecodeError as e:
                raise ValueError(f"Line {line_num}: invalid JSON - {e}")
    return ids


def main() -> int:
    snapshot_ids = load_snapshot_ids()
    sitemap_ids = load_sitemap_ids()
    ledger_ids = load_ledger_ids()

    print(f"Snapshot IDs: {len(snapshot_ids)}")
    print(f"Sitemap IDs:  {len(sitemap_ids)}")
    print(f"Ledger IDs:   {len(ledger_ids)}")

    if snapshot_ids != sitemap_ids:
        missing_in_sitemap = snapshot_ids - sitemap_ids
        extra_in_sitemap = sitemap_ids - snapshot_ids
        print("MISMATCH: snapshot != sitemap", file=sys.stderr)
        if missing_in_sitemap:
            print(f"  Missing in sitemap: {sorted(missing_in_sitemap)}", file=sys.stderr)
        if extra_in_sitemap:
            print(f"  Extra in sitemap:   {sorted(extra_in_sitemap)}", file=sys.stderr)
        return 1

    if snapshot_ids != ledger_ids:
        missing_in_ledger = snapshot_ids - ledger_ids
        extra_in_ledger = ledger_ids - snapshot_ids
        print("MISMATCH: snapshot != ledger", file=sys.stderr)
        if missing_in_ledger:
            print(f"  Missing in ledger: {sorted(missing_in_ledger)}", file=sys.stderr)
        if extra_in_ledger:
            print(f"  Extra in ledger:   {sorted(extra_in_ledger)}", file=sys.stderr)
        return 1

    if sitemap_ids != ledger_ids:
        missing_in_ledger = sitemap_ids - ledger_ids
        extra_in_ledger = ledger_ids - sitemap_ids
        print("MISMATCH: sitemap != ledger", file=sys.stderr)
        if missing_in_ledger:
            print(f"  Missing in ledger: {sorted(missing_in_ledger)}", file=sys.stderr)
        if extra_in_ledger:
            print(f"  Extra in ledger:   {sorted(extra_in_ledger)}", file=sys.stderr)
        return 1

    print("OK: snapshot == sitemap == ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())