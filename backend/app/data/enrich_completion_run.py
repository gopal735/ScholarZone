"""Deep enrichment completion run over the valid catalogue.

Uses the multi-page engine, which follows same-domain eligibility / funding /
application / documents / FAQ links and merges whatever additional facts they
state. Prioritises the sparsest records so effort lands where it changes the
record most, then sweeps the rest.

Loops until a pass stops producing field writes, so a second pass is only used
to catch records the first pass could not reach.
"""
from __future__ import annotations

import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.services.enrichment_runner import EnrichmentBatchRunner

PERSIST = "--persist" in sys.argv
MAX_PASSES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3
SPARSE_FIRST = "--sparse" in sys.argv
OUT = r"C:\Users\GopaL\AppData\Local\Temp\kilo\enrich_complete.json"


def progress(done: int, total: int, result) -> None:
    changed = [u for u in result.updates if u.action in ("merged", "filled", "replaced")]
    real = [u for u in changed if u.field_name != "last_verified_at"]
    if real:
        print(
            f"[{done:4d}/{total}] id={result.scholarship_id:<5d} "
            f"{','.join(u.field_name for u in real)[:70]}",
            flush=True,
        )


def main() -> None:
    from app.services.official_source_fetcher import clear_official_source_cache

    factory = get_session_factory()
    ids = None
    if SPARSE_FIRST:
        from sqlalchemy import select

        from app.models import Scholarship
        from app.data.sparseness_rank import FACT_FIELDS

        session = factory()
        try:
            rows = session.scalars(
                select(Scholarship).where(Scholarship.verification_status != "quarantined")
            ).all()
            scored = []
            for row in rows:
                missing = sum(
                    1 for f in FACT_FIELDS if getattr(row, f, None) in (None, "", [])
                )
                scored.append((missing, row.id))
            scored.sort(key=lambda t: (-t[0], t[1]))
            ids = [sid for _n, sid in scored]
            print(f"prioritised {len(ids)} valid records, sparsest first", flush=True)
        finally:
            session.close()

    all_results: list[dict] = []
    totals: dict[str, int] = {}
    started = time.monotonic()

    for pass_no in range(1, MAX_PASSES + 1):
        print(f"\n=== enrichment pass {pass_no} ===", flush=True)
        clear_official_source_cache()
        runner = EnrichmentBatchRunner(
            factory, dry_run=not PERSIST, batch_size=20, max_attempts=2, max_workers=8
        )
        report = runner.run(ids=ids, progress=progress)
        for k, v in report.metrics.as_dict().items():
            if isinstance(v, int):
                totals[k] = totals.get(k, 0) + v
        for r in report.results:
            changed = [
                u.field_name
                for u in r.updates
                if u.action in ("merged", "filled", "replaced")
                and u.field_name != "last_verified_at"
            ]
            if changed:
                all_results.append(
                    {"id": r.scholarship_id, "fields": changed, "source": r.source_url}
                )

        content_writes = report.metrics.fields_updated
        print(
            f"pass {pass_no}: enriched={report.metrics.records_enriched} "
            f"field_writes={content_writes} "
            f"no_extraction={report.metrics.no_usable_extraction} "
            f"source_failures={report.metrics.source_failures}",
            flush=True,
        )
        if content_writes == 0:
            print("pass produced no content writes; stopping", flush=True)
            break
        # Second and later passes cover everything, not only the sparse list.
        ids = None

    print("\n" + "=" * 70)
    print(f"ENRICHMENT COMPLETE in {time.monotonic() - started:.0f}s  (mode: {'PERSIST' if PERSIST else 'DRY RUN'})")
    print("=" * 70)
    print(json.dumps(totals, indent=2))
    print(f"\nrecords with content field writes: {len(all_results)}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"totals": totals, "records": all_results}, fh, indent=2)
    print(f"details -> {OUT}")


if __name__ == "__main__":
    main()
