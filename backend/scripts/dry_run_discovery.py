#!/usr/bin/env python3
"""5-country dry-run for automatic scholarship discovery scheduler.

Uses an isolated in-memory database. No production data is touched.
Reports discovery metrics without inserting scholarships.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import datetime, timezone

# Ensure test isolation
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, ApprovedSource, Scholarship
from app.services.discovery_config import seed_approved_sources
from app.services.discovery_scheduler import DiscoveryScheduler

COUNTRIES_TO_TEST = ["Germany", "France", "USA", "Japan", "South Korea"]


def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    session = session_factory()
    try:
        seed_approved_sources(session)
        session.commit()

        for country in COUNTRIES_TO_TEST:
            session.add(
                Scholarship(
                    title=f"Existing {country} Scholarship",
                    country=country,
                    degree="Masters",
                    funding="Full",
                    official_source_url=f"https://example.com/{country.lower()}/scholarship",
                )
            )
        session.commit()
    finally:
        session.close()

    print("=" * 70)
    print("SCHOLARZONE DISCOVERY SCHEDULER — 5-COUNTRY DRY-RUN")
    print("=" * 70)
    print(f"Database  : temp-file SQLite (isolated)")
    print(f"Mode      : DRY-RUN (no DB writes)")
    print(f"Countries : {', '.join(COUNTRIES_TO_TEST)}")
    print(f"Started   : {datetime.now(timezone.utc).isoformat()}")
    print("-" * 70)

    scheduler = DiscoveryScheduler(
        session_factory=session_factory,
        dry_run=True,
        max_workers=2,
    )

    start = time.monotonic()
    metrics = scheduler.run()
    elapsed = (time.monotonic() - start) * 1000.0

    print(f"Completed : {datetime.now(timezone.utc).isoformat()}")
    print(f"Runtime   : {elapsed:.1f} ms")
    print("-" * 70)
    print("RESULTS")
    print("-" * 70)
    print(f"Countries scanned       : {metrics.countries_scanned}")
    print(f"Sources checked         : {metrics.sources_checked}")
    print(f"URLs checked            : {metrics.urls_checked}")
    print(f"Discovery candidates    : {metrics.discovery_candidates}")
    print(f"Verified new scholarships: {metrics.verified_new_scholarships}")
    print(f"Expected new inserts    : {metrics.inserted_scholarships}")
    print(f"Duplicates              : {metrics.duplicates}")
    print(f"Rejected candidates     : {metrics.rejected_candidates}")
    print(f"Errors                  : {metrics.errors}")
    print(f"Image discoveries triggered: {metrics.image_discoveries_triggered}")
    print(f"Images HIGH (auto-persist): {metrics.image_high}")
    print(f"Images MEDIUM (HUMAN_REVIEW): {metrics.image_medium}")
    print(f"Images LOW (rejected)   : {metrics.image_low}")
    print(f"Image reviews created   : {metrics.image_review}")
    print(f"Temp/network failures   : {metrics.temp_failures}")
    print(f"Network failures        : {metrics.network_failures}")
    print("-" * 70)
    print("COUNTRY BREAKDOWN")
    print("-" * 70)
    for country, result in metrics.country_results.items():
        status = result.get("status", "unknown")
        discovered = result.get("discovered", 0)
        duplicates = result.get("duplicates", 0)
        rejected = result.get("rejected", 0)
        errors = result.get("errors", 0)
        net_failures = result.get("network_failures", 0)
        print(
            f"  {country:20s} | {status:6s} | discovered={discovered:3d} | "
            f"duplicates={duplicates:3d} | rejected={rejected:3d} | errors={errors:3d} | "
            f"net_failures={net_failures:3d}"
        )
    print("=" * 70)
    print("DRY-RUN COMPLETE — NO PRODUCTION DATA MODIFIED")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
