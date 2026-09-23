"""Regression tests for scholarship official image handling.

Covers:
- Valid official image
- Missing image fallback
- Broken image
- Duplicate/reused image detection
- API serialization
- Verification metadata
"""

import os
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-test-img-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.models import Base, Scholarship, ScholarshipVerificationHistory  # noqa: E402
from app.services.scholarship_image_verifier import (  # noqa: E402
    ImageSourceType,
    ImageVerifier,
    is_official_domain,
    is_valid_source_type,
)

SCHOLARSHIP_DATA = {
    "title": "Test Scholarship",
    "country": "Germany",
    "degree": "Master",
    "funding": "Fully Funded",
    "official_source_url": "https://www.daad.de/en/scholarships/test",
}


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()
    engine.dispose()


class TestImageSourceTypes:
    def test_all_source_types_are_valid(self):
        for source_type in ImageSourceType:
            assert is_valid_source_type(source_type.value)

    def test_invalid_source_type_rejected(self):
        assert not is_valid_source_type("generic_image")
        assert not is_valid_source_type("")
        assert not is_valid_source_type(None)

    def test_is_official_domain_accepts_government(self):
        assert is_official_domain("studyinkorea.go.kr")
        assert is_official_domain("www.campusfrance.org")
        assert is_official_domain("erasmus-plus.ec.europa.eu")
        assert is_official_domain("go.jp")

    def test_is_official_domain_accepts_swiss_german_official(self):
        assert is_official_domain("sbfi.admin.ch")
        assert is_official_domain("deutschlandstipendium.de")
        assert is_official_domain("ethz.ch")
        assert is_official_domain("epfl.ch")

    def test_is_official_domain_accepts_french_gov(self):
        assert is_official_domain("aefe.gouv.fr")
        assert is_official_domain("gouv.fr")

    def test_is_official_domain_rejects_french_third_party(self):
        assert not is_official_domain("scholarship-finder.gouv.fr")
        assert not is_official_domain("fake-edu.gouv.fr")
        assert not is_official_domain("blog.gouv.fr")

    def test_is_official_domain_rejects_third_party_aggregators(self):
        assert not is_official_domain("www.scholarship-positions.com")
        assert not is_official_domain("www.findaphd.com")
        assert not is_official_domain("unsplash.com")
        assert not is_official_domain("images.google.com")
        assert not is_official_domain(None)
        assert not is_official_domain("")


