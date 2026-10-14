import sqlite3
conn = sqlite3.connect('scholarzone.db')
cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for row in cursor:
    print(row[0])
    print('---')
conn.close()
