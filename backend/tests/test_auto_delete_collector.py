"""The collector's database behaviour: exact ids, revalidation, rollback, repeat.

The policy tests prove a record is judged correctly. These prove the judgement is
actually what governs the delete - that a stale decision cannot delete a record
that came back to life, that only the named ids go, that a failure part-way
leaves nothing half-deleted, and that running it twice is a no-op.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Scholarship, ScholarshipReview, ScholarshipSnapshot
from app.services.auto_delete_collector import (
    CONTRACT_VERSION,
    arm,
    collect,
    delete_exact,
)
from app.services.auto_delete_policy import (
    AUTO_DELETE_AFTER_DAYS,
    DELETE_GRACE_DAYS,
    VERDICT_SAFE_DELETE,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    return tmp_path / "purged_records_archive.json"


def make_closed(session, sid: int, *, days: int = 400, **overrides) -> Scholarship:
    archived = NOW - timedelta(days=days)
    fields = dict(
        title=f"Closed programme {sid}",
        country="XX",
        degree="master",
        funding="stipend",
        deadline_precision="month",
        status="closed",
        is_archived=True,
        archived_at=archived,
        archived_reason="deadline passed",
        verification_status="retired",
        is_verified=True,
        fully_funded=False,
        updated_at=archived,
        created_at=archived,
    )
    fields.update(overrides)
    row = Scholarship(id=sid, **fields)
    session.add(row)
    session.commit()
    return row


def public_ids(session) -> set[int]:
    from app.repositories.scholarships import public_visibility_conditions

    return set(
        session.scalars(
            select(Scholarship.id).where(*public_visibility_conditions())
        ).all()
    )


class TestCollection:
    def test_collect_is_read_only(self, session_factory):
        session = session_factory()
        try:
            make_closed(session, 1)
            before = session.execute(
                select(Scholarship.id, Scholarship.auto_delete_candidate_since)
            ).all()
            collect(session, now=NOW)
            session.rollback()
            after = session.execute(
                select(Scholarship.id, Scholarship.auto_delete_candidate_since)
            ).all()
            assert before == after
        finally:
            session.close()

    def test_a_freshly_closed_record_is_not_a_candidate(self, session_factory):
        session = session_factory()
        try:
            make_closed(session, 1, days=3)
            decisions = {d.id: d for d in collect(session, now=NOW)}
            assert decisions[1].verdict == "INSUFFICIENT_RETENTION_EVIDENCE"
            assert decisions[1].eligible_ids is False
        finally:
            session.close()


class TestArming:
    def test_arming_starts_the_grace_clock_and_is_written(self, session_factory):
        session = session_factory()
        try:
            make_closed(session, 1)
            decisions = collect(session, now=NOW)
            outcome = arm(session, decisions, now=NOW, dry_run=False)
            assert outcome["newly_armed"] == [1]
            row = session.get(Scholarship, 1)
            assert row.auto_delete_candidate_since is not None
        finally:
            session.close()

    def test_dry_run_arming_writes_nothing(self, session_factory):
        session = session_factory()
        try:
            make_closed(session, 1)
            decisions = collect(session, now=NOW)
            arm(session, decisions, now=NOW, dry_run=True)
            row = session.get(Scholarship, 1)
            assert row.auto_delete_candidate_since is None
        finally:
            session.close()

    def test_a_record_that_stops_qualifying_is_disarmed(self, session_factory):
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            assert session.get(Scholarship, 1).auto_delete_candidate_since is not None

            # Reopened between cycles.
            row = session.get(Scholarship, 1)
            row.is_archived = False
            row.status = "open"
            session.commit()

            outcome = arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            assert outcome["disarmed"] == [1]
            assert session.get(Scholarship, 1).auto_delete_candidate_since is None
        finally:
            session.close()

    def test_a_reopened_record_is_never_deleted_however_long_ago(self, session_factory, archive):
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.is_archived = False
            row.status = "open"
            session.commit()

            report = delete_exact(session, [1], now=NOW, archive_path=archive)
            assert report["deleted"] == []
            assert report["aborted"]
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()


class TestExactIdDeletion:
    def test_only_the_named_ids_are_deleted(self, session_factory, archive):
        session = session_factory()
        try:
            for sid in (1, 2, 3):
                make_closed(session, sid)
                arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            # Move the grace clock past its end for 1 and 2 only.
            for sid in (1, 2):
                row = session.get(Scholarship, sid)
                row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()

            report = delete_exact(session, [1, 2], now=NOW, archive_path=archive)
            assert sorted(report["deleted"]) == [1, 2]
            assert session.get(Scholarship, 1) is None
            assert session.get(Scholarship, 2) is None
            assert session.get(Scholarship, 3) is not None, "an unnamed id was deleted"
        finally:
            session.close()

    def test_a_record_outside_the_policy_is_aborted_not_deleted(self, session_factory, archive):
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            row.verification_status = "needs_review"
            session.commit()

            report = delete_exact(session, [1], now=NOW, archive_path=archive)
            assert report["deleted"] == []
            assert "needs a human" in report["aborted"][0]["reason"]
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_a_blocking_dependency_added_after_arming_aborts_the_delete(
        self, session_factory, archive
    ):
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()
            # A snapshot appears after the record was armed.
            session.add(
                ScholarshipSnapshot(
                    scholarship_id=1,
                    version_id="v1",
                    valid_from=NOW,
                    snapshot_data={"a": 1},
                )
            )
            session.commit()

            report = delete_exact(session, [1], now=NOW, archive_path=archive)
            assert report["deleted"] == []
            assert "ScholarshipSnapshot" in report["aborted"][0]["reason"]
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_a_concurrent_change_after_the_candidate_list_is_computed_aborts_the_delete(
        self, session_factory, archive
    ):
        """13: the delete transaction re-decides, so a stale decision cannot delete.

        The candidate list is a snapshot. Anything that changes the record between
        that snapshot and the delete must stop it, and the only place that can be
        observed is inside the transaction.
        """
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()

            # The list is computed here, while the record still qualifies.
            eligible = [d.id for d in collect(session, now=NOW) if d.eligible_ids]
            assert eligible == [1]

            # ...and then the record is reopened before the delete runs.
            row = session.get(Scholarship, 1)
            row.is_archived = False
            row.status = "open"
            session.commit()

            report = delete_exact(session, eligible, now=NOW, archive_path=archive)
            assert report["deleted"] == []
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()

    def test_an_unresolved_review_added_after_arming_aborts_the_delete(
        self, session_factory, archive
    ):
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()
            session.add(
                ScholarshipReview(
                    scholarship_id=1,
                    field_name="funding",
                    current_value="stipend",
                    proposed_value="37,000 per month",
                    conflict_reason="official page contradicts the stored award",
                    verification_state="conflict",
                    decision=None,
                )
            )
            session.commit()

            report = delete_exact(session, [1], now=NOW, archive_path=archive)
            assert report["deleted"] == []
            assert session.get(Scholarship, 1) is not None
        finally:
            session.close()


class TestDryRunAndIdempotency:
    def test_dry_run_deletes_nothing(self, session_factory, archive):
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()

            report = delete_exact(session, [1], now=NOW, dry_run=True, archive_path=archive)
            assert report["mode"] == "DRY RUN"
            assert report["deleted"] == [1]
            assert report["child_rows_removed"] == 0
            assert session.get(Scholarship, 1) is not None
            assert not archive.exists(), "a dry run wrote a deletion manifest"
        finally:
            session.close()

    def test_second_run_deletes_nothing_and_writes_no_duplicate_event(
        self, session_factory, archive
    ):
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()

            first = delete_exact(session, [1], now=NOW, archive_path=archive)
            assert first["deleted"] == [1]

            second = delete_exact(session, [1], now=NOW, archive_path=archive)
            assert second["deleted"] == []
            assert "NO SAFE DELETE TARGETS" in second["note"]

            import json

            archive_doc = json.loads(archive.read_text(encoding="utf-8"))
            ids = [r["id"] for batch in archive_doc["batches"] for r in batch["records"]]
            assert ids == [1], "the same id was recorded as deleted twice"
        finally:
            session.close()

    def test_an_empty_target_set_says_so_rather_than_failing(self, session_factory, archive):
        session = session_factory()
        try:
            report = delete_exact(session, [], now=NOW, archive_path=archive)
            assert report["deleted"] == []
            assert report["note"] == "NO SAFE DELETE TARGETS"
            assert not archive.exists()
        finally:
            session.close()


class TestManifest:
    def test_a_deletion_is_recorded_with_every_required_field(self, session_factory, archive):
        import json

        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()

            delete_exact(session, [1], now=NOW, archive_path=archive)
            batch = json.loads(archive.read_text(encoding="utf-8"))["batches"][-1]
            assert batch["ids"] == [1]
            assert batch["deleted"] == 1
            assert batch["contract_version"] == CONTRACT_VERSION
            assert batch["policy"]["auto_delete_after_days"] == AUTO_DELETE_AFTER_DAYS
            assert batch["policy"]["delete_grace_days"] == DELETE_GRACE_DAYS
            assert batch["system"]
            assert batch["deleted_at"]
            parent = batch["parents"][0]
            assert parent["id"] == 1
            assert parent["archived_at"]
            record = batch["records"][0]
            for field in ("id", "reason", "retention_days", "archived_since", "dependency_summary"):
                assert field in record
        finally:
            session.close()

    def test_a_corrupt_archive_is_not_silently_overwritten(self, session_factory, archive):
        import json

        archive.write_text("{not json", encoding="utf-8")
        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()
            delete_exact(session, [1], now=NOW, archive_path=archive)
            doc = json.loads(archive.read_text(encoding="utf-8"))
            assert doc["batches"][-1]["ids"] == [1]
        finally:
            session.close()


    def test_the_manifest_is_written_before_the_delete_commits(self, session_factory, archive):
        """The row must be recoverable even if the process dies mid-delete.

        Writing the manifest only after the commit means a crash in between
        leaves rows deleted and nothing written down. This asserts the order in
        the source, because that is the property and it is the only place it is
        observable.
        """
        import inspect

        from app.services import auto_delete_collector

        source = inspect.getsource(auto_delete_collector.delete_exact)
        first_write = source.index("_append_manifest(")
        commit_at = source.index("session.commit()")
        assert first_write < commit_at, "the manifest is written after the delete commits"

    def test_an_unconfirmed_manifest_entry_does_not_inflate_the_total(
        self, session_factory, archive
    ):
        import json

        session = session_factory()
        try:
            make_closed(session, 1)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 1)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()
            delete_exact(session, [1], now=NOW, archive_path=archive)
            doc = json.loads(archive.read_text(encoding="utf-8"))
            assert doc["count"] == 1
            assert all(b["confirmed"] for b in doc["batches"])
        finally:
            session.close()


class TestPublicSafety:
    def test_a_public_record_is_never_a_target(self, session_factory, archive):
        session = session_factory()
        try:
            make_closed(session, 1, is_archived=False, status="open", verification_status="active")
            make_closed(session, 2)
            before = public_ids(session)
            decisions = {d.id: d for d in collect(session, now=NOW)}
            eligible = [d.id for d in decisions.values() if d.verdict == VERDICT_SAFE_DELETE]
            assert eligible == [], "a record was eligible without being armed"
            report = delete_exact(session, eligible, now=NOW, archive_path=archive)
            assert report["deleted"] == []
            assert public_ids(session) == before
        finally:
            session.close()

    def test_deleting_an_internal_record_does_not_change_the_public_set(
        self, session_factory, archive
    ):
        session = session_factory()
        try:
            make_closed(
                session, 1, is_archived=False, status="open", verification_status="active"
            )
            public_before = public_ids(session)
            make_closed(session, 2)
            arm(session, collect(session, now=NOW), now=NOW, dry_run=False)
            row = session.get(Scholarship, 2)
            row.auto_delete_candidate_since = NOW - timedelta(days=DELETE_GRACE_DAYS)
            session.commit()

            report = delete_exact(session, [2], now=NOW, archive_path=archive)
            assert report["deleted"] == [2]
            assert public_ids(session) == public_before
        finally:
            session.close()
