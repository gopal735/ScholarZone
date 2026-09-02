"""Production observability and performance telemetry for ScholarZone.

Lightweight, structured telemetry for pipeline latency, reliability,
performance metrics, source intelligence, and correlation tracing.

No external dependencies. Designed for future OpenTelemetry/Prometheus integration.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

logger = logging.getLogger(__name__)


PipelineStage = str


class PipelineStages:
    FETCH = "fetch"
    EXTRACTION = "extraction"
    DIFF = "diff"
    EVIDENCE = "evidence"
    CONFIDENCE = "confidence"
    UPDATE = "update"
    REVIEW = "review"
    DISCOVERY = "discovery"
    SCHEDULER = "scheduler"
    RETRY = "retry"


class MetricType:
    LATENCY = "latency"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    TERMINAL = "terminal"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"


class ErrorCategory:
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    CONNECTION_ERROR = "connection_error"
    CLIENT_ERROR = "client_error"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    TERMINAL = "terminal"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class TelemetryEvent:
    """Immutable telemetry event with correlation context."""

    event_id: str
    correlation_id: str
    stage: PipelineStage
    metric_type: str
    timestamp: float
    duration_ms: float | None = None
    scholarship_id: int | None = None
    source: str | None = None
    job_id: str | None = None
    verification_id: str | None = None
    success: bool | None = None
    error_type: str | None = None
    error_category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyStats:
    """Aggregated latency statistics for a pipeline stage."""

    stage: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    values: list[float] = field(default_factory=list)

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count > 0 else 0.0

    @property
    def p50_ms(self) -> float:
        return self._percentile(50)

    @property
    def p95_ms(self) -> float:
        return self._percentile(95)

    @property
    def p99_ms(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: float) -> float:
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = int((len(sorted_vals) - 1) * p / 100.0)
        return sorted_vals[idx]

    def add(self, duration_ms: float) -> None:
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)
        self.values.append(duration_ms)
        if len(self.values) > 10000:
            self.values = self.values[-5000:]


@dataclass
class SourceStats:
    """Aggregated statistics for a specific source domain."""

    domain: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_count: int = 0
    rate_limited_count: int = 0
    server_error_count: int = 0
    retry_count: int = 0
    terminal_failure_count: int = 0
    total_latency_ms: float = 0.0
    last_request_at: float | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error_type: str | None = None
    consecutive_failures: int = 0

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    @property
    def is_healthy(self) -> bool:
        if self.total_requests == 0:
            return True
        if self.consecutive_failures >= 5:
            return False
        return self.error_rate < 0.5


@dataclass
class TelemetrySnapshot:
    """Thread-safe snapshot of all telemetry metrics."""

    pipeline_latency: dict[str, LatencyStats] = field(default_factory=dict)
    pipeline_success: dict[str, int] = field(default_factory=dict)
    pipeline_failure: dict[str, int] = field(default_factory=dict)
    source_stats: dict[str, SourceStats] = field(default_factory=dict)
    total_events: int = 0
    review_count: int = 0
    auto_update_count: int = 0
    terminal_failure_count: int = 0
    retry_count: int = 0
    slowest_operations: list[TelemetryEvent] = field(default_factory=list)


_SLOW_OPERATION_THRESHOLD_MS = 5000.0
_MAX_SLOW_OPERATIONS = 100


class _TelemetryCollector:
    """Thread-safe singleton telemetry collector."""

    _instance: _TelemetryCollector | None = None
    _lock = threading.Lock()

    def __new__(cls) -> _TelemetryCollector:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._pipeline_latency: dict[str, LatencyStats] = defaultdict(
            lambda: LatencyStats(stage="unknown")
        )
        self._pipeline_success: dict[str, int] = defaultdict(int)
        self._pipeline_failure: dict[str, int] = defaultdict(int)
        self._source_stats: dict[str, SourceStats] = {}
        self._total_events = 0
        self._review_count = 0
        self._auto_update_count = 0
        self._terminal_failure_count = 0
        self._retry_count = 0
        self._slowest_operations: list[TelemetryEvent] = []
        self._data_lock = threading.Lock()
        self._correlation_context = threading.local()
        self._initialized = True

    def reset(self) -> None:
        """Reset all metrics. For testing only."""
        with self._data_lock:
            self._pipeline_latency.clear()
            self._pipeline_success.clear()
            self._pipeline_failure.clear()
            self._source_stats.clear()
            self._total_events = 0
            self._review_count = 0
            self._auto_update_count = 0
            self._terminal_failure_count = 0
            self._retry_count = 0
            self._slowest_operations.clear()

    def record_event(self, event: TelemetryEvent) -> None:
        """Record a telemetry event. Never raises."""
        try:
            with self._data_lock:
                self._total_events += 1
                self._record_latency(event)
                self._record_success_failure(event)
                self._record_source_stats(event)
                self._record_counters(event)
                self._record_slow_operation(event)
        except Exception:
            pass

    def _record_latency(self, event: TelemetryEvent) -> None:
        if event.duration_ms is None:
            return
        stage = event.stage
        if stage not in self._pipeline_latency:
            self._pipeline_latency[stage] = LatencyStats(stage=stage)
        self._pipeline_latency[stage].add(event.duration_ms)

    def _record_success_failure(self, event: TelemetryEvent) -> None:
        if event.success is None:
            return
        stage = event.stage
        if event.success:
            self._pipeline_success[stage] += 1
        else:
            self._pipeline_failure[stage] += 1

    def _record_source_stats(self, event: TelemetryEvent) -> None:
        if event.source is None:
            return
        domain = event.source
        if domain not in self._source_stats:
            self._source_stats[domain] = SourceStats(domain=domain)

        stats = self._source_stats[domain]
        stats.total_requests += 1
        stats.last_request_at = event.timestamp

        if event.duration_ms is not None:
            stats.total_latency_ms += event.duration_ms

        if event.success is True:
            stats.successful_requests += 1
            stats.last_success_at = event.timestamp
            stats.consecutive_failures = 0
        elif event.success is False:
            stats.failed_requests += 1
            stats.last_failure_at = event.timestamp
            stats.last_error_type = event.error_type
            stats.consecutive_failures += 1

        if event.error_category == ErrorCategory.TIMEOUT:
            stats.timeout_count += 1
        elif event.error_category == ErrorCategory.RATE_LIMITED:
            stats.rate_limited_count += 1
        elif event.error_category == ErrorCategory.SERVER_ERROR:
            stats.server_error_count += 1

        if event.metric_type == MetricType.RETRY:
            stats.retry_count += 1
        elif event.metric_type == MetricType.TERMINAL:
            stats.terminal_failure_count += 1

    def _record_counters(self, event: TelemetryEvent) -> None:
        if event.metric_type == MetricType.RETRY:
            self._retry_count += 1
        elif event.metric_type == MetricType.TERMINAL:
            self._terminal_failure_count += 1

        if event.stage == PipelineStages.REVIEW and event.success is True:
            self._review_count += 1
        elif event.stage == PipelineStages.UPDATE and event.success is True:
            self._auto_update_count += 1

    def _record_slow_operation(self, event: TelemetryEvent) -> None:
        if event.duration_ms is None:
            return
        if event.duration_ms < _SLOW_OPERATION_THRESHOLD_MS:
            return
        self._slowest_operations.append(event)
        self._slowest_operations.sort(key=lambda e: e.duration_ms, reverse=True)
        if len(self._slowest_operations) > _MAX_SLOW_OPERATIONS:
            self._slowest_operations = self._slowest_operations[:_MAX_SLOW_OPERATIONS]

    def get_correlation_id(self) -> str:
        """Get current thread's correlation ID or generate one."""
        cid = getattr(self._correlation_context, "correlation_id", None)
        if cid is None:
            cid = str(uuid.uuid4())
            self._correlation_context.correlation_id = cid
        return cid

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for current thread."""
        self._correlation_context.correlation_id = correlation_id

    def clear_correlation_id(self) -> None:
        """Clear correlation ID for current thread."""
        if hasattr(self._correlation_context, "correlation_id"):
            delattr(self._correlation_context, "correlation_id")

    def snapshot(self) -> TelemetrySnapshot:
        """Get a thread-safe snapshot of all metrics."""
        with self._data_lock:
            latency_copy = {}
            for stage, stats in self._pipeline_latency.items():
                latency_copy[stage] = LatencyStats(
                    stage=stats.stage,
                    count=stats.count,
                    total_ms=stats.total_ms,
                    min_ms=stats.min_ms,
                    max_ms=stats.max_ms,
                    values=list(stats.values),
                )
            return TelemetrySnapshot(
                pipeline_latency=latency_copy,
                pipeline_success=dict(self._pipeline_success),
                pipeline_failure=dict(self._pipeline_failure),
                source_stats=dict(self._source_stats),
                total_events=self._total_events,
                review_count=self._review_count,
                auto_update_count=self._auto_update_count,
                terminal_failure_count=self._terminal_failure_count,
                retry_count=self._retry_count,
                slowest_operations=list(self._slowest_operations),
            )


def _classify_error(error_type: str | None) -> str | None:
    """Classify error type into category."""
    if error_type is None:
        return None
    mapping = {
        "timeout": ErrorCategory.TIMEOUT,
        "rate_limited": ErrorCategory.RATE_LIMITED,
        "server_error": ErrorCategory.SERVER_ERROR,
        "connection_error": ErrorCategory.CONNECTION_ERROR,
        "client_error": ErrorCategory.CLIENT_ERROR,
        "not_found": ErrorCategory.NOT_FOUND,
        "forbidden": ErrorCategory.FORBIDDEN,
        "terminal": ErrorCategory.TERMINAL,
        "unexpected_error": ErrorCategory.UNEXPECTED,
    }
    return mapping.get(error_type, ErrorCategory.UNEXPECTED)


def get_collector() -> _TelemetryCollector:
    """Get the singleton telemetry collector."""
    return _TelemetryCollector()


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def record_event(
    stage: str,
    metric_type: str,
    *,
    duration_ms: float | None = None,
    scholarship_id: int | None = None,
    source: str | None = None,
    job_id: str | None = None,
    verification_id: str | None = None,
    success: bool | None = None,
    error_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TelemetryEvent:
    """Record a telemetry event."""
    if success is None:
        if metric_type == MetricType.SUCCESS:
            success = True
        elif metric_type in (MetricType.FAILURE, MetricType.TIMEOUT, MetricType.RATE_LIMITED, MetricType.SERVER_ERROR, MetricType.TERMINAL):
            success = False
    collector = get_collector()
    event = TelemetryEvent(
        event_id=str(uuid.uuid4()),
        correlation_id=collector.get_correlation_id(),
        stage=stage,
        metric_type=metric_type,
        timestamp=time.time(),
        duration_ms=duration_ms,
        scholarship_id=scholarship_id,
        source=source,
        job_id=job_id,
        verification_id=verification_id,
        success=success,
        error_type=error_type,
        error_category=_classify_error(error_type),
        metadata=_sanitize_metadata(metadata),
    )
    collector.record_event(event)
    return event


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Remove sensitive fields from metadata."""
    if metadata is None:
        return {}
    sensitive_keys = {"token", "api_key", "secret", "password", "cookie", "authorization", "auth"}
    return {
        k: v
        for k, v in metadata.items()
        if k.lower() not in sensitive_keys and not any(s in k.lower() for s in sensitive_keys)
    }


