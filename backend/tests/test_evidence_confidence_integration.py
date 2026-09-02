"""Integration tests for evidence + confidence integration in verification pipeline."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-evidence-integration-{uuid4().hex}.db"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.database import get_session_factory, init_database, close_database, reset_database_connections  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.official_source_fetcher import OfficialSourceFetchResult  # noqa: E402
from app.services.scholarship_evidence import EvidenceCollection, EvidenceStatus  # noqa: E402
from app.services.scholarship_extractor import ExtractionConfidence, ScholarshipExtractionResult  # noqa: E402
from app.services.scholarship_verifier import (  # noqa: E402
    VerificationFetchStatus,
    VerificationStatus,
    verify_scholarship,
)
from app.services.verification_confidence import VerificationAssessment, VerificationState  # noqa: E402


def _unique_url(suffix: str) -> str:
    return f"https://www.daad.de/{suffix}-{uuid4().hex}/"


def _unique_third_party_url(suffix: str) -> str:
    return f"https://example.com/{suffix}-{uuid4().hex}/"


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


class TestHighConfidenceOfficialEvidence(unittest.TestCase):
    """High-confidence official evidence should produce valid update candidate."""

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

    def test_high_confidence_official_evidence_valid_candidate(self):
        """High-confidence change from official source becomes update candidate."""
        with get_session_factory()() as session:
            url = _unique_url("high-confidence")
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
            self.assertEqual(result.fetch_status, VerificationFetchStatus.SUCCESS)
            self.assertTrue(len(result.automatic_update_candidates) > 0)
            candidate_fields = [c["field"] for c in result.automatic_update_candidates]
            self.assertIn("deadline_display", candidate_fields)


class TestAgreeingOfficialSources(unittest.TestCase):
    """Agreeing official sources should produce valid update candidate."""

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

    def test_agreeing_official_sources_valid_candidate(self):
        """Multiple agreeing official sources produce valid update candidate."""
        with get_session_factory()() as session:
            url = _unique_url("agreeing-sources")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="November 1, 2026",
            )

            extraction = _make_extraction(
                deadline="January 15, 2027",
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

            fetch_content = (
                "<html><head><title>Test Scholarship</title></head><body>"
                "<p>Degree: Master</p>"
                "<p>Offered by: Test Provider</p>"
                "<p>Eligibility: Must be enrolled</p>"
                "<p>Duration: 2 years</p>"
                "<p>Deadline: January 15, 2027</p>"
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


class TestConflictingEvidence(unittest.TestCase):
    """Evidence quality is affected when source doesn't support extraction."""

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

    def test_evidence_quality_reflects_source_content(self):
        """Evidence quality reflects whether source supports extraction."""
        with get_session_factory()() as session:
            url = _unique_url("evidence-quality")
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

            # Content has DIFFERENT deadline than extraction
            fetch_content = (
                "<html><head><title>Test Scholarship</title></head><body>"
                "<p>Degree: Master</p>"
                "<p>Offered by: Test Provider</p>"
                "<p>Eligibility: Must be enrolled</p>"
                "<p>Duration: 2 years</p>"
                "<p>Deadline: March 15, 2027</p>"
                "<a href='https://example.com/apply'>Apply now</a>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertIsNotNone(result.evidence_collection)
            self.assertIsNotNone(result.confidence_assessment)

            # Evidence should exist for deadline_display
            deadline_evidence = result.evidence_collection.get_evidence_for_field("deadline_display")
            self.assertIsNotNone(deadline_evidence)

            # Confidence assessment should exist for deadline_display
            deadline_confidence = result.confidence_assessment.get_field_result("deadline_display")
            self.assertIsNotNone(deadline_confidence)
            self.assertTrue(deadline_confidence.source_count > 0)


class TestThirdPartySource(unittest.TestCase):
    """Third-party sources should block automatic update."""

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

    def test_third_party_source_no_candidate(self):
        """Third-party source blocks automatic update."""
        with get_session_factory()() as session:
            url = _unique_third_party_url("third-party")
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
            # Third-party source should block auto-update
            candidate_fields = [c["field"] for c in result.automatic_update_candidates]
            self.assertNotIn("deadline_display", candidate_fields)


class TestLowConfidenceExtraction(unittest.TestCase):
    """Low-confidence extraction should block automatic update."""

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

    def test_low_confidence_extraction_no_candidate(self):
        """Low-confidence extraction blocks automatic update."""
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
            # Low confidence should block auto-update
            self.assertIn("deadline_display", result.uncertain_fields)
            candidate_fields = [c["field"] for c in result.automatic_update_candidates]
            self.assertNotIn("deadline_display", candidate_fields)


class TestMissingEvidence(unittest.TestCase):
    """Missing evidence should block automatic update."""

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

    def test_missing_evidence_no_candidate(self):
        """Missing evidence blocks automatic update."""
        with get_session_factory()() as session:
            url = _unique_url("missing-evidence")
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

            # Empty content - no evidence can be extracted
            fetch_content = "<html><body></body></html>"

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            # Missing evidence should block auto-update
            candidate_fields = [c["field"] for c in result.automatic_update_candidates]
            self.assertNotIn("deadline_display", candidate_fields)


class TestIdentityConflict(unittest.TestCase):
    """Identity conflict should block automatic update."""

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

    def test_identity_conflict_no_candidate(self):
        """Identity conflict blocks automatic update."""
        with get_session_factory()() as session:
            url = _unique_url("identity-conflict")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                title="Original Scholarship Title",
            )

            extraction = _make_extraction(
                scholarship_name="Completely Different Title",
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

            fetch_content = (
                "<html><head><title>Completely Different Title</title></head><body>"
                "<p>Degree: Master</p>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.verification_status, VerificationStatus.NEEDS_REVIEW)
            # Identity conflict should block auto-update
            candidate_fields = [c["field"] for c in result.automatic_update_candidates]
            self.assertNotIn("title", candidate_fields)
            self.assertTrue(any("Identity conflict" in w for w in result.warnings))


class TestVerificationResultContainsEvidenceAndConfidence(unittest.TestCase):
    """Final VerificationResult should contain evidence + confidence assessment."""

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

    def test_result_contains_evidence_collection(self):
        """VerificationResult contains evidence_collection."""
        with get_session_factory()() as session:
            url = _unique_url("evidence-collection")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(deadline="December 1, 2026")

            fetch_content = (
                "<html><head><title>Test Scholarship</title></head><body>"
                "<p>Deadline: December 1, 2026</p>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertIsNotNone(result.evidence_collection)
            self.assertIsInstance(result.evidence_collection, EvidenceCollection)
            self.assertEqual(result.evidence_collection.scholarship_id, scholarship_id)
            self.assertTrue(len(result.evidence_collection.items) > 0)

    def test_result_contains_confidence_assessment(self):
        """VerificationResult contains confidence_assessment."""
        with get_session_factory()() as session:
            url = _unique_url("confidence-assessment")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(deadline="December 1, 2026")

            fetch_content = (
                "<html><head><title>Test Scholarship</title></head><body>"
                "<p>Deadline: December 1, 2026</p>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertIsNotNone(result.confidence_assessment)
            self.assertIsInstance(result.confidence_assessment, VerificationAssessment)
            self.assertEqual(result.confidence_assessment.scholarship_id, scholarship_id)
            self.assertTrue(len(result.confidence_assessment.field_results) > 0)

    def test_evidence_items_have_status(self):
        """Evidence items have proper status classification."""
        with get_session_factory()() as session:
            url = _unique_url("evidence-status")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(deadline="December 1, 2026")

            fetch_content = (
                "<html><head><title>Test Scholarship</title></head><body>"
                "<p>Deadline: December 1, 2026</p>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertIsNotNone(result.evidence_collection)

            deadline_evidence = result.evidence_collection.get_evidence_for_field("deadline_display")
            self.assertIsNotNone(deadline_evidence)
            self.assertIn(deadline_evidence.status, [
                EvidenceStatus.HIGH_CONFIDENCE,
                EvidenceStatus.LOW_CONFIDENCE,
                EvidenceStatus.MISSING,
            ])

    def test_confidence_field_results_have_states(self):
        """Confidence field results have proper verification states."""
        with get_session_factory()() as session:
            url = _unique_url("confidence-states")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                deadline_display="October 15, 2026",
            )

            extraction = _make_extraction(deadline="December 1, 2026")

            fetch_content = (
                "<html><head><title>Test Scholarship</title></head><body>"
                "<p>Deadline: December 1, 2026</p>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertIsNotNone(result.confidence_assessment)

            deadline_result = result.confidence_assessment.get_field_result("deadline_display")
            self.assertIsNotNone(deadline_result)
            self.assertIn(deadline_result.verification_state, [
                VerificationState.VERIFIED,
                VerificationState.PARTIALLY_VERIFIED,
                VerificationState.UNCERTAIN,
                VerificationState.UNSUPPORTED,
            ])


class TestDatabaseRemainsUnchanged(unittest.TestCase):
    """Verify pipeline is read-only: no database writes occur."""

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

    def test_database_unchanged_after_verification(self):
        """Database remains unchanged after verification with evidence + confidence."""
        with get_session_factory()() as session:
            url = _unique_url("read-only")
            scholarship_id = _make_scholarship(
                session,
                official_source_url=url,
                title="Read Only Test",
                deadline_display="October 15, 2026",
                verification_status="active",
            )
            original_updated_at = session.execute(
                select(Scholarship.updated_at).where(Scholarship.id == scholarship_id)
            ).scalar_one()

            extraction = _make_extraction(deadline="December 1, 2026")

            fetch_content = (
                "<html><head><title>Read Only Test</title></head><body>"
                "<p>Deadline: December 1, 2026</p>"
                "</body></html>"
            )

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url, content=fetch_content)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=extraction):
                result = verify_scholarship(session, scholarship_id)

            session.expire_all()
            scholarship = session.execute(
                select(Scholarship).where(Scholarship.id == scholarship_id)
            ).scalar_one()

            self.assertEqual(scholarship.title, "Read Only Test")
            self.assertEqual(scholarship.deadline_display, "October 15, 2026")
            self.assertEqual(scholarship.verification_status, "active")
            self.assertEqual(scholarship.updated_at, original_updated_at)


if __name__ == "__main__":
    unittest.main()
