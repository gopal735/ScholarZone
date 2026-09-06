"""Focused tests for official image fallback and admin review system.

Covers:
- image_kind serialization
- official logo fallback behavior
- third-party logo rejection
- favicon/UI icon rejection
- admin-only review access
- public user cannot access review data
- approve/reject flow
- audit trail
- idempotent persistence
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.database import get_session_factory, init_database, reset_database_connections
from app.main import app
from app.models import Base, ImageReview, Scholarship, ScholarshipVerificationHistory
from app.services.admin_image_review import (
    approve_image_review,
    create_image_review,
    get_image_review,
    get_pending_image_reviews,
    reject_image_review,
)
from app.services.image_discovery import ImageCandidate, ImageDiscoveryService
from app.services.image_validator import ImageValidator, ImageValidationResult, ValidationStatus
from app.services.scholarship_image_verifier import ImageVerifier


def _make_test_db_path() -> Path:
    return Path(tempfile.gettempdir()) / f"scholarzone-test-admin-review-{uuid4().hex}.db"


@pytest.fixture(scope="module")
def test_db_path():
    path = _make_test_db_path()
    return path


@pytest.fixture(scope="module")
def client(test_db_path):
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_VERIFICATION_SECRET"] = "test-secret"
    os.environ["SCHOLARZONE_ADMIN_SECRET"] = "admin-secret"
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
    os.environ["SCHOLARZONE_ADMIN_SECRET"] = "admin-secret"
    engine = create_engine(f"sqlite:///{test_db_path.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


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
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return scholarship.id


class TestImageKindSerialization:
    def test_scholarship_response_includes_image_kind(self, client, session):
        scholarship_id = _make_scholarship(session)
        session.get(Scholarship, scholarship_id).image_kind = "program_image"
        session.commit()

        response = client.get(f"/scholarships/{scholarship_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["image_kind"] == "program_image"

    def test_scholarship_list_includes_image_kind(self, client, session):
        scholarship = Scholarship(
            title="List Test Scholarship",
            country="Testland",
            degree="Master",
            funding="Fully Funded",
            official_source_url=f"https://example.com/list-{uuid4().hex}",
            image_kind="official_banner",
        )
        session.add(scholarship)
        session.commit()

        response = client.get(f"/scholarships/{scholarship.id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["image_kind"] == "official_banner"


class TestOfficialLogoFallback:
    def test_logo_rejected_when_better_candidate_exists(self, session):
        validator = ImageValidator(timeout=30.0)
        logo_result = ImageValidationResult(
            candidate=ImageCandidate(
                image_url="https://www.daad.de/logo.png",
                page_url="https://www.daad.de/en/program",
                discovery_method="html-img",
                alt_text="Official Logo",
            ),
            is_reachable=True,
            is_valid_image=True,
            is_official_domain=True,
            image_domain="www.daad.de",
            source_domain="www.daad.de",
            width=200,
            height=200,
            relevance_score=0.6,
            confidence="MEDIUM",
            status=ValidationStatus.HUMAN_REVIEW,
        )
        logo_result.image_kind = "official_logo"

        cover_result = ImageValidationResult(
            candidate=ImageCandidate(
                image_url="https://www.daad.de/cover.jpg",
                page_url="https://www.daad.de/en/program",
                discovery_method="og:image",
                alt_text="Program Cover",
            ),
            is_reachable=True,
            is_valid_image=True,
            is_official_domain=True,
            image_domain="www.daad.de",
            source_domain="www.daad.de",
            width=1200,
            height=630,
            relevance_score=0.9,
            confidence="HIGH",
            status=ValidationStatus.APPROVED,
            image_kind="program_image",
        )
        cover_result.result_id = 1
        logo_result.result_id = 2

        logo_result = validator._validate_logo_fallback(logo_result, [logo_result, cover_result])

        assert logo_result.image_kind is None
        assert logo_result.status == ValidationStatus.REJECTED
        assert any("program image or banner candidate exists" in r.lower() for r in logo_result.rejection_reasons)

    def test_third_party_logo_rejected(self, session):
        validator = ImageValidator(timeout=30.0)
        result = ImageValidationResult(
            candidate=ImageCandidate(
                image_url="https://www.daad.de/facebook-logo.png",
                page_url="https://www.daad.de/en/program",
                discovery_method="html-img",
                alt_text="Facebook Logo",
            ),
            is_reachable=True,
            is_valid_image=True,
            is_official_domain=True,
            image_domain="www.daad.de",
            source_domain="www.daad.de",
            width=200,
            height=200,
            relevance_score=0.6,
            confidence="MEDIUM",
            status=ValidationStatus.HUMAN_REVIEW,
        )
        result.image_kind = validator._classify_image_kind(result)
        result = validator._validate_logo_fallback(result, [result])

        assert result.image_kind is None or result.status == ValidationStatus.REJECTED
        assert any("third-party" in r.lower() or "social" in r.lower() or "facebook" in r.lower() for r in result.rejection_reasons)

    def test_favicon_rejected_as_logo(self, session):
        validator = ImageValidator(timeout=30.0)
        result = ImageValidationResult(
            candidate=ImageCandidate(
                image_url="https://www.daad.de/favicon.ico",
                page_url="https://www.daad.de/en/program",
                discovery_method="html-img",
                alt_text="Favicon",
            ),
            is_reachable=True,
            is_valid_image=True,
            is_official_domain=True,
            image_domain="www.daad.de",
            source_domain="www.daad.de",
            width=32,
            height=32,
            relevance_score=0.6,
            confidence="MEDIUM",
            status=ValidationStatus.HUMAN_REVIEW,
        )
        result.image_kind = validator._classify_image_kind(result)
        result = validator._validate_logo_fallback(result, [result])

        assert result.image_kind is None
        assert result.status == ValidationStatus.REJECTED
        assert any("third-party" in r.lower() or "favicon" in r.lower() for r in result.rejection_reasons)

    def test_social_icon_rejected_as_logo(self, session):
        validator = ImageValidator(timeout=30.0)
        result = ImageValidationResult(
            candidate=ImageCandidate(
                image_url="https://www.daad.de/facebook-icon.png",
                page_url="https://www.daad.de/en/program",
                discovery_method="html-img",
                alt_text="Facebook",
            ),
            is_reachable=True,
            is_valid_image=True,
            is_official_domain=True,
            image_domain="www.daad.de",
            source_domain="www.daad.de",
            width=128,
            height=128,
            relevance_score=0.6,
            confidence="MEDIUM",
            status=ValidationStatus.HUMAN_REVIEW,
        )
        result.image_kind = validator._classify_image_kind(result)
        result = validator._validate_logo_fallback(result, [result])

        assert result.image_kind is None
        assert result.status == ValidationStatus.REJECTED
        assert any("third-party" in r.lower() or "social" in r.lower() for r in result.rejection_reasons)


class TestAdminReviewAccess:
    def test_missing_admin_secret_returns_401(self, client):
        response = client.get("/admin/images/review-queue")
        assert response.status_code == 401

    def test_wrong_admin_secret_returns_401(self, client):
        response = client.get(
            "/admin/images/review-queue",
            headers={"X-Admin-Secret": "wrong"},
        )
        assert response.status_code == 401

    def test_valid_admin_secret_returns_queue(self, client, session):
        scholarship_id = _make_scholarship(session)
        create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/img.jpg",
            image_kind="program_image",
            confidence="MEDIUM",
            reason_for_review="test",
        )
        session.commit()

        response = client.get(
            "/admin/images/review-queue",
            headers={"X-Admin-Secret": "admin-secret"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["image_url"] == "https://example.com/img.jpg"
        assert data[0]["image_kind"] == "program_image"


class TestPublicUserCannotAccessReviewData:
    def test_public_endpoint_excludes_review_data(self, client, session):
        scholarship_id = _make_scholarship(session)
        create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/secret.jpg",
            image_kind="program_image",
            confidence="MEDIUM",
            reason_for_review="secret review",
        )
        session.commit()

        response = client.get(f"/scholarships/{scholarship_id}")
        assert response.status_code == 200
        payload = response.json()
        assert "review_queue" not in payload
        assert "secret.jpg" not in str(payload)

    def test_review_queue_endpoint_requires_admin(self, client):
        response = client.get("/admin/images/review-queue")
        assert response.status_code == 401


class TestApproveRejectFlow:
    def test_approve_persists_image_with_kind(self, client, session):
        scholarship_id = _make_scholarship(session)

        review = create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/approved.jpg",
            image_kind="program_image",
            source_page="https://example.com/program",
            source_type="official_university",
            confidence="MEDIUM",
            reason_for_review="test approval",
        )
        session.commit()
        assert review.created is True

        response = client.post(
            f"/admin/images/review/{review.review_id}/approve",
            headers={"X-Admin-Secret": "admin-secret"},
            json={"approved": True, "reviewer_note": "Looks good"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == "approved"
        assert payload["reviewed_by"] == "admin"

        session.expire_all()
        refreshed = session.get(Scholarship, scholarship_id)
        assert refreshed.image_url == "https://example.com/approved.jpg"
        assert refreshed.image_kind == "program_image"
        assert refreshed.image_verified_at is not None

        history = session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
        ).all()
        assert len(history) >= 1
        assert any(h.field_name == "image_url" for h in history)

    def test_reject_does_not_persist_image(self, client, session):
        scholarship_id = _make_scholarship(session)

        review = create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/rejected.jpg",
            image_kind="program_image",
            confidence="MEDIUM",
            reason_for_review="test rejection",
        )
        session.commit()

        response = client.post(
            f"/admin/images/review/{review.review_id}/reject",
            headers={"X-Admin-Secret": "admin-secret"},
            json={"approved": False, "reviewer_note": "Not suitable"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == "rejected"

        session.expire_all()
        refreshed = session.get(Scholarship, scholarship_id)
        assert refreshed.image_url is None


class TestAuditTrail:
    def test_approve_creates_audit_record(self, session):
        scholarship_id = _make_scholarship(session)

        review = create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/audit.jpg",
            image_kind="official_banner",
            source_type="official_government",
            confidence="MEDIUM",
            reason_for_review="audit test",
        )
        session.commit()

        approve_image_review(
            session=session,
            review_id=review.review_id,
            reviewed_by="admin",
            reviewer_note="audit",
        )
        session.commit()

        history = session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
            .where(ScholarshipVerificationHistory.field_name == "image_url")
        ).all()
        assert len(history) >= 1
        assert history[-1].new_value == "https://example.com/audit.jpg"
        assert history[-1].change_type == "modified"

    def test_reject_creates_audit_record(self, session):
        scholarship_id = _make_scholarship(session)

        review = create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/reject-audit.jpg",
            image_kind="program_image",
            confidence="MEDIUM",
            reason_for_review="reject audit",
        )
        session.commit()

        reject_image_review(
            session=session,
            review_id=review.review_id,
            reviewed_by="admin",
            reviewer_note="rejected",
        )
        session.commit()

        history = session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
            .where(ScholarshipVerificationHistory.field_name == "image_url")
            .where(ScholarshipVerificationHistory.change_type == "rejected")
        ).all()
        assert len(history) >= 1


class TestIdempotentPersistence:
    @patch("app.routers.verification.ImageValidator")
    def test_same_image_twice_no_duplicate_audit(self, mock_validator_cls, client, session):
        mock_validator = MagicMock()
        mock_validator_cls.return_value = mock_validator
        mock_result = MagicMock()
        mock_result.confidence = "HIGH"
        mock_result.status.value = "approved"
        mock_result.is_generic_image = False
        mock_result.is_ui_asset = False
        mock_result.image_kind = "program_image"
        mock_validator.validate_candidate.return_value = mock_result

        scholarship_id = _make_scholarship(session)

        response1 = client.post(
            "/internal/images/verify",
            headers={"X-Verification-Secret": "test-secret"},
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/idempotent.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_university",
                "image_kind": "program_image",
            },
        )
        assert response1.status_code == 200
        assert response1.json()["status"] == "updated"

        response2 = client.post(
            "/internal/images/verify",
            headers={"X-Verification-Secret": "test-secret"},
            json={
                "scholarship_id": scholarship_id,
                "image_url": "https://example.com/idempotent.jpg",
                "image_source_url": "https://example.com/program",
                "image_source_type": "official_university",
                "image_kind": "program_image",
            },
        )
        assert response2.status_code == 200
        assert response2.json()["status"] == "unchanged"

        session.expire_all()
        history = session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
        ).all()
        assert len(history) == 1

    def test_admin_approve_idempotent(self, session):
        scholarship_id = _make_scholarship(session)

        review = create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/admin-idempotent.jpg",
            image_kind="program_image",
            confidence="MEDIUM",
            reason_for_review="idempotent test",
        )
        session.commit()

        result1 = approve_image_review(session, review.review_id, "admin")
        assert result1.success is True

        result2 = approve_image_review(session, review.review_id, "admin")
        assert result2.success is False
        assert "already decided" in result2.error

    def test_does_not_overwrite_verified_image(self, session):
        scholarship_id = _make_scholarship(session)

        verifier = ImageVerifier(session)
        verifier.mark_image_verified(
            scholarship_id,
            image_url="https://example.com/verified.jpg",
            image_source_url="https://example.com/program",
            source_type="official_university",
            image_kind="program_image",
        )
        session.commit()

        review = create_image_review(
            session=session,
            scholarship_id=scholarship_id,
            image_url="https://example.com/new.jpg",
            image_kind="program_image",
            confidence="MEDIUM",
            reason_for_review="overwrite test",
        )
        session.commit()

        result = approve_image_review(session, review.review_id, "admin")
        assert result.success is False
        assert "verified image" in result.error.lower() or "concurrency" in result.error.lower()

        session.expire_all()
        refreshed = session.get(Scholarship, scholarship_id)
        assert refreshed.image_url == "https://example.com/verified.jpg"
