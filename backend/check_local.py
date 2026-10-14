import sqlite3
conn = sqlite3.connect('scholarzone.db')
cursor = conn.cursor()
cursor.execute("SELECT id, title, status, deadline_precision, eligibility, benefits, coverage, requirements, documents, application_method FROM scholarships WHERE id IN (489, 490, 1, 100, 306)")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
