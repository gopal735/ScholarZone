"""Finish funding_period normalization: explicit per-id mapping for the 34
values whose leading text does not resolve to a canonical short period. The
full original text is preserved as funding_period_detail; the column keeps a
short canonical cadence; unpublished periods become null rather than a guess.
"""
import json
import os

BASE = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone'
DETAILS = os.path.join(BASE, 'backend', 'config', 'programme_details.json')

MAP = {
    18: 'per month',            # doctoral researcher employment, paid monthly
    53: 'per fellowship',       # ten-month fellowship programme
    109: 'per month',           # monthly stipend
    115: 'per year',            # three years of fellowship support
    186: 'per semester',        # 75% tuition reduction over 4 semesters
    193: 'per year',            # 50% tuition reduction, programme duration
    207: 'per year',            # up to 25% fee reduction for course duration
    227: 'per month',           # salary under collective agreement
    254: None,                  # no fixed period published
    255: 'per year',            # percentage of one year of tuition fees
    257: 'per year',            # one-year tenure
    278: None,                  # not published as a period
    301: 'one-off',             # partial remission awarded per admitted student
    333: None,                  # not published as a period
    334: None,                  # not published as a period
    391: 'per month',           # personal stipend
    423: 'per mobility',        # per mobility period
    424: 'per year',            # for the first year of study
    433: 'per year',            # annual allowance
    447: 'per year',            # annual allowance
    456: 'per year',            # per study year
    459: 'per year',            # spread over first three years
    500: 'per year',            # one-academic-year grant
    25: 'per month',            # monthly stipend
    30: 'per fortnight',        # fortnightly contribution
    104: 'per month',           # monthly stipend
    123: 'per year',            # tuition scholarship for the degree
    202: 'per year',            # tuition reduction for programme duration
    259: 'per year',            # three-year tenure
    271: 'per admission cycle',
    322: 'per month',           # monthly living allowance
    443: 'per year',            # annual subsidised tuition fees
    470: 'per month',           # stipend for the grant period
    318: None,                  # coverage list, not a published period
}

raw = json.loads(open(DETAILS, encoding='utf-8').read())
moved = 0
for rec in raw['records']:
    if not isinstance(rec, dict):
        continue
    official = rec.get('official') or {}
    fp = official.get('funding_period')
    if isinstance(fp, str) and len(fp) > 64 and rec.get('id') in MAP:
        official['funding_period_detail'] = fp.strip()
        official['funding_period'] = MAP[rec['id']]
        rec['official'] = official
        moved += 1

with open(DETAILS, 'w', encoding='utf-8') as f:
    json.dump(raw, f, ensure_ascii=False, indent=1)

bad = [(rec.get('id'), len((rec.get('official') or {}).get('funding_period')))
       for rec in raw['records']
       if isinstance((rec.get('official') or {}).get('funding_period'), str)
       and len((rec.get('official') or {}).get('funding_period')) > 64]
print(f'resolved {moved}; remaining over-length: {bad}')
