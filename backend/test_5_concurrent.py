"""Minimal test: process 5 scholarships concurrently to check for deadlocks."""
import sys, os
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
ids = session.scalars(select(Scholarship.id).order_by(Scholarship.id).limit(5)).all()
session.close()
engine.dispose()

print(f"Processing {len(ids)} scholarships...")
results = run_concurrent_dry_run(ids, max_concurrency=5, timeout=30.0, max_retries=2)
print(f"Done! {len(results)} results")
for r in results:
    print(f"  #{r.scholarship_id}: {r.decision} ({r.candidates_found} cand)")
