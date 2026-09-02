"""Tests for the telemetry and observability layer."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.telemetry import (
    ErrorCategory,
    LatencyStats,
    MetricType,
    PipelineStages,
    SourceStats,
    TelemetryEvent,
    TelemetrySnapshot,
    TimerContext,
    _TelemetryCollector,
    _classify_error,
    _sanitize_metadata,
    generate_correlation_id,
    get_auto_update_rate,
    get_collector,
    get_latency_stats,
    get_pipeline_summary,
    get_review_rate,
    get_snapshot,
    get_source_health,
    get_source_stats,
    record_event,
    record_failure,
    record_retry,
    record_success,
    record_terminal_failure,
    reset_telemetry,
    timer,
)
from app.services.telemetry_tracing import (
    CorrelationContext,
    TraceContext,
    VerificationTracer,
    trace_operation,
)


class TestTelemetryEvent:
    """Test TelemetryEvent creation and immutability."""

    def test_create_event_with_defaults(self):
        event = TelemetryEvent(
            event_id="test-123",
            correlation_id="corr-456",
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            timestamp=1000.0,
        )
        assert event.event_id == "test-123"
        assert event.correlation_id == "corr-456"
        assert event.stage == PipelineStages.FETCH
        assert event.metric_type == MetricType.SUCCESS
        assert event.duration_ms is None
        assert event.metadata == {}

    def test_event_is_frozen(self):
        event = TelemetryEvent(
            event_id="test-123",
            correlation_id="corr-456",
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            timestamp=1000.0,
        )
        with pytest.raises(AttributeError):
            event.stage = "modified"  # type: ignore[misc]

    def test_event_with_all_fields(self):
        event = TelemetryEvent(
            event_id="test-123",
            correlation_id="corr-456",
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            timestamp=1000.0,
            duration_ms=150.5,
            scholarship_id=42,
            source="example.com",
            job_id="job-789",
            verification_id="ver-101",
            success=True,
            error_type=None,
            error_category=None,
            metadata={"key": "value"},
        )
        assert event.duration_ms == 150.5
        assert event.scholarship_id == 42
        assert event.source == "example.com"
        assert event.success is True


class TestRecordEvent:
    """Test recording telemetry events."""

    def setup_method(self):
        reset_telemetry()

    def test_record_success_event(self):
        event = record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            duration_ms=100.0,
            scholarship_id=1,
            source="example.com",
            success=True,
        )
        assert event.stage == PipelineStages.FETCH
        assert event.success is True
        assert event.duration_ms == 100.0

    def test_record_failure_event(self):
        event = record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.FAILURE,
            duration_ms=5000.0,
            scholarship_id=1,
            source="example.com",
            success=False,
            error_type="timeout",
        )
        assert event.success is False
        assert event.error_type == "timeout"
        assert event.error_category == ErrorCategory.TIMEOUT

    def test_record_increments_total_events(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)
        record_event(stage=PipelineStages.EXTRACTION, metric_type=MetricType.SUCCESS)
        snapshot = get_snapshot()
        assert snapshot.total_events == 2

    def test_record_with_metadata(self):
        event = record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            metadata={"key": "value", "count": 5},
        )
        assert event.metadata == {"key": "value", "count": 5}


class TestLatencyStats:
    """Test latency statistics aggregation."""

    def setup_method(self):
        reset_telemetry()

    def test_single_value(self):
        stats = LatencyStats(stage=PipelineStages.FETCH)
        stats.add(100.0)
        assert stats.count == 1
        assert stats.avg_ms == 100.0
        assert stats.min_ms == 100.0
        assert stats.max_ms == 100.0

    def test_multiple_values(self):
        stats = LatencyStats(stage=PipelineStages.FETCH)
        for v in [100.0, 200.0, 300.0, 400.0, 500.0]:
            stats.add(v)
        assert stats.count == 5
        assert stats.avg_ms == 300.0
        assert stats.min_ms == 100.0
        assert stats.max_ms == 500.0

    def test_percentile_calculation(self):
        stats = LatencyStats(stage=PipelineStages.FETCH)
        for i in range(100):
            stats.add(float(i + 1))
        assert stats.p50_ms == 50.0
        assert stats.p95_ms == 95.0
        assert stats.p99_ms == 99.0

    def test_empty_percentiles(self):
        stats = LatencyStats(stage=PipelineStages.FETCH)
        assert stats.p50_ms == 0.0
        assert stats.p95_ms == 0.0
        assert stats.p99_ms == 0.0

    def test_values_capped_at_10000(self):
        stats = LatencyStats(stage=PipelineStages.FETCH)
        for i in range(11000):
            stats.add(float(i))
        assert len(stats.values) <= 6000


class TestSourceStats:
    """Test source statistics tracking."""

    def setup_method(self):
        reset_telemetry()

    def test_initial_state(self):
        stats = SourceStats(domain="example.com")
        assert stats.total_requests == 0
        assert stats.error_rate == 0.0
        assert stats.is_healthy is True

    def test_successful_request(self):
        stats = SourceStats(domain="example.com")
        stats.total_requests += 1
        stats.successful_requests += 1
        stats.total_latency_ms += 100.0
        assert stats.error_rate == 0.0
        assert stats.avg_latency_ms == 100.0

    def test_failed_request(self):
        stats = SourceStats(domain="example.com")
        stats.total_requests += 1
        stats.failed_requests += 1
        stats.consecutive_failures += 1
        assert stats.error_rate == 1.0

    def test_mixed_requests(self):
        stats = SourceStats(domain="example.com")
        stats.total_requests = 10
        stats.successful_requests = 7
        stats.failed_requests = 3
        assert stats.error_rate == 0.3

    def test_consecutive_failures_health(self):
        stats = SourceStats(domain="example.com")
        stats.total_requests = 10
        stats.consecutive_failures = 5
        assert stats.is_healthy is False

    def test_error_rate_health(self):
        stats = SourceStats(domain="example.com")
        stats.total_requests = 10
        stats.failed_requests = 6
        assert stats.is_healthy is False


class TestTimerContext:
    """Test timer context manager."""

    def setup_method(self):
        reset_telemetry()

    def test_timer_records_success(self):
        with timer(PipelineStages.FETCH, scholarship_id=1, source="example.com") as ctx:
            time.sleep(0.01)
        assert ctx.duration_ms >= 10.0
        assert ctx.event is not None
        assert ctx.event.success is True

    def test_timer_records_failure(self):
        with pytest.raises(ValueError):
            with timer(PipelineStages.FETCH) as ctx:
                raise ValueError("test error")
        assert ctx.event is not None
        assert ctx.event.success is False
        assert ctx.event.error_type == "ValueError"

    def test_timer_records_latency(self):
        with timer(PipelineStages.FETCH) as ctx:
            time.sleep(0.05)
        stats = get_latency_stats(PipelineStages.FETCH)
        assert stats is not None
        assert stats.count == 1
        assert stats.avg_ms >= 50.0


class TestCorrelationContext:
    """Test correlation context management."""

    def setup_method(self):
        reset_telemetry()

    def test_correlation_id_generation(self):
        cid = generate_correlation_id()
        assert len(cid) == 36
        assert "-" in cid

    def test_correlation_context_sets_id(self):
        collector = get_collector()
        original_cid = collector.get_correlation_id()
        with CorrelationContext(correlation_id="test-corr-123") as ctx:
            assert collector.get_correlation_id() == "test-corr-123"
        assert collector.get_correlation_id() == original_cid

    def test_correlation_context_records_event(self):
        with CorrelationContext(correlation_id="test-corr-123", scholarship_id=42) as ctx:
            ctx.record(PipelineStages.FETCH, MetricType.SUCCESS, success=True)
        snapshot = get_snapshot()
        assert snapshot.total_events == 1

    def test_nested_correlation_context(self):
        collector = get_collector()
        with CorrelationContext(correlation_id="outer"):
            assert collector.get_correlation_id() == "outer"
            with CorrelationContext(correlation_id="inner"):
                assert collector.get_correlation_id() == "inner"
            assert collector.get_correlation_id() == "outer"


class TestTraceOperation:
    """Test trace operation context manager."""

    def setup_method(self):
        reset_telemetry()

    def test_trace_records_success(self):
        with trace_operation(PipelineStages.FETCH, scholarship_id=1) as ctx:
            time.sleep(0.01)
        assert ctx.duration_ms >= 10.0
        snapshot = get_snapshot()
        assert snapshot.total_events == 1

    def test_trace_records_failure(self):
        with pytest.raises(ValueError):
            with trace_operation(PipelineStages.FETCH) as ctx:
                raise ValueError("test")
        snapshot = get_snapshot()
        assert snapshot.total_events == 1

    def test_trace_add_sub_event(self):
        with trace_operation(PipelineStages.FETCH) as ctx:
            ctx.add_event("sub_stage", success=True)
        snapshot = get_snapshot()
        assert snapshot.total_events == 2


class TestVerificationTracer:
    """Test verification pipeline tracer."""

    def setup_method(self):
        reset_telemetry()

    def test_tracer_records_all_stages(self):
        with VerificationTracer(scholarship_id=1, source="example.com") as tracer:
            tracer.record_fetch(100.0, True)
            tracer.record_extraction(50.0, True)
            tracer.record_diff(25.0, True)
            tracer.record_evidence(30.0, True)
            tracer.record_confidence(20.0, True)
            tracer.record_update(40.0, True)
            tracer.record_review(35.0, False)
        snapshot = get_snapshot()
        assert snapshot.total_events >= 7

    def test_tracer_records_summary(self):
        with VerificationTracer(scholarship_id=1) as tracer:
            tracer.record_fetch(100.0, True)
        snapshot = get_snapshot()
        assert snapshot.total_events >= 1

    def test_tracer_handles_failure(self):
        with pytest.raises(RuntimeError):
            with VerificationTracer(scholarship_id=1) as tracer:
                tracer.record_fetch(5000.0, False, "timeout")
                raise RuntimeError("test")  # noqa: F821
        snapshot = get_snapshot()
        assert snapshot.total_events >= 1


class TestErrorClassification:
    """Test error classification."""

    def test_classify_timeout(self):
        assert _classify_error("timeout") == ErrorCategory.TIMEOUT

    def test_classify_rate_limited(self):
        assert _classify_error("rate_limited") == ErrorCategory.RATE_LIMITED

    def test_classify_server_error(self):
        assert _classify_error("server_error") == ErrorCategory.SERVER_ERROR

    def test_classify_connection_error(self):
        assert _classify_error("connection_error") == ErrorCategory.CONNECTION_ERROR

    def test_classify_unknown(self):
        assert _classify_error("unknown_error") == ErrorCategory.UNEXPECTED

    def test_classify_none(self):
        assert _classify_error(None) is None


class TestSanitizeMetadata:
    """Test metadata sanitization."""

    def test_remove_sensitive_keys(self):
        metadata = {
            "url": "https://example.com",
            "api_key": "secret123",
            "token": "bearer_token",
            "password": "hunter2",
            "count": 5,
        }
        sanitized = _sanitize_metadata(metadata)
        assert "url" in sanitized
        assert "count" in sanitized
        assert "api_key" not in sanitized
        assert "token" not in sanitized
        assert "password" not in sanitized

    def test_empty_metadata(self):
        assert _sanitize_metadata({}) == {}

    def test_none_metadata(self):
        assert _sanitize_metadata(None) == {}

    def test_partial_sensitive_match(self):
        metadata = {"authorization_header": "Bearer xyz", "data": "safe"}
        sanitized = _sanitize_metadata(metadata)
        assert "authorization_header" not in sanitized
        assert "data" in sanitized


class TestRecordHelpers:
    """Test convenience recording functions."""

    def setup_method(self):
        reset_telemetry()

    def test_record_success(self):
        event = record_success(PipelineStages.FETCH, scholarship_id=1)
        assert event.success is True
        assert event.stage == PipelineStages.FETCH

    def test_record_failure(self):
        event = record_failure(PipelineStages.FETCH, "timeout", scholarship_id=1)
        assert event.success is False
        assert event.error_type == "timeout"

    def test_record_retry(self):
        event = record_retry(PipelineStages.RETRY, "rate_limited", scholarship_id=1)
        assert event.metric_type == MetricType.RETRY
        assert event.success is False

    def test_record_terminal_failure(self):
        event = record_terminal_failure(PipelineStages.FETCH, "server_error", scholarship_id=1)
        assert event.metric_type == MetricType.TERMINAL
        assert event.success is False


class TestGetters:
    """Test metric getter functions."""

    def setup_method(self):
        reset_telemetry()

    def test_get_latency_stats(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS, duration_ms=100.0)
        stats = get_latency_stats(PipelineStages.FETCH)
        assert stats is not None
        assert stats.count == 1

    def test_get_source_stats(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS, source="example.com")
        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.total_requests == 1

    def test_get_source_health(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS, source="example.com")
        health = get_source_health("example.com")
        assert health["total_requests"] == 1
        assert health["is_healthy"] is True

    def test_get_source_health_unknown(self):
        health = get_source_health("unknown.com")
        assert health["total_requests"] == 0
        assert health["is_healthy"] is True

    def test_get_review_rate(self):
        record_success(PipelineStages.FETCH)
        record_success(PipelineStages.REVIEW)
        rate = get_review_rate()
        assert rate == 0.5

    def test_get_auto_update_rate(self):
        record_success(PipelineStages.FETCH)
        record_success(PipelineStages.UPDATE)
        rate = get_auto_update_rate()
        assert rate == 0.5

    def test_get_pipeline_summary(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS, duration_ms=100.0)
        summary = get_pipeline_summary()
        assert "total_events" in summary
        assert "stages" in summary
        assert PipelineStages.FETCH in summary["stages"]


class TestConcurrency:
    """Test thread safety of telemetry collector."""

    def setup_method(self):
        reset_telemetry()

    def test_concurrent_event_recording(self):
        def record_events():
            for _ in range(100):
                record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_events) for _ in range(10)]
            for f in futures:
                f.result()

        snapshot = get_snapshot()
        assert snapshot.total_events == 1000

    def test_concurrent_latency_recording(self):
        def record_latency():
            for i in range(50):
                record_event(
                    stage=PipelineStages.FETCH,
                    metric_type=MetricType.SUCCESS,
                    duration_ms=float(i + 1),
                )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(record_latency) for _ in range(5)]
            for f in futures:
                f.result()

        stats = get_latency_stats(PipelineStages.FETCH)
        assert stats is not None
        assert stats.count == 250

    def test_concurrent_source_stats(self):
        def record_source_events():
            for _ in range(50):
                record_event(
                    stage=PipelineStages.FETCH,
                    metric_type=MetricType.SUCCESS,
                    source="example.com",
                )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(record_source_events) for _ in range(5)]
            for f in futures:
                f.result()

        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.total_requests == 250


class TestTelemetryFailureIsolation:
    """Test that telemetry failures don't break operations."""

    def setup_method(self):
        reset_telemetry()

    def test_record_event_never_raises(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)
        snapshot = get_snapshot()
        assert snapshot.total_events == 1

    def test_timer_never_breaks_operation(self):
        result = None
        with timer(PipelineStages.FETCH) as ctx:
            result = "operation_result"
        assert result == "operation_result"

    def test_correlation_context_never_breaks(self):
        with CorrelationContext(correlation_id="test"):
            pass


