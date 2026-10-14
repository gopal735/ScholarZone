"""Test 20 scholarships for timing."""
import time, sys, os
from pathlib import Path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ['SCHOLARZONE_DATABASE_URL'] = 'sqlite:///scholarzone.db'
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'
from app.services.concurrent_dry_run import run_concurrent_dry_run
from app.database import reset_database_connections
from app.models import Scholarship, Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

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

start = time.time()
results = run_concurrent_dry_run(ids, max_concurrency=8, timeout=30.0, max_retries=2)
elapsed = time.time() - start
total_candidates = sum(r.candidates_found for r in results)
print(f'20 scholarships in {elapsed:.1f}s ({elapsed/20:.1f}s each)')
print(f'Total candidates: {total_candidates} ({total_candidates/20:.1f} avg)')
for r in results:
    print(f'  #{r.scholarship_id}: {r.decision} ({r.candidates_found} cand)')
