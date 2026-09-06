"""Intelligent verification scheduler engine.

Priority-driven, bounded-concurrency scheduler that wraps the existing
verification pipeline with retry orchestration.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..database import get_session_factory
from ..models import Scholarship
from .scheduler_config import SchedulerConfig
from .scheduler_priority import PriorityScore, calculate_priority
from .scheduler_queue import QueuedJob, VerificationQueue
from .scholarship_fetch_executor import execute_fetch_with_retry, process_due_retries
from .scholarship_history import HistoryEntry, write_verification_history
from .scholarship_review_coordinator import create_reviews_from_verification
from .scholarship_updater import apply_verified_updates
from .scholarship_verifier import VerificationStatus, verify_scholarship
from .scholarship_image_verifier import ImageVerifier
from .adaptive_policy import compute_adaptive_policy
from .lifecycle_manager import apply_lifecycle_transition, evaluate_lifecycle
from .telemetry import PipelineStages, record_event, record_retry, record_terminal_failure
from .telemetry_tracing import CorrelationContext, trace_operation

logger = logging.getLogger(__name__)


class SchedulerEngine:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        config: SchedulerConfig | None = None,
        now_fn: Callable[[], date] | None = None,
    ) -> None:
        self.config = config or SchedulerConfig()
        self.session_factory = session_factory or get_session_factory()
        self.now_fn = now_fn or (lambda: date.today())
        self.queue = VerificationQueue()
        self._executor: ThreadPoolExecutor | None = None
        self._shutdown = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self._pending_futures: list = []
        self._completed_count = 0
        self._failed_count = 0

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._executor = ThreadPoolExecutor(
                max_workers=self.config.max_workers,
                thread_name_prefix="verify-worker",
            )
            self._shutdown.clear()
            self._started = True
            logger.info("SchedulerEngine started (workers=%d)", self.config.max_workers)

    def shutdown(self, wait: bool = True) -> None:
        self._shutdown.set()
        with self._lock:
            executor = self._executor
            self._executor = None
            self._started = False
        if executor is not None:
            executor.shutdown(wait=wait)
        logger.info("SchedulerEngine shut down")

    @property
    def is_running(self) -> bool:
        return self._started and not self._shutdown.is_set()

    @property
    def completed_count(self) -> int:
        return self._completed_count

    @property
    def failed_count(self) -> int:
        return self._failed_count

    def wait_for_completion(self, timeout: float | None = None) -> None:
        """Block until all submitted background jobs finish.

        Uses the futures stored from submit_batch(). No-op if the engine is
        shutting down or no jobs were submitted.
        """
        if self._shutdown.is_set():
            return
        with self._lock:
            futures = list(self._pending_futures)
        for future in futures:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass

    def _new_session(self) -> Session:
        return self.session_factory()

    def find_due_candidates(self, session: Session, today: date) -> list[Scholarship]:
        stmt = (
            select(Scholarship)
            .where(
                Scholarship.official_source_url.isnot(None),
                (Scholarship.next_verification_due <= today)
                | (Scholarship.next_verification_due.is_(None)),
            )
            .limit(self.config.batch_size)
        )
        return list(session.scalars(stmt).all())

    def enqueue_candidates(self, scholarships: list[Scholarship]) -> int:
        session = self._new_session()
        try:
            today = self.now_fn()
            enqueued = 0
            for s in scholarships:
                if self.queue.is_active(s.id, s.official_source_url):
                    continue
                priority = calculate_priority(session, s, today)
                job = QueuedJob(
                    scholarship_id=s.id,
                    source_url=s.official_source_url,
                    priority=priority,
                )
                if self.queue.enqueue(job):
                    enqueued += 1
            return enqueued
        finally:
            session.close()

    def process_due_retries(self) -> int:
        if self._shutdown.is_set():
            return 0
        retry_start = time.monotonic()
        session = self._new_session()
        try:
            results = process_due_retries(session, max_attempts=self.config.max_attempts_per_job)
            session.commit()
            retry_duration_ms = (time.monotonic() - retry_start) * 1000.0
            record_event(
                stage=PipelineStages.RETRY,
                metric_type="success",
                duration_ms=retry_duration_ms,
                success=True,
                metadata={"retries_processed": len(results)},
            )
            return len(results)
        except Exception:
            logger.exception("process_due_retries failed")
            session.rollback()
            return 0
        finally:
            session.close()

    def submit_batch(self) -> int:
        if not self.is_running:
            return 0
        batch_start = time.monotonic()
        session = self._new_session()
        try:
            today = self.now_fn()
            candidates = self.find_due_candidates(session, today)
        finally:
            session.close()

        count = self.enqueue_candidates(candidates)
        if count == 0:
            return 0

        submitted = 0
        futures = []
        while not self._shutdown.is_set():
            job = self.queue.dequeue()
            if job is None:
                break
            future = self._executor.submit(self._execute_job, job)
            futures.append(future)
            submitted += 1

        with self._lock:
            self._pending_futures.extend(futures)

        batch_duration_ms = (time.monotonic() - batch_start) * 1000.0
        record_event(
            stage=PipelineStages.SCHEDULER,
            metric_type="success",
            duration_ms=batch_duration_ms,
            success=True,
            metadata={"jobs_submitted": submitted},
        )
        return submitted

    def _execute_job(self, job: QueuedJob) -> None:
        try:
            self._run_single_verification(job)
        except Exception:
            logger.exception("Job failed for scholarship %s", job.scholarship_id)
            self.queue.mark_failed(job)
            with self._lock:
                self._failed_count += 1
        else:
            self.queue.mark_completed(job)
            with self._lock:
                self._completed_count += 1

    def _run_single_verification(self, job: QueuedJob) -> None:
        correlation_id = f"job-{job.scholarship_id}-{int(time.time())}"
        with CorrelationContext(
            correlation_id=correlation_id,
            scholarship_id=job.scholarship_id,
            source=job.source_url,
        ):
            self._run_single_verification_inner(job)

    def _run_single_verification_inner(self, job: QueuedJob) -> None:
        session = self._new_session()
        try:
            scholarship = session.get(Scholarship, job.scholarship_id)
            if scholarship is None:
                return

            result = verify_scholarship(session, scholarship.id)
            if result is None:
                return

            if result.fetch_status == "failed":
                self._handle_fetch_failure(session, scholarship, result)
                return

            if result.automatic_update_candidates:
                self._apply_auto_updates(session, scholarship, result)

            if result.uncertain_fields:
                self._create_reviews(session, result)

            evaluation = evaluate_lifecycle(
                scholarship,
                verification_result={
                    "fetch_status": result.fetch_status,
                },
            )
            if evaluation.should_transition:
                transition = apply_lifecycle_transition(
                    session, scholarship, evaluation, source_url=scholarship.official_source_url
                )
                if transition:
                    logger.info(
                        "Lifecycle transition: scholarship_id=%d %s -> %s",
                        scholarship.id, transition.from_state, transition.to_state,
                    )

            self._update_verification_timestamp(session, scholarship, result)

            if scholarship.image_url:
                try:
                    image_verifier = ImageVerifier(session)
                    image_verifier.revalidate_stored_image(scholarship.id)
                except Exception:
                    logger.exception("Image revalidation failed for scholarship %s", job.scholarship_id)

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _handle_fetch_failure(self, session: Session, scholarship: Scholarship, result) -> None:
        if scholarship.official_source_url and result.fetch_result:
            fetch_error = result.fetch_result.error_type or "unknown"
            retry_start = time.monotonic()
            fetch_result = execute_fetch_with_retry(
                session,
                scholarship.id,
                scholarship.official_source_url,
                max_attempts=self.config.max_attempts_per_job,
            )
            retry_duration_ms = (time.monotonic() - retry_start) * 1000.0
            if fetch_result.status == "retrying":
                record_retry(
                    stage=PipelineStages.RETRY,
                    error_type=fetch_error,
                    scholarship_id=scholarship.id,
                    source=scholarship.official_source_url,
                    duration_ms=retry_duration_ms,
                )
            elif fetch_result.status == "terminal":
                record_terminal_failure(
                    stage=PipelineStages.RETRY,
                    error_type=fetch_error,
                    scholarship_id=scholarship.id,
                    source=scholarship.official_source_url,
                    duration_ms=retry_duration_ms,
                )
            session.flush()

    def _apply_auto_updates(self, session: Session, scholarship: Scholarship, result) -> None:
        update_start = time.monotonic()
        update_result = apply_verified_updates(
            session,
            scholarship.id,
            result.automatic_update_candidates,
        )
        update_duration_ms = (time.monotonic() - update_start) * 1000.0
        record_event(
            stage=PipelineStages.UPDATE,
            metric_type="success" if update_result.updated_fields else "failure",
            duration_ms=update_duration_ms,
            scholarship_id=scholarship.id,
            source=scholarship.official_source_url,
            success=bool(update_result.updated_fields),
            metadata={"updated_fields": update_result.updated_fields},
        )
        if update_result.updated_fields:
            entries = [
                HistoryEntry(
                    field_name=f,
                    old_value=next(
                        (c.get("old_value") for c in result.automatic_update_candidates if c.get("field") == f),
                        None,
                    ),
                    new_value=next(
                        (c.get("new_value") for c in result.automatic_update_candidates if c.get("field") == f),
                        None,
                    ),
                    change_type="modified",
                    source_url=scholarship.official_source_url,
                    verification_status=result.verification_status,
                )
                for f in update_result.updated_fields
            ]
            write_verification_history(
                session,
                scholarship.id,
                entries,
                source_url=scholarship.official_source_url,
                verification_status=result.verification_status,
            )

    def _create_reviews(self, session: Session, result) -> None:
        review_start = time.monotonic()
        reviews = create_reviews_from_verification(session, result)
        review_duration_ms = (time.monotonic() - review_start) * 1000.0
        record_event(
            stage=PipelineStages.REVIEW,
            metric_type="success" if reviews else "failure",
            duration_ms=review_duration_ms,
            scholarship_id=result.scholarship_id,
            source=result.official_source_url,
            success=bool(reviews),
            metadata={"review_count": len(reviews)},
        )

    def _update_verification_timestamp(self, session: Session, scholarship: Scholarship, result) -> None:
        today = self.now_fn()
        scholarship.last_verified_at = today
        scholarship.last_verified_date = today
        scholarship.is_verified = True
        if result.verification_status in (VerificationStatus.ACTIVE, VerificationStatus.NEEDS_REVIEW):
            scholarship.verification_status = result.verification_status
        policy = compute_adaptive_policy(session, scholarship, today)
        scholarship.next_verification_due = policy.next_due_at
