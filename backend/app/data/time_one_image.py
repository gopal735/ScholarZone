"""Time a single image-discovery record to find the bottleneck."""
from __future__ import annotations

import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from app.database import get_session_factory
from app.models import Scholarship
from app.services.image_discovery_orchestrator import ImageDiscoveryOrchestrator

sid = int(sys.argv[1]) if len(sys.argv) > 1 else 1

factory = get_session_factory()
session = factory()
row = session.get(Scholarship, sid)
print(f"id={sid} title={row.title[:60]!r}")
print(f"source={row.official_source_url}")
session.close()

orch = ImageDiscoveryOrchestrator(session_factory=factory, dry_run=True)
t0 = time.monotonic()
result = orch.run(
    scholarship_id=sid,
    scholarship_title=row.title,
    official_source_url=row.official_source_url,
    official_source_name=row.official_source,
)
elapsed = time.monotonic() - t0
print(f"\nelapsed={elapsed:.1f}s status={result.status.value} candidates={len(result.image_results)}")
print(f"requests_made={result.requests_made} error={result.error}")
for r in result.image_results:
    print(f"  [{r.confidence.value}] score={r.relevance_score:.2f} kind={r.image_kind}")
    print(f"    {r.image_url[:110]}")
    print(f"    page: {r.page_url[:110]}")
