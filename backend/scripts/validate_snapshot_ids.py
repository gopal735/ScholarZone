"""Validate exact equality of scholarship IDs across snapshot, sitemap, and ledger.

This script ensures that the three canonical sources of public scholarship IDs
are perfectly in sync:
  - snapshot IDs: frontend/public/scholarships-snapshot.json
  - sitemap scholarship IDs: frontend/public/sitemap.xml (only /scholarships/{id} URLs)
  - ledger IDs: backend/verification/research_ledger.jsonl

DATA CONTRACT:
- Snapshot == Sitemap scholarship IDs (both represent the public catalogue)
- Ledger is a broader research inventory that MUST contain all snapshot IDs
  (i.e., snapshot ⊆ ledger). The ledger may contain additional research-only entries.
- Any snapshot ID missing from ledger is a BUG.
- Any snapshot ID missing from sitemap is a BUG.
- Any sitemap scholarship ID missing from snapshot is a BUG.

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


def load_sitemap_ids() -> tuple[set[int], set[str]]:
    """Extract scholarship IDs and all URLs from the sitemap XML.

    Returns:
        Tuple of (scholarship_ids_set, all_urls_set)
    """
    if not SITEMAP_PATH.exists():
        raise FileNotFoundError(f"Sitemap not found at {SITEMAP_PATH}")
    content = SITEMAP_PATH.read_text(encoding="utf-8")

    # Extract scholarship IDs
    pattern = r"/scholarships/(\d+)"
    ids_list = [int(match) for match in re.findall(pattern, content)]
    seen = set()
    duplicates = set()
    for id_val in ids_list:
        if id_val in seen:
            duplicates.add(id_val)
        seen.add(id_val)
    if duplicates:
        raise ValueError(f"Sitemap contains duplicate scholarship IDs: {sorted(duplicates)}")

    # Extract all URLs for reporting
    url_pattern = r"<loc>(https?://[^<]+)</loc>"
    all_urls = set(re.findall(url_pattern, content))

    scholarship_ids = set(ids_list)

    return scholarship_ids, all_urls


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
    sitemap_scholarship_ids, sitemap_all_urls = load_sitemap_ids()
    ledger_ids = load_ledger_ids()

    # Count non-scholarship URLs in sitemap
    sitemap_scholarship_urls = {f"https://scholarzone-fwzj.vercel.app/scholarships/{i}" for i in sitemap_scholarship_ids}
    non_scholarship_urls = sitemap_all_urls - sitemap_scholarship_urls

    print(f"Snapshot scholarship IDs:     {len(snapshot_ids)}")
    print(f"Sitemap scholarship IDs:      {len(sitemap_scholarship_ids)}")
    print(f"Sitemap total URLs:           {len(sitemap_all_urls)}")
    print(f"  - Scholarship URLs:         {len(sitemap_scholarship_urls)}")
    print(f"  - Non-scholarship URLs:     {len(non_scholarship_urls)}")
    print(f"Ledger IDs (research inventory): {len(ledger_ids)}")

    # CONTRACT 1: Snapshot == Sitemap scholarship IDs (exact match)
    if snapshot_ids != sitemap_scholarship_ids:
        missing_in_sitemap = snapshot_ids - sitemap_scholarship_ids
        extra_in_sitemap = sitemap_scholarship_ids - snapshot_ids
        print("MISMATCH: snapshot != sitemap scholarship IDs", file=sys.stderr)
        if missing_in_sitemap:
            print(f"  Missing in sitemap: {sorted(missing_in_sitemap)}", file=sys.stderr)
        if extra_in_sitemap:
            print(f"  Extra in sitemap:   {sorted(extra_in_sitemap)}", file=sys.stderr)
        return 1

    # CONTRACT 2: Ledger must be a superset of snapshot (all public IDs tracked in research)
    missing_in_ledger = snapshot_ids - ledger_ids
    extra_in_ledger = ledger_ids - snapshot_ids

    if missing_in_ledger:
        # This is a BUG - all public scholarships must be in the research ledger
        print("ERROR: Snapshot IDs missing from research ledger", file=sys.stderr)
        print(f"  Missing in ledger: {sorted(missing_in_ledger)}", file=sys.stderr)
        print("  These scholarships exist in the public catalogue but are not tracked in the research inventory.", file=sys.stderr)
        return 1

    # Report extra ledger entries (these are research-only, acceptable)
    if extra_in_ledger:
        print(f"INFO: Ledger contains {len(extra_in_ledger)} research-only entries not in public snapshot:")
        print(f"  Extra in ledger: {sorted(extra_in_ledger)}")

    print("OK: snapshot == sitemap scholarship IDs")
    print("OK: snapshot subset of ledger ({} public IDs all tracked in ledger of {} total)".format(len(snapshot_ids), len(ledger_ids)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())