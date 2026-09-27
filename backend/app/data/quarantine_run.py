"""Quarantine non-scholarship records. Dry run unless --persist."""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.services.catalogue_quarantine import quarantine_non_scholarships

PERSIST = "--persist" in sys.argv
verdicts = quarantine_non_scholarships(get_session_factory(), dry_run=not PERSIST)

print(f"mode: {'PERSIST' if PERSIST else 'DRY RUN'}")
print(f"records flagged as non-scholarship: {len(verdicts)}\n")
for v in verdicts:
    print(f"  id={v.scholarship_id}")
    print(f"    title: {v.evidence.get('title')}")
    print(f"    url  : {v.evidence.get('official_source_url')}")
    for r in v.reasons:
        print(f"    - {r}")
    print()
