"""Tests for adaptive verification frequency policy."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Base,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipVerificationHistory,
    SourceHealth,
)
from app.services.adaptive_policy import (
    BASE_INTERVAL_DAYS,
    MAX_INTERVAL_DAYS,
    MIN_INTERVAL_DAYS,
    AdaptiveVerificationPolicy,
    compute_adaptive_policy,
    compute_next_due_date,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def session(session_factory):
    return session_factory()


def _make_scholarship(
    session: Session,
    *,
    scholarship_id: int = 1,
    official_source_url: str | None = None,
    deadline_date: date | None = None,
    last_verified_at: date | None = None,
    status: str = "open",
    verification_status: str = "active",
    is_verified: bool = True,
) -> Scholarship:
    if official_source_url is None:
        official_source_url = f"https://example{scholarship_id}.gov/scholarship"
    s = Scholarship(
        id=scholarship_id,
        title=f"Test Scholarship {scholarship_id}",
        country="Test Country",
        degree="PhD",
        funding="Full",
        official_source_url=official_source_url,
        deadline_date=deadline_date,
        last_verified_at=last_verified_at,
        status=status,
        verification_status=verification_status,
        is_verified=is_verified,
    )
    session.add(s)
    session.commit()
    return s


def _make_source_health(
    session: Session,
    *,
    domain: str = "example.gov",
    health_status: str = "unknown",
    reliability_score: float = 0.0,
    consecutive_failures: int = 0,
    p95_latency_ms: float | None = None,
    success_count: int = 0,
    failure_count: int = 0,
    manual_override: str | None = None,
) -> SourceHealth:
    sh = SourceHealth(
        domain=domain,
        health_status=health_status,
        reliability_score=reliability_score,
        consecutive_failures=consecutive_failures,
        p95_latency_ms=p95_latency_ms,
        success_count=success_count,
        failure_count=failure_count,
        manual_override=manual_override,
    )
    session.add(sh)
    session.commit()
    return sh


def _make_history_entry(
    session: Session,
    scholarship_id: int,
    *,
    change_type: str = "modified",
    days_ago: int = 0,
) -> ScholarshipVerificationHistory:
    entry = ScholarshipVerificationHistory(
        scholarship_id=scholarship_id,
        field_name="deadline_date",
        old_value="2025-01-01",
        new_value="2025-02-01",
        change_type=change_type,
        source_url="https://example.gov/scholarship",
        verification_status="active",
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    session.add(entry)
    session.commit()
    return entry


def _make_fetch_attempt(
    session: Session,
    scholarship_id: int,
    source_url: str,
    *,
    status: str = "resolved",
    attempt_count: int = 1,
) -> ScholarshipFetchAttempt:
    attempt = ScholarshipFetchAttempt(
        scholarship_id=scholarship_id,
        source_url=source_url,
        status=status,
        attempt_count=attempt_count,
    )
    session.add(attempt)
    session.commit()
    return attempt


class TestStableSourceSlowsFrequency:
    def test_healthy_source_increases_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            domain=f"example{scholarship.id}.gov",
            health_status="healthy",
            reliability_score=95.0,
            consecutive_failures=0,
            success_count=20,
            failure_count=0,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days > MIN_INTERVAL_DAYS
        assert "source_healthy" in policy.reason_codes

    def test_stable_source_no_changes(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            domain=f"example{scholarship.id}.gov",
            health_status="healthy",
            reliability_score=90.0,
            consecutive_failures=0,
            success_count=10,
            failure_count=0,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days >= MIN_INTERVAL_DAYS
        assert policy.recommended_interval_days <= MAX_INTERVAL_DAYS


class TestFrequentChangesIncreaseFrequency:
    def test_high_change_frequency_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(session, health_status="healthy", reliability_score=90.0)

        for i in range(6):
            _make_history_entry(session, scholarship.id, days_ago=i * 10)

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days < BASE_INTERVAL_DAYS
        assert "high_change_frequency" in policy.reason_codes

    def test_moderate_change_frequency(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(session, health_status="healthy", reliability_score=90.0)

        for i in range(3):
            _make_history_entry(session, scholarship.id, days_ago=i * 20)

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days < BASE_INTERVAL_DAYS
        assert "moderate_change_frequency" in policy.reason_codes


class TestDeadlineNearIncreasesFrequency:
    def test_deadline_critical_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=7),
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days < BASE_INTERVAL_DAYS
        assert "deadline_critical" in policy.reason_codes

    def test_deadline_urgent_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=21),
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days < BASE_INTERVAL_DAYS
        assert "deadline_urgent" in policy.reason_codes

    def test_deadline_approaching_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=45),
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days < BASE_INTERVAL_DAYS
        assert "deadline_approaching" in policy.reason_codes


class TestStaleCriticalFieldIncreasesFrequency:
    def test_stale_critical_field_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=200),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert any("stale_critical_field" in code for code in policy.reason_codes)


class TestUnhealthySourceBacksOff:
    def test_unhealthy_source_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            domain=f"example{scholarship.id}.gov",
            health_status="unhealthy",
            reliability_score=30.0,
            consecutive_failures=6,
            success_count=2,
            failure_count=8,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert "source_unhealthy" in policy.reason_codes
        assert policy.recommended_interval_days < BASE_INTERVAL_DAYS

    def test_high_consecutive_failures_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            domain=f"example{scholarship.id}.gov",
            health_status="degraded",
            reliability_score=60.0,
            consecutive_failures=5,
            success_count=5,
            failure_count=5,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert "high_consecutive_failures" in policy.reason_codes


class TestRetryStateRespected:
    def test_active_retry_reduces_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_fetch_attempt(
            session,
            scholarship.id,
            scholarship.official_source_url,
            status="retrying",
            attempt_count=2,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert "active_retry_state" in policy.reason_codes
        assert policy.recommended_interval_days < BASE_INTERVAL_DAYS


class TestLifecycleAwarePolicy:
    def test_archived_lifecycle_max_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today - timedelta(days=400),
            status="open",
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days == MAX_INTERVAL_DAYS
        assert policy.priority_multiplier == 0.0

    def test_deadline_near_lifecycle(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=15),
            status="open",
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert any("lifecycle_deadline_near" in code for code in policy.reason_codes)

    def test_discovered_lifecycle(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            verification_status="pending",
            is_verified=False,
            last_verified_at=None,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert any("lifecycle_discovered" in code for code in policy.reason_codes)


class TestBoundedIntervals:
    def test_interval_never_below_minimum(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=1),
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            health_status="unhealthy",
            reliability_score=10.0,
            consecutive_failures=10,
        )

        for i in range(10):
            _make_history_entry(session, scholarship.id, days_ago=i * 5)

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days >= MIN_INTERVAL_DAYS

    def test_interval_never_above_maximum(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=500),
            last_verified_at=today - timedelta(days=30),
            status="closed",
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days <= MAX_INTERVAL_DAYS


class TestDeterministicOutput:
    def test_same_input_same_output(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(session, health_status="healthy", reliability_score=85.0)

        policy1 = compute_adaptive_policy(session, scholarship, today)
        policy2 = compute_adaptive_policy(session, scholarship, today)

        assert policy1.recommended_interval_days == policy2.recommended_interval_days
        assert policy1.priority_multiplier == policy2.priority_multiplier
        assert policy1.reason_codes == policy2.reason_codes
        assert policy1.confidence == policy2.confidence

    def test_different_inputs_different_output(self, session):
        today = date.today()
        scholarship1 = _make_scholarship(
            session,
            scholarship_id=1,
            last_verified_at=today - timedelta(days=30),
        )
        scholarship2 = _make_scholarship(
            session,
            scholarship_id=2,
            deadline_date=today + timedelta(days=7),
            last_verified_at=today - timedelta(days=30),
        )

        policy1 = compute_adaptive_policy(session, scholarship1, today)
        policy2 = compute_adaptive_policy(session, scholarship2, today)

        assert policy1.recommended_interval_days != policy2.recommended_interval_days


class TestNoVerificationStorm:
    def test_multiple_scholarships_different_intervals(self, session):
        today = date.today()
        scholarships = []
        for i in range(5):
            s = _make_scholarship(
                session,
                scholarship_id=i + 1,
                deadline_date=today + timedelta(days=10 * (i + 1)),
                last_verified_at=today - timedelta(days=30),
            )
            scholarships.append(s)

        policies = [compute_adaptive_policy(session, s, today) for s in scholarships]

        intervals = [p.recommended_interval_days for p in policies]
        assert len(set(intervals)) > 1

    def test_no_duplicate_reason_codes(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert len(policy.reason_codes) == len(set(policy.reason_codes))


class TestNoNPlusOne:
    def test_batch_computation_no_extra_queries(self, session):
        today = date.today()
        scholarships = []
        for i in range(10):
            s = _make_scholarship(
                session,
                scholarship_id=i + 1,
                last_verified_at=today - timedelta(days=30),
            )
            scholarships.append(s)

        policies = []
        for s in scholarships:
            policy = compute_adaptive_policy(session, s, today)
            policies.append(policy)

        assert len(policies) == 10
        assert all(isinstance(p, AdaptiveVerificationPolicy) for p in policies)


class TestComputeNextDueDate:
    def test_returns_future_date(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )

        next_due = compute_next_due_date(session, scholarship, today)

        assert next_due > today

    def test_respects_minimum_interval(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=1),
            last_verified_at=today - timedelta(days=30),
        )

        next_due = compute_next_due_date(session, scholarship, today)

        assert (next_due - today).days >= MIN_INTERVAL_DAYS


class TestConfidence:
    def test_confidence_bounded(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert 0.0 <= policy.confidence <= 1.0

    def test_more_data_higher_confidence(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            health_status="healthy",
            reliability_score=95.0,
            success_count=50,
            failure_count=2,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.confidence > 0.5


class TestPriorityMultiplier:
    def test_deadline_critical_increases_priority(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today + timedelta(days=7),
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.priority_multiplier > 1.0

    def test_archived_zero_priority(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            deadline_date=today - timedelta(days=400),
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.priority_multiplier == 0.0


class TestSourceSpecificAdaptation:
    def test_different_sources_different_policies(self, session):
        today = date.today()
        scholarship1 = _make_scholarship(
            session,
            scholarship_id=1,
            official_source_url="https://healthy.gov/scholarship",
            last_verified_at=today - timedelta(days=30),
        )
        scholarship2 = _make_scholarship(
            session,
            scholarship_id=2,
            official_source_url="https://unhealthy.gov/scholarship",
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            domain="healthy.gov",
            health_status="healthy",
            reliability_score=95.0,
            success_count=20,
        )
        _make_source_health(
            session,
            domain="unhealthy.gov",
            health_status="unhealthy",
            reliability_score=20.0,
            consecutive_failures=6,
            failure_count=10,
        )

        policy1 = compute_adaptive_policy(session, scholarship1, today)
        policy2 = compute_adaptive_policy(session, scholarship2, today)

        assert policy1.recommended_interval_days != policy2.recommended_interval_days


class TestScholarshipSpecificAdaptation:
    def test_different_deadlines_different_policies(self, session):
        today = date.today()
        scholarship1 = _make_scholarship(
            session,
            scholarship_id=1,
            deadline_date=today + timedelta(days=10),
            last_verified_at=today - timedelta(days=30),
        )
        scholarship2 = _make_scholarship(
            session,
            scholarship_id=2,
            deadline_date=today + timedelta(days=100),
            last_verified_at=today - timedelta(days=30),
        )

        policy1 = compute_adaptive_policy(session, scholarship1, today)
        policy2 = compute_adaptive_policy(session, scholarship2, today)

        assert policy1.recommended_interval_days < policy2.recommended_interval_days


class TestManualOverride:
    def test_manual_override_respected(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )
        _make_source_health(
            session,
            domain=f"example{scholarship.id}.gov",
            health_status="unhealthy",
            manual_override="healthy",
            reliability_score=30.0,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert "source_healthy" in policy.reason_codes


class TestEdgeCases:
    def test_no_source_health_data(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days >= MIN_INTERVAL_DAYS
        assert policy.recommended_interval_days <= MAX_INTERVAL_DAYS

    def test_no_official_source_url(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            official_source_url=None,
            last_verified_at=today - timedelta(days=30),
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days >= MIN_INTERVAL_DAYS

    def test_no_last_verified(self, session):
        today = date.today()
        scholarship = _make_scholarship(
            session,
            last_verified_at=None,
        )

        policy = compute_adaptive_policy(session, scholarship, today)

        assert policy.recommended_interval_days >= MIN_INTERVAL_DAYS
