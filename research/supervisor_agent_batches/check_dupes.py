import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "..", "backend", "scholarzone.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("== coverage rows per scholarship (duplicates) ==")
rows = cur.execute(
    "SELECT scholarship_id, COUNT(*) AS n FROM scholarship_supervisor_coverage GROUP BY scholarship_id HAVING n > 1"
).fetchall()
print("scholarships with duplicate coverage rows:", len(rows))
for r in rows:
    sid = r[0]
    print(f"\nscholarship {sid}:")
    for c in cur.execute(
        "SELECT id, status, verified_supervisor_count, evidence_state, updated_at FROM scholarship_supervisor_coverage WHERE scholarship_id=?",
        (sid,),
    ).fetchall():
        print("   ", dict(c))

print("\n== unicode integrity ==")
for r in cur.execute(
    "SELECT id, canonical_name FROM professor_profiles WHERE canonical_name LIKE '%nther%' OR canonical_name LIKE '%Ferran%' LIMIT 5"
).fetchall():
    print(dict(r))

print("\n== coverage of archived scholarships ==")
cur.execute(
    "SELECT c.status, COUNT(*) FROM scholarship_supervisor_coverage c "
    "JOIN scholarships s ON s.id = c.scholarship_id WHERE s.is_archived = 1 GROUP BY c.status"
)
print(cur.fetchall())

print("\n== coverage of active scholarships ==")
cur.execute(
    "SELECT c.status, COUNT(*) FROM scholarship_supervisor_coverage c "
    "JOIN scholarships s ON s.id = c.scholarship_id WHERE s.is_archived = 0 OR s.is_archived IS NULL GROUP BY c.status"
)
print(cur.fetchall())
con.close()
