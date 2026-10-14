import json, sqlite3, sys
sys.path.insert(0, 'backend')

c = sqlite3.connect('backend/scholarzone.db')
WHERE = ("verification_status != 'quarantined' AND is_verified = 1 "
         "AND image_url IS NOT NULL AND image_verified_at IS NOT NULL "
         "AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)")
pub = set(r[0] for r in c.execute('SELECT id FROM scholarships WHERE ' + WHERE))
allrows = set(r[0] for r in c.execute('SELECT id FROM scholarships'))

pd = json.load(open('backend/config/programme_details.json', encoding='utf-8'))
pd_ids = set(r['id'] for r in pd['records'])

old = json.load(open('verification/detail_shape_repairs.json', encoding='utf-8'))
old_ids = set(r['id'] for r in old['records'])

print('=== dataset reconciliation (three different populations) ===')
print('A  local SQLite public (visibility predicate):', len(pub))
print('A\' local SQLite total rows in storage        :', len(allrows))
print('B  programme_details.json records            :', len(pd_ids))
print('   old 117-record artifact                   :', len(old_ids))
print()
print('A INTERSECT B          :', len(pub & pd_ids))
print('A MINUS B (no detail cfg):', len(pub - pd_ids), sorted(pub - pd_ids)[:25])
print('B MINUS A (cfg not public locally):', len(pd_ids - pub))
print()
print('=== the "18-record gap" premise ===')
print('programme_details (%d) vs claimed public 386 -> gap of %d'
      % (len(pd_ids), 386 - len(pd_ids)))
print('But 386 is the PRODUCTION PostgreSQL total, not this dataset:')
print('  local public =', len(pub), '| local storage =', len(allrows))
print('  => the 18 figure compared a CONFIG FILE against a PRODUCTION DB count.')
print('     They are different populations and were never comparable.')
print()
print('=== old artifact vs local public universe ===')
print('old artifact ids           :', len(old_ids))
print('  of which public locally  :', len(old_ids & pub))
print('  NOT public locally       :', len(old_ids - pub))
print('public locally NOT in old artifact:', len(pub - old_ids))
print()
print('=== ID 466 ===')
r = c.execute('SELECT id, title, verification_status, is_verified, image_url IS NOT NULL '
              'FROM scholarships WHERE id=466').fetchone()
print('row 466 in local DB        :', r)
print('466 in local public set    :', 466 in pub)
print('466 in old artifact        :', 466 in old_ids)
e = [x for x in old['records'] if x['id'] == 466]
print('466 artifact http_status   :', e[0].get('http_status') if e else 'n/a')
c.close()
