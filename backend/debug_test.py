import os
os.environ.setdefault('SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED', 'false')
os.environ.setdefault('SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE', 'false')
os.environ.setdefault('SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE', 'false')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Scholarship
from app.repositories.scholarships import public_visibility_conditions

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = sessionmaker(bind=engine)()

# Create test data
real = Scholarship(
    title='Real Scholarship',
    country='Germany',
    degree='Master',
    funding='Full',
    verification_status='active',
)
landing = Scholarship(
    title='Welcome to GOV.UK',
    country='United Kingdom',
    degree='Master',
    funding='Full',
    verification_status='quarantined',
)

session = sessionmaker(bind=engine)()
session.add_all([real, landing])
session.commit()

# Check the visibility conditions
from app.repositories.scholarships import public_visibility_conditions
from app.models import Scholarship
from sqlalchemy import select

conditions = public_visibility_conditions()
print('Conditions:', conditions)

# Apply conditions
from app.models import Scholarship
from sqlalchemy import select
query = select(Scholarship).where(*public_visibility_conditions())
session = sessionmaker(bind=engine)()
results = session.execute(query).scalars().all()
print(f'Visible records: {len(results)}')
for r in results:
    print(f'  - {r.title}: verification_status={r.verification_status}, is_archived={r.is_archived}, status={r.status}')