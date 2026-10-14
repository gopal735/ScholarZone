import sqlite3

DB_PATH = "scholarzone.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

countries = ['Australia', 'Austria', 'Belgium', 'Canada', 'China']
for country in countries:
    cursor.execute('''
        SELECT id, title, official_source_url, funding, degree, status
        FROM scholarships
        WHERE country = ?
        ORDER BY id
    ''', (country,))
    rows = cursor.fetchall()
    print(f"\n=== {country} ({len(rows)} records) ===")
    for row in rows:
        print(f"  [{row[0]}] {row[1]}")
        print(f"       URL: {row[2]}")
        print(f"       Funding: {row[3]} | Degree: {row[4]} | Status: {row[5]}")

conn.close()
