"""Run dry-run in batches to find where it stalls."""
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
all_ids = session.scalars(select(Scholarship.id).order_by(Scholarship.id)).all()
session.close()
engine.dispose()

print(f"Total scholarships: {len(all_ids)}", flush=True)

batch_size = 5
for i in range(0, len(all_ids), batch_size):
    batch = all_ids[i:i+batch_size]
    print(f"\n=== Batch {i//batch_size + 1}: IDs {batch[0]}-{batch[-1]} ({len(batch)} scholarships) ===", flush=True)
    start = time.time()
    json_output = run_concurrent_dry_run_json(batch, max_concurrency=5, timeout=30.0, max_retries=2)
    elapsed = time.time() - start
    print(f"Batch completed in {elapsed:.1f}s", flush=True)
    
    import json
    results = json.loads(json_output)
    approved = [r for r in results if r['decision'] == 'approved']
    human_review = [r for r in results if r['decision'] == 'human_review']
    rejected = [r for r in results if r['decision'] == 'rejected']
    errors = [r for r in results if r.get('error')]
    print(f"  Approved: {len(approved)}, Human Review: {len(human_review)}, Rejected: {len(rejected)}, Errors: {len(errors)}", flush=True)
    for a in approved:
        print(f"    APPROVED #{a['scholarship_id']}: {a['scholarship_title'][:50]} -> {a['best_candidate_url'][:70]}", flush=True)

print("\n=== ALL BATCHES COMPLETE ===", flush=True)
