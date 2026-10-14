import sys, json, sqlite3
sys.path.insert(0, 'backend')
from pydantic import ValidationError
from app.schemas import ScholarshipDetailResponse
from app.database import get_session_factory
from app.services.scholarships import get_scholarship_details
from app.services.list_columns import normalize_list_column, ListColumnShapeError

FIELDS = ['eligibility', 'benefits', 'coverage', 'requirements', 'documents', 'application_method']

c = sqlite3.connect('backend/scholarzone.db')
c.row_factory = sqlite3.Row
WHERE = ("verification_status != 'quarantined' AND is_verified = 1 "
         "AND image_url IS NOT NULL AND image_verified_at IS NOT NULL "
         "AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)")
pub = [r['id'] for r in c.execute('SELECT id FROM scholarships WHERE ' + WHERE)]
bad = []
for sid in pub:
    row = c.execute('SELECT %s FROM scholarships WHERE id=?' % ','.join(FIELDS), (sid,)).fetchone()
    for f in FIELDS:
        try:
            v = json.loads(row[f]) if row[f] else None
        except Exception:
            v = 'UNPARSEABLE'
        if v is not None and not isinstance(v, list):
            bad.append((sid, f, type(v).__name__))
c.close()

print('public ids (local SQLite) :', len(pub))
print('pre-normalisation violations:', len(bad))
for b in bad:
    print('   ', b)
print()

print('=== normalizer unit checks ===')
cases = [
    ('bare string', 'Apply through the DAAD portal', ['Apply through the DAAD portal'], True),
    ('list', ['a', 'b'], ['a', 'b'], False),
    ('None', None, [], True),
    ('blank string', '   ', [], True),
    ('empty list', [], [], False),
]
allok = True
for label, inp, want, want_changed in cases:
    got, changed = normalize_list_column(inp, field='t')
    ok = got == want and changed == want_changed
    allok &= ok
    print('  %-14s -> %-34r changed=%-5s %s' % (label, got, changed, 'OK' if ok else 'FAIL'))
for label, inp in [('int', 5), ('dict', {'a': 1}), ('bool', True), ('nested list', [['a']])]:
    try:
        normalize_list_column(inp, field='t')
        print('  %-14s -> NOT REFUSED  ** FAIL **' % label); allok = False
    except ListColumnShapeError as e:
        print('  %-14s -> refused explicitly: %s' % (label, str(e)[:58]))
# idempotency of the rule
probe = 'Apply through the DAAD portal'
once, _ = normalize_list_column(probe)
twice, changed2 = normalize_list_column(once)
idem = (once == twice) and changed2 is False
print('  idempotent          :', idem)
print('NORMALIZER OK:', allok and idem)
print()

print('=== end-to-end ScholarshipDetailResponse for the violating rows ===')
s = get_session_factory()()
ok = 0; fail = []
for sid in sorted({b[0] for b in bad}):
    sch = get_scholarship_details(s, sid)
    try:
        resp = ScholarshipDetailResponse.model_validate(sch, from_attributes=True)
        ok += 1
        el = resp.eligibility
        print('  id %-4s OK  eligibility type=%s len=%d first=%r' % (
            sid, type(el).__name__, len(el), (el[0][:58] if el else None)))
    except ValidationError as e:
        fail.append((sid, str(e)[:160]))
print('built OK: %d   failed: %d' % (ok, len(fail)))
for f in fail:
    print('   FAIL', f)
s.close()
