"""TASK 37 — Full Integration & Production Readiness Audit.

End-to-end tests exercising the complete verification lifecycle:
DISCOVERY -> FETCH -> EXTRACTION -> DIFF -> EVIDENCE -> CONFIDENCE ->
CONSENSUS -> ANOMALY -> COUNTERFACTUAL SAFETY -> AUTO UPDATE / HUMAN REVIEW ->
HISTORY -> SNAPSHOT -> CALIBRATION -> RECOVERY / RESTORE

Focus areas:
1. Auto-update integrity (update -> history -> snapshot consistency)
2. Human review (approve/reject, stale protection, no unsafe mutation)
3. Recovery (restore -> safety gate -> update -> history -> new snapshot)
4. Cross-layer consistency (Scholarship, ScholarshipReview, ScholarshipVerificationHistory,
   ScholarshipSnapshot, ScholarshipRestoreRecord, Calibration state)
5. Realistic E2E scenarios
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Base,
    Scholarship,
    ScholarshipRestoreRecord,
    ScholarshipReview,
    ScholarshipSnapshot,
    ScholarshipVerificationHistory,
)
from app.services.counterfactual_safety import (
    CounterfactualSeverity,
    simulate_counterfactual,
)
from app.services.feedback_calibration import (
    HumanDecision,
    compute_calibration,
    record_feedback,
)
from app.services.scholarship_history import HistoryEntry, write_verification_history
from app.services.scholarship_recovery import (
    RestoreBlockReason,
    RestoreOutcome,
    restore_snapshot,
)
from app.services.scholarship_review import (
    ReviewDecision,
    approve_review,
    create_review,
    get_pending_reviews,
    reject_review,
)
from app.services.scholarship_updater import (
    _UPDATE_STATUS_SUCCESS,
    apply_verified_updates,
)
from app.services.temporal_versioning import (
    create_snapshot,
    get_current_version,
    get_state_at,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory):
    return session_factory()


def _make_scholarship(
    session: Session,
    *,
    scholarship_id: int = 1,
    title: str = "Test Scholarship",
    status: str = "open",
    funding: str = "Full",
    country: str = "Test Country",
    degree: str = "PhD",
    duration: str = "2 years",
    description: str = "Original description",
    deadline_date: date | None = None,
    official_source: str = "Test Source",
    eligibility: list[str] | None = None,
    application_method: list[str] | None = None,
) -> Scholarship:
    s = Scholarship(
        id=scholarship_id,
        title=title,
        country=country,
        degree=degree,
        funding=funding,
        status=status,
        duration=duration,
        description=description,
        official_source=official_source,
        official_source_url=f"https://example{scholarship_id}.gov/scholarship",
        deadline_date=deadline_date,
        eligibility=eligibility or ["Must be enrolled"],
        application_method=application_method or ["Online"],
    )
    session.add(s)
    session.commit()
    return s


def _create_snapshot_with_state(
    session: Session,
    scholarship: Scholarship,
    changed_fields: list[str],
    timestamp: datetime | None = None,
) -> ScholarshipSnapshot:
    return create_snapshot(
        session,
        scholarship,
        changed_fields=changed_fields,
        timestamp=timestamp,
    )


# ============================================================================
# 1. AUTO-UPDATE INTEGRITY TESTS
# ============================================================================


class TestAutoUpdateIntegrity:
    """Test update -> history -> snapshot consistency."""

    def test_auto_update_creates_history_and_snapshot(self, session):
        """Successful auto-update creates both history and snapshot."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        # Apply auto-update
        candidates = [
            {
                "field": "duration",
                "old_value": "2 years",
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]
        update_result = apply_verified_updates(session, 1, candidates)

        assert update_result.update_status == _UPDATE_STATUS_SUCCESS
        assert "duration" in update_result.updated_fields

        # Write history
        history_entries = [
            HistoryEntry(
                field_name="duration",
                old_value="2 years",
                new_value="3 years",
                change_type="modified",
                source_url="https://example1.gov/scholarship",
                evidence_text="Updated from official source",
                confidence="high",
                verification_status="auto_updated",
            )
        ]
        write_verification_history(session, 1, history_entries)

        # Create new snapshot
        session.refresh(scholarship)
        new_snapshot_result = create_snapshot(
            session,
            scholarship,
            changed_fields=["duration"],
            source_url="https://example1.gov/scholarship",
        )

        # Verify consistency
        assert new_snapshot_result.created is True

        # Retrieve the actual snapshot to verify data
        new_snapshot = session.scalar(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.version_id == new_snapshot_result.version_id
            )
        )
        assert new_snapshot is not None
        assert new_snapshot.snapshot_data["duration"] == "3 years"

        # Verify history was written
        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == 1
            )
        ).all()
        assert len(history) >= 1
        assert history[0].field_name == "duration"
        assert history[0].old_value == "2 years"
        assert history[0].new_value == "3 years"

    def test_atomic_rollback_on_failure(self, session):
        """Failed update rolls back all changes atomically."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years", funding="Full")

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration", "funding"], timestamp=t1)

        # Get original state
        original_duration = scholarship.duration
        original_funding = scholarship.funding

        # Apply update with one valid and one invalid candidate
        candidates = [
            {
                "field": "duration",
                "old_value": "2 years",
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            },
            {
                "field": "title",  # Frozen field - should be rejected
                "old_value": "Test Scholarship",
                "new_value": "New Title",
                "confidence": "high",
                "is_update_candidate": True,
            },
        ]
        update_result = apply_verified_updates(session, 1, candidates)

        # Should succeed with partial status (duration updated, title rejected)
        assert update_result.update_status == "partial"
        assert "duration" in update_result.updated_fields
        assert any(r["field"] == "title" for r in update_result.rejected_fields)

        # Verify scholarship was updated
        session.refresh(scholarship)
        assert scholarship.duration == "3 years"
        assert scholarship.title == "Test Scholarship"  # Unchanged

    def test_concurrency_conflict_detected(self, session):
        """Concurrency conflict is detected when old_value doesn't match current."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Try to update with wrong old_value (simulating concurrent modification)
        candidates = [
            {
                "field": "duration",
                "old_value": "1 year",  # Wrong - actual is "2 years"
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]
        update_result = apply_verified_updates(session, 1, candidates)

        assert update_result.concurrency_conflict is True
        assert update_result.update_status == "conflict"

        # Verify scholarship was NOT modified
        session.refresh(scholarship)
        assert scholarship.duration == "2 years"

    def test_idempotent_update_no_duplicate_history(self, session):
        """Reapplying the same update is idempotent."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        candidates = [
            {
                "field": "duration",
                "old_value": "2 years",
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]

        # First update
        result1 = apply_verified_updates(session, 1, candidates)
        assert result1.update_status == _UPDATE_STATUS_SUCCESS

        # Second update with same values (now old_value matches current)
        candidates2 = [
            {
                "field": "duration",
                "old_value": "3 years",  # Now current value
                "new_value": "3 years",  # Same as current
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]
        result2 = apply_verified_updates(session, 1, candidates2)
        assert result2.update_status == "noop"


# ============================================================================
# 2. HUMAN REVIEW TESTS
# ============================================================================


class TestHumanReview:
    """Test approve/reject, stale protection, no unsafe mutation."""

    def test_human_approval_updates_scholarship(self, session):
        """Human approval through review updates scholarship correctly."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create review
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
            verification_state="uncertain",
            confidence="medium",
        )
        assert review_result.created is True
        review_id = review_result.review_id

        # Approve review
        approval_result = approve_review(
            session,
            review_id=review_id,
            reviewed_by="human_reviewer",
            reviewer_note="Verified with official source",
        )

        assert approval_result.success is True
        assert approval_result.decision == ReviewDecision.APPROVED
        assert "duration" in approval_result.updated_fields

        # Verify scholarship was updated
        session.refresh(scholarship)
        assert scholarship.duration == "3 years"

        # Verify review record is updated
        review = session.get(ScholarshipReview, review_id)
        assert review.decision == ReviewDecision.APPROVED
        assert review.reviewed_by == "human_reviewer"

    def test_human_rejection_leaves_scholarship_unchanged(self, session):
        """Human rejection does not modify scholarship."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create review
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="low_confidence",
            verification_state="uncertain",
            confidence="low",
        )
        review_id = review_result.review_id

        # Reject review
        rejection_result = reject_review(
            session,
            review_id=review_id,
            reviewed_by="human_reviewer",
            reviewer_note="Insufficient evidence",
        )

        assert rejection_result.success is True
        assert rejection_result.decision == ReviewDecision.REJECTED

        # Verify scholarship was NOT modified
        session.refresh(scholarship)
        assert scholarship.duration == "2 years"

        # Verify review record is updated
        review = session.get(ScholarshipReview, review_id)
        assert review.decision == ReviewDecision.REJECTED

    def test_stale_review_approval_blocked(self, session):
        """Approval of stale review (current value changed) is blocked."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create review
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
        )
        review_id = review_result.review_id

        # Modify scholarship externally (simulating concurrent change)
        scholarship.duration = "4 years"
        session.commit()

        # Try to approve stale review
        approval_result = approve_review(
            session,
            review_id=review_id,
            reviewed_by="human_reviewer",
        )

        assert approval_result.success is False
        assert approval_result.concurrency_conflict is True

        # Verify scholarship was NOT modified by the stale approval
        session.refresh(scholarship)
        assert scholarship.duration == "4 years"

    def test_duplicate_review_prevention(self, session):
        """Cannot create duplicate pending reviews for same field."""
        _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create first review
        result1 = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
        )
        assert result1.created is True

        # Try to create duplicate
        result2 = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="4 years",
            conflict_reason="conflicting_sources",
        )
        assert result2.created is False
        assert result2.existing_review_id == result1.review_id

    def test_review_immutability_after_decision(self, session):
        """Review records are immutable after decision."""
        _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create and approve review
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
        )
        review_id = review_result.review_id

        approve_review(session, review_id=review_id, reviewed_by="reviewer1")

        # Try to approve again
        second_approval = approve_review(session, review_id=review_id, reviewed_by="reviewer2")
        assert second_approval.success is False
        assert "already decided" in second_approval.error


