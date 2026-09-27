"""Post-phase integrity checks: no session noise, repairs recorded, provenance present."""
from __future__ import annotations

import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
conn = sqlite3.connect("scholarzone.db")
q = conn.execute
total = q("SELECT COUNT(*) FROM scholarships").fetchone()[0]

print("=== SOURCE INTEGRITY ===")
bad = q("SELECT COUNT(*) FROM scholarships WHERE official_source_url LIKE '%jsessionid%' OR official_source_url LIKE '%phpsessid%'").fetchone()[0]
print(f"  session-id URLs stored       : {bad}  (must be 0)")
uniq = q("SELECT COUNT(*) FROM (SELECT official_source_url FROM scholarships GROUP BY official_source_url HAVING COUNT(*)>1)").fetchone()[0]
print(f"  duplicate source URLs       : {uniq}")

print("\n=== REPAIR EVIDENCE ===")
rows = q("SELECT COUNT(*) FROM scholarship_verification_history").fetchall()
print(f"  verification_history rows   : {rows[0][0]}")
for t, n in q("SELECT change_type, COUNT(*) FROM scholarship_verification_history GROUP BY change_type ORDER BY 2 DESC").fetchall():
    print(f"    {t:<14} {n}")
for r in q("""SELECT scholarship_id, old_value, new_value FROM scholarship_verification_history
              WHERE change_type IN ('redirected','repaired') LIMIT 5""").fetchall():
    print(f"    id={r[0]}: {str(r[1])[:46]} -> {str(r[2])[:52]}")

print("\n=== IMAGE PROVENANCE ===")
for col in ("image_url", "image_source_url", "image_source_type", "image_kind", "image_verified_at"):
    n = q(f"SELECT COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL AND {col} IS NOT NULL").fetchone()[0]
    print(f"  verified rows with {col:<20}: {n}")
kinds = q("SELECT image_kind, COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL GROUP BY image_kind").fetchall()
print(f"  image_kind distribution     : {kinds}")
stypes = q("SELECT image_source_type, COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL GROUP BY image_source_type").fetchall()
print(f"  image_source_type           : {stypes}")

print("\n=== STATUS ===")
for s, n in q("SELECT status, COUNT(*) FROM scholarships GROUP BY status ORDER BY 2 DESC").fetchall():
    print(f"  {s:<14} {n:>4}  ({100*n/total:5.1f}%)")
conn.close()
