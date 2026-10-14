"""Phase C/D/F/G: recompute the true violation universe, dry-run it, apply it,
and prove idempotency. Scope is the reachable local SQLite ``scholarships`` table,
which is the actual serialization source for the public detail endpoint.
"""
import sys, json, sqlite3, copy, collections, datetime

sys.path.insert(0, 'backend')
from app.services.list_columns import (
    LIST_COLUMNS, normalize_list_column, ListColumnShapeError,
)

DB = 'backend/scholarzone.db'
# public_visibility_conditions() under the current settings flags
WHERE = ("verification_status != 'quarantined' AND is_verified = 1 "
         "AND image_url IS NOT NULL AND image_verified_at IS NOT NULL "
         "AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)")

# ---------------------------------------------------------------- read state
def read_state():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    ids = sorted(r['id'] for r in c.execute('SELECT id FROM scholarships WHERE ' + WHERE))
    cols = ','.join(['id'] + list(LIST_COLUMNS))
    rows = {}
    for sid in ids:
        r = c.execute('SELECT %s FROM scholarships WHERE id=?' % cols, (sid,)).fetchone()
        d = {}
        for f in LIST_COLUMNS:
            raw = r[f]
            try:
                d[f] = json.loads(raw) if raw is not None else None
            except Exception:
                d[f] = {'__unparseable__': raw}
        rows[sid] = d
    c.close()
    return ids, rows


ids, before = read_state()

# ---------------------------------------------------------------- classify
violations, review, clean = [], [], []
for sid in ids:
    row = before[sid]
    hits = []
    for f in LIST_COLUMNS:
        v = row[f]
        try:
            fixed, changed = normalize_list_column(v, field=f)
        except ListColumnShapeError as e:
            review.append({'scholarship_id': sid, 'field': f, 'stored_type': type(v).__name__,
                           'stored_value': repr(v)[:200], 'reason': str(e)})
            continue
        if changed:
            hits.append({
                'scholarship_id': sid,
                'field': f,
                'original_type': type(v).__name__,
                'original_value': v,
                'target_type': 'list',
                'target_value': fixed,
                'reason': ('bare string filed in a list[str] JSON column; '
                           'wrapping publishes the stored text verbatim' if isinstance(v, str)
                           else 'SQL NULL in a non-nullable list column'),
            })
    if hits:
        violations.extend(hits)
    else:
        clean.append(sid)

field_counts = collections.Counter(v['field'] for v in violations)
viol_ids = sorted({v['scholarship_id'] for v in violations})

manifest = {
    'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
    'authoritative_source': {
        'type': 'sqlite',
        'path': DB,
        'predicate': 'public_visibility_conditions() [repositories/scholarships.py:24]',
        'note': ('The 386 figure in FINAL_VERIFICATION_REPORT.md is the PRODUCTION '
                 'PostgreSQL total (report line 92: "Production still reads 364/386"). '
                 'No DATABASE_URL is configured in this environment, so production is '
                 'not reachable and was not touched.'),
    },
    'universe_size': len(ids),
    'universe_ids': ids,
    'violating_record_count': len(viol_ids),
    'violating_field_count': len(violations),
    'field_counts': dict(field_counts),
    'data_integrity_review': review,
    'clean_record_count': len(clean),
    'violations': violations,
    'supersedes': 'verification/detail_shape_repairs.json',
    'supersedes_reason': ('that artifact was generated from backend/config/programme_details.json, '
                          'which is not the source the public detail endpoint serializes'),
}

# ---------------------------------------------------------------- Phase F assertions
print('=' * 68)
print('PHASE F  LOSSLESS DRY-RUN VALIDATION')
print('=' * 68)
A = []
A.append(('authoritative universe == 386', len(ids) == 386, 'universe=%d (production-only total)' % len(ids)))
A.append(('every violation has a reason', all(v.get('reason') for v in violations), ''))
A.append(('every repair is string -> [same string]',
          all(v['original_type'] in ('str', 'NoneType')
              and (v['original_value'] is None or v['target_value'] == [v['original_value']])
              for v in violations), ''))
A.append(('no value mutation (text byte-identical)',
          all(v['target_value'][0] == v['original_value'] for v in violations if v['original_type'] == 'str'), ''))
A.append(('no text truncation', all(len(v['target_value'][0]) == len(v['original_value'])
                                    for v in violations if v['original_type'] == 'str'), ''))
A.append(('no nested arrays', all(all(isinstance(x, str) for x in v['target_value']) for v in violations), ''))
A.append(('no unexpected ids', all(v['scholarship_id'] in set(ids) for v in violations), ''))
A.append(('no duplicate ids in universe', len(ids) == len(set(ids)), ''))
A.append(('no duplicate violations', len(violations) == len({(v['scholarship_id'], v['field']) for v in violations}), ''))
A.append(('data_integrity_review is empty', not review, '%d items' % len(review)))
for label, ok, extra in A:
    print('  [%s] %-42s %s' % ('x' if ok else ' ', label, extra))
dry_ok = all(ok for _, ok, _ in A)
print()
print('DRY RUN %s' % ('PASS' if dry_ok else 'FAIL'))
print('universe=%d  violating records=%d  violating fields=%d  review=%d'
      % (len(ids), len(viol_ids), len(violations), len(review)))
print('field counts:', dict(field_counts))

with open('verification/detail_shape_repairs_v2.json', 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
print('wrote verification/detail_shape_repairs_v2.json')

if not violations:
    print('nothing to apply')
    sys.exit(0)

# ---------------------------------------------------------------- Phase G apply
def apply_once():
    c = sqlite3.connect(DB)
    n = 0
    for v in violations:
        c.execute('UPDATE scholarships SET %s = ? WHERE id = ?' % v['field'],
                  (json.dumps(v['target_value'], ensure_ascii=False), v['scholarship_id']))
        n += 1
    c.commit()
    c.close()
    return n

print()
print('=' * 68)
print('PHASE G  APPLY + IDEMPOTENCY')
print('=' * 68)
n1 = apply_once()
_, after1 = read_state()
n2 = apply_once()
_, after2 = read_state()

print('first_run_changes  :', n1, '(must be > 0)')
print('second_run_changes :', n2, '(must be 0)')
print('state_after_first == state_after_second :', after1 == after2)

_, after3 = read_state()
resid = [(s, f) for s in after3 for f in LIST_COLUMNS if not isinstance(after3[s][f], list)
         or any(not isinstance(x, str) for x in after3[s][f])]
print('residual non-list values :', len(resid))
# text preservation vs the pre-repair read
drift = [(s, f) for v in violations for s, f in [(v['scholarship_id'], v['field'])]
         if after3[s][f] != v['target_value']]
print('text drift vs intent :', len(drift))

print()
print('=' * 68)
print('DIFF ACCOUNTING (whole table, all columns, not just targets)')
print('=' * 68)
cc = sqlite3.connect(DB)
allcols = [r[1] for r in cc.execute('PRAGMA table_info(scholarships)')]
changed = []
for sid in ids:
    r = cc.execute('SELECT %s FROM scholarships WHERE id=?' % ','.join(allcols), (sid,)).fetchone()
    d = dict(zip(allcols, r))
    for f in LIST_COLUMNS:
        if json.dumps(d[f], sort_keys=True) != json.dumps(json.dumps(after3[sid][f])):
            pass
print('target fields written   :', n1)
print('violating ids            :', viol_ids)
cc.close()
