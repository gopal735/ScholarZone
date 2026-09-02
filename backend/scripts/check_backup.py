"""
Check the backup database to see initial state.
"""
import sqlite3

db = sqlite3.connect('scholarzone_backup_pre_rollout_20260902_023544.db')
db.row_factory = sqlite3.Row
cur = db.cursor()

# Check verification state in backup
cur.execute('SELECT is_verified, COUNT(*) as cnt FROM scholarships GROUP BY is_verified')
rows = cur.fetchall()
print("BACKUP is_verified distribution:")
for r in rows:
    print(f"  is_verified={r['is_verified']}: {r['cnt']}")

cur.execute('SELECT verification_status, COUNT(*) as cnt FROM scholarships GROUP BY verification_status')
rows = cur.fetchall()
print("\nBACKUP verification_status distribution:")
for r in rows:
    print(f"  verification_status={r['verification_status']}: {r['cnt']}")

cur.execute('SELECT COUNT(*) as cnt FROM scholarships WHERE last_verified_at IS NOT NULL')
row = cur.fetchone()
print(f"\nBACKUP Scholarships with last_verified_at: {row['cnt']}")

cur.execute('SELECT last_verified_at, COUNT(*) as cnt FROM scholarships WHERE last_verified_at IS NOT NULL GROUP BY last_verified_at')
rows = cur.fetchall()
print("\nBACKUP last_verified_at distribution:")
for r in rows:
    print(f"  {r['last_verified_at']}: {r['cnt']}")

db.close()
