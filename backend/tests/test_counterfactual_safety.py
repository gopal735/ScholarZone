"""Comprehensive tests for the counterfactual safety and pre-commit consistency engine."""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-counterfactual-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"


fake_scheduler = types.ModuleType("app.scheduler")
fake_scheduler.start_scheduler = lambda: None
fake_scheduler.mark_due_for_review = lambda: None
sys.modules["app.scheduler"] = fake_scheduler


from app.database import close_database, get_session_factory, init_database, reset_database_connections  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.counterfactual_safety import (  # noqa: E402
    CounterfactualResult,
    CounterfactualSeverity,
    LifecycleImpact,
    batch_simulate_counterfactual,
    simulate_counterfactual,
    validate_proposed_state,
)


def _make_scholarship(
    session,
    title: str = "Test Scholarship",
    country: str = "Test Country",
    degree: str = "Master",
    funding: str = "Full",
    duration: str = "2 years",
    status: str = "open",
    deadline_date: date | None = None,
    deadline_display: str = "October 15, 2026",
    eligibility: list[str] | None = None,
    application_method: list[str] | None = None,
    application_link: str | None = "https://example.com/apply",
    coverage: list[str] | None = None,
    requirements: list[str] | None = None,
    is_verified: bool = True,
    last_verified_at: date | None = None,
    verification_status: str = "active",
    source_url: str | None = None,
) -> Scholarship:
    if deadline_date is None:
        deadline_date = date.today() + timedelta(days=60)
    if eligibility is None:
        eligibility = ["Must be enrolled"]
    if application_method is None:
        application_method = ["Online"]
    if coverage is None:
        coverage = ["Tuition", "Living expenses"]
    if requirements is None:
        requirements = ["Bachelor degree", "English proficiency"]
    if last_verified_at is None:
        last_verified_at = date.today() - timedelta(days=7)

    # Generate unique source URL to avoid UNIQUE constraint violations
    if source_url is None:
        unique_id = uuid4().hex[:8]
        source_url = f"https://example-{unique_id}.com/scholarship"

    scholarship = Scholarship(
        title=title,
        country=country,
        degree=degree,
        funding=funding,
        duration=duration,
        status=status,
        deadline_date=deadline_date,
        deadline_display=deadline_display,
        eligibility=eligibility,
        application_method=application_method,
        application_link=application_link,
        coverage=coverage,
        requirements=requirements,
        is_verified=is_verified,
        last_verified_at=last_verified_at,
        verification_status=verification_status,
        official_source_url=source_url,
    )
    session.add(scholarship)
    session.commit()
    return scholarship


def _get_scholarship(session, scholarship_id: int) -> Scholarship:
    return session.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id)
    ).scalar_one()


def _extract_state(scholarship: Scholarship) -> dict:
    return {
        "title": scholarship.title,
        "country": scholarship.country,
        "degree": scholarship.degree,
        "funding": scholarship.funding,
        "description": scholarship.description,
        "deadline_date": scholarship.deadline_date,
        "deadline_display": scholarship.deadline_display,
        "deadline_precision": scholarship.deadline_precision,
        "status": scholarship.status,
        "is_verified": scholarship.is_verified,
        "last_verified_at": scholarship.last_verified_at,
        "last_verified_date": scholarship.last_verified_date,
        "verification_status": scholarship.verification_status,
        "next_verification_due": scholarship.next_verification_due,
        "verified_by": scholarship.verified_by,
        "verification_notes": scholarship.verification_notes,
        "region": scholarship.region,
        "duration": scholarship.duration,
        "application_period": scholarship.application_period,
        "official_source": scholarship.official_source,
        "official_source_url": scholarship.official_source_url,
        "catalogue_url": scholarship.catalogue_url,
        "official_updates_url": scholarship.official_updates_url,
        "application_link": scholarship.application_link,
        "eligibility": scholarship.eligibility,
        "eligibility_summary": scholarship.eligibility_summary,
        "benefits": scholarship.benefits,
        "coverage": scholarship.coverage,
        "requirements": scholarship.requirements,
        "documents": scholarship.documents,
        "english_requirement": scholarship.english_requirement,
        "application_method": scholarship.application_method,
        "selection_notes": scholarship.selection_notes,
        "program_type": scholarship.program_type,
        "best_fit": scholarship.best_fit,
        "notes": scholarship.notes,
    }


class TestCounterfactualSafetyBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_database_connections()
        init_database()

    @classmethod
    def tearDownClass(cls):
        close_database()
        reset_database_connections()
        if TEST_DATABASE_PATH.exists():
            TEST_DATABASE_PATH.unlink(missing_ok=True)

    def setUp(self):
        """Clean database before each test."""
        with get_session_factory()() as session:
            scholarships = session.execute(select(Scholarship)).scalars().all()
            for s in scholarships:
                session.delete(s)
            session.commit()

    def tearDown(self):
        """Clean database after each test."""
        with get_session_factory()() as session:
            scholarships = session.execute(select(Scholarship)).scalars().all()
            for s in scholarships:
                session.delete(s)
            session.commit()


class TestSafeDeadlineChange(TestCounterfactualSafetyBase):
    def test_safe_deadline_extension(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() + timedelta(days=90)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.safe)
            self.assertEqual(result.severity, CounterfactualSeverity.SAFE)
            self.assertEqual(len(result.violated_rules), 0)

    def test_safe_deadline_with_status_change(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)

            proposed = {
                "deadline_date": date.today() + timedelta(days=90),
                "status": "active",
            }
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.safe)
            self.assertEqual(result.severity, CounterfactualSeverity.SAFE)


class TestDeadlineStatusInconsistency(TestCounterfactualSafetyBase):
    def test_deadline_passed_but_status_active(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
                status="open",
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() - timedelta(days=10)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("deadline_passed_but_status_active", result.reason_codes)

    def test_deadline_future_but_status_closed(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() - timedelta(days=10),
                status="closed",
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() + timedelta(days=60)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("deadline_future_but_status_closed", result.reason_codes)


class TestDeadlineApplicationPeriodInconsistency(TestCounterfactualSafetyBase):
    def test_seasonal_mismatch(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)

            # Set deadline to December but application_period says "Spring"
            proposed = {
                "deadline_date": date(2026, 12, 15),
                "application_period": "Spring 2027",
            }
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("deadline_application_period_season_mismatch", result.reason_codes)


class TestFundingCoverageInconsistency(TestCounterfactualSafetyBase):
    def test_full_funding_empty_coverage(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                funding="Full",
                coverage=["Tuition"],
            )
            current_state = _extract_state(scholarship)

            proposed = {"coverage": []}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("full_funding_empty_coverage", result.reason_codes)

    def test_no_funding_has_coverage(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                funding="None",
                coverage=[],
            )
            current_state = _extract_state(scholarship)

            proposed = {"coverage": ["Tuition", "Living expenses"]}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("no_funding_has_coverage", result.reason_codes)


class TestEligibilityRequirementsInconsistency(TestCounterfactualSafetyBase):
    def test_phd_with_bachelor_only_requirements(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                degree="PhD",
                requirements=["Master degree"],
            )
            current_state = _extract_state(scholarship)

            proposed = {"requirements": ["Bachelor degree"]}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("eligibility_degree_requirements_mismatch", result.reason_codes)


class TestApplicationMethodLinkInconsistency(TestCounterfactualSafetyBase):
    def test_online_method_missing_link(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                application_method=["Online"],
                application_link="https://example.com/apply",
            )
            current_state = _extract_state(scholarship)

            proposed = {"application_link": None}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("online_method_missing_link", result.reason_codes)


class TestLifecycleContradiction(TestCounterfactualSafetyBase):
    def test_archived_with_future_deadline(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() - timedelta(days=400),
                status="archived",
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() + timedelta(days=60)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("archived_with_future_deadline", result.reason_codes)

    def test_terminal_regression(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() - timedelta(days=10),
                status="closed",
            )
            current_state = _extract_state(scholarship)

            proposed = {"status": "active"}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertIn("invalid_lifecycle_regression", result.reason_codes)


class TestDependencyViolation(TestCounterfactualSafetyBase):
    def test_deadline_change_affects_application_period(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() + timedelta(days=90)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertIn("application_period", result.affected_dependencies)

    def test_eligibility_change_affects_requirements(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(session)
            current_state = _extract_state(scholarship)

            proposed = {"eligibility": ["New eligibility criteria"]}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertIn("requirements", result.affected_dependencies)


class TestNewlyIntroducedAnomaly(TestCounterfactualSafetyBase):
    def test_large_deadline_shift_detected(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=30),
            )
            current_state = _extract_state(scholarship)

            # Shift deadline by 100 days (critical threshold is 90)
            proposed = {"deadline_date": date.today() + timedelta(days=130)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            # Should detect anomaly
            self.assertTrue(len(result.anomaly_flags) > 0)

    def test_funding_reduction_detected(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                funding="Full",
            )
            current_state = _extract_state(scholarship)

            proposed = {"funding": "None"}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(len(result.anomaly_flags) > 0)


class TestMultipleSimultaneousChanges(TestCounterfactualSafetyBase):
    def test_multiple_changes_safe(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(session)
            current_state = _extract_state(scholarship)

            proposed = {
                "duration": "3 years",
                "description": "Updated description",
            }
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.safe)
            self.assertEqual(result.severity, CounterfactualSeverity.SAFE)

    def test_multiple_changes_with_inconsistency(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
                status="open",
            )
            current_state = _extract_state(scholarship)

            proposed = {
                "deadline_date": date.today() - timedelta(days=10),
                "status": "open",
            }
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)


class TestPartialProposal(TestCounterfactualSafetyBase):
    def test_single_field_change(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(session)
            current_state = _extract_state(scholarship)

            proposed = {"duration": "4 years"}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertIsInstance(result, CounterfactualResult)
            self.assertIn("duration", result.simulated_fields)
            self.assertEqual(result.simulated_fields["duration"], "4 years")

    def test_empty_proposal(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(session)
            current_state = _extract_state(scholarship)

            proposed = {}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.safe)
            self.assertEqual(result.severity, CounterfactualSeverity.SAFE)


class TestImmutableCurrentState(TestCounterfactualSafetyBase):
    def test_current_state_not_mutated(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)
            original_deadline = current_state["deadline_date"]

            proposed = {"deadline_date": date.today() + timedelta(days=90)}
            simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            # Verify current_state dict was not mutated
            self.assertEqual(current_state["deadline_date"], original_deadline)

    def test_scholarship_object_not_mutated(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
                duration="2 years",
            )
            original_deadline = scholarship.deadline_date
            original_duration = scholarship.duration

            proposed = {
                "deadline_date": date.today() + timedelta(days=90),
                "duration": "3 years",
            }
            simulate_counterfactual(
                session,
                scholarship,
                proposed,
            )

            # Verify scholarship ORM object was not mutated
            self.assertEqual(scholarship.deadline_date, original_deadline)
            self.assertEqual(scholarship.duration, original_duration)


class TestDeterministicResult(TestCounterfactualSafetyBase):
    def test_same_input_same_output(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() + timedelta(days=90)}

            result1 = simulate_counterfactual(
                session, scholarship, proposed, current_state
            )
            result2 = simulate_counterfactual(
                session, scholarship, proposed, current_state
            )

            self.assertEqual(result1.safe, result2.safe)
            self.assertEqual(result1.severity, result2.severity)
            self.assertEqual(result1.violated_rules, result2.violated_rules)
            self.assertEqual(result1.reason_codes, result2.reason_codes)


class TestNoNPlusOne(TestCounterfactualSafetyBase):
    def test_batch_does_not_query_per_scholarship(self):
        with get_session_factory()() as session:
            scholarships = []
            for i in range(5):
                s = _make_scholarship(
                    session,
                    title=f"Scholarship {i}",
                )
                scholarships.append(s)

            proposed_list = [
                {"duration": f"{i + 1} years"} for i in range(5)
            ]

            results = batch_simulate_counterfactual(
                session, scholarships, proposed_list
            )

            self.assertEqual(len(results), 5)
            for result in results:
                self.assertIsInstance(result, CounterfactualResult)


class TestNoDatabaseMutationDuringSimulation(TestCounterfactualSafetyBase):
    def test_database_unchanged_after_simulation(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
                duration="2 years",
            )
            scholarship_id = scholarship.id

            proposed = {
                "deadline_date": date.today() + timedelta(days=90),
                "duration": "3 years",
            }
            simulate_counterfactual(session, scholarship, proposed)

            session.expire_all()
            db_scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(db_scholarship.deadline_date, date.today() + timedelta(days=60))
            self.assertEqual(db_scholarship.duration, "2 years")


class TestSafeUpdateIntegration(TestCounterfactualSafetyBase):
    def test_safe_change_passes_all_checks(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)

            proposed = {
                "deadline_date": date.today() + timedelta(days=75),
                "duration": "3 years",
            }
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.safe)
            self.assertFalse(result.requires_review())
            self.assertFalse(result.should_block())

    def test_unsafe_change_requires_review(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
                status="open",
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() - timedelta(days=10)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertFalse(result.safe)
            self.assertTrue(result.requires_review())


class TestUnsafeUpdateBlocked(TestCounterfactualSafetyBase):
    def test_critical_inconsistency_blocks(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() - timedelta(days=400),
                status="archived",
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() + timedelta(days=60)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.should_block())
            self.assertEqual(result.severity, CounterfactualSeverity.CRITICAL)


class TestReviewEscalation(TestCounterfactualSafetyBase):
    def test_multiple_medium_issues_escalate_to_high(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                funding="Full",
                coverage=["Tuition"],
                application_method=["Online"],
                application_link="https://example.com/apply",
            )
            current_state = _extract_state(scholarship)

            # Create multiple issues
            proposed = {
                "coverage": [],
                "application_link": None,
            }
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.requires_review())
            self.assertIn(result.severity, (CounterfactualSeverity.HIGH, CounterfactualSeverity.MEDIUM))


class TestValidateProposedState(TestCounterfactualSafetyBase):
    def test_validate_returns_tuple(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(session)
            current_state = _extract_state(scholarship)

            proposed = {"duration": "3 years"}
            is_valid, result = validate_proposed_state(
                session, scholarship, proposed, current_state
            )

            self.assertIsInstance(is_valid, bool)
            self.assertIsInstance(result, CounterfactualResult)
            self.assertTrue(is_valid)


class TestLifecycleImpact(TestCounterfactualSafetyBase):
    def test_lifecycle_impact_populated(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
                status="open",
            )
            current_state = _extract_state(scholarship)

            proposed = {"status": "closed"}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertIsNotNone(result.lifecycle_impact)
            self.assertIsInstance(result.lifecycle_impact, LifecycleImpact)


class TestCounterfactualResultProperties(TestCounterfactualSafetyBase):
    def test_requires_review_thresholds(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
                status="open",
            )
            current_state = _extract_state(scholarship)

            proposed = {"deadline_date": date.today() - timedelta(days=10)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            if result.severity in (CounterfactualSeverity.HIGH, CounterfactualSeverity.CRITICAL):
                self.assertTrue(result.requires_review())

    def test_should_block_only_critical(self):
        result = CounterfactualResult(
            safe=False,
            severity=CounterfactualSeverity.HIGH,
        )
        self.assertFalse(result.should_block())

        result_critical = CounterfactualResult(
            safe=False,
            severity=CounterfactualSeverity.CRITICAL,
        )
        self.assertTrue(result_critical.should_block())


class TestEdgeCases(TestCounterfactualSafetyBase):
    def test_none_values_in_proposed(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(session)
            current_state = _extract_state(scholarship)

            proposed = {"description": None}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertIsInstance(result, CounterfactualResult)

    def test_proposed_same_as_current(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                duration="2 years",
            )
            current_state = _extract_state(scholarship)

            proposed = {"duration": "2 years"}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            self.assertTrue(result.safe)
            self.assertEqual(result.severity, CounterfactualSeverity.SAFE)

    def test_future_date_far_future(self):
        with get_session_factory()() as session:
            scholarship = _make_scholarship(
                session,
                deadline_date=date.today() + timedelta(days=60),
            )
            current_state = _extract_state(scholarship)

            # Deadline more than 3 years in future
            proposed = {"deadline_date": date.today() + timedelta(days=3 * 365 + 1)}
            result = simulate_counterfactual(
                session,
                scholarship,
                proposed,
                current_state,
            )

            # Should have anomaly flags for far future
            far_future_anomalies = [
                a for a in result.anomaly_flags
                if "deadline_far_future" in a.reason_codes
            ]
            self.assertTrue(len(far_future_anomalies) > 0)


if __name__ == "__main__":
    unittest.main()
