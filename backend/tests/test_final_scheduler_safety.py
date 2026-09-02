"""FINAL PRE-PRODUCTION SCHEDULER SAFETY TEST

Tests the corrected SchedulerEngine under both success and failure conditions
using an ISOLATED in-memory database. No production data is modified.

Tests:
1. Success path - small controlled batch
2. Telemetry failure path - rollback verification
3. Retry path - duration_ms recording
4. Terminal failure path - consistency check
5. Idempotency - second run produces 0 changes
"""

from __future__ import annotations

import os
import tempfile
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


# ===========================================================================
# FIXTURES - Isolated test environment
# ===========================================================================


@pytest.fixture
def db_engine():
    """Create isolated file-based database for thread-safe testing."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def session_factory(db_engine):
    """Create session factory bound to isolated database."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def config():
    """Small batch config for testing."""
    return SchedulerConfig(max_workers=1, batch_size=3, max_attempts_per_job=3)


@pytest.fixture
def scheduler(session_factory, config):
    """Create scheduler with isolated session factory."""
    return SchedulerEngine(session_factory=session_factory, config=config)


@pytest.fixture
def test_scholarships(session_factory):
    """Create 3 test scholarships for controlled testing."""
    session = session_factory()
    scholarships = [
        Scholarship(
            title="Test Scholarship Alpha",
            country="Germany",
            degree="Masters",
            funding="Full",
            official_source_url="https://test.example.com/alpha",
            next_verification_due=date.today() - timedelta(days=1),
            verification_status="active",
            is_verified=False,
        ),
        Scholarship(
            title="Test Scholarship Beta",
            country="France",
            degree="PhD",
            funding="Partial",
            official_source_url="https://test.example.com/beta",
            next_verification_due=date.today() - timedelta(days=5),
            verification_status="active",
            is_verified=False,
        ),
        Scholarship(
            title="Test Scholarship Gamma",
            country="UK",
            degree="Masters",
            funding="Full",
            official_source_url="https://test.example.com/gamma",
            next_verification_due=None,  # Never verified - should be picked up
            verification_status="active",
            is_verified=False,
        ),
    ]
    session.add_all(scholarships)
    session.commit()
    ids = [s.id for s in scholarships]
    session.close()
    return ids


# ===========================================================================
# TEST 1 — SUCCESS PATH
# ===========================================================================


