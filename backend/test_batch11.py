"""Test batch 11 specifically."""
import sys, os
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ['SCHOLARZONE_DATABASE_URL'] = 'sqlite:///scholarzone.db'
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'

from app.services.concurrent_dry_run import run_concurrent_dry_run_json
from app.database import reset_database_connections
from app.models import Scholarship, Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import time

DB_PATH = backend_dir / 'scholarzone.db'
DB_URL = f'sqlite:///{DB_PATH.as_posix()}'

reset_database_connections()
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
batch = session.scalars(select(Scholarship.id).order_by(Scholarship.id).offset(50).limit(5)).all()
session.close()
engine.dispose()

print(f"Testing batch: IDs {batch}", flush=True)
start = time.time()
json_output = run_concurrent_dry_run_json(batch, max_concurrency=5, timeout=30.0, max_retries=2)
elapsed = time.time() - start
print(f"Completed in {elapsed:.1f}s", flush=True)

import json
results = json.loads(json_output)
for r in results:
    print(f"  #{r['scholarship_id']}: {r['decision']} ({r.get('error')})", flush=True)
