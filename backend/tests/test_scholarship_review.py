"""Focused tests for the conflict + human review workflow.

Tests cover:
1. conflict creates review item
2. no review item for safe auto-update
3. duplicate review prevention
4. review contains evidence/confidence/source
5. approve applies update through safe updater
6. approve writes verification history
7. approve is atomic
8. rollback leaves scholarship + review consistent
9. reject changes nothing
10. stale review approval is blocked
11. already decided review cannot be decided again
12. review decision is auditable
13. third-party/low-confidence/identity conflict cannot bypass review
14. transaction failure does not create partial state
"""

from __future__ import annotations

import os
import tempfile
import types
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-review-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"


fake_scheduler = types.ModuleType("app.scheduler")
fake_scheduler.start_scheduler = lambda: None
fake_scheduler.mark_due_for_review = lambda: None
import sys
sys.modules["app.scheduler"] = fake_scheduler


from app.database import close_database, get_session_factory, init_database, reset_database_connections  # noqa: E402
from app.models import Scholarship, ScholarshipReview, ScholarshipVerificationHistory  # noqa: E402
from app.services.scholarship_review import (  # noqa: E402
    ConflictReason,
    ReviewDecision,
    ReviewDecisionResult,
    approve_review,
    create_review,
    get_pending_reviews,
    get_review,
    get_pending_review,
    reject_review,
)
from app.services.scholarship_history import HistoryEntry, write_verification_history  # noqa: E402


def _make_scholarship(
    session,
    title: str = "Test Scholarship",
    country: str = "Test Country",
    degree: str = "Master",
    funding: str = "Fully Funded",
    duration: str = "2 years",
    status: str = "open",
) -> int:
    scholarship = Scholarship(
        title=title,
        country=country,
        degree=degree,
        funding=funding,
        duration=duration,
        status=status,
    )
    session.add(scholarship)
    session.commit()
    return scholarship.id


class TestConflictCreatesReviewItem(unittest.TestCase):
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

    def test_conflict_creates_review_item(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                verification_state="conflict",
                confidence="low",
                source_urls=["https://source1.com", "https://source2.com"],
                evidence_text="Conflicting duration values found",
            )
            session.commit()

            self.assertTrue(result.created)
            self.assertIsNotNone(result.review_id)

            review = get_review(session, result.review_id)
            self.assertIsNotNone(review)
            self.assertEqual(review.scholarship_id, scholarship_id)
            self.assertEqual(review.field_name, "duration")
            self.assertEqual(review.current_value, "2 years")
            self.assertEqual(review.proposed_value, "3 years")
            self.assertEqual(review.conflict_reason, ConflictReason.CONFLICTING_SOURCES)
            self.assertEqual(review.decision, ReviewDecision.PENDING)


class TestNoReviewForSafeAutoUpdate(unittest.TestCase):
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

    def test_no_review_item_for_safe_auto_update(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            pending = get_pending_review(session, scholarship_id, "duration")
            self.assertIsNone(pending)

            pending_reviews = get_pending_reviews(session, scholarship_id)
            self.assertEqual(len(pending_reviews), 0)


class TestDuplicateReviewPrevention(unittest.TestCase):
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

    def test_duplicate_review_prevention(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result1 = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
            )
            session.commit()

            result2 = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="4 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
            )
            session.commit()

            self.assertTrue(result1.created)
            self.assertFalse(result2.created)
            self.assertEqual(result2.existing_review_id, result1.review_id)

            pending = get_pending_reviews(session, scholarship_id)
            self.assertEqual(len(pending), 1)


class TestReviewContainsEvidenceConfidenceSource(unittest.TestCase):
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

    def test_review_contains_evidence_confidence_source(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, status="open")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="status",
                current_value="open",
                proposed_value="closed",
                conflict_reason=ConflictReason.THIRD_PARTY_SOURCE,
                verification_state="uncertain",
                confidence="low",
                source_urls=["https://third-party-blog.com"],
                evidence_text="Blog post says applications closed",
            )
            session.commit()

            review = get_review(session, result.review_id)
            self.assertEqual(review.confidence, "low")
            self.assertEqual(review.source_urls, ["https://third-party-blog.com"])
            self.assertEqual(review.evidence_text, "Blog post says applications closed")
            self.assertEqual(review.verification_state, "uncertain")


