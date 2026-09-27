"""Bounded, resumable batch runner for scholarship enrichment.

Wraps :class:`ScholarshipEnrichmentService` with the operational concerns the
catalogue scale requires:

* bounded batches with a caller-supplied size
* deterministic ordering so a run can be resumed from a cursor
* per-record isolation (one failure never aborts the batch)
* retry accounting separated from hard source failures
* cumulative metrics suitable for an operational report

This is a library, not a script: the same entry point serves the internal API,
the scheduled workflow, and tests.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Scholarship
from .discovery_scheduler import DomainRateLimiter
from .scholarship_enrichment import (
    EnrichmentOutcome,
    EnrichmentResult,
    ScholarshipEnrichmentService,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 15
MAX_BATCH_SIZE = 50


@dataclass
class EnrichmentMetrics:
    """Cumulative counters for one enrichment run."""

    records_scanned: int = 0
    records_enriched: int = 0
    records_unchanged: int = 0
    fields_updated: int = 0
    fields_skipped: int = 0
    status_changes: int = 0
    deadline_changes: int = 0
    source_failures: int = 0
    retry_failures: int = 0
    no_official_source: int = 0
    not_authoritative: int = 0
    no_usable_extraction: int = 0
    hard_errors: int = 0
    retry_attempts: int = 0
    total_fetch_attempts: int = 0
    runtime_ms: float = 0.0

    # field_name -> number of times written
    field_update_counts: dict[str, int] = field(default_factory=dict)

    def record(self, result: EnrichmentResult) -> None:
        self.records_scanned += 1
        self.total_fetch_attempts += result.fetch_attempts
        if result.fetch_attempts > 1:
            self.retry_attempts += 1

        for update in result.updates:
            if update.action in ("merged", "filled", "replaced"):
                self.fields_updated += 1
                self.field_update_counts[update.field_name] = (
                    self.field_update_counts.get(update.field_name, 0) + 1
                )
            elif update.action == "skipped":
                self.fields_skipped += 1

        if result.status_changed:
            self.status_changes += 1

        for update in result.updates:
            if update.field_name in ("deadline_display", "deadline_precision") and update.action in (
                "merged",
                "filled",
                "replaced",
            ):
                self.deadline_changes += 1
                break

        if result.outcome == EnrichmentOutcome.ENRICHED:
            self.records_enriched += 1
        elif result.outcome == EnrichmentOutcome.UNCHANGED:
            self.records_unchanged += 1
        elif result.outcome == EnrichmentOutcome.SOURCE_UNAVAILABLE:
            self.source_failures += 1
            if result.retryable:
                self.retry_failures += 1
        elif result.outcome == EnrichmentOutcome.NO_OFFICIAL_SOURCE:
            self.no_official_source += 1
        elif result.outcome == EnrichmentOutcome.NOT_AUTHORITATIVE:
            self.not_authoritative += 1
        elif result.outcome == EnrichmentOutcome.NO_USABLE_EXTRACTION:
            self.no_usable_extraction += 1
        elif result.outcome == EnrichmentOutcome.ERROR:
            self.hard_errors += 1

    def as_dict(self) -> dict[str, object]:
        return {
            "records_scanned": self.records_scanned,
            "records_enriched": self.records_enriched,
            "records_unchanged": self.records_unchanged,
            "fields_updated": self.fields_updated,
            "fields_skipped": self.fields_skipped,
            "status_changes": self.status_changes,
            "deadline_changes": self.deadline_changes,
            "source_failures": self.source_failures,
            "retry_failures": self.retry_failures,
            "no_official_source": self.no_official_source,
            "not_authoritative": self.not_authoritative,
            "no_usable_extraction": self.no_usable_extraction,
            "hard_errors": self.hard_errors,
            "retry_attempts": self.retry_attempts,
            "total_fetch_attempts": self.total_fetch_attempts,
            "runtime_ms": round(self.runtime_ms, 1),
            "field_update_counts": dict(sorted(self.field_update_counts.items())),
        }


@dataclass
class EnrichmentRunReport:
    """Result of a batch run: aggregate metrics plus per-record detail."""

    metrics: EnrichmentMetrics
    results: list[EnrichmentResult] = field(default_factory=list)
    batch_count: int = 0
    dry_run: bool = True
    last_id: int | None = None

    def failures(self) -> list[EnrichmentResult]:
        return [r for r in self.results if r.outcome == EnrichmentOutcome.SOURCE_UNAVAILABLE]

    def as_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "batch_count": self.batch_count,
            "last_id": self.last_id,
            "metrics": self.metrics.as_dict(),
            "failures": [
                {
                    "scholarship_id": r.scholarship_id,
                    "source_url": r.source_url,
                    "error": r.fetch_error,
                    "retryable": r.retryable,
                    "attempts": r.fetch_attempts,
                }
                for r in self.failures()
            ],
        }


class EnrichmentBatchRunner:
    """Run enrichment over the catalogue in bounded, resumable batches."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        dry_run: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_attempts: int = 2,
        rate_limiter: DomainRateLimiter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.dry_run = dry_run
        self.batch_size = max(1, min(batch_size, MAX_BATCH_SIZE))
        self.rate_limiter = rate_limiter or DomainRateLimiter(min_interval_seconds=1.0)
        self._service = ScholarshipEnrichmentService(
            session_factory,
            dry_run=dry_run,
            rate_limiter=self.rate_limiter,
            max_attempts=max_attempts,
        )

    def list_ids(
        self,
        *,
        ids: Iterable[int] | None = None,
        start_after: int | None = None,
        limit: int | None = None,
        only_missing_source: bool = False,
    ) -> list[int]:
        """Deterministic, resumable id selection."""
        session = self._session_factory()
        try:
            stmt = select(Scholarship.id)
            if ids is not None:
                id_list = list(ids)
                if not id_list:
                    return []
                stmt = stmt.where(Scholarship.id.in_(id_list))
            else:
                if only_missing_source:
                    stmt = stmt.where(Scholarship.official_source_url.is_(None))
                if start_after is not None:
                    stmt = stmt.where(Scholarship.id > start_after)
            stmt = stmt.order_by(Scholarship.id)
            if limit is not None:
                stmt = stmt.limit(limit)
            return list(session.scalars(stmt).all())
        finally:
            session.close()

    def run(
        self,
        *,
        ids: Iterable[int] | None = None,
        limit: int | None = None,
        start_after: int | None = None,
        only_missing_source: bool = False,
        progress: Callable[[int, int, EnrichmentResult], None] | None = None,
    ) -> EnrichmentRunReport:
        """Execute the run. Records are processed one at a time, in id order."""
        started = time.monotonic()
        target_ids = self.list_ids(
            ids=ids,
            start_after=start_after,
            limit=limit,
            only_missing_source=only_missing_source,
        )
        metrics = EnrichmentMetrics()
        results: list[EnrichmentResult] = []
        batch_count = 0
        last_id = start_after

        for index in range(0, len(target_ids), self.batch_size):
            batch = target_ids[index : index + self.batch_size]
            batch_count += 1
            logger.info("enrichment batch %d: %d records", batch_count, len(batch))
            for scholarship_id in batch:
                result = self._service.enrich_one(scholarship_id)
                metrics.record(result)
                results.append(result)
                last_id = scholarship_id
                if progress is not None:
                    progress(index + len(batch), len(target_ids), result)

        metrics.runtime_ms = (time.monotonic() - started) * 1000.0
        return EnrichmentRunReport(
            metrics=metrics,
            results=results,
            batch_count=batch_count,
            dry_run=self.dry_run,
            last_id=last_id,
        )
