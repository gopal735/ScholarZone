import sys, json, sqlite3, collections

sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app
from app.services.list_columns import LIST_COLUMNS

DB = 'backend/scholarzone.db'
WHERE = ("verification_status != 'quarantined' AND is_verified = 1 "
         "AND image_url IS NOT NULL AND image_verified_at IS NOT NULL "
         "AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)")

c = sqlite3.connect(DB)
ids = sorted(r[0] for r in c.execute('SELECT id FROM scholarships WHERE ' + WHERE))
print('universe size:', len(ids))

# ---------------- precise idempotency: count only real deltas ----------------
def snapshot():
    cc = sqlite3.connect(DB)
    out = {}
    for sid in ids:
        r = cc.execute('SELECT %s FROM scholarships WHERE id=?' % ','.join(LIST_COLUMNS), (sid,)).fetchone()
        out[sid] = tuple(r)
    cc.close()
    return out

targets = [412, 415, 416, 417, 418, 421, 422, 424, 425, 427]
s0 = snapshot()
cc = sqlite3.connect(DB)
cc.execute('BEGIN')
for sid in targets:
    v = cc.execute('SELECT eligibility FROM scholarships WHERE id=?', (sid,)).fetchone()[0]
    parsed = json.loads(v)
    if isinstance(parsed, str):
        cc.execute('UPDATE scholarships SET eligibility=? WHERE id=?', (json.dumps([parsed]), sid))
cc.commit()
cc.close()
s1 = snapshot()
delta1 = sum(1 for k in s1 if s1[k] != s0[k])
cc = sqlite3.connect(DB)
cc.execute('BEGIN')
for sid in targets:
    v = cc.execute('SELECT eligibility FROM scholarships WHERE id=?', (sid,)).fetchone()[0]
    parsed = json.loads(v)
    if isinstance(parsed, str):
        cc.execute('UPDATE scholarships SET eligibility=? WHERE id=?', (json.dumps([parsed]), sid))
cc.commit()
cc.close()
s2 = snapshot()
delta2 = sum(1 for k in s2 if s2[k] != s1[k])
print()
print('=== PRECISE IDEMPOTENCY ===')
print('first_run_changes  :', delta1)
print('second_run_changes :', delta2)
print('state_after_first == state_after_second :', s1 == s2)
print()

# ---------------- Phase I: full endpoint sweep ----------------
print('=== PHASE I  FULL PUBLIC DETAIL SWEEP ===')
client = TestClient(app, raise_server_exceptions=False)
statuses = collections.Counter()
failures = []
shape_bad = []
FIELDS = ('eligibility', 'benefits', 'coverage', 'requirements',
          'documents', 'required_documents', 'application_method')
for sid in ids:
    r = client.get('/api/scholarships/%d' % sid)
    statuses[r.status_code] += 1
    if r.status_code != 200:
        failures.append({'id': sid, 'status': r.status_code,
                         'error': r.text[:200]})
        continue
    d = r.json()
    for f in FIELDS:
        v = d.get(f)
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            shape_bad.append({'id': sid, 'field': f, 'type': type(v).__name__})
print('swept               :', len(ids))
print('status distribution :', dict(statuses))
print('HTTP 500            :', statuses.get(500, 0))
print('non-200             :', len(failures))
print('schema shape failures:', len(shape_bad))
for f in failures[:10]:
    print('   FAIL', f)
for s in shape_bad[:10]:
    print('   SHAPE', s)

print()
print('VALID %d / %d' % (len(ids) - len(failures), len(ids)))
json.dump({'universe': len(ids), 'statuses': dict(statuses),
           'http_500': statuses.get(500, 0), 'failures': failures,
           'shape_failures': shape_bad},
          open('research/bachelor/_merged/endpoint_sweep.json', 'w'), indent=2)