class TestValidImage:
    def test_mark_image_verified_success(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        result = verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/scholarship-banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
            alt_text="DAAD Scholarship banner",
            image_kind="program_image",
        )
        assert result is True

        updated = session.get(Scholarship, scholarship.id)
        assert updated.image_url == "https://www.daad.de/images/scholarship-banner.jpg"
        assert updated.image_source_url == "https://www.daad.de/en/scholarships/test"
        assert updated.image_source_type == "official_provider"
        assert updated.image_kind == "program_image"
        assert updated.image_verified_at is not None
        assert updated.image_alt_text == "DAAD Scholarship banner"

    def test_mark_image_verified_invalid_source_type(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        result = verifier.mark_image_verified(
            scholarship.id,
            image_url="https://example.com/image.jpg",
            image_source_url="https://example.com",
            source_type="invalid_type",
        )
        assert result is False

    def test_mark_image_verified_same_url_no_change(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
        )

        result = verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
        )
        assert result is False

    def test_mark_image_verified_normalizes_urls_for_idempotency(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(
            **SCHOLARSHIP_DATA,
            image_url="https://www.daad.de/images/banner.jpg/",
            image_source_url="https://www.daad.de/en/scholarships/test/",
            image_source_type="official_provider",
        )
        session.add(scholarship)
        session.commit()
        first_timestamp = scholarship.image_verified_at

        result = verifier.mark_image_verified(
            scholarship.id,
            image_url="https://daad.de/images/banner.jpg",
            image_source_url="https://daad.de/en/scholarships/test",
            source_type="official_provider",
        )

        assert result is False
        refreshed = session.get(Scholarship, scholarship.id)
        assert refreshed.image_url == "https://www.daad.de/images/banner.jpg/"
        assert refreshed.image_source_url == "https://www.daad.de/en/scholarships/test/"
        assert refreshed.image_verified_at == first_timestamp
        assert session.scalar(
            select(func.count(ScholarshipVerificationHistory.id)).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship.id
            )
        ) == 0

    def test_automatic_discovery_does_not_overwrite_existing_image(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(
            **SCHOLARSHIP_DATA,
            image_url="https://www.daad.de/images/existing.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            image_source_type="official_provider",
            image_kind="program_image",
            image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            image_alt_text="Existing program image",
        )
        session.add(scholarship)
        session.commit()

        result = verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/new.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
            image_kind="program_image",
            automatic=True,
        )

        assert result is False
        refreshed = session.get(Scholarship, scholarship.id)
        assert refreshed.image_url == "https://www.daad.de/images/existing.jpg"
        assert refreshed.image_source_url == "https://www.daad.de/en/scholarships/test"
        assert refreshed.image_source_type == "official_provider"
        assert refreshed.image_kind == "program_image"
        assert refreshed.image_verified_at is not None
        assert refreshed.image_verified_at.replace(tzinfo=timezone.utc) == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert refreshed.image_alt_text == "Existing program image"
        assert session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship.id
            )
        ).all() == []

    def test_automatic_discovery_can_replace_unverified_image(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)
        scholarship = Scholarship(
            **SCHOLARSHIP_DATA,
            image_url="https://www.daad.de/images/unverified.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            image_source_type="official_provider",
            image_kind="program_image",
        )
        session.add(scholarship)
        session.commit()

        result = verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/new.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
            image_kind="official_banner",
            automatic=True,
        )

        assert result is True
        refreshed = session.get(Scholarship, scholarship.id)
        assert refreshed.image_url == "https://www.daad.de/images/new.jpg"
        assert refreshed.image_kind == "official_banner"
        assert refreshed.image_verified_at is not None

    def test_image_kind_none_preserves_existing_kind(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(
            **SCHOLARSHIP_DATA,
            image_url="https://www.daad.de/images/existing.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            image_source_type="official_provider",
            image_kind="program_image",
        )
        session.add(scholarship)
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/new.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
            image_kind=None,
        )

        assert session.get(Scholarship, scholarship.id).image_kind == "program_image"

    def test_verification_audit_contains_source_evidence(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/scholarship-banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
            image_kind="program_image",
        )

        history = session.scalars(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship.id
            )
        ).one()
        assert history.evidence_text == "https://www.daad.de/en/scholarships/test"

    def test_repeated_identical_submission_is_idempotent(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        kwargs = {
            "scholarship_id": scholarship.id,
            "image_url": "https://www.daad.de/images/idempotent.jpg",
            "image_source_url": "https://www.daad.de/en/scholarships/test",
            "source_type": "official_provider",
            "image_kind": "program_image",
            "alt_text": "Program image",
        }
        assert verifier.mark_image_verified(**kwargs) is True
        first_timestamp = session.get(Scholarship, scholarship.id).image_verified_at
        first_history_count = session.scalar(
            select(func.count(ScholarshipVerificationHistory.id)).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship.id
            )
        )

        assert verifier.mark_image_verified(**kwargs) is False

        refreshed = session.get(Scholarship, scholarship.id)
        assert refreshed.image_verified_at == first_timestamp
        assert session.scalar(
            select(func.count(ScholarshipVerificationHistory.id)).where(
                ScholarshipVerificationHistory.scholarship_id == scholarship.id
            )
        ) == first_history_count == 1


class TestImageUrlChangeAudited:
    def test_image_url_change_recorded_in_audit(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/old-banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
        )
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/new-banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
        )

        history = session.scalars(
            select(ScholarshipVerificationHistory.field_name)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship.id)
        ).all()
        assert "image_url" in history


class TestMissingImageFallback:
    def test_scholarship_without_image_returns_none(self, in_memory_session):
        session, _ = in_memory_session

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        fetched = session.get(Scholarship, scholarship.id)
        assert fetched.image_url is None
        assert fetched.image_source_url is None
        assert fetched.image_source_type is None


