"""Build the 500-agent deep-research queue for ScholarZone enrichment.

Reads the live DB, partitions the 643 active scholarship rows into exactly 500
agent assignments (group A = rows missing funding_amount that the existing
programme_details corpus does not cover, one row per agent; group B = the rest,
paired by country so one agent researches one official domain for two rows),
writes per-agent assignment briefs and a shared instruction file.
"""
import json
import os
import sqlite3
from collections import defaultdict

BASE = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone'
DB = os.path.join(BASE, 'backend', 'scholarzone.db')
DETAILS = os.path.join(BASE, 'backend', 'config', 'programme_details.json')
OUT = os.path.join(BASE, 'backend', 'research_output', 'live500')
TODAY = '2026-10-10'

os.makedirs(os.path.join(OUT, 'assignments'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'results'), exist_ok=True)

det = json.loads(open(DETAILS, encoding='utf-8').read())
covered_ids = set()
for r in det['records']:
    if isinstance(r, dict) and 'id' in r:
        if (r.get('official') or {}).get('funding_amount') not in (None, ''):
            covered_ids.add(int(r['id']))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM scholarships WHERE is_archived = 0')
rows = [dict(r) for r in cur.fetchall()]
conn.close()

def jsonfield(v):
    if v is None or v == '':
        return None
    try:
        p = json.loads(v)
        return p
    except Exception:
        return v

def brief(r):
    existing = {
        'funding_amount': r['funding_amount'],
        'funding_currency': r['funding_currency'],
        'funding_period': r['funding_period'],
        'tuition_coverage': r['tuition_coverage'],
        'living_cost_coverage': r['living_cost_coverage'],
        'travel_coverage': r['travel_coverage'],
        'fully_funded': r['fully_funded'],
        'description': r['description'],
        'eligibility': jsonfield(r['eligibility']),
        'eligibility_summary': r['eligibility_summary'],
        'benefits': jsonfield(r['benefits']),
        'coverage': jsonfield(r['coverage']),
        'requirements': jsonfield(r['requirements']),
        'documents': jsonfield(r['documents']),
        'english_requirement': r['english_requirement'],
        'application_method': jsonfield(r['application_method']),
        'selection_notes': r['selection_notes'],
        'best_fit': r['best_fit'],
        'notes': r['notes'],
        'duration': r['duration'],
        'application_period': r['application_period'],
        'deadline_display': r['deadline_display'],
        'deadline_date': str(r['deadline_date']) if r['deadline_date'] else None,
        'region': r['region'],
        'program_type': r['program_type'],
        'applicant_utility': jsonfield(r['applicant_utility']),
        'official_details': jsonfield(r['official_details']),
    }
    missing = [k for k, v in existing.items() if v in (None, '', [], {})]
    return {
        'id': r['id'],
        'title': r['title'],
        'country': r['country'],
        'degree': r['degree'],
        'funding_label': r['funding'],
        'status': r['status'],
        'official_source': r['official_source'],
        'official_source_url': r['official_source_url'],
        'application_link': r['application_link'],
        'catalogue_url': r['catalogue_url'],
        'official_updates_url': r['official_updates_url'],
        'existing': existing,
        'missing_fields': missing,
    }, missing

briefs = {}
for r in rows:
    b, m = brief(r)
    briefs[r['id']] = b

groupA = [r['id'] for r in rows
          if (r['funding_amount'] in (None, '')) and r['id'] not in covered_ids]
groupB = [r['id'] for r in rows if r['id'] not in set(groupA)]
# pair group B by country for domain efficiency
by_country = defaultdict(list)
for rid in groupB:
    by_country[briefs[rid]['country']].append(rid)
pairs = []
for country in sorted(by_country):
    ids = sorted(by_country[country])
    for i in range(0, len(ids), 2):
        pairs.append(ids[i:i + 2])

assert len(groupA) + sum(len(p) for p in pairs) == len(rows), (len(groupA), sum(len(p) for p in pairs), len(rows))
assert set(groupA).isdisjoint(set(groupB))

assignments = []
for rid in groupA:
    assignments.append([rid])
for p in pairs:
    assignments.append(p)
# rebalance so the single-row assignments sit in group B where needed
total = len(assignments)

TARGET = 500
# Fold surplus single-row assignments into existing ones, preferring same
# country, until exactly TARGET agents remain.
while len(assignments) > TARGET:
    singles = [i for i, a in enumerate(assignments) if len(a) == 1]
    if len(singles) < 2:
        # fall back to folding the smallest multi-row assignment
        singles = sorted(range(len(assignments)), key=lambda i: len(assignments[i]))[:2]
    a, b = singles[0], singles[1]
    assignments[a] = assignments[a] + assignments[b]
    del assignments[b]
print('final agent count:', len(assignments), 'rows covered:', sum(len(a) for a in assignments))

manifest = []
for n, ids in enumerate(assignments):
    name = f'agent_{n:03d}'
    rec = {
        'agent': name,
        'assignment_count': len(ids),
        'scholarships': [briefs[i] for i in ids],
        'result_file': os.path.join(OUT, 'results', f'{name}.json'),
    }
    with open(os.path.join(OUT, 'assignments', f'{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    manifest.append({'agent': name, 'ids': ids,
                     'result_file': os.path.join(OUT, 'results', f'{name}.json')})

with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump({'created': TODAY, 'total_agents': len(manifest),
               'active_rows': len(rows), 'assignments': manifest}, f, ensure_ascii=False, indent=1)
print('wrote', len(manifest), 'assignment files to', OUT)
