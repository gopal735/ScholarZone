"""Run the image sweep until every valid scholarship has been evaluated.

Single pass over the catalogue, then repeats over whatever is still outstanding
until no unverified valid scholarship remains. Each pass is resumable, and a
record that keeps failing does not stop the loop: the driver stops only when a
whole pass adds nothing and every remaining record has a recorded outcome.
"""
from __future__ import annotations

import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.services.image_coverage_runner import ImageCoverageRunner

PERSIST = "--persist" in sys.argv
MAX_PASSES = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8
OUT = (
    r"C:\Users\GopaL\AppData\Local\Temp\kilo\image_complete.json"
)


def outstanding(factory) -> int:
    """Valid records that are neither verified nor terminally evaluated.

    A record that was evaluated and produced no trustworthy image is finished,
    not outstanding. Counting it as outstanding would make the sweep retry the
    same negative result forever and would report 100% coverage as impossible.
    """
    from sqlalchemy import func, select

    from app.models import Scholarship
    from app.services.image_evaluation_status import TERMINAL_STATUSES

    session = factory()
    try:
        return (
            session.scalar(
                select(func.count())
                .select_from(Scholarship)
                .where(Scholarship.image_verified_at.is_(None))
                .where(Scholarship.verification_status != "quarantined")
                .where(
                    Scholarship.image_evaluation_status.is_(None)
                    | Scholarship.image_evaluation_status.not_in(tuple(TERMINAL_STATUSES))
                )
            )
            or 0
        )
    finally:
        session.close()


def main() -> None:
    from app.services.image_discovery import clear_shared_page_cache

    factory = get_session_factory()
    all_outcomes: list[dict] = []
    totals: dict[str, int] = {}
    started = time.monotonic()

    for pass_no in range(1, MAX_PASSES + 1):
        remaining = outstanding(factory)
        print(f"\n=== pass {pass_no}: {remaining} valid records without a verified image ===", flush=True)
        if remaining == 0:
            print("catalogue complete", flush=True)
            break

        clear_shared_page_cache()
        runner = ImageCoverageRunner(
            factory,
            dry_run=not PERSIST,
            batch_size=25,
            max_workers=10,
            exclude_quarantined=True,
            skip_terminally_evaluated=True,
        )
        before = remaining
        metrics = runner.run()
        all_outcomes.extend(metrics.outcomes)
        for k, v in metrics.as_dict().items():
            if isinstance(v, int):
                totals[k] = totals.get(k, 0) + v

        after = outstanding(factory)
        print(
            f"pass {pass_no}: {before} -> {after} outstanding  "
            f"(accepted={metrics.newly_found} persisted={metrics.persisted} "
            f"blocked={metrics.source_blocked} no_image={metrics.no_official_image})",
            flush=True,
        )
        if after == before:
            print("pass added nothing; remaining records are recorded and not retried", flush=True)
            break

    final_remaining = outstanding(factory)
    print("\n" + "=" * 70)
    print(f"IMAGE SWEEP COMPLETE in {time.monotonic() - started:.0f}s  (mode: {'PERSIST' if PERSIST else 'DRY RUN'})")
    print("=" * 70)
    print(json.dumps(totals, indent=2))
    print(f"\nvalid scholarships still without a verified image: {final_remaining}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"totals": totals, "outcomes": all_outcomes}, fh, indent=2)
    print(f"outcomes -> {OUT}")


if __name__ == "__main__":
    main()
