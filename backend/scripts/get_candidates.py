import sqlite3
import json

conn = sqlite3.connect(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
    SELECT id, title, official_source_url, deadline_display, deadline_date,
           deadline_precision, status, verification_status, last_verified_at,
           last_verified_date, degree, funding, is_verified
    FROM scholarships
    WHERE id IN (40, 280, 285, 289, 294, 299)
    ORDER BY id
""")
for r in cur.fetchall():
    d = dict(r)
    print(json.dumps(d, indent=2, default=str))
    print("---")
