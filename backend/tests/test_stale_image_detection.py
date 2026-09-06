"""Regression tests for stale image detection and safe revalidation.

Covers:
- stored image still present -> CURRENT
- stored image no longer present -> HUMAN_REVIEW (CHANGED/REMOVED)
- source inaccessible -> safe fallback
- image URL changed -> audit event
- repeated identical revalidation -> idempotent
- no accidental scholarship modification
- missing image or source -> HUMAN_REVIEW without mutation
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, ScholarshipReview, ScholarshipVerificationHistory
from app.services.scholarship_image_verifier import (
    ImageVerifier,
    StaleImageStatus,
    StaleImageResult,
)


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_scholarship(session, title="Test Scholarship", image_url=None, official_source_url=None) -> int:
    scholarship = Scholarship(
        title=title,
        country="Testland",
        degree="Master",
        funding="Fully Funded",
        official_source_url=official_source_url,
        image_url=image_url,
    )
    session.add(scholarship)
    session.commit()
    return scholarship.id


class MockPageResult:
    def __init__(self, url="https://example.com/program/test", status_code=200, content=None, error=None):
        self.url = url
        self.status_code = status_code
        self.content = content
        self.error = error


class TestStaleImageCurrent:
    def test_image_still_present_returns_current(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://example.com/images/cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://example.com/images/cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result = verifier.check_stale_image(in_memory_session.get(Scholarship, scholarship_id))

        assert result.status == StaleImageStatus.CURRENT
        assert result.action_taken == "none"

    def test_current_revalidation_updates_timestamp(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://example.com/images/cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://example.com/images/cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result = verifier.revalidate_stored_image(scholarship_id)

        assert result.status == StaleImageStatus.CURRENT
        assert result.action_taken == "timestamp_updated"

        refreshed = in_memory_session.get(Scholarship, scholarship_id)
        assert refreshed.image_verified_at is not None


class TestStaleImageRemoved:
    def test_image_removed_no_replacement_returns_removed(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/old-cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://other-domain.com/images/cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://other-domain.com/images/cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result = verifier.check_stale_image(in_memory_session.get(Scholarship, scholarship_id))

        assert result.status == StaleImageStatus.REMOVED


class TestStaleImageChanged:
    def test_image_changed_same_domain_returns_changed(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/old-cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://example.com/images/new-cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://example.com/images/new-cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result = verifier.check_stale_image(in_memory_session.get(Scholarship, scholarship_id))

        assert result.status == StaleImageStatus.CHANGED


class TestStaleImageSourceInaccessible:
    def test_source_inaccessible_returns_source_inaccessible(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            status_code=503,
            error="Service Unavailable",
        )

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result = verifier.check_stale_image(in_memory_session.get(Scholarship, scholarship_id))

        assert result.status == StaleImageStatus.SOURCE_INACCESSIBLE


class TestStaleImageMissingData:
    def test_missing_image_url_returns_human_review(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url=None,
            official_source_url="https://example.com/program/test",
        )

        verifier = ImageVerifier(in_memory_session)
        result = verifier.check_stale_image(in_memory_session.get(Scholarship, scholarship_id))

        assert result.status == StaleImageStatus.HUMAN_REVIEW
        assert result.action_taken == "none"

    def test_missing_official_source_url_returns_human_review(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/cover.jpg",
            official_source_url=None,
        )

        verifier = ImageVerifier(in_memory_session)
        result = verifier.check_stale_image(in_memory_session.get(Scholarship, scholarship_id))

        assert result.status == StaleImageStatus.HUMAN_REVIEW
        assert result.action_taken == "none"


class TestRevalidationSafeActions:
    def test_removed_creates_review_and_audit(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/old-cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://other-domain.com/images/cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://other-domain.com/images/cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result = verifier.revalidate_stored_image(scholarship_id)

        assert result.status == StaleImageStatus.REMOVED
        assert result.action_taken == "review_created"

        review = in_memory_session.execute(
            select(ScholarshipReview).where(
                ScholarshipReview.scholarship_id == scholarship_id,
                ScholarshipReview.field_name == "image_url",
                ScholarshipReview.decision == "pending",
            )
        ).scalar_one_or_none()
        assert review is not None
        assert review.conflict_reason == "stale_image_removed"

        history = in_memory_session.execute(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship_id,
                ScholarshipVerificationHistory.field_name == "image_url",
                ScholarshipVerificationHistory.change_type == "stale_detected",
            )
        ).scalars().all()
        assert len(history) == 1

        refreshed = in_memory_session.get(Scholarship, scholarship_id)
        assert refreshed.image_url == "https://example.com/images/old-cover.jpg"

    def test_source_inaccessible_does_not_clear_image(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            status_code=503,
            error="Service Unavailable",
        )

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result = verifier.revalidate_stored_image(scholarship_id)

        assert result.status == StaleImageStatus.SOURCE_INACCESSIBLE
        assert result.action_taken == "review_created"

        refreshed = in_memory_session.get(Scholarship, scholarship_id)
        assert refreshed.image_url == "https://example.com/images/cover.jpg"


class TestRevalidationIdempotency:
    def test_repeated_current_does_not_duplicate_history(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://example.com/images/cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://example.com/images/cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            verifier.revalidate_stored_image(scholarship_id)
            verifier.revalidate_stored_image(scholarship_id)

        history = in_memory_session.execute(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship_id
            )
        ).scalars().all()
        assert len(history) == 0

    def test_repeated_removed_does_not_duplicate_review(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/old-cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://other-domain.com/images/cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://other-domain.com/images/cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            result1 = verifier.revalidate_stored_image(scholarship_id)
            result2 = verifier.revalidate_stored_image(scholarship_id)

        assert result1.action_taken == "review_created"
        assert result2.action_taken == "review_already_exists"

        reviews = in_memory_session.execute(
            select(ScholarshipReview).where(
                ScholarshipReview.scholarship_id == scholarship_id,
                ScholarshipReview.field_name == "image_url",
            )
        ).scalars().all()
        assert len(reviews) == 1

    def test_repeated_removed_does_not_duplicate_stale_history_within_12h(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/old-cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        html = '<html><head><meta property="og:image" content="https://other-domain.com/images/cover.jpg"></head></html>'
        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            content=html,
        )
        mock_discovery.extract_images_from_html.return_value = [
            MagicMock(image_url="https://other-domain.com/images/cover.jpg"),
        ]

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            with patch("app.services.scholarship_image_verifier.datetime") as mock_dt:
                now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
                mock_dt.now.return_value = now
                verifier.revalidate_stored_image(scholarship_id)

                twelve_hours_later = datetime(2026, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
                mock_dt.now.return_value = twelve_hours_later
                result2 = verifier.revalidate_stored_image(scholarship_id)

        assert result2.action_taken == "review_already_exists"


class TestNoAccidentalScholarshipModification:
    def test_revalidation_never_clears_image_fields(self, in_memory_session):
        scholarship_id = _make_scholarship(
            in_memory_session,
            image_url="https://example.com/images/cover.jpg",
            official_source_url="https://example.com/program/test",
        )

        mock_discovery = MagicMock()
        mock_discovery.fetch_page.return_value = MockPageResult(
            url="https://example.com/program/test",
            status_code=503,
            error="Service Unavailable",
        )

        verifier = ImageVerifier(in_memory_session)
        with patch("app.services.image_discovery.ImageDiscoveryService", return_value=mock_discovery):
            verifier.revalidate_stored_image(scholarship_id)

        refreshed = in_memory_session.get(Scholarship, scholarship_id)
        assert refreshed.image_url == "https://example.com/images/cover.jpg"
        assert refreshed.image_source_url is None
        assert refreshed.image_source_type is None
        assert refreshed.image_alt_text is None
        assert refreshed.image_verified_at is None


class TestUrlNormalization:
    def test_trailing_slash_normalized(self):
        from app.services.scholarship_image_verifier import _normalize_url

        assert _normalize_url("https://example.com/images/cover.jpg/") == _normalize_url("https://example.com/images/cover.jpg")

    def test_www_prefix_stripped(self):
        from app.services.scholarship_image_verifier import _normalize_url

        assert _normalize_url("https://www.example.com/images/cover.jpg") == _normalize_url("https://example.com/images/cover.jpg")

    def test_case_insensitive_domain(self):
        from app.services.scholarship_image_verifier import _normalize_url

        assert _normalize_url("https://Example.COM/images/cover.jpg") == _normalize_url("https://example.com/images/cover.jpg")
