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
from typing import Callable
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Scholarship
from .image_discovery_orchestrator import (
    ImageDiscoveryOrchestrator,
    OrchestratorRunResult,
    TrustworthyImageStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 40
# Bounded concurrency. Kept deliberately small: each worker performs real
# requests to official sites, so this is a politeness limit as much as a
# resource limit. The DomainRateLimiter remains the hard per-domain guard.
DEFAULT_MAX_WORKERS = 10
MAX_WORKERS = 16
# A domain that has refused us this many times in a row is almost certainly
# blocking automated access rather than being temporarily unavailable. Without
# this, a catalogue sweep re-pays the full per-record budget once per record on
# the same blocked domain.
DOMAIN_FAILURE_THRESHOLD = 2


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
    ) -> None:
        self._session_factory = session_factory
        self.dry_run = dry_run
        self.batch_size = max(1, min(batch_size, MAX_BATCH_SIZE))
        self.only_missing = only_missing
        self.max_workers = max(1, min(max_workers, MAX_WORKERS))

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
            )
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

        def _work(row) -> tuple[OrchestratorRunResult | None, int, str | None]:
            scholarship_id, title, source_url, source_name, verified_at = row
            if verified_at is not None:
                return None, scholarship_id, None
            if breaker.is_open(source_url):
                return None, scholarship_id, "domain_blocked"
            orchestrator = ImageDiscoveryOrchestrator(
                session_factory=self._session_factory,
                dry_run=self.dry_run,
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
        for index in range(0, len(rows), self.batch_size):
            batch = rows[index : index + self.batch_size]
            # Record-level breaker check: domains opened while a previous batch
            # was running are skipped here, not merely on the next batch.
            pending = []
            for row in batch:
                sid, title, source_url, source_name, verified_at = row
                if verified_at is not None:
                    skipped_ids.add(sid)
                    continue
                if breaker.is_open(source_url):
                    metrics.domain_blocked_skipped += 1
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
                        metrics.skipped_existing += 1
                        processed += 1
                        continue

                    self._tally(metrics, result)

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
