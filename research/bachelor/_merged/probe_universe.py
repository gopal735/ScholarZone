import sqlite3, json

c = sqlite3.connect('backend/scholarzone.db')
c.row_factory = sqlite3.Row

# Mirror of public_visibility_conditions() with the CURRENT settings flags:
#   public_require_verified=True, public_require_verified_image=True,
#   public_allow_third_party_image=False
# is_archived is absent from this SQLite file, which per the PostgreSQL
# migration comment means "immediately, correctly un-archived" (default FALSE).
WHERE = """
verification_status != 'quarantined'
AND is_verified = 1
AND image_url IS NOT NULL
AND image_verified_at IS NOT NULL
AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)
"""

rows = c.execute('SELECT id FROM scholarships WHERE ' + WHERE).fetchall()
ids = sorted(r['id'] for r in rows)
print('rows in storage                :', c.execute('SELECT COUNT(*) FROM scholarships').fetchone()[0])
print('passing visibility predicate   :', len(ids))

# progressive narrowing, to show where the number lands
steps = [
    ('verification_status != quarantined', "verification_status != 'quarantined'"),
    ('+ is_verified', "verification_status != 'quarantined' AND is_verified = 1"),
    ('+ image_url not null', "verification_status != 'quarantined' AND is_verified = 1 AND image_url IS NOT NULL"),
    ('+ image_verified_at not null', WHERE.replace("AND (image_source_type", "AND 1=1 AND (image_source_type")),
]
print()
for label, w in steps:
    print('  %-32s -> %d' % (label, c.execute('SELECT COUNT(*) FROM scholarships WHERE ' + w).fetchone()[0]))

# what blocks the rest
print()
tot = c.execute('SELECT COUNT(*) FROM scholarships').fetchone()[0]
print('not verified                   :', c.execute("SELECT COUNT(*) FROM scholarships WHERE is_verified != 1").fetchone()[0])
print('verified but no image_url      :', c.execute("SELECT COUNT(*) FROM scholarships WHERE is_verified = 1 AND image_url IS NULL").fetchone()[0])
print('image_url but not image_verified:', c.execute("SELECT COUNT(*) FROM scholarships WHERE is_verified = 1 AND image_url IS NOT NULL AND image_verified_at IS NULL").fetchone()[0])
print('wikimedia image_source_type    :', c.execute("SELECT COUNT(*) FROM scholarships WHERE image_source_type = 'wikimedia'").fetchone()[0])
print('quarantined                    :', c.execute("SELECT COUNT(*) FROM scholarships WHERE verification_status = 'quarantined'").fetchone()[0])

json.dump({'predicate_ids': ids, 'count': len(ids)},
          open('research/bachelor/_merged/sqlite_predicate_ids.json', 'w'))
print()
print('max id in file:', c.execute('SELECT MAX(id) FROM scholarships').fetchone()[0])
c.close()
