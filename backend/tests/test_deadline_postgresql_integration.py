"""PostgreSQL integration tests for deadline_within_days filtering.

These tests require a running PostgreSQL instance and are skipped unless
TEST_POSTGRESQL_URL is set. They are NOT schema-migration tests.
"""

import os
import uuid
from datetime import date, timedelta, timezone

import pytest

from app.database import init_database, reset_database_connections
from app.main import app
from app.models import Scholarship
from app.repositories import scholarships as repo


FIXED_TODAY = date(2026, 11, 17)


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRESQL_URL"),
    reason="TEST_POSTGRESQL_URL not set",
)
class TestPostgreSQLDeadlineIntegration:
    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        pg_url = os.environ.get("TEST_POSTGRESQL_URL")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", pg_url)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        reset_database_connections()
        init_database()
        monkeypatch.setattr(repo, "_utc_today", lambda: FIXED_TODAY)
        yield
        reset_database_connections()

    @pytest.fixture
    def pg_session(self):
        from app.database import get_session_factory

        session = get_session_factory()()
        records = [
            Scholarship(
                title="Yesterday",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="open",
                verification_status="active",
                is_archived=False,
                deadline_date=FIXED_TODAY - timedelta(days=1),
                official_source_url="https://example.edu/yesterday",
            ),
            Scholarship(
                title="Today",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="open",
                verification_status="active",
                is_archived=False,
                deadline_date=FIXED_TODAY,
                official_source_url="https://example.edu/today",
            ),
            Scholarship(
                title="Day30",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="open",
                verification_status="active",
                is_archived=False,
                deadline_date=FIXED_TODAY + timedelta(days=30),
                official_source_url="https://example.edu/day30",
            ),
            Scholarship(
                title="Day31",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="open",
                verification_status="active",
                is_archived=False,
                deadline_date=FIXED_TODAY + timedelta(days=31),
                official_source_url="https://example.edu/day31",
            ),
            Scholarship(
                title="NullDeadline",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="open",
                verification_status="active",
                is_archived=False,
                deadline_date=None,
                official_source_url="https://example.edu/null",
            ),
            Scholarship(
                title="Closed",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="closed",
                verification_status="active",
                is_archived=False,
                deadline_date=FIXED_TODAY + timedelta(days=5),
                official_source_url="https://example.edu/closed",
            ),
            Scholarship(
                title="Archived",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="open",
                verification_status="active",
                is_archived=True,
                deadline_date=FIXED_TODAY + timedelta(days=5),
                official_source_url="https://example.edu/archived",
            ),
        ]
        session.add_all(records)
        session.commit()
        yield session
        session.close()

    def test_deadline_window_boundaries(self, pg_session):
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/scholarships", params={"deadline_within_days": 30, "limit": 50})
            assert response.status_code == 200
            titles = {item["title"] for item in response.json()["items"]}
            assert "Today" in titles
            assert "Day30" in titles
            assert "Yesterday" not in titles
            assert "Day31" not in titles
            assert "NullDeadline" not in titles
            assert "Closed" not in titles
            assert "Archived" not in titles

    def test_deadline_window_rejects_above_365(self, pg_session):
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/scholarships", params={"deadline_within_days": 366})
            assert response.status_code == 422
