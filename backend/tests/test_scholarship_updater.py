"""Focused tests for the safe scholarship update engine."""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-updater-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"


fake_scheduler = types.ModuleType("app.scheduler")
fake_scheduler.start_scheduler = lambda: None
fake_scheduler.mark_due_for_review = lambda: None
sys.modules["app.scheduler"] = fake_scheduler


from app.database import close_database, get_session_factory, init_database, reset_database_connections  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.scholarship_diff import ChangeSet, FieldChange, FieldChangeType  # noqa: E402
from app.services.scholarship_extractor import ExtractionConfidence  # noqa: E402
from app.services.scholarship_updater import (  # noqa: E402
    _ALLOWLISTED_FIELDS,
    _FROZEN_FIELDS,
    UpdateResult,
    apply_changeset,
    apply_verified_updates,
)


def _make_scholarship(
    session,
    title: str = "Test Scholarship",
    country: str = "Test Country",
    degree: str = "Master",
    funding: str = "Fully Funded",
    duration: str = "2 years",
    status: str = "open",
    deadline_display: str = "October 15, 2026",
    eligibility: list[str] | None = None,
    application_method: list[str] | None = None,
    application_link: str = "https://example.com/apply",
    description: str | None = None,
) -> int:
    scholarship = Scholarship(
        title=title,
        country=country,
        degree=degree,
        funding=funding,
        duration=duration,
        status=status,
        deadline_display=deadline_display,
        eligibility=eligibility or ["Must be enrolled"],
        application_method=application_method or ["Online"],
        application_link=application_link,
        description=description,
    )
    session.add(scholarship)
    session.commit()
    return scholarship.id


def _get_scholarship(session, scholarship_id: int) -> Scholarship:
    return session.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id)
    ).scalar_one()


