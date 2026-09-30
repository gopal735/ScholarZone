"""DRY RUN enrichment driver. Writes nothing; prints a real report."""
from __future__ import annotations

import json
import sys

from app.database import get_session_factory
from app.services.enrichment_runner import EnrichmentBatchRunner

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 20
START_AFTER = int(sys.argv[2]) if len(sys.argv) > 2 else None


def progress(done: int, total: int, result) -> None:
    changed = [u for u in result.updates if u.action in ("merged", "filled", "replaced")]
    flag = "*" if changed else " "
    print(
        f"[{done:4d}/{total}] {flag} id={result.scholarship_id:<5d} {result.outcome.value:<22s} "
        f"changes={len(changed):<3d} fields={','.join(u.field_name for u in changed)[:70]}",
        flush=True,
    )
    if result.fetch_error:
        print(f"        error: {result.fetch_error[:110]}", flush=True)


def main() -> None:
    runner = EnrichmentBatchRunner(get_session_factory(), dry_run=True, batch_size=10)
    report = runner.run(limit=LIMIT, start_after=START_AFTER, progress=progress)

    print("\n" + "=" * 78)
    print("DRY RUN ENRICHMENT REPORT")
    print("=" * 78)
    print(json.dumps(report.metrics.as_dict(), indent=2))

    print("\n--- SAMPLE OF PROPOSED CHANGES (first 12 enriched records) ---")
    shown = 0
    for r in report.results:
        changed = [u for u in r.updates if u.action in ("merged", "filled", "replaced")]
        if not changed or shown >= 12:
            continue
        shown += 1
        print(f"\nid={r.scholarship_id}  source={r.source_url}")
        print(f"   source_type={r.source_type} status->{r.new_status}")
        for u in changed[:6]:
            sample = "; ".join(u.added_items)[:150]
            print(f"   [{u.action:8s}] {u.field_name:24s} {u.reason[:44]}")
            if sample:
                print(f"             + {sample}")

    print("\n--- FAILURES ---")
    for f in report.failures()[:12]:
        print(f"  id={f.scholarship_id} attempts={f.fetch_attempts} retryable={f.retryable}")
        print(f"     {f.source_url}")
        print(f"     {str(f.fetch_error)[:110]}")


if __name__ == "__main__":
    main()
