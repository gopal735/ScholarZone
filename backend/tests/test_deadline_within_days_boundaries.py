"""Frozen-clock boundary tests for deadline_within_days filtering."""

import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.database import init_database, reset_database_connections
from app.main import app
from app.models import Scholarship
from app.repositories import scholarships as repo


FIXED_TODAY = date(2026, 11, 17)


@pytest.fixture
def boundary_db(monkeypatch, tmp_path):
    db_path = tmp_path / "scholarzone-dwd-boundary.db"
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    reset_database_connections()
    init_database()

    # Freeze the repository clock.
    monkeypatch.setattr(repo, "_utc_today", lambda: FIXED_TODAY)

    from app.database import get_session_factory

    session = get_session_factory()()
    records = [
        Scholarship(
            title="Expired deadline",
            country="Testland",
            degree="Master",
            funding="Fully Funded",
            status="open",
            verification_status="active",
            is_archived=False,
            deadline_date=FIXED_TODAY - timedelta(days=1),
            official_source_url="https://example.edu/expired",
        ),
        Scholarship(
            title="Today deadline",
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
            title="Day 30 deadline",
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
            title="Day 31 deadline",
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
            title="No deadline",
            country="Testland",
            degree="Master",
            funding="Fully Funded",
            status="open",
            verification_status="active",
            is_archived=False,
            deadline_date=None,
            official_source_url="https://example.edu/none",
        ),
    ]
    session.add_all(records)
    session.commit()
    session.close()
    yield db_path
    reset_database_connections()


def test_deadline_within_days_boundary_inclusion(boundary_db):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/scholarships", params={"deadline_within_days": 30, "limit": 50})
        assert response.status_code == 200
        titles = {item["title"] for item in response.json()["items"]}
        assert "Today deadline" in titles
        assert "Day 30 deadline" in titles
        assert "Expired deadline" not in titles
        assert "Day 31 deadline" not in titles
        assert "No deadline" not in titles


def test_deadline_within_days_rejects_above_365(boundary_db):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/scholarships", params={"deadline_within_days": 366})
        assert response.status_code == 422


def test_deadline_within_days_365_includes_day31(boundary_db):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/scholarships", params={"deadline_within_days": 365, "limit": 50})
        assert response.status_code == 200
        titles = {item["title"] for item in response.json()["items"]}
        assert "Day 31 deadline" in titles
        assert "Today deadline" in titles