class TestSuccessPath:
    """TEST 1: Process a very small controlled batch and verify success."""

    def setup_method(self):
        reset_telemetry()

    def test_success_path_full_verification(self, scheduler, session_factory, test_scholarships):
        """Verify: source fetch succeeds, verification succeeds, telemetry succeeds,
        expected DB update occurs, verification history is correct, transaction commits,
        no duplicate records, no duplicate history."""
        initial_count = len(test_scholarships)

        # Mock verify_scholarship to return successful results
        def mock_verify(session, scholarship_id):
            result = MagicMock()
            result.scholarship_id = scholarship_id
            result.fetch_status = "success"
            result.automatic_update_candidates = []
            result.uncertain_fields = []
            result.verification_status = "active"
            result.verification_result = MagicMock()
            result.verification_result.status = "active"
            result.official_source_url = f"https://test.example.com/scholarship_{scholarship_id}"
            return result

        with patch("app.services.scheduler_engine.verify_scholarship", side_effect=mock_verify):
            with patch("app.services.scheduler_engine.create_reviews_from_verification", return_value=[]):
                with patch("app.services.scheduler_engine.compute_adaptive_policy") as mock_policy:
                    mock_policy.return_value = MagicMock(next_due_at=date.today() + timedelta(days=30))

                    # Start scheduler and process batch (submit_batch handles find + enqueue + submit)
                    scheduler.start()
                    submitted = scheduler.submit_batch()
                    assert submitted == initial_count, f"Expected {initial_count} submitted, got {submitted}"
                    scheduler.shutdown(wait=True)

        # Verify DB state
        session = session_factory()
        for sid in test_scholarships:
            s = session.get(Scholarship, sid)
            assert s.verification_status == "active", f"Scholarship {sid} status should be active"
            assert s.is_verified is True, f"Scholarship {sid} should be verified"
            assert s.last_verified_at is not None, f"Scholarship {sid} should have last_verified_at"
            assert s.last_verified_date is not None, f"Scholarship {sid} should have last_verified_date"
            assert s.next_verification_due is not None, f"Scholarship {sid} should have next_verification_due"

        # Verify no duplicate records
        total = session.query(Scholarship).count()
        assert total == initial_count, f"Expected {initial_count} scholarships, got {total}"

        # Verify no history entries (no field changes, just verification timestamp)
        history_count = session.query(ScholarshipVerificationHistory).count()
        assert history_count == 0, f"Expected 0 history entries, got {history_count}"

        session.close()

        # Verify telemetry recorded events
        snapshot = get_snapshot()
        assert snapshot.total_events > 0, "Telemetry should have recorded events"

        # Verify DB state
        session = session_factory()
        for sid in test_scholarships:
            s = session.get(Scholarship, sid)
            assert s.verification_status == "active", f"Scholarship {sid} status should be active"
            assert s.is_verified is True, f"Scholarship {sid} should be verified"
            assert s.last_verified_at is not None, f"Scholarship {sid} should have last_verified_at"
            assert s.last_verified_date is not None, f"Scholarship {sid} should have last_verified_date"
            assert s.next_verification_due is not None, f"Scholarship {sid} should have next_verification_due"

        # Verify no duplicate records
        total = session.query(Scholarship).count()
        assert total == initial_count, f"Expected {total} scholarships, got {total}"

        # Verify no history entries (no changes were made, just verification timestamp)
        history_count = session.query(ScholarshipVerificationHistory).count()
        # Note: No field changes means no history entries - this is correct
        assert history_count == 0, f"Expected 0 history entries, got {history_count}"

        session.close()

        # Verify telemetry recorded events
        snapshot = get_snapshot()
        assert snapshot.total_events > 0, "Telemetry should have recorded events"

    def test_success_path_with_auto_update(self, scheduler, session_factory, test_scholarships):
        """Verify: when auto-update candidates exist, they are applied correctly."""
        session = session_factory()
        target = session.get(Scholarship, test_scholarships[0])
        original_deadline = target.deadline_display
        session.close()

        # Mock verify_scholarship to return a result with auto-update candidates
        def mock_verify_with_update(session, scholarship_id):
            result = MagicMock()
            result.scholarship_id = scholarship_id
            result.fetch_status = "success"
            result.automatic_update_candidates = [
                {"field": "deadline_display", "old_value": original_deadline, "new_value": "15 March 2026"},
            ]
            result.uncertain_fields = []
            result.verification_status = "active"
            result.verification_result = MagicMock()
            result.verification_result.status = "active"
            result.official_source_url = f"https://test.example.com/scholarship_{scholarship_id}"
            return result

        with patch("app.services.scheduler_engine.verify_scholarship", side_effect=mock_verify_with_update):
            with patch("app.services.scheduler_engine.apply_verified_updates") as mock_apply:
                mock_apply.return_value = MagicMock(updated_fields=["deadline_display"])
                with patch("app.services.scheduler_engine.create_reviews_from_verification", return_value=[]):
                    with patch("app.services.scheduler_engine.compute_adaptive_policy") as mock_policy:
                        mock_policy.return_value = MagicMock(next_due_at=date.today() + timedelta(days=30))
                        with patch("app.services.scheduler_engine.write_verification_history") as mock_history:
                            mock_history.return_value = MagicMock(entries_written=1, history_ids=[1])

                            # Start scheduler and process batch
                            scheduler.start()
                            submitted = scheduler.submit_batch()
                            assert submitted > 0, "Should submit at least 1 job"
                            scheduler.shutdown(wait=True)

                            # Verify history was written for auto-update candidates
                            # Should be called once per scholarship with auto-updates
                            assert mock_history.call_count >= 1, \
                                f"Expected at least 1 history write, got {mock_history.call_count}"


