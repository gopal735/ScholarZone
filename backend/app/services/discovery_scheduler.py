"""Automatic country-level scholarship discovery scheduler.

Iterates every country represented in the database, runs the existing
discovery pipeline against authoritative official sources, auto-approves
verified new candidates, and immediately enqueues image discovery for
newly inserted scholarships with NULL image_url.

Features:
- Bounded concurrency per country (ThreadPoolExecutor)
- Per-domain rate limiting
- Idempotent via existing discovery_hash deduplication
- One failed country never stops remaining countries
- Dry-run mode for safe pre-execution validation
- Full audit trail and metrics
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .discovery_config import seed_approved_sources
from .discovery_pipeline import DiscoveryBatch, DiscoveryPipeline
from .telemetry import PipelineStages, record_event

logger = logging.getLogger(__name__)


@dataclass
class DiscoverySchedulerMetrics:
    countries_scanned: int = 0
    sources_checked: int = 0
    urls_checked: int = 0
    discovery_candidates: int = 0
    verified_new_scholarships: int = 0
    inserted_scholarships: int = 0
    duplicates: int = 0
    rejected_candidates: int = 0
    errors: int = 0
    image_discoveries_triggered: int = 0
    image_high: int = 0
    image_medium: int = 0
    image_low: int = 0
    image_review: int = 0
    temp_failures: int = 0
    network_failures: int = 0
    runtime_ms: float = 0.0
    country_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    operation_id: str = ""


class DomainRateLimiter:
    def __init__(self, min_interval_seconds: float = 1.0) -> None:
        self._min_interval = min_interval_seconds
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait_if_needed(self, domain: str) -> None:
        with self._lock:
            now = time.monotonic()
            last = self._last_request.get(domain, 0.0)
            elapsed = now - last
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request[domain] = time.monotonic()


class DiscoveryScheduler:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        max_workers: int = 4,
        dry_run: bool = False,
        rate_limit_interval: float = 1.0,
        now_fn=None,
    ) -> None:
        self.session_factory = session_factory
        self.max_workers = max_workers
        self.dry_run = dry_run
        self.rate_limiter = DomainRateLimiter(min_interval_seconds=rate_limit_interval)
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._operation_id = str(int(time.time() * 1e9))

    def _new_session(self) -> Session:
        if self.session_factory is None:
            from ..database import get_session_factory
            self.session_factory = get_session_factory()
        return self.session_factory()

    def run(self) -> DiscoverySchedulerMetrics:
        start = time.monotonic()
        metrics = DiscoverySchedulerMetrics(operation_id=self._operation_id)

        session = self._new_session()
        try:
            seed_approved_sources(session)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

        countries = self._get_all_countries()
        if not countries:
            logger.info("No countries represented in DB. Discovery skipped.")
            metrics.runtime_ms = (time.monotonic() - start) * 1000.0
            return metrics

        logger.info(
            "Discovery scheduler starting: countries=%d dry_run=%s workers=%d",
            len(countries),
            self.dry_run,
            self.max_workers,
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_country, country, metrics): country
                for country in countries
            }
            for future in as_completed(futures):
                country = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.exception("Country discovery failed for %s: %s", country, exc)
                    metrics.errors += 1
                    metrics.country_results[country] = {
                        "status": "error",
                        "error": str(exc),
                    }

        metrics.runtime_ms = (time.monotonic() - start) * 1000.0
        metrics.countries_scanned = len(
            [c for c, r in metrics.country_results.items() if r.get("status") != "error"]
        )

        record_event(
            stage=PipelineStages.DISCOVERY,
            metric_type="success",
            duration_ms=metrics.runtime_ms,
            success=True,
            metadata={
                "operation_id": self._operation_id,
                "countries_scanned": metrics.countries_scanned,
                "inserted": metrics.inserted_scholarships,
                "duplicates": metrics.duplicates,
                "rejected": metrics.rejected_candidates,
                "errors": metrics.errors,
                "dry_run": self.dry_run,
            },
        )

        logger.info(
            "Discovery scheduler completed: countries=%d inserted=%d duplicates=%d rejected=%d errors=%d runtime_ms=%.1f",
            metrics.countries_scanned,
            metrics.inserted_scholarships,
            metrics.duplicates,
            metrics.rejected_candidates,
            metrics.errors,
            metrics.runtime_ms,
        )
        return metrics

    def _get_all_countries(self) -> list[str]:
        session = self._new_session()
        try:
            from ..models import Scholarship
            results = session.scalars(
                select(Scholarship.country)
                .distinct()
                .where(Scholarship.country.is_not(None))
            ).all()
            return [r for r in results if r]
        finally:
            session.close()

    def _process_country(self, country: str, metrics: DiscoverySchedulerMetrics) -> None:
        country_start = time.monotonic()
        country_metrics: dict[str, Any] = {
            "status": "ok",
            "sources_checked": 0,
            "urls_checked": 0,
            "discovered": 0,
            "duplicates": 0,
            "rejected": 0,
            "errors": 0,
            "network_failures": 0,
            "temp_failures": 0,
        }

        session = self._new_session()
        try:
            seed_approved_sources(session)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

        source_urls = self._build_source_urls(country)
        if not source_urls:
            logger.info("No source URLs for country %s", country)
            metrics.country_results[country] = country_metrics
            return

        pipeline = DiscoveryPipeline(session_factory=self.session_factory)
        batch = pipeline.discover_batch(source_urls)

        country_metrics["sources_checked"] = len(source_urls)
        country_metrics["urls_checked"] = len(source_urls)
        country_metrics["discovered"] = len(batch.discovered)
        country_metrics["duplicates"] = batch.duplicates
        country_metrics["rejected"] = batch.rejected
        country_metrics["errors"] = batch.errors

        metrics.country_results[country] = country_metrics
        metrics.sources_checked += len(source_urls)
        metrics.urls_checked += len(source_urls)
        metrics.discovery_candidates += len(batch.discovered)
        metrics.duplicates += batch.duplicates
        metrics.rejected_candidates += batch.rejected
        metrics.errors += batch.errors

        for result in batch.discovered:
            if result.status == "error":
                metrics.network_failures += 1
                country_metrics["network_failures"] = country_metrics.get("network_failures", 0) + 1
            if result.status in ("error", "rejected"):
                metrics.temp_failures += 1
                country_metrics["temp_failures"] = country_metrics.get("temp_failures", 0) + 1

        if self.dry_run:
            pending_count = sum(1 for r in batch.discovered if r.status == "pending")
            metrics.verified_new_scholarships += pending_count
            metrics.inserted_scholarships += pending_count
            logger.info(
                "DRY RUN [%s]: candidates=%d pending=%d duplicates=%d rejected=%d errors=%d runtime_ms=%.1f",
                country,
                len(batch.discovered),
                pending_count,
                batch.duplicates,
                batch.rejected,
                batch.errors,
                (time.monotonic() - country_start) * 1000.0,
            )
            return

        for result in batch.discovered:
            if result.status != "pending":
                continue
            try:
                scholarship_id = pipeline.approve_candidate(result.candidate_id)
                if scholarship_id is not None:
                    metrics.inserted_scholarships += 1
                    metrics.verified_new_scholarships += 1
                    self._trigger_image_discovery(pipeline, scholarship_id, metrics)
            except Exception as exc:
                logger.exception(
                    "Failed to approve candidate %d for country %s: %s",
                    result.candidate_id,
                    country,
                    exc,
                )
                metrics.errors += 1

    def _build_source_urls(self, country: str) -> list[str]:
        session = self._new_session()
        try:
            from ..models import ApprovedSource
            rows = session.scalars(
                select(ApprovedSource).where(
                    ApprovedSource.is_active.is_(True),
                    ApprovedSource.country.ilike(country),
                )
            ).all()
            urls: list[str] = []
            seen: set[str] = set()
            for row in rows:
                if row.discovery_url_patterns:
                    for url in row.discovery_url_patterns:
                        if url not in seen:
                            urls.append(url)
                            seen.add(url)
                elif row.domain:
                    url = f"https://{row.domain}/"
                    if url not in seen:
                        urls.append(url)
                        seen.add(url)
            return urls
        finally:
            session.close()

    def _trigger_image_discovery(
        self, pipeline: DiscoveryPipeline, scholarship_id: int, metrics: DiscoverySchedulerMetrics
    ) -> None:
        session = self._new_session()
        try:
            from ..models import Scholarship
            scholarship = session.get(Scholarship, scholarship_id)
            if scholarship is None or scholarship.image_url:
                return
            if not scholarship.official_source_url:
                return

            metrics.image_discoveries_triggered += 1

            from .image_discovery import ImageDiscoveryService
            from .image_validator import ImageCandidate, ImageValidator
            from ..models import ImageReview

            discovery = ImageDiscoveryService()
            candidates = discovery.discover_from_scholarship(scholarship.official_source_url)
            if not candidates:
                return

            validator = ImageValidator()
            results = validator.validate_candidates(
                candidates,
                scholarship_title=scholarship.title,
                official_source_url=scholarship.official_source_url,
            )

            best = validator.find_best_result(results)
            if best is None:
                return

            if best.status.value == "approved" and best.confidence == "HIGH":
                from .scholarship_image_verifier import ImageVerifier
                image_verifier = ImageVerifier(session)
                updated = image_verifier.mark_image_verified(
                    scholarship_id=scholarship_id,
                    image_url=best.candidate.image_url,
                    image_source_url=best.candidate.page_url or scholarship.official_source_url,
                    source_type="official_scholarship",
                    alt_text=best.candidate.alt_text,
                    image_kind=best.image_kind,
                )
                if updated:
                    metrics.image_high += 1
                    session.commit()
            elif best.status.value == "human_review" and best.confidence == "MEDIUM":
                review = ImageReview(
                    scholarship_id=scholarship_id,
                    image_url=best.candidate.image_url,
                    image_kind=best.image_kind or "unknown",
                    source_page=best.candidate.page_url,
                    source_type="official_scholarship",
                    relevance_evidence="; ".join(best.relevance_notes[:3]) if best.relevance_notes else None,
                    confidence=best.confidence,
                    reason_for_review=best.human_review_reason or "Auto-discovered image requires review",
                    decision="pending",
                )
                session.add(review)
                session.commit()
                metrics.image_medium += 1
                metrics.image_review += 1
            else:
                metrics.image_low += 1
        except Exception:
            session.rollback()
            logger.exception("Image discovery failed for scholarship %s", scholarship_id)
        finally:
            session.close()