class TestDuplicateReusedImageDetection:
    def test_duplicate_image_urls_across_scholarships_detected(self, in_memory_session):
        session, _ = in_memory_session

        s1 = Scholarship(
            title="Scholarship One",
            country="Germany",
            degree="Master",
            funding="Fully Funded",
            official_source_url="https://uni-a.de/scholarship",
            image_url="https://uni-a.de/images/common-banner.jpg",
            image_source_url="https://uni-a.de/scholarship",
            image_source_type="official_university",
        )
        s2 = Scholarship(
            title="Scholarship Two",
            country="Germany",
            degree="PhD",
            funding="Fully Funded",
            official_source_url="https://uni-b.de/scholarship",
            image_url="https://uni-a.de/images/common-banner.jpg",
            image_source_url="https://uni-a.de/scholarship",
            image_source_type="official_university",
        )
        session.add_all([s1, s2])
        session.commit()

        distinct_count = session.scalar(
            select(func.count(func.distinct(Scholarship.image_url)))
            .where(Scholarship.image_url.is_not(None))
        )
        assert distinct_count == 1

        reused = session.scalars(
            select(Scholarship.image_url)
            .where(Scholarship.image_url.is_not(None))
            .group_by(Scholarship.image_url)
            .having(func.count(Scholarship.id) > 1)
        ).all()
        assert "https://uni-a.de/images/common-banner.jpg" in reused


class TestImageAuditGap:
    def test_null_to_image_creates_audit(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/scholarship-banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
            alt_text="DAAD Scholarship banner",
        )

        history = session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship.id)
        ).all()
        assert len(history) == 1
        record = history[0]
        assert record.field_name == "image_url"
        assert record.old_value is None
        assert record.new_value == "https://www.daad.de/images/scholarship-banner.jpg"
        assert record.change_type == "verified"
        assert record.source_url is None

    def test_image_to_different_image_creates_audit(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/old-banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
        )
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/new-banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
        )

        history = session.scalars(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship.id)
        ).all()
        assert len(history) == 2
        latest = history[-1]
        assert latest.field_name == "image_url"
        assert latest.old_value == "https://www.daad.de/images/old-banner.jpg"
        assert latest.new_value == "https://www.daad.de/images/new-banner.jpg"
        assert latest.change_type == "modified"


class TestBrokenImage:
    def test_clear_image_when_not_set_returns_false(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        result = verifier.clear_image(scholarship.id)
        assert result is False

    def test_clear_image_removes_fields(self, in_memory_session):
        session, _ = in_memory_session
        verifier = ImageVerifier(session)

        scholarship = Scholarship(**SCHOLARSHIP_DATA)
        session.add(scholarship)
        session.commit()

        verifier.mark_image_verified(
            scholarship.id,
            image_url="https://www.daad.de/images/banner.jpg",
            image_source_url="https://www.daad.de/en/scholarships/test",
            source_type="official_provider",
        )
        session.commit()

        result = verifier.clear_image(scholarship.id)
        assert result is True

        updated = session.get(Scholarship, scholarship.id)
        assert updated.image_url is None
        assert updated.image_source_url is None
        assert updated.image_source_type is None
        assert updated.image_verified_at is None
        assert updated.image_alt_text is None


class TestImageApiSerialization:
    @classmethod
    def setup_class(cls):
        os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
        os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
        from app.database import reset_database_connections
        reset_database_connections()
        from app.main import app
        from starlette.testclient import TestClient
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def teardown_class(cls):
        cls.client.__exit__(None, None, None)
        if TEST_DATABASE_PATH.exists():
            TEST_DATABASE_PATH.unlink()

    def test_detail_response_includes_image_fields(self):
        response = self.client.get("/scholarships/1")
        assert response.status_code == 200
        payload = response.json()
        assert "image_url" in payload
        assert "image_source_url" in payload
        assert "image_source_type" in payload
        assert "image_verified_at" in payload
        assert "image_alt_text" in payload

    def test_list_response_includes_image_fields(self):
        response = self.client.get("/scholarships?limit=1")
        assert response.status_code == 200
        payload = response.json()
        item = payload["items"][0]
        assert "image_url" in item
        assert "image_source_type" in item
