"""Official-source verification/repair driver. Dry run by default; --persist writes."""
from __future__ import annotations

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.services.discovery_scheduler import DomainRateLimiter
from app.services.source_repair import (
    SourceQuality,
    SourceRepairService,
    iter_repair_candidates,
)

PERSIST = "--persist" in sys.argv
WORKERS = 8
args = [a for a in sys.argv[1:] if a != "--persist"]
LIMIT = int(args[0]) if args else None
START_AFTER = int(args[1]) if len(args) > 1 else None

OUT = r"C:\Users\GopaL\AppData\Local\Temp\kilo\source_repair_%s.json" % ("persist" if PERSIST else "dryrun")


def main() -> None:
    factory = get_session_factory()
    session = factory()
    ids = iter_repair_candidates(session, limit=LIMIT, start_after=START_AFTER)
    session.close()
    print(f"records to verify: {len(ids)}", flush=True)

    limiter = DomainRateLimiter(min_interval_seconds=1.0)

    def work(sid: int):
        svc = SourceRepairService(factory, dry_run=not PERSIST, rate_limiter=limiter)
        return svc.repair_one(sid)

    counts: Counter[str] = Counter()
    rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(work, sid): sid for sid in ids}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                r = fut.result()
            except Exception as exc:  # noqa: BLE001
                counts["crash"] += 1
                print(f"[{done:4d}/{len(ids)}] id={sid} CRASH {type(exc).__name__}: {exc}", flush=True)
                done += 1
                continue
            done += 1
            counts[r.quality.value] += 1
            if r.repaired or r.quality == SourceQuality.UNRESOLVED:
                rows.append(
                    {
                        "id": r.scholarship_id,
                        "quality": r.quality.value,
                        "from": r.original_url,
                        "to": r.new_url,
                        "reason": r.reason,
                        "evidence": r.evidence,
                        "status": r.status_code,
                    }
                )
                mark = "REPAIRED" if r.repaired else "UNRESOLVED"
                print(
                    f"[{done:4d}/{len(ids)}] {mark:10s} id={sid:<5d} {str(r.original_url)[:58]}",
                    flush=True,
                )
                if r.new_url:
                    print(f"{'':22s}-> {r.new_url[:96]}", flush=True)
                    print(f"{'':22s}   {r.reason[:92]}", flush=True)

    print("\n" + "=" * 78)
    print(f"SOURCE REPAIR {'PERSIST' if PERSIST else 'DRY RUN'} REPORT")
    print("=" * 78)
    total = sum(counts.values())
    for k, v in counts.most_common():
        print(f"  {k:<34s} {v:>4d}  ({100*v/total:5.1f}%)")
    print(f"  {'TOTAL':<34s} {total:>4d}")

    summary = {"mode": "persist" if PERSIST else "dry_run", "counts": dict(counts), "rows": rows}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\ndetails -> {OUT}")


if __name__ == "__main__":
    main()
