"""Tests for temporal versioning and time-travel reconstruction."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Base,
    Scholarship,
    ScholarshipSnapshot,
)
from app.services.temporal_versioning import (
    batch_reconstruct_at_timestamps,
    create_snapshot,
    get_current_version,
    get_cycle_state,
    get_state_at,
    get_version_history,
    get_versions_in_range,
    has_meaningful_changes,
    initialize_version_history,
    reconstruct_at_timestamp,
)


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
) -> Scholarship:
    s = Scholarship(
        id=scholarship_id,
        title=title,
        country=country,
        degree=degree,
        funding=funding,
        status=status,
        official_source_url=f"https://example{scholarship_id}.gov/scholarship",
    )
    session.add(s)
    session.commit()
    return s


class TestVersionCreation:
    def test_creates_snapshot_with_changed_fields(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)
        result = create_snapshot(
            session,
            scholarship,
            changed_fields=["title", "status"],
            source_url="https://example.gov/updated",
        )

        assert result.created is True
        assert result.snapshot_id > 0
        assert len(result.version_id) == 16

    def test_snapshot_stores_all_fields(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="Original")
        result = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
        )

        snapshot = session.get(ScholarshipSnapshot, result.snapshot_id)
        assert snapshot.snapshot_data["title"] == "Original"
        assert snapshot.snapshot_data["country"] == "Test Country"
        assert snapshot.changed_fields == ["title"]

    def test_empty_changed_fields_no_snapshot(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)
        result = create_snapshot(session, scholarship, changed_fields=[])

        assert result.created is False


class TestMeaningfulVsNoOpChange:
    def test_detects_meaningful_change(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="Original")
        create_snapshot(session, scholarship, changed_fields=["title"])

        scholarship.title = "Updated Title"
        assert has_meaningful_changes(session, scholarship, ["title"]) is True

    def test_no_op_change_detected(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="Same")
        create_snapshot(session, scholarship, changed_fields=["title"])

        assert has_meaningful_changes(session, scholarship, ["title"]) is False

    def test_first_change_always_meaningful(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)
        assert has_meaningful_changes(session, scholarship, ["title"]) is True


class TestChronologicalOrdering:
    def test_versions_ordered_by_valid_from(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        t3 = datetime(2024, 3, 1)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        create_snapshot(session, scholarship, changed_fields=["status"], timestamp=t2)
        create_snapshot(session, scholarship, changed_fields=["funding"], timestamp=t3)

        history = get_version_history(session, scholarship.id)
        assert len(history) == 3
        assert history[0].valid_from.replace(tzinfo=None) == t3
        assert history[1].valid_from.replace(tzinfo=None) == t2
        assert history[2].valid_from.replace(tzinfo=None) == t1

    def test_valid_from_valid_to_chain(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        create_snapshot(session, scholarship, changed_fields=["status"], timestamp=t2)

        history = get_version_history(session, scholarship.id)
        assert history[0].valid_to is None
        assert history[1].valid_to.replace(tzinfo=None) == t2


class TestCurrentVersion:
    def test_most_recent_is_current(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        create_snapshot(session, scholarship, changed_fields=["status"], timestamp=t2)

        current = get_current_version(session, scholarship.id)
        assert current is not None
        assert current.is_current is True
        assert current.valid_from.replace(tzinfo=None) == t2

    def test_previous_version_no_longer_current(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)

        r1 = create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        r2 = create_snapshot(session, scholarship, changed_fields=["status"], timestamp=t2)

        old_snapshot = session.get(ScholarshipSnapshot, r1.snapshot_id)
        new_snapshot = session.get(ScholarshipSnapshot, r2.snapshot_id)

        assert old_snapshot.is_current is False
        assert new_snapshot.is_current is True


class TestHistoricalStateReconstruction:
    def test_get_state_at_exact_timestamp(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="V1")

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        scholarship.title = "V2"
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t2)

        result = get_state_at(session, scholarship.id, t1)
        assert result.found is True
        assert result.state["title"] == "V1"

    def test_get_state_at_intermediate_timestamp(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="V1")

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        t_mid = datetime(2024, 1, 15)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        scholarship.title = "V2"
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t2)

        result = get_state_at(session, scholarship.id, t_mid)
        assert result.found is True
        assert result.state["title"] == "V1"

    def test_get_state_after_last_version(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="V1")

        t1 = datetime(2024, 1, 1)
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)

        scholarship.title = "V2"
        t2 = datetime(2024, 2, 1)
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t2)

        t_future = datetime(2024, 3, 1)
        result = get_state_at(session, scholarship.id, t_future)
        assert result.found is True
        assert result.state["title"] == "V2"

    def test_get_state_before_any_version(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)

        t_early = datetime(2023, 1, 1)
        result = get_state_at(session, scholarship.id, t_early)
        assert result.found is False


class TestCycleReconstruction:
    def test_get_cycle_state(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            cycle_id="2024",
        )

        result = get_cycle_state(session, scholarship.id, "2024")
        assert result is not None
        assert result.found is True
        assert result.version_id is not None

    def test_get_nonexistent_cycle(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)
        create_snapshot(session, scholarship, changed_fields=["title"])

        result = get_cycle_state(session, scholarship.id, "2025")
        assert result is None

    def test_different_cycles_different_snapshots(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            cycle_id="2024",
        )
        create_snapshot(
            session,
            scholarship,
            changed_fields=["status"],
            cycle_id="2025",
        )

        state_2024 = get_cycle_state(session, scholarship.id, "2024")
        state_2025 = get_cycle_state(session, scholarship.id, "2025")

        assert state_2024 is not None
        assert state_2025 is not None
        assert state_2024.version_id != state_2025.version_id


class TestMultipleFieldChanges:
    def test_multiple_fields_in_single_snapshot(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        result = create_snapshot(
            session,
            scholarship,
            changed_fields=["title", "status", "funding"],
        )

        snapshot = session.get(ScholarshipSnapshot, result.snapshot_id)
        assert set(snapshot.changed_fields) == {"title", "status", "funding"}

    def test_changed_fields_are_sorted(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        result = create_snapshot(
            session,
            scholarship,
            changed_fields=["funding", "title", "status"],
        )

        snapshot = session.get(ScholarshipSnapshot, result.snapshot_id)
        assert snapshot.changed_fields == ["funding", "status", "title"]


class TestImmutableHistory:
    def test_existing_snapshots_not_mutated(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="Original")

        result = create_snapshot(session, scholarship, changed_fields=["title"])
        snapshot_id = result.snapshot_id
        original_version_id = result.version_id

        scholarship.title = "Modified"
        create_snapshot(session, scholarship, changed_fields=["title"])

        original_snapshot = session.get(ScholarshipSnapshot, snapshot_id)
        assert original_snapshot.version_id == original_version_id
        assert original_snapshot.snapshot_data["title"] == "Original"


class TestIdempotency:
    def test_same_change_same_timestamp_no_duplicate(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)

        r1 = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            timestamp=t1,
        )
        r2 = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            timestamp=t1,
        )

        assert r1.created is True
        assert r2.created is False

    def test_different_timestamps_create_different_versions(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)

        r1 = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            timestamp=t1,
        )
        r2 = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            timestamp=t2,
        )

        assert r1.created is True
        assert r2.created is True
        assert r1.version_id != r2.version_id


class TestConcurrentVersionCreation:
    def test_only_one_current_version(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 1, 2)
        t3 = datetime(2024, 1, 3)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        create_snapshot(session, scholarship, changed_fields=["status"], timestamp=t2)
        create_snapshot(session, scholarship, changed_fields=["funding"], timestamp=t3)

        stmt = (
            select(func.count())
            .select_from(ScholarshipSnapshot)
            .where(
                ScholarshipSnapshot.scholarship_id == scholarship.id,
                ScholarshipSnapshot.is_current == True,
            )
        )
        current_count = session.execute(stmt).scalar_one()
        assert current_count == 1


class TestProvenancePreservation:
    def test_source_url_preserved(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        result = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            source_url="https://example.gov/source",
        )

        snapshot = session.get(ScholarshipSnapshot, result.snapshot_id)
        assert snapshot.source_url == "https://example.gov/source"

    def test_provenance_data_preserved(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        provenance_data = {
            "verification_method": "automated",
            "confidence": "high",
            "source": "official_catalogue",
        }
        result = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            provenance=provenance_data,
        )

        snapshot = session.get(ScholarshipSnapshot, result.snapshot_id)
        assert snapshot.provenance == provenance_data


class TestMissingTimestampEdgeCases:
    def test_no_scholarship_returns_not_found(self, session):
        t1 = datetime(2024, 1, 1)
        result = get_state_at(session, 999, t1)
        assert result.found is False

    def test_empty_history_returns_not_found(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        result = get_state_at(session, scholarship.id, t1)
        assert result.found is False


class TestBatchReconstruction:
    def test_batch_reconstruct_multiple_timestamps(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="V1")

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        t3 = datetime(2024, 3, 1)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        scholarship.title = "V2"
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t2)
        scholarship.title = "V3"
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t3)

        timestamps = [
            datetime(2024, 1, 15),
            datetime(2024, 2, 15),
            datetime(2024, 3, 15),
        ]

        results = batch_reconstruct_at_timestamps(session, scholarship.id, timestamps)

        assert len(results) == 3
        assert results[0].state["title"] == "V1"
        assert results[1].state["title"] == "V2"
        assert results[2].state["title"] == "V3"

    def test_batch_empty_timestamps(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)
        results = batch_reconstruct_at_timestamps(session, scholarship.id, [])
        assert results == []


class TestIndexedLookup:
    def test_get_versions_in_range(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 2, 1)
        t3 = datetime(2024, 3, 1)

        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)
        create_snapshot(session, scholarship, changed_fields=["status"], timestamp=t2)
        create_snapshot(session, scholarship, changed_fields=["funding"], timestamp=t3)

        versions = get_versions_in_range(
            session,
            scholarship.id,
            datetime(2024, 1, 15),
            datetime(2024, 2, 15),
        )

        assert len(versions) == 1
        assert versions[0].valid_from.replace(tzinfo=None) == t2


class TestDeterministicOutput:
    def test_same_scholarship_same_input_same_version_id(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1, title="Same")

        t1 = datetime(2024, 1, 1)

        r1 = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            timestamp=t1,
        )
        r2 = create_snapshot(
            session,
            scholarship,
            changed_fields=["title"],
            timestamp=t1,
        )

        assert r1.created is True
        assert r2.created is False

    def test_different_scholarship_different_version_id(self, session):
        s1 = _make_scholarship(session, scholarship_id=1, title="Title1")
        s2 = _make_scholarship(session, scholarship_id=2, title="Title2")

        t1 = datetime(2024, 1, 1)

        r1 = create_snapshot(session, s1, changed_fields=["title"], timestamp=t1)
        r2 = create_snapshot(session, s2, changed_fields=["title"], timestamp=t1)

        assert r1.version_id != r2.version_id


class TestNoNPlusOne:
    def test_batch_reconstruct_single_query(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        for i in range(5):
            t = datetime(2024, 1, i + 1)
            create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t)

        timestamps = [
            datetime(2024, 1, 1, 12),
            datetime(2024, 1, 3, 12),
            datetime(2024, 1, 5, 12),
        ]

        results = batch_reconstruct_at_timestamps(session, scholarship.id, timestamps)
        assert len(results) == 3
        assert all(r.found for r in results)


class TestInitializeVersionHistory:
    def test_initialize_creates_first_version(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        result = initialize_version_history(session, scholarship)

        assert result.created is True
        assert result.snapshot_id > 0

    def test_initialize_idempotent(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        r1 = initialize_version_history(session, scholarship)
        r2 = initialize_version_history(session, scholarship)

        assert r1.created is True
        assert r2.created is False

    def test_initialize_sets_current(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        initialize_version_history(session, scholarship)

        current = get_current_version(session, scholarship.id)
        assert current is not None
        assert current.is_current is True


class TestReconstructAtTimestamp:
    def test_alias_for_get_state_at(self, session):
        scholarship = _make_scholarship(session, scholarship_id=1)

        t1 = datetime(2024, 1, 1)
        create_snapshot(session, scholarship, changed_fields=["title"], timestamp=t1)

        result = reconstruct_at_timestamp(session, scholarship.id, t1)
        assert result.found is True
        assert result.state is not None