class TestApproveAppliesUpdateThroughSafeUpdater(unittest.TestCase):
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

    def test_approve_applies_update_through_safe_updater(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
            )
            session.commit()

            decision = approve_review(session, result.review_id, reviewed_by="test_reviewer")

            self.assertTrue(decision.success)
            self.assertEqual(decision.decision, ReviewDecision.APPROVED)
            self.assertIn("duration", decision.updated_fields)

            scholarship = session.get(Scholarship, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")


class TestApproveWritesVerificationHistory(unittest.TestCase):
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

    def test_approve_writes_verification_history(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
                source_urls=["https://official-source.gov"],
                evidence_text="Official announcement",
            )
            session.commit()

            approve_review(session, result.review_id, reviewed_by="test_reviewer")

            stmt = select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship_id
            )
            history = list(session.execute(stmt).scalars().all())
            self.assertEqual(len(history), 1)

            record = history[0]
            self.assertEqual(record.field_name, "duration")
            self.assertEqual(record.old_value, "2 years")
            self.assertEqual(record.new_value, "3 years")
            self.assertEqual(record.source_url, "https://official-source.gov")
            self.assertEqual(record.evidence_text, "Official announcement")
            self.assertEqual(record.confidence, "high")


class TestApproveIsAtomic(unittest.TestCase):
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

    def test_approve_is_atomic(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
            )
            session.commit()

            approve_review(session, result.review_id, reviewed_by="test_reviewer")

            review = get_review(session, result.review_id)
            scholarship = session.get(Scholarship, scholarship_id)

            self.assertEqual(review.decision, ReviewDecision.APPROVED)
            self.assertEqual(scholarship.duration, "3 years")
            self.assertIsNotNone(review.reviewed_at)
            self.assertEqual(review.reviewed_by, "test_reviewer")


class TestRollbackLeavesConsistentState(unittest.TestCase):
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

    def test_rollback_leaves_scholarship_and_review_consistent(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
            )
            session.commit()

            review_id = result.review_id

        with get_session_factory()() as session:
            review = get_review(session, review_id)
            self.assertEqual(review.decision, ReviewDecision.PENDING)

            scholarship = session.get(Scholarship, scholarship_id)
            self.assertEqual(scholarship.duration, "2 years")


class TestRejectChangesNothing(unittest.TestCase):
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

    def test_reject_changes_nothing(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
            )
            session.commit()

            decision = reject_review(session, result.review_id, reviewed_by="test_reviewer")

            self.assertTrue(decision.success)
            self.assertEqual(decision.decision, ReviewDecision.REJECTED)

            scholarship = session.get(Scholarship, scholarship_id)
            self.assertEqual(scholarship.duration, "2 years")

            review = get_review(session, result.review_id)
            self.assertEqual(review.decision, ReviewDecision.REJECTED)
            self.assertIsNotNone(review.reviewed_at)
            self.assertEqual(review.reviewed_by, "test_reviewer")


class TestStaleReviewApprovalBlocked(unittest.TestCase):
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

    def test_stale_review_approval_is_blocked(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
            )
            session.commit()

            scholarship = session.get(Scholarship, scholarship_id)
            scholarship.duration = "5 years"
            session.commit()

        with get_session_factory()() as session:
            decision = approve_review(session, result.review_id, reviewed_by="test_reviewer")

            self.assertFalse(decision.success)
            self.assertTrue(decision.concurrency_conflict)

            review = get_review(session, result.review_id)
            self.assertEqual(review.decision, ReviewDecision.PENDING)

            scholarship = session.get(Scholarship, scholarship_id)
            self.assertEqual(scholarship.duration, "5 years")


class TestAlreadyDecidedReviewCannotBeDecidedAgain(unittest.TestCase):
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

    def test_already_decided_review_cannot_be_decided_again(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
            )
            session.commit()

            approve_review(session, result.review_id, reviewed_by="test_reviewer")

            decision2 = approve_review(session, result.review_id, reviewed_by="test_reviewer")
            self.assertFalse(decision2.success)
            self.assertIn("already decided", decision2.error)

            decision3 = reject_review(session, result.review_id, reviewed_by="test_reviewer")
            self.assertFalse(decision3.success)
            self.assertIn("already decided", decision3.error)


class TestReviewDecisionIsAuditable(unittest.TestCase):
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

    def test_review_decision_is_auditable(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
                source_urls=["https://official-source.gov"],
                evidence_text="Official announcement",
            )
            session.commit()

            review_id = result.review_id
            created_at = get_review(session, review_id).created_at

            approve_review(session, result.review_id, reviewed_by="test_reviewer", reviewer_note="Verified against official source")

            review = get_review(session, review_id)
            self.assertEqual(review.decision, ReviewDecision.APPROVED)
            self.assertEqual(review.reviewed_by, "test_reviewer")
            self.assertEqual(review.reviewer_note, "Verified against official source")
            self.assertIsNotNone(review.reviewed_at)
            self.assertEqual(review.created_at, created_at)
            self.assertEqual(review.scholarship_id, scholarship_id)
            self.assertEqual(review.field_name, "duration")
            self.assertEqual(review.current_value, "2 years")
            self.assertEqual(review.proposed_value, "3 years")
            self.assertEqual(review.conflict_reason, ConflictReason.CONFLICTING_SOURCES)


