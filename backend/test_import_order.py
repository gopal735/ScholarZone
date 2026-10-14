import os
import sys
sys.path.insert(0, r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend')

# Simulate test collection order
os.environ.setdefault('SCHOLARZONE_ENVIRONMENT', 'test')
os.environ.setdefault('SCHOLARZONE_DATABASE_URL', 'sqlite:///:memory:')

# Import country intelligence test module first
import tests.test_country_intelligence as ci_test

# Now try to import scholarships test module
# This simulates what happens when pytest collects test_scholarships.py after test_country_intelligence.py
import importlib
import tests.test_scholarships as sch_test
importlib.reload(sch_test)

# Check the database URL
from app.database import get_session_factory
factory = get_session_factory()
print(f'Database URL: {factory.kwargs.get("url", "unknown")}')