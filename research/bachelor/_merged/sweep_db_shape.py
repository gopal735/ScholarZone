import sqlite3, json, collections

FIELDS = ['eligibility', 'benefits', 'coverage', 'application_method', 'requirements', 'documents']

c = sqlite3.connect('backend/scholarzone.db')
c.row_factory = sqlite3.Row

WHERE = """
verification_status != 'quarantined'
AND is_verified = 1
AND image_url IS NOT NULL
AND image_verified_at IS NOT NULL
AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)
"""
pub = [r['id'] for r in c.execute('SELECT id FROM scholarships WHERE ' + WHERE)]
print('public rows in local SQLite :', len(pub))

viol = collections.defaultdict(list)
types = collections.defaultdict(collections.Counter)
checked = 0

for sid in pub:
    row = c.execute('SELECT id, %s FROM scholarships WHERE id = ?' % ', '.join(FIELDS), (sid,)).fetchone()
    for f in FIELDS:
        raw = row[f]
        checked += 1
        if raw is None:
            types[f]['null(SQL NULL)'] += 1
            viol[f].append((sid, 'null', None))
            continue
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            types[f]['unparseable'] += 1
            viol[f].append((sid, 'unparseable', raw[:60]))
            continue
        if isinstance(v, list):
            bad = [x for x in v if not isinstance(x, str)]
            if bad:
                types[f]['list_with_non_str'] += 1
                viol[f].append((sid, 'list_with_non_str', bad[:3]))
            elif any(isinstance(x, list) for x in v):
                types[f]['nested_list'] += 1
                viol[f].append((sid, 'nested_list', v[:2]))
            else:
                types[f]['ok_list'] += 1
        elif isinstance(v, str):
            types[f]['BARE_STRING'] += 1
            viol[f].append((sid, 'bare_string', v[:80]))
        elif isinstance(v, dict):
            types[f]['dict'] += 1
            viol[f].append((sid, 'dict', list(v)[:3]))
        else:
            types[f]['other:' + type(v).__name__] += 1
            viol[f].append((sid, 'other:' + type(v).__name__, v))

print('field values checked        :', checked)
print()
print('=== value shape per field ===')
total_bad = 0
for f in FIELDS:
    print('%-20s %s' % (f, dict(types[f])))
    total_bad += sum(n for k, n in types[f].items() if k != 'ok_list')
print()
print('TOTAL NON-CONFORMING VALUES :', total_bad)
for f in FIELDS:
    if viol[f]:
        print('  %s -> %d violations, e.g. %s' % (f, len(viol[f]), viol[f][:2]))

json.dump({f: [{'id': i, 'kind': k, 'value': v} for i, k, v in viol[f]] for f in FIELDS},
          open('research/bachelor/_merged/db_field_violations.json', 'w'), indent=2)
c.close()
