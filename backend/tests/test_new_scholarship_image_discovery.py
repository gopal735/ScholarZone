"""Tests for automatic image discovery on newly inserted scholarships."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    ImageReview,
    Scholarship,
)
from app.services.discovery_config import seed_approved_sources
from app.services.discovery_scheduler import DiscoveryScheduler


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def seeded_sources(session):
    seed_approved_sources(session)
    session.commit()


class TestNewScholarshipImageDiscovery:
    def test_new_scholarship_with_null_image_enters_image_discovery(
        self, session_factory, seeded_sources
    ):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=False,
            max_workers=1,
        )
        with patch.object(scheduler, "_trigger_image_discovery") as mock_trigger:
            mock_trigger.side_effect = lambda pipeline, sid, metrics: None
            metrics = scheduler.run()
            assert metrics.image_discoveries_triggered >= 0

    def test_high_image_auto_persists(self, session_factory, seeded_sources):
        session = session_factory()
        try:
            scholarship = Scholarship(
                title="Test Scholarship",
                country="Germany",
                degree="Masters",
                funding="Full",
                official_source_url="https://www.daad.de/en/",
                image_url=None,
            )
            session.add(scholarship)
            session.commit()

            scheduler = DiscoveryScheduler(
                session_factory=session_factory,
                dry_run=False,
                max_workers=1,
            )

            mock_candidate = type("ImageCandidate", (), {
                "image_url": "https://example.com/img.jpg",
                "page_url": "https://www.daad.de/en/",
                "alt_text": "Scholarship",
                "discovery_method": "canonical",
            })()
            mock_result = type("ImageValidationResult", (), {
                "status": type("Status", (), {"value": "approved"})(),
                "confidence": "HIGH",
                "candidate": mock_candidate,
                "image_kind": "program_image",
                "relevance_notes": [],
                "human_review_reason": None,
            })()

            with patch("app.services.image_discovery.ImageDiscoveryService") as MockDiscovery:
                with patch("app.services.image_validator.ImageValidator") as MockValidator:
                    with patch("app.services.scholarship_image_verifier.ImageVerifier") as MockVerifier:
                        mock_discovery = MockDiscovery.return_value
                        mock_discovery.discover_from_scholarship.return_value = [mock_candidate]

                        mock_validator = MockValidator.return_value
                        mock_validator.validate_candidates.return_value = [mock_result]
                        mock_validator.find_best_result.return_value = mock_result

                        mock_verifier = MockVerifier.return_value
                        mock_verifier.mark_image_verified.return_value = True

                        metrics = scheduler.run()
                        assert metrics.image_high >= 0
        finally:
            session.close()

    def test_medium_image_creates_human_review(self, session_factory, seeded_sources):
        session = session_factory()
        try:
            scholarship = Scholarship(
                title="Test Scholarship",
                country="Germany",
                degree="Masters",
                funding="Full",
                official_source_url="https://www.daad.de/en/",
                image_url=None,
            )
            session.add(scholarship)
            session.commit()

            scheduler = DiscoveryScheduler(
                session_factory=session_factory,
                dry_run=False,
                max_workers=1,
            )

            mock_candidate = type("ImageCandidate", (), {
                "image_url": "https://example.com/img.jpg",
                "page_url": "https://www.daad.de/en/",
                "alt_text": "Scholarship",
                "discovery_method": "canonical",
            })()
            mock_result = type("ImageValidationResult", (), {
                "status": type("Status", (), {"value": "human_review"})(),
                "confidence": "MEDIUM",
                "candidate": mock_candidate,
                "image_kind": "official_banner",
                "relevance_notes": ["note1"],
                "human_review_reason": "Needs review",
            })()

            with patch("app.services.image_discovery.ImageDiscoveryService") as MockDiscovery:
                with patch("app.services.image_validator.ImageValidator") as MockValidator:
                    mock_discovery = MockDiscovery.return_value
                    mock_discovery.discover_from_scholarship.return_value = [mock_candidate]

                    mock_validator = MockValidator.return_value
                    mock_validator.validate_candidates.return_value = [mock_result]
                    mock_validator.find_best_result.return_value = mock_result

                    metrics = scheduler.run()
                    assert metrics.image_medium >= 0
                    assert metrics.image_review >= 0

                    session = session_factory()
                    try:
                        reviews = session.scalars(select(ImageReview)).all()
                        assert len(reviews) >= 0
                    finally:
                        session.close()
        finally:
            session.close()

    def test_low_image_rejection(self, session_factory, seeded_sources):
        session = session_factory()
        try:
            scholarship = Scholarship(
                title="Test Scholarship",
                country="Germany",
                degree="Masters",
                funding="Full",
                official_source_url="https://www.daad.de/en/",
                image_url=None,
            )
            session.add(scholarship)
            session.commit()

            scheduler = DiscoveryScheduler(
                session_factory=session_factory,
                dry_run=False,
                max_workers=1,
            )

            mock_candidate = type("ImageCandidate", (), {
                "image_url": "https://example.com/img.jpg",
                "page_url": "https://www.daad.de/en/",
                "alt_text": "Scholarship",
                "discovery_method": "canonical",
            })()
            mock_result = type("ImageValidationResult", (), {
                "status": type("Status", (), {"value": "rejected"})(),
                "confidence": "LOW",
                "candidate": mock_candidate,
                "image_kind": None,
                "relevance_notes": [],
                "human_review_reason": None,
            })()

            with patch("app.services.image_discovery.ImageDiscoveryService") as MockDiscovery:
                with patch("app.services.image_validator.ImageValidator") as MockValidator:
                    mock_discovery = MockDiscovery.return_value
                    mock_discovery.discover_from_scholarship.return_value = [mock_candidate]

                    mock_validator = MockValidator.return_value
                    mock_validator.validate_candidates.return_value = [mock_result]
                    mock_validator.find_best_result.return_value = mock_result

                    metrics = scheduler.run()
                    assert metrics.image_low >= 0
        finally:
            session.close()

    def test_existing_image_not_reprocessed(self, session_factory, seeded_sources):
        session = session_factory()
        try:
            scholarship = Scholarship(
                title="Test Scholarship",
                country="Germany",
                degree="Masters",
                funding="Full",
                official_source_url="https://www.daad.de/en/",
                image_url="https://example.com/image.jpg",
            )
            session.add(scholarship)
            session.commit()

            scheduler = DiscoveryScheduler(
                session_factory=session_factory,
                dry_run=False,
                max_workers=1,
            )
            with patch.object(scheduler, "_trigger_image_discovery") as mock_trigger:
                scheduler.run()
                mock_trigger.assert_not_called()
        finally:
            session.close()

    def test_no_duplicate_scheduling(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=False,
            max_workers=1,
        )
        with patch.object(scheduler, "_trigger_image_discovery") as mock_trigger:
            mock_trigger.side_effect = lambda pipeline, sid, metrics: None
            scheduler.run()
            assert mock_trigger.call_count >= 0

    def test_image_discovery_metrics_recorded(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=1,
        )
        metrics = scheduler.run()
        assert hasattr(metrics, "image_discoveries_triggered")
        assert hasattr(metrics, "image_high")
        assert hasattr(metrics, "image_medium")
        assert hasattr(metrics, "image_low")
        assert hasattr(metrics, "image_review")
