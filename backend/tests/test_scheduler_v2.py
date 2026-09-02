"""Tests for the intelligent verification scheduler."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipReview,
    ScholarshipVerificationHistory,
)
from app.services.scheduler_config import SchedulerConfig
from app.services.scheduler_engine import SchedulerEngine
from app.services.scheduler_priority import (
    PriorityScore,
    calculate_priority,
    compute_change_frequency,
    compute_deadline_urgency,
    compute_impact,
    compute_review_pending,
    compute_source_reliability,
    compute_staleness,
)
from app.services.scheduler_queue import QueuedJob, VerificationQueue


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


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


@pytest.fixture
def config():
    return SchedulerConfig(max_workers=2, batch_size=10)


@pytest.fixture
def scheduler(session_factory, config):
    return SchedulerEngine(session_factory=session_factory, config=config)


class TestPriorityCalculation:
    def test_staleness_overdue(self, session, scholarship):
        scholarship.next_verification_due = date.today() - timedelta(days=30)
        session.commit()
        score = compute_staleness(scholarship, date.today(), SchedulerConfig())
        assert score > 0

    def test_staleness_not_due(self, session, scholarship):
        scholarship.next_verification_due = date.today() + timedelta(days=30)
        session.commit()
        score = compute_staleness(scholarship, date.today(), SchedulerConfig())
        assert score == 0

    def test_staleness_never_verified(self, session, scholarship):
        scholarship.next_verification_due = None
        session.commit()
        score = compute_staleness(scholarship, date.today(), SchedulerConfig())
        assert score == 100

    def test_staleness_capped(self, session, scholarship):
        scholarship.next_verification_due = date.today() - timedelta(days=1000)
        session.commit()
        score = compute_staleness(scholarship, date.today(), SchedulerConfig())
        assert score == 100

    def test_deadline_urgency_close(self, session, scholarship):
        scholarship.deadline_date = date.today() + timedelta(days=10)
        session.commit()
        score = compute_deadline_urgency(scholarship, date.today(), SchedulerConfig())
        assert score > 50

    def test_deadline_urgency_far(self, session, scholarship):
        scholarship.deadline_date = date.today() + timedelta(days=200)
        session.commit()
        score = compute_deadline_urgency(scholarship, date.today(), SchedulerConfig())
        assert score == 0

    def test_deadline_urgency_past(self, session, scholarship):
        scholarship.deadline_date = date.today() - timedelta(days=10)
        session.commit()
        score = compute_deadline_urgency(scholarship, date.today(), SchedulerConfig())
        assert score == 0

    def test_deadline_urgency_none(self, session, scholarship):
        scholarship.deadline_date = None
        session.commit()
        score = compute_deadline_urgency(scholarship, date.today(), SchedulerConfig())
        assert score == 0

    def test_change_frequency_zero(self, session, scholarship):
        score = compute_change_frequency(session, scholarship, date.today(), SchedulerConfig())
        assert score == 0

    def test_change_frequency_with_history(self, session, scholarship):
        for _ in range(3):
            h = ScholarshipVerificationHistory(
                scholarship_id=scholarship.id,
                field_name="status",
                old_value="open",
                new_value="closed",
                change_type="modified",
                verification_status="active",
            )
            session.add(h)
        session.commit()
        score = compute_change_frequency(session, scholarship, date.today(), SchedulerConfig())
        assert score > 0

    def test_source_reliability_no_attempts(self, session, scholarship):
        score = compute_source_reliability(session, scholarship)
        assert score == 50

    def test_source_reliability_all_terminal(self, session, scholarship):
        for _ in range(3):
            a = ScholarshipFetchAttempt(
                scholarship_id=scholarship.id,
                source_url=scholarship.official_source_url,
                status="terminal",
                terminal=True,
            )
            session.add(a)
        session.commit()
        score = compute_source_reliability(session, scholarship)
        assert score == 100

    def test_source_reliability_mixed(self, session, scholarship):
        session.add(ScholarshipFetchAttempt(
            scholarship_id=scholarship.id,
            source_url=scholarship.official_source_url,
            status="resolved",
            terminal=False,
        ))
        session.add(ScholarshipFetchAttempt(
            scholarship_id=scholarship.id,
            source_url=scholarship.official_source_url,
            status="terminal",
            terminal=True,
        ))
        session.commit()
        score = compute_source_reliability(session, scholarship)
        assert score == 50

    def test_review_pending_none(self, session, scholarship):
        score = compute_review_pending(session, scholarship)
        assert score == 0

    def test_review_pending_exists(self, session, scholarship):
        r = ScholarshipReview(
            scholarship_id=scholarship.id,
            field_name="status",
            conflict_reason="low_confidence",
            verification_state="uncertain",
            decision="pending",
        )
        session.add(r)
        session.commit()
        score = compute_review_pending(session, scholarship)
        assert score == 100

    def test_impact_zero(self, session, scholarship):
        score = compute_impact(session, scholarship, date.today(), SchedulerConfig())
        assert score == 0

    def test_impact_with_changes(self, session, scholarship):
        for _ in range(5):
            h = ScholarshipVerificationHistory(
                scholarship_id=scholarship.id,
                field_name="status",
                old_value="open",
                new_value="closed",
                change_type="modified",
                verification_status="active",
            )
            session.add(h)
        session.commit()
        score = compute_impact(session, scholarship, date.today(), SchedulerConfig())
        assert score > 0

    def test_calculate_priority_deterministic(self, session, scholarship):
        p1 = calculate_priority(session, scholarship, date.today())
        p2 = calculate_priority(session, scholarship, date.today())
        assert p1 == p2

    def test_priority_sort_key_ordering(self):
        low = PriorityScore(scholarship_id=1, staleness=10)
        high = PriorityScore(scholarship_id=2, staleness=100)
        assert high.to_sort_key() < low.to_sort_key()

    def test_priority_total_weights(self):
        score = PriorityScore(scholarship_id=1, staleness=50, deadline_urgency=50)
        cfg = SchedulerConfig()
        expected = 50 * cfg.staleness_weight + 50 * cfg.deadline_urgency_weight
        assert score.total == expected


class TestVerificationQueue:
    def test_enqueue_dequeue(self):
        q = VerificationQueue()
        job = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1, staleness=50))
        assert q.enqueue(job) is True
        assert q.size == 1
        dequeued = q.dequeue()
        assert dequeued is not None
        assert dequeued.scholarship_id == 1

    def test_duplicate_prevention(self):
        q = VerificationQueue()
        job1 = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1, staleness=50))
        job2 = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1, staleness=100))
        assert q.enqueue(job1) is True
        assert q.enqueue(job2) is False
        assert q.size == 1

    def test_different_sources_allowed(self):
        q = VerificationQueue()
        job1 = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1))
        job2 = QueuedJob(scholarship_id=1, source_url="https://b.com", priority=PriorityScore(scholarship_id=1))
        assert q.enqueue(job1) is True
        assert q.enqueue(job2) is True
        assert q.size == 2

    def test_running_prevents_reenqueue(self):
        q = VerificationQueue()
        job = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1))
        q.enqueue(job)
        q.dequeue()
        assert q.is_running(1, "https://a.com")
        assert q.enqueue(job) is False

    def test_mark_completed_allows_reenqueue(self):
        q = VerificationQueue()
        job = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1))
        q.enqueue(job)
        q.dequeue()
        q.mark_completed(job)
        assert q.is_active(1, "https://a.com") is False
        assert q.enqueue(job) is True

    def test_priority_ordering(self):
        q = VerificationQueue()
        low = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1, staleness=10))
        high = QueuedJob(scholarship_id=2, source_url="https://b.com", priority=PriorityScore(scholarship_id=2, staleness=100))
        q.enqueue(low)
        q.enqueue(high)
        first = q.dequeue()
        assert first is not None
        assert first.scholarship_id == 2

    def test_clear_returns_jobs(self):
        q = VerificationQueue()
        job = QueuedJob(scholarship_id=1, source_url="https://a.com", priority=PriorityScore(scholarship_id=1))
        q.enqueue(job)
        cleared = q.clear()
        assert len(cleared) == 1
        assert q.size == 0


class TestSchedulerEngine:
    def test_start_shutdown(self, scheduler):
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.shutdown()
        assert scheduler.is_running is False

    def test_double_start_noop(self, scheduler):
        scheduler.start()
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.shutdown()

    def test_find_due_candidates(self, session_factory, config):
        engine = SchedulerEngine(session_factory=session_factory, config=config)
        session = session_factory()
        s1 = Scholarship(
            title="Due", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://a.com/due",
            next_verification_due=date.today() - timedelta(days=1),
        )
        s2 = Scholarship(
            title="Future", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://b.com/future",
            next_verification_due=date.today() + timedelta(days=30),
        )
        s3 = Scholarship(
            title="NoURL", country="Germany", degree="Masters", funding="Full",
            official_source_url=None,
            next_verification_due=date.today() - timedelta(days=1),
        )
        session.add_all([s1, s2, s3])
        session.commit()

        candidates = engine.find_due_candidates(session, date.today())
        ids = {c.id for c in candidates}
        assert s1.id in ids
        assert s2.id not in ids
        assert s3.id not in ids
        session.close()

    def test_find_due_candidates_includes_null_due(self, session_factory, config):
        engine = SchedulerEngine(session_factory=session_factory, config=config)
        session = session_factory()
        s = Scholarship(
            title="Never", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://c.com/never",
            next_verification_due=None,
        )
        session.add(s)
        session.commit()
        candidates = engine.find_due_candidates(session, date.today())
        assert any(c.id == s.id for c in candidates)
        session.close()

    def test_enqueue_skips_already_active(self, session_factory, config):
        engine = SchedulerEngine(session_factory=session_factory, config=config)
        session = session_factory()
        s = Scholarship(
            title="Test", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://d.com/test",
            next_verification_due=date.today() - timedelta(days=1),
        )
        session.add(s)
        session.commit()

        count1 = engine.enqueue_candidates([s])
        assert count1 == 1
        count2 = engine.enqueue_candidates([s])
        assert count2 == 0
        session.close()

    def test_submit_batch_not_running(self, scheduler):
        result = scheduler.submit_batch()
        assert result == 0

    def test_shutdown_stops_processing(self, session_factory, config):
        engine = SchedulerEngine(session_factory=session_factory, config=config)
        engine.start()
        engine.shutdown()
        assert engine.is_running is False

    def test_graceful_shutdown_with_pending(self, session_factory, config):
        engine = SchedulerEngine(session_factory=session_factory, config=config)
        session = session_factory()
        for i in range(5):
            s = Scholarship(
                title=f"S{i}", country="Germany", degree="Masters", funding="Full",
                official_source_url=f"https://e.com/s{i}",
                next_verification_due=date.today() - timedelta(days=1),
            )
            session.add(s)
        session.commit()
        session.close()

        engine.start()
        engine.enqueue_candidates(session_factory().query(Scholarship).all())
        engine.shutdown(wait=False)
        assert engine.is_running is False


class TestSchedulerIntegration:
    def test_end_to_end_priority_respected(self, session_factory):
        cfg = SchedulerConfig(max_workers=1, batch_size=10)
        engine = SchedulerEngine(session_factory=session_factory, config=cfg)
        session = session_factory()

        s_low = Scholarship(
            title="Low", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://low.com",
            next_verification_due=date.today() - timedelta(days=1),
        )
        s_high = Scholarship(
            title="High", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://high.com",
            next_verification_due=date.today() - timedelta(days=60),
        )
        session.add_all([s_low, s_high])
        session.commit()

        engine.start()
        engine.enqueue_candidates([s_low, s_high])

        first = engine.queue.dequeue()
        assert first is not None
        assert first.scholarship_id == s_high.id

        engine.shutdown()
        session.close()

    def test_retry_state_affects_priority(self, session_factory):
        cfg = SchedulerConfig(max_workers=1, batch_size=10)
        engine = SchedulerEngine(session_factory=session_factory, config=cfg)
        session = session_factory()

        s = Scholarship(
            title="Retry", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://retry.com",
            next_verification_due=date.today() - timedelta(days=1),
        )
        session.add(s)
        session.commit()

        attempt = ScholarshipFetchAttempt(
            scholarship_id=s.id,
            source_url=s.official_source_url,
            status="retrying",
            next_retry_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session.add(attempt)
        session.commit()

        priority = calculate_priority(session, s, date.today())
        assert priority.retry_pending == 100
        session.close()

    def test_source_isolation(self, session_factory):
        cfg = SchedulerConfig(max_workers=2, batch_size=10)
        engine = SchedulerEngine(session_factory=session_factory, config=cfg)
        session = session_factory()

        s1 = Scholarship(
            title="A", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://source-a.com",
            next_verification_due=date.today() - timedelta(days=1),
        )
        s2 = Scholarship(
            title="B", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://source-b.com",
            next_verification_due=date.today() - timedelta(days=1),
        )
        session.add_all([s1, s2])
        session.commit()

        engine.start()
        engine.enqueue_candidates([s1, s2])
        assert engine.queue.size == 2
        engine.shutdown()
        session.close()

    def test_restart_safe_no_duplicate(self, session_factory):
        cfg = SchedulerConfig(max_workers=1, batch_size=10)

        engine1 = SchedulerEngine(session_factory=session_factory, config=cfg)
        session = session_factory()
        s = Scholarship(
            title="Restart", country="Germany", degree="Masters", funding="Full",
            official_source_url="https://restart.com",
            next_verification_due=date.today() - timedelta(days=1),
        )
        session.add(s)
        session.commit()

        engine1.start()
        engine1.enqueue_candidates([s])
        assert engine1.queue.size == 1
        engine1.shutdown()

        engine2 = SchedulerEngine(session_factory=session_factory, config=cfg)
        engine2.start()
        engine2.enqueue_candidates([s])
        assert engine2.queue.size == 1
        engine2.shutdown()
        session.close()


class TestSchedulerConfig:
    def test_default_values(self):
        cfg = SchedulerConfig()
        assert cfg.max_workers == 4
        assert cfg.batch_size == 100

    def test_custom_values(self):
        cfg = SchedulerConfig(max_workers=8, batch_size=50)
        assert cfg.max_workers == 8
        assert cfg.batch_size == 50

    def test_weights_positive(self):
        cfg = SchedulerConfig()
        assert cfg.staleness_weight > 0
        assert cfg.deadline_urgency_weight > 0
        assert cfg.change_frequency_weight > 0
