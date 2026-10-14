import sqlite3

DB_PATH = "scholarzone.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Total scholarships:", cursor.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0])
print("Distinct URLs:", cursor.execute("SELECT COUNT(DISTINCT official_source_url) FROM scholarships").fetchone()[0])
print("Missing URLs:", cursor.execute("SELECT COUNT(*) FROM scholarships WHERE official_source_url IS NULL OR official_source_url = ''").fetchone()[0])

cursor.execute("SELECT country, COUNT(*) FROM scholarships GROUP BY country ORDER BY country")
rows = cursor.fetchall()
print(f"\nDistinct countries: {len(rows)}")
for row in rows:
    print(f"  {row[0]}: {row[1]}")

cursor.execute("""
    SELECT title, official_source_url, COUNT(*) as cnt
    FROM scholarships
    GROUP BY title, official_source_url
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 20
""")
dups = cursor.fetchall()
print(f"\nDuplicate groups (title+url): {len(dups)}")
for row in dups:
    print(f"  [{row[2]}] {row[0]} | {row[1]}")

cursor.execute("SELECT country FROM scholarships GROUP BY country ORDER BY country LIMIT 5")
first5 = [row[0] for row in cursor.fetchall()]
print(f"\nFirst 5 countries: {first5}")

conn.close()
