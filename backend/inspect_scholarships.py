"""Inspect scholarships 489 and 490 for potential serialization issues."""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db")

conn = sqlite3.connect(DB_PATH.as_posix())
conn.row_factory = sqlite3.Row

cursor = conn.cursor()

# Check if records exist
cursor.execute("SELECT id, title, status, verification_status, deadline_precision FROM scholarships WHERE id IN (489, 490)")
rows = cursor.fetchall()
print("=== Records 489 and 490 ===")
for r in rows:
    print(f"ID={r['id']}, title={r['title']}, status={r['status']}, verification_status={r['verification_status']}, deadline_precision={r['deadline_precision']}")

if not rows:
    print("No records found for 489 and 490 in local DB")

# Check JSON fields for problematic records
json_fields = ['eligibility', 'benefits', 'coverage', 'requirements', 'documents', 'application_method']
for sid in [489, 490]:
    cursor.execute("SELECT * FROM scholarships WHERE id = ?", (sid,))
    row = cursor.fetchone()
    if row:
        print(f"\n=== Scholarship {sid} full data ===")
        for field in json_fields:
            val = row[field]
            print(f"  {field}: {repr(val)} (type: {type(val).__name__})")
            if val is not None:
                try:
                    parsed = json.loads(val) if isinstance(val, str) else val
                    print(f"    parsed: {repr(parsed)}")
                    if not isinstance(parsed, list):
                        print(f"    WARNING: Not a list!")
                    else:
                        for i, item in enumerate(parsed):
                            if not isinstance(item, str):
                                print(f"    WARNING: Item {i} is not a string: {repr(item)} (type: {type(item).__name__})")
                except Exception as e:
                    print(f"    WARNING: JSON parse error: {e}")
        
        # Check date fields
        date_fields = ['deadline_date', 'last_verified_at', 'last_verified_date', 'next_verification_due', 'image_verified_at']
        for field in date_fields:
            val = row[field]
            print(f"  {field}: {repr(val)}")

# Also check status distribution
cursor.execute("SELECT status, COUNT(*) as cnt FROM scholarships GROUP BY status")
print("\n=== Status distribution ===")
for r in cursor.fetchall():
    print(f"  {r['status']}: {r['cnt']}")

# Check for any non-standard status values
cursor.execute("SELECT DISTINCT status FROM scholarships WHERE status NOT IN ('open', 'upcoming', 'closing-soon', 'closed')")
print("\n=== Non-standard status values ===")
for r in cursor.fetchall():
    print(f"  {r['status']}")

conn.close()
