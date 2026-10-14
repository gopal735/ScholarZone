"""Profile validation step by step."""
import sys, os
from pathlib import Path
import time

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ['SCHOLARZONE_DATABASE_URL'] = 'sqlite:///scholarzone.db'
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'

from app.services.image_discovery import ImageDiscoveryService
from app.services.image_validator import ImageValidator
from app.models import Scholarship, Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

DB_PATH = backend_dir / 'scholarzone.db'
DB_URL = f'sqlite:///{DB_PATH.as_posix()}'
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

try:
    s = session.get(Scholarship, 1)
    discovery = ImageDiscoveryService(timeout=30.0, max_candidates=50)
    candidates = discovery.discover_from_scholarship(s.official_source_url)
    print(f"Discovered {len(candidates)} candidates")
    
    validator = ImageValidator(seen_images={}, timeout=30.0)
    
    for i, c in enumerate(candidates[:5]):
        print(f"\n--- Candidate {i+1}: {c.image_url[:70]} ---")
        
        t0 = time.time()
        result = validator.validate_candidate(c, s.title, s.official_source_url)
        t1 = time.time()
        
        print(f"  Status: {result.status.value} in {t1-t0:.2f}s")
        print(f"  Reachable: {result.is_reachable} ({result.http_status})")
        print(f"  Valid image: {result.is_valid_image} ({result.content_type})")
        print(f"  Official domain: {result.is_official_domain}")
        print(f"  Non-content signals: {len(result.non_content_signals)}, weight={result.non_content_total_weight}")
        print(f"  Relevance: {result.relevance_score}")
        print(f"  Rejection reasons: {result.rejection_reasons}")
finally:
    session.close()
    engine.dispose()
