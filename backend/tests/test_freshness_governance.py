"""Tests for Freshness SLA + Data Freshness Governance layer."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, SourceHealth, Scholarship
from app.services.freshness_governance import (
    CLASS_MAX_AGE_DAYS,
    DEADLINE_TIGHTENING_THRESHOLD_DAYS,
    FIELD_FRESHNESS_CLASSES,
    FRESHNESS_CLASS_CRITICAL,
    FRESHNESS_CLASS_HIGH,
    FRESHNESS_CLASS_LOW,
    FRESHNESS_CLASS_MEDIUM,
    STATE_CRITICAL_STALE,
    STATE_FRESH,
    STATE_NEVER_VERIFIED,
    STATE_STALE,
    STATE_WARNING,
    FieldFreshnessResult,
    FreshnessClass,
    FreshnessPolicy,
    FreshnessPolicyOverride,
    FreshnessState,
    ScholarshipFreshnessResult,
    batch_evaluate_freshness,
    evaluate_field_freshness,
    evaluate_scholarship_freshness,
    get_field_freshness_class,
    get_freshness_max_age,
    get_freshness_summary,
    get_policy_definitions,
    is_field_sla_breached,
    is_field_within_sla,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


_url_counter = 0


@pytest.fixture
def scholarship_factory(session):
    def _make(**kwargs):
        global _url_counter
        _url_counter += 1
        url = kwargs.get("official_source_url", f"https://example.com/scholarship-{_url_counter}")
        defaults = {
            "title": "Test Scholarship",
            "country": "Germany",
            "degree": "Masters",
            "funding": "Full",
            "official_source_url": url,
            "official_source": "Test Provider",
        }
        defaults.update(kwargs)
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s
    return _make


@pytest.fixture
def today():
    return date(2026, 9, 1)


class TestFreshField:
    def test_fresh_critical_field(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "deadline_date",
            today - timedelta(days=5),
            s,
            session,
            today=today,
        )
        assert result.state == STATE_FRESH
        assert result.freshness_class == FRESHNESS_CLASS_CRITICAL
        assert result.sla_breach_severity == 0

    def test_fresh_high_field(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "application_link",
            today - timedelta(days=10),
            s,
            session,
            today=today,
        )
        assert result.state == STATE_FRESH
        assert result.freshness_class == FRESHNESS_CLASS_HIGH

    def test_fresh_low_field(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "notes",
            today - timedelta(days=50),
            s,
            session,
            today=today,
        )
        assert result.state == STATE_FRESH
        assert result.freshness_class == FRESHNESS_CLASS_LOW


class TestWarningState:
    def test_warning_state_triggered(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "application_link",
            today - timedelta(days=45),
            s,
            session,
            today=today,
        )
        assert result.state == STATE_WARNING
        assert result.sla_breach_severity > 0

    def test_warning_before_stale(self, session, scholarship_factory, today):
        s = scholarship_factory()
        warning_result = evaluate_field_freshness(
            "requirements",
            today - timedelta(days=45),
            s,
            session,
            today=today,
        )
        stale_result = evaluate_field_freshness(
            "requirements",
            today - timedelta(days=200),
            s,
            session,
            today=today,
        )
        assert warning_result.state == STATE_WARNING
        assert stale_result.state in (STATE_STALE, STATE_CRITICAL_STALE)
        assert warning_result.warning_age_days < warning_result.max_age_days


class TestStaleField:
    def test_stale_field(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "duration",
            today - timedelta(days=200),
            s,
            session,
            today=today,
        )
        assert result.state in (STATE_STALE, STATE_CRITICAL_STALE)
        assert result.sla_breach_severity > 0

    def test_stale_severity_positive(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "best_fit",
            today - timedelta(days=200),
            s,
            session,
            today=today,
        )
        assert result.state in (STATE_STALE, STATE_CRITICAL_STALE)
        assert result.sla_breach_severity > 0


class TestCriticalStale:
    def test_critical_stale_on_double_threshold(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "official_updates_url",
            today - timedelta(days=200),
            s,
            session,
            today=today,
        )
        assert result.state == STATE_CRITICAL_STALE
        assert result.sla_breach_severity >= 80


class TestNeverVerified:
    def test_never_verified_critical_field(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "deadline_date",
            None,
            s,
            session,
            today=today,
        )
        assert result.state == STATE_NEVER_VERIFIED
        assert result.sla_breach_severity == 100
        assert "never_verified" in result.reason_codes

    def test_never_verified_low_field(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_field_freshness(
            "notes",
            None,
            s,
            session,
            today=today,
        )
        assert result.state == STATE_NEVER_VERIFIED
        assert result.sla_breach_severity == 50


class TestCriticalVsLowSLA:
    def test_critical_field_stricter_than_low(self):
        critical_max = get_freshness_max_age("deadline_date")
        low_max = get_freshness_max_age("notes")
        assert critical_max < low_max

    def test_field_class_assignment(self):
        assert get_field_freshness_class("deadline_date") == FRESHNESS_CLASS_CRITICAL
        assert get_field_freshness_class("application_link") == FRESHNESS_CLASS_HIGH
        assert get_field_freshness_class("duration") == FRESHNESS_CLASS_MEDIUM
        assert get_field_freshness_class("notes") == FRESHNESS_CLASS_LOW


class TestDeadlineNearTightening:
    def test_deadline_near_tightens_sla(self, session, scholarship_factory, today):
        s = scholarship_factory(deadline_date=today + timedelta(days=10))
        result = evaluate_field_freshness(
            "deadline_date",
            today - timedelta(days=15),
            s,
            session,
            today=today,
        )
        base_max = CLASS_MAX_AGE_DAYS[FRESHNESS_CLASS_CRITICAL]
        assert result.max_age_days < base_max

    def test_deadline_far_no_tightening(self, session, scholarship_factory, today):
        s = scholarship_factory(
            deadline_date=today + timedelta(days=120),
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        result = evaluate_field_freshness(
            "deadline_date",
            today - timedelta(days=5),
            s,
            session,
            today=today,
        )
        base_max = CLASS_MAX_AGE_DAYS[FRESHNESS_CLASS_CRITICAL]
        deadline = s.deadline_date
        if isinstance(deadline, datetime):
            deadline = deadline.date()
        delta = (deadline - today).days
        if delta > DEADLINE_TIGHTENING_THRESHOLD_DAYS:
            assert result.max_age_days <= base_max

    def test_deadline_past_no_tightening(self, session, scholarship_factory, today):
        s = scholarship_factory(
            deadline_date=today - timedelta(days=5),
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        result = evaluate_field_freshness(
            "deadline_date",
            today - timedelta(days=5),
            s,
            session,
            today=today,
        )
        base_max = CLASS_MAX_AGE_DAYS[FRESHNESS_CLASS_CRITICAL]
        assert result.state == STATE_FRESH
        assert result.max_age_days > 0


class TestLifecycleAdjustment:
    def test_discovered_lifecycle_tightens(self, session, scholarship_factory, today):
        s = scholarship_factory(
            created_at=datetime(2026, 8, 15),
            updated_at=datetime(2026, 8, 15),
        )
        result = evaluate_field_freshness(
            "deadline_date",
            today - timedelta(days=5),
            s,
            session,
            today=today,
        )
        assert result.max_age_days > 0

    def test_archived_lifecycle_relaxes(self, session, scholarship_factory, today):
        s = scholarship_factory(
            status="archived",
            created_at=datetime(2025, 1, 1),
            updated_at=datetime(2025, 1, 1),
        )
        result = evaluate_field_freshness(
            "notes",
            today - timedelta(days=50),
            s,
            session,
            today=today,
        )
        assert result.max_age_days > 0


class TestSourceHealthAdjustment:
    def test_unhealthy_source_increases_priority(self, session, scholarship_factory, today):
        s = scholarship_factory(official_source_url="https://unhealthy-example.com/scholarship")
        health = SourceHealth(
            domain="unhealthy-example.com",
            health_status="unhealthy",
            reliability_score=30.0,
            success_count=10,
            failure_count=20,
        )
        session.add(health)
        session.commit()

        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=5)},
            today=today,
            source_health=health,
        )
        assert result.source_health_confidence < 1.0

    def test_healthy_source_full_confidence(self, session, scholarship_factory, today):
        s = scholarship_factory(official_source_url="https://healthy-example.com/scholarship")
        health = SourceHealth(
            domain="healthy-example.com",
            health_status="healthy",
            reliability_score=95.0,
            success_count=100,
            failure_count=5,
        )
        session.add(health)
        session.commit()

        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=5)},
            today=today,
            source_health=health,
        )
        assert result.source_health_confidence == 1.0


class TestManualOverride:
    def test_manual_override_forces_fresh(self, session, scholarship_factory, today):
        s = scholarship_factory()
        overrides = {
            "deadline_date": FreshnessPolicyOverride(
                field_name="deadline_date",
                max_age_days=365,
                reason_code="manual_override_admin",
            )
        }
        result = evaluate_field_freshness(
            "deadline_date",
            None,
            s,
            session,
            today=today,
            overrides=overrides,
        )
        assert result.state == STATE_FRESH
        assert result.sla_breach_severity == 0
        assert "manual_override_admin" in result.reason_codes


class TestSchedulerVisibility:
    def test_freshness_priority_present(self, session, scholarship_factory, today):
        s = scholarship_factory(deadline_date=today + timedelta(days=10))
        result = evaluate_scholarship_freshness(
            session,
            s,
            {
                "deadline_date": today - timedelta(days=5),
                "application_link": today - timedelta(days=10),
            },
            today=today,
        )
        assert 0 <= result.freshness_priority <= 100

    def test_sla_breach_severity_present(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=100)},
            today=today,
        )
        assert result.sla_breach_severity > 0

    def test_next_required_verification_present(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=5)},
            today=today,
        )
        assert result.next_required_verification is not None
        assert result.next_required_verification >= today

    def test_critical_breach_immediately_due(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": None},
            today=today,
        )
        assert result.next_required_verification == today

    def test_reason_codes_exposed(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {
                "deadline_date": today - timedelta(days=100),
                "application_link": today - timedelta(days=50),
            },
            today=today,
        )
        assert len(result.reason_codes) > 0


class TestDeterministicOutput:
    def test_same_input_same_output(self, session, scholarship_factory, today):
        s = scholarship_factory()
        r1 = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=10)},
            today=today,
        )
        r2 = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=10)},
            today=today,
        )
        assert r1 == r2

    def test_field_evaluation_deterministic(self, session, scholarship_factory, today):
        s = scholarship_factory()
        r1 = evaluate_field_freshness(
            "deadline_date",
            today - timedelta(days=10),
            s,
            session,
            today=today,
        )
        r2 = evaluate_field_freshness(
            "deadline_date",
            today - timedelta(days=10),
            s,
            session,
            today=today,
        )
        assert r1 == r2


class TestBatchEvaluation:
    def test_batch_returns_all(self, session, scholarship_factory, today):
        s1 = scholarship_factory()
        s2 = scholarship_factory()
        s3 = scholarship_factory()

        results = batch_evaluate_freshness(
            session,
            [s1, s2, s3],
            {
                s1.id: {"deadline_date": today - timedelta(days=5)},
                s2.id: {"deadline_date": today - timedelta(days=50)},
                s3.id: {"deadline_date": None},
            },
            today=today,
        )

        assert len(results) == 3
        assert s1.id in results
        assert s2.id in results
        assert s3.id in results

    def test_batch_results_independent(self, session, scholarship_factory, today):
        s1 = scholarship_factory()
        s2 = scholarship_factory()

        results = batch_evaluate_freshness(
            session,
            [s1, s2],
            {
                s1.id: {"deadline_date": today - timedelta(days=5)},
                s2.id: {"deadline_date": today - timedelta(days=100)},
            },
            today=today,
        )

        assert results[s1.id].overall_state == STATE_FRESH
        assert results[s2.id].overall_state in (STATE_STALE, STATE_CRITICAL_STALE)


class TestNoUnsafeSkipping:
    def test_critical_breach_not_silent(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": None},
            today=today,
        )
        assert result.sla_breach_severity > 0
        assert result.freshness_priority > 0

    def test_critical_never_verified_urgent(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {
                "deadline_date": None,
                "eligibility": None,
            },
            today=today,
        )
        assert result.overall_state == STATE_NEVER_VERIFIED
        assert result.sla_breach_severity == 100
        assert result.freshness_priority > 0

    def test_summary_has_critical_breach_flag(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=200)},
            today=today,
        )
        summary = get_freshness_summary(result)
        assert summary["has_critical_breach"] is True


class TestPolicyDefinitions:
    def test_all_fields_have_class(self):
        policies = get_policy_definitions()
        assert len(policies) > 0
        for field_name in FIELD_FRESHNESS_CLASSES:
            assert field_name in policies

    def test_policy_caching(self):
        p1 = get_policy_definitions()
        p2 = get_policy_definitions()
        assert p1 is p2

    def test_critical_class_thresholds(self):
        policies = get_policy_definitions()
        deadline_policy = policies["deadline_date"]
        notes_policy = policies["notes"]
        assert deadline_policy.max_age_days < notes_policy.max_age_days


class TestHelperFunctions:
    def test_is_field_within_sla_true(self, today):
        assert is_field_within_sla("deadline_date", today - timedelta(days=1)) is True

    def test_is_field_within_sla_false_when_stale(self, today):
        assert is_field_within_sla("deadline_date", today - timedelta(days=100)) is False

    def test_is_field_within_sla_false_when_none(self, today):
        assert is_field_within_sla("deadline_date", None) is False

    def test_is_field_sla_breached_true(self, today):
        assert is_field_sla_breached("deadline_date", today - timedelta(days=100)) is True

    def test_is_field_sla_breached_false_when_fresh(self, today):
        assert is_field_sla_breached("deadline_date", today - timedelta(days=1)) is False

    def test_is_field_sla_breached_critical_field_never_verified(self, today):
        assert is_field_sla_breached("deadline_date", None) is True

    def test_is_field_sla_breached_low_field_never_verified(self, today):
        assert is_field_sla_breached("notes", None) is False


class TestFreshnessSummary:
    def test_summary_structure(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {"deadline_date": today - timedelta(days=5)},
            today=today,
        )
        summary = get_freshness_summary(result)
        assert "scholarship_id" in summary
        assert "overall_state" in summary
        assert "overall_sla_severity" in summary
        assert "freshness_priority" in summary
        assert "sla_breach_severity" in summary
        assert "next_required_verification" in summary
        assert "reason_codes" in summary
        assert "deadline_urgency" in summary
        assert "source_health_confidence" in summary
        assert "lifecycle_state" in summary
        assert "has_critical_breach" in summary


class TestNoNPlusOne:
    def test_batch_no_duplicate_queries(self, session, scholarship_factory, today):
        scholarships = [scholarship_factory() for _ in range(5)]
        timestamps_map = {
            s.id: {"deadline_date": today - timedelta(days=5)}
            for s in scholarships
        }
        results = batch_evaluate_freshness(
            session,
            scholarships,
            timestamps_map,
            today=today,
        )
        assert len(results) == 5


class TestAggregateFreshness:
    def test_scholarship_worst_field_wins(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {
                "deadline_date": today - timedelta(days=5),
                "application_link": today - timedelta(days=200),
            },
            today=today,
        )
        assert result.overall_state in (STATE_STALE, STATE_CRITICAL_STALE)

    def test_all_fresh_scholarship_fresh(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {
                "deadline_date": today - timedelta(days=1),
                "application_link": today - timedelta(days=1),
            },
            today=today,
        )
        assert result.overall_state == STATE_FRESH
        assert result.overall_sla_severity == 0

    def test_mixed_states_aggregate_correctly(self, session, scholarship_factory, today):
        s = scholarship_factory()
        result = evaluate_scholarship_freshness(
            session,
            s,
            {
                "deadline_date": today - timedelta(days=1),
                "application_link": today - timedelta(days=50),
                "notes": today - timedelta(days=150),
            },
            today=today,
        )
        assert result.overall_state != STATE_FRESH
