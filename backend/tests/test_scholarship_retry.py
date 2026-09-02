"""Tests for retry/failure handling layer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, ScholarshipFetchAttempt
from app.services.error_classification import classify_error, is_retryable, is_terminal
from app.services.official_source_fetcher import OfficialSourceFetchResult
from app.services.scholarship_fetch_executor import (
    execute_fetch_with_retry,
    get_or_create_attempt,
    get_source_health,
    process_due_retries,
)
from app.services.scholarship_retry import (
    BASE_BACKOFF_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    JITTER_FRACTION,
    RATE_LIMIT_BACKOFF_SECONDS,
    compute_backoff,
    compute_next_retry_at,
    make_retry_decision,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def scholarship(session):
    s = Scholarship(
        title="Test Scholarship",
        country="Germany",
        degree="Masters",
        funding="Full",
        official_source_url="https://example.com/scholarship",
    )
    session.add(s)
    session.commit()
    return s


class TestErrorClassification:
    def test_timeout_is_retryable(self):
        assert is_retryable("timeout") is True

    def test_connection_error_is_retryable(self):
        assert is_retryable("connection_error") is True

    def test_rate_limited_is_retryable(self):
        assert is_retryable("rate_limited") is True

    def test_server_error_is_retryable(self):
        assert is_retryable("server_error") is True

    def test_not_found_is_non_retryable(self):
        assert is_retryable("not_found") is False

    def test_forbidden_is_non_retryable(self):
        assert is_retryable("forbidden") is False

    def test_invalid_url_is_non_retryable(self):
        assert is_retryable("invalid_url") is False

    def test_invalid_content_type_is_non_retryable(self):
        assert is_retryable("invalid_content_type") is False

    def test_client_error_is_non_retryable(self):
        assert is_retryable("client_error") is False

    def test_unexpected_error_is_non_retryable(self):
        assert is_retryable("unexpected_error") is False

    def test_not_found_is_terminal(self):
        assert is_terminal("not_found") is True

    def test_forbidden_is_terminal(self):
        assert is_terminal("forbidden") is True

    def test_timeout_is_not_terminal(self):
        assert is_terminal("timeout") is False

    def test_rate_limited_is_not_terminal(self):
        assert is_terminal("rate_limited") is False


class TestRetryDecision:
    def test_retryable_error_returns_should_retry(self):
        decision = make_retry_decision("timeout", attempt_count=1, max_attempts=5)
        assert decision.should_retry is True
        assert decision.next_retry_at is not None

    def test_non_retryable_error_returns_no_retry(self):
        decision = make_retry_decision("not_found", attempt_count=1, max_attempts=5)
        assert decision.should_retry is False
        assert decision.next_retry_at is None

    def test_max_attempts_exhausted_returns_no_retry(self):
        decision = make_retry_decision("timeout", attempt_count=5, max_attempts=5)
        assert decision.should_retry is False
        assert decision.next_retry_at is None

    def test_max_attempts_exceeded_returns_no_retry(self):
        decision = make_retry_decision("timeout", attempt_count=6, max_attempts=5)
        assert decision.should_retry is False

    def test_rate_limited_uses_longer_backoff(self):
        decision = make_retry_decision("rate_limited", attempt_count=1, max_attempts=5)
        assert decision.should_retry is True
        expected_min = datetime.now(timezone.utc) + timedelta(seconds=RATE_LIMIT_BACKOFF_SECONDS * 0.5)
        assert decision.next_retry_at > expected_min


class TestExponentialBackoff:
    @patch("app.services.scholarship_retry.random.uniform")
    def test_backoff_increases_with_attempts(self, mock_uniform):
        mock_uniform.return_value = 0.0
        b1 = compute_backoff(1, "timeout")
        b2 = compute_backoff(2, "timeout")
        b3 = compute_backoff(3, "timeout")
        assert b1 < b2 < b3

    @patch("app.services.scholarship_retry.random.uniform")
    def test_backoff_doubles_each_attempt(self, mock_uniform):
        mock_uniform.return_value = 0.0
        b1 = compute_backoff(1, "timeout")
        b2 = compute_backoff(2, "timeout")
        assert b2 / b1 == pytest.approx(2.0, rel=1e-9)

    def test_backoff_respects_max(self):
        b = compute_backoff(20, "timeout")
        assert b <= 300.0 * (1 + JITTER_FRACTION)

    def test_backoff_is_non_negative(self):
        for i in range(1, 10):
            b = compute_backoff(i, "timeout")
            assert b >= 0.0


class TestJitter:
    def test_jitter_varies_backoff(self):
        values = {compute_backoff(3, "timeout") for _ in range(50)}
        assert len(values) > 1

    def test_jitter_stays_within_fraction(self):
        base = BASE_BACKOFF_SECONDS * (2 ** 2)
        max_jitter = base * JITTER_FRACTION
        for _ in range(100):
            b = compute_backoff(3, "timeout")
            assert abs(b - base) <= max_jitter + 0.01


class Test429Handling:
    def test_rate_limit_uses_fixed_backoff(self):
        b = compute_backoff(1, "rate_limited")
        assert abs(b - RATE_LIMIT_BACKOFF_SECONDS) < 1.0

    def test_rate_limit_retryable(self):
        decision = make_retry_decision("rate_limited", attempt_count=1, max_attempts=5)
        assert decision.should_retry is True


class TestSourceIsolation:
    def test_different_sources_tracked_separately(self, session, scholarship):
        url1 = "https://source1.com"
        url2 = "https://source2.com"

        a1 = get_or_create_attempt(session, scholarship.id, url1)
        a2 = get_or_create_attempt(session, scholarship.id, url2)
        session.commit()

        assert a1.id != a2.id
        assert a1.source_url == url1
        assert a2.source_url == url2

    def test_source_health_isolated(self, session, scholarship):
        url1 = "https://healthy.com"
        url2 = "https://unhealthy.com"

        a1 = ScholarshipFetchAttempt(
            scholarship_id=scholarship.id,
            source_url=url1,
            status="resolved",
            attempt_count=1,
            max_attempts=5,
            terminal=False,
        )
        a2 = ScholarshipFetchAttempt(
            scholarship_id=scholarship.id,
            source_url=url2,
            status="terminal",
            attempt_count=5,
            max_attempts=5,
            terminal=True,
        )
        session.add_all([a1, a2])
        session.commit()

        health1 = get_source_health(session, url1)
        health2 = get_source_health(session, url2)

        assert health1["healthy"] is True
        assert health2["healthy"] is False


class TestIdempotentRetry:
    def test_repeated_fetch_returns_same_attempt(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url=url,
                content="<html></html>",
            )
            r1 = execute_fetch_with_retry(session, scholarship.id, url)
            r2 = execute_fetch_with_retry(session, scholarship.id, url)

        assert r1.attempt_id == r2.attempt_id
        assert mock_fetch.call_count == 1

    def test_terminal_state_prevents_retry(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="not_found",
                error_reason="404 not found",
            )
            r1 = execute_fetch_with_retry(session, scholarship.id, url)
            r2 = execute_fetch_with_retry(session, scholarship.id, url)

        assert r1.status == "terminal"
        assert r2.status == "terminal"
        assert mock_fetch.call_count == 1


class TestTerminalFailure:
    def test_non_retryable_error_creates_terminal(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="not_found",
                error_reason="404 not found",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "terminal"
        assert result.attempts_remaining == 0

        attempt = session.query(ScholarshipFetchAttempt).get(result.attempt_id)
        assert attempt.terminal is True
        assert attempt.status == "terminal"

    def test_max_retries_exhausted_creates_terminal(self, session, scholarship):
        url = "https://example.com/scholarship"
        now = datetime.now(timezone.utc)

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            for i in range(DEFAULT_MAX_ATTEMPTS):
                with patch("app.services.scholarship_fetch_executor.datetime") as mock_dt:
                    mock_dt.now.return_value = now + timedelta(seconds=i * 1000)
                    mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
                    result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "terminal"
        assert result.attempts_remaining == 0

        attempt = session.query(ScholarshipFetchAttempt).get(result.attempt_id)
        assert attempt.terminal is True
        assert attempt.attempt_count == DEFAULT_MAX_ATTEMPTS


class TestRestartSafePersistedState:
    def test_state_survives_session_recreate(self, engine, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        attempt_id = result.attempt_id

        Session2 = sessionmaker(bind=engine)
        new_session = Session2()

        attempt = new_session.query(ScholarshipFetchAttempt).get(attempt_id)
        assert attempt is not None
        assert attempt.attempt_count == 1
        assert attempt.status == "retrying"
        assert attempt.last_error_type == "timeout"

        new_session.close()

    def test_terminal_state_persists(self, engine, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="not_found",
                error_reason="404 not found",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        attempt_id = result.attempt_id

        Session2 = sessionmaker(bind=engine)
        new_session = Session2()

        attempt = new_session.query(ScholarshipFetchAttempt).get(attempt_id)
        assert attempt.terminal is True
        assert attempt.status == "terminal"

        new_session.close()


class TestNoDuplicateHistoryReviewUpdate:
    def test_retry_does_not_create_history(self, session, scholarship):
        from app.models import ScholarshipVerificationHistory

        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            execute_fetch_with_retry(session, scholarship.id, url)

        history = session.query(ScholarshipVerificationHistory).filter(
            ScholarshipVerificationHistory.scholarship_id == scholarship.id
        ).all()
        assert len(history) == 0

    def test_retry_does_not_create_review(self, session, scholarship):
        from app.models import ScholarshipReview

        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            execute_fetch_with_retry(session, scholarship.id, url)

        reviews = session.query(ScholarshipReview).filter(
            ScholarshipReview.scholarship_id == scholarship.id
        ).all()
        assert len(reviews) == 0

    def test_retry_does_not_update_scholarship(self, session, scholarship):
        url = "https://example.com/scholarship"
        original_title = scholarship.title

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            execute_fetch_with_retry(session, scholarship.id, url)

        session.refresh(scholarship)
        assert scholarship.title == original_title


class TestProcessDueRetries:
    def test_processes_only_due_retries(self, session, scholarship):
        url = "https://example.com/scholarship"
        now = datetime.now(timezone.utc)

        attempt = ScholarshipFetchAttempt(
            scholarship_id=scholarship.id,
            source_url=url,
            status="retrying",
            attempt_count=1,
            max_attempts=5,
            next_retry_at=now - timedelta(seconds=1),
        )
        session.add(attempt)
        session.commit()

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                final_url=url,
                content="<html></html>",
            )
            results = process_due_retries(session)

        assert len(results) == 1
        assert results[0].status == "resolved"

    def test_skips_non_due_retries(self, session, scholarship):
        url = "https://example.com/scholarship"
        now = datetime.now(timezone.utc)

        attempt = ScholarshipFetchAttempt(
            scholarship_id=scholarship.id,
            source_url=url,
            status="retrying",
            attempt_count=1,
            max_attempts=5,
            next_retry_at=now + timedelta(hours=1),
        )
        session.add(attempt)
        session.commit()

        with patch("app.services.scholarship_fetch_executor.fetch_official_source"):
            results = process_due_retries(session)

        assert len(results) == 0


class TestRetryableError:
    def test_timeout_retries(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "retrying"
        assert result.attempts_remaining == DEFAULT_MAX_ATTEMPTS - 1

    def test_connection_error_retries(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="connection_error",
                error_reason="connection refused",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "retrying"

    def test_server_error_retries(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="server_error",
                error_reason="500 internal server error",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "retrying"


class TestNonRetryableError:
    def test_404_does_not_retry(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="not_found",
                error_reason="404 not found",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "terminal"
        assert mock_fetch.call_count == 1

    def test_403_does_not_retry(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="forbidden",
                error_reason="403 forbidden",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "terminal"

    def test_invalid_url_does_not_retry(self, session, scholarship):
        url = "https://example.com/scholarship"

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="invalid_url",
                error_reason="empty url",
            )
            result = execute_fetch_with_retry(session, scholarship.id, url)

        assert result.status == "terminal"


class TestMaxRetryLimit:
    def test_retries_up_to_max(self, session, scholarship):
        url = "https://example.com/scholarship"
        now = datetime.now(timezone.utc)

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            results = []
            for i in range(DEFAULT_MAX_ATTEMPTS):
                with patch("app.services.scholarship_fetch_executor.datetime") as mock_dt:
                    mock_dt.now.return_value = now + timedelta(seconds=i * 1000)
                    mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
                    result = execute_fetch_with_retry(session, scholarship.id, url)
                    results.append(result)

        assert results[-1].status == "terminal"
        assert mock_fetch.call_count == DEFAULT_MAX_ATTEMPTS

    def test_custom_max_attempts(self, session, scholarship):
        url = "https://example.com/scholarship"
        custom_max = 3
        now = datetime.now(timezone.utc)

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False,
                final_url=url,
                error_type="timeout",
                error_reason="connection timed out",
            )
            results = []
            for i in range(custom_max):
                with patch("app.services.scholarship_fetch_executor.datetime") as mock_dt:
                    mock_dt.now.return_value = now + timedelta(seconds=i * 1000)
                    mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
                    result = execute_fetch_with_retry(session, scholarship.id, url, max_attempts=custom_max)
                    results.append(result)

        assert results[-1].status == "terminal"
        assert mock_fetch.call_count == custom_max
