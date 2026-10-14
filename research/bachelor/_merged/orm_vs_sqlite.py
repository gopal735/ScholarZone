import sys, sqlite3
sys.path.insert(0, 'backend')
from app.models import Scholarship

orm = {a.key for a in Scholarship.__table__.columns}
c = sqlite3.connect('backend/scholarzone.db')
lite = {r[1] for r in c.execute('PRAGMA table_info(scholarships)')}
c.close()

missing = sorted(orm - lite)
extra = sorted(lite - orm)
print('ORM columns      :', len(orm))
print('SQLite columns   :', len(lite))
print()
print('MISSING in SQLite (%d):' % len(missing))
for m in missing:
    col = Scholarship.__table__.columns[m]
    print('   %-26s %s null=%s' % (m, col.type, col.nullable))
print()
print('in SQLite but not ORM (%d):' % len(extra), extra)
