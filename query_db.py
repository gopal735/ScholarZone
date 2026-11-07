import sqlite3

conn = sqlite3.connect(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db')
cursor = conn.cursor()

# Schema for scholarships
cursor.execute("PRAGMA table_info(scholarships)")
print("Scholarships table schema:")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

# Count records with correct columns
cursor.execute("SELECT COUNT(*) FROM scholarships")
print(f"\nTotal scholarships: {cursor.fetchone()[0]}")

# Check status values
cursor.execute("SELECT DISTINCT status FROM scholarships")
print(f"\nStatus values: {[r[0] for r in cursor.fetchall()]}")

cursor.execute("SELECT DISTINCT verification_status FROM scholarships")
print(f"Verification status values: {[r[0] for r in cursor.fetchall()]}")

# Check for archived/quarantined columns or similar
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE status != 'closed' AND verification_status = 'active'")
print(f"Public (active, not closed): {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM scholarships WHERE status = 'closed'")
print(f"Closed: {cursor.fetchone()[0]}")

# Check IDs range
cursor.execute("SELECT MIN(id), MAX(id) FROM scholarships")
min_id, max_id = cursor.fetchone()
print(f"ID range: {min_id} - {max_id}")

# Check for IDs 1293-1352
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE id BETWEEN 1293 AND 1352")
print(f"IDs 1293-1352 count: {cursor.fetchone()[0]}")

cursor.execute("SELECT id, title, status, verification_status FROM scholarships WHERE id BETWEEN 1293 AND 1352")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1][:60]}... status={row[2]}, verified={row[3]}")