class ScholarshipUpdaterTests(unittest.TestCase):
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

    def test_approved_field_update(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "success")
            self.assertEqual(result.updated_fields, ["duration"])
            self.assertEqual(result.skipped_fields, [])
            self.assertEqual(result.rejected_fields, [])
            self.assertFalse(result.concurrency_conflict)
            self.assertIsNone(result.error_reason)

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")

    def test_multiple_approved_fields(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(
                session,
                duration="2 years",
                status="open",
                deadline_display="October 15, 2026",
            )

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                },
                {
                    "field": "status",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "open",
                    "new_value": "closed",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                },
                {
                    "field": "deadline_display",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "October 15, 2026",
                    "new_value": "December 1, 2026",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                },
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "success")
            self.assertEqual(set(result.updated_fields), {"duration", "status", "deadline_display"})
            self.assertFalse(result.concurrency_conflict)

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")
            self.assertEqual(scholarship.status, "closed")
            self.assertEqual(scholarship.deadline_display, "December 1, 2026")

    def test_no_candidates_returns_noop(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session)

            result = apply_verified_updates(session, scholarship_id, [])

            self.assertEqual(result.update_status, "noop")
            self.assertEqual(result.updated_fields, [])
            self.assertEqual(result.error_reason, "no candidates provided")

    def test_uncertain_candidate_rejected(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.UNCERTAIN,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.LOW,
                    "is_update_candidate": False,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "rejected")
            self.assertEqual(result.updated_fields, [])
            self.assertEqual(len(result.rejected_fields), 1)
            self.assertEqual(result.rejected_fields[0]["field"], "duration")

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "2 years")

    def test_identity_conflict_rejected(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, title="Original Title")

            candidates = [
                {
                    "field": "title",
                    "change_type": FieldChangeType.IDENTITY_CONFLICT,
                    "old_value": "Original Title",
                    "new_value": "Different Title",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": False,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "rejected")
            self.assertEqual(result.updated_fields, [])
            self.assertEqual(len(result.rejected_fields), 1)
            self.assertIn("identity conflict", result.rejected_fields[0]["reason"])

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.title, "Original Title")

    def test_low_confidence_rejected(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.LOW,
                    "is_update_candidate": False,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "rejected")
            self.assertEqual(result.updated_fields, [])
            self.assertEqual(len(result.rejected_fields), 1)
            self.assertIn("low confidence", result.rejected_fields[0]["reason"])

    def test_stale_old_value_concurrency_conflict(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "1 year",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "conflict")
            self.assertTrue(result.concurrency_conflict)
            self.assertEqual(result.updated_fields, [])
            self.assertEqual(len(result.rejected_fields), 1)
            self.assertIn("concurrency conflict", result.rejected_fields[0]["reason"])

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "2 years")

    def test_atomic_rollback_when_one_update_fails(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(
                session,
                duration="2 years",
                status="open",
            )

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                },
                {
                    "field": "status",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "open",
                    "new_value": "closed",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                },
            ]

            original_flush = session.flush
            call_count = 0

            def failing_flush(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Simulated database error")
                return original_flush(*args, **kwargs)

            session.flush = failing_flush

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "rejected")
            self.assertEqual(result.updated_fields, [])
            self.assertIn("transaction failed", result.error_reason or "")

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "2 years")
            self.assertEqual(scholarship.status, "open")

    def test_repeated_changeset_idempotent(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="2 years")

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                }
            ]

            result1 = apply_verified_updates(session, scholarship_id, candidates)
            self.assertEqual(result1.update_status, "success")
            self.assertEqual(result1.updated_fields, ["duration"])

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")

            result2 = apply_verified_updates(session, scholarship_id, candidates)
            self.assertEqual(result2.update_status, "noop")
            self.assertEqual(result2.updated_fields, [])
            self.assertIn("no fields required updating", result2.error_reason or "")

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")

    def test_unrelated_fields_remain_unchanged(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(
                session,
                title="Original Title",
                country="Test Country",
                duration="2 years",
                status="open",
                description="Original description",
            )

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "success")
            self.assertEqual(result.updated_fields, ["duration"])

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")
            self.assertEqual(scholarship.title, "Original Title")
            self.assertEqual(scholarship.country, "Test Country")
            self.assertEqual(scholarship.status, "open")
            self.assertEqual(scholarship.description, "Original description")

    def test_frozen_fields_rejected(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, country="Test Country")

            candidates = [
                {
                    "field": "country",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "Test Country",
                    "new_value": "Different Country",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "rejected")
            self.assertEqual(len(result.rejected_fields), 1)
            self.assertIn("frozen", result.rejected_fields[0]["reason"])

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.country, "Test Country")

    def test_changeset_integration(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(
                session,
                duration="2 years",
                deadline_display="October 15, 2026",
            )

            changeset = ChangeSet(
                changes=[
                    FieldChange(
                        field="duration",
                        change_type=FieldChangeType.MODIFIED,
                        old_value="2 years",
                        new_value="3 years",
                        source="extractor -> database",
                        confidence=ExtractionConfidence.HIGH,
                        is_update_candidate=True,
                    ),
                    FieldChange(
                        field="deadline_display",
                        change_type=FieldChangeType.MODIFIED,
                        old_value="October 15, 2026",
                        new_value="December 1, 2026",
                        source="extractor -> database",
                        confidence=ExtractionConfidence.HIGH,
                        is_update_candidate=True,
                    ),
                ]
            )

            result = apply_changeset(session, scholarship_id, changeset)

            self.assertEqual(result.update_status, "success")
            self.assertEqual(set(result.updated_fields), {"duration", "deadline_display"})

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")
            self.assertEqual(scholarship.deadline_display, "December 1, 2026")

    def test_partial_update_with_rejections(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(
                session,
                duration="2 years",
                status="open",
            )

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                },
                {
                    "field": "status",
                    "change_type": FieldChangeType.UNCERTAIN,
                    "old_value": "open",
                    "new_value": "closed",
                    "confidence": ExtractionConfidence.LOW,
                    "is_update_candidate": False,
                },
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "partial")
            self.assertEqual(result.updated_fields, ["duration"])
            self.assertEqual(len(result.rejected_fields), 1)
            self.assertEqual(result.rejected_fields[0]["field"], "status")

            session.expire_all()
            scholarship = _get_scholarship(session, scholarship_id)
            self.assertEqual(scholarship.duration, "3 years")
            self.assertEqual(scholarship.status, "open")

    def test_nonexistent_scholarship(self):
        candidates = [
            {
                "field": "duration",
                "change_type": FieldChangeType.MODIFIED,
                "old_value": "2 years",
                "new_value": "3 years",
                "confidence": ExtractionConfidence.HIGH,
                "is_update_candidate": True,
            }
        ]

        with get_session_factory()() as session:
            result = apply_verified_updates(session, 999999, candidates)

            self.assertEqual(result.update_status, "rejected")
            self.assertIn("not found", result.error_reason or "")

    def test_already_applied_value_skipped(self):
        with get_session_factory()() as session:
            scholarship_id = _make_scholarship(session, duration="3 years")

            candidates = [
                {
                    "field": "duration",
                    "change_type": FieldChangeType.MODIFIED,
                    "old_value": "2 years",
                    "new_value": "3 years",
                    "confidence": ExtractionConfidence.HIGH,
                    "is_update_candidate": True,
                }
            ]

            result = apply_verified_updates(session, scholarship_id, candidates)

            self.assertEqual(result.update_status, "noop")
            self.assertEqual(result.skipped_fields, ["duration"])
            self.assertEqual(result.updated_fields, [])

    def test_allowlist_excludes_frozen_fields(self):
        self.assertTrue(_FROZEN_FIELDS.isdisjoint(_ALLOWLISTED_FIELDS))

    def test_allowlist_includes_known_content_fields(self):
        expected_fields = {
            "degree",
            "funding",
            "duration",
            "status",
            "deadline_display",
            "eligibility",
            "application_method",
            "application_link",
        }
        self.assertTrue(expected_fields.issubset(_ALLOWLISTED_FIELDS))

    def test_frozen_fields_include_identity_and_metadata(self):
        expected_frozen = {
            "id",
            "title",
            "country",
            "official_source",
            "official_source_url",
            "is_verified",
            "verification_status",
            "created_at",
            "updated_at",
        }
        self.assertTrue(expected_frozen.issubset(_FROZEN_FIELDS))


if __name__ == "__main__":
    unittest.main()
