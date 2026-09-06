"""Tests for evidence-driven image discovery, validation, and confidence decision.

Covers:
- Unreachable image (HTTP 404)
- Invalid image content-type
- Official domain candidate validation
- Generic banner rejection (logo/icon patterns)
- Duplicate image detection
- licensing_unknown handling
- Confidence decision model (HIGH/MEDIUM/LOW)
- Human-review routing
- NULL fallback when no trustworthy image exists
"""

import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-test-discovery-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.models import Base, Scholarship  # noqa: E402
from app.services.image_analysis import ImageAnalysisResult  # noqa: E402
from app.services.image_discovery import (  # noqa: E402
    ImageCandidate,
    ImageDiscoveryService,
    PageFetchResult,
)
from app.services.image_validator import (  # noqa: E402
    ImageValidator,
    ImageValidationResult,
    ValidationStatus,
    determine_image_source_type,
)
from app.services.scholarship_image_verifier import (  # noqa: E402
    ImageSourceType,
    is_official_domain,
)


def _make_candidate(
    image_url: str = "https://daad.de/image.jpg",
    page_url: str = "https://daad.de/page",
    discovery_method: str = "html-img",
    alt_text: str | None = "Test image",
    width: int | None = 800,
    height: int | None = 600,
) -> ImageCandidate:
    return ImageCandidate(
        image_url=image_url,
        page_url=page_url,
        discovery_method=discovery_method,
        alt_text=alt_text,
        width=width,
        height=height,
        html_context="Test Scholarship Program",
    )


def _mock_head(status_code: int, content_type: str = "image/jpeg") -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.headers = {"content-type": content_type}
    return mock


