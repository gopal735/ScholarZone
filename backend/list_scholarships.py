import sys
sys.path.insert(0, r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend')

from app.database import get_engine, init_database
from sqlalchemy import text

init_database()
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT id, title, country, official_source_url, official_source, image_url
        FROM scholarships
        ORDER BY id
    '''))
    rows = result.fetchall()
    print(f'Total scholarships: {len(rows)}')
    for r in rows:
        line = f"ID:{r[0]} | {r[1][:60]} | {r[2]} | img:{r[5]}"
        sys.stdout.buffer.write((line + '\n').encode('utf-8'))
