"""Capture pre-rollout database state."""
import sqlite3

db = sqlite3.connect('scholarzone.db')
db.row_factory = sqlite3.Row
cur = db.cursor()

cur.execute('SELECT COUNT(*) as cnt FROM scholarships')
row = cur.fetchone()
print(f'Total scholarships: {row["cnt"]}')

cur.execute('SELECT status, COUNT(*) as cnt FROM scholarships GROUP BY status')
rows = cur.fetchall()
for r in rows:
    print(f'  {r["status"]}: {r["cnt"]}')

cur.execute('SELECT COUNT(DISTINCT official_source_url) as cnt FROM scholarships WHERE official_source_url IS NOT NULL')
row = cur.fetchone()
print(f'Distinct URLs: {row["cnt"]}')

cur.execute('SELECT COUNT(*) as cnt FROM scholarship_verification_history')
row = cur.fetchone()
print(f'Verification history entries: {row["cnt"]}')

cur.execute('SELECT id, title, status, is_verified, deadline_display, application_link FROM scholarships WHERE id = 73')
row = cur.fetchone()
if row:
    print(f'ID 73: status={row["status"]}, verified={row["is_verified"]}, deadline={row["deadline_display"]}, link={row["application_link"]}')

db.close()
