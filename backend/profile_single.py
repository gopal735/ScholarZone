"""Detailed timing for a single scholarship."""
import sys
import os
from pathlib import Path
import time

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///scholarzone.db")
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.concurrent_dry_run import _process_scholarship
from app.services.source_resolver import SourceResolverService
from app.services.image_discovery import ImageDiscoveryService
from app.services.image_validator import ImageValidator
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
    s = session.get(Scholarship, 1)
    print(f"Scholarship: {s.title}")
    print(f"Source: {s.official_source_url}")
    
    t0 = time.time()
    
    resolver = SourceResolverService(timeout=30.0)
    t1 = time.time()
    resolved = resolver.resolve_source(s.official_source_url, s.title)
    t2 = time.time()
    print(f"Source resolution: {t2-t1:.1f}s -> {resolved.resolved_url}")
    
    if resolved.resolved_url:
        discovery = ImageDiscoveryService(timeout=30.0, max_candidates=50)
        t3 = time.time()
        candidates = discovery.discover_from_scholarship(resolved.resolved_url)
        t4 = time.time()
        print(f"Discovery: {t4-t3:.1f}s, {len(candidates)} candidates")
        
        validator = ImageValidator(seen_images={}, timeout=30.0)
        t5 = time.time()
        results = validator.validate_candidates(candidates, s.title, resolved.resolved_url)
        t6 = time.time()
        print(f"Validation: {t6-t5:.1f}s")
        for r in results[:3]:
            print(f"  {r.status.value}: {r.candidate.image_url[:60]}...")
    
    total = time.time() - t0
    print(f"Total: {total:.1f}s")
    
finally:
    session.close()
    engine.dispose()
