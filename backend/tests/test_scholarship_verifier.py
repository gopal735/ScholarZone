"""Unit tests for the scholarship verification service foundation."""

import os
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-verifier-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from pydantic import ValidationError  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.database import get_session_factory, init_database, close_database, reset_database_connections  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.services.official_source_fetcher import OfficialSourceFetchResult, fetch_official_source  # noqa: E402
from app.services.scholarship_extractor import ExtractionConfidence, ScholarshipExtractionResult, extract_scholarship_information  # noqa: E402
from app.services.scholarship_verifier import verify_scholarship, VerificationResult, VerificationFetchStatus  # noqa: E402
from app.seed import seed_database  # noqa: E402


def _unique_url(suffix: str) -> str:
    return f"https://example.com/{suffix}-{uuid4().hex}"


def _mock_fetch_success(url: str) -> OfficialSourceFetchResult:
    return OfficialSourceFetchResult(
        success=True,
        status_code=200,
        final_url=url,
        content=(
            "<html><head><title>Valid URL Scholarship</title></head><body>"
            "<p>Degree: Master</p>"
            "<p>Offered by: Test Provider</p>"
            "<p>Eligibility: Must be enrolled</p>"
            "<p>Duration: 2 years</p>"
            "<p>Deadline: October 15, 2026</p>"
            "<a href='https://example.com/apply'>Apply now</a>"
            "</body></html>"
        ),
        content_type="text/html",
    )


def _mock_extraction_complete() -> ScholarshipExtractionResult:
    return ScholarshipExtractionResult(
        scholarship_name="Valid URL Scholarship",
        provider="Test Provider",
        degree_level="Master",
        eligibility="Must be enrolled",
        duration="2 years",
        application_method="Online",
        deadline="October 15, 2026",
        status="open",
        application_url="https://example.com/apply",
        confidence={
            "scholarship_name": ExtractionConfidence.HIGH,
            "provider": ExtractionConfidence.MEDIUM,
            "degree_level": ExtractionConfidence.MEDIUM,
            "eligibility": ExtractionConfidence.MEDIUM,
            "duration": ExtractionConfidence.MEDIUM,
            "application_method": ExtractionConfidence.MEDIUM,
            "deadline": ExtractionConfidence.HIGH,
            "status": ExtractionConfidence.MEDIUM,
            "application_url": ExtractionConfidence.HIGH,
        },
    )


class ScholarshipVerifierFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_database_connections()
        init_database()
        seed_database()

    @classmethod
    def tearDownClass(cls):
        close_database()
        reset_database_connections()
        if TEST_DATABASE_PATH.exists():
            TEST_DATABASE_PATH.unlink(missing_ok=True)

    def test_non_existent_scholarship_returns_none(self):
        with get_session_factory()() as session:
            result = verify_scholarship(session, 999999)
            self.assertIsNone(result)

    def test_missing_official_source_url_returns_error_result(self):
        with get_session_factory()() as session:
            scholarship = Scholarship(
                title="No Source Scholarship",
                country="Test Country",
                degree="Master",
                funding="Fully Funded",
            )
            session.add(scholarship)
            session.commit()
            scholarship_id = scholarship.id

            result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.scholarship_id, scholarship_id)
            self.assertIsNone(result.official_source_url)
            self.assertEqual(result.verification_status, "active")
            self.assertEqual(result.fetch_status, VerificationFetchStatus.PENDING)
            self.assertEqual(result.extracted_fields, {})
            self.assertEqual(result.changed_fields, {})
            self.assertEqual(result.warnings, ["Scholarship has no official_source_url; automatic verification cannot proceed"])
            self.assertEqual(result.error_reason, "official_source_url is missing")
            self.assertIsNone(result.fetch_result)

    def test_empty_official_source_url_returns_error_result(self):
        with get_session_factory()() as session:
            scholarship = Scholarship(
                title="Empty Source Scholarship",
                country="Test Country",
                degree="Master",
                funding="Fully Funded",
                official_source_url="   ",
            )
            session.add(scholarship)
            session.commit()
            scholarship_id = scholarship.id

            result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.scholarship_id, scholarship_id)
            self.assertEqual(result.official_source_url, "   ")
            self.assertEqual(result.verification_status, "active")
            self.assertEqual(result.fetch_status, VerificationFetchStatus.PENDING)
            self.assertEqual(result.extracted_fields, {})
            self.assertEqual(result.changed_fields, {})
            self.assertIn("official_source_url is not a valid URL", result.warnings)
            self.assertEqual(result.error_reason, "official_source_url is not a valid URL")
            self.assertIsNone(result.fetch_result)

    def test_invalid_url_returns_error_result(self):
        with get_session_factory()() as session:
            scholarship = Scholarship(
                title="Invalid URL Scholarship",
                country="Test Country",
                degree="Master",
                funding="Fully Funded",
                official_source_url="not-a-valid-url",
            )
            session.add(scholarship)
            session.commit()
            scholarship_id = scholarship.id

            result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.scholarship_id, scholarship_id)
            self.assertEqual(result.official_source_url, "not-a-valid-url")
            self.assertEqual(result.fetch_status, VerificationFetchStatus.PENDING)
            self.assertIn("official_source_url is not a valid URL", result.warnings)
            self.assertEqual(result.error_reason, "official_source_url is not a valid URL")
            self.assertIsNone(result.fetch_result)

    def test_valid_url_returns_complete_result(self):
        with get_session_factory()() as session:
            url = _unique_url("valid")
            scholarship = Scholarship(
                title="Valid URL Scholarship",
                country="Test Country",
                degree="Master",
                funding="Fully Funded",
                official_source="Test Provider",
                official_source_url=url,
                verification_status="active",
                eligibility=["Must be enrolled"],
                duration="2 years",
                deadline_display="October 15, 2026",
                application_link="https://example.com/apply",
            )
            session.add(scholarship)
            session.commit()
            scholarship_id = scholarship.id

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)) as mock_fetch, \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=_mock_extraction_complete()):
                result = verify_scholarship(session, scholarship_id)
                mock_fetch.assert_called_once_with(url)

            self.assertIsNotNone(result)
            self.assertEqual(result.scholarship_id, scholarship_id)
            self.assertEqual(result.official_source_url, url)
            self.assertEqual(result.verification_status, "active")
            self.assertEqual(result.fetch_status, VerificationFetchStatus.SUCCESS)
            self.assertIsNotNone(result.extracted_fields)
            self.assertIsInstance(result.extracted_fields, dict)
            self.assertEqual(result.changed_fields, {})
            self.assertEqual(result.warnings, [])
            self.assertIsNone(result.error_reason)
            self.assertIsNotNone(result.fetch_result)
            self.assertTrue(result.fetch_result.success)
            self.assertEqual(result.fetch_result.status_code, 200)
            self.assertEqual(result.fetch_result.final_url, url)

    def test_result_contains_all_required_fields(self):
        with get_session_factory()() as session:
            url = _unique_url("complete")
            scholarship = Scholarship(
                title="Valid URL Scholarship",
                country="Test Country",
                degree="Master",
                funding="Fully Funded",
                official_source="Test Provider",
                official_source_url=url,
                verification_status="needs_review",
                eligibility=["Must be enrolled"],
                duration="2 years",
                deadline_display="October 15, 2026",
                application_link="https://example.com/apply",
            )
            session.add(scholarship)
            session.commit()
            scholarship_id = scholarship.id

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)), \
                 patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=_mock_extraction_complete()):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.scholarship_id, scholarship_id)
            self.assertEqual(result.official_source_url, url)
            self.assertEqual(result.verification_status, "needs_review")
            self.assertEqual(result.fetch_status, VerificationFetchStatus.SUCCESS)
            self.assertIsInstance(result.extracted_fields, dict)
            self.assertIsInstance(result.changed_fields, dict)
            self.assertIsInstance(result.warnings, list)
            self.assertIsNone(result.error_reason)
            self.assertIsNotNone(result.fetch_result)
            self.assertIsInstance(result.fetch_result, OfficialSourceFetchResult)
            self.assertIsNotNone(result.extraction_result)
            self.assertIsInstance(result.extraction_result, dict)

    def test_url_normalisation_trailing_slash(self):
        with get_session_factory()() as session:
            url = _unique_url("trailing")
            scholarship = Scholarship(
                title="Trailing Slash Scholarship",
                country="Test Country",
                degree="Master",
                funding="Fully Funded",
                official_source_url=f"{url}/",
            )
            session.add(scholarship)
            session.commit()
            scholarship_id = scholarship.id

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(url)):
                result = verify_scholarship(session, scholarship_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.official_source_url, url)

    def test_verify_scholarship_does_not_modify_database(self):
        with get_session_factory()() as session:
            scholarship = Scholarship(
                title="No DB Change Scholarship",
                country="Test Country",
                degree="Master",
                funding="Fully Funded",
                official_source_url=_unique_url("no-db-change"),
                verification_status="active",
            )
            session.add(scholarship)
            session.commit()
            scholarship_id = scholarship.id
            original_updated_at = scholarship.updated_at

            with patch("app.services.scholarship_verifier.fetch_official_source", return_value=_mock_fetch_success(scholarship.official_source_url)):
                verify_scholarship(session, scholarship_id)

            session.refresh(scholarship)
            self.assertEqual(scholarship.id, scholarship_id)
            self.assertEqual(scholarship.verification_status, "active")
            self.assertEqual(scholarship.updated_at, original_updated_at)


