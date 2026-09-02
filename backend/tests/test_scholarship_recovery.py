"""Focused tests for disaster recovery / snapshot restore workflow.

Tests cover:
1. successful restore
2. corrupted snapshot
3. broken version chain
4. rejected-review protection
5. counterfactual safety block
6. frozen-field protection
7. atomic rollback
8. idempotent repeated restore
9. immutable old snapshots
10. audit record creation
11. exactly one current snapshot
12. restore creates a NEW snapshot
13. no changes when already at snapshot state
14. snapshot not found
15. scholarship not found
"""

from __future__ import annotations

from datetime import date, datetime, timezone

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
from app.services.counterfactual_safety import simulate_counterfactual
from app.services.scholarship_history import HistoryEntry, write_verification_history
from app.services.scholarship_recovery import (
    RestoreBlockReason,
    RestoreOutcome,
    RestoreResult,
    check_rejected_review_conflicts,
    restore_snapshot,
    validate_snapshot_integrity,
    verify_version_chain,
)
from app.services.temporal_versioning import create_snapshot


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
    title: str = "Test Scholarship",
    status: str = "open",
    funding: str = "Full",
    country: str = "Test Country",
    degree: str = "PhD",
    duration: str = "2 years",
    description: str = "Original description",
    deadline_date: date | None = None,
    official_source: str = "Test Source",
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