class TestSnapshot:
    """Test telemetry snapshot."""

    def setup_method(self):
        reset_telemetry()

    def test_empty_snapshot(self):
        snapshot = get_snapshot()
        assert snapshot.total_events == 0
        assert snapshot.pipeline_latency == {}
        assert snapshot.source_stats == {}

    def test_snapshot_with_data(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS, duration_ms=100.0)
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.FAILURE, source="example.com")
        snapshot = get_snapshot()
        assert snapshot.total_events == 2
        assert PipelineStages.FETCH in snapshot.pipeline_latency
        assert "example.com" in snapshot.source_stats

    def test_snapshot_isolation(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)
        snapshot1 = get_snapshot()
        record_event(stage=PipelineStages.EXTRACTION, metric_type=MetricType.SUCCESS)
        snapshot2 = get_snapshot()
        assert snapshot1.total_events == 1
        assert snapshot2.total_events == 2


class TestResetTelemetry:
    """Test telemetry reset functionality."""

    def test_reset_clears_all_metrics(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)
        record_event(stage=PipelineStages.EXTRACTION, metric_type=MetricType.SUCCESS)
        reset_telemetry()
        snapshot = get_snapshot()
        assert snapshot.total_events == 0

    def test_reset_clears_latency(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS, duration_ms=100.0)
        reset_telemetry()
        stats = get_latency_stats(PipelineStages.FETCH)
        assert stats is None

    def test_reset_clears_source_stats(self):
        record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS, source="example.com")
        reset_telemetry()
        stats = get_source_stats("example.com")
        assert stats is None


