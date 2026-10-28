"""Quick subset dry-run to measure before/after validator improvement."""
import sys, json, os
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.database import get_engine
from app.models import Scholarship
from app.services.image_discovery import ImageDiscoveryService
from app.services.image_validator import ImageValidator, ValidationStatus

engine = get_engine()
Session = sessionmaker(bind=engine)
session = Session()

rows = session.execute(select(Scholarship.id, Scholarship.title, Scholarship.official_source_url).limit(10)).all()
session.close()

results = []
for r in rows:
    resolver = None
    resolved_url = r.official_source_url
    # Simple resolution: use official_source_url as-is for this subset
    if not resolved_url:
        continue
    discovery = ImageDiscoveryService(timeout=20.0, max_candidates=20)
    try:
        candidates = discovery.discover_from_scholarship(resolved_url)
    except Exception as e:
        results.append({"id": r.id, "title": r.title, "candidates": 0, "decision": "error", "error": str(e)})
        continue
    
    validator = ImageValidator(timeout=20.0)
    try:
        vresults = validator.validate_candidates(candidates, scholarship_title=r.title, official_source_url=resolved_url)
        best = validator.find_best_result(vresults)
        if best:
            results.append({
                "id": r.id,
                "title": r.title,
                "candidates": len(candidates),
                "decision": best.status.value,
                "confidence": best.confidence,
                "relevance": best.relevance_score,
                "non_content_weight": best.non_content_total_weight,
                "signals": [s.label for s in best.non_content_signals],
            })
        else:
            results.append({"id": r.id, "title": r.title, "candidates": len(candidates), "decision": "rejected"})
    except Exception as e:
        results.append({"id": r.id, "title": r.title, "candidates": len(candidates), "decision": "error", "error": str(e)})

print(json.dumps(results, indent=2))

approved = sum(1 for r in results if r.get("decision") == "approved")
human_review = sum(1 for r in results if r.get("decision") == "human_review")
rejected = sum(1 for r in results if r.get("decision") == "rejected")
print(f"\nSubset metrics: APPROVED={approved} HUMAN_REVIEW={human_review} REJECTED={rejected} TOTAL={len(results)}")
