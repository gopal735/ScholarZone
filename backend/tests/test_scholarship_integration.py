"""Integration tests for the verification pipeline with confidence safety gate."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import select


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-integration-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.database import get_session_factory, init_database, close_database, reset_database_connections  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.official_source_fetcher import OfficialSourceFetchResult  # noqa: E402
from app.services.scholarship_extractor import ExtractionConfidence, ScholarshipExtractionResult  # noqa: E402
from app.services.scholarship_verifier import (  # noqa: E402
    VerificationFetchStatus,
    VerificationStatus,
    verify_scholarship,
)


def _unique_url(suffix: str) -> str:
    return f"https://example.com/{suffix}-{uuid4().hex}"


def _make_scholarship(
    session,
    title: str = "Test Scholarship",
    official_source_url: str | None = None,
    degree: str = "Master",
    official_source: str = "Test Provider",
    eligibility: list[str] | None = None,
    duration: str = "2 years",
    application_method: list[str] | None = None,
    deadline_display: str = "October 15, 2026",
    status: str = "open",
    application_link: str = "https://example.com/apply",
    verification_status: str = "active",
) -> int:
    scholarship = Scholarship(
        title=title,
        country="Test Country",
        degree=degree,
        funding="Fully Funded",
        official_source=official_source,
        official_source_url=official_source_url,
        eligibility=eligibility or ["Must be enrolled"],
        duration=duration,
        application_method=application_method or ["Online"],
        deadline_display=deadline_display,
        status=status,
        application_link=application_link,
        verification_status=verification_status,
    )
    session.add(scholarship)
    session.commit()
    return scholarship.id


def _mock_fetch_success(url: str, content: str = "<html>success</html>") -> OfficialSourceFetchResult:
    return OfficialSourceFetchResult(
        success=True,
        status_code=200,
        final_url=url,
        content=content,
        content_type="text/html",
    )


def _mock_fetch_failure(url: str, error: str = "Connection failed") -> OfficialSourceFetchResult:
    return OfficialSourceFetchResult(
        success=False,
        error_type="connection_error",
        error_reason=error,
    )


def _make_extraction(
    scholarship_name: str | None = "Test Scholarship",
    provider: str | None = "Test Provider",
    degree_level: str | None = "Master",
    eligibility: str | None = "Must be enrolled",
    duration: str | None = "2 years",
    application_method: str | None = "Online",
    deadline: str | None = "October 15, 2026",
    status: str | None = "open",
    application_url: str | None = "https://example.com/apply",
    confidence: dict[str, str] | None = None,
) -> ScholarshipExtractionResult:
    if confidence is None:
        confidence = {
            "scholarship_name": ExtractionConfidence.HIGH,
            "provider": ExtractionConfidence.HIGH,
            "degree_level": ExtractionConfidence.HIGH,
            "eligibility": ExtractionConfidence.HIGH,
            "duration": ExtractionConfidence.HIGH,
            "application_method": ExtractionConfidence.HIGH,
            "deadline": ExtractionConfidence.HIGH,
            "status": ExtractionConfidence.HIGH,
            "application_url": ExtractionConfidence.HIGH,
        }
    return ScholarshipExtractionResult(
        scholarship_name=scholarship_name,
        provider=provider,
        degree_level=degree_level,
        eligibility=eligibility,
        duration=duration,
        application_method=application_method,
        deadline=deadline,
        status=status,
        application_url=application_url,
        confidence=confidence,
    )


class VerificationPipelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
        reset_database_connections()
        init_database()

    @classmethod
    def tearDownClass(cls):
        close_database()
        reset_database_connections()
        if TEST_DATABASE_PATH.exists():
            TEST_DATABASE_PATH.unlink(missing_ok=True)

    def test_1_successful_fetch_extraction_no_changes(self):
        """Successful fetch + extraction with identical data produces no changes."""
        with get_session_factory()() as session:
            url = _unique_url("no-changes")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                title="Test Scholarship",
                degree="Master",
                official_source="Test Provider",
                eligibility=["Must be enrolled"],
                duration="2 years",
                application_method=["Online"],
                deadline_display="October 15, 2026",
                status="open",
                application_link="https://example.com/apply",
            )

            extraction = _make_extraction()

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.fetch_status, VerificationFetchStatus.SUCCESS)
            self.assertEqual(result.changed_fields, {})
            self.assertEqual(result.automatic_update_candidates, [])
            self.assertIn("title", result.unchanged_fields)
            self.assertIn("degree", result.unchanged_fields)

    def test_2_successful_fetch_valid_change(self):
        """Successful fetch + extraction with a valid field change detected."""
        with get_session_factory()() as session:
            url = _unique_url("valid-change")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(deadline="December 1, 2026")

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.fetch_status, VerificationFetchStatus.SUCCESS)
            self.assertIn("deadline_display", result.changed_fields)
            self.assertEqual(result.changed_fields["deadline_display"], ("October 15, 2026", "December 1, 2026"))

    def test_3_high_confidence_change_becomes_update_candidate(self):
        """High-confidence validated changes become automatic update candidates."""
        with get_session_factory()() as session:
            url = "https://www.daad.de/en/"
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(
                deadline="December 1, 2026",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "provider": ExtractionConfidence.HIGH,
                    "degree_level": ExtractionConfidence.HIGH,
                    "eligibility": ExtractionConfidence.HIGH,
                    "duration": ExtractionConfidence.HIGH,
                    "application_method": ExtractionConfidence.HIGH,
                    "deadline": ExtractionConfidence.HIGH,
                    "status": ExtractionConfidence.HIGH,
                    "application_url": ExtractionConfidence.HIGH,
                },
            )

            # Mock fetch returns content with the NEW deadline to match extraction
            fetch_content = (
                "<html><head><title>Test Scholarship</title></head><body>"
                "<p>Degree: Master</p>"
                "<p>Offered by: Test Provider</p>"
                "<p>Eligibility: Must be enrolled</p>"
                "<p>Duration: 2 years</p>"
                "<p>Deadline: December 1, 2026</p>"
                "<a href='https://example.com/apply'>Apply now</a>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertTrue(len(result.automatic_update_candidates) > 0)
            candidate_fields = [c["field"] for c in result.automatic_update_candidates]
            self.assertIn("deadline_display", candidate_fields)
            for candidate in result.automatic_update_candidates:
                self.assertEqual(candidate["confidence"], ExtractionConfidence.HIGH)

    def test_4_none_extraction_becomes_uncertain(self):
        """Extractor returning None for a field marks it as uncertain."""
        with get_session_factory()() as session:
            url = _unique_url("none-extraction")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(deadline=None)

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertIn("deadline_display", result.uncertain_fields)
            self.assertTrue(len(result.automatic_update_candidates) == 0 or
                           all(c["field"] != "deadline_display" for c in result.automatic_update_candidates))

    def test_5_low_confidence_becomes_uncertain(self):
        """Low confidence changes are flagged as uncertain, not auto-updated."""
        with get_session_factory()() as session:
            url = _unique_url("low-confidence")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(
                deadline="December 1, 2026",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "provider": ExtractionConfidence.HIGH,
                    "degree_level": ExtractionConfidence.HIGH,
                    "eligibility": ExtractionConfidence.HIGH,
                    "duration": ExtractionConfidence.HIGH,
                    "application_method": ExtractionConfidence.HIGH,
                    "deadline": ExtractionConfidence.LOW,
                    "status": ExtractionConfidence.HIGH,
                    "application_url": ExtractionConfidence.HIGH,
                },
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertIn("deadline_display", result.uncertain_fields)
            candidate_fields = [c["field"] for c in result.automatic_update_candidates]
            self.assertNotIn("deadline_display", candidate_fields)

    def test_6_identity_conflict_becomes_needs_review(self):
        """Identity field changes trigger needs_review status."""
        with get_session_factory()() as session:
            url = _unique_url("identity-conflict")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                title="Original Scholarship Title",
            )

            extraction = _make_extraction(scholarship_name="Completely Different Title")

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.verification_status, VerificationStatus.NEEDS_REVIEW)
            self.assertTrue(len(result.automatic_update_candidates) == 0 or
                           all(c["field"] != "title" for c in result.automatic_update_candidates))
            self.assertTrue(any("Identity conflict" in w for w in result.warnings))

    def test_7_fetch_failure(self):
        """Fetch failure results in failed status with no update candidates."""
        with get_session_factory()() as session:
            url = _unique_url("fetch-failure")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_failure(url)):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.fetch_status, VerificationFetchStatus.FAILED)
            self.assertEqual(result.automatic_update_candidates, [])
            self.assertIsNotNone(result.error_reason)
            self.assertIn("Fetch failed", result.warnings[0] if result.warnings else "")

    def test_8_extraction_failure(self):
        """Extraction returning empty result produces no update candidates."""
        with get_session_factory()() as session:
            url = _unique_url("extraction-failure")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
            )

            empty_extraction = ScholarshipExtractionResult(
                extraction_notes=["Failed to parse HTML"],
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=empty_extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.fetch_status, VerificationFetchStatus.SUCCESS)
            self.assertEqual(result.automatic_update_candidates, [])

    def test_9_database_remains_unchanged(self):
        """Verify pipeline is read-only: no database writes occur."""
        with get_session_factory()() as session:
            url = _unique_url("read-only")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                title="Read Only Test",
                verification_status="active",
            )
            original_updated_at = session.execute(
                select(Scholarship.updated_at).where(Scholarship.id == scholarship_id)
            ).scalar_one()

            extraction = _make_extraction(scholarship_name="Different Title")

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                verify_scholarship(session, scholarship_id)

            session.expire_all()
            scholarship = session.execute(
                select(Scholarship).where(Scholarship.id == scholarship_id)
            ).scalar_one()

            self.assertEqual(scholarship.title, "Read Only Test")
            self.assertEqual(scholarship.verification_status, "active")
            self.assertEqual(scholarship.updated_at, original_updated_at)

    def test_10_deterministic_result(self):
        """Same inputs produce identical results on repeated calls."""
        with get_session_factory()() as session:
            url = _unique_url("deterministic")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(deadline="December 1, 2026")

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result1 = verify_scholarship(session, scholarship_id)
                result2 = verify_scholarship(session, scholarship_id)

            self.assertEqual(result1.changed_fields, result2.changed_fields)
            self.assertEqual(result1.unchanged_fields, result2.unchanged_fields)
            self.assertEqual(result1.uncertain_fields, result2.uncertain_fields)
            self.assertEqual(result1.automatic_update_candidates, result2.automatic_update_candidates)
            self.assertEqual(result1.verification_status, result2.verification_status)


if __name__ == "__main__":
    unittest.main()
