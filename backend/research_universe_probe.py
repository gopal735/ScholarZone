import sys, json
sys.path.insert(0, '.')
from sqlalchemy import select, func
from app.database import get_session_factory
from app.repositories.scholarships import public_visibility_conditions
from app.core.config import get_settings
from app.models import Scholarship

st = get_settings()
print('flags: require_verified=%s require_image=%s allow_third_party=%s' % (
    st.public_require_verified, st.public_require_verified_image, st.public_allow_third_party_image))

s = get_session_factory()()
conds = public_visibility_conditions()

ids = sorted(set(s.execute(select(Scholarship.id).where(*conds)).scalars().all()))
total_rows = s.execute(select(func.count()).select_from(Scholarship)).scalar()
print('TOTAL rows in storage      :', total_rows)
print('AUTHORITATIVE PUBLIC IDS   :', len(ids))

# catalogue_counts is what /stats publishes
from app.services.counting.catalogue import catalogue_counts, catalogue_summary
counts = catalogue_counts(s)
print()
print('=== /stats published figures ===')
for k, v in sorted(summary.items()) if (summary := catalogue_summary(counts)) else []:
    print('  %-34s %s' % (k, v))

json.dump({'authoritative_public_ids': ids, 'total_rows': total_rows,
           'flags': {'require_verified': st.public_require_verified,
                     'require_image': st.public_require_verified_image,
                     'allow_third_party': st.public_allow_third_party_image}},
          open('../research/bachelor/_merged/authoritative_universe.json', 'w'), indent=2)
print()
print('wrote authoritative_universe.json')
s.close()
