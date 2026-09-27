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
from dataclasses import dataclass, field
from typing import Callable

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
    runtime_ms: float = 0.0

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
    ) -> None:
        self._session_factory = session_factory
        self.dry_run = dry_run
        self.batch_size = max(1, min(batch_size, MAX_BATCH_SIZE))
        self.only_missing = only_missing

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
            if ids:
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

        orchestrator = ImageDiscoveryOrchestrator(
            session_factory=self._session_factory,
            dry_run=self.dry_run,
        )

        processed = 0
        for index in range(0, len(rows), self.batch_size):
            batch = rows[index : index + self.batch_size]
            logger.info("image coverage batch: %d records", len(batch))
            for row in batch:
                scholarship_id, title, source_url, source_name, verified_at = row
                if verified_at is not None:
                    metrics.skipped_existing += 1
                    continue

                result = orchestrator.run(
                    scholarship_id=scholarship_id,
                    scholarship_title=title,
                    official_source_url=source_url,
                    official_source_name=source_name,
                )
                self._tally(metrics, result)
                processed += 1
                if progress is not None:
                    progress(processed, len(rows), result)

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
                "error": result.error,
            }
        )
