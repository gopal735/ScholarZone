import sys
sys.path.insert(0, r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend')

from app.database import get_engine, init_database
from sqlalchemy import text

init_database()
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT id, title, official_source_url
        FROM scholarships
        WHERE official_source_url IS NOT NULL
        ORDER BY id
    '''))
    rows = result.fetchall()
    print(f'Scholarships with official_source_url: {len(rows)}')
    for r in rows:
        line = f"ID:{r[0]} | {r[1][:50]} | {r[2]}"
        sys.stdout.buffer.write((line + '\n').encode('utf-8'))
