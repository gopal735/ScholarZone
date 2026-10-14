"""Test processing a single scholarship to debug the stall."""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///scholarzone.db")
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.concurrent_dry_run import _process_scholarship
from app.database import reset_database_connections
from app.models import Scholarship, Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

DB_PATH = backend_dir / "scholarzone.db"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

reset_database_connections()
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

try:
    scholarship = session.get(Scholarship, 1)
    if scholarship:
        print(f"Processing scholarship {scholarship.id}: {scholarship.title}")
        print(f"Source URL: {scholarship.official_source_url}")
        
        import threading
        result = _process_scholarship(
            scholarship,
            timeout=30.0,
            max_retries=2,
            cache_lock=threading.Lock(),
            thread_local=threading.local(),
        )
        print(f"Done: {result.decision}")
        print(f"Error: {result.error}")
    else:
        print("Scholarship 1 not found")
finally:
    session.close()
    engine.dispose()
