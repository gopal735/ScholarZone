"""Tests for source health intelligence layer."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, ScholarshipFetchAttempt, SourceHealth
from app.services.source_health_service import (
    DEGRADED,
    HEALTHY,
    UNHEALTHY,
    UNKNOWN,
    HealthConfig,
    _empty_metrics,
    classify_health_status,
    compute_reliability_score,
    extract_domain,
    get_all_source_health,
    get_source_health,
    is_source_healthy,
    refresh_all_source_health,
    refresh_source_health,
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


def _make_attempt(
    session,
    scholarship_id: int,
    source_url: str,
    status: str,
    error_type: str | None = None,
    attempt_at: datetime | None = None,
) -> ScholarshipFetchAttempt:
    attempt = ScholarshipFetchAttempt(
        scholarship_id=scholarship_id,
        source_url=source_url,
        status=status,
        attempt_count=1,
        max_attempts=5,
        last_error_type=error_type,
        last_attempt_at=attempt_at or datetime.now(timezone.utc),
    )
    session.add(attempt)
    session.flush()
    return attempt


class TestHealthySource:
    def test_healthy_source_high_success_rate(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(10):
            _make_attempt(
                session, scholarship.id, "https://daad.de/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "daad.de")
        session.commit()

        assert health is not None
        assert health.health_status == HEALTHY
        assert health.success_count == 10
        assert health.failure_count == 0
        assert health.consecutive_failures == 0
        assert health.reliability_score > 80.0

    def test_healthy_source_with_manual_override(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(10):
            _make_attempt(
                session, scholarship.id, "https://daad.de/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "daad.de")
        health.manual_override = DEGRADED
        session.commit()

        refreshed = refresh_source_health(session, "daad.de")
        assert refreshed.health_status == DEGRADED
        assert refreshed.manual_override == DEGRADED


class TestDegradedSource:
    def test_degraded_source_moderate_failures(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(5):
            _make_attempt(
                session, scholarship.id, "https://erasmus-plus.ec.europa.eu/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i + 2),
            )
        for i in range(5):
            _make_attempt(
                session, scholarship.id, "https://erasmus-plus.ec.europa.eu/scholarship",
                "terminal", error_type="timeout",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "erasmus-plus.ec.europa.eu")
        session.commit()

        assert health is not None
        assert health.health_status in (DEGRADED, UNHEALTHY)
        assert health.failure_count > 0
        assert health.success_count > 0

    def test_degraded_source_consecutive_failures(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(4):
            _make_attempt(
                session, scholarship.id, "https://chevening.org/scholarship",
                "retrying", error_type="connection_error",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        config = HealthConfig(min_attempts_for_known=1)
        health = refresh_source_health(session, "chevening.org", config=config)
        session.commit()

        assert health.consecutive_failures >= 3
        assert health.health_status in (DEGRADED, UNHEALTHY)


class TestUnhealthySource:
    def test_unhealthy_source_high_failure_rate(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(2):
            _make_attempt(
                session, scholarship.id, "https://unhealthy-example.com/scholarship",
                "resolved", attempt_at=now - timedelta(hours=20),
            )
        for i in range(8):
            _make_attempt(
                session, scholarship.id, "https://unhealthy-example.com/scholarship",
                "terminal", error_type="not_found",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "unhealthy-example.com")
        session.commit()

        assert health is not None
        assert health.health_status == UNHEALTHY
        assert health.failure_count > health.success_count
        assert health.reliability_score < 50.0

    def test_unhealthy_source_many_consecutive_failures(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(6):
            _make_attempt(
                session, scholarship.id, "https://failing-source.org/scholarship",
                "retrying", error_type="timeout",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        config = HealthConfig(min_attempts_for_known=1)
        health = refresh_source_health(session, "failing-source.org", config=config)
        session.commit()

        assert health.consecutive_failures >= 5
        assert health.health_status == UNHEALTHY


class TestUnknownSource:
    def test_unknown_source_no_history(self, session):
        health = refresh_source_health(session, "unknown-source.com")
        session.commit()

        assert health is not None
        assert health.health_status == UNKNOWN
        assert health.total_count == 0
        assert health.reliability_score == 0.0

    def test_unknown_source_few_attempts(self, session, scholarship):
        now = datetime.now(timezone.utc)
        _make_attempt(
            session, scholarship.id, "https://new-source.org/scholarship",
            "resolved", attempt_at=now,
        )
        session.commit()

        config = HealthConfig(min_attempts_for_known=5)
        health = refresh_source_health(session, "new-source.org", config=config)
        session.commit()

        assert health.health_status == UNKNOWN


class TestSuccessFailureRatio:
    def test_success_failure_ratio_calculated(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(7):
            _make_attempt(
                session, scholarship.id, "https://mixed-source.com/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i + 3),
            )
        for i in range(3):
            _make_attempt(
                session, scholarship.id, "https://mixed-source.com/scholarship",
                "terminal", error_type="server_error",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "mixed-source.com")
        session.commit()

        assert health.success_count == 7
        assert health.failure_count == 3


class TestConsecutiveFailures:
    def test_consecutive_failures_counted(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(5):
            _make_attempt(
                session, scholarship.id, "https://consecutive-failures.com/scholarship",
                "retrying", error_type="connection_error",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "consecutive-failures.com")
        session.commit()

        assert health.consecutive_failures == 5

    def test_consecutive_failures_reset_by_success(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(3):
            _make_attempt(
                session, scholarship.id, "https://reset-failures.com/scholarship",
                "retrying", error_type="timeout",
                attempt_at=now - timedelta(hours=i + 1),
            )
        _make_attempt(
            session, scholarship.id, "https://reset-failures.com/scholarship",
            "resolved", attempt_at=now,
        )
        session.commit()

        health = refresh_source_health(session, "reset-failures.com")
        session.commit()

        assert health.consecutive_failures == 0


class TestRateLimitImpact:
    def test_rate_limit_increases_failure_count(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(5):
            _make_attempt(
                session, scholarship.id, "https://rate-limited.com/scholarship",
                "retrying", error_type="rate_limited",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "rate-limited.com")
        session.commit()

        assert health.rate_limit_count == 5
        assert health.failure_count == 5


class TestSourceIsolation:
    def test_source_isolation(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(10):
            _make_attempt(
                session, scholarship.id, "https://healthy-source.com/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i),
            )
        for i in range(10):
            _make_attempt(
                session, scholarship.id, "https://unhealthy-source.com/scholarship",
                "terminal", error_type="not_found",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        healthy = refresh_source_health(session, "healthy-source.com")
        unhealthy = refresh_source_health(session, "unhealthy-source.com")
        session.commit()

        assert healthy.health_status == HEALTHY
        assert unhealthy.health_status == UNHEALTHY
        assert healthy.reliability_score > unhealthy.reliability_score


class TestDeterministicScore:
    def test_deterministic_score(self):
        score1 = compute_reliability_score(
            success_count=8, failure_count=2, timeout_count=1,
            rate_limit_count=0, consecutive_failures=1, total_count=10,
        )
        score2 = compute_reliability_score(
            success_count=8, failure_count=2, timeout_count=1,
            rate_limit_count=0, consecutive_failures=1, total_count=10,
        )
        assert score1 == score2

    def test_score_bounds(self):
        score = compute_reliability_score(
            success_count=0, failure_count=100, timeout_count=50,
            rate_limit_count=25, consecutive_failures=10, total_count=100,
        )
        assert 0.0 <= score <= 100.0


class TestEmptyHistory:
    def test_empty_history_returns_unknown(self, session):
        health = refresh_source_health(session, "no-history.com")
        session.commit()

        assert health.health_status == UNKNOWN
        assert health.success_count == 0
        assert health.failure_count == 0
        assert health.consecutive_failures == 0


class TestNoNPlusOneQueries:
    def test_refresh_all_single_query(self, session, scholarship):
        now = datetime.now(timezone.utc)
        domains = ["domain1.com", "domain2.com", "domain3.com"]
        for i, domain in enumerate(domains):
            for j in range(3):
                _make_attempt(
                    session, scholarship.id, f"https://{domain}/scholarship",
                    "resolved", attempt_at=now - timedelta(hours=i * 3 + j),
                )
        session.commit()

        results = refresh_all_source_health(session)
        session.commit()

        assert len(results) >= 3
        for r in results:
            assert r.computed_at is not None


class TestRestartSafeState:
    def test_state_survives_session_recreate(self, engine, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(5):
            _make_attempt(
                session, scholarship.id, "https://persistent-source.com/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        health = refresh_source_health(session, "persistent-source.com")
        session.commit()

        domain = health.domain
        status = health.health_status

        Session2 = sessionmaker(bind=engine)
        new_session = Session2()

        persisted = get_source_health(new_session, domain)
        assert persisted is not None
        assert persisted.health_status == status
        assert persisted.success_count == 5

        new_session.close()


class TestIsSourceHealthy:
    def test_is_source_healthy_true_by_default(self, session):
        assert is_source_healthy(session, "unknown.com") is True

    def test_is_source_healthy_false_when_unhealthy(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(10):
            _make_attempt(
                session, scholarship.id, "https://bad-source.com/scholarship",
                "terminal", error_type="not_found",
                attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        refresh_source_health(session, "bad-source.com")
        session.commit()

        assert is_source_healthy(session, "bad-source.com") is False


class TestExtractDomain:
    def test_extract_domain_valid_url(self):
        assert extract_domain("https://www.daad.de/en/scholarship") == "www.daad.de"

    def test_extract_domain_empty_string(self):
        assert extract_domain("") is None

    def test_extract_domain_none(self):
        assert extract_domain(None) is None


class TestClassifyHealthStatus:
    def test_classify_healthy(self):
        status = classify_health_status(
            reliability_score=90.0, total_count=10,
            consecutive_failures=0, config=HealthConfig(),
        )
        assert status == HEALTHY

    def test_classify_degraded(self):
        status = classify_health_status(
            reliability_score=60.0, total_count=10,
            consecutive_failures=0, config=HealthConfig(),
        )
        assert status == DEGRADED

    def test_classify_unhealthy(self):
        status = classify_health_status(
            reliability_score=30.0, total_count=10,
            consecutive_failures=0, config=HealthConfig(),
        )
        assert status == UNHEALTHY

    def test_classify_unknown_no_attempts(self):
        status = classify_health_status(
            reliability_score=0.0, total_count=0,
            consecutive_failures=0, config=HealthConfig(),
        )
        assert status == UNKNOWN


class TestGetAllSourceHealth:
    def test_get_all_source_health(self, session, scholarship):
        now = datetime.now(timezone.utc)
        for i in range(3):
            _make_attempt(
                session, scholarship.id, "https://source-a.com/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i),
            )
        for i in range(3):
            _make_attempt(
                session, scholarship.id, "https://source-b.com/scholarship",
                "resolved", attempt_at=now - timedelta(hours=i),
            )
        session.commit()

        refresh_source_health(session, "source-a.com")
        refresh_source_health(session, "source-b.com")
        session.commit()

        all_health = get_all_source_health(session)
        domains = {h.domain for h in all_health}
        assert "source-a.com" in domains
        assert "source-b.com" in domains


class TestEmptyMetrics:
    def test_empty_metrics_defaults(self):
        m = _empty_metrics()
        assert m.total == 0
        assert m.successes == 0
        assert m.consecutive_failures == 0
        assert m.last_success_at is None
