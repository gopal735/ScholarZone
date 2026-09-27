"""Final numeric completion report for the catalogue phase."""
from __future__ import annotations

import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
conn = sqlite3.connect("scholarzone.db")
q = conn.execute

total = q("SELECT COUNT(*) FROM scholarships").fetchone()[0]
quarantined = q("SELECT COUNT(*) FROM scholarships WHERE verification_status='quarantined'").fetchone()[0]
valid = total - quarantined

print("=" * 62)
print("CATALOGUE")
print("=" * 62)
print(f"  total records            : {total}")
print(f"  valid scholarships       : {valid}")
print(f"  quarantined (not a prog) : {quarantined}")

print("\n" + "=" * 62)
print("IMAGES")
print("=" * 62)
verified = q("SELECT COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL").fetchone()[0]
print(f"  verified images          : {verified}  ({100*verified/total:.1f}%)")
print(f"  without image            : {total-verified}  ({100*(total-verified)/total:.1f}%)")
print("  by kind:")
for k, n in q("SELECT COALESCE(image_kind,'(unset)'), COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL GROUP BY image_kind ORDER BY 2 DESC").fetchall():
    print(f"     {k:<20} {n}")
print("  by source type:")
for k, n in q("SELECT COALESCE(image_source_type,'(unset)'), COUNT(*) FROM scholarships WHERE image_verified_at IS NOT NULL GROUP BY image_source_type ORDER BY 2 DESC").fetchall():
    print(f"     {k:<20} {n}")
prov = q("""SELECT COUNT(*) FROM scholarships
            WHERE image_verified_at IS NOT NULL
              AND image_url IS NOT NULL AND image_source_url IS NOT NULL
              AND image_source_type IS NOT NULL AND image_alt_text IS NOT NULL""").fetchone()[0]
print(f"  with full provenance     : {prov}/{verified}")

print("\n" + "=" * 62)
print("SOURCE INTEGRITY")
print("=" * 62)
session_ids = q(
    "SELECT COUNT(*) FROM scholarships "
    "WHERE official_source_url LIKE '%jsessionid%' "
    "OR official_source_url LIKE '%phpsessid%'"
).fetchone()[0]
print(f"  session-id URLs          : {session_ids}")
print(f"  duplicate source URLs    : {q('SELECT COUNT(*) FROM (SELECT official_source_url FROM scholarships GROUP BY official_source_url HAVING COUNT(*)>1)').fetchone()[0]}")
print(f"  repair evidence rows     : {q('SELECT COUNT(*) FROM scholarship_verification_history').fetchone()[0]}")
for t, n in q("SELECT change_type, COUNT(*) FROM scholarship_verification_history GROUP BY change_type ORDER BY 2 DESC").fetchall():
    print(f"     {t:<14} {n}")
print(f"  image review rows        : {q('SELECT COUNT(*) FROM image_reviews').fetchone()[0]}")

print("\n" + "=" * 62)
print("STATUS")
print("=" * 62)
for s, n in q("SELECT status, COUNT(*) FROM scholarships WHERE verification_status!='quarantined' GROUP BY status ORDER BY 2 DESC").fetchall():
    print(f"  {s:<14} {n:>4}  ({100*n/valid:5.1f}%)")
conn.close()
