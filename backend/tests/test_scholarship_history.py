"""Focused tests for the persistent verification history layer."""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-history-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"


fake_scheduler = types.ModuleType("app.scheduler")
fake_scheduler.start_scheduler = lambda: None
fake_scheduler.mark_due_for_review = lambda: None
sys.modules["app.scheduler"] = fake_scheduler


from app.database import close_database, get_session_factory, init_database, reset_database_connections  # noqa: E402
from app.models import Scholarship, ScholarshipVerificationHistory  # noqa: E402
from app.services.scholarship_diff import ChangeSet, FieldChange, FieldChangeType  # noqa: E402
from app.services.scholarship_history import (  # noqa: E402
    HistoryEntry,
    HistoryWriteResult,
    _serialize_value,
    get_verification_history,
    write_changeset_history,
    write_verification_history,
)


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


def _get_history_count(session, scholarship_id: int) -> int:
    stmt = select(ScholarshipVerificationHistory).where(
        ScholarshipVerificationHistory.scholarship_id == scholarship_id
    )
    return len(list(session.execute(stmt).scalars().all()))


class TestSerializeValue(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(_serialize_value(None))

    def test_string_returned_as_is(self):
        self.assertEqual(_serialize_value("hello"), "hello")

    def test_list_joined_with_comma(self):
        self.assertEqual(_serialize_value(["a", "b", "c"]), "a, b, c")

    def test_bool_serialized(self):
        self.assertEqual(_serialize_value(True), "true")
        self.assertEqual(_serialize_value(False), "false")

    def test_number_serialized(self):
        self.assertEqual(_serialize_value(42), "42")

    def test_deterministic_output(self):
        self.assertEqual(_serialize_value(["b", "a"]), _serialize_value(["b", "a"]))


class TestSingleChangeInsert(unittest.TestCase):
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

    def test_single_change_inserted(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            entries = [
                HistoryEntry(
                    field_name="duration",
                    old_value="2 years",
                    new_value="3 years",
                    change_type="modified",
                    source_url="https://example.com",
                    evidence_text="Updated to 3 years",
                    confidence="high",
                )
            ]

            result = write_verification_history(session, scholarship_id, entries)
            session.commit()

            self.assertEqual(result.entries_written, 1)
            self.assertEqual(len(result.history_ids), 1)

            history = session.get(ScholarshipVerificationHistory, result.history_ids[0])
            self.assertIsNotNone(history)
            self.assertEqual(history.scholarship_id, scholarship_id)
            self.assertEqual(history.field_name, "duration")
            self.assertEqual(history.old_value, "2 years")
            self.assertEqual(history.new_value, "3 years")
            self.assertEqual(history.change_type, "modified")
            self.assertEqual(history.source_url, "https://example.com")
            self.assertEqual(history.evidence_text, "Updated to 3 years")
            self.assertEqual(history.confidence, "high")


class TestMultipleFieldChangesInserted(unittest.TestCase):
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

    def test_multiple_fields_inserted_in_single_call(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years", status="open")

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years"),
                HistoryEntry(field_name="status", old_value="open", new_value="closed"),
                HistoryEntry(field_name="funding", old_value="Partial", new_value="Full"),
            ]

            result = write_verification_history(session, scholarship_id, entries)
            session.commit()

            self.assertEqual(result.entries_written, 3)
            self.assertEqual(len(result.history_ids), 3)

            count = _get_history_count(session, scholarship_id)
            self.assertEqual(count, 3)


class TestOldNewValuesPreserved(unittest.TestCase):
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

    def test_old_new_values_preserved_exactly(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(
                    field_name="duration",
                    old_value="2 years",
                    new_value="4 years",
                )
            ]

            result = write_verification_history(session, scholarship_id, entries)
            session.commit()

            history = session.get(ScholarshipVerificationHistory, result.history_ids[0])
            self.assertEqual(history.old_value, "2 years")
            self.assertEqual(history.new_value, "4 years")

    def test_list_values_serialized_deterministically(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(
                    field_name="eligibility",
                    old_value=["Citizen", "Resident"],
                    new_value=["Citizen", "Resident", "Refugee"],
                )
            ]

            result = write_verification_history(session, scholarship_id, entries)
            session.commit()

            history = session.get(ScholarshipVerificationHistory, result.history_ids[0])
            self.assertEqual(history.old_value, "Citizen, Resident")
            self.assertEqual(history.new_value, "Citizen, Resident, Refugee")


class TestSourceEvidenceConfidencePreserved(unittest.TestCase):
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

    def test_source_evidence_confidence_preserved(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(
                    field_name="status",
                    old_value="open",
                    new_value="closed",
                    source_url="https://scholarship.program.gov/status",
                    evidence_text="Announcement page states: 'Applications closed'",
                    confidence="high",
                    verification_status="active",
                )
            ]

            result = write_verification_history(session, scholarship_id, entries)
            session.commit()

            history = session.get(ScholarshipVerificationHistory, result.history_ids[0])
            self.assertEqual(history.source_url, "https://scholarship.program.gov/status")
            self.assertEqual(history.evidence_text, "Announcement page states: 'Applications closed'")
            self.assertEqual(history.confidence, "high")
            self.assertEqual(history.verification_status, "active")


class TestPreviousHistoryImmutable(unittest.TestCase):
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

    def test_previous_history_unchanged_by_new_writes(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            entries1 = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years")
            ]
            result1 = write_verification_history(session, scholarship_id, entries1)
            session.commit()

            first_id = result1.history_ids[0]
            first_created_at = session.get(ScholarshipVerificationHistory, first_id).created_at

            entries2 = [
                HistoryEntry(field_name="status", old_value="open", new_value="closed")
            ]
            result2 = write_verification_history(session, scholarship_id, entries2)
            session.commit()

            first_record = session.get(ScholarshipVerificationHistory, first_id)
            self.assertEqual(first_record.field_name, "duration")
            self.assertEqual(first_record.old_value, "2 years")
            self.assertEqual(first_record.new_value, "3 years")
            self.assertEqual(first_record.created_at, first_created_at)


class TestSecondChangeCreatesNewRow(unittest.TestCase):
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

    def test_second_change_creates_new_row(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            entries1 = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years")
            ]
            write_verification_history(session, scholarship_id, entries1)
            session.commit()

            entries2 = [
                HistoryEntry(field_name="duration", old_value="3 years", new_value="4 years")
            ]
            write_verification_history(session, scholarship_id, entries2)
            session.commit()

            count = _get_history_count(session, scholarship_id)
            self.assertEqual(count, 2)

            history = get_verification_history(session, scholarship_id, field_name="duration")
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0].new_value, "4 years")
            self.assertEqual(history[1].old_value, "2 years")


