"""Tests for change impact and field-level staleness intelligence."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, SourceHealth
from app.services.change_impact_staleness import (
    CRITICAL,
    CRITICAL_STALE,
    FRESH,
    HIGH,
    LOW,
    MEDIUM,
    STALE,
    ChangeImpact,
    FieldStaleness,
    assess_scholarship_fields,
    compute_change_impact,
    compute_deadline_urgency,
    compute_field_staleness,
    compute_field_urgency,
    compute_overall_urgency,
    compute_urgency,
    get_field_criticality,
    get_freshness_threshold,
    get_source_health_confidence,
    is_field_critical_stale,
    is_field_stale,
    rank_fields_by_urgency,
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


class TestFieldCriticality:
    def test_critical_fields(self):
        assert get_field_criticality("deadline_date") == CRITICAL
        assert get_field_criticality("eligibility") == CRITICAL
        assert get_field_criticality("funding") == CRITICAL
        assert get_field_criticality("coverage") == CRITICAL
        assert get_field_criticality("application_method") == CRITICAL
        assert get_field_criticality("application_link") == CRITICAL

    def test_high_fields(self):
        assert get_field_criticality("required_documents") == HIGH
        assert get_field_criticality("requirements") == HIGH
        assert get_field_criticality("duration") == HIGH
        assert get_field_criticality("application_period") == HIGH
        assert get_field_criticality("english_requirement") == HIGH
        assert get_field_criticality("selection_notes") == HIGH

    def test_medium_fields(self):
        assert get_field_criticality("best_fit") == MEDIUM
        assert get_field_criticality("program_type") == MEDIUM
        assert get_field_criticality("notes") == MEDIUM
        assert get_field_criticality("catalogue_url") == MEDIUM
        assert get_field_criticality("official_updates_url") == MEDIUM

    def test_low_fields(self):
        assert get_field_criticality("title") == LOW
        assert get_field_criticality("description") == LOW
        assert get_field_criticality("country") == LOW
        assert get_field_criticality("degree") == LOW

    def test_unknown_field_defaults_to_low(self):
        assert get_field_criticality("nonexistent_field") == LOW


class TestFreshnessThresholds:
    def test_critical_field_thresholds(self):
        assert get_freshness_threshold("deadline_date") == 7
        assert get_freshness_threshold("application_link") == 14

    def test_high_field_thresholds(self):
        assert get_freshness_threshold("required_documents") == 60
        assert get_freshness_threshold("duration") == 90

    def test_medium_field_thresholds(self):
        assert get_freshness_threshold("best_fit") == 180
        assert get_freshness_threshold("program_type") == 180

    def test_low_field_thresholds(self):
        assert get_freshness_threshold("title") == 180
        assert get_freshness_threshold("country") == 365

    def test_unknown_field_default(self):
        assert get_freshness_threshold("nonexistent_field") == 90


class TestChangeImpact:
    def test_critical_field_change(self):
        impact = compute_change_impact("deadline_date", "2025-01-01", "2025-06-01")
        assert impact.field_name == "deadline_date"
        assert impact.impact_level == CRITICAL
        assert impact.impact_score == 100
        assert "critical" in impact.reason

    def test_high_field_change(self):
        impact = compute_change_impact("requirements", ["doc1"], ["doc1", "doc2"])
        assert impact.impact_level == HIGH
        assert impact.impact_score == 70

    def test_medium_field_change(self):
        impact = compute_change_impact("best_fit", "old", "new")
        assert impact.impact_level == MEDIUM
        assert impact.impact_score == 40

    def test_low_field_change(self):
        impact = compute_change_impact("description", "old", "new")
        assert impact.impact_level == LOW
        assert impact.impact_score == 10

    def test_new_field_populated(self):
        impact = compute_change_impact("deadline_date", None, "2025-06-01")
        assert impact.impact_score == 100
        assert "new" in impact.reason

    def test_field_cleared(self):
        impact = compute_change_impact("deadline_date", "2025-06-01", None)
        assert impact.impact_score == 100
        assert "cleared" in impact.reason

    def test_no_change(self):
        impact = compute_change_impact("deadline_date", "2025-06-01", "2025-06-01")
        assert impact.impact_score == 0
        assert "no change" in impact.reason


class TestFieldStaleness:
    def test_fresh_field(self):
        today = date(2026, 9, 1)
        verified_at = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
        staleness = compute_field_staleness("deadline_date", verified_at, today)
        assert staleness.freshness_state == FRESH
        assert staleness.staleness_score == 14
        assert staleness.age_days == 1

    def test_stale_field(self):
        today = date(2026, 9, 1)
        verified_at = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        staleness = compute_field_staleness("deadline_date", verified_at, today)
        assert staleness.freshness_state == STALE
        assert staleness.age_days == 10

    def test_critical_stale_field(self):
        today = date(2026, 9, 1)
        verified_at = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        staleness = compute_field_staleness("deadline_date", verified_at, today)
        assert staleness.freshness_state == CRITICAL_STALE
        assert staleness.age_days == 62

    def test_never_verified_field(self):
        staleness = compute_field_staleness("deadline_date", None)
        assert staleness.freshness_state == CRITICAL_STALE
        assert staleness.age_days is None
        assert staleness.last_verified_at is None
        assert staleness.staleness_score == 100

    def test_field_specific_thresholds(self):
        past = datetime.now(timezone.utc) - timedelta(days=100)
        stale_for_short = compute_field_staleness("deadline_date", past)
        assert stale_for_short.freshness_state == CRITICAL_STALE

        fresh_for_long = compute_field_staleness("country", past)
        assert fresh_for_long.freshness_state == FRESH

    def test_staleness_score_bounds(self):
        past = datetime.now(timezone.utc) - timedelta(days=365)
        staleness = compute_field_staleness("deadline_date", past)
        assert staleness.staleness_score == 100

    def test_different_fields_same_age_different_state(self):
        past = datetime.now(timezone.utc) - timedelta(days=200)
        deadline = compute_field_staleness("deadline_date", past)
        country = compute_field_staleness("country", past)
        assert deadline.freshness_state == CRITICAL_STALE
        assert country.freshness_state == FRESH


class TestDeadlineUrgency:
    def test_no_deadline(self):
        s = Scholarship(title="T", country="C", degree="D", funding="F")
        assert compute_deadline_urgency(s, date.today()) == 0

    def test_past_deadline(self):
        s = Scholarship(
            title="T", country="C", degree="D", funding="F",
            deadline_date=date.today() - timedelta(days=10),
        )
        assert compute_deadline_urgency(s, date.today()) == 0

    def test_critical_deadline(self):
        s = Scholarship(
            title="T", country="C", degree="D", funding="F",
            deadline_date=date.today() + timedelta(days=7),
        )
        assert compute_deadline_urgency(s, date.today()) == 100

    def test_urgent_deadline(self):
        s = Scholarship(
            title="T", country="C", degree="D", funding="F",
            deadline_date=date.today() + timedelta(days=21),
        )
        assert compute_deadline_urgency(s, date.today()) == 80

    def test_approaching_deadline(self):
        s = Scholarship(
            title="T", country="C", degree="D", funding="F",
            deadline_date=date.today() + timedelta(days=45),
        )
        assert compute_deadline_urgency(s, date.today()) == 50

    def test_distant_deadline(self):
        s = Scholarship(
            title="T", country="C", degree="D", funding="F",
            deadline_date=date.today() + timedelta(days=120),
        )
        assert compute_deadline_urgency(s, date.today()) == 10


class TestSourceHealthConfidence:
    def test_no_source_health(self):
        assert get_source_health_confidence(None) == 1.0

    def test_healthy_source(self):
        sh = SourceHealth(domain="example.com", health_status="healthy")
        assert get_source_health_confidence(sh) == 1.0

    def test_degraded_source(self):
        sh = SourceHealth(domain="example.com", health_status="degraded")
        assert get_source_health_confidence(sh) == 0.7

    def test_unhealthy_source(self):
        sh = SourceHealth(domain="example.com", health_status="unhealthy")
        assert get_source_health_confidence(sh) == 0.4

    def test_unknown_source(self):
        sh = SourceHealth(domain="example.com", health_status="unknown")
        assert get_source_health_confidence(sh) == 0.85

    def test_manual_override_takes_precedence(self):
        sh = SourceHealth(
            domain="example.com",
            health_status="unhealthy",
            manual_override="healthy",
        )
        assert get_source_health_confidence(sh) == 1.0


class TestFieldUrgency:
    def test_critical_stale_field_high_urgency(self):
        impact = compute_change_impact("deadline_date", "old", "new")
        past = datetime.now(timezone.utc) - timedelta(days=60)
        staleness = compute_field_staleness("deadline_date", past)
        urgency = compute_field_urgency(impact, staleness, 0)
        assert urgency > 50

    def test_fresh_low_field_low_urgency(self):
        impact = compute_change_impact("description", "old", "new")
        now = datetime.now(timezone.utc)
        staleness = compute_field_staleness("description", now)
        urgency = compute_field_urgency(impact, staleness, 0)
        assert urgency == 0

    def test_deadline_urgency_increases_field_urgency(self):
        impact = compute_change_impact("deadline_date", "old", "new")
        past = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        staleness = compute_field_staleness("deadline_date", past, date(2026, 9, 1))
        urgency_no_deadline = compute_field_urgency(impact, staleness, 0)
        urgency_with_deadline = compute_field_urgency(impact, staleness, 100)
        assert urgency_with_deadline >= urgency_no_deadline

    def test_critical_field_outranks_low_field(self):
        critical_impact = compute_change_impact("deadline_date", "old", "new")
        low_impact = compute_change_impact("description", "old", "new")
        past = datetime.now(timezone.utc) - timedelta(days=30)
        critical_staleness = compute_field_staleness("deadline_date", past)
        low_staleness = compute_field_staleness("description", past)
        critical_urgency = compute_field_urgency(critical_impact, critical_staleness, 0)
        low_urgency = compute_field_urgency(low_impact, low_staleness, 0)
        assert critical_urgency > low_urgency


class TestOverallUrgency:
    def test_empty_fields(self):
        assert compute_overall_urgency([], 50) == 50

    def test_single_field(self):
        overall = compute_overall_urgency([("deadline_date", 80)], 0)
        assert overall > 0
        assert overall <= 100

    def test_multiple_fields(self):
        fields = [("deadline_date", 80), ("description", 20)]
        overall = compute_overall_urgency(fields, 50)
        assert overall > 0
        assert overall <= 100

    def test_bounded_at_100(self):
        fields = [("deadline_date", 100), ("eligibility", 100), ("funding", 100)]
        overall = compute_overall_urgency(fields, 100)
        assert overall == 100


class TestAssessScholarshipFields:
    def test_assess_multiple_fields(self, session, scholarship):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=60)
        timestamps = {
            "deadline_date": past,
            "description": now,
            "country": None,
        }
        results = assess_scholarship_fields(session, scholarship, timestamps)
        assert len(results) == 3

    def test_never_verified_field_in_results(self, session, scholarship):
        timestamps = {"deadline_date": None}
        results = assess_scholarship_fields(session, scholarship, timestamps)
        assert len(results) == 1
        impact, staleness = results[0]
        assert staleness.freshness_state == CRITICAL_STALE


class TestComputeUrgency:
    def test_basic_urgency(self, session, scholarship):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=60)
        timestamps = {"deadline_date": past}
        urgency = compute_urgency(session, scholarship, timestamps)
        assert urgency.scholarship_id == scholarship.id
        assert urgency.overall_urgency > 0
        assert len(urgency.field_urgencies) == 1

    def test_source_health_influences_urgency(self, session, scholarship):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=30)
        timestamps = {"deadline_date": past}

        urgency_healthy = compute_urgency(session, scholarship, timestamps)

        sh = SourceHealth(domain="example.com", health_status="unhealthy")
        session.add(sh)
        session.commit()

        urgency_unhealthy = compute_urgency(session, scholarship, timestamps)
        assert urgency_unhealthy.source_health_confidence < urgency_healthy.source_health_confidence

    def test_deadline_urgency_included(self, session):
        s = Scholarship(
            title="T", country="C", degree="D", funding="F",
            deadline_date=date.today() + timedelta(days=7),
        )
        session.add(s)
        session.commit()
        urgency = compute_urgency(session, s, {})
        assert urgency.deadline_urgency == 100


class TestRankFieldsByUrgency:
    def test_ranking_order(self):
        from app.services.change_impact_staleness import UrgencyScore

        urgency = UrgencyScore(
            scholarship_id=1,
            overall_urgency=50,
            field_urgencies=[
                ("description", 10),
                ("deadline_date", 90),
                ("eligibility", 70),
            ],
            deadline_urgency=50,
            source_health_confidence=1.0,
        )
        ranked = rank_fields_by_urgency(urgency)
        assert ranked[0] == ("deadline_date", 90)
        assert ranked[1] == ("eligibility", 70)
        assert ranked[2] == ("description", 10)


class TestIsFieldStale:
    def test_fresh_field_not_stale(self):
        now = datetime.now(timezone.utc)
        assert not is_field_stale("deadline_date", now)

    def test_stale_field_is_stale(self):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        assert is_field_stale("deadline_date", past)

    def test_never_verified_is_stale(self):
        assert is_field_stale("deadline_date", None)

    def test_critical_stale_is_stale(self):
        past = datetime.now(timezone.utc) - timedelta(days=60)
        assert is_field_stale("deadline_date", past)


class TestIsFieldCriticalStale:
    def test_fresh_not_critical_stale(self):
        now = datetime.now(timezone.utc)
        assert not is_field_critical_stale("deadline_date", now)

    def test_stale_not_critical_stale(self):
        past = datetime.now(timezone.utc) - timedelta(days=10)
        assert not is_field_critical_stale("deadline_date", past)

    def test_critical_stale_is_critical_stale(self):
        past = datetime.now(timezone.utc) - timedelta(days=60)
        assert is_field_critical_stale("deadline_date", past)

    def test_never_verified_is_critical_stale(self):
        assert is_field_critical_stale("deadline_date", None)


class TestDeterministicResults:
    def test_same_input_same_output(self):
        impact1 = compute_change_impact("deadline_date", "old", "new")
        impact2 = compute_change_impact("deadline_date", "old", "new")
        assert impact1 == impact2

    def test_staleness_deterministic(self):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        s1 = compute_field_staleness("deadline_date", past)
        s2 = compute_field_staleness("deadline_date", past)
        assert s1 == s2

    def test_urgency_deterministic(self, session, scholarship):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        timestamps = {"deadline_date": past}
        u1 = compute_urgency(session, scholarship, timestamps)
        u2 = compute_urgency(session, scholarship, timestamps)
        assert u1 == u2


class TestImpactOrdering:
    def test_critical_scores_higher_than_high(self):
        critical = compute_change_impact("deadline_date", "old", "new")
        high = compute_change_impact("requirements", "old", "new")
        assert critical.impact_score > high.impact_score

    def test_high_scores_higher_than_medium(self):
        high = compute_change_impact("requirements", "old", "new")
        medium = compute_change_impact("best_fit", "old", "new")
        assert high.impact_score > medium.impact_score

    def test_medium_scores_higher_than_low(self):
        medium = compute_change_impact("best_fit", "old", "new")
        low = compute_change_impact("description", "old", "new")
        assert medium.impact_score > low.impact_score


class TestSchedulerCompatibility:
    def test_urgency_score_has_scholarship_id(self, session, scholarship):
        urgency = compute_urgency(session, scholarship, {})
        assert urgency.scholarship_id == scholarship.id

    def test_urgency_can_be_used_for_sorting(self, session):
        s1 = Scholarship(title="T1", country="C", degree="D", funding="F")
        s2 = Scholarship(title="T2", country="C", degree="D", funding="F")
        session.add_all([s1, s2])
        session.commit()

        past = datetime.now(timezone.utc) - timedelta(days=60)
        u1 = compute_urgency(session, s1, {"deadline_date": past})
        u2 = compute_urgency(session, s2, {"description": datetime.now(timezone.utc)})

        items = [(s1.id, u1.overall_urgency), (s2.id, u2.overall_urgency)]
        sorted_items = sorted(items, key=lambda x: -x[1])
        assert sorted_items[0][0] == s1.id
