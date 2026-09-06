"""Focused tests for POST /internal/images/verify."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient
from uuid import uuid4

from app.database import get_session_factory, init_database, reset_database_connections
from app.main import app
from app.models import Base, Scholarship, ScholarshipVerificationHistory


def _make_test_db_path() -> Path:
    return Path(tempfile.gettempdir()) / f"scholarzone-test-img-verify-{uuid4().hex}.db"


@pytest.fixture(scope="module")
def test_db_path():
    path = _make_test_db_path()
    return path


@pytest.fixture(scope="module")
def client(test_db_path):
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_VERIFICATION_SECRET"] = "test-secret"
    reset_database_connections()
    init_database()
    with TestClient(app) as c:
        c.__enter__()
        yield c
        c.__exit__(None, None, None)
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture(scope="module")
def session(test_db_path):
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_VERIFICATION_SECRET"] = "test-secret"
    engine = create_engine(f"sqlite:///{test_db_path.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _auth_headers() -> dict:
    return {"X-Verification-Secret": "test-secret"}


def _make_scholarship(session, title="Test Scholarship", official_source_url=None) -> int:
    if official_source_url is None:
        official_source_url = f"https://example.com/program/{uuid4().hex}"
    scholarship = Scholarship(
        title=title,
        country="Testland",
        degree="Master",
        funding="Fully Funded",
        official_source_url=official_source_url,
    )
    session.add(scholarship)
    session.commit()
    return scholarship.id


class TestAuthentication:
    def test_missing_secret_returns_401(self, client):
        response = client.post(
            "/internal/images/verify",
            json={
                "scholarship_id": 1,
                "image_url": "https://example.com/img.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response.status_code == 401

    def test_wrong_secret_returns_401(self, client):
        response = client.post(
            "/internal/images/verify",
            headers={"X-Verification-Secret": "wrong"},
            json={
                "scholarship_id": 1,
                "image_url": "https://example.com/img.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response.status_code == 401


class TestValidHighConfidenceImage:
    @patch("app.routers.verification.ImageValidator")
    def test_high_confidence_image_persists(self, mock_validator_cls, client, session):
        mock_validator = MagicMock()
        mock_validator_cls.return_value = mock_validator
        mock_result = MagicMock()
        mock_result.confidence = "HIGH"
        mock_result.status.value = "approved"
        mock_result.is_generic_image = False
        mock_result.is_ui_asset = False
        mock_result.image_kind = "program_image"
        mock_validator.validate_candidate.return_value = mock_result
        mock_validator._classify_image_kind.return_value = "program_image"

        scholarship_id = _make_scholarship(session)

        response = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/cover.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
                "image_alt_text": "Cover image",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "updated"
        assert payload["image_url"] == "https://example.com/cover.jpg"

        session.expire_all()
        refreshed = session.get(Scholarship, scholarship_id)
        assert refreshed.image_url == "https://example.com/cover.jpg"
        assert refreshed.image_source_url == "https://example.com/program"
        assert refreshed.image_source_type == "official_scholarship"
        assert refreshed.image_alt_text == "Cover image"
        assert refreshed.image_verified_at is not None

        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship_id
            )
        ).all()
        assert len(history) == 1
        assert history[0].field_name == "image_url"
        assert history[0].old_value is None
        assert history[0].new_value == "https://example.com/cover.jpg"
        assert history[0].change_type == "verified"


class TestRejectionCases:
    @patch("app.routers.verification.ImageValidator")
    def test_low_confidence_rejected(self, mock_validator_cls, client, session):
        mock_validator = MagicMock()
        mock_validator_cls.return_value = mock_validator
        mock_result = MagicMock()
        mock_result.confidence = "LOW"
        mock_result.status.value = "rejected"
        mock_result.is_generic_image = False
        mock_result.is_ui_asset = False
        mock_validator.validate_candidate.return_value = mock_result

        scholarship_id = _make_scholarship(session)

        response = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/img.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response.status_code == 400
        assert "LOW" in response.json()["detail"]

    @patch("app.routers.verification.ImageValidator")
    def test_human_review_rejected(self, mock_validator_cls, client, session):
        mock_validator = MagicMock()
        mock_validator_cls.return_value = mock_validator
        mock_result = MagicMock()
        mock_result.confidence = "MEDIUM"
        mock_result.status.value = "human_review"
        mock_result.is_generic_image = False
        mock_result.is_ui_asset = False
        mock_validator.validate_candidate.return_value = mock_result

        scholarship_id = _make_scholarship(session)

        response = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/img.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response.status_code == 400
        assert "medium" in response.json()["detail"].lower()

    @patch("app.routers.verification.ImageValidator")
    def test_ui_logo_image_rejected(self, mock_validator_cls, client, session):
        mock_validator = MagicMock()
        mock_validator_cls.return_value = mock_validator
        mock_result = MagicMock()
        mock_result.confidence = "HIGH"
        mock_result.status.value = "approved"
        mock_result.is_generic_image = True
        mock_result.is_ui_asset = True
        mock_validator.validate_candidate.return_value = mock_result

        scholarship_id = _make_scholarship(session)

        response = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/logo.png",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response.status_code == 400
        assert "non-content" in response.json()["detail"].lower()


class TestInvalidScholarshipId:
    @patch("app.routers.verification.ImageValidator")
    def test_invalid_scholarship_id_returns_404(self, mock_validator_cls, client, session):
        response = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": 99999,
                "image_url": "https://example.com/img.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestIdempotency:
    @patch("app.routers.verification.ImageValidator")
    def test_duplicate_submission_no_duplicate_audit(self, mock_validator_cls, client, session):
        mock_validator = MagicMock()
        mock_validator_cls.return_value = mock_validator
        mock_result = MagicMock()
        mock_result.confidence = "HIGH"
        mock_result.status.value = "approved"
        mock_result.is_generic_image = False
        mock_result.is_ui_asset = False
        mock_result.image_kind = "program_image"
        mock_validator.validate_candidate.return_value = mock_result
        mock_validator._classify_image_kind.return_value = "program_image"

        scholarship_id = _make_scholarship(session)

        response1 = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/cover.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response1.status_code == 200
        assert response1.json()["status"] == "updated"

        response2 = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/cover.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response2.status_code == 200
        assert response2.json()["status"] == "unchanged"

        session.expire_all()
        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship_id
            )
        ).all()
        assert len(history) == 1

    @patch("app.routers.verification.ImageValidator")
    def test_different_image_creates_modified_audit(self, mock_validator_cls, client, session):
        mock_validator = MagicMock()
        mock_validator_cls.return_value = mock_validator
        mock_result = MagicMock()
        mock_result.confidence = "HIGH"
        mock_result.status.value = "approved"
        mock_result.is_generic_image = False
        mock_result.is_ui_asset = False
        mock_result.image_kind = "program_image"
        mock_validator.validate_candidate.return_value = mock_result
        mock_validator._classify_image_kind.return_value = "program_image"

        scholarship_id = _make_scholarship(session)

        response1 = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/old.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response1.status_code == 200

        response2 = client.post(
            "/internal/images/verify",
            headers=_auth_headers(),
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/new.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_scholarship",
            },
        )
        assert response2.status_code == 200
        assert response2.json()["status"] == "updated"

        session.expire_all()
        refreshed = session.get(Scholarship, scholarship_id)
        assert refreshed.image_url == "https://example.com/new.jpg"

        history = session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
            .order_by(ScholarshipVerificationHistory.created_at.asc())
        ).all()
        assert len(history) == 2
        assert history[0].change_type == "verified"
        assert history[1].change_type == "modified"
        assert history[1].old_value == "https://example.com/old.jpg"
        assert history[1].new_value == "https://example.com/new.jpg"