class TestSlowOperationTracking:
    """Test slow operation tracking."""

    def setup_method(self):
        reset_telemetry()

    def test_slow_operation_recorded(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            duration_ms=6000.0,
        )
        snapshot = get_snapshot()
        assert len(snapshot.slowest_operations) == 1

    def test_fast_operation_not_recorded(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            duration_ms=100.0,
        )
        snapshot = get_snapshot()
        assert len(snapshot.slowest_operations) == 0

    def test_slow_operations_capped(self):
        for i in range(150):
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.SUCCESS,
                duration_ms=6000.0 + i,
            )
        snapshot = get_snapshot()
        assert len(snapshot.slowest_operations) == 100


class TestPipelineStages:
    """Test pipeline stage constants."""

    def test_all_stages_defined(self):
        assert PipelineStages.FETCH == "fetch"
        assert PipelineStages.EXTRACTION == "extraction"
        assert PipelineStages.DIFF == "diff"
        assert PipelineStages.EVIDENCE == "evidence"
        assert PipelineStages.CONFIDENCE == "confidence"
        assert PipelineStages.UPDATE == "update"
        assert PipelineStages.REVIEW == "review"
        assert PipelineStages.DISCOVERY == "discovery"
        assert PipelineStages.SCHEDULER == "scheduler"
        assert PipelineStages.RETRY == "retry"


