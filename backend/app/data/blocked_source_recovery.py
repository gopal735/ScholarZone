"""Targeted recovery pass for official sources that refuse plain HTTP.

A whole-catalogue pass must not pay for a browser: launching Chromium costs
tens of seconds and only a small minority of records are actually blocked.
This driver therefore does one job, slowly and boundedly - take the records
whose official source could not be read, re-fetch each one in a real browser,
and enrich whatever comes back.

Every record it cannot unblock keeps the classification it already had. The
pass adds no facts of its own; it only changes which fetcher reads the page.

Run with --dry-run first. The pass is slow by nature: a browser render is
roughly thirty times the cost of an HTTP GET, which is why it is not folded
into the main enrichment run.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Scholarship
from app.services.headless_source_fetcher import HeadlessSourceFetcher
from app.services.scholarship_enrichment import (
    EnrichmentOutcome,
    ScholarshipEnrichmentService,
)

logger = logging.getLogger("blocked_recovery")


def blocked_candidates(factory, limit: int) -> list[tuple[int, str, str]]:
    """Records whose last known official page could not be read.

    Selection is by recorded image-evaluation outcome plus a missing deadline,
    because a record that already has a rich set of facts is not where an
    unblocked fetch would add the most.
    """
    session = factory()
    try:
        rows = session.scalars(
            select(Scholarship)
            .where(Scholarship.verification_status != "quarantined")
            .order_by(Scholarship.id)
        ).all()
        out: list[tuple[int, str, str]] = []
        for row in rows:
            blocked = row.image_evaluation_status == "source_blocked"
            url = (row.official_source_url or "").strip()
            if not blocked or not url:
                continue
            out.append((row.id, row.title or "", url))
            if len(out) >= limit:
                break
        return out
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persist", action="store_true", help="write changes to the database")
    parser.add_argument("--limit", type=int, default=25, help="max records this run")
    parser.add_argument("--timeout", type=int, default=25000, help="per-page browser timeout (ms)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    factory = get_session_factory()
    candidates = blocked_candidates(factory, args.limit)
    print(f"blocked-source candidates: {len(candidates)}")

    fetcher = HeadlessSourceFetcher(timeout_ms=args.timeout)
    if not fetcher.available():
        print("headless browser unavailable in this environment; nothing attempted")
        return 0

    recovered = failed = 0
    writes = 0
    started = time.monotonic()
    try:
        for index, (scholarship_id, title, url) in enumerate(candidates, 1):
            record_started = time.monotonic()
            rendered = fetcher.fetch(url)
            if not rendered.usable:
                failed += 1
                print(f"[{index}/{len(candidates)}] id={scholarship_id:<4} still blocked ({rendered.error})")
                continue
            service = ScholarshipEnrichmentService(
                session_factory=factory,
                dry_run=not args.persist,
                follow_related_pages=True,
                # The browser already rendered this page; letting the plain-HTTP
                # path retry it would only earn another 403.
                use_headless_fallback=False,
            )
            result = service.enrich_one(scholarship_id)
            changed = len(result.changed_fields)
            writes += changed
            if result.outcome is EnrichmentOutcome.ENRICHED or changed:
                recovered += 1
                print(
                    f"[{index}/{len(candidates)}] id={scholarship_id:<4} unblocked "
                    f"-> {changed} fields"
                )
            else:
                print(
                    f"[{index}/{len(candidates)}] id={scholarship_id:<4} readable, "
                    f"no new fields ({str(title)[:40]})"
                )
            print(f"    {time.monotonic() - record_started:.1f}s")
    finally:
        fetcher.close()

    runtime = time.monotonic() - started
    print(
        f"\nrecovered={recovered} still_blocked={failed} field_writes={writes} "
        f"runtime={runtime:.0f}s mode={'PERSIST' if args.persist else 'DRY RUN'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
