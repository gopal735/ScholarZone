"""Test 20 scholarships with individual timing."""
import sys, os, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ['SCHOLARZONE_DATABASE_URL'] = 'sqlite:///scholarzone.db'
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'

from app.services.concurrent_dry_run import _process_scholarship
from app.database import reset_database_connections
from app.models import Scholarship, Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import threading

DB_PATH = backend_dir / 'scholarzone.db'
DB_URL = f'sqlite:///{DB_PATH.as_posix()}'
reset_database_connections()
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
ids = session.scalars(select(Scholarship.id).order_by(Scholarship.id).limit(20)).all()
session.close()
engine.dispose()

results = {}
start = time.time()

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {}
    for sid in ids:
        s = session.object_session(Session()) if session.object_session(Session()) else Session().get(Scholarship, sid)
        # Need to create a new session for each thread
        pass

# Actually let me use the existing function
from app.services.concurrent_dry_run import run_concurrent_dry_run
start = time.time()
results = run_concurrent_dry_run(ids, max_concurrency=8, timeout=30.0, max_retries=2)
elapsed = time.time() - start

for r in results:
    print(f"  #{r.scholarship_id}: {r.decision} ({r.candidates_found} cand) error={r.error}")
print(f"Total: {elapsed:.1f}s")
