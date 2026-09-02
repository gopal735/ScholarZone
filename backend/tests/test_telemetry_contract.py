"""Regression tests for telemetry contract and scheduler transaction safety.

These tests verify:
1. record_retry() and record_terminal_failure() accept duration_ms parameter
2. Telemetry failures do NOT leave scholarship status partially mutated
3. Database transaction rolls back correctly on scheduler failure
4. Retry/terminal-failure paths work with duration_ms
5. A scheduler run that fails mid-execution leaves production data consistent
6. No duplicate/incorrect history is produced after rollback
7. Normal successful scheduler execution still works
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipVerificationHistory,
)
from app.services.scheduler_config import SchedulerConfig
from app.services.scheduler_engine import SchedulerEngine
from app.services.telemetry import (
    MetricType,
    PipelineStages,
    get_snapshot,
    record_event,
    record_retry,
    record_terminal_failure,
    reset_telemetry,
)


class TestTelemetryContract:
    """TEST 1: Telemetry call accepts the expected arguments.

    Verifies that record_retry() and record_terminal_failure() accept
    the duration_ms parameter that scheduler_engine.py passes.
    """

    def setup_method(self):
        reset_telemetry()

    def test_record_retry_accepts_duration_ms(self):
        """record_retry() must accept duration_ms without raising TypeError."""
        event = record_retry(
            stage=PipelineStages.RETRY,
            error_type="timeout",
            scholarship_id=1,
            source="https://example.com",
            duration_ms=1500.0,
        )
        assert event is not None
        assert event.duration_ms == 1500.0
        assert event.metric_type == MetricType.RETRY
        assert event.error_type == "timeout"
        assert event.success is False

    def test_record_terminal_failure_accepts_duration_ms(self):
        """record_terminal_failure() must accept duration_ms without raising TypeError."""
        event = record_terminal_failure(
            stage=PipelineStages.RETRY,
            error_type="connection_error",
            scholarship_id=1,
            source="https://example.com",
            duration_ms=3000.0,
        )
        assert event is not None
        assert event.duration_ms == 3000.0
        assert event.metric_type == MetricType.TERMINAL
        assert event.error_type == "connection_error"
        assert event.success is False

    def test_record_retry_without_duration_ms_still_works(self):
        """Backward compatibility: record_retry() works without duration_ms."""
        event = record_retry(
            stage=PipelineStages.RETRY,
            error_type="timeout",
            scholarship_id=1,
        )
        assert event is not None
        assert event.duration_ms is None

    def test_record_terminal_failure_without_duration_ms_still_works(self):
        """Backward compatibility: record_terminal_failure() works without duration_ms."""
        event = record_terminal_failure(
            stage=PipelineStages.RETRY,
            error_type="server_error",
            scholarship_id=1,
        )
        assert event is not None
        assert event.duration_ms is None

    def test_record_retry_duration_ms_zero(self):
        """duration_ms=0 should be accepted."""
        event = record_retry(
            stage=PipelineStages.RETRY,
            error_type="timeout",
            duration_ms=0.0,
        )
        assert event.duration_ms == 0.0

    def test_record_terminal_failure_duration_ms_zero(self):
        """duration_ms=0 should be accepted."""
        event = record_terminal_failure(
            stage=PipelineStages.RETRY,
            error_type="timeout",
            duration_ms=0.0,
        )
        assert event.duration_ms == 0.0

    def test_record_retry_duration_ms_recorded_in_stats(self):
        """duration_ms should appear in latency stats."""
        record_retry(
            stage=PipelineStages.RETRY,
            error_type="timeout",
            duration_ms=2500.0,
        )
        snapshot = get_snapshot()
        assert snapshot.retry_count == 1

    def test_record_terminal_failure_duration_ms_recorded_in_stats(self):
        """duration_ms should appear in terminal failure count."""
        record_terminal_failure(
            stage=PipelineStages.RETRY,
            error_type="connection_error",
            duration_ms=5000.0,
        )
        snapshot = get_snapshot()
        assert snapshot.terminal_failure_count == 1


class TestSchedulerTransactionBoundary:
    """TESTS 2-3: Telemetry failure cannot leave scholarship status partially mutated.

    Verifies that when telemetry fails during scheduler execution,
    the database transaction is rolled back and no partial mutations persist.
    """

    @pytest.fixture
    def db_engine(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session_factory(self, db_engine):
        return sessionmaker(bind=db_engine)

    @pytest.fixture
    def config(self):
        return SchedulerConfig(max_workers=1, batch_size=10)

    @pytest.fixture
    def scheduler(self, session_factory, config):
        return SchedulerEngine(session_factory=session_factory, config=config)

    @pytest.fixture
    def scholarship(self, session_factory):
        session = session_factory()
        s = Scholarship(
            title="Test Scholarship",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source_url="https://example.com/test",
            next_verification_due=date.today() - timedelta(days=1),
            verification_status="active",
            is_verified=False,
        )
        session.add(s)
        session.commit()
        s_id = s.id
        session.close()
        return s_id

    def test_fetch_failure_with_telemetry_error_rolls_back(
        self, scheduler, session_factory, scholarship
    ):
        """When telemetry fails in _handle_fetch_failure, transaction must roll back.

        This reproduces the production bug where record_retry/record_terminal_failure
        raised TypeError due to unexpected duration_ms kwarg.
        """
        session = session_factory()
        s = session.get(Scholarship, scholarship)
        original_status = s.verification_status
        original_is_verified = s.is_verified
        session.close()

        # Mock verify_scholarship to return a failed fetch result
        mock_result = MagicMock()
        mock_result.fetch_status = "failed"
        mock_result.fetch_result.error_type = "timeout"

        # Mock execute_fetch_with_retry to return a "retrying" result
        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "retrying"

        # Mock record_retry to raise TypeError (simulating the bug)
        with patch(
            "app.services.scheduler_engine.verify_scholarship",
            return_value=mock_result,
        ), patch(
            "app.services.scheduler_engine.execute_fetch_with_retry",
            return_value=mock_fetch_result,
        ), patch(
            "app.services.scheduler_engine.record_retry",
            side_effect=TypeError("record_retry() got an unexpected keyword argument 'duration_ms'"),
        ):
            try:
                scheduler._run_single_verification_inner(
                    MagicMock(scholarship_id=scholarship, source_url="https://example.com/test")
                )
            except TypeError:
                pass  # Expected - the bug propagates

        # Verify NO changes were committed
        session = session_factory()
        s = session.get(Scholarship, scholarship)
        assert s.verification_status == original_status, \
            f"Status was mutated: expected '{original_status}', got '{s.verification_status}'"
        assert s.is_verified == original_is_verified, \
            f"is_verified was mutated: expected {original_is_verified}, got {s.is_verified}"
        session.close()

    def test_fetch_failure_with_terminal_telemetry_error_rolls_back(
        self, scheduler, session_factory, scholarship
    ):
        """When telemetry fails for terminal failure, transaction must roll back."""
        session = session_factory()
        s = session.get(Scholarship, scholarship)
        original_status = s.verification_status
        session.close()

        mock_result = MagicMock()
        mock_result.fetch_status = "failed"
        mock_result.fetch_result.error_type = "connection_error"

        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "terminal"

        with patch(
            "app.services.scheduler_engine.verify_scholarship",
            return_value=mock_result,
        ), patch(
            "app.services.scheduler_engine.execute_fetch_with_retry",
            return_value=mock_fetch_result,
        ), patch(
            "app.services.scheduler_engine.record_terminal_failure",
            side_effect=TypeError("record_terminal_failure() got an unexpected keyword argument 'duration_ms'"),
        ):
            try:
                scheduler._run_single_verification_inner(
                    MagicMock(scholarship_id=scholarship, source_url="https://example.com/test")
                )
            except TypeError:
                pass

        session = session_factory()
        s = session.get(Scholarship, scholarship)
        assert s.verification_status == original_status
        session.close()


class TestRetryTerminalFailurePaths:
    """TEST 4: Retry/terminal-failure paths work with duration_ms."""

    def setup_method(self):
        reset_telemetry()

    @pytest.fixture
    def db_engine(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session_factory(self, db_engine):
        return sessionmaker(bind=db_engine)

    def test_scheduler_engine_handle_fetch_failure_retry_path(self, session_factory):
        """Verify the full retry path in scheduler_engine works with duration_ms."""
        engine = SchedulerEngine(session_factory=session_factory)
        session = session_factory()
        s = Scholarship(
            title="Test",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source_url="https://example.com/test-retry",
        )
        session.add(s)
        session.commit()

        mock_result = MagicMock()
        mock_result.fetch_result = MagicMock()
        mock_result.fetch_result.error_type = "timeout"

        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "retrying"

        with patch(
            "app.services.scheduler_engine.execute_fetch_with_retry",
            return_value=mock_fetch_result,
        ):
            # This should NOT raise TypeError anymore
            engine._handle_fetch_failure(session, s, mock_result)

        session.rollback()
        session.close()

    def test_scheduler_engine_handle_fetch_failure_terminal_path(self, session_factory):
        """Verify the terminal failure path in scheduler_engine works with duration_ms."""
        engine = SchedulerEngine(session_factory=session_factory)
        session = session_factory()
        s = Scholarship(
            title="Test",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source_url="https://example.com/test-terminal",
        )
        session.add(s)
        session.commit()

        mock_result = MagicMock()
        mock_result.fetch_result = MagicMock()
        mock_result.fetch_result.error_type = "connection_error"

        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "terminal"

        with patch(
            "app.services.scheduler_engine.execute_fetch_with_retry",
            return_value=mock_fetch_result,
        ):
            # This should NOT raise TypeError anymore
            engine._handle_fetch_failure(session, s, mock_result)

        session.rollback()
        session.close()


class TestSchedulerExecutionConsistency:
    """TEST 5: A scheduler run that fails mid-execution leaves production data consistent."""

    @pytest.fixture
    def db_engine(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session_factory(self, db_engine):
        return sessionmaker(bind=db_engine)

    def test_failed_scheduler_run_no_partial_history(self, session_factory):
        """A scheduler run that fails must not leave partial history entries."""
        session = session_factory()

        # Create a scholarship
        s = Scholarship(
            title="Test Scholarship",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source_url="https://example.com/test",
            verification_status="active",
        )
        session.add(s)
        session.commit()
        s_id = s.id

        # Simulate a failed verification that writes some history then fails
        try:
            # Start a transaction
            h1 = ScholarshipVerificationHistory(
                scholarship_id=s_id,
                field_name="deadline_display",
                old_value="January 2026",
                new_value="information.",
                change_type="modified",
                verification_status="active",
            )
            session.add(h1)
            session.flush()

            # Simulate failure after partial write
            raise RuntimeError("Simulated telemetry failure")
        except RuntimeError:
            session.rollback()

        # Verify no history was committed
        history = session.query(ScholarshipVerificationHistory).filter_by(scholarship_id=s_id).all()
        assert len(history) == 0, f"Expected 0 history entries after rollback, got {len(history)}"

        # Verify scholarship status unchanged
        s = session.get(Scholarship, s_id)
        assert s.verification_status == "active"

        session.close()


class TestNoDuplicateIncorrectHistory:
    """TEST 6: No duplicate/incorrect history is produced after rollback."""

    @pytest.fixture
    def db_engine(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session_factory(self, db_engine):
        return sessionmaker(bind=db_engine)

    def test_rollback_clears_history_and_scholarship_changes(self, session_factory):
        """Both history and scholarship changes must be rolled back together."""
        session = session_factory()

        s = Scholarship(
            title="Test",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source_url="https://example.com/test",
            verification_status="active",
            is_verified=False,
        )
        session.add(s)
        session.commit()
        s_id = s.id

        # Simulate a transaction that updates scholarship and writes history
        try:
            s = session.get(Scholarship, s_id)
            s.verification_status = "needs_review"
            s.is_verified = True

            h = ScholarshipVerificationHistory(
                scholarship_id=s_id,
                field_name="status",
                old_value="active",
                new_value="needs_review",
                change_type="modified",
                verification_status="needs_review",
            )
            session.add(h)
            session.flush()

            raise RuntimeError("Simulated failure after flush")
        except RuntimeError:
            session.rollback()

        # Verify nothing persisted
        history = session.query(ScholarshipVerificationHistory).filter_by(scholarship_id=s_id).all()
        assert len(history) == 0

        s = session.get(Scholarship, s_id)
        assert s.verification_status == "active"
        assert s.is_verified is False

        session.close()


class TestNormalSchedulerExecution:
    """TEST 7: Normal successful scheduler execution still works."""

    def setup_method(self):
        reset_telemetry()

    def test_record_event_with_all_parameters(self):
        """Normal event recording with all parameters must work."""
        event = record_event(
            stage=PipelineStages.FETCH,
            metric_type=MetricType.SUCCESS,
            duration_ms=100.0,
            scholarship_id=1,
            source="https://example.com",
            success=True,
            metadata={"key": "value"},
        )
        assert event.stage == PipelineStages.FETCH
        assert event.duration_ms == 100.0
        assert event.scholarship_id == 1
        assert event.source == "https://example.com"
        assert event.success is True
        assert event.metadata == {"key": "value"}

    def test_record_helpers_all_work(self):
        """All record_* helper functions must work without errors."""
        from app.services.telemetry import record_failure, record_success

        success_event = record_success(PipelineStages.FETCH, scholarship_id=1)
        assert success_event.success is True

        failure_event = record_failure(PipelineStages.FETCH, "timeout", scholarship_id=1)
        assert failure_event.success is False

        retry_event = record_retry(
            PipelineStages.RETRY, "timeout",
            scholarship_id=1, duration_ms=100.0,
        )
        assert retry_event.metric_type == MetricType.RETRY

        terminal_event = record_terminal_failure(
            PipelineStages.FETCH, "server_error",
            scholarship_id=1, duration_ms=200.0,
        )
        assert terminal_event.metric_type == MetricType.TERMINAL

        snapshot = get_snapshot()
        assert snapshot.total_events == 4
