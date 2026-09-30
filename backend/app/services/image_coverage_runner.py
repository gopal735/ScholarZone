"""Catalogue-wide official image coverage runner.

Every scholarship must pass through official image discovery exactly once per
run. Records that already carry a verified image are never re-processed
automatically (``ImageVerifier`` enforces this as well), so the runner is safe
to invoke repeatedly and idempotent.

Reports a measurable coverage breakdown rather than claiming a percentage:

    already_present / newly_found / high / medium / low / none / failed / unchanged
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlparse

import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Scholarship
from .image_discovery import BROWSER_UA
from .image_discovery_orchestrator import (
    ImageDiscoveryOrchestrator,
    OrchestratorRunResult,
    TrustworthyImageStatus,
)
from .image_evaluation_status import (
    ImageEvaluationStatus,
    evaluation_status_for,
    preflight_status_for,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 40
# Bounded concurrency. Kept deliberately small: each worker performs real
# requests to official sites, so this is a politeness limit as much as a
# resource limit. The DomainRateLimiter remains the hard per-domain guard.
DEFAULT_MAX_WORKERS = 10

# Wall clock allowed per record for discovery. Matches the orchestrator default
# so an unset value behaves exactly as before.
DEFAULT_PER_RECORD_BUDGET_SECONDS = 90.0
MAX_WORKERS = 16
# A domain that has refused us this many times in a row is almost certainly
# blocking automated access rather than being temporarily unavailable. Without
# this, a catalogue sweep re-pays the full per-record budget once per record on
# the same blocked domain.
DOMAIN_FAILURE_THRESHOLD = 2

# Cheap reachability probe run before the full orchestrator. Most official sites
# in the catalogue answer 403 to automated requests, and discovering that with a
# full 5-phase crawl costs ~90s per record. One short probe settles it in ~2s.
PREFLIGHT_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class PreflightResult:
    reachable: bool
    status_code: int | None
    reason: str


def preflight_check(url: str | None, timeout: float = PREFLIGHT_TIMEOUT_SECONDS) -> PreflightResult:
    """Single cheap GET to decide whether the full crawl is worth attempting."""
    if not url:
        return PreflightResult(False, None, "no_source_url")
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": BROWSER_UA, "Accept": "text/html"},
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.TimeoutException:
        return PreflightResult(False, None, "timeout")
    except httpx.HTTPError as exc:
        return PreflightResult(False, None, "connection_error")
    except Exception:  # noqa: BLE001
        return PreflightResult(False, None, "unexpected")

    if response.status_code == 200:
        return PreflightResult(True, 200, "ok")
    if response.status_code in (403, 401, 412, 429):
        return PreflightResult(False, response.status_code, "blocked")
    if response.status_code == 404:
        return PreflightResult(True, 404, "page_missing_root_may_exist")
    return PreflightResult(True, response.status_code, "reachable")


@dataclass
class DomainCircuitBreaker:
    """Tracks per-domain hard failures so blocked domains are not hammered.

    This is a politeness mechanism, not a correctness shortcut: every skipped
    record is still reported as ``source_blocked`` so the outcome is never
    silently converted into "no image exists".
    """

    failures: dict[str, int] = field(default_factory=dict)
    open_domains: set[str] = field(default_factory=set)
    threshold: int = DOMAIN_FAILURE_THRESHOLD

    @staticmethod
    def domain_of(url: str | None) -> str:
        if not url:
            return ""
        return urlparse(url).netloc.lower().removeprefix("www.")

    def is_open(self, url: str | None) -> bool:
        return self.domain_of(url) in self.open_domains

    def record_success(self, url: str | None) -> None:
        domain = self.domain_of(url)
        if domain:
            self.failures.pop(domain, None)
            self.open_domains.discard(domain)

    def record_failure(self, url: str | None) -> bool:
        """Count a hard failure. Returns True when the domain just opened."""
        domain = self.domain_of(url)
        if not domain:
            return False
        count = self.failures.get(domain, 0) + 1
        self.failures[domain] = count
        if count >= self.threshold and domain not in self.open_domains:
            self.open_domains.add(domain)
            return True
        return False

    def report(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "open_domains": sorted(self.open_domains),
            "open_domain_count": len(self.open_domains),
        }


@dataclass
class ImageCoverageMetrics:
    """Coverage counters for one image run over a set of records."""

    records_in_scope: int = 0
    already_present: int = 0
    newly_found: int = 0
    high_confidence: int = 0
    medium_confidence: int = 0
    low_confidence: int = 0
    no_official_image: int = 0
    failed: int = 0
    skipped_existing: int = 0
    persisted: int = 0
    # Distinguishes "we looked and the page genuinely has no usable image" from
    # "the site refused us", which is a source-access failure, not a true
    # no-image result.
    source_blocked: int = 0
    source_unreachable: int = 0
    # Records skipped because their whole domain is a confirmed bot block.
    domain_blocked_skipped: int = 0
    runtime_ms: float = 0.0
    circuit_breaker: dict[str, object] = field(default_factory=dict)
    # Set when the run was planned rather than executed. A dry run makes no
    # network request, so its counters describe scope, not work performed.
    dry_run: bool = False
    # True when scope was reported without any network request at all.
    planned_only: bool = False

    # Per-record outcomes for auditing.
    outcomes: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "records_in_scope": self.records_in_scope,
            "already_present": self.already_present,
            "newly_found": self.newly_found,
            "high_confidence": self.high_confidence,
            "medium_confidence": self.medium_confidence,
            "low_confidence": self.low_confidence,
            "no_official_image": self.no_official_image,
            "failed": self.failed,
            "skipped_existing": self.skipped_existing,
            "persisted": self.persisted,
            "source_blocked": self.source_blocked,
            "source_unreachable": self.source_unreachable,
            "domain_blocked_skipped": self.domain_blocked_skipped,
            "circuit_breaker": self.circuit_breaker,
            "dry_run": self.dry_run,
            "planned_only": self.planned_only,
            "runtime_ms": round(self.runtime_ms, 1),
        }


class ImageCoverageRunner:
    """Run official image discovery across the catalogue in bounded batches."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        dry_run: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        only_missing: bool = True,
        max_workers: int = DEFAULT_MAX_WORKERS,
        preflight_fn=None,
        exclude_quarantined: bool = True,
        skip_terminally_evaluated: bool = False,
        plan_only: bool = False,
        logo_only: bool = False,
        per_record_budget_seconds: float | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.dry_run = dry_run
        self._logo_only = logo_only
        # Per-record wall clock for discovery. This is the single biggest
        # throughput lever in a catalogue-wide sweep: a record whose site blocks
        # us otherwise burns the full default budget before giving up, so a
        # sweep over blocked hosts costs the budget times the record count no
        # matter how much concurrency is available. A blocked site fails fast
        # and the slot is reused; a site that answers still gets its full
        # budget, so nothing is lost except waiting on hosts that were never
        # going to return an image.
        self._per_record_budget_seconds = per_record_budget_seconds
        self.plan_only = plan_only
        self.batch_size = max(1, min(batch_size, MAX_BATCH_SIZE))
        self.only_missing = only_missing
        self.max_workers = max(1, min(max_workers, MAX_WORKERS))
        self.exclude_quarantined = exclude_quarantined
        # A record that already reached a terminal outcome must not be crawled
        # again: re-running a confirmed negative costs a full request budget and
        # changes nothing.
        self.skip_terminally_evaluated = skip_terminally_evaluated
        # Injectable so tests never perform real network access.
        self._preflight_fn = preflight_fn or preflight_check

    def _record_evaluation(self, scholarship_id: int, status: str) -> None:
        """Persist one record's terminal image outcome.

        A record that already carries a verified image is never downgraded: the
        evaluator's own write is the authority, and a later negative outcome
        must not erase a good image. Dry runs never write.
        """
        if self.dry_run:
            return
        session = self._session_factory()
        try:
            row = session.get(Scholarship, scholarship_id)
            if row is None or row.image_verified_at is not None:
                return
            row.image_evaluation_status = str(status)
            row.image_evaluated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception:  # noqa: BLE001 - auditing must not abort a sweep
            session.rollback()
            logger.exception("failed to record image evaluation for id=%s", scholarship_id)
        finally:
            session.close()

    def _in_scope_ids(
        self,
        *,
        ids: list[int] | None,
        start_after: int | None,
        limit: int | None,
    ) -> tuple[list[tuple[int, str | None, str | None, str | None, bool]], int]:
        session = self._session_factory()
        try:
            stmt = select(
                Scholarship.id,
                Scholarship.title,
                Scholarship.official_source_url,
                Scholarship.official_source,
                Scholarship.image_verified_at,
                Scholarship.verification_status,
            )
            # Quarantined rows are site landing pages, not scholarships. They are
            # never a valid image target, so they are excluded from scope rather
            # than being reported as "no trustworthy image" for a programme that
            # does not exist.
            if self.exclude_quarantined:
                stmt = stmt.where(Scholarship.verification_status != "quarantined")
            if ids is not None:
                # An explicit empty list means "nothing selected". Falling
                # through would silently process the whole catalogue.
                if not ids:
                    return [], 0
                stmt = stmt.where(Scholarship.id.in_(ids))
            if start_after is not None:
                stmt = stmt.where(Scholarship.id > start_after)
            if self.only_missing:
                stmt = stmt.where(Scholarship.image_verified_at.is_(None))
            if self.skip_terminally_evaluated:
                from .image_evaluation_status import TERMINAL_STATUSES

                stmt = stmt.where(
                    Scholarship.image_evaluation_status.is_(None)
                    | Scholarship.image_evaluation_status.not_in(tuple(TERMINAL_STATUSES))
                )
            stmt = stmt.order_by(Scholarship.id)
            rows = list(session.execute(stmt).all())
            total_in_scope = len(rows)
            if limit is not None:
                rows = rows[:limit]
            return rows, total_in_scope
        finally:
            session.close()

    def run(
        self,
        *,
        ids: list[int] | None = None,
        limit: int | None = None,
        start_after: int | None = None,
        progress: Callable[[int, int, OrchestratorRunResult], None] | None = None,
    ) -> ImageCoverageMetrics:
        started = time.monotonic()
        rows, total_in_scope = self._in_scope_ids(ids=ids, start_after=start_after, limit=limit)
        metrics = ImageCoverageMetrics(records_in_scope=total_in_scope)

        # Each worker owns its own orchestrator and session: a record's DB work
        # must never be interleaved with another record's.
        breaker = DomainCircuitBreaker()

        # Reachability is a property of a *domain*, not of a page. The
        # catalogue has hundreds of records spread over far fewer providers, so
        # probing each record separately repeated the same request many times
        # over for no additional information. One probe per domain per run is
        # equally correct and much cheaper.
        #
        # This is a same-run cache only. It is deliberately not persisted: a
        # domain that was unreachable an hour ago may be reachable now, and
        # caching that judgement across runs would turn a temporary outage into
        # a permanent silent skip.
        preflight_cache: dict[str, object] = {}

        def _work(row) -> tuple[OrchestratorRunResult | None, int, str | None]:
            scholarship_id, title, source_url, source_name, verified_at = row[:5]
            if verified_at is not None:
                return None, scholarship_id, None
            if breaker.is_open(source_url):
                return None, scholarship_id, "domain_blocked"

            # Cheap gate first: do not pay the full crawl budget to discover
            # that the domain blocks us. The verdict is cached per domain for
            # the life of this run.
            domain = breaker.domain_of(source_url)
            probe = preflight_cache.get(domain)
            if probe is None:
                probe = self._preflight_fn(source_url)
                if domain:
                    preflight_cache[domain] = probe
            if not probe.reachable:
                if breaker.record_failure(source_url):
                    logger.info("domain %s opened as blocked (preflight)", breaker.domain_of(source_url))
                return None, scholarship_id, f"preflight:{probe.reason}"

            orchestrator = ImageDiscoveryOrchestrator(
                session_factory=self._session_factory,
                dry_run=self.dry_run,
                logo_only=self._logo_only,
                total_budget_seconds=(
                    self._per_record_budget_seconds
                    if self._per_record_budget_seconds is not None
                    else DEFAULT_PER_RECORD_BUDGET_SECONDS
                ),
            )
            result = orchestrator.run(
                scholarship_id=scholarship_id,
                scholarship_title=title,
                official_source_url=source_url,
                official_source_name=source_name,
            )
            return result, scholarship_id, source_url

        processed = 0
        skipped_ids: set[int] = set()

        if self.plan_only:
            # Plan-only is strictly weaker than dry_run: it makes no network
            # request at all and only reports scope.
            #
            # This exists because the worker's `--dry-run` promises "plans only,
            # writes nothing", and previously the image stage still probed and
            # crawled every in-scope record - about nine of the run's ten
            # minutes - which made that promise misleading and wasted the free
            # tier's request budget to produce a number nobody could act on.
            #
            # `dry_run` keeps its original meaning (fetch for measurement,
            # persist nothing) because callers depend on those counters.
            metrics.records_in_scope = len(rows)
            metrics.dry_run = True
            metrics.planned_only = True
            return metrics

        for index in range(0, len(rows), self.batch_size):
            batch = rows[index : index + self.batch_size]
            # Record-level breaker check: domains opened while a previous batch
            # was running are skipped here, not merely on the next batch.
            pending = []
            for row in batch:
                sid, title, source_url = row[0], row[1], row[2]
                verified_at = row[4]
                if verified_at is not None:
                    skipped_ids.add(sid)
                    continue
                if breaker.is_open(source_url):
                    metrics.domain_blocked_skipped += 1
                    self._record_evaluation(
                        sid, ImageEvaluationStatus.SOURCE_BLOCKED
                    )
                    metrics.outcomes.append(
                        {
                            "scholarship_id": sid,
                            "title": (title or "")[:80],
                            "status": "source_blocked",
                            "image_url": None,
                            "persisted": False,
                            "candidates": 0,
                            "requests_made": 0,
                            "page_error": "domain_blocked_after_repeated_failures",
                            "timed_out": False,
                            "error": None,
                        }
                    )
                    processed += 1
                    continue
                pending.append(row)

            if not pending:
                continue

            logger.info(
                "image coverage batch %d: %d of %d records (workers=%d, open_domains=%d)",
                index // self.batch_size + 1,
                len(pending),
                len(batch),
                self.max_workers,
                len(breaker.open_domains),
            )
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {pool.submit(_work, row): row for row in pending}
                for future in as_completed(futures):
                    row = futures[future]
                    sid, title, source_url = row[0], row[1], row[2]
                    try:
                        result, sid, url = future.result()
                    except Exception as exc:  # noqa: BLE001 - one record must not kill the batch
                        logger.exception("image discovery crashed for id=%s", sid)
                        metrics.failed += 1
                        self._record_evaluation(sid, ImageEvaluationStatus.ERROR)
                        metrics.outcomes.append(
                            {
                                "scholarship_id": sid,
                                "title": (title or "")[:80],
                                "status": "error",
                                "image_url": None,
                                "persisted": False,
                                "candidates": 0,
                                "requests_made": 0,
                                "page_error": None,
                                "timed_out": False,
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                        )
                        processed += 1
                        continue

                    if result is None:
                        sid_reason = url or ""
                        if sid_reason.startswith("preflight:"):
                            reason = sid_reason.split(":", 1)[1]
                            if reason in ("blocked", "timeout", "connection_error", "unexpected"):
                                metrics.source_blocked += 1
                                status = "source_blocked"
                            else:
                                metrics.source_unreachable += 1
                                status = "source_unreachable"
                            metrics.outcomes.append(
                                {
                                    "scholarship_id": sid,
                                    "title": (title or "")[:80],
                                    "status": status,
                                    "image_url": None,
                                    "persisted": False,
                                    "candidates": 0,
                                    "requests_made": 1,
                                    "page_error": f"preflight_{reason}",
                                    "timed_out": reason == "timeout",
                                    "error": None,
                                }
                            )
                            self._record_evaluation(sid, preflight_status_for(reason))
                        elif sid_reason == "domain_blocked":
                            metrics.domain_blocked_skipped += 1
                            self._record_evaluation(
                                sid, ImageEvaluationStatus.SOURCE_BLOCKED
                            )
                            metrics.outcomes.append(
                                {
                                    "scholarship_id": sid,
                                    "title": (title or "")[:80],
                                    "status": "source_blocked",
                                    "image_url": None,
                                    "persisted": False,
                                    "candidates": 0,
                                    "requests_made": 0,
                                    "page_error": "domain_blocked_after_repeated_failures",
                                    "timed_out": False,
                                    "error": None,
                                }
                            )
                        else:
                            metrics.skipped_existing += 1
                        processed += 1
                        continue

                    self._tally(metrics, result)
                    self._record_evaluation(
                        sid,
                        evaluation_status_for(
                            trusted_status=result.status.value,
                            candidate_count=len(result.image_results),
                            page_error=getattr(result.page_discovery, "error", None),
                            timed_out=bool(
                                getattr(result.page_discovery, "timed_out", False)
                            ),
                            requests_made=result.requests_made,
                        ),
                    )

                    # Feed the breaker: only genuine access failures count.
                    page_error = getattr(result.page_discovery, "error", None)
                    if page_error or getattr(result.page_discovery, "timed_out", False) or result.requests_made == 0:
                        if breaker.record_failure(source_url):
                            logger.info("domain %s opened as blocked", breaker.domain_of(source_url))
                    else:
                        breaker.record_success(source_url)

                    processed += 1
                    if progress is not None:
                        progress(processed, len(rows), result)

        metrics.circuit_breaker = breaker.report()
        metrics.runtime_ms = (time.monotonic() - started) * 1000.0
        return metrics

    @staticmethod
    def _tally(metrics: ImageCoverageMetrics, result: OrchestratorRunResult) -> None:
        has_candidate = bool(result.image_results)
        best_url = (
            result.new_image_url
            or (result.image_results[0].image_url if result.image_results else None)
        )

        if result.status == TrustworthyImageStatus.HIGH:
            metrics.high_confidence += 1
        elif result.status == TrustworthyImageStatus.MEDIUM:
            metrics.medium_confidence += 1
        elif result.status == TrustworthyImageStatus.LOW:
            metrics.low_confidence += 1
        elif result.status == TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE:
            # Distinguish a genuine absence from an access failure: a blocked or
            # unreachable source is not evidence that no image exists.
            page_error = (getattr(result.page_discovery, "error", None) or "").lower()
            timed_out = bool(getattr(result.page_discovery, "timed_out", False))
            if page_error:
                metrics.source_unreachable += 1
            elif timed_out or result.requests_made == 0:
                metrics.source_blocked += 1
            else:
                metrics.no_official_image += 1
        elif result.status in (TrustworthyImageStatus.ERROR, TrustworthyImageStatus.SKIPPED):
            metrics.failed += 1

        # "newly_found" counts trustworthy candidates discovered, which is
        # meaningful in a dry run. "persisted" counts actual writes, which is
        # only non-zero when dry_run=False.
        if result.status in (TrustworthyImageStatus.HIGH, TrustworthyImageStatus.MEDIUM) and has_candidate:
            metrics.newly_found += 1
        if result.persisted and result.new_image_url:
            metrics.persisted += 1
        elif result.previous_image_url:
            metrics.already_present += 1

        metrics.outcomes.append(
            {
                "scholarship_id": result.scholarship_id,
                "title": result.scholarship_title[:80],
                "status": result.status.value,
                "image_url": best_url,
                "persisted": result.persisted,
                "candidates": len(result.image_results),
                "requests_made": result.requests_made,
                "page_error": getattr(result.page_discovery, "error", None),
                "timed_out": bool(getattr(result.page_discovery, "timed_out", False)),
                "error": result.error,
            }
        )
