"""Direct maintenance worker: GitHub Actions -> Neon, with no API in between.

The scheduled workflow used to wake the SnapDeploy container and call the
production API over HTTP. On the free tier a container sleeps, the wake is not
guaranteed, and a scheduled run therefore depended on a platform behaviour it
does not control. Verification is the one job that most needs to run when
nobody is looking, so making it depend on a cold start is backwards.

This worker runs the same service layer in-process and talks straight to
Neon. Nothing here duplicates verification, discovery, enrichment or image
logic: each stage calls the same services the API calls, so a maintenance run
and an operator-triggered run cannot diverge.

Design rules this file follows, and why
---------------------------------------

**Enrichment advances.** The old selection was ``ORDER BY id LIMIT n`` with no
cursor, so every twelve-hour run re-enriched the same first records forever
and the tail of the catalogue was never reached. The enrich stage now takes
its batch from :class:`MaintenanceCursorStore`, a durable round-robin cursor in
the same database. See ``app/services/maintenance_cursor.py``.

**Failures are honest.** The old worker caught every stage exception, printed
it, and returned 0. GitHub therefore recorded a green run while the stage had
in fact failed. Now a stage failure makes the process exit non-zero, so a
broken verification round can never be reported as a successful workflow.
Per-record source failures are still data outcomes, not stage failures: an
unreachable provider is counted in metrics and does not fail the run.

**Expensive work waits for its prerequisite.** Enrichment, image coverage and
discovery all act on records that verification owns. If verification failed,
running them anyway would spend the free-tier fetch budget on records whose
freshness nobody has established, so they are skipped and reported as skipped.

**Nothing here is unbounded.** Every stage has a limit, a worker cap, and its
own transaction boundary. Sessions are opened and closed per unit of work and
no connection is held for the life of the process.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger("scholarzone_maintenance")

# Exit codes. Distinct values make a failure class obvious in the Actions log
# without having to read the whole summary.
EXIT_OK = 0
EXIT_STAGE_FAILED = 1
EXIT_FATAL = 2

# Bounded by construction, and named so the bounds are part of the contract
# rather than a literal buried in an argument parser.
DEFAULT_STAGE_LIMIT = 60
MAX_STAGE_WORKERS = 16

# Stage order reflects dependencies: verification establishes which records
# are current, and the remaining stages all operate on that outcome.
STAGE_ORDER = ("verify", "enrich", "images", "logos", "discover", "quarantine", "stats", "facts", "purge")

# A stage that fails stops the stages that depend on it, but not the ones that
# do not. Verification has no prerequisite and nothing gates it.
#
# `quarantine` deliberately does NOT depend on `enrich`.
#
# It used to, so that a record could not be judged structurally empty until
# enrichment had tried to fill it. That coupling had a worse failure mode than
# the one it avoided: quarantine inherits the *enrichment* cursor, so a record
# the enrichment sweep had not yet reached - including anything discovered
# today - was never assessed, and the safety gate silently had a hole exactly
# where new records arrive.
#
# The two concerns are now separated by time rather than by dependency.
# Quarantine runs on its own cursor, makes no network call, and costs a
# fraction of a second per batch, so it can safely sweep the whole valid
# catalogue every cycle regardless of where enrichment happens to be. Enrichment
# only ever fills fields on an existing record; a record that has never been
# enriched is a record that has more fields empty, and quarantine's own three
# independent signals - not field emptiness alone - decide.
STAGE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "verify": (),
    "enrich": ("verify",),
    "images": ("verify",),
    "discover": ("verify",),
    "quarantine": (),
    "stats": (),
    "facts": (),
    "logos": (),
    "purge": (),
}


@dataclass
class StageReport:
    name: str
    ok: bool
    detail: dict = field(default_factory=dict)
    error: str | None = None
    runtime_s: float = 0.0
    skipped: bool = False
    skip_reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "runtime_s": round(self.runtime_s, 3),
            "error": self.error,
            "detail": self.detail,
        }


def _issuer_kind(host: str, alt_text: str | None = None) -> str:
    """Classify which kind of body serves a logo.

    Recorded on the image so a card can state whether the mark belongs to a
    government, a university or a foundation. The host is consulted first
    because it is provenance we can actually verify; the alt text is a fallback
    for universities on national academic domains, where the TLD carries no
    signal at all - ``ut.ee``, ``lu.lv`` and ``hi.is`` are universities, and no
    host pattern can tell that.

    An issuer that cannot be classified falls back to official_logo, which is
    the honest answer: it is a logo, just not attributed more precisely.
    """
    if any(token in host for token in (".gov", "-gov.", "europa.eu", "un.org", "au.int")):
        return "official_government"
    if any(token in host for token in (".edu", ".ac.", "university", "unibe", "hochschule")):
        return "official_university"
    label = (alt_text or "").lower()
    if any(token in label for token in ("university", "universität", "universitat", "univ.")):
        return "official_university"
    return "official_logo"


def _run_stage(name: str, fn) -> StageReport:
    """Execute one stage in isolation, capturing its outcome.

    Isolation is deliberate and is about *per-record* resilience: a stage
    handles its own records, so an exception escaping here means something
    structural broke (the database, a missing table, a bad import), not that
    one provider was down. The exception is still captured so the remaining
    stages can report, but it now drives a non-zero exit.
    """
    started = time.monotonic()
    try:
        detail = fn() or {}
        return StageReport(
            name=name, ok=True, detail=detail, runtime_s=time.monotonic() - started
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("stage %s failed: %s", name, exc, exc_info=True)
        return StageReport(
            name=name,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            runtime_s=time.monotonic() - started,
        )


def _skipped(name: str, reason: str) -> StageReport:
    return StageReport(name=name, ok=False, skipped=True, skip_reason=reason)


def _quarantine_ids(factory, ids: list[int], *, dry_run: bool) -> int:
    """Assess specific ids now and quarantine the ones that are not programmes.

    Used twice: on the ids discovery just created, and by the routine sweep over
    the cursor. One short transaction, nothing deleted, and every decision is
    written to the review queue by the service itself.
    """
    if not ids:
        return 0
    from app.services.catalogue_quarantine import quarantine_record

    quarantined = 0
    session = factory()
    try:
        for scholarship_id in ids:
            verdict = quarantine_record(session, scholarship_id, dry_run=dry_run)
            if verdict.is_non_scholarship:
                quarantined += 1
        if not dry_run:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return quarantined


class FatalError(RuntimeError):
    """Unrecoverable problem: the run cannot meaningfully continue."""


# Failure classification, used by the workflow's bounded retry.
#
# A retry is only ever worth it for something that might be different next
# time. Retrying a missing secret, a bad import or a schema mismatch just burns
# runner minutes to arrive at the same error, so those are never retried.
TRANSIENT_PATTERNS = (
    "connection refused",
    "connection reset",
    "connection aborted",
    "could not connect",
    "server closed the connection",
    "operationalerror",
    "ssl",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "bad gateway",
    "service unavailable",
    "eof occurred",
    "name resolution",
    "temporary failure in name resolution",
    "network is unreachable",
    "packet loss",
    "502",
    "503",
    "504",
)

FATAL_PATTERNS = (
    "scholarzone_database_url is required",
    "requires a postgresql",
    "cannot import",
    "imports failed",
    "invalid configuration",
    "database initialisation failed",
    "no such table",
    "undefined column",
    "relation does not exist",
    "already exists",
    "syntaxerror",
    "indentationerror",
    "modulenotfounderror",
    "importerror",
)


def classify_failure(message: str | None) -> str:
    """Classify a failure as ``transient``, ``fatal`` or ``unknown``.

    Checked in order: fatal first, because a message that looks like a
    connectivity problem but names a missing table is a schema failure, and
    retrying that only delays the real error.
    """
    if not message:
        return "unknown"
    text = message.lower()
    for pattern in FATAL_PATTERNS:
        if pattern in text:
            return "fatal"
    for pattern in TRANSIENT_PATTERNS:
        if pattern in text:
            return "transient"
    return "unknown"


def emit_failure_classification(reports) -> dict[str, list[str]]:
    """Print a classification block the workflow can read.

    GitHub Actions cannot branch on log text, so the workflow simply retries on
    any non-zero exit. The classification exists so a human reading a failed run
    can tell immediately whether waiting would have helped.
    """
    buckets: dict[str, list[str]] = {"transient": [], "fatal": [], "unknown": []}
    for report in reports:
        if report.ok or report.skipped or not report.error:
            continue
        buckets[classify_failure(report.error)].append(report.name)
    print("\n--- failure classification ---")
    for kind, names in buckets.items():
        if names:
            print(f"  {kind:<10} {', '.join(names)}")
    return buckets


def _require_production_database(settings) -> None:
    """Refuse to run maintenance against anything but Neon.

    The config layer already rejects SQLite in production, but this is the
    stage where a silent fallback to the wrong database would be most
    expensive, and the check is cheap and absolute. Extracted so it can be
    tested without a live database.
    """
    if settings.environment != "production":
        return
    if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise FatalError(
            "production maintenance requires a PostgreSQL (Neon) database URL; "
            f"resolved dialect is not PostgreSQL (environment={settings.environment})"
        )


def _preflight() -> tuple:
    """Connect to the database and import the service layer, or fail hard.

    Doing this before any stage means a missing secret, an unreachable Neon
    instance, or a broken import is reported once, clearly, as a fatal
    configuration problem - instead of appearing as four identical stage
    failures that look like a bad database and are actually a bad import.
    """
    try:
        from app.core.config import get_settings
    except Exception as exc:  # noqa: BLE001
        raise FatalError(f"cannot import app.core.config: {exc}") from exc

    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001
        # The message from the config layer deliberately does not include the
        # URL, and neither do we.
        raise FatalError(f"invalid configuration: {exc}") from exc

    try:
        _require_production_database(settings)
    except FatalError as exc:
        raise FatalError(str(exc)) from exc

    try:
        from app.database import get_session_factory, init_database

        init_database()
        factory = get_session_factory()
    except Exception as exc:  # noqa: BLE001
        raise FatalError(f"database initialisation failed: {exc}") from exc

    try:
        from app.services.enrichment_runner import EnrichmentBatchRunner  # noqa: F401
        from app.services.image_coverage_runner import MAX_WORKERS, ImageCoverageRunner  # noqa: F401
        from app.services.maintenance_cursor import MaintenanceCursorStore
        from app.services.maintenance_run_log import MaintenanceRunRecorder
    except Exception as exc:  # noqa: BLE001
        raise FatalError(f"worker service imports failed: {exc}") from exc

    return factory, MaintenanceCursorStore, MaintenanceRunRecorder, MAX_WORKERS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        action="append",
        choices=["verify", "enrich", "images", "logos", "discover", "quarantine", "stats", "facts", "purge", "all"],
        default=None,
        help="Run only these stages (default: all).",
    )
    parser.add_argument(
        "--image-budget-seconds",
        type=float,
        default=None,
        help=(
            "Per-record wall clock for image discovery. Lower it for a fast "
            "catalogue sweep: blocked hosts then fail quickly instead of "
            "consuming the full default budget on every record."
        ),
    )
    parser.add_argument(
        "--logo-only",
        action="store_true",
        help=(
            "images stage: persist only official identity marks (logo, emblem, "
            "crest) and clear a stored programme photo rather than keeping it."
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_STAGE_LIMIT, help="Max records per stage."
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="Bounded concurrency per stage."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Compute without writing."
    )
    parser.add_argument(
        "--crawl-depth",
        type=int,
        default=0,
        help=(
            "Discovery crawl depth below each seed URL. 0 keeps the historical "
            "behaviour of fetching each seed once without following links. "
            "2 is the recommended value for a deep research round."
        ),
    )
    parser.add_argument(
        "--crawl-pages-per-seed",
        type=int,
        default=12,
        help="Maximum pages visited per discovery seed, including the seed.",
    )
    parser.add_argument(
        "--crawl-max-pages",
        type=int,
        default=600,
        help="Batch-wide ceiling on crawled pages, so one portal cannot starve the rest.",
    )
    parser.add_argument(
        "--quarantine-ids",
        default="",
        help=(
            "Comma-separated scholarship ids to assess and quarantine now, then "
            "exit. For records created by a run that has already finished, where "
            "the routine cursor would not reach them for dozens of cycles."
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    try:
        factory, CursorStore, RunRecorder, MAX_WORKERS = _preflight()
    except FatalError as exc:
        kind = classify_failure(str(exc))
        print("=" * 68)
        print("SCHOLARZONE MAINTENANCE - FATAL")
        print(f"  {exc}")
        print(f"  classification: {kind}")
        print("=" * 68)
        return EXIT_FATAL

    limit = max(1, args.limit)
    workers = max(1, min(args.workers, MAX_STAGE_WORKERS, MAX_WORKERS))

    # Targeted quarantine of explicit ids, handled before any stage so it is a
    # cheap single-purpose command rather than something that also runs a
    # verification or image pass over the catalogue.
    if args.quarantine_ids.strip():
        ids = [int(p) for p in args.quarantine_ids.split(",") if p.strip().isdigit()]
        if not ids:
            print("::error::--quarantine-ids did not contain any valid ids.")
            return EXIT_FATAL
        print("=" * 68)
        print("SCHOLARZONE TARGETED QUARANTINE")
        print(f"  ids: {', '.join(str(i) for i in ids)}")
        print("=" * 68)
        try:
            quarantined = _quarantine_ids(factory, ids, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001
            print(f"  error: {type(exc).__name__}: {exc}")
            print(f"  classification: {classify_failure(str(exc))}")
            return EXIT_STAGE_FAILED
        print(f"  assessed: {len(ids)}")
        print(f"  quarantined: {quarantined}")
        print(f"  not_quarantined: {len(ids) - quarantined}")
        # Per-id reasons. A targeted run exists to explain a specific decision:
        # "not_quarantined: 1" on its own leaves the reader with nothing to act
        # on, and re-deriving why a record survived means repeating the fetch.
        try:
            from app.models import Scholarship
            from app.services.catalogue_quarantine import assess_record

            session = factory()
            try:
                for scholarship_id in ids:
                    record = session.get(Scholarship, scholarship_id)
                    if record is None:
                        print(f"  {scholarship_id}: not found")
                        continue
                    verdict = assess_record(record)
                    state = "QUARANTINED" if verdict.is_non_scholarship else "kept"
                    print(f"  {scholarship_id}: {state}  title={record.title!r}")
                    for reason in verdict.reasons:
                        print(f"      - {reason[:160]}")
                    if not verdict.reasons:
                        print("      - (no signals: fewer than three, and not corrupt)")
            finally:
                session.close()
        except Exception:  # noqa: BLE001 - diagnostics must never fail the run
            logger.warning("could not print quarantine reasons", exc_info=True)
        return EXIT_OK

    store = CursorStore(factory)
    recorder = RunRecorder(factory, dry_run=args.dry_run)
    recorder.open()

    wanted = set(args.stage or ["all"])
    run_all = "all" in wanted
    selected = [s for s in STAGE_ORDER if run_all or s in wanted]

    # Import the runners once, after preflight has proven they load.
    from app.services.enrichment_runner import EnrichmentBatchRunner
    from app.services.image_coverage_runner import ImageCoverageRunner
    from app.scheduler_v2 import run_discovery_round, run_verification_round

    def do_stats() -> dict:
        """Print exact production catalogue totals. Read-only, no writes."""
        from urllib.parse import urlparse

        from sqlalchemy import func, select

        from app.models import Scholarship
        from app.services.catalogue_quarantine import QUARANTINE_STATUS
        from app.services.image_discovery_orchestrator import LOGO_IDENTITY_KINDS

        session = factory()
        try:
            total = session.scalar(select(func.count()).select_from(Scholarship))
            valid = session.scalar(
                select(func.count())
                .select_from(Scholarship)
                .where(Scholarship.verification_status != QUARANTINE_STATUS)
            )
            quarantined = session.scalar(
                select(func.count())
                .select_from(Scholarship)
                .where(Scholarship.verification_status == QUARANTINE_STATUS)
            )

            # Coverage, not just totals. A total says how big the catalogue is;
            # only these say whether it is usable, which is the question the
            # image and enrichment work is actually trying to answer.
            def _count_where(*conditions) -> int:
                return session.scalar(
                    select(func.count()).select_from(Scholarship).where(*conditions)
                )

            with_image = _count_where(Scholarship.image_url.isnot(None))
            identity_marks = _count_where(
                Scholarship.image_kind.in_(sorted(LOGO_IDENTITY_KINDS))
            )
            non_logo = _count_where(
                Scholarship.image_url.isnot(None),
                Scholarship.image_kind.not_in(sorted(LOGO_IDENTITY_KINDS)),
            )
            coverage = {
                f"missing_{field}": _count_where(getattr(Scholarship, field).is_(None))
                for field in (
                    "description", "eligibility", "funding", "degree",
                    "deadline_date", "benefits", "official_source",
                    "application_link",
                )
            }

            # Which hosts are actually blocking logo coverage. Coverage is a
            # per-host problem, not a per-record one: a missing logo almost
            # always means the awarding body's site is unreachable or has no
            # published logo file, and that is the list worth researching and
            # curating against.
            gap_rows = session.execute(
                select(Scholarship.official_source_url)
                .where(Scholarship.image_url.is_(None))
            ).all()
            host_counts: dict[str, int] = {}
            for (url,) in gap_rows:
                host = (urlparse(url or "").hostname or "").lower()
                host = host[4:] if host.startswith("www.") else host
                if host:
                    host_counts[host] = host_counts.get(host, 0) + 1
            top_hosts = sorted(host_counts.items(), key=lambda kv: (-kv[1], kv[0]))
            return {
                "total_records": total,
                "total_valid": valid,
                "quarantined": quarantined,
                "with_image": with_image,
                "without_image": total - with_image,
                "identity_marks": identity_marks,
                "non_logo_images_remaining": non_logo,
                **coverage,
                "distinct_hosts_needing_logo": len(top_hosts),
                "top_hosts_needing_logo": top_hosts,
            }
        finally:
            session.close()

    def do_verify() -> dict:
        # Same entry point the API's verification round uses, so a scheduled
        # run and an operator-triggered run cannot diverge.
        result = run_verification_round(dry_run=args.dry_run)
        return result.as_dict() if hasattr(result, "as_dict") else {"result": str(result)}

    def do_enrich() -> dict:
        # Cursor-driven: each run takes the next slice of the catalogue rather
        # than the same first slice forever.
        batch = store.select_batch("enrich", limit=limit, skip_complete=not args.dry_run)
        if batch.is_empty:
            return {"selected": 0, **store.state_as_dict("enrich")}
        runner = EnrichmentBatchRunner(
            factory,
            dry_run=args.dry_run,
            batch_size=min(15, limit),
            max_workers=workers,
        )
        report = runner.run(ids=batch.ids)
        # Advance only after the work has actually run. If this stage raises,
        # the cursor stays put and the same batch is re-selected next run
        # rather than being silently skipped.
        if not args.dry_run:
            store.advance("enrich", batch)
        detail = report.as_dict()
        detail["cursor"] = batch.as_dict()
        recorder.record_counts(
            {
                "enrich_records_scanned": report.metrics.records_scanned,
                "enrich_fields_updated": report.metrics.fields_updated,
                "enrich_source_failures": report.metrics.source_failures,
            }
        )
        return detail

    def do_logos() -> dict:
        """Attach audited official logos by exact official-source host.

        The images stage discovers logos by crawling, which is correct but slow:
        a record whose site blocks us burns its whole per-record budget before
        giving up, so a catalogue-wide sweep takes hours.

        The override file is the fast path for the institutions we already know.
        Every entry was probed live and confirmed to be image bytes served by the
        institution's own host, and it is keyed on the record's exact official
        source host, so a record cannot pick up another body's artwork.

        It still does not skip the honesty rules. The recorded provenance says
        exactly which page the bytes came from and whether the host is official,
        so a `official_host: false` entry is stored as third-party rather than
        quietly promoted. Only records with no image are touched: an existing
        verified identity mark is never replaced by a different one.
        """
        from urllib.parse import urlparse

        from app.services.image_discovery_orchestrator import LOGO_IDENTITY_KINDS
        from app.services.logo_fallback_resolver import find_override, load_overrides, root_of

        overrides = load_overrides()
        if not overrides:
            return {"overrides_loaded": 0, "matched": 0, "attached": 0, "skipped_existing": 0}

        def lookup(host: str):
            return find_override(overrides, host)

        from datetime import datetime, timezone

        from sqlalchemy import select

        from app.models import Scholarship

        now = datetime.now(timezone.utc)
        attached = 0
        skipped_existing = 0
        details: list[dict] = []
        still_missing: dict[str, int] = {}
        session = factory()
        try:
            rows = session.scalars(select(Scholarship)).all()
            for row in rows:
                host = (urlparse(row.official_source_url or "").hostname or "").lower()
                host = host[4:] if host.startswith("www.") else host
                found = lookup(host)
                if not found:
                    if not row.image_url and host:
                        still_missing[host] = still_missing.get(host, 0) + 1
                    continue
                key, entry = found
                if row.image_url:
                    # An existing verified identity mark is never replaced by a
                    # different one; a stored photo, though, is exactly what
                    # logo-only mode exists to remove.
                    if (row.image_kind or "") in LOGO_IDENTITY_KINDS:
                        skipped_existing += 1
                    else:
                        row.image_url = None
                        row.image_source_url = None
                        row.image_source_type = None
                        row.image_kind = None
                        row.image_alt_text = None
                        row.image_verified_at = None
                        still_missing[host] = still_missing.get(host, 0) + 1
                    continue
                if args.dry_run:
                    attached += 1
                    continue
                row.image_url = entry["url"]
                row.image_source_url = entry.get("page_url") or root_of(
                    row.official_source_url
                )
                row.image_source_type = _issuer_kind(key, entry.get("alt_text"))
                row.image_kind = "official_logo"
                row.image_alt_text = entry.get("alt_text") or key
                row.image_verified_at = now
                row.image_evaluated_at = now
                row.image_evaluation_status = "no_official_image"
                attached += 1
                if len(details) < 300:
                    details.append({"id": row.id, "host": host, "matched_key": key})
            if attached and not args.dry_run:
                session.commit()
            elif args.dry_run:
                session.rollback()
        finally:
            session.close()

        ranked = sorted(still_missing.items(), key=lambda kv: (-kv[1], kv[0]))
        detail = {
            "overrides_loaded": len(overrides),
            "attached": attached,
            "skipped_existing_image": skipped_existing,
            "records_still_without_logo": sum(count for _host, count in ranked),
            "distinct_hosts_still_without_logo": len(ranked),
            "top_hosts_still_without_logo": ranked,
            "attached_detail": details,
        }
        if not args.dry_run:
            recorder.record_counts({"logo_overrides_attached": attached})
        return detail

    def do_facts() -> dict:
        """Apply audited official programme facts to records that lack them.

        The enrichment stage reads the awarding body's own page, which is the
        right primary source. It cannot always finish the job: a page can be a
        JS-rendered app, or can bury the deadline below a folded accordion, and
        the record is then published with an empty field.

        This stage closes that gap from a small audited file, and it is
        deliberately timid. It only writes fields that are currently NULL, so a
        value the scraper did read always wins, and it only matches on the exact
        official source host, so a Chevening record can never pick up
        Commonwealth facts. Getting either of those wrong would write confident
        false data into the catalogue, which is the one failure mode this whole
        pipeline exists to prevent.
        """
        import json
        from datetime import date, datetime, timezone
        from pathlib import Path
        from urllib.parse import urlparse

        from sqlalchemy import select

        from app.models import Scholarship
        from app.services.scholarship_enrichment import derive_status

        facts_path = Path(__file__).resolve().parents[2] / "config" / "official_programme_facts.json"
        try:
            raw = json.loads(facts_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # A broken config must degrade to "no facts", never to a crash
            # inside a scheduled run and never to a guess.
            logger.warning("could not read programme facts from %s: %s", facts_path, exc)
            return {"facts_file": str(facts_path), "error": str(exc)}
        facts = {k: v for k, v in raw.items() if not str(k).startswith("_") and isinstance(v, dict)}
        if not facts:
            return {"facts_file": str(facts_path), "facts_loaded": 0, "matched": 0, "fields_filled": 0}

        # Facts keys map onto real columns. `provider` and `amount` are not
        # columns on this model: the awarding body is `official_source` and the
        # money is `benefits`. Writing to a name that does not exist raises
        # AttributeError inside a scheduled run, which is how this stage first
        # failed in production.
        text_fields = ("official_source", "benefits", "eligibility", "funding", "degree")
        today = date.today()
        applied: list[dict] = []
        session = factory()
        try:
            rows = session.scalars(select(Scholarship)).all()
            for row in rows:
                host = (urlparse(row.official_source_url or "").hostname or "").lower()
                host = host[4:] if host.startswith("www.") else host
                entry = facts.get(host)
                if not entry:
                    continue
                filled: list[str] = []
                for field in text_fields:
                    value = (entry.get(field) or "").strip() or None
                    if value and not getattr(row, field, None):
                        setattr(row, field, value)
                        filled.append(field)

                # A deadline is four columns, not one. Writing only the date
                # would leave the frontend's display string empty, so the card
                # would show no deadline at all while the record claimed one.
                if not row.deadline_date and (entry.get("deadline") or "").strip():
                    try:
                        parsed = date.fromisoformat(entry["deadline"].strip())
                    except ValueError:
                        logger.warning("unparseable deadline %r for %s", entry["deadline"], host)
                    else:
                        row.deadline_date = parsed
                        row.deadline_display = f"{parsed.day} {parsed.strftime('%B %Y')}"
                        row.deadline_precision = "day"
                        filled.extend(["deadline_date", "deadline_display", "deadline_precision"])

                if "deadline_date" in filled:
                    # Keep status consistent with the date we just wrote, using
                    # the same helper the enrichment stage uses so both paths
                    # agree on the open / closing-soon / closed vocabulary.
                    derived, _reason = derive_status(
                        today=today,
                        deadline_date=row.deadline_date,
                        deadline_display=row.deadline_display,
                        deadline_precision=row.deadline_precision,
                        source_text=None,
                        current_status=row.status,
                    )
                    if derived and derived != "unknown":
                        row.status = derived
                        filled.append("status")

                if not filled:
                    continue
                row.updated_at = datetime.now(timezone.utc)
                applied.append({"id": row.id, "host": host, "fields": filled})
            if applied and not args.dry_run:
                session.commit()
            elif args.dry_run:
                session.rollback()
        finally:
            session.close()

        detail = {
            "facts_file": str(facts_path),
            "facts_loaded": len(facts),
            "matched": len(applied),
            "fields_filled": sum(len(a["fields"]) for a in applied),
            "applied": applied[:200],
        }
        if not args.dry_run:
            recorder.record_counts(
                {
                    "facts_records_matched": len(applied),
                    "facts_fields_filled": detail["fields_filled"],
                }
            )
        return detail

    def do_purge() -> dict:
        """Clear stored images that are not official identity marks.

        A programme photograph is decoration, not provenance: it does not say
        who awards the scholarship. This stage removes those images so the
        images stage can go looking for a logo instead, and so the catalogue
        stops presenting a stock campus photo as though it were a verified
        emblem.

        Only the kind is used as the test, and a record whose kind was never
        recorded counts as non-logo. That is the conservative direction: an
        image we cannot identify is one we should not keep.
        """
        from sqlalchemy import select

        from app.models import Scholarship
        from app.services.image_discovery_orchestrator import LOGO_IDENTITY_KINDS

        session = factory()
        try:
            rows = session.scalars(
                select(Scholarship).where(Scholarship.image_url.isnot(None))
            ).all()
            offenders = [
                r for r in rows
                if (r.image_kind or "") not in LOGO_IDENTITY_KINDS
            ]
            if args.dry_run:
                return {
                    "image_rows": len(rows),
                    "would_clear": len(offenders),
                    "kept_identity_kinds": sorted(LOGO_IDENTITY_KINDS),
                }

            for row in offenders:
                row.image_url = None
                row.image_source_url = None
                row.image_source_type = None
                row.image_kind = None
                row.image_alt_text = None
                row.image_verified_at = None
            session.commit()

            detail = {
                "image_rows": len(rows),
                "cleared": len(offenders),
                "kept_identity_kinds": sorted(LOGO_IDENTITY_KINDS),
            }
            recorder.record_counts({"image_non_logo_cleared": len(offenders)})
            return detail
        finally:
            session.close()

    def do_images() -> dict:
        runner = ImageCoverageRunner(
            factory,
            dry_run=args.dry_run,
            plan_only=args.dry_run,
            batch_size=min(15, limit),
            max_workers=workers,
            exclude_quarantined=True,
            skip_terminally_evaluated=True,
            logo_only=args.logo_only,
            per_record_budget_seconds=args.image_budget_seconds,
        )
        metrics = runner.run(limit=limit)
        recorder.record_counts(
            {
                "image_records_in_scope": metrics.records_in_scope,
                "image_newly_found": metrics.newly_found,
                "image_source_blocked": metrics.source_blocked,
            }
        )
        return metrics.as_dict()

    def do_discover() -> dict:
        # Bounded deep crawling is opt-in via --crawl-depth. It is not the
        # default because it multiplies network cost, and a scheduled run
        # should not silently start taking twenty times as long.
        crawl_budget = None
        if args.crawl_depth > 0:
            from app.services.discovery_crawler import CrawlBudget

            crawl_budget = CrawlBudget(
                max_depth=args.crawl_depth,
                max_pages_per_seed=max(1, args.crawl_pages_per_seed),
                max_total_pages=max(1, args.crawl_max_pages),
            )
            logger.info("discovery deep crawl enabled: %s", crawl_budget.as_dict())

        result = run_discovery_round(
            dry_run=args.dry_run, max_workers=workers, crawl_budget=crawl_budget
        )
        detail = result.as_dict() if hasattr(result, "as_dict") else {"result": str(result)}
        # Close the quarantine latency gap in the same cycle.
        #
        # The cursor sweep cannot do this job: a record inserted this run has
        # the highest id in the catalogue, and the quarantine cursor is
        # somewhere in the middle, so the record would sit in the public
        # directory until the sweep wrapped around - roughly 49 runs at the
        # default limit. That is how "Home - Erasmus+" and "Ministry of
        # Education (MOE)" reached production with a bare site root and every
        # content field empty.
        #
        # Discovery is the only stage that can introduce a structurally invalid
        # record, so it is the only stage that needs this. The routine sweep
        # still runs afterwards and still covers the legacy catalogue.
        inserted = list(getattr(result, "inserted_ids", []) or [])
        if inserted and not args.dry_run:
            quarantined_now = _quarantine_ids(factory, inserted, dry_run=False)
            detail["immediately_quarantined"] = quarantined_now
            detail["immediately_assessed"] = len(inserted)
            recorder.record_counts(
                {
                    "discover_newly_inserted": len(inserted),
                    "discover_immediately_quarantined": quarantined_now,
                }
            )
        elif inserted:
            detail["immediately_assessed"] = len(inserted)
            detail["immediately_quarantined"] = 0
        return detail

    def do_quarantine() -> dict:
        # Routine sweep. Discovery's own new records were already assessed in
        # the same cycle by do_discover; this covers the legacy catalogue on
        # the durable cursor, including anything an earlier run inserted.
        from app.services.catalogue_quarantine import QUARANTINE_STATUS

        batch = store.select_batch(
            "quarantine", limit=limit, skip_complete=False
        )
        if batch.is_empty:
            return {"selected": 0, **store.state_as_dict("quarantine")}

        quarantined = _quarantine_ids(factory, batch.ids, dry_run=args.dry_run)
        if not args.dry_run:
            store.advance("quarantine", batch)
        recorder.record_counts(
            {
                "quarantine_scanned": len(batch.ids),
                "quarantine_applied": quarantined,
            }
        )
        return {
            "selected": len(batch.ids),
            "records_scanned": len(batch.ids),
            "quarantined": quarantined,
            "status_value": QUARANTINE_STATUS,
            "cursor": batch.as_dict(),
            "dry_run": args.dry_run,
        }

    stages = {
        "verify": do_verify,
        "enrich": do_enrich,
        "images": do_images,
        "discover": do_discover,
        "quarantine": do_quarantine,
        "stats": do_stats,
        "facts": do_facts,
        "logos": do_logos,
        "purge": do_purge,
    }

    reports: list[StageReport] = []
    failed: set[str] = set()

    print("=" * 68)
    print("SCHOLARZONE MAINTENANCE")
    print(f"  mode        : {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  stages      : {', '.join(selected)}")
    print(f"  limit/stage : {limit}   workers: {workers}")
    print(f"  run_id      : {recorder.run_id}")
    print("=" * 68)

    for name in selected:
        blocked_by = [d for d in STAGE_DEPENDENCIES.get(name, ()) if d in failed]
        if blocked_by:
            report = _skipped(
                name, f"prerequisite stage failed: {', '.join(blocked_by)}"
            )
            logger.warning("skipping %s: %s", name, report.skip_reason)
        else:
            report = _run_stage(name, stages[name])
            if not report.ok and not report.skipped:
                failed.add(name)
        reports.append(report)
        recorder.record_stage(
            name, report.ok, report.detail, report.runtime_s, report.error or report.skip_reason
        )

    print()
    for report in reports:
        if report.skipped:
            print(f"[SKIPPED] {report.name}  ({report.skip_reason})")
            continue
        status = "ok" if report.ok else "FAILED"
        print(f"[{status}] {report.name}  ({report.runtime_s:.1f}s)")
        for key, value in report.detail.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    print(f"    {sub_key}: {sub_value}")
            else:
                print(f"    {key}: {value}")
        if report.error:
            print(f"    error: {report.error}")

    failed_count = sum(1 for r in reports if not r.ok and not r.skipped)
    skipped_count = sum(1 for r in reports if r.skipped)

    try:
        for name in ("enrich",):
            if name in selected and not any(
                r.name == name and r.skipped for r in reports
            ):
                print(f"    {name} cursor: {store.state_as_dict(name)}")
    except Exception:  # noqa: BLE001 - never fail a run over a status print
        logger.warning("could not read cursor state", exc_info=True)

    status = "ok" if not failed_count else "failed"
    record_saved = True
    try:
        recorder.record_counts(
            {
                "stages_run": len(reports) - skipped_count,
                "stages_failed": failed_count,
                "stages_skipped": skipped_count,
            }
        )
        record_saved = recorder.finish(status)
    except Exception:  # noqa: BLE001
        logger.warning("could not persist run record", exc_info=True)
        record_saved = False

    if not record_saved:
        print("\n::error::The maintenance run record could not be written to the database.")
        print("::error::Stage results are only in this log; the run is not observable from the database.")
        status = "failed"

    failed_reports = [r for r in reports if not r.ok and not r.skipped]
    if failed_reports:
        emit_failure_classification(failed_reports)

    # Compact, flat metric block. Deliberately not a monitoring framework: it
    # is the same numbers already in MaintenanceRun, printed so a single log
    # read answers "what did this run cost".
    print("\n--- metrics ---")
    for key in sorted(recorder.counts):
        print(f"  {key}: {recorder.counts[key]}")
    total_runtime = sum(r.runtime_s for r in reports if not r.skipped)
    print(f"  total_runtime_s: {total_runtime:.1f}")
    for report in reports:
        if not report.skipped:
            print(f"  stage_runtime_s.{report.name}: {report.runtime_s:.1f}")

    print("\n" + "=" * 68)
    print(f"run_id: {recorder.run_id}   status: {status}")
    print(f"stages run: {len(reports) - skipped_count}   failed: {failed_count}   skipped: {skipped_count}")
    if failed_count:
        print("FAILED STAGES: " + ", ".join(r.name for r in reports if not r.ok and not r.skipped))
    print("=" * 68)

    # A stage failure is a failed workflow. The old worker returned 0 here,
    # which meant a scheduled run that verified nothing still showed green.
    if failed_count or not record_saved:
        return EXIT_STAGE_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