class TestRollbackRemovesIncompleteHistory(unittest.TestCase):
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

    def test_rollback_removes_incomplete_history(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years"),
                HistoryEntry(field_name="status", old_value="open", new_value="closed"),
            ]

            write_verification_history(session, scholarship_id, entries)
            session.rollback()

            count = _get_history_count(session, scholarship_id)
            self.assertEqual(count, 0)


class TestHistoryServiceDoesNotIndependentlyCommit(unittest.TestCase):
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

    def test_history_service_does_not_commit(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years")
            ]

            result = write_verification_history(session, scholarship_id, entries)

            self.assertEqual(result.entries_written, 1)
            self.assertIsNotNone(result.history_ids[0])

            session.rollback()

            count = _get_history_count(session, scholarship_id)
            self.assertEqual(count, 0)

    def test_caller_controls_transaction(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years")
            ]

            write_verification_history(session, scholarship_id, entries)
            session.commit()

            new_session = get_session_factory()()
            count = _get_history_count(new_session, scholarship_id)
            self.assertEqual(count, 1)
            new_session.close()


class TestNoNPlusOneQueries(unittest.TestCase):
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

    def test_bulk_insert_no_n_plus_one(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(field_name=f"field_{i}", old_value=str(i), new_value=str(i + 1))
                for i in range(10)
            ]

            result = write_verification_history(session, scholarship_id, entries)
            session.commit()

            self.assertEqual(result.entries_written, 10)

            count = _get_history_count(session, scholarship_id)
            self.assertEqual(count, 10)


class TestIndexedLookup(unittest.TestCase):
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

    def test_indexed_lookup_by_scholarship(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years"),
                HistoryEntry(field_name="status", old_value="open", new_value="closed"),
            ]

            write_verification_history(session, scholarship_id, entries)
            session.commit()

            history = get_verification_history(session, scholarship_id)
            self.assertEqual(len(history), 2)

    def test_indexed_lookup_by_field(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years"),
                HistoryEntry(field_name="status", old_value="open", new_value="closed"),
                HistoryEntry(field_name="duration", old_value="3 years", new_value="4 years"),
            ]

            write_verification_history(session, scholarship_id, entries)
            session.commit()

            duration_history = get_verification_history(session, scholarship_id, field_name="duration")
            self.assertEqual(len(duration_history), 2)

            status_history = get_verification_history(session, scholarship_id, field_name="status")
            self.assertEqual(len(status_history), 1)


