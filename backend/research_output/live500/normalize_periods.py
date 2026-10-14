"""Normalize funding_period values that overflow the 64-char column.

The apply stage refuses a value that does not fit rather than truncating it,
because a fragment of a cadence reads as if it were the cadence. The long
strings are genuine details, so they are moved to funding_period_detail inside
the same official block (which is preserved whole in official_details) and the
column keeps a short, canonical period.
"""
import json
import os
import re

BASE = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone'
DETAILS = os.path.join(BASE, 'backend', 'config', 'programme_details.json')

SHORT = [
    (r'\bper month\b', 'per month'),
    (r'\bper week\b', 'per week'),
    (r'\bper day\b', 'per day'),
    (r'\bper semester\b', 'per semester'),
    (r'\bacademic year\b', 'per academic year'),
    (r'\bper annum\b', 'per year'),
    (r'\bper year\b', 'per year'),
    (r'\bone[- ]time\b|\bone[- ]off\b|\blump sum\b', 'one-off'),
    (r'\btotal\b', 'total award'),
]

def shorten(text):
    t = text.lower()
    for pattern, short in SHORT:
        if re.search(pattern, t):
            if short == 'per academic year' and re.search(r'per semester|semi', t):
                return 'per semester'
            if short == 'per year' and re.search(r'academic year', t):
                return 'per academic year'
            return short
    return None

path = DETAILS
raw = json.loads(open(path, encoding='utf-8').read())
records = raw['records'] if isinstance(raw, dict) else raw
moved = 0
unresolved = []
for rec in records:
    if not isinstance(rec, dict):
        continue
    official = rec.get('official') or {}
    fp = official.get('funding_period')
    if isinstance(fp, str) and len(fp.strip()) > 64:
        short = shorten(fp)
        if short is None:
            unresolved.append({'id': rec.get('id'), 'len': len(fp), 'value': fp[:90]})
            continue
        official['funding_period_detail'] = fp.strip()
        official['funding_period'] = short
        rec['official'] = official
        moved += 1

if unresolved:
    print('UNRESOLVED (left untouched):')
    for u in unresolved:
        print(' ', u)

with open(path, 'w', encoding='utf-8') as f:
    json.dump(raw, f, ensure_ascii=False, indent=1)
print(f'shortened {moved} funding_period values; {len(unresolved)} unresolved')

# verify
bad = 0
for rec in records:
    fp = (rec.get('official') or {}).get('funding_period')
    if isinstance(fp, str) and len(fp) > 64:
        bad += 1
print('remaining over-length funding_period:', bad)
