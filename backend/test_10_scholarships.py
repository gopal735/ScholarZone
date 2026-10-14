"""Test dry-run with first 10 scholarships to check for stalls."""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///scholarzone.db")
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.concurrent_dry_run import run_concurrent_dry_run
from app.database import reset_database_connections
from app.models import Scholarship, Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import time

DB_PATH = backend_dir / "scholarzone.db"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

reset_database_connections()
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

try:
    ids = session.scalars(select(Scholarship.id).order_by(Scholarship.id).limit(10)).all()
    print(f"Processing {len(ids)} scholarships: {ids}")
    start = time.time()
    results = run_concurrent_dry_run(ids, max_concurrency=8, timeout=30.0, max_retries=2)
    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s")
    for r in results:
        print(f"  #{r.scholarship_id}: {r.decision} (candidates={r.candidates_found})")
finally:
    session.close()
    engine.dispose()
