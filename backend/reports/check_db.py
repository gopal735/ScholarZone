import sqlite3
conn = sqlite3.connect('scholarzone.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT id, title, image_url FROM scholarships WHERE image_url IS NOT NULL')
rows = cur.fetchall()
print('Existing images in DB:')
for row in rows:
    print('  ID', row['id'], ':', row['title'])
    print('    Image:', row['image_url'])
print('Total:', len(rows))
conn.close()
