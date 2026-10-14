"""Profile time breakdown for a few scholarships."""
import sys
import os
from pathlib import Path
import time

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///scholarzone.db")
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.concurrent_dry_run import _process_scholarship
from app.database import reset_database_connections
from app.models import Scholarship, Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import threading

DB_PATH = backend_dir / "scholarzone.db"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

reset_database_connections()
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

try:
    ids = session.scalars(select(Scholarship.id).order_by(Scholarship.id).limit(3)).all()
    print(f"Processing {len(ids)} scholarships: {ids}")
    for sid in ids:
        s = session.get(Scholarship, sid)
        print(f"\n--- Scholarship {sid}: {s.title[:60]} ---")
        print(f"Source: {s.official_source_url}")
        start = time.time()
        result = _process_scholarship(
            s,
            timeout=30.0,
            max_retries=2,
            cache_lock=threading.Lock(),
            thread_local=threading.local(),
        )
        elapsed = time.time() - start
        print(f"Done in {elapsed:.1f}s: {result.decision}")
        print(f"  Candidates: {result.candidates_found}")
        print(f"  Best: {result.best_candidate_url}")
        print(f"  Error: {result.error}")
finally:
    session.close()
    engine.dispose()
