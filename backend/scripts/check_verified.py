"""
Check if verification state was pre-existing.
"""
import sqlite3

db = sqlite3.connect('scholarzone.db')
db.row_factory = sqlite3.Row
cur = db.cursor()

# Check last_verified_at dates
cur.execute('''
    SELECT last_verified_at, COUNT(*) as cnt
    FROM scholarships
    WHERE last_verified_at IS NOT NULL
    GROUP BY last_verified_at
    ORDER BY last_verified_at DESC
''')
rows = cur.fetchall()
print("last_verified_at distribution:")
for r in rows:
    print(f"  {r['last_verified_at']}: {r['cnt']}")

# Check specifically today's verifications
cur.execute('''
    SELECT id, title, last_verified_at, next_verification_due
    FROM scholarships
    WHERE last_verified_at = '2026-09-02'
    ORDER BY id
''')
rows = cur.fetchall()
print(f"\nScholarships verified today (2026-09-02): {len(rows)}")
for r in rows:
    try:
        title = r['title'][:50] if r['title'] else 'N/A'
    except:
        title = '[special chars]'
    print(f"  ID={r['id']}: {title}, next_due={r['next_verification_due']}")

db.close()
