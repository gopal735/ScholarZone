"""Tests for explainable verification intelligence."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, SourceHealth as SourceHealthModel
from app.services.verification_intelligence import (
    AUTO_UPDATE,
    NO_CHANGE,
    REJECTED,
    REVIEW_REQUIRED,
    ChangeSummary,
    FieldExplanation,
    ReasonCode,
    SourceAuthority,
    VerificationExplanation,
    VerificationInput,
    _coerce_value,
    _values_equal,
    _explain_field,
    _decide_decision,
    _compute_confidence,
    _summarize_changes,
    batch_explain,
    explain_verification,
    get_explanation_summary,
    is_auto_approved,
    is_no_change,
    is_rejected,
    is_review_required,
    quick_explain,
)
from app.services.lifecycle_identity import (
    ARCHIVED,
    CLOSED,
    LifecycleState,
    LifecycleTransition,
    classify_lifecycle_state,
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
        defaults = {
            "title": "Test Scholarship",
            "country": "Germany",
            "degree": "Masters",
            "funding": "Full",
            "official_source_url": f"https://example.com/scholarship-{_url_counter}",
            "official_source": "Test Provider",
        }
        defaults.update(kwargs)
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s
    return _make


@pytest.fixture
def source_health_factory(session):
    def _make(**kwargs):
        defaults = {
            "domain": "example.com",
            "success_count": 10,
            "failure_count": 1,
            "health_status": "healthy",
            "reliability_score": 90.0,
        }
        defaults.update(kwargs)
        sh = SourceHealthModel(**defaults)
        session.add(sh)
        session.commit()
        return sh
    return _make


class TestValueCoercion:
    def test_none_returns_none(self):
        assert _coerce_value(None) is None

    def test_string_returns_string(self):
        assert _coerce_value("hello") == "hello"

    def test_list_returns_json(self):
        result = _coerce_value(["a", "b"])
        assert '"a"' in result

    def test_dict_returns_json(self):
        result = _coerce_value({"key": "value"})
        assert '"key"' in result

    def test_int_returns_string(self):
        assert _coerce_value(42) == "42"


class TestValuesEqual:
    def test_both_none(self):
        assert _values_equal(None, None) is True

    def test_one_none(self):
        assert _values_equal("value", None) is False

    def test_same_values(self):
        assert _values_equal("value", "value") is True

    def test_different_values(self):
        assert _values_equal("old", "new") is False

    def test_list_equal(self):
        assert _values_equal(["a", "b"], ["a", "b"]) is True


class TestNoChangeDetection:
    def test_no_changes_returns_no_change(self, session, scholarship_factory):
        scholarship = scholarship_factory()
        today = date.today()

        fields = {
            "title": (scholarship.title, scholarship.title),
            "country": (scholarship.country, scholarship.country),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == NO_CHANGE

    def test_no_change_has_no_field_changes(self, session, scholarship_factory):
        scholarship = scholarship_factory()
        today = date.today()

        fields = {
            "title": ("Same Title", "Same Title"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.change_summary.total_fields_changed == 0

    def test_no_change_confidence_is_one(self, session, scholarship_factory):
        scholarship = scholarship_factory()
        today = date.today()

        fields = {
            "title": ("Same", "Same"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.confidence == 1.0


class TestAutoUpdateDecision:
    def test_low_criticality_change_auto_approved(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old description", "New description"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == AUTO_UPDATE

    def test_new_field_populated_auto_approved(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "best_fit": (None, "Great fit for engineers"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == AUTO_UPDATE

    def test_auto_update_has_confidence(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "notes": (None, "Some note"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.confidence > 0.5


class TestReviewRequiredDecision:
    def test_critical_field_change_requires_review(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "deadline_date": (date(2026, 6, 1), date(2026, 12, 1)),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REVIEW_REQUIRED

    def test_many_fields_changed_requires_review(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
            "notes": ("Old note", "New note"),
            "best_fit": ("Old fit", "New fit"),
            "program_type": ("Old type", "New type"),
            "selection_notes": ("Old selection", "New selection"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REVIEW_REQUIRED

    def test_degraded_source_requires_review(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="degraded")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REVIEW_REQUIRED

    def test_field_cleared_requires_review(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old description", None),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REVIEW_REQUIRED


class TestRejectedDecision:
    def test_archived_lifecycle_rejected(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory(status="archived")
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REJECTED

    def test_closed_lifecycle_rejected(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory(status="closed")
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REJECTED

    def test_blocked_source_rejected(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(
            domain="example.com",
            health_status="unhealthy",
            manual_override="unhealthy",
        )
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REJECTED


class TestFieldExplanation:
    def test_field_explanation_has_required_fields(self):
        today = date.today()
        fe = _explain_field("title", "Old", "New", None, today)

        assert fe.field_name == "title"
        assert fe.old_value == "Old"
        assert fe.new_value == "New"
        assert fe.impact_level is not None
        assert fe.impact_score > 0

    def test_unchanged_field_has_zero_impact(self):
        today = date.today()
        fe = _explain_field("title", "Same", "Same", None, today)

        assert fe.impact_score == 0

    def test_new_field_populated(self):
        today = date.today()
        fe = _explain_field("best_fit", None, "Great fit", None, today)

        assert fe.old_value is None
        assert fe.new_value == "Great fit"
        assert fe.impact_score > 0

    def test_field_cleared(self):
        today = date.today()
        fe = _explain_field("description", "Old desc", None, None, today)

        assert fe.old_value == "Old desc"
        assert fe.new_value is None
        assert fe.impact_score > 0


class TestChangeSummary:
    def test_no_changes_summary(self):
        today = date.today()
        explanations = [
            _explain_field("title", "Same", "Same", None, today),
        ]
        summary = _summarize_changes(explanations)

        assert summary.total_fields_changed == 0
        assert summary.max_impact_level == "none"

    def test_mixed_changes_summary(self):
        today = date.today()
        explanations = [
            _explain_field("title", "Old", "New", None, today),
            _explain_field("description", "Old", "New", None, today),
        ]
        summary = _summarize_changes(explanations)

        assert summary.total_fields_changed == 2

    def test_critical_change_summary(self):
        today = date.today()
        explanations = [
            _explain_field("deadline_date", "2026-01-01", "2026-06-01", None, today),
        ]
        summary = _summarize_changes(explanations)

        assert summary.critical_fields_changed == 1
        assert summary.max_impact_level == "critical"


class TestDecisionLogic:
    def test_no_changes_returns_no_change(self):
        today = date.today()
        explanations = [
            _explain_field("title", "Same", "Same", None, today),
        ]
        source_auth = SourceAuthority(
            domain="example.com",
            health_status="healthy",
            reliability_score=90.0,
            confidence_factor=1.0,
            is_trusted=True,
            is_blocked=False,
            explanation="test",
        )
        lifecycle = LifecycleState(
            state="active",
            previous_state=None,
            scholarship_id=1,
            reason="test",
            deadline_urgency=0,
            is_terminal=False,
        )
        summary = _summarize_changes(explanations)
        decision, reason, _, _ = _decide_decision(explanations, source_auth, lifecycle, summary)

        assert decision == NO_CHANGE

    def test_blocked_source_rejected(self):
        today = date.today()
        explanations = [
            _explain_field("title", "Old", "New", None, today),
        ]
        source_auth = SourceAuthority(
            domain="example.com",
            health_status="unhealthy",
            reliability_score=0.0,
            confidence_factor=0.4,
            is_trusted=False,
            is_blocked=True,
            explanation="blocked",
        )
        lifecycle = LifecycleState(
            state="active",
            previous_state=None,
            scholarship_id=1,
            reason="test",
            deadline_urgency=0,
            is_terminal=False,
        )
        summary = _summarize_changes(explanations)
        decision, reason, _, _ = _decide_decision(explanations, source_auth, lifecycle, summary)

        assert decision == REJECTED

    def test_archived_lifecycle_rejected(self):
        today = date.today()
        explanations = [
            _explain_field("title", "Old", "New", None, today),
        ]
        source_auth = SourceAuthority(
            domain="example.com",
            health_status="healthy",
            reliability_score=90.0,
            confidence_factor=1.0,
            is_trusted=True,
            is_blocked=False,
            explanation="test",
        )
        lifecycle = LifecycleState(
            state=ARCHIVED,
            previous_state=None,
            scholarship_id=1,
            reason="archived",
            deadline_urgency=0,
            is_terminal=True,
        )
        summary = _summarize_changes(explanations)
        decision, reason, _, _ = _decide_decision(explanations, source_auth, lifecycle, summary)

        assert decision == REJECTED


class TestConfidenceComputation:
    def test_no_change_confidence_is_one(self):
        source_auth = SourceAuthority(
            domain="example.com",
            health_status="healthy",
            reliability_score=90.0,
            confidence_factor=1.0,
            is_trusted=True,
            is_blocked=False,
            explanation="test",
        )
        summary = ChangeSummary(
            total_fields_changed=0,
            critical_fields_changed=0,
            high_fields_changed=0,
            fields_cleared=0,
            fields_populated=0,
            max_impact_level="none",
            overall_impact_score=0,
        )
        confidence = _compute_confidence(source_auth, summary, NO_CHANGE)
        assert confidence == 1.0

    def test_rejected_confidence_boosted(self):
        source_auth = SourceAuthority(
            domain="example.com",
            health_status="unhealthy",
            reliability_score=0.0,
            confidence_factor=0.4,
            is_trusted=False,
            is_blocked=True,
            explanation="blocked",
        )
        summary = ChangeSummary(
            total_fields_changed=1,
            critical_fields_changed=0,
            high_fields_changed=0,
            fields_cleared=0,
            fields_populated=0,
            max_impact_level="low",
            overall_impact_score=10,
        )
        confidence = _compute_confidence(source_auth, summary, REJECTED)
        assert confidence > 0.4

    def test_critical_field_reduces_confidence(self):
        source_auth = SourceAuthority(
            domain="example.com",
            health_status="healthy",
            reliability_score=90.0,
            confidence_factor=1.0,
            is_trusted=True,
            is_blocked=False,
            explanation="test",
        )
        summary = ChangeSummary(
            total_fields_changed=1,
            critical_fields_changed=1,
            high_fields_changed=0,
            fields_cleared=0,
            fields_populated=0,
            max_impact_level="critical",
            overall_impact_score=100,
        )
        confidence = _compute_confidence(source_auth, summary, REVIEW_REQUIRED)
        assert confidence < 1.0


class TestSourceAuthority:
    def test_no_source_url(self, session, scholarship_factory):
        from app.services.verification_intelligence import _compute_source_authority

        scholarship = scholarship_factory()
        result = _compute_source_authority(session, scholarship, None, None)

        assert result.domain == ""
        assert result.is_trusted is False

    def test_unknown_domain(self, session, scholarship_factory):
        from app.services.verification_intelligence import _compute_source_authority

        scholarship = scholarship_factory()
        result = _compute_source_authority(session, scholarship, "https://unknown.com/page", None)

        assert result.domain == "unknown.com"
        assert result.health_status == "unknown"
        assert result.is_trusted is True

    def test_healthy_source(self, session, scholarship_factory, source_health_factory):
        from app.services.verification_intelligence import _compute_source_authority

        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy", reliability_score=95.0)
        result = _compute_source_authority(session, scholarship, "https://example.com/page", None)

        assert result.health_status == "healthy"
        assert result.is_trusted is True
        assert result.confidence_factor == 1.0

    def test_blocked_source(self, session, scholarship_factory, source_health_factory):
        from app.services.verification_intelligence import _compute_source_authority

        scholarship = scholarship_factory()
        source_health_factory(
            domain="example.com",
            health_status="unhealthy",
            manual_override="unhealthy",
        )
        result = _compute_source_authority(session, scholarship, "https://example.com/page", None)

        assert result.is_blocked is True
        assert result.is_trusted is False


class TestDeterministicOutput:
    def test_same_input_same_output(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result1 = quick_explain(session, scholarship, fields, today=today)
        result2 = quick_explain(session, scholarship, fields, today=today)

        assert result1.decision == result2.decision
        assert result1.confidence == result2.confidence
        assert result1.explanation_text == result2.explanation_text

    def test_deterministic_across_calls(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "notes": ("Old note", "New note"),
        }

        results = [quick_explain(session, scholarship, fields, today=today) for _ in range(5)]
        decisions = [r.decision for r in results]

        assert all(d == decisions[0] for d in decisions)


class TestSafetyGates:
    def test_critical_field_never_auto_approved(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy", reliability_score=100.0)
        today = date.today()

        fields = {
            "deadline_date": (date(2026, 1, 1), date(2026, 12, 31)),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision != AUTO_UPDATE

    def test_archived_never_auto_updated(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory(status="archived")
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REJECTED

    def test_blocked_source_never_auto_approved(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(
            domain="example.com",
            health_status="unhealthy",
            manual_override="unhealthy",
        )
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)
        assert result.decision == REJECTED


class TestExplanationStructure:
    def test_explanation_has_all_fields(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)

        assert result.scholarship_id == scholarship.id
        assert result.decision in {AUTO_UPDATE, REVIEW_REQUIRED, REJECTED, NO_CHANGE}
        assert result.primary_reason_code is not None
        assert result.summary is not None
        assert result.explanation_text is not None
        assert result.generated_at is not None

    def test_field_explanations_populated(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
            "notes": ("Old note", "New note"),
        }

        result = quick_explain(session, scholarship, fields, today=today)

        assert len(result.field_explanations) == 2

    def test_change_summary_populated(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)

        assert result.change_summary.total_fields_changed >= 0
        assert result.change_summary.max_impact_level is not None


class TestHelperFunctions:
    def test_is_auto_approved(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        if result.decision == AUTO_UPDATE:
            assert is_auto_approved(result) is True

    def test_is_review_required(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"deadline_date": (date(2026, 1, 1), date(2026, 12, 31))}
        result = quick_explain(session, scholarship, fields, today=today)

        if result.decision == REVIEW_REQUIRED:
            assert is_review_required(result) is True

    def test_is_rejected(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory(status="archived")
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        assert is_rejected(result) is True

    def test_is_no_change(self, session, scholarship_factory):
        scholarship = scholarship_factory()
        today = date.today()

        fields = {"title": ("Same", "Same")}
        result = quick_explain(session, scholarship, fields, today=today)

        assert is_no_change(result) is True

    def test_get_explanation_summary(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        summary = get_explanation_summary(result)

        assert "scholarship_id" in summary
        assert "decision" in summary
        assert "confidence" in summary
        assert "explanation_text" in summary


class TestBatchOperations:
    def test_batch_explain(self, session, scholarship_factory, source_health_factory):
        scholarship1 = scholarship_factory()
        scholarship2 = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        lifecycle1 = classify_lifecycle_state(session, scholarship1, today)
        lifecycle2 = classify_lifecycle_state(session, scholarship2, today)

        inputs = [
            VerificationInput(
                scholarship=scholarship1,
                candidate_fields={"description": ("Old", "New")},
                source_url="https://example.com/s1",
                source_health=None,
                lifecycle_state=lifecycle1,
                today=today,
            ),
            VerificationInput(
                scholarship=scholarship2,
                candidate_fields={"notes": ("Old", "New")},
                source_url="https://example.com/s2",
                source_health=None,
                lifecycle_state=lifecycle2,
                today=today,
            ),
        ]

        results = batch_explain(session, inputs)

        assert len(results) == 2
        assert results[0].scholarship_id == scholarship1.id
        assert results[1].scholarship_id == scholarship2.id


class TestLifecycleIntegration:
    def test_lifecycle_state_in_explanation(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        assert result.lifecycle_state is not None
        assert result.lifecycle_reason is not None

    def test_deadline_near_lifecycle(self, session, scholarship_factory, source_health_factory):
        near_deadline = date.today() + timedelta(days=15)
        scholarship = scholarship_factory(deadline_date=near_deadline, status="open")
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        assert result.lifecycle_state == "deadline_near"


class TestEvidenceQuality:
    def test_evidence_in_field_explanation(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        for fe in result.field_explanations:
            assert fe.explanation is not None
            assert len(fe.explanation) > 0

    def test_confidence_reflects_source_health(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="degraded", reliability_score=50.0)
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        assert result.source_authority.health_status == "degraded"


class TestConflictExplanation:
    def test_multiple_changes_flagged(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {
            "description": ("Old", "New"),
            "notes": ("Old", "New"),
            "best_fit": ("Old", "New"),
            "program_type": ("Old", "New"),
            "selection_notes": ("Old", "New"),
        }

        result = quick_explain(session, scholarship, fields, today=today)

        assert result.change_summary.total_fields_changed == 5
        assert result.decision == REVIEW_REQUIRED


class TestStalenessExplanation:
    def test_staleness_in_field_explanation(self):
        today = date.today()
        old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)

        fe = _explain_field("deadline_date", "2020-01-01", "2026-01-01", old_date, today)

        assert fe.staleness_state is not None
        assert fe.freshness_threshold_days > 0
        assert fe.age_days is not None
        assert fe.age_days > 0


class TestImpactExplanation:
    def test_impact_level_in_field_explanation(self):
        today = date.today()

        fe_critical = _explain_field("deadline_date", "2026-01-01", "2026-12-01", None, today)
        fe_low = _explain_field("description", "Old", "New", None, today)

        assert fe_critical.impact_level == "critical"
        assert fe_low.impact_level == "low"
        assert fe_critical.impact_score > fe_low.impact_score


class TestSchedulerCompatibility:
    def test_explanation_has_scholarship_id(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        assert result.scholarship_id == scholarship.id

    def test_decision_is_machine_readable(self, session, scholarship_factory, source_health_factory):
        scholarship = scholarship_factory()
        source_health_factory(domain="example.com", health_status="healthy")
        today = date.today()

        fields = {"description": ("Old", "New")}
        result = quick_explain(session, scholarship, fields, today=today)

        assert result.decision in DECISION_TYPES_SET


DECISION_TYPES_SET = {AUTO_UPDATE, REVIEW_REQUIRED, REJECTED, NO_CHANGE}
