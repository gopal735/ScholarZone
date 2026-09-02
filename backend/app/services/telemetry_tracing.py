"""Correlation context and tracing utilities for telemetry."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

from .telemetry import (
    PipelineStages,
    TimerContext,
    get_collector,
    record_event,
)

logger = logging.getLogger(__name__)


class CorrelationContext:
    """Thread-local correlation context for tracing operations."""

    def __init__(
        self,
        correlation_id: str | None = None,
        job_id: str | None = None,
        verification_id: str | None = None,
        scholarship_id: int | None = None,
        source: str | None = None,
    ) -> None:
        self.correlation_id = correlation_id or get_collector().get_correlation_id()
        self.job_id = job_id
        self.verification_id = verification_id
        self.scholarship_id = scholarship_id
        self.source = source
        self._previous_correlation_id: str | None = None

    def __enter__(self) -> CorrelationContext:
        collector = get_collector()
        self._previous_correlation_id = collector.get_correlation_id()
        collector.set_correlation_id(self.correlation_id)
        return self

    def __exit__(self, *exc: Any) -> None:
        collector = get_collector()
        if self._previous_correlation_id:
            collector.set_correlation_id(self._previous_correlation_id)
        else:
            collector.clear_correlation_id()

    def record(
        self,
        stage: str,
        metric_type: str,
        *,
        duration_ms: float | None = None,
        success: bool | None = None,
        error_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an event with this context's correlation ID."""
        record_event(
            stage=stage,
            metric_type=metric_type,
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            job_id=self.job_id,
            verification_id=self.verification_id,
            success=success,
            error_type=error_type,
            metadata=metadata,
        )


@contextmanager
def trace_operation(
    stage: str,
    *,
    scholarship_id: int | None = None,
    source: str | None = None,
    job_id: str | None = None,
    verification_id: str | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[TraceContext]:
    """Context manager for tracing a complete operation with correlation."""
    ctx = TraceContext(
        stage=stage,
        scholarship_id=scholarship_id,
        source=source,
        job_id=job_id,
        verification_id=verification_id,
        correlation_id=correlation_id,
        metadata=metadata,
    )
    ctx.start()
    try:
        yield ctx
    except Exception as e:
        ctx.finish(success=False, error_type=type(e).__name__)
        raise
    else:
        ctx.finish(success=True)


class TraceContext:
    """Context for tracing a complete operation."""

    def __init__(
        self,
        stage: str,
        *,
        scholarship_id: int | None = None,
        source: str | None = None,
        job_id: str | None = None,
        verification_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.stage = stage
        self.scholarship_id = scholarship_id
        self.source = source
        self.job_id = job_id
        self.verification_id = verification_id
        self.correlation_id = correlation_id or get_collector().get_correlation_id()
        self.metadata = metadata or {}
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration_ms: float = 0.0
        self.events: list[dict[str, Any]] = []

    def start(self) -> None:
        self.start_time = time.monotonic()

    def finish(
        self,
        *,
        success: bool,
        error_type: str | None = None,
    ) -> None:
        self.end_time = time.monotonic()
        self.duration_ms = (self.end_time - self.start_time) * 1000.0
        record_event(
            stage=self.stage,
            metric_type="success" if success else "failure",
            duration_ms=self.duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            job_id=self.job_id,
            verification_id=self.verification_id,
            success=success,
            error_type=error_type,
            metadata=self.metadata,
        )

    def add_event(
        self,
        sub_stage: str,
        *,
        duration_ms: float | None = None,
        success: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a sub-event to this trace."""
        event_metadata = {**self.metadata, **(metadata or {})}
        record_event(
            stage=f"{self.stage}.{sub_stage}",
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            job_id=self.job_id,
            verification_id=self.verification_id,
            success=success,
            metadata=event_metadata,
        )


class VerificationTracer:
    """Traces a complete verification pipeline from fetch to decision."""

    def __init__(
        self,
        scholarship_id: int,
        source: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.scholarship_id = scholarship_id
        self.source = source
        self.correlation_id = correlation_id or get_collector().get_correlation_id()
        self.fetch_duration_ms: float | None = None
        self.extraction_duration_ms: float | None = None
        self.diff_duration_ms: float | None = None
        self.evidence_duration_ms: float | None = None
        self.confidence_duration_ms: float | None = None
        self.update_duration_ms: float | None = None
        self.review_duration_ms: float | None = None
        self.total_duration_ms: float | None = None
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.success: bool | None = None
        self.error_type: str | None = None
        self.auto_updated: bool = False
        self.review_created: bool = False

    def __enter__(self) -> VerificationTracer:
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.end_time = time.monotonic()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000.0
        if exc[0] is not None:
            self.success = False
            self.error_type = type(exc[0]).__name__
        self._record_summary()

    def _record_summary(self) -> None:
        record_event(
            stage=PipelineStages.SCHEDULER,
            metric_type="verification_summary",
            duration_ms=self.total_duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=self.success,
            error_type=self.error_type,
            metadata={
                "fetch_ms": self.fetch_duration_ms,
                "extraction_ms": self.extraction_duration_ms,
                "diff_ms": self.diff_duration_ms,
                "evidence_ms": self.evidence_duration_ms,
                "confidence_ms": self.confidence_duration_ms,
                "update_ms": self.update_duration_ms,
                "review_ms": self.review_duration_ms,
                "auto_updated": self.auto_updated,
                "review_created": self.review_created,
            },
        )

    def record_fetch(self, duration_ms: float, success: bool, error_type: str | None = None) -> None:
        self.fetch_duration_ms = duration_ms
        record_event(
            stage=PipelineStages.FETCH,
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=success,
            error_type=error_type,
        )

    def record_extraction(self, duration_ms: float, success: bool) -> None:
        self.extraction_duration_ms = duration_ms
        record_event(
            stage=PipelineStages.EXTRACTION,
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=success,
        )

    def record_diff(self, duration_ms: float, success: bool) -> None:
        self.diff_duration_ms = duration_ms
        record_event(
            stage=PipelineStages.DIFF,
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=success,
        )

    def record_evidence(self, duration_ms: float, success: bool) -> None:
        self.evidence_duration_ms = duration_ms
        record_event(
            stage=PipelineStages.EVIDENCE,
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=success,
        )

    def record_confidence(self, duration_ms: float, success: bool) -> None:
        self.confidence_duration_ms = duration_ms
        record_event(
            stage=PipelineStages.CONFIDENCE,
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=success,
        )

    def record_update(self, duration_ms: float, success: bool) -> None:
        self.update_duration_ms = duration_ms
        self.auto_updated = success
        record_event(
            stage=PipelineStages.UPDATE,
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=success,
        )

    def record_review(self, duration_ms: float, success: bool) -> None:
        self.review_duration_ms = duration_ms
        self.review_created = success
        record_event(
            stage=PipelineStages.REVIEW,
            metric_type="success" if success else "failure",
            duration_ms=duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            success=success,
        )

    def finish(self, *, success: bool, error_type: str | None = None) -> None:
        self.end_time = time.monotonic()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000.0
        self.success = success
        self.error_type = error_type
        self._record_summary()
