import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else 'scholarzone.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print(f'Database: {db_path}')
print('Tables:')
for t in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {t[0]}')
    count = cursor.fetchone()[0]
    print(f'  {t[0]}: {count} rows')
conn.close()