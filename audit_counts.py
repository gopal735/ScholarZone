import sqlite3

conn = sqlite3.connect('backend/scholarzone.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM scholarships')
print('Total records:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM scholarships WHERE is_archived = 0')
print('Non-archived:', cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM scholarships WHERE status != 'closed'")
print("Status != closed:", cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived = 0 AND status != 'closed'")
print("Public (not archived, not closed):", cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM scholarships WHERE is_archived = 1')
print('Archived:', cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM scholarships WHERE status = 'closed'")
print('Closed:', cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM scholarships WHERE verification_status = 'quarantined'")
print('Quarantined:', cursor.fetchone()[0])

# Check for IDs in range 1293-1352
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE id BETWEEN 1293 AND 1352")
print('IDs 1293-1352:', cursor.fetchone()[0])

cursor.execute("SELECT id FROM scholarships WHERE id BETWEEN 1293 AND 1352 ORDER BY id")
ids = [row[0] for row in cursor.fetchall()]
print('IDs in range:', ids)

# Check duplicates by official_source_url
cursor.execute("""
    SELECT official_source_url, COUNT(*) as cnt 
    FROM scholarships 
    WHERE official_source_url IS NOT NULL 
    GROUP BY official_source_url 
    HAVING COUNT(*) > 1
""")
dupes = cursor.fetchall()
print('Duplicate official_source_url:', len(dupes))
for d in dupes:
    print(f'  {d[0]}: {d[1]}')

# Check duplicates by title+provider (official_source)
cursor.execute("""
    SELECT title, official_source, COUNT(*) as cnt 
    FROM scholarships 
    WHERE official_source IS NOT NULL 
    GROUP BY title, official_source 
    HAVING COUNT(*) > 1
""")
dupes2 = cursor.fetchall()
print('Duplicate title+provider:', len(dupes2))
for d in dupes2:
    print(f'  {d[0]} | {d[1]}: {d[2]}')

conn.close()