class OfficialSourceFetcherTests(unittest.TestCase):
    def _mock_response(self, status_code, url, headers=None, text=None, content=None):
        response = MagicMock()
        response.status_code = status_code
        response.url = url
        response.headers = headers or {}
        response.text = text or ""
        response.content = content or b""
        return response

    def test_successful_200_fetch(self):
        mock_response = self._mock_response(
            200,
            "https://example.com/success",
            headers={"content-type": "text/html"},
            text="<html>success</html>",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/success")

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.final_url, "https://example.com/success")
        self.assertEqual(result.content, "<html>success</html>")
        self.assertEqual(result.content_type, "text/html")
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.error_reason)

    def test_redirect_followed(self):
        mock_response = self._mock_response(
            200,
            "https://example.com/new",
            headers={"content-type": "text/html"},
            text="<html>redirected</html>",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/old")

        self.assertTrue(result.success)
        self.assertEqual(result.final_url, "https://example.com/new")

    def test_404_returns_error(self):
        mock_response = self._mock_response(
            404,
            "https://example.com/missing",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/missing")

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.error_type, "not_found")
        self.assertIn("404", result.error_reason)

    def test_403_returns_error(self):
        mock_response = self._mock_response(
            403,
            "https://example.com/denied",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/denied")

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 403)
        self.assertEqual(result.error_type, "forbidden")
        self.assertIn("403", result.error_reason)

    def test_429_returns_error(self):
        mock_response = self._mock_response(
            429,
            "https://example.com/limited",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/limited")

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result.error_type, "rate_limited")
        self.assertIn("429", result.error_reason)

    def test_500_returns_error(self):
        mock_response = self._mock_response(
            500,
            "https://example.com/error",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/error")

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.error_type, "server_error")
        self.assertIn("500", result.error_reason)

    def test_timeout_returns_error(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/slow")

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "timeout")
        self.assertIsNone(result.status_code)
        self.assertIn("timed out", result.error_reason)

    def test_connection_failure_returns_error(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/unreachable")

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "connection_error")
        self.assertIsNone(result.status_code)
        self.assertIn("connect", result.error_reason)

    def test_invalid_content_type_returns_error(self):
        mock_response = self._mock_response(
            200,
            "https://example.com/doc.pdf",
            headers={"content-type": "application/pdf"},
            content=b"%PDF-1.4",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/doc.pdf")

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.error_type, "invalid_content_type")
        self.assertIn("application/pdf", result.error_reason)

    def test_final_redirected_url(self):
        mock_response = self._mock_response(
            200,
            "https://example.com/final",
            headers={"content-type": "text/html"},
            text="<html>ok</html>",
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/start")

        self.assertTrue(result.success)
        self.assertEqual(result.final_url, "https://example.com/final")

    def test_empty_url_returns_error(self):
        result = fetch_official_source("")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "invalid_url")
        self.assertIsNone(result.status_code)

    def test_fetcher_never_raises(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Unexpected failure")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.services.official_source_fetcher.httpx.Client", return_value=mock_client):
            result = fetch_official_source("https://example.com/crash")

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "unexpected_error")
        self.assertIsNone(result.status_code)


