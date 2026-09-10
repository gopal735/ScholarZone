"""Regression tests for seed.py status authority fix."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, ScholarshipVerificationHistory
from app.seed import refresh_scholarship_statuses
from app.services.lifecycle_manager import (
    apply_lifecycle_transition,
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
            "is_verified": True,
        }
        defaults.update(kwargs)
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s

    return _make


def _record_authored_status(session, scholarship, old_status, new_status):
    session.add(
        ScholarshipVerificationHistory(
            scholarship_id=scholarship.id,
            field_name="status",
            old_value=old_status,
            new_value=new_status,
            change_type="modified",
            source_url="https://example.com/official",
            evidence_text="Authoritative lifecycle evaluation",
            confidence="high",
            verification_status="active",
        )
    )
    session.commit()


class TestPreserveUpcoming:
    """Requirement 2: never convert UPCOMING -> OPEN merely because deadline is NULL or far future."""

    def test_upcoming_with_future_deadline_remains_upcoming(self, session, scholarship_factory):
        s = scholarship_factory(
            status="upcoming",
            deadline_date=date.today() + timedelta(days=60),
            is_verified=True,
        )
        _record_authored_status(session, s, "open", "upcoming")

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 0
        assert s.status == "upcoming"

    def test_upcoming_with_null_deadline_remains_upcoming(self, session, scholarship_factory):
        s = scholarship_factory(
            status="upcoming",
            deadline_date=None,
            is_verified=True,
        )
        _record_authored_status(session, s, "open", "upcoming")

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 0
        assert s.status == "upcoming"


class TestPreserveVerifiedLifecycleStates:
    """Requirement 3: seed must not blindly overwrite CLOSING-SOON or CLOSED."""

    def test_closing_soon_not_overwritten(self, session, scholarship_factory):
        s = scholarship_factory(
            status="closing-soon",
            deadline_date=date.today() + timedelta(days=5),
            is_verified=True,
        )
        _record_authored_status(session, s, "open", "closing-soon")

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 0
        assert s.status == "closing-soon"

    def test_closed_not_reopened_by_seed(self, session, scholarship_factory):
        s = scholarship_factory(
            status="closed",
            deadline_date=date.today() - timedelta(days=10),
            is_verified=True,
        )
        _record_authored_status(session, s, "open", "closed")

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 0
        assert s.status == "closed"


class TestSeedIdempotency:
    """Requirement 5: seed twice -> no unauthorized status changes."""

    def test_seed_twice_produces_no_status_changes(self, session, scholarship_factory):
        s1 = scholarship_factory(
            status="open",
            deadline_date=date.today() + timedelta(days=60),
            is_verified=True,
        )
        s2 = scholarship_factory(
            status="upcoming",
            deadline_date=None,
            is_verified=True,
        )
        _record_authored_status(session, s2, "open", "upcoming")

        first = refresh_scholarship_statuses(session)
        second = refresh_scholarship_statuses(session)

        assert first == 0  # s1 open+future deadline -> no transition; s2 upcoming+authored -> skipped
        assert second == 0
        session.refresh(s2)
        assert s2.status == "upcoming"


class TestLifecycleAuthority:
    """Requirement 1 & 6: lifecycle manager remains the sole authority for transitions."""

    def test_lifecycle_manager_is_only_authority_for_transitions(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() - timedelta(days=1),
            is_verified=True,
        )
        evaluation = evaluate_lifecycle(s)
        assert evaluation.should_transition
        assert evaluation.proposed_state == "closed"

        transition = apply_lifecycle_transition(session, s, evaluation)
        session.commit()

        assert transition is not None
        assert s.status == "closed"

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)
        assert changed == 0
        assert s.status == "closed"

    def test_seed_does_not_modify_production_data(self, session, scholarship_factory):
        """Requirement 6: seed must not bulk-correct existing records."""
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() - timedelta(days=1),
            is_verified=True,
        )
        _record_authored_status(session, s, "open", "closed")
        s.status = "closed"
        session.commit()

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 0
        assert s.status == "closed"


class TestAuditHistory:
    """Requirement 5: every automatic transition writes verification history."""

    def test_seed_writes_audit_for_never_evaluated_records(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() - timedelta(days=1),
            is_verified=True,
        )

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 1
        assert s.status == "closed"

        history = session.execute(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == s.id,
                ScholarshipVerificationHistory.field_name == "status",
            )
        ).scalar()
        assert history is not None
        assert history.old_value == "open"
        assert history.new_value == "closed"
        assert history.change_type == "modified"
        assert history.verification_status == "active"

    def test_seed_writes_audit_for_closing_soon(self, session, scholarship_factory):
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() + timedelta(days=5),
            is_verified=True,
        )

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 1
        assert s.status == "closing-soon"

        history = session.execute(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == s.id,
                ScholarshipVerificationHistory.field_name == "status",
            )
        ).scalar()
        assert history is not None
        assert history.old_value == "open"
        assert history.new_value == "closing-soon"


class TestNoDirectStatusAssignment:
    """Requirement 5: NO direct scholarship.status = ... for existing records in seed path."""

    def test_seed_does_not_directly_assign_status(self, session, scholarship_factory):
        """Verify the seed path uses apply_lifecycle_transition, not direct assignment."""
        s = scholarship_factory(
            status="open",
            deadline_date=date.today() - timedelta(days=1),
            is_verified=True,
        )

        changed = refresh_scholarship_statuses(session)
        session.refresh(s)

        assert changed == 1
        assert s.status == "closed"

        history_count = session.execute(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == s.id,
                ScholarshipVerificationHistory.field_name == "status",
            )
        ).all()
        assert len(history_count) == 1