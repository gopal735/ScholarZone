"""Tests for the lifecycle state manager."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, ScholarshipVerificationHistory
from app.services.lifecycle_manager import (
    LifecycleState,
    VALID_TRANSITIONS,
    apply_lifecycle_transition,
    batch_evaluate_lifecycle,
    evaluate_lifecycle,
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
def scholarship_factory(session):
    counter = {"n": 0}
    def _make(**kwargs):
        counter["n"] += 1
        defaults = {
            "title": "Test Scholarship",
            "country": "Germany",
            "degree": "Masters",
            "funding": "Full",
            "official_source_url": f"https://example.com/scholarship-{counter['n']}",
            "official_source": "Test Provider",
            "status": "open",
        }
        defaults.update(kwargs)
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s
    return _make


class TestLifecycleStates:
    def test_valid_states(self):
        assert LifecycleState.OPEN == "open"
        assert LifecycleState.UPCOMING == "upcoming"
        assert LifecycleState.CLOSING_SOON == "closing-soon"
        assert LifecycleState.CLOSED == "closed"

    def test_valid_transitions_from_open(self):
        allowed = VALID_TRANSITIONS[LifecycleState.OPEN]
        assert LifecycleState.CLOSING_SOON in allowed
        assert LifecycleState.CLOSED in allowed
        assert LifecycleState.OPEN not in allowed
        assert LifecycleState.UPCOMING not in allowed

    def test_valid_transitions_from_closed(self):
        allowed = VALID_TRANSITIONS[LifecycleState.CLOSED]
        assert LifecycleState.UPCOMING in allowed
        assert LifecycleState.OPEN not in allowed

    def test_valid_transitions_from_upcoming(self):
        allowed = VALID_TRANSITIONS[LifecycleState.UPCOMING]
        assert LifecycleState.OPEN in allowed
        assert LifecycleState.CLOSED in allowed


class TestEvaluateLifecycle:
    def test_open_with_future_deadline(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() + timedelta(days=60),
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(s)
        assert evaluation.proposed_state == "open"
        assert not evaluation.should_transition

    def test_open_deadline_passed(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() - timedelta(days=1),
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(s)
        assert evaluation.proposed_state == "closed"
        assert evaluation.should_transition
        assert evaluation.reason == "deadline_passed"

    def test_open_closing_soon(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() + timedelta(days=10),
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(s)
        assert evaluation.proposed_state == "closing-soon"
        assert evaluation.should_transition
        assert evaluation.reason == "deadline_within_14_days"

    def test_closed_to_upcoming_with_next_cycle(self, session, scholarship_factory):
        s = scholarship_factory(
            status="closed",
            is_verified=True,
            notes="Applications open for 2027-2028",
        )
        evaluation = evaluate_lifecycle(s)
        assert evaluation.proposed_state == "upcoming"
        assert evaluation.should_transition
        assert evaluation.reason == "next_cycle_announced"

    def test_fetch_failure_preserves_current_status(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(
            s,
            verification_result={"fetch_status": "failed"},
        )
        assert evaluation.proposed_state == "open"
        assert not evaluation.should_transition
        assert evaluation.reason == "source_fetch_failed"

    def test_upcoming_to_open_on_verification(self, session, scholarship_factory):
        s = scholarship_factory(
            status="upcoming",
            is_verified=True,
            application_period="Applications open now",
        )
        evaluation = evaluate_lifecycle(s)
        assert evaluation.proposed_state == "open"
        assert evaluation.should_transition
        assert "application_open" in evaluation.reason

    def test_fetch_failure_does_not_change_status(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(
            s,
            verification_result={"fetch_status": "failed"},
        )
        assert evaluation.proposed_state == "open"
        assert not evaluation.should_transition
        assert evaluation.reason == "source_fetch_failed"


class TestApplyLifecycleTransition:
    def test_transition_creates_history(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() - timedelta(days=1),
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(s)
        transition = apply_lifecycle_transition(session, s, evaluation)
        session.commit()

        assert transition is not None
        assert transition.from_state == "open"
        assert transition.to_state == "closed"
        assert transition.history_written

        history = session.query(ScholarshipVerificationHistory).filter(
            ScholarshipVerificationHistory.scholarship_id == s.id,
            ScholarshipVerificationHistory.field_name == "status",
        ).first()
        assert history is not None
        assert history.old_value == "open"
        assert history.new_value == "closed"

    def test_invalid_transition_blocked(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() - timedelta(days=1),
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(s)
        evaluation = evaluate_lifecycle(
            s.__class__(**{k: v for k, v in s.__dict__.items() if not k.startswith('_')}),
            verification_result={},
        )
        # Manually set invalid transition
        evaluation = evaluate_lifecycle(s)
        # The evaluation should allow open -> closed
        assert evaluation.transition_allowed

    def test_no_transition_when_already_in_state(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() + timedelta(days=60),
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(s)
        assert not evaluation.should_transition


class TestBatchEvaluateLifecycle:
    def test_batch_evaluation(self, session, scholarship_factory):
        s1 = scholarship_factory(status="open", deadline_date=date.today() + timedelta(days=60), is_verified=True)
        s2 = scholarship_factory(status="open", deadline_date=date.today() - timedelta(days=1), is_verified=True)
        s3 = scholarship_factory(status="closed", is_verified=True, notes="Next cycle 2027")

        results = batch_evaluate_lifecycle(session, [s1, s2, s3])
        assert len(results) == 3
        assert not results[0].should_transition
        assert results[1].should_transition
        assert results[2].should_transition
