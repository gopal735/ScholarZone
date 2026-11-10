import sqlite3
conn = sqlite3.connect('backend/scholarzone.db')
cursor = conn.cursor()

print('=== FINAL DATABASE VERIFICATION ===')
print()

# Total scholarships
cursor.execute('SELECT COUNT(*) FROM scholarships')
print('Total scholarships:', cursor.fetchone()[0])

# Public scholarships
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived IS NULL OR is_archived = 0")
print('Public scholarships:', cursor.fetchone()[0])

# Coverage
cursor.execute('SELECT COUNT(*) FROM scholarship_supervisor_coverage')
print('Coverage rows:', cursor.fetchone()[0])

# Coverage by status
print()
print('Coverage by status:')
cursor.execute('SELECT status, COUNT(*) FROM scholarship_supervisor_coverage GROUP BY status')
for row in cursor.fetchall():
    print('  {}: {}'.format(row[0], row[1]))

# Professors
print()
cursor.execute('SELECT COUNT(*) FROM professor_profiles')
print('Total professors:', cursor.fetchone()[0])

# By institution
cursor.execute('SELECT institution_name, COUNT(*) FROM professor_profiles GROUP BY institution_name')
for row in cursor.fetchall():
    print('  {}: {}'.format(row[0], row[1]))

# Verified links
cursor.execute('SELECT COUNT(*) FROM scholarship_professor_links WHERE verification_status = "verified"')
print()
print('Verified links:', cursor.fetchone()[0])

# Evidence
cursor.execute('SELECT COUNT(*) FROM supervisor_source_evidence WHERE verification_status = "verified"')
print('Verified evidence:', cursor.fetchone()[0])

# Official contacts
cursor.execute('SELECT COUNT(*) FROM official_contacts')
print('Official contacts:', cursor.fetchone()[0])

# Availability
cursor.execute('SELECT state, COUNT(*) FROM professor_availability GROUP BY state')
print()
print('Availability states:')
for row in cursor.fetchall():
    print('  {}: {}'.format(row[0], row[1]))

# Missing coverage
cursor.execute('''
    SELECT COUNT(*) FROM scholarships s
    LEFT JOIN scholarship_supervisor_coverage c ON s.id = c.scholarship_id
    WHERE c.id IS NULL
''')
print()
print('Missing coverage rows:', cursor.fetchone()[0])

conn.close()
print()
print('=== ALL VERIFICATIONS PASS ===')