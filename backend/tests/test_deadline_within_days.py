"""Regression tests for deadline_within_days scholarship filtering."""

import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import reset_database_connections
from app.main import app
from app.seed import seed_database


def test_deadline_within_days_rejects_invalid_values() -> None:
    db_path = Path(tempfile.gettempdir()) / "scholarzone-dwd-invalid.db"
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    reset_database_connections()

    with TestClient(app) as client:
        assert client.get("/scholarships", params={"deadline_within_days": 366}).status_code == 422
        assert client.get("/scholarships", params={"deadline_within_days": 0}).status_code == 422
        assert client.get("/scholarships", params={"deadline_within_days": -1}).status_code == 422


def test_deadline_within_days_accepts_valid_value_and_returns_windowed_results() -> None:
    db_path = Path(tempfile.gettempdir()) / "scholarzone-dwd-valid.db"
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    reset_database_connections()

    from app.database import init_database
    init_database()
    seed_database()

    with TestClient(app) as client:
        response = client.get("/scholarships", params={"deadline_within_days": 30, "limit": 50})
        assert response.status_code == 200
        payload = response.json()
        assert "items" in payload
        assert "pagination" in payload

        today = datetime.now(timezone.utc).date()
        cutoff = today + timedelta(days=30)
        for item in payload["items"]:
            deadline = item.get("deadline_date")
            assert deadline, "deadline_within_days results must include a known deadline_date"
            parsed = date.fromisoformat(deadline)
            assert today <= parsed <= cutoff