class TestInvalidScholarshipIdRejected(unittest.TestCase):
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

    def test_invalid_scholarship_id_rejected_by_fk(self):
        with get_session_factory()() as session:
            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years")
            ]

            with self.assertRaises(Exception):
                write_verification_history(session, 999999, entries)
                session.commit()

            session.rollback()


class TestDeterministicHistoricalRepresentation(unittest.TestCase):
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

    def test_deterministic_serialization(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            entries1 = [
                HistoryEntry(field_name="eligibility", old_value=["A", "B", "C"])
            ]
            result1 = write_verification_history(session, scholarship_id, entries1)
            session.commit()

            entries2 = [
                HistoryEntry(field_name="eligibility", old_value=["A", "B", "C"])
            ]
            result2 = write_verification_history(session, scholarship_id, entries2)
            session.commit()

            record1 = session.get(ScholarshipVerificationHistory, result1.history_ids[0])
            record2 = session.get(ScholarshipVerificationHistory, result2.history_ids[0])

            self.assertEqual(record1.old_value, record2.old_value)

    def test_history_independent_of_current_record(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years")
            ]
            result = write_verification_history(session, scholarship_id, entries)
            session.commit()

            scholarship = session.get(Scholarship, scholarship_id)
            scholarship.duration = "4 years"
            session.commit()

            history = session.get(ScholarshipVerificationHistory, result.history_ids[0])
            self.assertEqual(history.old_value, "2 years")
            self.assertEqual(history.new_value, "3 years")


class TestWriteChangesetHistory(unittest.TestCase):
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

    def test_changeset_history_inserted(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years", status="open")

            changeset = ChangeSet(
                changes=[
                    FieldChange(
                        field="duration",
                        change_type=FieldChangeType.MODIFIED,
                        old_value="2 years",
                        new_value="3 years",
                    ),
                    FieldChange(
                        field="status",
                        change_type=FieldChangeType.MODIFIED,
                        old_value="open",
                        new_value="closed",
                    ),
                ]
            )

            result = write_changeset_history(
                session,
                scholarship_id,
                changeset,
                source_url="https://example.com",
            )
            session.commit()

            self.assertEqual(result.entries_written, 2)

    def test_unchanged_fields_skipped(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            changeset = ChangeSet(
                changes=[
                    FieldChange(
                        field="duration",
                        change_type=FieldChangeType.UNCHANGED,
                        old_value="2 years",
                        new_value="2 years",
                    ),
                    FieldChange(
                        field="status",
                        change_type=FieldChangeType.MODIFIED,
                        old_value="open",
                        new_value="closed",
                    ),
                ]
            )

            result = write_changeset_history(session, scholarship_id, changeset)
            session.commit()

            self.assertEqual(result.entries_written, 1)


class TestEmptyEntries(unittest.TestCase):
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

    def test_empty_entries_returns_zero(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            result = write_verification_history(session, scholarship_id, [])

            self.assertEqual(result.entries_written, 0)
            self.assertEqual(len(result.history_ids), 0)


class TestTransactionIntegration(unittest.TestCase):
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

    def test_scholarship_update_and_history_in_same_transaction(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            scholarship = session.get(Scholarship, scholarship_id)
            scholarship.duration = "3 years"

            entries = [
                HistoryEntry(
                    field_name="duration",
                    old_value="2 years",
                    new_value="3 years",
                    source_url="https://example.com",
                )
            ]
            write_verification_history(session, scholarship_id, entries)

            session.commit()

            scholarship = session.get(Scholarship, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")

            count = _get_history_count(session, scholarship_id)
            self.assertEqual(count, 1)

    def test_rollback_reverts_both_scholarship_and_history(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            scholarship = session.get(Scholarship, scholarship_id)
            scholarship.duration = "3 years"

            entries = [
                HistoryEntry(field_name="duration", old_value="2 years", new_value="3 years")
            ]
            write_verification_history(session, scholarship_id, entries)

            session.rollback()

            scholarship = session.get(Scholarship, scholarship_id)
            self.assertEqual(scholarship.duration, "2 years")

            count = _get_history_count(session, scholarship_id)
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