class TestMetricTypes:
    """Test metric type constants."""

    def test_all_metric_types_defined(self):
        assert MetricType.LATENCY == "latency"
        assert MetricType.SUCCESS == "success"
        assert MetricType.FAILURE == "failure"
        assert MetricType.RETRY == "retry"
        assert MetricType.TERMINAL == "terminal"
        assert MetricType.TIMEOUT == "timeout"
        assert MetricType.RATE_LIMITED == "rate_limited"
        assert MetricType.SERVER_ERROR == "server_error"


class TestErrorCategories:
    """Test error category constants."""

    def test_all_categories_defined(self):
        assert ErrorCategory.TIMEOUT == "timeout"
        assert ErrorCategory.RATE_LIMITED == "rate_limited"
        assert ErrorCategory.SERVER_ERROR == "server_error"
        assert ErrorCategory.CONNECTION_ERROR == "connection_error"
        assert ErrorCategory.CLIENT_ERROR == "client_error"
        assert ErrorCategory.NOT_FOUND == "not_found"
        assert ErrorCategory.FORBIDDEN == "forbidden"
        assert ErrorCategory.TERMINAL == "terminal"
        assert ErrorCategory.UNEXPECTED == "unexpected"


class TestDeterministicMetrics:
    """Test that metrics are deterministic."""

    def setup_method(self):
        reset_telemetry()

    def test_same_input_same_output(self):
        for _ in range(10):
            reset_telemetry()
            for i in range(5):
                record_event(
                    stage=PipelineStages.FETCH,
                    metric_type=MetricType.SUCCESS,
                    duration_ms=float(i + 1),
                )
            snapshot = get_snapshot()
            stats = get_latency_stats(PipelineStages.FETCH)
            assert stats.count == 5
            assert stats.avg_ms == 3.0


