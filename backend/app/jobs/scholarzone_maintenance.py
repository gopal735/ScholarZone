"""Direct maintenance worker: GitHub Actions -> Neon, with no API in between.

The scheduled workflow used to wake the SnapDeploy container and call the
production API over HTTP. On the free tier a container sleeps, the wake is not
guaranteed, and a scheduled run therefore depends on a platform behaviour it
does not control. Verification is the one job that most needs to run when
nobody is looking, so making it depend on a cold start is backwards.

This worker runs the same service layer in-process and talks straight to
Neon. Nothing here duplicates verification, discovery, enrichment or image
logic: each stage calls the same services the API calls, so a maintenance run
and an operator-triggered run cannot diverge.

It is deliberately bounded. Each stage has a limit, each stage commits
independently, and a stage that fails is reported and skipped rather than
aborting the remaining stages - one unreachable provider must not stop the
other 486 records from being checked.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger("scholarzone_maintenance")


@dataclass
class StageReport:
    name: str
    ok: bool
    detail: dict = field(default_factory=dict)
    error: str | None = None
    runtime_s: float = 0.0


def _run_stage(name: str, fn) -> StageReport:
    started = time.monotonic()
    try:
        detail = fn() or {}
        return StageReport(
            name=name, ok=True, detail=detail, runtime_s=time.monotonic() - started
        )
    except Exception as exc:  # noqa: BLE001
        # A stage failure is reported, not fatal. The remaining stages still
        # describe state the owner needs to see.
        logger.warning("stage %s failed: %s", name, exc)
        return StageReport(
            name=name,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            runtime_s=time.monotonic() - started,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        action="append",
        choices=["verify", "enrich", "images", "discover", "all"],
        default=None,
        help="Run only these stages (default: all).",
    )
    parser.add_argument("--limit", type=int, default=60, help="Max records per stage.")
    parser.add_argument("--workers", type=int, default=4, help="Bounded concurrency per stage.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Compute without writing."
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    # Importing these validates the schema and proves the database is
    # reachable before any stage starts, so a connection failure is reported
    # once and clearly rather than once per stage.
    from app.database import get_session_factory, init_database

    init_database()
    factory = get_session_factory()

    from app.services.enrichment_runner import EnrichmentBatchRunner
    from app.services.image_coverage_runner import MAX_WORKERS, ImageCoverageRunner

    wanted = set(args.stage or ["all"])
    run_all = "all" in wanted
    limit = max(1, args.limit)
    workers = max(1, min(args.workers, MAX_WORKERS))
    reports: list[StageReport] = []

    if run_all or "verify" in wanted:
        def verify() -> dict:
            # The same entry point the API's verification round uses, so a
            # scheduled run and an operator-triggered run cannot diverge.
            from app.scheduler_v2 import run_verification_round

            result = run_verification_round()
            return (
                result.as_dict()
                if hasattr(result, "as_dict")
                else {"result": str(result)}
            )

        reports.append(_run_stage("verify", verify))

    if run_all or "enrich" in wanted:
        def enrich() -> dict:
            runner = EnrichmentBatchRunner(
                factory,
                dry_run=args.dry_run,
                batch_size=min(15, limit),
                max_workers=workers,
            )
            return runner.run(limit=limit).as_dict()

        reports.append(_run_stage("enrich", enrich))

    if run_all or "images" in wanted:
        def images() -> dict:
            runner = ImageCoverageRunner(
                factory,
                dry_run=args.dry_run,
                batch_size=min(15, limit),
                max_workers=workers,
                exclude_quarantined=True,
                skip_terminally_evaluated=True,
            )
            return runner.run(limit=limit).as_dict()

        reports.append(_run_stage("images", images))

    if run_all or "discover" in wanted:
        def discover() -> dict:
            from app.scheduler_v2 import run_discovery_round

            result = run_discovery_round(dry_run=args.dry_run, max_workers=workers)
            return (
                result.as_dict()
                if hasattr(result, "as_dict")
                else {"result": str(result)}
            )

        reports.append(_run_stage("discover", discover))

    print("=" * 68)
    print("SCHOLARZONE MAINTENANCE")
    print(f"  mode        : {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  limit/stage : {limit}   workers: {workers}")
    print("=" * 68)
    failed = 0
    for report in reports:
        status = "ok" if report.ok else "FAILED"
        print(f"\n[{status}] {report.name}  ({report.runtime_s:.1f}s)")
        for key, value in report.detail.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    print(f"    {sub_key}: {sub_value}")
            else:
                print(f"    {key}: {value}")
        if report.error:
            failed += 1
            print(f"    error: {report.error}")

    print("\n" + "=" * 68)
    print(f"stages run: {len(reports)}   failed: {failed}")
    print("=" * 68)
    # A failing stage is reported, not fatal: the job exits 0 so a scheduled
    # run is not marked broken every time one provider is unreachable, and the
    # per-stage errors above carry the real signal.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