class TestSuccessfulRestore:
    def test_restore_brings_back_original_values(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years", description="Original description")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration", "description"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        scholarship.description = "Modified description"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True
        assert result.outcome == RestoreOutcome.SUCCESS

        refreshed = session.get(Scholarship, 1)
        assert refreshed.duration == "2 years"
        assert refreshed.description == "Original description"

    def test_restore_only_affected_fields(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years", funding="Full")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration", "funding"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        scholarship.funding = "Partial"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True
        assert "duration" in result.restored_fields
        assert "funding" in result.restored_fields

    def test_restore_creates_new_snapshot(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True
        assert result.target_version_id is not None
        assert result.target_version_id != original_version_id

        new_snapshot = session.scalar(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.version_id == result.target_version_id
            )
        )
        assert new_snapshot is not None
        assert new_snapshot.is_current is True

    def test_restore_marks_old_snapshot_not_current(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        scholarship.duration = "3 years"
        session.flush()
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t2)

        original_snapshot = session.get(ScholarshipSnapshot, r1.snapshot_id)
        assert original_snapshot.is_current is False

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=r1.version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True

    def test_restore_creates_verification_history(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == 1
            )
        ).all()

        assert len(history) >= 1
        restore_entries = [h for h in history if h.change_type == "restored"]
        assert len(restore_entries) >= 1
        assert restore_entries[0].field_name == "duration"
        assert "2 years" in (restore_entries[0].new_value, "")


class TestCorruptedSnapshot:
    def test_corrupt_snapshot_data_rejected(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id="nonexistent_version_id_xx",
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.outcome == RestoreOutcome.REJECTED
        assert result.block_reason == RestoreBlockReason.SNAPSHOT_NOT_FOUND

    def test_snapshot_with_invalid_version_id(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        r1 = _create_snapshot_with_state(session, scholarship, ["duration"])
        snapshot = session.get(ScholarshipSnapshot, r1.snapshot_id)
        snapshot.version_id = "short"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id="short",
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.CORRUPT_SNAPSHOT


class TestBrokenVersionChain:
    def test_multiple_current_versions_detected(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        scholarship.duration = "3 years"
        session.flush()
        t2 = datetime(2024, 2, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t2)

        from sqlalchemy import update
        session.execute(
            update(ScholarshipSnapshot)
            .where(ScholarshipSnapshot.scholarship_id == 1)
            .values(is_current=True)
        )
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=r1.version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.BROKEN_VERSION_CHAIN

    def test_non_current_without_valid_to_detected(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        scholarship.duration = "3 years"
        session.flush()
        t2 = datetime(2024, 2, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t2)

        from sqlalchemy import update
        session.execute(
            update(ScholarshipSnapshot)
            .where(ScholarshipSnapshot.version_id == r1.version_id)
            .values(is_current=False, valid_to=None)
        )
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=r1.version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.BROKEN_VERSION_CHAIN


class TestRejectedReviewProtection:
    def test_restore_blocked_by_rejected_review(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        review = ScholarshipReview(
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="2 years",
            conflict_reason="test",
            verification_state="uncertain",
            confidence="high",
            decision="rejected",
            created_at=datetime.now(timezone.utc),
        )
        session.add(review)
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.REJECTED_REVIEW_CONFLICT

    def test_restore_allowed_when_no_rejected_review(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True

    def test_check_rejected_review_conflicts_detects_match(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        review = ScholarshipReview(
            scholarship_id=1,
            field_name="duration",
            current_value="2 years",
            proposed_value="2 years",
            conflict_reason="test",
            verification_state="uncertain",
            confidence="high",
            decision="rejected",
            created_at=datetime.now(timezone.utc),
        )
        session.add(review)
        session.commit()

        has_conflict, fields, _ = check_rejected_review_conflicts(
            session, 1, {"duration": "2 years"}
        )

        assert has_conflict is True
        assert "duration" in fields


class TestCounterfactualSafetyBlock:
    def test_restore_blocked_by_critical_safety(self, session):
        scholarship = _make_scholarship(
            session,
            scholarship_id=1,
            status="open",
        )

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["status"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.status = "archived"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.outcome == RestoreOutcome.BLOCKED
        assert result.block_reason == RestoreBlockReason.SAFETY_CRITICAL

    def test_restore_allowed_when_safety_safe(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years", status="open")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True


class TestFrozenFieldProtection:
    def test_frozen_field_rejected(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years", title="Original Title")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration", "title"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        scholarship.title = "Modified Title"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.FROZEN_FIELD


class TestIdempotentRestore:
    def test_repeated_restore_returns_idempotent(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        result1 = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result1.success is True
        assert result1.outcome == RestoreOutcome.SUCCESS

        result2 = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result2.success is True
        assert result2.outcome == RestoreOutcome.IDEMPOTENT
        assert result2.operation_id == result1.operation_id

    def test_idempotent_restore_no_duplicate_records(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        count = session.scalar(
            select(func.count()).select_from(ScholarshipRestoreRecord)
        )
        assert count == 1


class TestImmutableOldSnapshots:
    def test_original_snapshot_unchanged_after_restore(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id
        original_snapshot_id = r1.snapshot_id

        scholarship.duration = "3 years"
        session.commit()

        restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        original_snapshot = session.get(ScholarshipSnapshot, original_snapshot_id)
        assert original_snapshot.version_id == original_version_id
        assert original_snapshot.snapshot_data["duration"] == "2 years"


class TestAuditRecordCreation:
    def test_successful_restore_creates_audit_record(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.restore_record_id is not None

        record = session.get(ScholarshipRestoreRecord, result.restore_record_id)
        assert record is not None
        assert record.scholarship_id == 1
        assert record.source_version_id == original_version_id
        assert record.target_version_id == result.target_version_id
        assert record.operator == "test_operator"
        assert record.reason == "Testing restore"
        assert record.outcome == RestoreOutcome.SUCCESS
        assert "duration" in record.restored_fields

    def test_audit_record_distinguishable_from_normal_updates(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        record = session.scalar(select(ScholarshipRestoreRecord))
        assert record is not None
        assert record.operation_id is not None
        assert len(record.operation_id) == 16


class TestExactlyOneCurrentSnapshot:
    def test_restore_maintains_single_current_snapshot(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)

        scholarship.duration = "3 years"
        session.flush()
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t2)

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=r1.version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True

        current_count = session.scalar(
            select(func.count())
            .select_from(ScholarshipSnapshot)
            .where(
                ScholarshipSnapshot.scholarship_id == 1,
                ScholarshipSnapshot.is_current == True,
            )
        )
        assert current_count == 1


class TestRestoreCreatesNewSnapshot:
    def test_restore_creates_new_current_snapshot(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is True

        new_snapshot = session.scalar(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.version_id == result.target_version_id
            )
        )
        assert new_snapshot is not None
        assert new_snapshot.is_current is True
        assert new_snapshot.snapshot_data["duration"] == "2 years"

    def test_new_snapshot_has_restore_provenance(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        scholarship.duration = "3 years"
        session.commit()

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        new_snapshot = session.scalar(
            select(ScholarshipSnapshot).where(
                ScholarshipSnapshot.version_id == result.target_version_id
            )
        )
        assert new_snapshot.provenance is not None
        assert "restore_operation_id" in new_snapshot.provenance
        assert new_snapshot.provenance["source_version_id"] == original_version_id


class TestNoChangesWhenAlreadyAtSnapshot:
    def test_restore_noop_when_already_at_snapshot_state(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        original_version_id = r1.version_id

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id=original_version_id,
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.outcome == RestoreOutcome.NOOP


class TestSnapshotNotFound:
    def test_restore_with_nonexistent_snapshot(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        result = restore_snapshot(
            session,
            scholarship_id=1,
            source_version_id="nonexistent_12345678",
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.outcome == RestoreOutcome.REJECTED
        assert result.block_reason == RestoreBlockReason.SNAPSHOT_NOT_FOUND


class TestScholarshipNotFound:
    def test_restore_with_nonexistent_scholarship(self, session):
        result = restore_snapshot(
            session,
            scholarship_id=999,
            source_version_id="some_version_123456",
            operator="test_operator",
            reason="Testing restore",
        )

        assert result.success is False
        assert result.block_reason == RestoreBlockReason.SNAPSHOT_NOT_FOUND


class TestValidateSnapshotIntegrity:
    def test_valid_snapshot_passes(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        r1 = _create_snapshot_with_state(session, scholarship, ["duration"])
        snapshot = session.get(ScholarshipSnapshot, r1.snapshot_id)

        is_valid, error = validate_snapshot_integrity(session, snapshot)
        assert is_valid is True
        assert error is None

    def test_missing_snapshot_data_fails(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        r1 = _create_snapshot_with_state(session, scholarship, ["duration"])
        snapshot = session.get(ScholarshipSnapshot, r1.snapshot_id)
        snapshot.snapshot_data = {}
        session.commit()

        is_valid, error = validate_snapshot_integrity(session, snapshot)
        assert is_valid is False
        assert "snapshot_data" in error

    def test_current_with_valid_to_fails(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        r1 = _create_snapshot_with_state(session, scholarship, ["duration"])
        snapshot = session.get(ScholarshipSnapshot, r1.snapshot_id)
        snapshot.valid_to = datetime.now(timezone.utc)
        session.commit()

        is_valid, error = validate_snapshot_integrity(session, snapshot)
        assert is_valid is False
        assert "valid_to" in error


class TestVerifyVersionChain:
    def test_valid_chain_passes(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t2)

        is_valid, error = verify_version_chain(session, 1)
        assert is_valid is True
        assert error is None

    def test_empty_chain_passes(self, session):
        is_valid, error = verify_version_chain(session, 1)
        assert is_valid is True
        assert error is None

    def test_multiple_current_fails(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, duration="2 years")

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        r1 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t1)
        r2 = _create_snapshot_with_state(session, scholarship, ["duration"], timestamp=t2)

        s1 = session.get(ScholarshipSnapshot, r1.snapshot_id)
        s1.is_current = True
        s2 = session.get(ScholarshipSnapshot, r2.snapshot_id)
        s2.is_current = True
        session.commit()

        is_valid, error = verify_version_chain(session, 1)
        assert is_valid is False
        assert "multiple current" in error
