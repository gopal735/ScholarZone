import sqlite3

conn = sqlite3.connect(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db')
cursor = conn.cursor()

# Get all IDs
cursor.execute('SELECT id FROM scholarships')
all_ids = set(row[0] for row in cursor.fetchall())
print(f'TOTAL = {len(all_ids)}')

# Closed IDs
cursor.execute("SELECT id FROM scholarships WHERE status = 'closed'")
closed_ids = set(row[0] for row in cursor.fetchall())
print(f'CLOSED = {len(closed_ids)}')

# Archived IDs
cursor.execute('SELECT id FROM scholarships WHERE is_archived = 1')
archived_ids = set(row[0] for row in cursor.fetchall())
print(f'ARCHIVED = {len(archived_ids)}')

# Quarantined IDs
cursor.execute("SELECT id FROM scholarships WHERE verification_status = 'quarantined'")
quarantined_ids = set(row[0] for row in cursor.fetchall())
print(f'QUARANTINED = {len(quarantined_ids)}')

# Intersections
print(f'CLOSED+ARCHIVED = {len(closed_ids & archived_ids)}')
print(f'CLOSED+QUARANTINED = {len(closed_ids & quarantined_ids)}')
print(f'ARCHIVED+QUARANTINED = {len(archived_ids & quarantined_ids)}')
print(f'ALL THREE = {len(closed_ids & archived_ids & quarantined_ids)}')

# Union
excluded = closed_ids | archived_ids | quarantined_ids
print(f'EXCLUDED UNION = {len(excluded)}')

# Public
public = all_ids - excluded
print(f'PUBLIC = {len(public)}')

# Verify
print(f'PUBLIC + EXCLUDED = {len(public) + len(set().union(closed_ids, archived_ids, quarantined_ids))} == TOTAL? {len(public) + len(set().union(closed_ids, archived_ids, quarantined_ids)) == len(all_ids)}')

conn.close()