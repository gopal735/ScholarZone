"""Official image coverage driver. Dry run by default; --persist writes."""
from __future__ import annotations

import json
import sys

from app.database import get_session_factory
from app.services.image_coverage_runner import ImageCoverageRunner

PERSIST = "--persist" in sys.argv
BATCH = 8
args = [a for a in sys.argv[1:] if a != "--persist"]
LIMIT = int(args[0]) if args else None


def progress(done: int, total: int, result) -> None:
    mark = "+" if result.image_results else " "
    print(
        f"[{done:4d}/{total}] {mark} id={result.scholarship_id:<5d} "
        f"{result.status.value:<20s} cand={len(result.image_results)} "
        f"{(result.image_results[0].image_url[:64] if result.image_results else '')}",
        flush=True,
    )
    if result.error:
        print(f"        error: {result.error[:100]}", flush=True)


def main() -> None:
    runner = ImageCoverageRunner(
        get_session_factory(),
        dry_run=not PERSIST,
        batch_size=BATCH,
    )
    metrics = runner.run(limit=LIMIT, progress=progress)

    print("\n" + "=" * 78)
    print("OFFICIAL IMAGE COVERAGE REPORT" + ("  (PERSISTING)" if PERSIST else "  (DRY RUN)"))
    print("=" * 78)
    summary = metrics.as_dict()
    print(json.dumps(summary, indent=2))

    found = [o for o in metrics.outcomes if o["candidates"] > 0]
    print(f"\n--- RECORDS WITH A CANDIDATE ({len(found)}) ---")
    for o in found[:40]:
        print(f"  id={o['scholarship_id']:<5d} {o['status']:<10s} {str(o['title'])[:44]}")
        print(f"        {str(o['image_url'])[:104]}")

    errs = [o for o in metrics.outcomes if o["status"] in ("error", "skipped")]
    print(f"\n--- ERRORS ({len(errs)}) ---")
    for o in errs[:25]:
        print(f"  id={o['scholarship_id']:<5d} {str(o['error'])[:100]}")

    with open(_out_path(), "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "outcomes": metrics.outcomes}, fh, indent=2)
    print(f"\nfull outcome dump written to {_out_path()}")


def _out_path() -> str:
    import tempfile
    name = "image_coverage_persist.json" if PERSIST else "image_coverage_dryrun.json"
    return f"{tempfile.gettempdir()}\\{name}"


if __name__ == "__main__":
    main()