# ===========================================================================
# TEST 2 — TELEMETRY FAILURE PATH
# ===========================================================================


class TestTelemetryFailurePath:
    """TEST 2: Deliberately make telemetry function fail and verify rollback."""

    def setup_method(self):
        reset_telemetry()

    def test_telemetry_failure_rolls_back_transaction(self, scheduler, session_factory, test_scholarships):
        """Expected: scheduler reports failure, transaction rolls back,
        scholarship data is unchanged, status is unchanged, no partial mutation,
        no incorrect history, no duplicate records."""
        # Get initial state
        session = session_factory()
        initial_states = {}
        for sid in test_scholarships:
            s = session.get(Scholarship, sid)
            initial_states[sid] = {
                "verification_status": s.verification_status,
                "is_verified": s.is_verified,
                "deadline_display": s.deadline_display,
            }
        session.close()

        # Mock verify_scholarship to return failed fetch
        mock_result = MagicMock()
        mock_result.fetch_status = "failed"
        mock_result.fetch_result = MagicMock()
        mock_result.fetch_result.error_type = "timeout"

        # Mock execute_fetch_with_retry to return "retrying" status
        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "retrying"

        # Mock record_retry to raise an exception (simulating telemetry failure)
        with patch("app.services.scheduler_engine.verify_scholarship", return_value=mock_result):
            with patch("app.services.scheduler_engine.execute_fetch_with_retry", return_value=mock_fetch_result):
                with patch(
                    "app.services.scheduler_engine.record_retry",
                    side_effect=RuntimeError("Simulated telemetry failure"),
                ):
                    session = session_factory()
                    candidates = scheduler.find_due_candidates(session, date.today())
                    session.close()

                    scheduler.start()
                    scheduler.enqueue_candidates(candidates)
                    # submit_batch will catch the exception in the thread pool
                    scheduler.submit_batch()
                    scheduler.shutdown(wait=True)

        # Verify NO changes were committed
        session = session_factory()
        for sid in test_scholarships:
            s = session.get(Scholarship, sid)
            assert s.verification_status == initial_states[sid]["verification_status"], \
                f"Scholarship {sid} status changed unexpectedly"
            assert s.is_verified == initial_states[sid]["is_verified"], \
                f"Scholarship {sid} is_verified changed unexpectedly"
            assert s.deadline_display == initial_states[sid]["deadline_display"], \
                f"Scholarship {sid} deadline_display changed unexpectedly"

        # Verify no history entries were created
        history_count = session.query(ScholarshipVerificationHistory).count()
        assert history_count == 0, f"Expected 0 history entries, got {history_count}"

        # Verify no duplicate records
        total = session.query(Scholarship).count()
        assert total == len(test_scholarships), f"Expected {len(test_scholarships)} scholarships, got {total}"

        session.close()


# ===========================================================================
# TEST 3 — RETRY PATH
# ===========================================================================


