import sqlite3
import json

conn = sqlite3.connect(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db')
cursor = conn.cursor()

# Get details of removed IDs
removed_ids = [2, 54, 59, 62, 103, 382, 419, 421, 492, 496, 497, 510, 514, 521, 556, 563, 583, 587, 588, 592, 594, 624, 626, 642, 651, 652, 655, 657, 662, 666, 677, 711, 724, 753, 758, 760, 769, 772, 778, 783, 784, 785, 788, 790, 1216, 1218, 1231, 1233, 1244]

print("=== REMOVED RECORDS ===")
for rid in removed_ids:
    cursor.execute("SELECT id, title, country, status, verification_status, is_archived, is_verified FROM scholarships WHERE id = ?", (rid,))
    row = cursor.fetchone()
    if row:
        print(f"  ID {row[0]}: {row[1][:70]} | {row[2]} | status={row[3]} | verified={row[4]} | archived={row[5]} | is_verified={row[6]}")
    else:
        print(f"  ID {rid}: NOT IN CURRENT DB (was removed)")

# Get details of added IDs (1247-1352)
print("\n=== ADDED RECORDS (1247-1352) ===")
cursor.execute("SELECT id, title, country, status, verification_status, is_verified, fully_funded, official_source_url FROM scholarships WHERE id BETWEEN 1247 AND 1352 ORDER BY id")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1][:60]}... | {row[2]} | {row[3]}/{row[4]} | verified={row[5]} | funded={row[6]} | {row[7][:60] if row[7] else 'NO URL'}...")

# Check the specific range 1293-1352
print("\n=== RECORDS 1293-1352 (60 records) ===")
cursor.execute("SELECT id, title, country, fully_funded, funding_amount, funding_currency, funding_period, tuition_coverage, living_cost_coverage, travel_coverage, official_source_url FROM scholarships WHERE id BETWEEN 1293 AND 1352 ORDER BY id")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1][:50]}... | {row[2]} | funded={row[3]} | amt={row[4]} {row[5]}/{row[6]} | tuition={row[7]} living={row[8]} travel={row[9]}")