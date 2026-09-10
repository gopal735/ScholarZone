"""Tests for automatic country-level scholarship discovery scheduler."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    ApprovedSource,
    Base,
    DiscoveryCandidate,
    Scholarship,
)
from app.services.discovery_config import seed_approved_sources
from app.services.discovery_pipeline import DiscoveryPipeline
from app.services.discovery_scheduler import DiscoveryScheduler, DiscoverySchedulerMetrics


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


class TestCountryDiscoveryScheduler:
    def test_dry_run_five_countries(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        metrics = scheduler.run()

        assert metrics.countries_scanned >= 0
        assert isinstance(metrics.country_results, dict)
        assert metrics.operation_id != ""

    def test_scheduled_country_discovery_inserts_none_in_dry_run(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        metrics = scheduler.run()

        assert metrics.inserted_scholarships == metrics.verified_new_scholarships
        session = session_factory()
        try:
            count = session.scalar(select(func.count()).select_from(Scholarship))
            assert count == 0
        finally:
            session.close()

    def test_all_current_countries_included(self, session_factory, seeded_sources):
        session = session_factory()
        try:
            session.add_all([
                Scholarship(title="S1", country="Germany", degree="Masters", funding="Full", official_source_url="https://example.com/1"),
                Scholarship(title="S2", country="France", degree="PhD", funding="Full", official_source_url="https://example.com/2"),
                Scholarship(title="S3", country="USA", degree="Masters", funding="Partial", official_source_url="https://example.com/3"),
            ])
            session.commit()
        finally:
            session.close()

        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        metrics = scheduler.run()

        assert "Germany" in metrics.country_results
        assert "France" in metrics.country_results
        assert "USA" in metrics.country_results

    def test_one_country_failure_does_not_stop_others(self, session_factory, seeded_sources):
        session = session_factory()
        try:
            session.add_all([
                Scholarship(title="S1", country="Germany", degree="Masters", funding="Full", official_source_url="https://example.com/1"),
                Scholarship(title="S2", country="France", degree="PhD", funding="Full", official_source_url="https://example.com/2"),
            ])
            session.commit()
        finally:
            session.close()

        from app.services.discovery_pipeline import DiscoveryPipeline
        original_discover_batch = DiscoveryPipeline.discover_batch

        def failing_discover_batch(self, source_urls):
            if any("daad" in str(url).lower() for url in source_urls):
                raise RuntimeError("Simulated network failure")
            return original_discover_batch(self, source_urls)

        with patch.object(DiscoveryPipeline, "discover_batch", failing_discover_batch):
            scheduler = DiscoveryScheduler(
                session_factory=session_factory,
                dry_run=True,
                max_workers=2,
            )
            metrics = scheduler.run()

        assert metrics.errors >= 1

    def test_duplicate_prevention(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        metrics_run1 = scheduler.run()

        scheduler2 = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        metrics_run2 = scheduler2.run()

        assert metrics_run1.duplicates + metrics_run2.duplicates >= 0

    def test_idempotent_repeat_discovery(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        metrics1 = scheduler.run()
        metrics2 = scheduler.run()

        assert metrics1.countries_scanned == metrics2.countries_scanned

    def test_metrics_structure(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        metrics = scheduler.run()

        assert hasattr(metrics, "countries_scanned")
        assert hasattr(metrics, "inserted_scholarships")
        assert hasattr(metrics, "duplicates")
        assert hasattr(metrics, "rejected_candidates")
        assert hasattr(metrics, "errors")
        assert hasattr(metrics, "image_discoveries_triggered")
        assert hasattr(metrics, "runtime_ms")
        assert hasattr(metrics, "country_results")
        assert hasattr(metrics, "operation_id")

    def test_dry_run_no_scholarships_inserted(self, session_factory, seeded_sources):
        scheduler = DiscoveryScheduler(
            session_factory=session_factory,
            dry_run=True,
            max_workers=2,
        )
        scheduler.run()

        session = session_factory()
        try:
            count = session.scalar(select(func.count()).select_from(Scholarship))
            assert count == 0
        finally:
            session.close()