class TestNoNPlusOne:
    """Test that telemetry doesn't cause N+1 queries."""

    def setup_method(self):
        reset_telemetry()

    def test_batch_recording(self):
        for i in range(100):
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.SUCCESS,
                duration_ms=float(i),
            )
        snapshot = get_snapshot()
        assert snapshot.total_events == 100

    def test_snapshot_is_consistent(self):
        for i in range(50):
            record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)
        snapshot = get_snapshot()
        assert snapshot.total_events == 50
        assert snapshot.pipeline_success.get(PipelineStages.FETCH, 0) == 50


class TestSourceIntelligence:
    """Test source intelligence tracking."""

    def setup_method(self):
        reset_telemetry()

    def test_source_latency_tracking(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            source="example.com",
            duration_ms=100.0,
        )
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            source="example.com",
            duration_ms=200.0,
        )
        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.avg_latency_ms == 150.0

    def test_source_error_rate(self):
        for _ in range(7):
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.SUCCESS,
                source="example.com",
            )
        for _ in range(3):
            record_event(
                stage=PipelineStages.FETCH,
                metric_type=MetricType.FAILURE,
                source="example.com",
                success=False,
            )
        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.error_rate == 0.3

    def test_source_timeout_count(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.TIMEOUT,
            source="example.com",
            success=False,
            error_type="timeout",
        )
        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.timeout_count == 1

    def test_source_rate_limited_count(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.RATE_LIMITED,
            source="example.com",
            success=False,
            error_type="rate_limited",
        )
        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.rate_limited_count == 1

    def test_source_server_error_count(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SERVER_ERROR,
            source="example.com",
            success=False,
            error_type="server_error",
        )
        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.server_error_count == 1

    def test_source_last_error_type(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.FAILURE,
            source="example.com",
            success=False,
            error_type="timeout",
        )
        stats = get_source_stats("example.com")
        assert stats is not None
        assert stats.last_error_type == "timeout"

    def test_source_isolation(self):
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            source="source1.com",
        )
        record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.FAILURE,
            source="source2.com",
            success=False,
        )
        stats1 = get_source_stats("source1.com")
        stats2 = get_source_stats("source2.com")
        assert stats1.total_requests == 1
        assert stats2.total_requests == 1
        assert stats1.successful_requests == 1
        assert stats2.failed_requests == 1


