"""
Capture run 3 final state and generate report.
"""
import sqlite3

db = sqlite3.connect('scholarzone.db')
db.row_factory = sqlite3.Row
cur = db.cursor()

# Overall state
cur.execute('SELECT COUNT(*) as cnt FROM scholarships')
total = cur.fetchone()['cnt']

cur.execute('SELECT status, COUNT(*) as cnt FROM scholarships GROUP BY status')
status = {r['status']: r['cnt'] for r in cur.fetchall()}

cur.execute('SELECT COUNT(*) as cnt FROM scholarship_verification_history')
history = cur.fetchone()['cnt']

cur.execute('SELECT COUNT(*) as cnt FROM scholarships WHERE is_verified = 1')
verified = cur.fetchone()['cnt']

cur.execute('SELECT COUNT(*) as cnt FROM scholarships WHERE verification_status = "needs_review"')
needs_review = cur.fetchone()['cnt']

cur.execute('''
    SELECT official_source_url, COUNT(*) as cnt
    FROM scholarships
    WHERE official_source_url IS NOT NULL
    GROUP BY official_source_url
    HAVING cnt > 1
''')
dup_urls = cur.fetchall()

print("=" * 70)
print("CONTROLLED ROLLOUT - FINAL STATE")
print("=" * 70)
print(f"\nDATABASE:")
print(f"  Total scholarships: {total}")
print(f"  Status breakdown: {status}")
print(f"  Verified: {verified}")
print(f"  Needs review: {needs_review}")
print(f"  Verification history entries: {history}")
print(f"  Duplicate URLs: {len(dup_urls)}")

# Run 3 specific changes (IDs 12-23 from the selected list)
run3_ids = [12, 13, 14, 15, 16, 19, 20, 21, 22, 23]
print(f"\nRUN 3 CHANGES (IDs: {run3_ids}):")
for sid in run3_ids:
    cur.execute('''
        SELECT title, is_verified, verification_status, last_verified_at
        FROM scholarships WHERE id = ?
    ''', (sid,))
    row = cur.fetchone()
    if row:
        try:
            title = row['title'][:40] if row['title'] else 'N/A'
        except:
            title = '[special chars]'
        print(f"  ID={sid}: verified={row['is_verified']}, status={row['verification_status']}, last={row['last_verified_at']}")

db.close()