class ScholarshipExtractorTests(unittest.TestCase):
    def test_basic_scholarship_page(self):
        html = """
        <html>
        <head><title>Test Scholarship</title></head>
        <body>
            <h1>Test Scholarship Program</h1>
            <p>Degree: Master's</p>
            <p>Award: $10,000</p>
            <p>Duration: 2 years</p>
        </body>
        </html>
        """
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.scholarship_name, "Test Scholarship")
        self.assertEqual(result.degree_level, "Master's")
        self.assertEqual(result.award_amount, "$10,000")
        self.assertEqual(result.duration, "2 years")
        self.assertEqual(result.confidence["scholarship_name"], ExtractionConfidence.HIGH)
        self.assertEqual(result.confidence["degree_level"], ExtractionConfidence.MEDIUM)
        self.assertEqual(result.confidence["award_amount"], ExtractionConfidence.MEDIUM)
        self.assertEqual(result.confidence["duration"], ExtractionConfidence.MEDIUM)

    def test_deadline_extraction(self):
        html = """
        <html>
        <body>
            <p>Deadline: October 15, 2026</p>
            <p>Applications close December 1, 2026</p>
            <p>Apply by January 15, 2027</p>
            <p>Applications are due March 1, 2027</p>
        </body>
        </html>
        """
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.deadline, "October 15, 2026")
        self.assertEqual(result.deadline_type, "application_deadline")
        self.assertEqual(result.confidence["deadline"], ExtractionConfidence.HIGH)

    def test_award_extraction(self):
        html = """
        <html>
        <body>
            <p>Value: $25,000 per year</p>
            <p>Full tuition coverage</p>
            <p>Living stipend of $15,000</p>
        </body>
        </html>
        """
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.award_amount, "$25,000 per year")
        self.assertEqual(result.tuition_coverage, "coverage")
        self.assertEqual(result.living_stipend, "of $15,000")
        self.assertEqual(result.confidence["award_amount"], ExtractionConfidence.MEDIUM)
        self.assertEqual(result.confidence["tuition_coverage"], ExtractionConfidence.MEDIUM)
        self.assertEqual(result.confidence["living_stipend"], ExtractionConfidence.MEDIUM)

    def test_eligibility_extraction(self):
        html = """
        <html>
        <body>
            <h2>Eligibility Criteria</h2>
            <p>Must be a citizen of an eligible country</p>
            <p>Minimum GPA: 3.5</p>
            <p>English proficiency required</p>
        </body>
        </html>
        """
        result = extract_scholarship_information(html, "https://example.com")
        self.assertIn("citizen", result.eligibility or "")
        self.assertEqual(result.gpa_requirement, "3.5")
        self.assertEqual(result.language_requirement, "proficiency required")

    def test_application_url_extraction(self):
        html = """
        <html>
        <body>
            <a href="/apply">Apply now</a>
            <a href="https://example.com/scholarship-application">Scholarship application</a>
            <a href="/contact">Contact us</a>
        </body>
        </html>
        """
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.application_url, "https://example.com/apply")
        self.assertEqual(result.confidence["application_url"], ExtractionConfidence.HIGH)

    def test_rolling_deadline(self):
        html = "<html><body><p>Deadline: Rolling</p></body></html>"
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.deadline, "rolling")

    def test_unannounced_deadline(self):
        html = "<html><body><p>Deadline: Not announced</p></body></html>"
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.deadline, "not announced")

    def test_variable_deadline(self):
        html = "<html><body><p>Deadline: Varies by program</p></body></html>"
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.deadline, "varies")

    def test_noisy_html(self):
        html = """
        <html>
        <head>
            <script>console.log('noise');</script>
            <style>.noise { display: none; }</style>
        </head>
        <body>
            <nav><a href="/">Home</a></nav>
            <p>Eligibility: Must be enrolled in an accredited institution</p>
            <footer>Copyright 2026</footer>
        </body>
        </html>
        """
        result = extract_scholarship_information(html, "https://example.com")
        self.assertIn("accredited institution", result.eligibility or "")

    def test_malformed_html(self):
        html = "<html><body><p>Unclosed paragraph<div>Broken HTML</div>"
        result = extract_scholarship_information(html, "https://example.com")
        self.assertIsNotNone(result)

    def test_missing_fields(self):
        html = "<html><body><p>No scholarship data here</p></body></html>"
        result = extract_scholarship_information(html, "https://example.com")
        self.assertIsNone(result.scholarship_name)
        self.assertIsNone(result.deadline)
        self.assertEqual(result.extraction_notes, [])

    def test_no_guessing_when_ambiguous(self):
        html = "<html><body><p>Usually in October</p></body></html>"
        result = extract_scholarship_information(html, "https://example.com")
        self.assertIsNone(result.deadline)

    def test_normalization(self):
        html = "<html><body><p>Eligibility:   Multiple   spaces   </p><p>Text&amp;More</p></body></html>"
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.eligibility, "Multiple spaces")

    def test_extraction_confidence(self):
        html = """
        <html>
        <head><title>Confidence Test</title></head>
        <body>
            <p>Deadline: October 15, 2026</p>
            <p>Maybe award: $500?</p>
        </body>
        </html>
        """
        result = extract_scholarship_information(html, "https://example.com")
        self.assertEqual(result.confidence["deadline"], ExtractionConfidence.HIGH)
        self.assertEqual(result.confidence["scholarship_name"], ExtractionConfidence.HIGH)
        self.assertEqual(result.confidence["award_amount"], ExtractionConfidence.MEDIUM)


if __name__ == "__main__":
    unittest.main()
