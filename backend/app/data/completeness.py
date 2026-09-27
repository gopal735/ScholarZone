"""Catalogue completeness metrics, for BEFORE/AFTER comparison."""
from __future__ import annotations

import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = sys.argv[1] if len(sys.argv) > 1 else "scholarzone.db"
LABEL = sys.argv[2] if len(sys.argv) > 2 else ""

conn = sqlite3.connect(DB)
q = conn.execute
total = q("SELECT COUNT(*) FROM scholarships").fetchone()[0]

images = q("SELECT COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL").fetchone()[0]
print(f"=== CATALOGUE COMPLETENESS {LABEL} ===")
print(f"total records          : {total}")
print(f"verified images        : {images}  ({100*images/total:.1f}%)")
print(f"records without image  : {total-images}  ({100*(total-images)/total:.1f}%)")
print()

FIELDS = [
    "description", "region", "duration", "program_type", "application_period",
    "eligibility_summary", "eligibility", "benefits", "coverage", "requirements",
    "documents", "english_requirement", "application_method", "selection_notes",
    "best_fit", "notes", "deadline_display", "deadline_date", "catalogue_url",
    "official_updates_url",
]
print(f"{'field':<24} {'populated':>10}   {'pct':>7}")
print("-" * 46)
for f in FIELDS:
    n = q(
        f"SELECT COUNT(*) FROM scholarships WHERE {f} IS NOT NULL AND {f} NOT IN ('[]','')"
    ).fetchone()[0]
    print(f"{f:<24} {n:>10}   {100*n/total:6.1f}%")

print()
print("status distribution:")
for status, n in q("SELECT status, COUNT(*) FROM scholarships GROUP BY status ORDER BY 2 DESC").fetchall():
    print(f"  {status:<14} {n:>4}  ({100*n/total:5.1f}%)")
conn.close()