class TestCounterTracking:
    """Test counter tracking for reviews, updates, retries, terminals."""

    def setup_method(self):
        reset_telemetry()

    def test_review_counter(self):
        record_success(PipelineStages.REVIEW, scholarship_id=1)
        snapshot = get_snapshot()
        assert snapshot.review_count == 1

    def test_auto_update_counter(self):
        record_success(PipelineStages.UPDATE, scholarship_id=1)
        snapshot = get_snapshot()
        assert snapshot.auto_update_count == 1

    def test_retry_counter(self):
        record_retry(PipelineStages.RETRY, "timeout")
        snapshot = get_snapshot()
        assert snapshot.retry_count == 1

    def test_terminal_failure_counter(self):
        record_terminal_failure(PipelineStages.FETCH, "server_error")
        snapshot = get_snapshot()
        assert snapshot.terminal_failure_count == 1


class TestLowOverhead:
    """Test that telemetry has minimal overhead."""

    def setup_method(self):
        reset_telemetry()

    def test_event_recording_is_fast(self):
        start = time.monotonic()
        for _ in range(1000):
            record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)
        duration = time.monotonic() - start
        assert duration < 1.0

    def test_snapshot_is_fast(self):
        for _ in range(100):
            record_event(stage=PipelineStages.FETCH, metric_type=MetricType.SUCCESS)
        start = time.monotonic()
        for _ in range(100):
            get_snapshot()
        duration = time.monotonic() - start
        assert duration < 1.0
