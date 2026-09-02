"""
Verify actual database state.
"""
import sqlite3

db = sqlite3.connect('scholarzone.db')
db.row_factory = sqlite3.Row
cur = db.cursor()

# Check actual verification state
cur.execute('SELECT is_verified, COUNT(*) as cnt FROM scholarships GROUP BY is_verified')
rows = cur.fetchall()
print("is_verified distribution:")
for r in rows:
    print(f"  is_verified={r['is_verified']}: {r['cnt']}")

cur.execute('SELECT verification_status, COUNT(*) as cnt FROM scholarships GROUP BY verification_status')
rows = cur.fetchall()
print("\nverification_status distribution:")
for r in rows:
    print(f"  verification_status={r['verification_status']}: {r['cnt']}")

cur.execute('SELECT status, COUNT(*) as cnt FROM scholarships GROUP BY status')
rows = cur.fetchall()
print("\nstatus distribution:")
for r in rows:
    print(f"  status={r['status']}: {r['cnt']}")

# Check how many have last_verified_at set
cur.execute('SELECT COUNT(*) as cnt FROM scholarships WHERE last_verified_at IS NOT NULL')
row = cur.fetchone()
print(f"\nScholarships with last_verified_at: {row['cnt']}")

# Check next_verification_due distribution
cur.execute('SELECT next_verification_due, COUNT(*) as cnt FROM scholarships GROUP BY next_verification_due ORDER BY next_verification_due')
rows = cur.fetchall()
print("\nnext_verification_due distribution:")
for r in rows[:10]:
    print(f"  {r['next_verification_due']}: {r['cnt']}")
if len(rows) > 10:
    print(f"  ... and {len(rows) - 10} more")

# Total
cur.execute('SELECT COUNT(*) as cnt FROM scholarships')
row = cur.fetchone()
print(f"\nTotal scholarships: {row['cnt']}")

db.close()