@contextmanager
def timer(
    stage: str,
    *,
    scholarship_id: int | None = None,
    source: str | None = None,
    job_id: str | None = None,
    verification_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[TimerContext]:
    """Context manager for timing a pipeline stage."""
    ctx = TimerContext(
        stage=stage,
        scholarship_id=scholarship_id,
        source=source,
        job_id=job_id,
        verification_id=verification_id,
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


@dataclass
class TimerContext:
    """Context for timing a pipeline operation."""

    stage: str
    scholarship_id: int | None = None
    source: str | None = None
    job_id: str | None = None
    verification_id: str | None = None
    metadata: dict[str, Any] | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    event: TelemetryEvent | None = None

    def start(self) -> None:
        self.start_time = time.monotonic()

    def finish(
        self,
        *,
        success: bool,
        error_type: str | None = None,
        metric_type: str | None = None,
    ) -> TelemetryEvent:
        self.end_time = time.monotonic()
        self.duration_ms = (self.end_time - self.start_time) * 1000.0
        mt = metric_type or (MetricType.SUCCESS if success else MetricType.FAILURE)
        self.event = record_event(
            stage=self.stage,
            metric_type=mt,
            duration_ms=self.duration_ms,
            scholarship_id=self.scholarship_id,
            source=self.source,
            job_id=self.job_id,
            verification_id=self.verification_id,
            success=success,
            error_type=error_type,
            metadata=self.metadata,
        )
        return self.event


def record_success(
    stage: str,
    *,
    scholarship_id: int | None = None,
    source: str | None = None,
    job_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TelemetryEvent:
    """Record a successful operation."""
    return record_event(
        stage=stage,
        metric_type=MetricType.SUCCESS,
        scholarship_id=scholarship_id,
        source=source,
        job_id=job_id,
        success=True,
        metadata=metadata,
    )


def record_failure(
    stage: str,
    error_type: str,
    *,
    scholarship_id: int | None = None,
    source: str | None = None,
    job_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TelemetryEvent:
    """Record a failed operation."""
    return record_event(
        stage=stage,
        metric_type=MetricType.FAILURE,
        scholarship_id=scholarship_id,
        source=source,
        job_id=job_id,
        success=False,
        error_type=error_type,
        metadata=metadata,
    )


def record_retry(
    stage: str,
    error_type: str,
    *,
    scholarship_id: int | None = None,
    source: str | None = None,
    job_id: str | None = None,
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> TelemetryEvent:
    """Record a retry operation."""
    return record_event(
        stage=stage,
        metric_type=MetricType.RETRY,
        scholarship_id=scholarship_id,
        source=source,
        job_id=job_id,
        duration_ms=duration_ms,
        success=False,
        error_type=error_type,
        metadata=metadata,
    )


def record_terminal_failure(
    stage: str,
    error_type: str,
    *,
    scholarship_id: int | None = None,
    source: str | None = None,
    job_id: str | None = None,
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> TelemetryEvent:
    """Record a terminal (non-retryable) failure."""
    return record_event(
        stage=stage,
        metric_type=MetricType.TERMINAL,
        scholarship_id=scholarship_id,
        source=source,
        job_id=job_id,
        duration_ms=duration_ms,
        success=False,
        error_type=error_type,
        metadata=metadata,
    )


def get_latency_stats(stage: str) -> LatencyStats | None:
    """Get latency statistics for a pipeline stage."""
    snapshot = get_collector().snapshot()
    return snapshot.pipeline_latency.get(stage)


def get_source_stats(domain: str) -> SourceStats | None:
    """Get statistics for a specific source domain."""
    snapshot = get_collector().snapshot()
    return snapshot.source_stats.get(domain)


def get_snapshot() -> TelemetrySnapshot:
    """Get a full snapshot of all telemetry metrics."""
    return get_collector().snapshot()


def reset_telemetry() -> None:
    """Reset all telemetry data. For testing only."""
    get_collector().reset()


def get_review_rate() -> float:
    """Get the review rate (reviews / total verification successes)."""
    snapshot = get_collector().snapshot()
    total_success = sum(snapshot.pipeline_success.values())
    if total_success == 0:
        return 0.0
    return snapshot.review_count / total_success


def get_auto_update_rate() -> float:
    """Get the auto-update rate (auto-updates / total verification successes)."""
    snapshot = get_collector().snapshot()
    total_success = sum(snapshot.pipeline_success.values())
    if total_success == 0:
        return 0.0
    return snapshot.auto_update_count / total_success


def get_source_health(domain: str) -> dict[str, Any]:
    """Get health status for a source domain."""
    stats = get_source_stats(domain)
    if stats is None:
        return {
            "domain": domain,
            "total_requests": 0,
            "error_rate": 0.0,
            "avg_latency_ms": 0.0,
            "is_healthy": True,
            "consecutive_failures": 0,
        }
    return {
        "domain": stats.domain,
        "total_requests": stats.total_requests,
        "successful_requests": stats.successful_requests,
        "failed_requests": stats.failed_requests,
        "error_rate": stats.error_rate,
        "avg_latency_ms": stats.avg_latency_ms,
        "is_healthy": stats.is_healthy,
        "consecutive_failures": stats.consecutive_failures,
        "timeout_count": stats.timeout_count,
        "rate_limited_count": stats.rate_limited_count,
        "server_error_count": stats.server_error_count,
        "retry_count": stats.retry_count,
        "terminal_failure_count": stats.terminal_failure_count,
        "last_error_type": stats.last_error_type,
    }


def get_pipeline_summary() -> dict[str, Any]:
    """Get a summary of all pipeline metrics."""
    snapshot = get_collector().snapshot()
    summary = {
        "total_events": snapshot.total_events,
        "review_count": snapshot.review_count,
        "auto_update_count": snapshot.auto_update_count,
        "terminal_failure_count": snapshot.terminal_failure_count,
        "retry_count": snapshot.retry_count,
        "review_rate": get_review_rate(),
        "auto_update_rate": get_auto_update_rate(),
        "stages": {},
    }
    for stage, latency in snapshot.pipeline_latency.items():
        summary["stages"][stage] = {
            "count": latency.count,
            "avg_ms": latency.avg_ms,
            "p50_ms": latency.p50_ms,
            "p95_ms": latency.p95_ms,
            "p99_ms": latency.p99_ms,
            "min_ms": latency.min_ms if latency.min_ms != float("inf") else 0.0,
            "max_ms": latency.max_ms,
            "success_count": snapshot.pipeline_success.get(stage, 0),
            "failure_count": snapshot.pipeline_failure.get(stage, 0),
        }
    return summary