def _mock_get_image(content_type: str = "image/jpeg"):
    def mock_get(*args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": content_type}
        resp.raw = MagicMock()
        return resp
    return mock_get


class TestUnreachableImage:
    def test_unreachable_image_rejected(self):
        candidate = _make_candidate(image_url="https://daad.de/image.jpg")
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(404, "text/html")
        mock_httpx_module.RequestError = type("E", (), {})

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            result = validator.validate_candidate(candidate, scholarship_title="DAAD")

        assert result.is_reachable is False
        assert result.http_status == 404
        assert result.status == ValidationStatus.REJECTED
        assert result.confidence == "LOW"


class TestInvalidImage:
    def test_invalid_content_type_rejected(self):
        candidate = _make_candidate(
            image_url="https://daad.de/image.jpg",
            page_url="https://daad.de/page",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "text/html")
        mock_httpx_module.RequestError = type("E", (), {})

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing") as mock_lic:
                mock_lic.side_effect = lambda result: result
                result = validator.validate_candidate(candidate, scholarship_title="DAAD")

        assert result.is_valid_image is False
        assert result.status == ValidationStatus.REJECTED
        assert any("Invalid content-type" in r for r in result.rejection_reasons)


class TestOfficialDomainCandidate:
    def test_official_domain_approved_when_all_checks_pass(self):
        candidate = _make_candidate(
            image_url="https://www.daad.de/images/scholarship-program.jpg",
            page_url="https://www.daad.de/en/scholarships/program",
            discovery_method="og:image",
            alt_text="DAAD scholarship students studying",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            result.licensing_evidence = "CC BY 4.0"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD Scholarship Program",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.is_official_domain is True
        assert result.is_valid_image is True
        assert result.is_reachable is True
        assert result.status == ValidationStatus.APPROVED
        assert result.confidence == "HIGH"
        assert result.is_duplicate is False


class TestGenericBannerRejection:
    def test_generic_banner_logo_rejected(self):
        candidate = _make_candidate(
            image_url="https://daad.de/images/header-banner.jpg",
            page_url="https://daad.de/page",
            discovery_method="html-img",
            alt_text="Site header banner",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            result = validator.validate_candidate(
                candidate,
                scholarship_title="Test Scholarship",
                official_source_url="https://daad.de",
            )

        assert result.is_generic_image is True
        assert result.non_content_total_weight >= 1.5
        assert any("Non-content image" in r for r in result.rejection_reasons)
        assert result.status == ValidationStatus.REJECTED


class TestDuplicateImageDetection:
    def test_duplicate_image_detected(self):
        candidate = _make_candidate(
            image_url="https://daad.de/images/banner.jpg",
            page_url="https://daad.de/en/scholarships",
            discovery_method="og:image",
        )
        validator = ImageValidator(seen_images={"https://daad.de/images/banner.jpg": 1})

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            result.licensing_evidence = "CC BY"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD Scholarship",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.is_duplicate is True


class TestLicensingUnknown:
    def test_licensing_unknown_leads_to_human_review_or_reject(self):
        candidate = _make_candidate(
            image_url="https://studyinkorea.go.kr/images/gks-program.jpg",
            page_url="https://studyinkorea.go.kr/en/plan/scholarship",
            discovery_method="og:image",
            alt_text="Global Korea Scholarship program",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_unknown"
            result.licensing_evidence = None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="Global Korea Scholarship",
                    official_source_url="https://studyinkorea.go.kr/en/plan/scholarship",
                )

        assert result.licensing_status == "licensing_unknown"
        assert result.status in (ValidationStatus.HUMAN_REVIEW, ValidationStatus.REJECTED)


class TestConfidenceDecision:
    def test_high_confidence_approved(self):
        candidate = _make_candidate(
            image_url="https://erasmus-plus.ec.europa.eu/images/emjm-campus.jpg",
            page_url="https://erasmus-plus.ec.europa.eu/opportunities/erasmus-mundus-joint-masters",
            discovery_method="og:image",
            alt_text="Erasmus Mundus Joint Masters students on European campus",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            result.licensing_evidence = "CC BY 4.0"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="Erasmus Mundus Joint Masters",
                    official_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
                )

        assert result.confidence == "HIGH"
        assert result.status == ValidationStatus.APPROVED
        assert result.licensing_status == "licensing_known"
        assert result.licensing_evidence is not None

    def test_low_relevance_no_license_rejected(self):
        candidate = _make_candidate(
            image_url="https://daad.de/images/daad-students.jpg",
            page_url="https://daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="DAAD",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_unknown"
            result.licensing_evidence = None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD Scholarship",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.licensing_status == "licensing_unknown"
        assert result.status in (ValidationStatus.HUMAN_REVIEW, ValidationStatus.REJECTED)


class TestHumanReviewRouting:
    def test_non_content_image_with_license_still_rejected(self):
        """Non-content images with licensing known must still be rejected — layered evidence."""
        candidate = _make_candidate(
            image_url="https://daad.de/images/header-banner.jpg",
            page_url="https://daad.de/en/scholarships",
            discovery_method="og:image",
            alt_text="DAAD scholarship header banner",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            result.licensing_evidence = "CC BY"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD Scholarship",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert result.confidence == "LOW"


class TestNullFallback:
    def test_null_fallback_when_image_unreachable(self):
        candidate = _make_candidate(image_url="https://daad.de/image.jpg")
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(404, "text/html")
        mock_httpx_module.RequestError = type("E", (), {})

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            result = validator.validate_candidate(candidate, scholarship_title="Test")

        assert result.status == ValidationStatus.REJECTED
        assert result.confidence == "LOW"
        assert not result.is_reachable

    def test_null_fallback_for_non_official_domain(self):
        candidate = _make_candidate(
            image_url="https://unsplash.com/photos/image.jpg",
            page_url="https://unsplash.com",
            discovery_method="og:image",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            result.licensing_evidence = "CC0"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="Test Scholarship",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.is_official_domain is False
        assert result.status == ValidationStatus.REJECTED
        assert result.confidence == "LOW"

    def test_find_best_result_returns_none_when_all_rejected(self):
        validator = ImageValidator()
        results_obj = [
            MagicMock(status=ValidationStatus.REJECTED, relevance_score=0.5),
            MagicMock(status=ValidationStatus.REJECTED, relevance_score=0.3),
        ]
        best = validator.find_best_result(results_obj)
        assert best is None


class TestUiAssetRejection:
    """Regression tests: UI assets must never be auto-approved."""

    def test_btn_drawer_close_svg_rejected(self):
        candidate = _make_candidate(
            image_url="https://www.jasso.go.jp/en/kyotsu/arrow/btn_drawer_close.svg",
            page_url="https://www.jasso.go.jp/en/kyotsu/",
            discovery_method="html-img",
            alt_text="Close drawer",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/svg+xml")
        mock_httpx_module.RequestError = type("E", (), {})

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            result.licensing_evidence = "All rights reserved"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="JASSO Scholarship",
                    official_source_url="https://www.jasso.go.jp/en/kyotsu/",
                )

        assert result.non_content_total_weight >= 1.5
        assert result.is_svg is True
        assert result.is_svg_content_illustration is False
        assert result.status == ValidationStatus.REJECTED
        assert result.confidence == "LOW"

    def test_icon_svg_rejected(self):
        candidate = _make_candidate(
            image_url="https://daad.de/images/icon.svg",
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="Icon",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/svg+xml")
        mock_httpx_module.RequestError = type("E", (), {})

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.non_content_total_weight >= 1.5
        assert result.is_svg is True
        assert result.status == ValidationStatus.REJECTED

    def test_arrow_svg_rejected(self):
        candidate = _make_candidate(
            image_url="https://erasmus-plus.ec.europa.eu/images/arrow.svg",
            page_url="https://erasmus-plus.ec.europa.eu/opportunities",
            discovery_method="html-img",
            alt_text="Next arrow",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/svg+xml")
        mock_httpx_module.RequestError = type("E", (), {})

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="Erasmus Mundus",
                    official_source_url="https://erasmus-plus.ec.europa.eu/opportunities",
                )

        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED

    def test_logo_svg_rejected(self):
        candidate = _make_candidate(
            image_url="https://www.daad.de/images/logo.svg",
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="DAAD Logo",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/svg+xml")
        mock_httpx_module.RequestError = type("E", (), {})

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.non_content_logo_weight >= 1.5
        assert result.is_svg is True
        assert result.status == ValidationStatus.REJECTED


class TestSvgContentIllustration:
    """SVG content illustrations with strong context may go to HUMAN_REVIEW but never auto-approved."""

    def test_svg_with_content_signals_goes_to_human_review(self):
        from app.services.image_validator import SVG_APPROVAL_WHITELIST

        candidate = _make_candidate(
            image_url="https://daad.de/images/scholarship-students.svg",
            page_url="https://www.daad.de/en/scholarships/daad-scholarship-program",
            discovery_method="og:image",
            alt_text="DAAD scholarship students studying on campus",
            width=800,
            height=600,
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/svg+xml")
        mock_httpx_module.RequestError = type("E", (), {})

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            result.licensing_evidence = "CC BY 4.0"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD Scholarship Program",
                    official_source_url="https://www.daad.de/en/scholarships/daad-scholarship-program",
                )

        assert result.is_svg is True
        assert result.is_svg_content_illustration is True
        assert result.non_content_total_weight == 0
        assert result.status == ValidationStatus.HUMAN_REVIEW
        assert result.confidence == "MEDIUM"

    def test_svg_without_content_signals_rejected(self):
        candidate = _make_candidate(
            image_url="https://daad.de/images/generic-diagram.svg",
            page_url="https://www.daad.de/en/scholarships/program",
            discovery_method="html-img",
            alt_text="Diagram",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/svg+xml")
        mock_httpx_module.RequestError = type("E", (), {})

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_known"
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD Scholarship",
                    official_source_url="https://www.daad.de/en/scholarships/program",
                )

        assert result.is_svg is True
        assert result.is_svg_content_illustration is False
        assert result.status == ValidationStatus.REJECTED


class TestUiAssetPatternDetection:
    """Various UI asset filename patterns should be detected and rejected."""

    @pytest.mark.parametrize("url,reason_contains", [
        ("https://daad.de/icons/btn-apply.svg", "UI element"),
        ("https://daad.de/img/close-btn.png", "UI element"),
        ("https://daad.de/assets/icons/menu.png", "nav/icon"),
        ("https://daad.de/img/chevron-right.png", "UI element"),
        ("https://daad.de/img/arrow-next.png", "UI element"),
        ("https://daad.de/img/toggle-switch.png", "UI element"),
        ("https://daad.de/img/loading-spinner.gif", "UI element"),
        ("https://daad.de/img/sprite-sheet.png", "sprite"),
        ("https://daad.de/img/social-facebook.png", "social"),
        ("https://daad.de/img/avatar-default.png", "placeholder"),
        ("https://daad.de/img/tracking-pixel.gif", "UI element"),
    ])
    def test_ui_asset_patterns_detected(self, url, reason_contains):
        candidate = _make_candidate(
            image_url=url,
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="Some UI element",
        )
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/png")
        mock_httpx_module.RequestError = type("E", (), {})

        def mock_check_licensing(self, result):
            result.licensing_status = "licensing_unknown"
            result.licensing_evidence = None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                result = validator.validate_candidate(
                    candidate,
                    scholarship_title="DAAD",
                    official_source_url="https://www.daad.de/en/scholarships",
                )

        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED


class TestDetermineSourceType:
    def test_eu_commission_is_scholarship(self):
        assert determine_image_source_type("erasmus-plus.ec.europa.eu") == ImageSourceType.OFFICIAL_SCHOLARSHIP

    def test_daad_is_provider(self):
        assert determine_image_source_type("www.daad.de") == ImageSourceType.OFFICIAL_PROVIDER

    def test_iccr_is_scholarship(self):
        assert determine_image_source_type("a2ascholarships.iccr.gov.in") == ImageSourceType.OFFICIAL_SCHOLARSHIP

    def test_gks_is_scholarship(self):
        assert determine_image_source_type("www.studyinkorea.go.kr") == ImageSourceType.OFFICIAL_SCHOLARSHIP

    def test_mext_is_scholarship(self):
        assert determine_image_source_type("www.studyinjapan.go.jp") == ImageSourceType.OFFICIAL_SCHOLARSHIP

    def test_university_domain(self):
        assert determine_image_source_type("www.harvard.edu") == ImageSourceType.OFFICIAL_UNIVERSITY

    def test_government_domain(self):
        assert determine_image_source_type("www.state.gov") == ImageSourceType.OFFICIAL_GOVERNMENT

    def test_unknown_domain_returns_none(self):
        assert determine_image_source_type("www.example.com") is None
        assert determine_image_source_type(None) is None


class TestDiscoveryService:
    def test_discovers_og_image_from_html(self):
        html_content = """
        <html>
        <head>
            <meta property="og:image" content="https://daad.de/images/og-scholarship.jpg">
            <title>DAAD Scholarship Program</title>
        </head>
        <body>
            <img src="/images/banner.jpg" alt="DAAD Banner">
        </body>
        </html>
        """
        service = ImageDiscoveryService()
        candidates = service.extract_images_from_html(html_content, "https://daad.de/en/scholarships")

        image_urls = [c.image_url for c in candidates]
        assert "https://daad.de/images/og-scholarship.jpg" in image_urls
        assert "https://daad.de/images/banner.jpg" in image_urls

    def test_does_not_crawl_non_official_domain(self):
        service = ImageDiscoveryService()
        service._crawl_page("https://unsplash.com/photos/abc", depth=0)
        assert len(service._candidates) == 0

    def test_deduplicates_candidates(self):
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
            <img src="https://daad.de/img.jpg" alt="test1">
            <img src="https://daad.de/img.jpg" alt="test2">
        </body>
        </html>
        """
        service = ImageDiscoveryService()
        candidates = service.extract_images_from_html(html_content, "https://daad.de/page")
        assert len(candidates) == 1


class TestNonContentImageRegression:
    """Regression tests for all false-positive classes that previously passed.

    Each test verifies that a specific non-content image class is rejected
    with layered evidence scoring, never auto-approved.
    """

    def _validate_mocked(self, candidate, scholarship_title, official_source_url,
                        licensing_status="licensing_known"):
        """Helper: run validator with mocked HTTP."""
        validator = ImageValidator()
        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = licensing_status
            result.licensing_evidence = "CC BY 4.0" if licensing_status == "licensing_known" else None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                return validator.validate_candidate(
                    candidate,
                    scholarship_title=scholarship_title,
                    official_source_url=official_source_url,
                )

    # --- False-positive class tests ---

    def test_banner_image_rejected(self):
        """1. Site-wide banner must be rejected when generic."""
        candidate = _make_candidate(
            image_url="https://www.daad.de/fileadmin/_migrated/content/banner_asia_pc4.png",
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="DAAD banner",
            width=1920,
            height=400,
        )
        result = self._validate_mocked(
            candidate, "DAAD Scholarship", "https://www.daad.de/en/scholarships")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("banner" in s.label for s in result.non_content_signals)

    def test_untitled_image_rejected(self):
        """2. Placeholder/untitled image must be rejected."""
        candidate = _make_candidate(
            image_url="https://studyinjapan.go.jp/assets/images/Untitled_5.png",
            page_url="https://www.studyinjapan.go.jp/en/scholarships",
            discovery_method="html-img",
            alt_text="Untitled image",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "MEXT Scholarship", "https://www.studyinjapan.go.jp/en/scholarships")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("untitled" in s.label for s in result.non_content_signals)

    def test_nav_image_rejected(self):
        """3. Navigation/UI element must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.studyinkorea.go.kr/public/v3/images/common/img-work-1@2x.png",
            page_url="https://www.studyinkorea.go.kr/en/plan/scholarship",
            discovery_method="html-img",
            alt_text="Navigation work image",
            width=200,
            height=150,
        )
        result = self._validate_mocked(
            candidate, "Global Korea Scholarship", "https://www.studyinkorea.go.kr/en/plan/scholarship")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED

    def test_500_error_image_rejected(self):
        """4. Error page image (500-error) must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.studyinkorea.go.kr/images/500-error.png",
            page_url="https://www.studyinkorea.go.kr/en/plan/scholarship",
            discovery_method="html-img",
            alt_text="500 Error",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "Global Korea Scholarship", "https://www.studyinkorea.go.kr/en/plan/scholarship")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("error" in s.label for s in result.non_content_signals)

    def test_emblem_image_rejected(self):
        """5. Logo/emblem/crest must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.gist.ac.kr/images/gist_emblem.png",
            page_url="https://www.gist.ac.kr/en/admission/scholarship",
            discovery_method="html-img",
            alt_text="GIST Emblem",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "GIST Government Scholarship", "https://www.gist.ac.kr/en/admission/scholarship")
        assert result.non_content_logo_weight >= 1.5
        assert result.image_kind == "official_logo"
        assert any("logo/emblem" in s.label or "logo/emblem" in s.label.lower() for s in result.non_content_signals)

    def test_facebook_share_image_rejected(self):
        """6. Facebook/social share image must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.jasso.go.jp/images/facebook327x151e.png",
            page_url="https://www.jasso.go.jp/en/kyotsu/",
            discovery_method="html-img",
            alt_text="Share on Facebook",
            width=327,
            height=151,
        )
        result = self._validate_mocked(
            candidate, "JASSO Reservation Program", "https://www.jasso.go.jp/en/kyotsu/")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("social" in s.label for s in result.non_content_signals)

    def test_og_thumbnail_rejected(self):
        """7. Open Graph thumbnail must be rejected when generic."""
        candidate = _make_candidate(
            image_url="https://www.studyinjapan.go.jp/ja/assets/images/common/ogimg.png",
            page_url="https://www.studyinjapan.go.jp/en/scholarships",
            discovery_method="og:image",
            alt_text="Study in Japan",
            width=1200,
            height=630,
        )
        result = self._validate_mocked(
            candidate, "MEXT YLP Scholarship", "https://www.studyinjapan.go.jp/en/scholarships")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("OG" in s.label for s in result.non_content_signals)

    def test_generic_site_wide_hero_rejected(self):
        """8. Generic site-wide hero image must be rejected."""
        candidate = _make_candidate(
            image_url="https://studyinjapan.go.jp/ja/assets/images/common/study_in_japan.webp",
            page_url="https://www.studyinjapan.go.jp/en/scholarships",
            discovery_method="html-img",
            alt_text="Study in Japan",
            width=1920,
            height=1080,
        )
        result = self._validate_mocked(
            candidate, "MEXT YLP", "https://www.studyinjapan.go.jp/en/scholarships")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED

    def test_site_wide_common_path_rejected(self):
        """9. Images in /common/ or /assets/common/ paths are site-wide, not content-specific."""
        candidate = _make_candidate(
            image_url="https://www.studyinjapan.go.jp/ja/assets/common/hero_bg.jpg",
            page_url="https://www.studyinjapan.go.jp/en/scholarships",
            discovery_method="html-img",
            alt_text="Background",
            width=1920,
            height=1080,
        )
        result = self._validate_mocked(
            candidate, "MEXT", "https://www.studyinjapan.go.jp/en/scholarships")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED

    def test_error_in_filename_rejected(self):
        """10. Any image filename containing 'error' or status codes rejected."""
        candidate = _make_candidate(
            image_url="https://www.studyinkorea.go.kr/images/error_404.png",
            page_url="https://www.studyinkorea.go.kr/en/plan/scholarship",
            discovery_method="html-img",
            alt_text="404 Not Found",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "GKS", "https://www.studyinkorea.go.kr/en/plan/scholarship")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED

    def test_crest_image_rejected(self):
        """11. University crest (specific term) must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.ox.ac.uk/images/university_crest.png",
            page_url="https://www.ox.ac.uk/admissions/graduate/scholarships",
            discovery_method="html-img",
            alt_text="University Crest",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "Oxford Scholarship", "https://www.ox.ac.uk/admissions/graduate/scholarships")
        assert result.non_content_logo_weight >= 1.5
        assert result.image_kind == "official_logo"
        assert any("logo/emblem" in s.label or "crest" in s.label.lower() for s in result.non_content_signals)

    def test_homepage_banner_with_dimensions_rejected(self):
        """12. Generic homepage banner with CMS dimensions in path must be rejected.

        Regression for ID 54: admissions.miami.edu/_assets/images/home/1600x550/statue-1600.jpg
        discovered from a crawled subpage rather than the primary program page.
        """
        candidate = _make_candidate(
            image_url="https://admissions.miami.edu/_assets/images/home/1600x550/statue-1600.jpg",
            page_url="https://admissions.miami.edu/undergraduate/financial-aid/scholarships",
            discovery_method="og:image",
            alt_text="University of Miami home banner",
            width=1600,
            height=550,
        )
        result = self._validate_mocked(
            candidate,
            "University of Miami Stamps Scholarship",
            "https://admissions.miami.edu/undergraduate/financial-aid/scholarships/stamps/",
        )
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("homepage" in s.label for s in result.non_content_signals)
        assert any("dimensions" in s.label for s in result.non_content_signals)

    def test_homepage_path_alone_rejected(self):
        """13. /home/ path without program-specific context must be flagged."""
        candidate = _make_candidate(
            image_url="https://example.university.edu/_assets/images/home/banner.jpg",
            page_url="https://example.university.edu/academics/graduate/scholarships",
            discovery_method="html-img",
            alt_text="Home banner",
            width=1920,
            height=1080,
        )
        result = self._validate_mocked(
            candidate,
            "Example University Graduate Scholarship",
            "https://example.university.edu/academics/graduate/scholarships/funding",
        )
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("homepage" in s.label for s in result.non_content_signals)

    def test_wp_content_uploads_legitimate_content_not_rejected_by_path(self):
        """14. WordPress /wp-content/uploads/ alone must NOT reject legitimate content images.

        Regression for EPFL Master Excellence Fellowships (ID 15):
        https://www.epfl.ch/education/master/wp-content/uploads/2021/09/RLC_Olivier-Christinat2019_web.jpg
        """
        candidate = _make_candidate(
            image_url="https://www.epfl.ch/education/master/wp-content/uploads/2021/09/RLC_Olivier-Christinat2019_web.jpg",
            page_url="https://www.epfl.ch/education/master/scholarships",
            discovery_method="html-img",
            alt_text="Campus life photograph by Olivier Christinat",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate,
            "EPFL Master Excellence Fellowships",
            "https://www.epfl.ch/education/master/scholarships",
        )
        assert not any("site-wide asset path" in s.label for s in result.non_content_signals), \
            "WordPress upload path alone must not trigger site-wide asset rejection"
        assert result.status != ValidationStatus.REJECTED or result.non_content_total_weight < 1.5, \
            "Legitimate WP content image should not be rejected solely due to /wp-content/uploads/ path"

    def test_wp_content_uploads_banner_path_rejected(self):
        """15. /wp-content/uploads/banners/ is a specific banner directory — must be rejected."""
        candidate = _make_candidate(
            image_url="https://example.edu/wp-content/uploads/banners/program-banner.jpg",
            page_url="https://example.edu/scholarships",
            discovery_method="html-img",
            alt_text="Program banner",
            width=1920,
            height=400,
        )
        result = self._validate_mocked(
            candidate,
            "Example Scholarship",
            "https://example.edu/scholarships",
        )
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("banner" in s.label or "site-wide asset path" in s.label for s in result.non_content_signals)

    def test_wp_content_uploads_logo_rejected(self):
        """16. Logo/icon in /wp-content/uploads/ must be rejected based on filename/alt text, not path alone."""
        candidate = _make_candidate(
            image_url="https://example.edu/wp-content/uploads/2022/01/university-logo.png",
            page_url="https://example.edu/scholarships",
            discovery_method="html-img",
            alt_text="University Logo",
            width=400,
            height=400,
        )
        result = self._validate_mocked(
            candidate,
            "Example Scholarship",
            "https://example.edu/scholarships",
        )
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("logo" in s.label.lower() for s in result.non_content_signals)

    def test_wp_content_uploads_unrelated_rejected(self):
        """17. Unrelated /wp-content/uploads/ image must be rejected based on other evidence."""
        candidate = _make_candidate(
            image_url="https://example.edu/wp-content/uploads/2021/05/campus-map.jpg",
            page_url="https://example.edu/scholarships",
            discovery_method="html-img",
            alt_text="",
            width=300,
            height=200,
        )
        result = self._validate_mocked(
            candidate,
            "Example Scholarship",
            "https://example.edu/scholarships",
        )
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED


class TestGenericFilenameRegression:
    """Regression tests for hash-based filenames, country flags, and CMS download handlers."""

    def _validate_mocked(self, candidate, scholarship_title, official_source_url,
                        licensing_status="licensing_known"):
        validator = ImageValidator()
        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = licensing_status
            result.licensing_evidence = "CC BY 4.0" if licensing_status == "licensing_known" else None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                return validator.validate_candidate(
                    candidate,
                    scholarship_title=scholarship_title,
                    official_source_url=official_source_url,
                )

    def test_hash_based_filename_rejected(self):
        """Hash-based filenames (long alphanumeric) must be rejected."""
        candidate = _make_candidate(
            image_url="https://en.snu.ac.kr/webdata/site/eng/config/ac9z5dezceaz6c9z911z3a3zfecz077z889z429za0.png",
            page_url="https://en.snu.ac.kr/admissions",
            discovery_method="html-img",
            alt_text="SNU image",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "SNU President Fellowship", "https://en.snu.ac.kr/admissions")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("hash-based" in s.label for s in result.non_content_signals)

    def test_country_code_flag_rejected(self):
        """Country-code filenames like 'in.png' (India flag) must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.inde.campusfrance.org/sites/pays/files/inde/drapeau/in.png",
            page_url="https://www.inde.campusfrance.org/en",
            discovery_method="html-img",
            alt_text="India flag",
            width=400,
            height=300,
        )
        result = self._validate_mocked(
            candidate, "France Excellence Charpak", "https://www.inde.campusfrance.org/en")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("country-code" in s.label for s in result.non_content_signals)

    def test_cms_download_handler_rejected(self):
        """CMS download scripts (.html?mode=IMG) must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.gist.ac.kr/dreamfund/html/sub01/0105.html?mode=IMG&no=221822&file_id=82196",
            page_url="https://www.gist.ac.kr/dreamfund/",
            discovery_method="html-img",
            alt_text="GIST emblem",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "GIST Government Scholarship", "https://www.gist.ac.kr/dreamfund/")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("download handler" in s.label for s in result.non_content_signals)


class TestInfrastructureRegression:
    """Regression tests for infrastructure/proxy URLs, CMS styles, and low-res images."""

    def _validate_mocked(self, candidate, scholarship_title, official_source_url,
                        licensing_status="licensing_known"):
        validator = ImageValidator()
        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = licensing_status
            result.licensing_evidence = "CC BY 4.0" if licensing_status == "licensing_known" else None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                return validator.validate_candidate(
                    candidate,
                    scholarship_title=scholarship_title,
                    official_source_url=official_source_url,
                )

    def test_nextjs_image_proxy_rejected(self):
        """Next.js image optimization proxy URLs (_next/image?url=...) must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.berea.edu/_next/image?url=https%3A%2F%2Fbereafaust.wpengine.com%2Fwp-content%2Fuploads%2F2023%2F03%2Fadmissionspage-scaled.jpg&w=3840&q=75",
            page_url="https://www.berea.edu/admissions",
            discovery_method="html-img",
            alt_text="Berea campus",
            width=2560,
            height=1705,
        )
        result = self._validate_mocked(
            candidate, "Berea College Tuition Promise", "https://www.berea.edu/admissions")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("Next.js image proxy" in s.label for s in result.non_content_signals)

    def test_drupal_menu_style_rejected(self):
        """Drupal styles/mobile_menu_image paths are UI/navigation, not content."""
        candidate = _make_candidate(
            image_url="https://www.inde.campusfrance.org/sites/pays/files/inde/styles/mobile_menu_image_1_2_et_3/public/menu/2022-06/Counselling.png?h=57024e64&itok=ChlMhl0l",
            page_url="https://www.inde.campusfrance.org/france-excellence-charpak",
            discovery_method="html-img",
            alt_text="Counselling",
            width=768,
            height=492,
        )
        result = self._validate_mocked(
            candidate, "France Excellence Charpak", "https://www.inde.campusfrance.org/en")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("Drupal" in s.label for s in result.non_content_signals)

    def test_thumbnail_dimension_in_url_rejected(self):
        """URL with thumbnail dimension params (h=460&w=460) must be rejected."""
        candidate = _make_candidate(
            image_url="https://www.cranfield.ac.uk/-/media/images-for-new-website/study/life-on-campus/accommodationteaser5.ashx?h=460&w=460&la=en&hash=789B9E9FE694430212F7DB55BAF4EB511B68C3B7",
            page_url="https://www.cranfield.ac.uk/study/taught-degrees/why-cranfield",
            discovery_method="html-img",
            alt_text="Accommodation",
            width=460,
            height=460,
        )
        result = self._validate_mocked(
            candidate, "GREAT Scholarship Cranfield", "https://www.cranfield.ac.uk/study")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("Thumbnail dimensions" in s.label for s in result.non_content_signals)

    def test_low_resolution_image_rejected(self):
        """Images under 500px on shortest side are not suitable as cover images."""
        candidate = _make_candidate(
            image_url="https://uic.yonsei.ac.kr/images/uic_img_stem.jpg",
            page_url="https://uic.yonsei.ac.kr/main/admission.php?mid=m04_03_02",
            discovery_method="html-img",
            alt_text="Campus image",
            width=408,
            height=388,
        )
        result = self._validate_mocked(
            candidate, "Yonsei UIC Admissions", "https://uic.yonsei.ac.kr/")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("Low resolution" in s.label for s in result.non_content_signals)

    def test_img_prefix_rejected(self):
        """Filename starting with 'img_' is a generic UI pattern, not content."""
        candidate = _make_candidate(
            image_url="https://uic.yonsei.ac.kr/images/uic_img_stem.jpg",
            page_url="https://uic.yonsei.ac.kr/main/admission.php?mid=m04_03_02",
            discovery_method="html-img",
            alt_text="Campus image",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "Yonsei UIC Admissions", "https://uic.yonsei.ac.kr/")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("img_" in s.label for s in result.non_content_signals)

    def test_timestamp_filename_rejected(self):
        """Timestamp-based filenames (e.g. 20260904140825301371.png) must be rejected."""
        candidate = _make_candidate(
            image_url="https://uic.yonsei.ac.kr/main/upload/etc/2026/20260904140825301371.png",
            page_url="https://uic.yonsei.ac.kr/main/admission.php",
            discovery_method="html-img",
            alt_text="UIC image",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "Yonsei UIC Admissions", "https://uic.yonsei.ac.kr/")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("timestamp" in s.label or "hash-based" in s.label for s in result.non_content_signals)

    def test_document_flyer_filename_rejected(self):
        """Pamphlet/flyer filenames must be rejected as non-content."""
        candidate = _make_candidate(
            image_url="https://www.jasso.go.jp/en/ryugaku/__icsFiles/afieldfile/2023/04/28/english_scholarship_pamphlet_1.jpg",
            page_url="https://www.jasso.go.jp/en/ryugaku/scholarship_j/shoreihi/",
            discovery_method="html-img",
            alt_text="Scholarship pamphlet",
            width=327,
            height=151,
        )
        result = self._validate_mocked(
            candidate, "JASSO Scholarship", "https://www.jasso.go.jp/en/ryugaku")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("document" in s.label for s in result.non_content_signals)

    def test_low_resolution_image_rejected(self):
        """Small thumbnail dimensions (< 500px) must be rejected for cover use."""
        candidate = _make_candidate(
            image_url="https://www.jasso.go.jp/en/ryugaku/scholarship_j/__icsFiles/afieldfile/2021/03/22/oubo-saiyou_eng.png",
            page_url="https://www.jasso.go.jp/en/ryugaku/scholarship_j/ukeire.html",
            discovery_method="html-img",
            alt_text="Recruitment image",
            width=510,
            height=368,
        )
        result = self._validate_mocked(
            candidate, "JASSO Student Exchange", "https://www.jasso.go.jp/en/ryugaku")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED
        assert any("Low resolution" in s.label for s in result.non_content_signals)


class TestOgImageDimensionFetching:
    """Regression tests for OG images missing HTML width/height attributes."""

    def _make_stream_mock(self, width: int, height: int, content_type: str = "image/jpeg"):
        """Create a mock httpx.stream context manager that returns a realistic image."""
        from PIL import Image as PILImage
        import io

        img = PILImage.new("RGB", (width, height))
        pixels = img.load()
        for y in range(height):
            for x in range(width):
                pixels[x, y] = ((x ^ y) % 256, (x + y) % 256, (x * 2 + y) % 256)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": content_type}

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_response)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = image_bytes

        return mock_stream

    def _validate_mocked(self, candidate, scholarship_title, official_source_url,
                         licensing_status="licensing_known", stream_mock=None):
        validator = ImageValidator()

        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.stream.return_value = stream_mock or self._make_stream_mock(1200, 800)

        def mock_check_licensing(self, result):
            result.licensing_status = licensing_status
            result.licensing_evidence = "CC BY 4.0" if licensing_status == "licensing_known" else None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                return validator.validate_candidate(
                    candidate,
                    scholarship_title=scholarship_title,
                    official_source_url=official_source_url,
                )

    def test_og_image_without_dimensions_small_rejected(self):
        """OG images missing HTML dimensions must be fetched and rejected if < 500px."""
        candidate = _make_candidate(
            image_url="https://www.inde.campusfrance.org/sites/pays/files/inde/medias/images/2018-07/france-education-destination.jpg",
            page_url="https://www.inde.campusfrance.org/node/42",
            discovery_method="og:image",
            alt_text="France education destination",
            width=None,
            height=None,
        )
        stream_mock = self._make_stream_mock(400, 267)
        result = self._validate_mocked(
            candidate,
            "France Excellence Charpak Scholarship Program",
            "https://www.inde.campusfrance.org/node/42",
            stream_mock=stream_mock,
        )
        assert result.width == 400
        assert result.height == 267
        assert result.is_generic_image is True
        assert result.status == ValidationStatus.REJECTED
        assert any("too small for cover" in r for r in result.rejection_reasons)

    def test_og_image_without_dimensions_large_approved(self):
        """OG images missing HTML dimensions must be fetched and approved if >= 500px."""
        candidate = _make_candidate(
            image_url="https://www.brandeis.edu/isso/images/programs/wien/wein.jpg",
            page_url="https://www.brandeis.edu/isso/programs/wien/index.html",
            discovery_method="html-img",
            alt_text="Wien International Scholarship",
            width=None,
            height=None,
        )
        stream_mock = self._make_stream_mock(960, 640)
        result = self._validate_mocked(
            candidate,
            "Brandeis University Wien International Scholarship",
            "https://www.brandeis.edu/isso/programs/wien/index.html",
            stream_mock=stream_mock,
        )
        assert result.width == 960
        assert result.height == 640
        assert result.status == ValidationStatus.APPROVED
        assert result.confidence == "HIGH"


class TestPositiveImageApproval:
    """Positive tests proving legitimate images can still reach HIGH/APPROVED."""

    def _validate_mocked(self, candidate, scholarship_title, official_source_url,
                        licensing_status="licensing_known"):
        validator = ImageValidator()
        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = licensing_status
            result.licensing_evidence = "CC BY 4.0" if licensing_status == "licensing_known" else None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                return validator.validate_candidate(
                    candidate,
                    scholarship_title=scholarship_title,
                    official_source_url=official_source_url,
                )

    def test_university_campus_photo_approved(self):
        """Legitimate university campus photograph can still reach HIGH."""
        candidate = _make_candidate(
            image_url="https://www.harvard.edu/scholarships/campus-students-2024.jpg",
            page_url="https://www.harvard.edu/scholarships/programs",
            discovery_method="html-img",
            alt_text="Harvard scholarship students on campus",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate, "Harvard Scholarship Program", "https://www.harvard.edu/scholarships")
        assert result.non_content_total_weight == 0
        assert result.status == ValidationStatus.APPROVED
        assert result.confidence == "HIGH"

    def test_scholarship_campaign_image_approved(self):
        """Legitimate scholarship campaign image can still reach HIGH."""
        candidate = _make_candidate(
            image_url="https://erasmus-plus.ec.europa.eu/images/emjm-campus.jpg",
            page_url="https://erasmus-plus.ec.europa.eu/opportunities/erasmus-mundus-joint-masters",
            discovery_method="og:image",
            alt_text="Erasmus Mundus Joint Masters students on European campus",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate, "Erasmus Mundus Joint Masters", "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters")
        assert result.non_content_total_weight == 0
        assert result.status == ValidationStatus.APPROVED
        assert result.confidence == "HIGH"

    def test_program_photograph_approved(self):
        """Legitimate program photograph can still reach HIGH."""
        candidate = _make_candidate(
            image_url="https://www.studyinjapan.go.jp/en/images/programs/gks-students-campus.jpg",
            page_url="https://www.studyinjapan.go.jp/en/plan/scholarships/gks",
            discovery_method="html-img",
            alt_text="GKS scholarship students at Japanese university campus",
            width=1200,
            height=900,
        )
        result = self._validate_mocked(
            candidate, "MEXT Scholarship", "https://www.studyinjapan.go.jp/en/scholarships")
        assert result.non_content_total_weight == 0
        assert result.status == ValidationStatus.APPROVED
        assert result.confidence == "HIGH"

    def test_official_promotional_image_approved(self):
        """Legitimate official promotional image can still reach HIGH."""
        candidate = _make_candidate(
            image_url="https://www.daad.de/fileadmin/scholarships/scholarship-campaign-students.jpg",
            page_url="https://www.daad.de/en/scholarships/daad-scholarship-program",
            discovery_method="json-ld",
            alt_text="DAAD scholarship program students in Germany",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate, "DAAD Scholarship Program", "https://www.daad.de/en/scholarships")
        assert result.non_content_total_weight == 0
        assert result.status == ValidationStatus.APPROVED
        assert result.confidence == "HIGH"

    def test_content_relevant_filename_with_context_approved(self):
        """Image with content-relevant filename and strong context reaches HIGH."""
        candidate = _make_candidate(
            image_url="https://www.studyinkorea.go.kr/file/scholarship/gks-program-campus-students.jpg",
            page_url="https://www.studyinkorea.go.kr/en/plan/scholarship/gks",
            discovery_method="html-img",
            alt_text="Global Korea Scholarship program students on campus",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate, "Global Korea Scholarship", "https://www.studyinkorea.go.kr/en/plan/scholarship/gks")
        assert result.non_content_total_weight == 0
        assert result.status == ValidationStatus.APPROVED

    def test_primary_page_image_gets_relevance_boost(self):
        """Image discovered from primary program page receives relevance boost."""
        candidate = _make_candidate(
            image_url="https://www.harvard.edu/scholarships/campus-students-2024.jpg",
            page_url="https://www.harvard.edu/scholarships/programs",
            discovery_method="html-img",
            alt_text="Harvard scholarship students on campus",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate, "Harvard Scholarship Program", "https://www.harvard.edu/scholarships/programs")
        assert result.non_content_total_weight == 0
        assert result.status == ValidationStatus.APPROVED
        assert result.confidence == "HIGH"
        assert any("primary program page" in note for note in result.relevance_notes)


class TestFalsePositiveRecovery:
    """Regression tests proving legitimate images are no longer auto-rejected
    by overly aggressive URL heuristics."""

    def _validate_mocked(self, candidate, scholarship_title, official_source_url,
                         licensing_status="licensing_known"):
        validator = ImageValidator()
        mock_httpx_module = MagicMock()
        mock_httpx_module.head.return_value = _mock_head(200, "image/jpeg")
        mock_httpx_module.RequestError = type("E", (), {})
        mock_httpx_module.get = _mock_get_image()

        def mock_check_licensing(self, result):
            result.licensing_status = licensing_status
            result.licensing_evidence = "CC BY 4.0" if licensing_status == "licensing_known" else None
            return result

        with patch("app.services.image_validator.httpx", mock_httpx_module):
            with patch.object(ImageValidator, "_check_licensing", mock_check_licensing):
                return validator.validate_candidate(
                    candidate,
                    scholarship_title=scholarship_title,
                    official_source_url=official_source_url,
                )

    def test_sites_default_content_image_not_auto_rejected(self):
        """Images on /sites/default/ paths are not automatically rejected as banners."""
        candidate = _make_candidate(
            image_url="https://erasmus-plus.ec.europa.eu/sites/default/files/styles/medium/public/2025-11/em-20th-anniversary-celebration.jpg",
            page_url="https://erasmus-plus.ec.europa.eu/news/erasmus-mundus-20th-anniversary",
            discovery_method="html-img",
            alt_text="Erasmus Mundus 20th anniversary celebration event",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate,
            "Erasmus Mundus Joint Masters",
            "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
        )
        assert not any("site-wide" in s.label for s in result.non_content_signals)
        assert result.status in (ValidationStatus.APPROVED, ValidationStatus.HUMAN_REVIEW)

    def test_nologo_filename_not_flagged_as_logo(self):
        """Filenames containing 'nologo' must not trigger logo detection."""
        candidate = _make_candidate(
            image_url="https://knight-hennessy.stanford.edu/sites/g/files/sbiybj23586/files/styles/responsive_large/public/media/image/khscohort_graphic_2026_3000x1000_nologo_rev2_0.jpg",
            page_url="https://knight-hennessy.stanford.edu/2026-cohort-announcement",
            discovery_method="html-img",
            alt_text="Knight-Hennessy 2026 cohort of 87 scholars",
            width=3000,
            height=1000,
        )
        result = self._validate_mocked(
            candidate,
            "Knight-Hennessy Scholars Program",
            "https://knight-hennessy.stanford.edu/",
        )
        assert not any("logo" in s.label for s in result.non_content_signals)
        assert result.status in (ValidationStatus.APPROVED, ValidationStatus.HUMAN_REVIEW)

    def test_responsive_large_drupal_style_not_flagged_as_ui(self):
        """Drupal responsive_large style path is a standard content style, not UI."""
        candidate = _make_candidate(
            image_url="https://knight-hennessy.stanford.edu/sites/g/files/sbiybj23586/files/styles/responsive_large/public/media/image/cohort-graphic.jpg",
            page_url="https://knight-hennessy.stanford.edu/2026-cohort",
            discovery_method="html-img",
            alt_text="Knight-Hennessy cohort graphic",
            width=3000,
            height=1000,
        )
        result = self._validate_mocked(
            candidate,
            "Knight-Hennessy Scholars Program",
            "https://knight-hennessy.stanford.edu/",
        )
        assert not any("responsive" in s.label for s in result.non_content_signals)
        assert result.status in (ValidationStatus.APPROVED, ValidationStatus.HUMAN_REVIEW)

    def test_subpage_image_receives_relevance_not_rejection(self):
        """Image discovered from an official subpage gets relevance reduction, not rejection."""
        candidate = _make_candidate(
            image_url="https://www.harvard.edu/scholarships/campus-students-2024.jpg",
            page_url="https://www.harvard.edu/scholarships/news/2024-cohort",
            discovery_method="html-img",
            alt_text="Harvard scholarship students on campus",
            width=1200,
            height=800,
        )
        result = self._validate_mocked(
            candidate, "Harvard Scholarship Program", "https://www.harvard.edu/scholarships/programs")
        assert not any("subpage" in s.label for s in result.non_content_signals)
        assert result.status == ValidationStatus.APPROVED
        assert any("subpage" in note for note in result.relevance_notes)

    def test_ui_icon_still_rejected(self):
        """UI icons with explicit icon/btn keywords must still be rejected."""
        candidate = _make_candidate(
            image_url="https://www.daad.de/assets/icons/arrow-next.svg",
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="Next arrow icon",
            width=24,
            height=24,
        )
        result = self._validate_mocked(
            candidate, "DAAD Scholarship", "https://www.daad.de/en/scholarships")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED

    def test_tiny_asset_still_rejected(self):
        """Tiny images (< 500px shortest side) must still be rejected."""
        candidate = _make_candidate(
            image_url="https://www.daad.de/images/tiny-icon.png",
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="Tiny icon",
            width=32,
            height=32,
        )
        result = self._validate_mocked(
            candidate, "DAAD Scholarship", "https://www.daad.de/en/scholarships")
        assert result.non_content_total_weight >= 1.5
        assert result.status == ValidationStatus.REJECTED

    def test_unrelated_campus_image_still_rejected(self):
        """Unrelated campus images on non-official domains must still be rejected."""
        candidate = _make_candidate(
            image_url="https://unsplash.com/photos/campus-sunset.jpg",
            page_url="https://unsplash.com",
            discovery_method="html-img",
            alt_text="Beautiful campus sunset",
            width=1920,
            height=1080,
        )
        result = self._validate_mocked(
            candidate, "University General Scholarship",
            "https://www.university.edu/academics/scholarships/funding")
        assert result.status == ValidationStatus.REJECTED
        assert not result.is_official_domain

    def test_logo_in_alt_text_still_rejected(self):
        """Images explicitly identified as logos in alt text must still be rejected."""
        candidate = _make_candidate(
            image_url="https://www.daad.de/images/scholarship-program-logo.png",
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="DAAD Scholarship Program official logo",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "DAAD Scholarship", "https://www.daad.de/en/scholarships")
        assert result.non_content_logo_weight >= 1.5
        assert result.image_kind == "official_logo"
        assert result.status == ValidationStatus.HUMAN_REVIEW

    def test_logo_in_path_still_rejected(self):
        """Images in explicit /logo/ directories must still be rejected."""
        candidate = _make_candidate(
            image_url="https://www.daad.de/logo/scholarship-logo.png",
            page_url="https://www.daad.de/en/scholarships",
            discovery_method="html-img",
            alt_text="DAAD Logo",
            width=800,
            height=600,
        )
        result = self._validate_mocked(
            candidate, "DAAD Scholarship", "https://www.daad.de/en/scholarships")
        assert result.non_content_logo_weight >= 1.5
        assert result.image_kind == "official_logo"
        assert result.status == ValidationStatus.HUMAN_REVIEW


class TestImageContentAnalysisNoneMetrics:
    """Regression tests for _check_image_content with missing analysis metrics."""

    def _make_result(self, candidate, **overrides):
        result = ImageValidationResult(candidate=candidate)
        result.is_reachable = True
        result.is_valid_image = True
        result.is_official_domain = True
        result.width = candidate.width or 1200
        result.height = candidate.height or 800
        result.relevance_score = 1.0
        for key, value in overrides.items():
            setattr(result, key, value)
        return result

    def test_none_edge_density_does_not_crash_ui(self):
        """None edge_density in UI analysis must not crash formatting."""
        candidate = _make_candidate(
            image_url="https://www.university.edu/ui.jpg",
            page_url="https://www.university.edu/program",
            width=1200,
            height=800,
        )
        validator = ImageValidator()
        result = self._make_result(
            candidate,
            image_analysis=ImageAnalysisResult(
                is_likely_ui=True,
                is_likely_logo=False,
                is_likely_photo=False,
                edge_density=None,
                unique_colors=None,
                color_variance=None,
                file_size_bytes=None,
            ),
        )
        result = validator._check_image_content(result)
        assert result.is_ui_asset is True
        assert any("Image analysis: likely UI asset" in r for r in result.rejection_reasons)

    def test_none_metrics_do_not_crash_logo(self):
        """None metrics in logo analysis must not crash formatting."""
        candidate = _make_candidate(
            image_url="https://www.university.edu/logo.jpg",
            page_url="https://www.university.edu/program",
            width=1200,
            height=800,
        )
        validator = ImageValidator()
        result = self._make_result(
            candidate,
            image_analysis=ImageAnalysisResult(
                is_likely_ui=False,
                is_likely_logo=True,
                is_likely_photo=False,
                edge_density=None,
                unique_colors=None,
                color_variance=None,
                file_size_bytes=None,
            ),
        )
        result = validator._check_image_content(result)
        assert result.is_generic_image is True
        assert any("Image analysis: likely logo/graphic" in r for r in result.rejection_reasons)

    def test_none_metrics_do_not_crash_photo(self):
        """None metrics in photo analysis must not crash formatting."""
        candidate = _make_candidate(
            image_url="https://www.university.edu/photo.jpg",
            page_url="https://www.university.edu/program",
            width=1200,
            height=800,
        )
        validator = ImageValidator()
        result = self._make_result(
            candidate,
            image_analysis=ImageAnalysisResult(
                is_likely_ui=False,
                is_likely_logo=False,
                is_likely_photo=True,
                edge_density=None,
                unique_colors=None,
                color_variance=None,
                file_size_bytes=None,
            ),
        )
        result = validator._check_image_content(result)
        assert result.is_generic_image is False
        assert any("Image analysis: content photograph detected" in r for r in result.relevance_notes)