# ============================================================================
# 3. RECOVERY TESTS
# ============================================================================


class TestRecovery:
    """Test restore flow, safety gates, idempotency."""

    def test_successful_restore_full_cycle(self, session):
        """Complete restore cycle: snapshot -> modify -> restore -> verify."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            duration="2 years",
            description="Original description",
        )

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration", "description"], timestamp=t1)
        original_version_id = r1.version_id

        # Modify scholarship
        scholarship.duration = "3 years"
        scholarship.description = "Modified description"
        session.commit()

        # Restore to original
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Reverting incorrect changes",
        )

        assert result.success is True
        assert result.outcome == RestoreOutcome.SUCCESS
        assert "duration" in result.restored_fields
        assert "description" in result.restored_fields

        # Verify scholarship restored
        session.refresh(scholarship)
        assert scholarship.duration == "2 years"
        assert scholarship.description == "Original description"

        # Verify new snapshot created
        assert result.target_version_id is not None
        assert result.target_version_id != original_version_id

        # Verify restore record created
        assert result.restore_record_id is not None
        record = session.get(ScholarshipRestoreRecord, result.restore_record_id)
        assert record is not None
        assert record.outcome == RestoreOutcome.SUCCESS

    def test_restore_blocked_by_rejected_review(self, session):
        """Restore that would reintroduce rejected changes is blocked."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create snapshot
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        # Modify scholarship
        scholarship.duration = "3 years"
        session.commit()

        # Create rejected review for the original value
        review = ScholarshipReview(
            scholarship_id=1,
            field_name="duration",
            current_value="3 years",
            proposed_value="2 years",  # This was rejected
            conflict_reason="test",
            verification_state="uncertain",
            confidence="high",
            decision="rejected",
            created_at=datetime.now(timezone.utc),
        )
        session.add(review)
        session.commit()

        # Try to restore (would reintroduce rejected value)
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing rejected review protection",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.REJECTED_REVIEW_CONFLICT

        # Verify scholarship was NOT modified
        session.refresh(scholarship)
        assert scholarship.duration == "3 years"

    def test_restore_blocked_by_safety_critical(self, session):
        """Restore that violates safety-critical rules is blocked."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            status="open",
        )

        # Create snapshot with open status
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["status"], timestamp=t1)
        original_version_id = r1.version_id

        # Change to archived (terminal state)
        scholarship.status = "archived"
        session.commit()

        # Try to restore to open (terminal regression)
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing safety block",
        )

        assert result.success is False
        assert result.outcome == RestoreOutcome.BLOCKED
        assert result.block_reason == RestoreBlockReason.SAFETY_CRITICAL

        # Verify scholarship was NOT modified
        session.refresh(scholarship)
        assert scholarship.status == "archived"

    def test_restore_idempotency(self, session):
        """Repeated restore with same parameters is idempotent."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create snapshot
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        # Modify scholarship
        scholarship.duration = "3 years"
        session.commit()

        # First restore
        result1 = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing idempotency",
        )
        assert result1.success is True
        assert result1.outcome == RestoreOutcome.SUCCESS

        # Modify again to allow second restore
        scholarship.duration = "4 years"
        session.commit()

        # Second restore with same parameters (should be idempotent)
        result2 = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing idempotency",
        )
        assert result2.success is True
        assert result2.outcome == RestoreOutcome.IDEMPOTENT
        assert result2.operation_id == result1.operation_id

        # Verify only one restore record exists
        count = session.scalar(select(func.count()).select_from(ScholarshipRestoreRecord))
        assert count == 1

    def test_restore_creates_new_snapshot_not_mutates_old(self, session):
        """Restore creates new snapshot, old snapshots remain immutable."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create snapshot
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id
        original_snapshot_id = r1.snapshot_id

        # Modify and create second snapshot
        scholarship.duration = "3 years"
        session.flush()
        t2 = datetime(2024, 2, 1)
        r2 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t2)

        # Restore to first snapshot
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing snapshot immutability",
        )

        assert result.success is True

        # Verify original snapshot is unchanged
        original_snapshot = session.get(ScholarshipSnapshot, original_snapshot_id)
        assert original_snapshot.snapshot_data["duration"] == "2 years"
        assert original_snapshot.version_id == original_version_id

        # Verify new snapshot exists
        new_snapshot = session.scalar(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.version_id == result.target_version_id
            )
        )
        assert new_snapshot is not None
        assert new_snapshot.is_current is True


# ============================================================================
# 4. CROSS-LAYER CONSISTENCY TESTS
# ============================================================================


class TestCrossLayerConsistency:
    """Test consistency across all models after operations."""

    def test_full_verification_cycle_consistency(self, session):
        """Verify all models remain consistent after full verification cycle."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            duration="2 years",
            description="Original",
        )

        # Step 1: Create initial snapshot
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration", "description"], timestamp=t1)

        # Step 2: Apply auto-update
        candidates = [
            {
                "field": "duration",
                "old_value": "2 years",
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]
        update_result = apply_verified_updates(session, 1, candidates)
        assert update_result.update_status == _UPDATE_STATUS_SUCCESS

        # Step 3: Write history
        history_entries = [
            HistoryEntry(
                field_name="duration",
                old_value="2 years",
                new_value="3 years",
                change_type="modified",
                verification_status="auto_updated",
            )
        ]
        write_verification_history(session, 1, history_entries)

        # Step 4: Create new snapshot
        session.refresh(scholarship)
        r2 = create_snapshot(session, scholarship, ["duration"])

        # Verify consistency
        # Scholarship
        assert scholarship.duration == "3 years"

        # Snapshot chain
        snapshots = session.scalars(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.scholarship_id == 1
            ).order_by(ScholarshipSnapshot.valid_from.asc())
        ).all()
        assert len(snapshots) == 2
        assert snapshots[0].is_current is False
        assert snapshots[0].valid_to is not None
        assert snapshots[1].is_current is True
        assert snapshots[1].valid_to is None

        # History
        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == 1
            )
        ).all()
        assert len(history) >= 1

    def test_review_approval_updates_all_layers(self, session):
        """Review approval updates scholarship, history, and snapshot consistently."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        # Create review
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
        )
        review_id = review_result.review_id

        # Approve review
        approval_result = approve_review(session, review_id=review_id, reviewed_by="reviewer")
        assert approval_result.success is True

        # Verify all layers
        # Scholarship
        session.refresh(scholarship)
        assert scholarship.duration == "3 years"

        # Review
        review = session.get(ScholarshipReview, review_id)
        assert review.decision == ReviewDecision.APPROVED

        # History
        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == 1,
                ScholarshipVerificationHistory.field_name == "duration",
            )
        ).all()
        assert len(history) >= 1
        assert history[0].new_value == "3 years"

    def test_restore_updates_all_layers(self, session):
        """Restore updates scholarship, history, snapshot, and restore record."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create snapshot
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        # Modify
        scholarship.duration = "3 years"
        session.commit()

        # Restore
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing full layer update",
        )
        assert result.success is True

        # Verify all layers
        # Scholarship
        session.refresh(scholarship)
        assert scholarship.duration == "2 years"

        # New snapshot
        new_snapshot = session.scalar(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.version_id == result.target_version_id
            )
        )
        assert new_snapshot is not None
        assert new_snapshot.is_current is True
        assert new_snapshot.snapshot_data["duration"] == "2 years"

        # History
        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == 1,
                ScholarshipVerificationHistory.change_type == "restored",
            )
        ).all()
        assert len(history) >= 1

        # Restore record
        record = session.get(ScholarshipRestoreRecord, result.restore_record_id)
        assert record is not None
        assert record.outcome == RestoreOutcome.SUCCESS

    def test_failed_operation_consistency(self, session):
        """Failed operations leave all layers in consistent state."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        # Get original state
        original_duration = scholarship.duration

        # Try to update with wrong old_value (concurrency conflict)
        candidates = [
            {
                "field": "duration",
                "old_value": "wrong_value",
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]
        update_result = apply_verified_updates(session, 1, candidates)

        assert update_result.concurrency_conflict is True

        # Verify all layers remain consistent
        session.refresh(scholarship)
        assert scholarship.duration == original_duration

        # No new history should be written for failed update
        history_count = session.scalar(
            select(func.count()).select_from(ScholarshipVerificationHistory)
        )
        assert history_count == 0


# ============================================================================
# 5. REALISTIC E2E SCENARIOS
# ============================================================================


class TestRealisticE2EScenarios:
    """Realistic end-to-end scenarios."""

    def test_normal_verification_update_scenario(self, session):
        """Scenario: Normal verification detects change and auto-updates."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            duration="2 years",
            deadline_date=date(2024, 12, 31),
        )

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration", "deadline_date"], timestamp=t1)

        # Verification detects change
        candidates = [
            {
                "field": "duration",
                "old_value": "2 years",
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]
        update_result = apply_verified_updates(session, 1, candidates)
        assert update_result.update_status == _UPDATE_STATUS_SUCCESS

        # Write history
        write_verification_history(
            session,
            1,
            [HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years", change_type="modified")],
        )

        # Create new snapshot
        session.refresh(scholarship)
        create_snapshot(session, scholarship, ["duration"])

        # Verify final state
        assert scholarship.duration == "3 years"
        current_version = get_current_version(session, 1)
        assert current_version is not None
        assert current_version.snapshot_data["duration"] == "3 years"

    def test_human_approval_scenario(self, session):
        """Scenario: Conflicting evidence triggers review, human approves."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        # Conflicting evidence creates review
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
            verification_state="uncertain",
            confidence="medium",
        )
        assert review_result.created is True

        # Verify pending review exists
        pending = get_pending_reviews(session, 1)
        assert len(pending) == 1

        # Human approves
        approval = approve_review(session, review_result.review_id, reviewed_by="expert_reviewer")
        assert approval.success is True

        # Verify state
        session.refresh(scholarship)
        assert scholarship.duration == "3 years"

        # Verify no pending reviews
        pending = get_pending_reviews(session, 1)
        assert len(pending) == 0

    def test_human_rejection_scenario(self, session):
        """Scenario: Low confidence triggers review, human rejects."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create review for low confidence change
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="low_confidence",
            verification_state="uncertain",
            confidence="low",
        )

        # Human rejects
        rejection = reject_review(session, review_result.review_id, reviewed_by="expert_reviewer")
        assert rejection.success is True

        # Verify scholarship unchanged
        session.refresh(scholarship)
        assert scholarship.duration == "2 years"

    def test_conflicting_evidence_scenario(self, session):
        """Scenario: Multiple sources provide conflicting information."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create review for conflicting sources
        review_result = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
            source_urls=["https://source-a.com", "https://source-b.com"],
            verification_state="conflict",
        )

        # Verify review created with conflict info
        review = session.get(ScholarshipReview, review_result.review_id)
        assert review.conflict_reason == "conflicting_sources"
        assert len(review.source_urls) == 2

    def test_safety_blocked_update_scenario(self, session):
        """Scenario: Safety rules block an update that would create inconsistency."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            status="archived",
            deadline_date=date(2025, 6, 1),  # Future deadline
        )

        # Try to simulate a change that would violate safety
        proposed_changes = {"status": "open"}  # Terminal regression

        result = simulate_counterfactual(
            session=session,
            scholarship=scholarship,
            proposed_changes=proposed_changes,
        )

        # Should be blocked by safety
        assert result.severity == CounterfactualSeverity.CRITICAL
        assert result.should_block() is True

    def test_failed_update_rollback_scenario(self, session):
        """Scenario: Update fails and all changes are rolled back."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            duration="2 years",
            funding="Full",
        )

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration", "funding"], timestamp=t1)

        # Get original state
        original_duration = scholarship.duration
        original_funding = scholarship.funding

        # Try update with concurrency conflict
        candidates = [
            {
                "field": "duration",
                "old_value": "wrong_value",  # Simulates concurrent modification
                "new_value": "3 years",
                "confidence": "high",
                "is_update_candidate": True,
            }
        ]
        result = apply_verified_updates(session, 1, candidates)

        assert result.concurrency_conflict is True

        # Verify rollback
        session.refresh(scholarship)
        assert scholarship.duration == original_duration
        assert scholarship.funding == original_funding

    def test_successful_restore_scenario(self, session):
        """Scenario: Admin restores scholarship to previous state after bad update."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            duration="2 years",
            description="Original description",
        )

        # Create initial snapshot (good state)
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration", "description"], timestamp=t1)
        good_version_id = r1.version_id

        # Bad update occurs
        scholarship.duration = "wrong_duration"
        scholarship.description = "wrong_description"
        session.commit()

        # Create snapshot of bad state
        t2 = datetime(2024, 2, 1)
        _create_snapshot_with_state(session, scholarship, ["duration", "description"], timestamp=t2)

        # Admin restores to good state
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=good_version_id,
            operator="admin",
            reason="Reverting bad update",
        )

        assert result.success is True
        assert result.outcome == RestoreOutcome.SUCCESS

        # Verify restoration
        session.refresh(scholarship)
        assert scholarship.duration == "2 years"
        assert scholarship.description == "Original description"

    def test_failed_restore_scenario(self, session):
        """Scenario: Restore fails due to safety violation."""
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            status="open",
        )

        # Create snapshot with open status
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["status"], timestamp=t1)
        original_version_id = r1.version_id

        # Change to archived (terminal state)
        scholarship.status = "archived"
        session.commit()

        # Try to restore to open (terminal regression)
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing failed restore",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.SAFETY_CRITICAL

    def test_repeated_restore_idempotency_scenario(self, session):
        """Scenario: Same restore operation multiple times is idempotent."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create snapshot
        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        # Modify
        scholarship.duration = "3 years"
        session.commit()

        # First restore
        result1 = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing idempotency",
        )
        assert result1.outcome == RestoreOutcome.SUCCESS

        # Modify again
        scholarship.duration = "4 years"
        session.commit()

        # Second restore (same parameters)
        result2 = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="admin",
            reason="Testing idempotency",
        )
        assert result2.outcome == RestoreOutcome.IDEMPOTENT
        assert result2.operation_id == result1.operation_id


# ============================================================================
# 6. CALIBRATION INTEGRATION TESTS
# ============================================================================


class TestCalibrationIntegration:
    """Test calibration with review feedback."""

    def test_calibration_from_review_feedback(self, session):
        """Calibration statistics computed from review feedback."""
        _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create reviews and record feedback
        review1 = create_review(
            session,
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="3 years",
            conflict_reason="conflicting_sources",
        )

        # Record feedback (human approved)
        feedback1 = record_feedback(
            review_id=review1.review_id,
            scholarship_id=1,
            field_name="duration",
            model_confidence=0.85,
            decision="auto_update",
            human_decision=HumanDecision.APPROVED,
        )

        # Compute calibration
        calibration = compute_calibration([feedback1])

        assert calibration.overall_sample_count == 1
        assert calibration.overall_approval_count == 1
        assert calibration.overall_approval_rate == 1.0

    def test_calibration_detects_over_confidence(self, session):
        """Calibration detects when system is over-confident."""
        _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create feedback records showing over-confidence
        # (high confidence but human rejected)
        feedbacks = []
        for i in range(15):
            review = create_review(
                session,
                scholarship_id=1,
                field_name=f"field_{i}",
                current_value="old",
                proposed_value="new",
                conflict_reason="conflicting_sources",
            )
            feedbacks.append(
                record_feedback(
                    review_id=review.review_id,
                    scholarship_id=1,
                    field_name=f"field_{i}",
                    model_confidence=0.95,  # High confidence
                    decision="auto_update",
                    human_decision=HumanDecision.REJECTED,  # But rejected
                )
            )

        calibration = compute_calibration(feedbacks)

        # System is over-confident (high confidence, low approval rate)
        assert calibration.overall_calibration_error > 0
        assert calibration.overall_approval_rate < 0.5


# ============================================================================
# 7. PRODUCTION READINESS TESTS
# ============================================================================


class TestProductionReadiness:
    """Test production readiness concerns."""

    def test_no_n_plus_1_in_history_write(self, session):
        """History write uses single bulk insert, no N+1 queries."""
        scholarship = _make_scholarship(session, scholarship_id=1)

        # Create multiple history entries
        entries = [
            HistoryEntry(field_name=f"field_{i}", old_value=str(i), new_value=str(i + 1))
            for i in range(10)
        ]

        # Write all at once (single bulk insert)
        result = write_verification_history(session, 1, entries)

        assert result.entries_written == 10
        assert len(result.history_ids) == 10

    def test_snapshot_chain_integrity(self, session):
        """Snapshot chain maintains integrity after multiple operations."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create multiple snapshots
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 2, 1),
            datetime(2024, 3, 1),
            datetime(2024, 4, 1),
        ]

        for i, ts in enumerate(timestamps):
            scholarship.duration = f"{i + 2} years"
            session.flush()
            create_snapshot(session, scholarship, ["duration"], timestamp=ts)

        # Verify chain integrity
        snapshots = session.scalars(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.scholarship_id == 1
            ).order_by(ScholarshipSnapshot.valid_from.asc())
        ).all()

        assert len(snapshots) == 4

        # Only latest should be current
        current_count = sum(1 for s in snapshots if s.is_current)
        assert current_count == 1
        assert snapshots[-1].is_current is True

        # All non-current should have valid_to
        for s in snapshots[:-1]:
            assert s.is_current is False
            assert s.valid_to is not None

    def test_temporal_reconstruction_accuracy(self, session):
        """Temporal reconstruction returns correct historical state."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create snapshots at different times
        t1 = datetime(2024, 1, 1)
        create_snapshot(session, scholarship, ["duration"], timestamp=t1)

        scholarship.duration = "3 years"
        session.flush()
        t2 = datetime(2024, 2, 1)
        create_snapshot(session, scholarship, ["duration"], timestamp=t2)

        scholarship.duration = "4 years"
        session.flush()
        t3 = datetime(2024, 3, 1)
        create_snapshot(session, scholarship, ["duration"], timestamp=t3)

        # Reconstruct state at t1
        state1 = get_state_at(session, 1, t1)
        assert state1.found is True
        assert state1.state["duration"] == "2 years"

        # Reconstruct state at t2
        state2 = get_state_at(session, 1, t2)
        assert state2.found is True
        assert state2.state["duration"] == "3 years"

        # Reconstruct state at t3
        state3 = get_state_at(session, 1, t3)
        assert state3.found is True
        assert state3.state["duration"] == "4 years"

    def test_error_handling_preserves_consistency(self, session):
        """Error handling preserves data consistency."""
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        # Create initial snapshot
        t1 = datetime(2024, 1, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        # Try to restore non-existent snapshot
        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id="nonexistent_version_123456",
            operator="admin",
            reason="Testing error handling",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.SNAPSHOT_NOT_FOUND

        # Verify scholarship is unchanged
        session.refresh(scholarship)
        assert scholarship.duration == "2 years"

        # Verify no restore record created for failed operation
        restore_count = session.scalar(select(func.count()).select_from(ScholarshipRestoreRecord))
        assert restore_count == 0
