"""Re-run official image discovery for records whose candidates were all rejected.

A record that reached a reachable official page, found candidates, and rejected
all of them has already proven the page is readable. Running the bounded
coverage pass again is therefore cheap and can succeed where the first attempt
failed: a transient failure while fetching the page, a candidate that only
loaded after JavaScript, or a page whose metadata changed since the last sweep.

This does not weaken any acceptance rule. The same validator decides, the same
provenance is required, and a record that legitimately publishes no usable
image still ends as a terminal negative. The pass exists so "all candidates
rejected" is retried a bounded number of times rather than being accepted as a
permanent answer on the first try.
"""

from __future__ import annotations

import logging
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Scholarship
from app.services.image_coverage_runner import MAX_WORKERS, ImageCoverageRunner

PERSIST = "--persist" in sys.argv
LIMIT = 200

logging.basicConfig(level=logging.WARNING, format="%(message)s")


def main() -> int:
    factory = get_session_factory()
    session = factory()
    try:
        targets = list(
            session.scalars(
                select(Scholarship)
                .where(Scholarship.image_evaluation_status == "invalid_candidates")
                .order_by(Scholarship.id)
            )
        )
    finally:
        session.close()

    print(f"records with rejected candidates: {len(targets)}")
    if not targets:
        return 0

    runner = ImageCoverageRunner(
        factory,
        dry_run=not PERSIST,
        batch_size=10,
        max_workers=min(MAX_WORKERS, 6),
        exclude_quarantined=True,
        # These records already have a terminal outcome, so the default scope
        # would skip every one of them. The point of this pass is to revisit
        # exactly those.
        skip_terminally_evaluated=False,
    )
    report = runner.run(limit=min(len(targets), LIMIT))
    # ImageCoverageRunner.run returns the metrics object itself.
    metrics = report.as_dict() if hasattr(report, "as_dict") else report
    print(
        f"scanned={metrics.get('records_scanned')} "
        f"fetched={metrics.get('records_fetched')} "
        f"found={metrics.get('images_found')} "
        f"blocked={metrics.get('source_blocked')} "
        f"runtime={metrics.get('runtime_ms', 0) / 1000:.0f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
