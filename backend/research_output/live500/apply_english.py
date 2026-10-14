"""Fill english_requirement from the merged corpus.

The apply stage's text_map deliberately covers the columns its ingestion model
polices; english_requirement is a Text column the stage never writes, so the
researched value would sit in the corpus and never reach the row. This writes
it the same way the stage does: empty fields only, and only from a block that
carries citations.
"""
import json
import os
import sqlite3
import sys
from datetime import date

BASE = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone'
DETAILS = os.path.join(BASE, 'backend', 'config', 'programme_details.json')
DB = os.path.join(BASE, 'backend', 'scholarzone.db')

def http_urls(values):
    if not isinstance(values, list):
        return []
    return [u for u in values if isinstance(u, str) and u.startswith(('http://', 'https://'))]

def main(apply=False):
    raw = json.loads(open(DETAILS, encoding='utf-8').read())
    records = raw['records'] if isinstance(raw, dict) else raw
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    filled, skipped = [], []
    for rec in records:
        rid = rec.get('id')
        if rid is None:
            continue
        official = rec.get('official') or {}
        verification = rec.get('verification') or {}
        citations = http_urls(verification.get('source_citations')) or http_urls(official.get('official_source_urls'))
        if not citations:
            skipped.append({'id': rid, 'reason': 'no citations'})
            continue
        value = official.get('english_requirement')
        if not isinstance(value, str) or not value.strip():
            continue
        row = conn.execute('SELECT id, english_requirement FROM scholarships WHERE id=?', (rid,)).fetchone()
        if row is None:
            continue
        if (row['english_requirement'] or '').strip():
            continue
        filled.append({'id': rid, 'length': len(value.strip())})
        if apply:
            conn.execute('UPDATE scholarships SET english_requirement=? WHERE id=?', (value.strip()[:4000], rid))
    if apply:
        conn.commit()
        conn.execute('UPDATE Scholarships SET x=1 WHERE 1=0') if False else None
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived=0 AND english_requirement IS NOT NULL AND english_requirement != ''")
    n = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM scholarships WHERE is_archived=0')
    total = cur.fetchone()[0]
    print(f'english_requirement filled this pass: {len(filled)}; skipped: {len(skipped)}')
    print(f'english_requirement now: {n}/{total} ({100*n/total:.1f}%)')
    conn.close()
    if not apply:
        print('DRY RUN - nothing written')

if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
