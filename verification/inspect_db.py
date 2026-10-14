"""Read-only inspection of the local catalogue for the final verification audit."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "backend" / "scholarzone.db"

con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("== tables ==")
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(" ", row["name"])

print("\n== scholarships columns ==")
for row in cur.execute("PRAGMA table_info(scholarships)"):
    print(f"  {row['name']:34} {row['type']}")

print("\n== counts ==")
q = "SELECT COUNT(*) FROM scholarships"
print("  total rows:", cur.execute(q).fetchone()[0])

print("\n== public visibility (is_archived=0) ==")
print("  public:", cur.execute(
    "SELECT COUNT(*) FROM scholarships WHERE is_archived=0").fetchone()[0])

print("\n== status distribution (public) ==")
for row in cur.execute(
        "SELECT status, COUNT(*) c FROM scholarships WHERE is_archived=0 GROUP BY status ORDER BY c DESC"):
    print(f"  {row['status']:20} {row['c']}")

print("\n== verification_status distribution (public) ==")
for row in cur.execute(
        "SELECT verification_status, COUNT(*) c FROM scholarships WHERE is_archived=0 "
        "GROUP BY verification_status ORDER BY c DESC"):
    print(f"  {str(row['verification_status']):24} {row['c']}")

print("\n== is_verified distribution (public) ==")
for row in cur.execute(
        "SELECT is_verified, COUNT(*) c FROM scholarships WHERE is_archived=0 GROUP BY is_verified"):
    print(f"  {row['is_verified']} {row['c']}")

print("\n== non-public rows ==")
for row in cur.execute(
        "SELECT id, title, is_archived, archived_reason, verification_status FROM scholarships "
        "WHERE is_archived=1 ORDER BY id"):
    print(" ", dict(row))

con.close()