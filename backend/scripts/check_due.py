"""Check which scholarships are due for verification."""
import sqlite3
from datetime import date

db = sqlite3.connect('scholarzone.db')
db.row_factory = sqlite3.Row
cur = db.cursor()

today = date.today().isoformat()
print(f'Today: {today}')

cur.execute('''
    SELECT id, title, status, is_verified, next_verification_due, last_verified_at, official_source_url
    FROM scholarships
    WHERE official_source_url IS NOT NULL
    AND (next_verification_due <= ? OR next_verification_due IS NULL)
    ORDER BY next_verification_due ASC
    LIMIT 10
''', (today,))

rows = cur.fetchall()
print(f'\nDue candidates (first 10):')
for r in rows:
    print(f'  ID={r["id"]}, title={r["title"][:50] if r["title"] else "N/A"}, '
          f'status={r["status"]}, verified={r["is_verified"]}, '
          f'due={r["next_verification_due"]}, last={r["last_verified_at"]}')

cur.execute('''
    SELECT COUNT(*) as cnt
    FROM scholarships
    WHERE official_source_url IS NOT NULL
    AND (next_verification_due <= ? OR next_verification_due IS NULL)
''', (today,))
row = cur.fetchone()
print(f'\nTotal due candidates: {row["cnt"]}')

db.close()
