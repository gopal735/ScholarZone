"""Tests for next-cycle discovery."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DiscoveryCandidate, Scholarship
from app.services.next_cycle_discovery import (
    NextCycleDiscoveryResult,
    _extract_context,
    batch_discover_next_cycles,
    discover_next_cycle,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def scholarship_factory(session):
    counter = {"n": 0}
    def _make(**kwargs):
        counter["n"] += 1
        defaults = {
            "title": "Test Scholarship",
            "country": "Germany",
            "degree": "Masters",
            "funding": "Full",
            "official_source_url": f"https://example.com/scholarship-{counter['n']}",
            "official_source": "Test Provider",
            "status": "closed",
        }
        defaults.update(kwargs)
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s
    return _make


class TestExtractContext:
    def test_extract_year_context(self):
        text = "The 2027 program is now open for applications. Apply now for the 2027-2028 cycle."
        result = _extract_context(text, 2027)
        assert result is not None
        assert "2027" in result

    def test_no_year(self):
        result = _extract_context("Some text without year", None)
        assert result is None


class TestDiscoverNextCycle:
    def test_missing_source_url(self, session, scholarship_factory):
        s = scholarship_factory(official_source_url=None)
        result = discover_next_cycle(session, s)
        assert not result.discovered
        assert result.error == "missing_source_url"

    def test_fetch_failure(self, session, scholarship_factory):
        s = scholarship_factory(official_source_url="https://example.com/scholarship")
        with patch("app.services.next_cycle_discovery.fetch_official_source") as mock_fetch:
            mock_fetch.return_value.success = False
            mock_fetch.return_value.error_type = "timeout"
            mock_fetch.return_value.error_reason = "Connection timed out"
            result = discover_next_cycle(session, s)
        assert not result.discovered
        assert result.error == "timeout"

    def test_next_cycle_detected_with_open_announcement(self, session, scholarship_factory):
        s = scholarship_factory(
            official_source_url="https://example.com/scholarship",
            title="Test Scholarship 2026",
        )
        fake_content = """
        <html>
        <body>
        <h1>Applications now open for 2028 programme</h1>
        <p>Apply now for the 2028 intake. Deadline: March 2028.</p>
        </body>
        </html>
        """
        with patch("app.services.next_cycle_discovery.fetch_official_source") as mock_fetch:
            mock_fetch.return_value.success = True
            mock_fetch.return_value.content = fake_content
            mock_fetch.return_value.final_url = "https://example.com/scholarship"
            with patch("app.services.next_cycle_discovery.extract_scholarship_information") as mock_extract:
                mock_extract.return_value.scholarship_name = "Test Scholarship 2028"
                mock_extract.return_value.provider = "Test Provider"
                mock_extract.return_value.deadline_display = "March 2028"
                mock_extract.return_value.deadline_date = None
                mock_extract.return_value.model_dump_json.return_value = '{"deadline": "March 2028"}'
                result = discover_next_cycle(session, s)

        assert result.discovered
        assert result.next_cycle_year == 2028
        assert result.confidence == "high"
        assert result.proposed_status == "upcoming"

    def test_no_next_cycle_detected(self, session, scholarship_factory):
        s = scholarship_factory(
            official_source_url="https://example.com/scholarship",
        )
        fake_content = """
        <html>
        <body>
        <h1>Scholarship Information</h1>
        <p>This is a generic scholarship page.</p>
        </body>
        </html>
        """
        with patch("app.services.next_cycle_discovery.fetch_official_source") as mock_fetch:
            mock_fetch.return_value.success = True
            mock_fetch.return_value.content = fake_content
            mock_fetch.return_value.final_url = "https://example.com/scholarship"
            with patch("app.services.next_cycle_discovery.extract_scholarship_information") as mock_extract:
                mock_extract.return_value.scholarship_name = "Test Scholarship"
                mock_extract.return_value.provider = "Test Provider"
                mock_extract.return_value.deadline_display = None
                mock_extract.return_value.deadline_date = None
                mock_extract.return_value.model_dump_json.return_value = "{}"
                result = discover_next_cycle(session, s)

        assert not result.discovered
        assert result.confidence == "low"
        assert result.proposed_status is None


class TestBatchDiscoverNextCycles:
    def test_batch_skips_non_closed(self, session, scholarship_factory):
        s1 = scholarship_factory(status="open")
        s2 = scholarship_factory(status="closed")
        s3 = scholarship_factory(status="upcoming")

        with patch("app.services.next_cycle_discovery.discover_next_cycle") as mock_discover:
            mock_discover.return_value = NextCycleDiscoveryResult(
                scholarship_id=0,
                discovered=True,
                next_cycle_year=2027,
                next_cycle_text="2027 program",
                source_verified=True,
                confidence="high",
                evidence="test",
                proposed_status="upcoming",
            )
            results = batch_discover_next_cycles(session, [s1.id, s2.id, s3.id])

        assert mock_discover.call_count == 1
        assert mock_discover.call_args[0][1].id == s2.id
