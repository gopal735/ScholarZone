import sys
sys.path.insert(0, '.')
from app.database import get_session_factory
from app.models import Scholarship
from datetime import date

session_factory = get_session_factory()
db = session_factory()
s = db.query(Scholarship).filter(Scholarship.id == 2).first()
s.next_verification_due = date(2020, 1, 1)
db.commit()
db.close()
print('Done')
