"""Persist enrichment results. Controlled: bounded, resumable, reports deltas."""
from __future__ import annotations

import json
import sys

from app.database import get_session_factory
from app.services.enrichment_runner import EnrichmentBatchRunner

PERSIST = "--persist" in sys.argv
BATCH = 15
args = [a for a in sys.argv[1:] if a != "--persist"]
LIMIT = int(args[0]) if args else None
START_AFTER = int(args[1]) if len(args) > 1 else None


def progress(done: int, total: int, result) -> None:
    changed = [u for u in result.updates if u.action in ("merged", "filled", "replaced")]
    if changed:
        names = ",".join(u.field_name for u in changed)
        print(f"[{done:4d}/{total}] * id={result.scholarship_id:<5d} {result.outcome.value:<20s} {names[:78]}", flush=True)
    else:
        print(f"[{done:4d}/{total}]   id={result.scholarship_id:<5d} {result.outcome.value}", flush=True)


def main() -> None:
    runner = EnrichmentBatchRunner(get_session_factory(), dry_run=not PERSIST, batch_size=BATCH)
    report = runner.run(limit=LIMIT, start_after=START_AFTER, progress=progress)
    payload = report.as_dict()
    payload["mode"] = "PERSIST" if PERSIST else "DRY RUN"
    print("\n" + "=" * 78)
    print(f"ENRICHMENT {'PERSIST' if PERSIST else 'DRY RUN'} REPORT")
    print("=" * 78)
    print(json.dumps({k: v for k, v in payload.items() if k != "failures"}, indent=2))
    print(f"\nfailures: {len(payload['failures'])}")


if __name__ == "__main__":
    main()
