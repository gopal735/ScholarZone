import sqlite3
import json

conn = sqlite3.connect('scholarzone.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM scholarships WHERE is_archived = 0 LIMIT 2")
for row in cur.fetchall():
    d = dict(row)
    print(json.dumps(d, indent=1, default=str)[:4000])
    print('=' * 60)
