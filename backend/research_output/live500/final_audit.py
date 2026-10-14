"""Final integrity audit for the live-500 enrichment run."""
import json
import os
import re
import sqlite3
from datetime import date

BASE = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone'
DB = os.path.join(BASE, 'backend', 'scholarzone.db')
DETAILS = os.path.join(BASE, 'backend', 'config', 'programme_details.json')

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def count(where):
    cur.execute(f'SELECT COUNT(*) FROM scholarships WHERE {where}')
    return cur.fetchone()[0]

total_active = count('is_archived=0')
print(f'active rows: {total_active}')

print('\n-- completeness --')
for c in ['funding_amount', 'funding_currency', 'funding_period', 'tuition_coverage',
          'living_cost_coverage', 'travel_coverage', 'fully_funded',
          'official_details', 'applicant_utility', 'programme_verification',
          'english_requirement', 'deadline_date', 'description']:
    n = count(f'is_archived=0 AND "{c}" IS NOT NULL AND "{c}" != \'\'')
    print(f'  {c:26s} {n:4d}/{total_active} ({100*n/total_active:.1f}%)')

print('\n-- integrity invariants --')
bad_ff = count('is_archived=0 AND fully_funded=1 AND (tuition_coverage IS NULL OR tuition_coverage=0)')
print(f'  fully_funded asserted without tuition coverage: {bad_ff} (must be 0)')

bad_cur = count("is_archived=0 AND funding_currency IS NOT NULL AND funding_currency != '' AND funding_currency NOT GLOB '[A-Z][A-Z][A-Z]'")
print(f'  non-ISO funding_currency: {bad_cur} (must be 0)')

bad_amt = count("is_archived=0 AND funding_amount IS NOT NULL AND funding_amount != '' AND CAST(funding_amount AS REAL) = 0")
print(f'  suspicious funding_amount: {bad_amt} (must be 0)')

long_period = count("is_archived=0 AND funding_period IS NOT NULL AND LENGTH(funding_period) > 64")
print(f'  funding_period over 64 chars: {long_period} (must be 0)')

json_cols = 0
bad_json = 0
for col in ('official_details', 'applicant_utility', 'programme_verification'):
    cur.execute(f'SELECT id, {col} FROM scholarships WHERE is_archived=0 AND {col} IS NOT NULL AND {col} != \'\'')
    for r in cur.fetchall():
        json_cols += 1
        try:
            json.loads(r[col])
        except (TypeError, ValueError):
            bad_json += 1
print(f'  JSON columns parse failures: {bad_json}/{json_cols} (must be 0)')

# citations present in verification
cur.execute("SELECT id, programme_verification FROM scholarships WHERE is_archived=0 AND programme_verification IS NOT NULL")
no_cite = 0
with_cite = 0
for r in cur.fetchall():
    try:
        v = json.loads(r['programme_verification']) or {}
    except ValueError:
        continue
    cites = [u for u in (v.get('source_citations') or []) if isinstance(u, str) and u.startswith('http')]
    if cites:
        with_cite += 1
    else:
        no_cite += 1
print(f'  programme_verification rows with http citations: {with_cite} (without: {no_cite})')

# fully_funded strictly implies tuition coverage
cur.execute('SELECT COUNT(*) FROM scholarships WHERE is_archived=0 AND fully_funded=1')
ff = cur.fetchone()[0]
print(f'  fully_funded=1 rows: {ff}')

raw = json.loads(open(DETAILS, encoding='utf-8').read())
records = raw['records']
print(f'\ncorpus: {len(records)} records')
utility_only = {
    'application_readiness_checklist', 'common_rejection_risks',
    'estimated_uncovered_costs', 'document_audit', 'alerts',
    'submission_workflow', 'summary', 'best_fit',
}
leaks = [r['id'] for r in records
         if any(k in (r.get('official') or {}) for k in utility_only)]
print(f'  records with utility keys inside official: {len(leaks)} (must be 0)')
no_ver = [r['id'] for r in records
          if not [u for u in ((r.get('verification') or {}).get('source_citations') or [])
                  if isinstance(u, str) and u.startswith('http')]
          and not [u for u in ((r.get('official') or {}).get('official_source_urls') or [])
                   if isinstance(u, str) and u.startswith('http')]]
print(f'  records without citations: {len(no_ver)} (must be 0) {no_ver[:8]}')
conn.close()