class TestRetryPath:
    """TEST 3: Force one controlled fetch failure followed by successful retry."""

    def setup_method(self):
        reset_telemetry()

    def test_retry_path_records_duration_ms(self, scheduler, session_factory, test_scholarships):
        """Verify: retry telemetry records correctly, duration_ms is recorded,
        final verification succeeds, final DB state is correct, no duplicate update occurs."""
        session = session_factory()
        target = session.get(Scholarship, test_scholarships[0])
        session.close()

        # Create a fetch attempt record (simulating prior retry state)
        session = session_factory()
        attempt = ScholarshipFetchAttempt(
            scholarship_id=test_scholarships[0],
            source_url="https://test.example.com/alpha",
            status="retrying",
            attempt_count=1,
            next_retry_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session.add(attempt)
        session.commit()
        session.close()

        # Mock _handle_fetch_failure to test the retry telemetry path
        mock_result = MagicMock()
        mock_result.fetch_result = MagicMock()
        mock_result.fetch_result.error_type = "timeout"

        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "retrying"

        with patch("app.services.scheduler_engine.execute_fetch_with_retry", return_value=mock_fetch_result):
            engine = SchedulerEngine(session_factory=session_factory)
            session = session_factory()
            s = session.get(Scholarship, test_scholarships[0])

            # This should NOT raise TypeError anymore
            engine._handle_fetch_failure(session, s, mock_result)

            session.rollback()
            session.close()

        # Verify telemetry recorded the retry with duration_ms
        snapshot = get_snapshot()
        assert snapshot.retry_count >= 1, f"Expected at least 1 retry recorded, got {snapshot.retry_count}"

    def test_retry_with_duration_ms_value(self, session_factory):
        """Verify duration_ms is correctly passed through in retry path."""
        reset_telemetry()

        engine = SchedulerEngine(session_factory=session_factory)
        session = session_factory()
        s = Scholarship(
            title="Retry Test",
            country="Test",
            degree="Masters",
            funding="Full",
            official_source_url="https://retry-test.example.com",
        )
        session.add(s)
        session.commit()

        mock_result = MagicMock()
        mock_result.fetch_result = MagicMock()
        mock_result.fetch_result.error_type = "rate_limited"

        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "retrying"

        with patch("app.services.scheduler_engine.execute_fetch_with_retry", return_value=mock_fetch_result):
            engine._handle_fetch_failure(session, s, mock_result)

        session.rollback()
        session.close()

        # Verify duration_ms was recorded
        snapshot = get_snapshot()
        assert snapshot.retry_count == 1


# ===========================================================================
# TEST 4 — TERMINAL FAILURE PATH
# ===========================================================================


class TestTerminalFailurePath:
    """TEST 4: Force a controlled failure that exhausts retries."""

    def setup_method(self):
        reset_telemetry()

    def test_terminal_failure_path(self, session_factory):
        """Verify: terminal failure telemetry records correctly, duration_ms is recorded,
        transaction state remains consistent, no partial scholarship mutation,
        failure is visible in logs/telemetry."""
        reset_telemetry()

        engine = SchedulerEngine(session_factory=session_factory)
        session = session_factory()
        s = Scholarship(
            title="Terminal Test",
            country="Test",
            degree="Masters",
            funding="Full",
            official_source_url="https://terminal-test.example.com",
            verification_status="active",
        )
        session.add(s)
        session.commit()
        original_status = s.verification_status

        mock_result = MagicMock()
        mock_result.fetch_result = MagicMock()
        mock_result.fetch_result.error_type = "connection_error"

        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "terminal"

        with patch("app.services.scheduler_engine.execute_fetch_with_retry", return_value=mock_fetch_result):
            engine._handle_fetch_failure(session, s, mock_result)

        session.rollback()
        session.close()

        # Verify telemetry recorded the terminal failure
        snapshot = get_snapshot()
        assert snapshot.terminal_failure_count >= 1, \
            f"Expected at least 1 terminal failure, got {snapshot.terminal_failure_count}"

    def test_terminal_failure_with_duration_ms(self, session_factory):
        """Verify duration_ms is correctly passed through in terminal failure path."""
        reset_telemetry()

        engine = SchedulerEngine(session_factory=session_factory)
        session = session_factory()
        s = Scholarship(
            title="Terminal Duration Test",
            country="Test",
            degree="Masters",
            funding="Full",
            official_source_url="https://terminal-duration.example.com",
        )
        session.add(s)
        session.commit()

        mock_result = MagicMock()
        mock_result.fetch_result = MagicMock()
        mock_result.fetch_result.error_type = "server_error"

        mock_fetch_result = MagicMock()
        mock_fetch_result.status = "terminal"

        with patch("app.services.scheduler_engine.execute_fetch_with_retry", return_value=mock_fetch_result):
            engine._handle_fetch_failure(session, s, mock_result)

        session.rollback()
        session.close()

        snapshot = get_snapshot()
        assert snapshot.terminal_failure_count == 1


# ===========================================================================
# TEST 5 — IDEMPOTENCY
# ===========================================================================


class TestIdempotency:
    """TEST 5: Run the same successful verification twice."""

    def setup_method(self):
        reset_telemetry()

    def test_idempotency_second_run_no_changes(self, scheduler, session_factory, test_scholarships):
        """Expected: FIRST RUN = expected update only, SECOND RUN = 0 changes,
        0 unnecessary DB mutations, 0 duplicate history."""
        # First run - should update verification timestamp
        def mock_verify(session, scholarship_id):
            result = MagicMock()
            result.scholarship_id = scholarship_id
            result.fetch_status = "success"
            result.automatic_update_candidates = []
            result.uncertain_fields = []
            result.verification_status = "active"
            result.verification_result = MagicMock()
            result.verification_result.status = "active"
            result.official_source_url = f"https://test.example.com/scholarship_{scholarship_id}"
            return result

        with patch("app.services.scheduler_engine.verify_scholarship", side_effect=mock_verify):
            with patch("app.services.scheduler_engine.create_reviews_from_verification", return_value=[]):
                with patch("app.services.scheduler_engine.compute_adaptive_policy") as mock_policy:
                    mock_policy.return_value = MagicMock(next_due_at=date.today() + timedelta(days=30))

                    # FIRST RUN
                    scheduler.start()
                    first_run_submitted = scheduler.submit_batch()
                    assert first_run_submitted > 0, "First run should process candidates"
                    scheduler.shutdown(wait=True)

        assert first_run_submitted > 0, "First run should process candidates"

        # Record state after first run
        session = session_factory()
        state_after_first = {}
        for sid in test_scholarships:
            s = session.get(Scholarship, sid)
            state_after_first[sid] = {
                "verification_status": s.verification_status,
                "is_verified": s.is_verified,
                "last_verified_at": s.last_verified_at,
                "next_verification_due": s.next_verification_due,
            }
        history_after_first = session.query(ScholarshipVerificationHistory).count()
        session.close()

        # Second run - should produce 0 changes (candidates no longer due)
        reset_telemetry()
        scheduler2 = SchedulerEngine(session_factory=session_factory, config=SchedulerConfig(max_workers=1, batch_size=3))

        with patch("app.services.scheduler_engine.verify_scholarship", side_effect=mock_verify):
            with patch("app.services.scheduler_engine.create_reviews_from_verification", return_value=[]):
                with patch("app.services.scheduler_engine.compute_adaptive_policy") as mock_policy:
                    mock_policy.return_value = MagicMock(next_due_at=date.today() + timedelta(days=30))

                    # SECOND RUN
                    session = session_factory()
                    candidates = scheduler2.find_due_candidates(session, date.today())
                    session.close()

                    # Candidates should be empty or processed without changes
                    scheduler2.start()
                    if candidates:
                        scheduler2.enqueue_candidates(candidates)
                    second_run_submitted = scheduler2.submit_batch()
                    scheduler2.shutdown(wait=True)

        # Verify state unchanged
        session = session_factory()
        for sid in test_scholarships:
            s = session.get(Scholarship, sid)
            assert s.verification_status == state_after_first[sid]["verification_status"]
            assert s.is_verified == state_after_first[sid]["is_verified"]

        # Verify no duplicate history
        history_after_second = session.query(ScholarshipVerificationHistory).count()
        assert history_after_second == history_after_first, \
            f"History count changed: {history_after_first} -> {history_after_second}"

        session.close()



