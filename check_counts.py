import sqlite3

conn = sqlite3.connect(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db')
cursor = conn.cursor()

# Total
cursor.execute('SELECT COUNT(*) FROM scholarships')
total = cursor.fetchone()[0]
print(f'TOTAL = {total}')

# With both gates ON (current production)
cursor.execute('''
    SELECT COUNT(*) FROM scholarships 
    WHERE verification_status = 'active' 
    AND is_archived = 0 
    AND status != 'closed'
    AND image_url IS NOT NULL
    AND image_verified_at IS NOT NULL
    AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)
''')
both_gates = cursor.fetchone()[0]
print(f'With both gates ON (current production): {both_gates}')

# With verification gate only
cursor.execute('''
    SELECT COUNT(*) FROM scholarships 
    WHERE verification_status = 'active' 
    AND is_archived = 0 
    AND status != 'closed'
''')
ver_gate = cursor.fetchone()[0]
print(f'Verification gate only: {ver_gate}')

# With NO gates (new behavior)
cursor.execute('''
    SELECT COUNT(*) FROM scholarships 
    WHERE verification_status != 'quarantined' 
    AND is_archived = 0 
    AND status != 'closed'
''')
no_gates = cursor.fetchone()[0]
print(f'No gates (expected new public count): {no_gates}')

# Status breakdown
cursor.execute('SELECT status, COUNT(*) FROM scholarships GROUP BY status')
print('\nStatus breakdown:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Verification status breakdown
cursor.execute('SELECT verification_status, COUNT(*) FROM scholarships GROUP BY verification_status')
print('\nVerification status breakdown:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Archived
cursor.execute('SELECT is_archived, COUNT(*) FROM scholarships GROUP BY is_archived')
print('\nArchived breakdown:')
for row in cursor.fetchall():
    print(f'  is_archived={row[0]}: {row[1]}')

# Quarantined
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE verification_status = 'quarantined'")
print(f'\nQuarantined: {cursor.fetchone()[0]}')

# Closed
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE status = 'closed'")
print(f'Closed: {cursor.fetchone()[0]}')

# Archived count
cursor.execute('SELECT COUNT(*) FROM scholarships WHERE is_archived = 1')
print(f'Archived: {cursor.fetchone()[0]}')

conn.close()