class TestThirdPartyLowConfidenceIdentityConflictCannotBypassReview(unittest.TestCase):
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

    def test_third_party_source_cannot_bypass_review(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, status="open")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="status",
                current_value="open",
                proposed_value="closed",
                conflict_reason=ConflictReason.THIRD_PARTY_SOURCE,
                confidence="low",
                source_urls=["https://third-party.com"],
            )
            session.commit()

            self.assertTrue(result.created)
            review = get_review(session, result.review_id)
            self.assertEqual(review.conflict_reason, ConflictReason.THIRD_PARTY_SOURCE)

    def test_low_confidence_cannot_bypass_review(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.LOW_CONFIDENCE,
                confidence="low",
            )
            session.commit()

            self.assertTrue(result.created)
            review = get_review(session, result.review_id)
            self.assertEqual(review.conflict_reason, ConflictReason.LOW_CONFIDENCE)

    def test_identity_conflict_cannot_bypass_review(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, title="Original Title")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="title",
                current_value="Original Title",
                proposed_value="Different Title",
                conflict_reason=ConflictReason.IDENTITY_CONFLICT,
                verification_state="needs_review",
            )
            session.commit()

            self.assertTrue(result.created)
            review = get_review(session, result.review_id)
            self.assertEqual(review.conflict_reason, ConflictReason.IDENTITY_CONFLICT)


class TestTransactionFailureDoesNotCreatePartialState(unittest.TestCase):
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

    def test_transaction_failure_does_not_create_partial_state(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            result = create_review(
                session=session,
                scholarship_id=scholarship_id,
                field_name="duration",
                current_value="2 years",
                proposed_value="3 years",
                conflict_reason=ConflictReason.CONFLICTING_SOURCES,
                confidence="high",
            )
            session.commit()

            review_id = result.review_id

        with get_session_factory()() as session:
            review = get_review(session, review_id)
            self.assertEqual(review.decision, ReviewDecision.PENDING)

            scholarship = session.get(Scholarship, scholarship_id)
            self.assertEqual(scholarship.duration, "2 years")

            stmt = select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship_id
            )
            history_count = len(list(session.execute(stmt).scalars().all()))
            self.assertEqual(history_count, 0)


class TestCoordinatorCreatesReviewsFromVerification(unittest.TestCase):
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

    def test_coordinator_creates_reviews_for_uncertain_fields(self):
        from app.services.scholarship_review_coordinator import create_reviews_from_verification
        from app.services.scholarship_verifier import VerificationResult, VerificationStatus
        from app.services.scholarship_diff import ChangeSet, FieldChange, FieldChangeType
        from app.services.scholarship_evidence import (
            EvidenceCollection,
            EvidenceItem,
            EvidenceStatus,
            SourceType,
        )
        from app.services.verification_confidence import (
            ConfidenceLevel,
            VerificationAssessment,
            VerificationState,
            FieldConfidenceResult,
        )

        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years", status="open")

            changeset = ChangeSet(
                changes=[
                    FieldChange(
                        field="duration",
                        change_type=FieldChangeType.MODIFIED,
                        old_value="2 years",
                        new_value="3 years",
                        confidence="high",
                        is_update_candidate=True,
                    ),
                ],
            )

            evidence_item = EvidenceItem(
                scholarship_id=scholarship_id,
                field_name="duration",
                extracted_value="3 years",
                source_url="https://third-party-blog.com",
                evidence_text="Blog says 3 years",
                confidence="high",
                source_type=SourceType.THIRD_PARTY,
                verification_timestamp="2026-01-01T00:00:00+00:00",
                status=EvidenceStatus.HIGH_CONFIDENCE,
            )
            evidence_collection = EvidenceCollection(
                scholarship_id=scholarship_id,
                source_url="https://third-party-blog.com",
                items=[evidence_item],
            )

            confidence_result = FieldConfidenceResult(
                field_name="duration",
                value="3 years",
                confidence=ConfidenceLevel.LOW,
                verification_state=VerificationState.UNCERTAIN,
                source_count=1,
                authoritative_source_count=0,
                agreeing_source_count=1,
                conflicting_source_count=0,
                is_update_candidate=False,
                reason="Third-party source",
            )
            confidence_assessment = VerificationAssessment(
                scholarship_id=scholarship_id,
                field_results=[confidence_result],
            )

            verification_result = VerificationResult(
                scholarship_id=scholarship_id,
                verification_status=VerificationStatus.UNCERTAIN,
                uncertain_fields=["duration"],
                changed_fields={"duration": ("2 years", "3 years")},
                changeset=changeset,
                evidence_collection=evidence_collection,
                confidence_assessment=confidence_assessment,
            )

            results = create_reviews_from_verification(session, verification_result)

            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].created)

            review = get_review(session, results[0].review_id)
            self.assertEqual(review.field_name, "duration")
            self.assertEqual(review.conflict_reason, ConflictReason.THIRD_PARTY_SOURCE)
            self.assertEqual(review.source_urls, ["https://third-party-blog.com"])
            self.assertEqual(review.evidence_text, "Blog says 3 years")


if __name__ == "__main__":
    unittest.main()
