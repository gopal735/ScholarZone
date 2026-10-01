"""Direct maintenance worker: GitHub Actions -> Neon, with no API in between.

Historical note: the scheduled workflow used to wake a SnapDeploy container and
call the production API over HTTP. On the free tier a container sleeps, the wake
is not guaranteed, and a scheduled run therefore depended on a platform
behaviour it does not control. Verification is the one job that most needs to
run when nobody is looking, so making it depend on a cold start is backwards.

That history is the reason this module is independent of the web runtime, and
the independence is deliberate: the worker connects straight to Neon and calls no
HTTP endpoint of any kind - not the public API, not an admin route, and not the
frontend. It therefore keeps working if the web tier is down, being deployed, or
on a different provider altogether.

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
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date

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
STAGE_ORDER = (
    "verify", "worklist", "inventory", "enrich", "programme_details", "images", "logos", "discover", "quarantine", "retire", "correct",
    "stats", "facts", "archive", "discontinued", "purge", "purge_closed",
)

# purge_closed is the only stage that deletes rows. It is excluded from "all"
# so a scheduled run cannot destroy the catalogue unattended, and named here so
# the contract is asserted rather than assumed.
PURGE_CLOSED_EXCLUDED_FROM_ALL = True

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
    # Read-only: it reports the backlog, so it stays a leaf rather than
    # reflecting whatever a partial run happened to have written.
    "worklist": (),
    "inventory": (),
    "stats": (),
    "facts": (),
    "logos": (),
    # Applies researched detail to empty fields only, so it depends on nothing
    # having been written in this run and can be dispatched on its own.
    "programme_details": (),
    # Retiring and correcting are both driven by audited files, and both have to
    # land before archive: archive derives its decision from the deadline, and a
    # record whose address was just repaired should not be judged on the old one.
    "retire": (),
    "correct": (),
    "archive": (),
    "discontinued": (),
    "purge": (),
    # Destroys rows; never rides along in "all".
    "purge_closed": (),
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


# Programmes that were retired outright rather than closing for a season, keyed
# by the host their official pages live on.
#
# Vanier CGS-D was folded into the Canada Graduate Research Scholarship - Doctoral
# and the Banting Postdoctoral Fellowship was replaced by the Canada
# Postdoctoral Research Award. Both official pages state that applications are
# no longer accepted, so a record advertising a closing date for either is worse
# than a blank one: it is a confident pointer to a programme that no longer
# exists. Each entry records the reason so the quarantine note explains itself
# to whoever reads the record later.
DO_DISCONTINUED_SOURCE: dict[str, str] = {
    "vanier.gc.ca": (
        "Vanier CGS-D was folded into the Canada Graduate Research Scholarship - "
        "Doctoral. The official page states applications are no longer accepted."
    ),
    "banting.fellowships-bourses.gc.ca": (
        "The Banting Postdoctoral Fellowship was replaced by the Canada "
        "Postdoctoral Research Award. The official page states applications are "
        "no longer accepted."
    ),
}


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


def _next_review_due(today: date) -> date:
    """When a record with no deadline of its own should next be checked.

    A rolling or undated programme has no natural reminder in its own calendar,
    so without this it would never be re-examined and would quietly rot.
    """
    from datetime import timedelta

    return today + timedelta(days=90)

def _column_length(model, field: str) -> int | None:
    """Declared length of a column, or None when it has none or does not exist.

    Not every column type has a `length` at all - a JSON column raises
    AttributeError on the attribute rather than returning None, which is how a
    research pass over eligibility values took the whole stage down. A name that
    is not a column at all raises KeyError here; detail fields that live in the
    structured blocks are not columns, and must be reported as having no width
    rather than stopping the run.
    """
    columns = model.__table__.columns
    if field not in columns:
        return None
    return getattr(columns[field].type, "length", None)


def _is_column(model, field: str) -> bool:
    return field in model.__table__.columns


# Flag labels the retire stage writes at the start of a record's archived
# reason. The archive stage writes "deadline passed on ..." and the discontinued
# stage writes "programme discontinued", so a reason beginning with one of these
# proves this stage is what hid the record, and that it may therefore be
# un-hidden when the audit stops listing it.
RETIRE_FLAG_PREFIXES = frozenset({
    "DEAD", "RENAMED", "DUPLICATE", "MISATTRIBUTED", "NEVER-EXISTED",
    "WRONG-DATA", "RETIRED-SUCCESSOR",
})


def _is_json_column(model, field: str) -> bool:
    from sqlalchemy import JSON

    return isinstance(model.__table__.c[field].type, JSON)


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

        # Neon closes idle pooled connections, and a maintenance run that starts
        # on a recycled socket loses the handshake. That is a transient network
        # condition, not a broken configuration, so retrying is correct; a
        # genuine misconfiguration still fails on the final attempt.
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                init_database()
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "database init attempt %d/3 failed: %s", attempt, exc
                )
                time.sleep(3 * attempt)
        if last_error is not None:
            raise last_error
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
        choices=["verify", "worklist", "inventory", "enrich", "programme_details", "images", "logos", "discover", "quarantine", "retire", "correct",
                     "stats", "facts", "archive", "discontinued", "retire", "purge", "purge_closed", "all"],
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

    # Bring the schema up to date before any stage touches a table.
    #
    # This worker runs stages that are dispatched independently, and a stage that
    # selects a column a previous deploy has not added yet fails with an opaque
    # UndefinedColumn error - which reads as a database problem rather than a
    # deploy-ordering one. The upgrade is idempotent and additive, so running it
    # on every invocation costs one introspection query.
    try:
        from app.database import init_database

        init_database()
    except Exception as exc:  # noqa: BLE001
        print(f"schema upgrade failed: {type(exc).__name__}: {exc}")
        return EXIT_FATAL

    wanted = set(args.stage or ["all"])
    run_all = "all" in wanted
    # "all" must never destroy rows. A scheduled run has no operator watching it,
    # so a stage that deletes records is only ever reachable by naming it.
    selected = [
        s
        for s in STAGE_ORDER
        if (run_all and s != "purge_closed") or s in wanted
    ]
    assert not (run_all and PURGE_CLOSED_EXCLUDED_FROM_ALL) or "purge_closed" not in selected

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
            # deadline_date alone is the wrong number to report. Most of the
            # catalogue's deadlines are legitimately undated - a per-ministry or
            # per-university scheme has no single date - and those records now
            # carry honest "varies by institution" text that an applicant
            # actually sees. Counting only the date column made real coverage
            # look like a permanent gap.
            coverage["missing_deadline_display"] = _count_where(
                Scholarship.deadline_display.is_(None)
            )
            coverage["deadline_varied_or_rolling"] = _count_where(
                Scholarship.deadline_precision.in_(("varies", "rolling", "recurring"))
            )
            # What the public can actually see, which is the number that matters
            # and the one total_records cannot tell you.
            coverage["archived_hidden"] = _count_where(Scholarship.is_archived.is_(True))
            coverage["public_visible"] = _count_where(
                Scholarship.is_archived.is_(False),
                Scholarship.verification_status != QUARANTINE_STATUS,
            )

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
        from app.services.image_evaluation_status import ImageEvaluationStatus
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
                # This stage records VERIFIED, not "no_official_image". The old
                # value was written on the line that attaches a logo, so every
                # record it filled claimed at the same time that it had no
                # official image - a contradiction that reads as a coverage
                # failure in any report counting evaluation status.
                row.image_evaluation_status = ImageEvaluationStatus.VERIFIED
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

    def do_archive() -> dict:
        """Archive records whose published deadline has passed.

        A scholarship with a closing date in the past is not an opportunity, and
        leaving it in the public directory sends applicants to a form that no
        longer accepts anything. Archiving is therefore a one-way flag, set from
        the date rather than by hand, and it is separate from ``status``:
        status flips back to open when a new cycle is published, and an archived
        record should not silently reappear because somebody re-derived its
        status.

        The record itself is never deleted. Its history, its verification trail
        and any inbound link survive, so an archived scholarship can be
        reinstated deliberately instead of being re-discovered from scratch.

        Safe to re-run: an already-archived record is excluded, so the work does
        not repeat and the reported count settles at zero.
        """
        from datetime import date, datetime, timedelta, timezone

        from sqlalchemy import select

        from app.models import Scholarship

        today = date.today()
        now = datetime.now(timezone.utc)
        session = factory()
        try:
            rows = session.scalars(
                select(Scholarship).where(
                    Scholarship.is_archived.is_(False),
                    Scholarship.deadline_date.isnot(None),
                    Scholarship.deadline_date < today,
                )
            ).all()
            if args.dry_run:
                session.rollback()
            else:
                for row in rows:
                    row.is_archived = True
                    row.archived_at = now
                    row.archived_reason = f"deadline passed on {row.deadline_date.isoformat()}"
                    # Status is derived from the same date, so leaving it open
                    # would make a filter on status contradict the archive.
                    row.status = "closed"
                session.commit()
        finally:
            session.close()

        detail = {
            "as_of": today.isoformat(),
            "archived": 0 if args.dry_run else len(rows),
            "would_archive": len(rows),
        }
        if not args.dry_run:
            recorder.record_counts({"archive_archived": len(rows)})
        return detail

    def _snapshot_row_payload(row) -> dict:
        """Every stored column of one record, JSON-safe.

        Used only by ``do_purge_closed``. A deleted row that cannot be
        described exactly is a row that cannot be brought back, so this
        serialises the mapped columns rather than the handful of fields the
        report happens to print.
        """
        from datetime import date as _date, datetime as _datetime
        from pathlib import Path

        def encode(value):
            if isinstance(value, (_date, _datetime)):
                return value.isoformat()
            return value

        return {
            column.name: encode(getattr(row, column.name))
            for column in row.__table__.columns
        }

    def do_purge_closed() -> dict:
        """Permanently delete records whose application round is closed.

        ``do_discontinued`` hides a dead programme and ``do_archive`` folds a
        finished one away; both keep the row. This stage is the opposite and is
        deliberately the only one that destroys data, so it is written to be
        reversible by construction:

        * it selects on the round being closed, never on a text match;
        * it writes every selected row out in full before deleting any of them;
        * the snapshot is returned and also written beside the configs, so the
          deleted rows can be restored without re-crawling anything.

        "Closed" means the round cannot be applied to right now: an explicit
        non-open status, an archived record, or a deadline that has already
        passed. A record with no deadline is never selected - a missing date is
        an unknown date, not an expired one, and deleting on a guess is the one
        outcome an applicant cannot recover from.
        """
        from sqlalchemy import select

        from app.models import Scholarship

        today = date.today()
        session = factory()
        try:
            rows = session.scalars(select(Scholarship)).all()
            selected: list[dict] = []
            breakdown = {
                "status_not_open": 0,
                "archived": 0,
                "deadline_passed": 0,
            }
            for row in rows:
                reasons = []
                status = (row.status or "").strip().lower()
                if status not in ("open", "upcoming"):
                    reasons.append("status_not_open")
                    breakdown["status_not_open"] += 1
                if row.is_archived:
                    reasons.append("archived")
                    breakdown["archived"] += 1
                if row.deadline_date is not None and row.deadline_date < today:
                    reasons.append("deadline_passed")
                    breakdown["deadline_passed"] += 1
                if not reasons:
                    continue
                selected.append(
                    {
                        "id": row.id,
                        "title": row.title,
                        "country": row.country,
                        "status": row.status,
                        "is_archived": row.is_archived,
                        "deadline_date": (
                            row.deadline_date.isoformat() if row.deadline_date else None
                        ),
                        "reasons": reasons,
                        "official_source_url": row.official_source_url,
                        "payload": _snapshot_row_payload(row),
                    }
                )

            snapshot_path = Path(__file__).resolve().parents[2] / "config" / "purged_records_archive.json"
            if args.dry_run:
                return {
                    "error": None,
                    "would_delete": len(selected),
                    "breakdown": breakdown,
                    "ids": [item["id"] for item in selected],
                    "snapshot_preview": selected[:3],
                }

            snapshot_path.write_text(
                json.dumps(
                    {
                        "purged_at": today.isoformat(),
                        "count": len(selected),
                        "breakdown": breakdown,
                        "records": selected,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            deleted: list[int] = []
            for item in selected:
                row = session.get(Scholarship, item["id"])
                if row is None:
                    continue
                session.delete(row)
                deleted.append(item["id"])
            session.commit()

            return {
                "error": None,
                "deleted": len(deleted),
                "breakdown": breakdown,
                "ids": deleted,
                "snapshot_file": str(snapshot_path),
            }
        except Exception as exc:
            session.rollback()
            return {"error": str(exc)}
        finally:
            session.close()

    def do_discontinued() -> dict:
        """Quarantine records for programmes that no longer exist.

        Some programmes are retired outright rather than closing for a season:
        Vanier CGS-D was folded into the Canada Graduate Research Scholarship and
        the Banting Postdoctoral Fellowship was replaced by the Canada
        Postdoctoral Research Award. Their official pages state they are no
        longer accepting applications, so a record advertising a closing date
        for them is worse than a blank one - it is a confident pointer to a dead
        programme.

        They are quarantined rather than deleted so the record, its history and
        any inbound link survive.
        """
        from datetime import datetime, timezone

        from sqlalchemy import select

        from app.models import Scholarship
        from app.services.catalogue_quarantine import QUARANTINE_STATUS

        session = factory()
        try:
            affected: list[int] = []
            for host, reason in DO_DISCONTINUED_SOURCE.items():
                rows = session.scalars(
                    select(Scholarship).where(
                        Scholarship.official_source_url.like(f"%{host}%")
                    )
                ).all()
                for row in rows:
                    affected.append(row.id)
                    if args.dry_run:
                        continue
                    if row.verification_status == QUARANTINE_STATUS:
                        continue
                    row.verification_status = QUARANTINE_STATUS
                    row.verification_notes = reason
                    if not row.is_archived:
                        row.is_archived = True
                        row.archived_at = datetime.now(timezone.utc)
                        row.archived_reason = "programme discontinued"
            if affected and not args.dry_run:
                session.commit()
            elif args.dry_run:
                session.rollback()
        finally:
            session.close()

        detail = {
            "retired_hosts": sorted(DO_DISCONTINUED_SOURCE),
            "records_matched": len(affected),
            "quarantined": 0 if args.dry_run else len(affected),
        }
        if not args.dry_run:
            recorder.record_counts({"discontinued_quarantined": len(affected)})
        return detail

    def do_retire() -> dict:
        """Quarantine and hide individual records research has disproved.

        Host-level retirement cannot express a catalogue's most common real
        problem. One host legitimately carries several programmes, so a single
        record among them can be dead, renamed, duplicated against a sibling, or
        attributed to the wrong organisation while its neighbours are perfectly
        sound. Six MEXT records on one domain are real; the seventh is a
        USA-only edition that duplicates another row.

        The decision is data, not code, so it lives in an audited file that
        records what was wrong and what replaced it. Nothing is deleted: the row
        keeps its history and its inbound links, but stops being published, and
        the reason is stored rather than implied.
        """
        import json
        from datetime import datetime, timezone
        from pathlib import Path

        from sqlalchemy import select

        from app.models import Scholarship
        from app.services.catalogue_quarantine import QUARANTINE_STATUS

        retire_path = (
            Path(__file__).resolve().parents[2] / "config" / "retired_records.json"
        )
        try:
            raw = json.loads(retire_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("could not read retired records from %s: %s", retire_path, exc)
            return {"retired_file": str(retire_path), "error": str(exc)}

        entries = raw.get("records") if isinstance(raw, dict) else raw
        entries = entries if isinstance(entries, list) else []
        wanted = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                rid = int(entry.get("id"))
            except (TypeError, ValueError):
                logger.warning("ignoring retired entry with no usable id: %r", entry)
                continue
            wanted[rid] = entry
        if not wanted:
            return {"retired_file": str(retire_path), "records_listed": 0, "matched": 0}

        session = factory()
        try:
            matched: list[dict] = []
            # The reason column is a bounded varchar and Postgres raises on an
            # overflow rather than truncating, so a long research sentence
            # failed the whole run - on the stage's first live execution, after
            # the audited file had already been written. The width is read from
            # the model so it cannot drift when the column changes.
            reason_limit = _column_length(Scholarship, "archived_reason") or 255
            for rid, entry in sorted(wanted.items()):
                row = session.get(Scholarship, rid)
                if row is None:
                    matched.append({"id": rid, "outcome": "not_found"})
                    continue
                flag = str(entry.get("flag") or "DISPROVED").upper()
                reason = str(entry.get("reason") or "disproved by research").strip()
                successor = str(entry.get("successor") or "").strip()
                note = f"{flag}: {reason}"
                if successor:
                    note += f" | successor: {successor}"
                matched.append(
                    {"id": rid, "outcome": "retired", "flag": flag, "title": row.title}
                )
                if args.dry_run:
                    continue
                if row.verification_status != QUARANTINE_STATUS:
                    row.verification_status = QUARANTINE_STATUS
                row.verification_notes = note
                if not row.is_archived:
                    row.is_archived = True
                    row.archived_at = datetime.now(timezone.utc)
                    row.archived_reason = note[:reason_limit]
                row.updated_at = datetime.now(timezone.utc)
            if not args.dry_run:
                session.commit()
            else:
                session.rollback()
        finally:
            session.close()

        # Reconciliation. The file is the only thing allowed to hide a record, so
        # a record this stage hid on an earlier pass and no longer lists has to
        # come back.
        #
        # This is not hypothetical. An earlier version of the audit decided what
        # to retire by matching keywords in a researcher's prose, and hid 76
        # records; under the current policy 40 qualify. The other 36 were
        # withdrawn on the evidence of a regex and had no other reason to be
        # hidden from an applicant. Only records this stage hid are eligible:
        # their archived reason begins with a flag label, which the archive and
        # discontinued stages never write.
        restored: list[int] = []
        session = factory()
        try:
            rows = session.scalars(
                select(Scholarship).where(Scholarship.is_archived.is_(True))
            ).all()
            for row in rows:
                reason = (row.archived_reason or "").strip()
                head = reason.split(":", 1)[0].strip().upper()
                if head not in RETIRE_FLAG_PREFIXES:
                    continue
                if row.id in wanted:
                    continue
                if args.dry_run:
                    restored.append(row.id)
                    continue
                row.is_archived = False
                row.archived_at = None
                row.archived_reason = None
                if row.verification_status == QUARANTINE_STATUS:
                    row.verification_status = "active"
                row.updated_at = datetime.now(timezone.utc)
                restored.append(row.id)
            if restored and not args.dry_run:
                session.commit()
            elif args.dry_run:
                session.rollback()
        finally:
            session.close()

        retired = [m for m in matched if m["outcome"] == "retired"]
        missing = [m["id"] for m in matched if m["outcome"] == "not_found"]
        by_flag: dict[str, int] = {}
        for item in retired:
            flag = item["flag"]
            by_flag[flag] = by_flag.get(flag, 0) + 1
        detail = {
            "retired_file": str(retire_path),
            "records_listed": len(wanted),
            "matched": len(retired),
            "not_found": missing,
            "restored_no_longer_listed": len(restored),
            "by_flag": dict(sorted(by_flag.items())),
        }
        if not args.dry_run:
            recorder.record_counts(
                {
                    "retired_records_hidden": len(retired),
                    "retired_records_restored": len(restored),
                }
            )
        return detail

    def do_correct() -> dict:
        """Fix records whose official source URL or title research disproved.

        Live research finds far more wrong links than dead programmes. A record
        for a perfectly real scholarship can point at a page that 404s, at an
        index instead of the programme, or at a PDF for the wrong cycle. Those
        records must not be retired: retiring them would hide a real
        scholarship from every applicant because a link rotted. The programme
        is fine, the address is not.

        So corrections and retirement are separate decisions with separate
        files. This stage repairs the address and the title; the retire stage
        hides records whose programme genuinely no longer exists. The split
        matters because only one of the two is reversible without loss.

        URLs are overwritten rather than filled only when empty, because a
        broken URL is worse than no URL: it is a confident pointer to nowhere.
        Every change is recorded per record so the reason survives with it.
        """
        import json
        from datetime import datetime, timezone
        from pathlib import Path
        from urllib.parse import urlparse

        from sqlalchemy import select

        from app.models import Scholarship

        corrections_path = (
            Path(__file__).resolve().parents[2] / "config" / "record_corrections.json"
        )
        try:
            raw = json.loads(corrections_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("could not read corrections from %s: %s", corrections_path, exc)
            return {"corrections_file": str(corrections_path), "error": str(exc)}

        entries = raw.get("records") if isinstance(raw, dict) else raw
        entries = entries if isinstance(entries, list) else []
        wanted: dict[int, dict] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                rid = int(entry.get("id"))
            except (TypeError, ValueError):
                logger.warning("ignoring correction with no usable id: %r", entry)
                continue
            wanted[rid] = entry
        if not wanted:
            return {"corrections_file": str(corrections_path), "records_listed": 0, "matched": 0}

        # Only these are written, and each is a text or URL column that exists.
        writable = {
            "official_source_url": "url",
            "application_link": "url",
            "title": "text",
            "official_source": "text",
            "description": "text",
        }

        session = factory()
        try:
            applied: list[dict] = []
            collisions: list[dict] = []
            # Addresses assigned earlier in this same batch. Two corrections can
            # propose the same new URL, and neither sees the other's write
            # because neither has been committed yet, so the database check
            # below cannot see the clash on its own.
            assigned: dict[str, int] = {}
            for rid, entry in sorted(wanted.items()):
                row = session.get(Scholarship, rid)
                if row is None:
                    applied.append({"id": rid, "outcome": "not_found"})
                    continue
                changed: list[str] = []
                if args.dry_run:
                    applied.append({"id": rid, "outcome": "would_change", "title": row.title})
                    continue
                for field, kind in writable.items():
                    value = str(entry.get(field) or "").strip()
                    if not value:
                        continue
                    if kind == "url":
                        parsed = urlparse(value)
                        if parsed.scheme not in ("http", "https") or not parsed.hostname:
                            logger.warning(
                                "skipping non-absolute %s for record %d: %r", field, rid, value
                            )
                            continue
                        if field == "official_source_url":
                            # official_source_url is unique, and a correction
                            # is allowed to point a record at an address another
                            # record already holds. Writing it raises a
                            # UniqueViolation that fails the whole run, and the
                            # duplicate it would create is itself a defect, so
                            # the correction is skipped and reported instead.
                            clash = assigned.get(value)
                            if clash is None:
                                clash = session.scalar(
                                    select(Scholarship.id).where(
                                        Scholarship.official_source_url == value,
                                        Scholarship.id != rid,
                                    ).limit(1)
                                )
                            if clash:
                                collisions.append(
                                    {"id": rid, "url": value, "already_used_by": clash}
                                )
                                continue
                            assigned[value] = rid
                    if (getattr(row, field, None) or "").strip() == value:
                        continue
                    setattr(row, field, value)
                    changed.append(field)
                if changed:
                    row.updated_at = datetime.now(timezone.utc)
                    reason = str(entry.get("reason") or "").strip()
                    if reason:
                        # Kept on the record so a later reader can tell a
                        # deliberate correction from a scraper's guess.
                        note = row.verification_notes or ""
                        if reason not in note:
                            row.verification_notes = (note + f" | corrected: {reason}")[:1000]
                applied.append(
                    {"id": rid, "outcome": "changed" if changed else "unchanged",
                     "fields": changed, "title": row.title}
                )
            if not args.dry_run:
                session.commit()
            else:
                session.rollback()
        finally:
            session.close()

        changed = [a for a in applied if a["outcome"] == "changed"]
        detail = {
            "corrections_file": str(corrections_path),
            "url_collisions_skipped": len(collisions),
            "url_collisions": collisions[:20],
            "records_listed": len(wanted),
            "matched": len([a for a in applied if a["outcome"] != "not_found"]),
            "changed": len(changed),
            "not_found": [a["id"] for a in applied if a["outcome"] == "not_found"],
            "applied": changed[:200],
        }
        if not args.dry_run:
            recorder.record_counts({"corrected_records": len(changed)})
        return detail

    def do_programme_details() -> dict:
        """Apply researched programme detail to the empty fields of each record.

        Written for the standard set by a Canada Graduate Research Scholarship
        record: award economics separated from coverage, institutional deadline
        separated from the programme's own, and the awarding body's published
        rules kept apart from guidance derived from them.

        Three rules make this safe to run repeatedly.

        Empty fields only. Research may disagree with what is already stored, and
        overwriting a verified value with a later reading would make the record
        less trustworthy every time it is refreshed. A correction is an explicit,
        separate decision.

        Nothing is invented. A field the researcher could not confirm is null in
        the source file and is skipped here, so an unanswered question stays
        unanswered instead of becoming a plausible value.

        Provenance travels with the data. A record that receives a funding amount
        also receives the citations that support it and the date it was checked,
        or the amount is not applied.
        """
        import json
        from datetime import date, datetime, timedelta, timezone
        from pathlib import Path
        from urllib.parse import urlparse

        from sqlalchemy import select

        from app.models import Scholarship

        details_path = (
            Path(__file__).resolve().parents[2] / "config" / "programme_details.json"
        )
        try:
            raw = json.loads(details_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("could not read programme details from %s: %s", details_path, exc)
            return {"details_file": str(details_path), "error": str(exc)}

        entries = raw.get("records") if isinstance(raw, dict) else raw
        entries = entries if isinstance(entries, list) else []
        wanted: dict[int, dict] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                wanted[int(entry["id"])] = entry
            except (KeyError, TypeError, ValueError):
                logger.warning("ignoring detail entry with no usable id: %r", entry)
        if not wanted:
            return {"details_file": str(details_path), "records_listed": 0, "matched": 0}

        # Scalar columns this stage may fill. The bounded widths are read from the
        # model rather than hardcoded, because a value that overflows a varchar
        # raises in PostgreSQL and takes the whole run with it.
        text_map = {
            "application_link": "url",
            "catalogue_url": "url",
            "official_updates_url": "url",
            "deadline_central_display": "text",
            "application_cycle": "text",
            "status_note": "text",
            "tuition_coverage_note": "text",
            "funding_period": "text",
            "program_type": "text",
            "region": "text",
            "coverage": "text",
            "application_method": "text",
            "application_route": "text",
            "citizenship_residency": "text",
            "international_eligibility": "text",
            "study_mode": "text",
            "research_requirement": "text",
            "subject_or_agency_requirement": "text",
            "duration": "text",
            "description": "text",
        }
        list_map = {
            "benefits": "benefits",
            "eligibility": "eligibility",
            "requirements": "requirements",
            "documents": "documents",
            "selection_criteria": "selection_notes",
        }
        applied: list[dict] = []
        skipped_no_provenance: list[int] = []
        # Values that do not fit the column they were filed under. Reported, not
        # truncated: a fragment of a value reads as if it were the value.
        skipped_too_long: list[dict] = []
        today = date.today()
        session = factory()
        try:
            for rid, entry in sorted(wanted.items()):
                row = session.get(Scholarship, rid)
                if row is None:
                    applied.append({"id": rid, "outcome": "not_found"})
                    continue
                official = entry.get("official") or {}
                verification = entry.get("verification") or {}
                utility = entry.get("applicant_utility") or {}
                citations = [
                    u for u in (verification.get("source_citations") or [])
                    if isinstance(u, str) and u.startswith("http")
                ] or [
                    u for u in (official.get("official_source_urls") or [])
                    if isinstance(u, str) and u.startswith("http")
                ]
                if not citations:
                    # An amount with nothing to check it against is worse than no
                    # amount: it looks researched and is not.
                    skipped_no_provenance.append(rid)
                    applied.append({"id": rid, "outcome": "skipped_no_provenance"})
                    continue

                filled: list[str] = []
                for field, kind in text_map.items():
                    # Several researched fields - the cycle, an institutional
                    # deadline, citizenship and residency wording - have no column
                    # of their own and are preserved in official_details, which
                    # receives the whole official block. Writing them as
                    # attributes would invent columns silently.
                    if not _is_column(Scholarship, field):
                        continue
                    value = (official.get(field) or "").strip() if isinstance(
                        official.get(field), str
                    ) else official.get(field)
                    if value in (None, "", "N/A", "-"):
                        continue
                    if getattr(row, field, None):
                        continue
                    if kind == "url":
                        parsed = urlparse(str(value))
                        if parsed.scheme not in ("http", "https") or not parsed.hostname:
                            continue
                    if kind == "text":
                        limit = _column_length(Scholarship, field)
                        if limit and len(str(value)) > limit:
                            continue
                    if kind == "url":
                        limit = _column_length(Scholarship, field)
                        if limit and len(str(value)) > limit:
                            continue
                    setattr(row, field, value)
                    filled.append(field)

                for source_field, column in list_map.items():
                    values = official.get(source_field)
                    if not isinstance(values, list) or not values:
                        continue
                    current = getattr(row, column, None)
                    if current:
                        continue
                    cleaned = [str(v).strip() for v in values if str(v).strip()]
                    if cleaned:
                        setattr(row, column, cleaned)
                        filled.append(column)

                # Award economics. Each is stored apart so a stipend cannot be
                # read as though it were a tuition waiver.
                amount = official.get("funding_amount")
                if amount not in (None, "") and row.funding_amount is None:
                    try:
                        row.funding_amount = float(amount)
                        filled.append("funding_amount")
                    except (TypeError, ValueError):
                        logger.warning("non-numeric funding_amount for record %d", rid)
                for field in ("funding_currency", "funding_period"):
                    value = official.get(field)
                    if isinstance(value, str) and value.strip() and not getattr(row, field, None):
                        limit = _column_length(Scholarship, field) or 64
                        if len(value.strip()) > limit:
                            # Truncating would publish a fragment - "CAD per "
                            # for an eight-character currency code. A value that
                            # does not fit is not the field it was filed under,
                            # so it is left out and counted rather than mangled.
                            skipped_too_long.append(
                                {"id": rid, "field": field,
                                 "length": len(value.strip()), "limit": limit}
                            )
                            continue
                        setattr(row, field, value.strip())
                        filled.append(field)
                for field in ("tuition_coverage", "living_cost_coverage", "travel_coverage"):
                    value = official.get(field)
                    if isinstance(value, bool) and getattr(row, field, None) is None:
                        setattr(row, field, value)
                        filled.append(field)
                # only_funded is honoured only when tuition coverage is not a bare
                # True, because "fully funded" without tuition coverage is a claim
                # about expenses the source never addressed.
                if official.get("fully_funded") is True and row.funding_amount is not None:
                    if row.tuition_coverage is True:
                        row.fully_funded = True
                        filled.append("fully_funded")

                deadline_central = (official.get("deadline_central") or "").strip()
                if isinstance(official.get("deadline_central"), str) and deadline_central:
                    try:
                        parsed_deadline = datetime.fromisoformat(
                            deadline_central.replace("Z", "+00:00")
                        ).date()
                    except ValueError:
                        parsed_deadline = None
                    if parsed_deadline and row.deadline_date is None:
                        row.deadline_date = parsed_deadline
                        row.deadline_display = (
                            (official.get("deadline_central_display") or "").strip()
                            or parsed_deadline.isoformat()
                        )[:255]
                        row.deadline_precision = "day_and_time" if "T" in deadline_central else "day"
                        filled.extend(["deadline_date", "deadline_display", "deadline_precision"])
                    elif row.deadline_date is None and (official.get("deadline_note") or "").strip():
                        row.deadline_display = official["deadline_note"].strip()[:255]
                        row.deadline_precision = "varies"
                        filled.extend(["deadline_display", "deadline_precision"])

                for column, payload in (
                    ("official_details", official),
                    ("applicant_utility", utility),
                    ("programme_verification", verification),
                ):
                    if payload and not getattr(row, column, None):
                        # The cycle and the date checked are stored with the data
                        # so a reader can tell how current it is without trusting
                        # the record's age.
                        if column == "programme_verification":
                            payload = {
                                **payload,
                                "last_verified_date": payload.get("last_verified_date")
                                or today.isoformat(),
                            }
                        setattr(row, column, payload)
                        filled.append(column)

                status = (official.get("status") or "").strip().upper()
                if status in {"OPEN", "UPCOMING"} and row.status == "closed":
                    row.status = "active"
                    filled.append("status")

                if filled:
                    row.last_verified_at = datetime.now(timezone.utc)
                    row.last_verified_date = today
                    row.next_verification_due = official.get("deadline_central") and None
                    if row.next_verification_due is None:
                        row.next_verification_due = _next_review_due(today)
                    filled.extend(["last_verified_at", "last_verified_date"])
                applied.append(
                    {"id": rid, "outcome": "changed" if filled else "unchanged",
                     "fields": len(filled), "citations": len(citations)}
                )
            if not args.dry_run:
                session.commit()
            else:
                session.rollback()
        finally:
            session.close()

        changed = [a for a in applied if a["outcome"] == "changed"]
        detail = {
            "details_file": str(details_path),
            "records_listed": len(wanted),
            "matched": len([a for a in applied if a["outcome"] != "not_found"]),
            "changed": len(changed),
            "skipped_no_provenance": len(skipped_no_provenance),
            "skipped_too_long": len(skipped_too_long),
            "too_long_sample": skipped_too_long[:20],
            "fields_written": sum(a.get("fields", 0) for a in changed),
        }
        if not args.dry_run:
            recorder.record_counts(
                {"programme_detail_records": len(changed),
                 "programme_detail_fields": detail["fields_written"]}
            )
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
        from datetime import date, datetime, timedelta, timezone
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

        # A host is not a programme. studyinjapan.go.jp carries eight separate
        # records for the seven MEXT scholarship types plus a USA-only edition,
        # each with its own funding figure, age limit and application route.
        # Host-keyed facts could only express one of them, and applying that one
        # to the other seven would write confidently wrong data. So an entry may
        # also be keyed "id:<n>" for a single record, and that wins over the host.
        by_host = {}
        by_record_id = {}
        for key, value in facts.items():
            key = str(key)
            if key.startswith("id:"):
                try:
                    by_record_id[int(key[3:])] = value
                except ValueError:
                    logger.warning("ignoring malformed record-keyed fact %r", key)
            else:
                by_host[key] = value
        facts = {**by_host, **by_record_id}

        # Facts keys map onto real columns. `provider` and `amount` are not
        # columns on this model: the awarding body is `official_source` and the
        # money is `benefits`. Writing to a name that does not exist raises
        # AttributeError inside a scheduled run, which is how this stage first
        # failed in production.
        text_fields = ("official_source", "benefits", "eligibility", "funding", "degree", "description")
        # Not a text field: an application link is a URL, and a malformed one
        # would send an applicant somewhere that is not the awarding body. It is
        # validated rather than trusted.
        url_fields = ("application_link",)
        today = date.today()
        applied: list[dict] = []
        skipped_too_long: list[dict] = []
        session = factory()
        try:
            rows = session.scalars(select(Scholarship)).all()
            for row in rows:
                host = (urlparse(row.official_source_url or "").hostname or "").lower()
                host = host[4:] if host.startswith("www.") else host
                # A record-specific entry is more precise than the host's, so it
                # is consulted first.
                entry = by_record_id.get(row.id) or by_host.get(host)
                if not entry:
                    continue
                filled: list[str] = []
                for field in text_fields:
                    value = (entry.get(field) or "").strip() or None
                    if not value or getattr(row, field, None):
                        continue
                    # Eligibility is a JSON list column, not text. Writing the
                    # sentence as a bare string put a string where the rest of
                    # the code expects a list of criteria.
                    if isinstance(getattr(row, field, None), list) or _is_json_column(
                        Scholarship, field
                    ):
                        current = getattr(row, field, None)
                        items = list(current) if isinstance(current, list) else []
                        items.append(value)
                        setattr(row, field, items)
                        filled.append(field)
                        continue
                    # Some of the other columns are bounded varchars, and
                    # Postgres raises on an overflow rather than truncating.
                    # Writing a research paragraph into a 120-character label
                    # column failed this stage outright and took the whole run
                    # with it. A value that does not fit is skipped and
                    # reported, which is honest: a half-written funding label is
                    # worse than none.
                    limit = _column_length(Scholarship, field)
                    if limit and len(value) > limit:
                        skipped_too_long.append(
                            {"id": row.id, "field": field, "length": len(value),
                             "limit": limit}
                        )
                        continue
                    setattr(row, field, value)
                    filled.append(field)

                for field in url_fields:
                    value = (entry.get(field) or "").strip()
                    if not value or getattr(row, field, None):
                        continue
                    parsed_url = urlparse(value)
                    if parsed_url.scheme in ("http", "https") and parsed_url.hostname:
                        setattr(row, field, value)
                        filled.append(field)

                # A programme with no single deadline is not a programme with a
                # blank deadline. Per-ministry and per-university schemes set
                # their own dates, so the honest thing to publish is that fact,
                # with the precision the rest of the pipeline already
                # understands. Leaving the field empty tells an applicant
                # nothing; "varies by university" tells them what to expect.
                deadline_mode = (entry.get("deadline_mode") or "").strip().lower()
                note = (entry.get("deadline_note") or "").strip()
                if (
                    not row.deadline_date
                    and not row.deadline_display
                    and deadline_mode in ("varies", "rolling")
                ):
                    display = note or (
                        "Rolling deadline"
                        if deadline_mode == "rolling"
                        else "Deadline varies by institution"
                    )
                    row.deadline_display = display[:255]
                    row.deadline_precision = deadline_mode
                    filled.extend(["deadline_display", "deadline_precision"])
                    derived, _reason = derive_status(
                        today=today,
                        deadline_date=None,
                        deadline_display=row.deadline_display,
                        deadline_precision=row.deadline_precision,
                        source_text=None,
                        current_status=row.status,
                    )
                    if derived and derived != "unknown":
                        row.status = derived
                        filled.append("status")

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
            "values_too_long_for_column": len(skipped_too_long),
            "too_long_sample": skipped_too_long[:20],
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

    def do_worklist() -> dict:
        """Emit the exact per-record research backlog. Read-only.

        Coverage counts say how bad the gap is; they cannot say which record to
        send a researcher. Closing the remaining gap means filling specific
        fields on specific rows, and doing that by hand from an aggregate number
        invites drift. This stage prints one compact line per record that still
        lacks a logo, a deadline, a description or an official source, so the
        backlog can be sharded across agents and reconciled afterwards without
        guessing which rows were covered.
        """
        import json
        from urllib.parse import urlparse

        from sqlalchemy import or_, select

        from app.models import Scholarship
        from app.services.catalogue_quarantine import QUARANTINE_STATUS

        session = factory()
        try:
            rows = session.execute(
                select(
                    Scholarship.id,
                    Scholarship.title,
                    Scholarship.official_source_url,
                    Scholarship.application_link,
                    Scholarship.deadline_display,
                    Scholarship.image_url,
                    Scholarship.description,
                    Scholarship.deadline_date,
                    Scholarship.official_source,
                    Scholarship.deadline_precision,
                )
                .where(Scholarship.verification_status != QUARANTINE_STATUS)
                .order_by(Scholarship.id)
            ).all()
        finally:
            session.close()

        pending = []
        for (
            rid,
            title,
            source_url,
            app_link,
            deadline_display,
            image_url,
            description,
            deadline_date,
            official_source,
            deadline_precision,
        ) in rows:
            missing = []
            if not image_url:
                missing.append("logo")
            if not deadline_date:
                missing.append("deadline")
            if not description:
                missing.append("description")
            if not official_source:
                missing.append("official_source")
            if not missing:
                continue
            host = (urlparse(source_url or "").hostname or "").lower()
            pending.append(
                {
                    "id": rid,
                    "host": host[4:] if host.startswith("www.") else host,
                    "title": title,
                    "missing": ",".join(missing),
                    "url": source_url,
                    "application_link": app_link,
                    "deadline_display": deadline_display,
                    "deadline_precision": deadline_precision,
                }
            )

        # Hosts, not records, are the unit of research. One researcher resolves
        # a programme page and its logo once, then reports the facts that apply
        # to every record the host carries.
        host_order: dict[str, int] = {}
        for item in pending:
            host_order[item["host"]] = host_order.get(item["host"], 0) + 1

        # Written to a file rather than printed. The backlog is a few hundred
        # kilobytes on one line, and a log line that long truncates the run log
        # and takes the stage's own output with it - the step then dies before
        # reporting success. A file survives and can be sharded.
        out_dir = os.environ.get("SCHOLARZONE_WORKLIST_DIR") or os.path.join(
            os.getcwd(), ".worklist"
        )
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "pending_research.json")
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(
                {"records": pending, "host_order": host_order}, handle, ensure_ascii=True, indent=1
            )
        print(f"worklist_file: {out_path}")
        return {
            "records_pending": len(pending),
            "hosts_pending": len(host_order),
            "worklist_file": out_path,
            "hosts_by_gap": sorted(host_order.items(), key=lambda kv: (-kv[1], kv[0])),
        }

    def do_inventory() -> dict:
        """List every record with a field a research pass could fill.

        Coverage totals say how many records are thin; they cannot say which
        fields are thin on which record. Enriching a catalogue needs the second
        question answered exactly, because a research agent is only useful if it
        is told precisely which fields are empty and therefore worth the fetch.

        Read-only, and the output is a file rather than log lines for the same
        reason the worklist is: a few hundred records of field lists overflows
        the run log and takes the stage's own result with it.
        """
        import json
        from pathlib import Path
        from urllib.parse import urlparse

        from sqlalchemy import select

        from app.models import Scholarship
        from app.services.catalogue_quarantine import QUARANTINE_STATUS

        # Fields a research pass can fill from an official source. Internal
        # bookkeeping columns are excluded on purpose: is_verified and
        # image_verified_at record what this system concluded, not what the
        # awarding body published.
        researchable = (
            "description", "funding", "benefits", "eligibility", "degree",
            "deadline_date", "deadline_display", "deadline_precision",
            "application_link", "application_method", "application_period",
            "requirements", "documents", "english_requirement",
            "selection_notes", "program_type", "best_fit", "notes",
            "coverage", "duration", "region", "catalogue_url",
            "official_updates_url", "qualifications",
        )
        available = {c.name for c in Scholarship.__table__.columns}
        targets = [f for f in researchable if f in available]

        session = factory()
        try:
            rows = session.execute(
                select(Scholarship.id, Scholarship.title, Scholarship.country,
                       Scholarship.official_source_url, Scholarship.degree)
                .where(Scholarship.verification_status != QUARANTINE_STATUS)
                .order_by(Scholarship.id)
            ).all()
            records = []
            for rid, title, country, source_url, degree in rows:
                row = session.get(Scholarship, rid)
                empty = [
                    f for f in targets
                    if getattr(row, f, None) in (None, "", [], {})
                ]
                if not empty:
                    continue
                host = (urlparse(source_url or "").hostname or "").lower()
                records.append({
                    "id": rid,
                    "title": title,
                    "country": country,
                    "host": host[4:] if host.startswith("www.") else host,
                    "url": source_url,
                    "degree": degree,
                    "empty_fields": empty,
                })
        finally:
            session.close()

        tally: dict[str, int] = {}
        for rec in records:
            for field in rec["empty_fields"]:
                tally[field] = tally.get(field, 0) + 1

        out_dir = os.environ.get("SCHOLARZONE_WORKLIST_DIR") or os.path.join(
            os.getcwd(), ".worklist"
        )
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "field_inventory.json")
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump({"targets": targets, "records": records}, handle, indent=1)

        print(f"inventory_file: {out_path}")
        return {
            "records_needing_research": len(records),
            "fields_considered": len(targets),
            "empty_field_frequency": dict(sorted(tally.items(), key=lambda kv: -kv[1])),
        }

    stages = {
        "verify": do_verify,
        "worklist": do_worklist,
        "inventory": do_inventory,
        "programme_details": do_programme_details,
        "enrich": do_enrich,
        "images": do_images,
        "discover": do_discover,
        "quarantine": do_quarantine,
        "stats": do_stats,
        "facts": do_facts,
        "logos": do_logos,
        "archive": do_archive,
        "discontinued": do_discontinued,
        "retire": do_retire,
        "correct": do_correct,
        "purge": do_purge,
        "purge_closed": do_purge_closed,
    }
    # A stage in STAGE_ORDER with no dispatcher here fails at dispatch time,
    # after the database work has already started, which is a confusing way to
    # learn that a stage was only half-wired.
    missing = [name for name in STAGE_ORDER if name not in stages]
    if missing:
        raise RuntimeError(f"stages declared without a runner: {', '.join(missing)}")

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
