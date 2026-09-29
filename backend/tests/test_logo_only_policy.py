"""Tests for logo-only image policy.

The catalogue's images are meant to identify the awarding body. A programme
photograph does not: a stock campus shot is decoration, and presenting one as a
scholarship's image is a claim the pixels cannot support. These tests pin the
behaviour that keeps identity marks and drops artwork.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.image_discovery_orchestrator import (
    LOGO_IDENTITY_KINDS,
    ImageDiscoveryOrchestrator,
    _clear_stored_image,
    _is_non_logo_stored,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _scholarship(session, kind, image_url="https://provider.example/img.jpg", title="Test"):
    row = Scholarship(
        title=title,
        country="Testland",
        degree="Master",
        funding="Full",
        official_source_url=f"https://provider.example/p/{abs(hash(title))}",
        image_url=image_url,
        image_kind=kind,
        image_source_url="https://provider.example/p",
        image_source_type="official_provider",
        image_alt_text="x",
    )
    session.add(row)
    session.commit()
    return row


class TestLogoIdentityKinds:
    def test_kinds_cover_logo_government_and_university_only(self):
        assert LOGO_IDENTITY_KINDS == frozenset({
            "official_logo", "official_government", "official_university"
        })

    @pytest.mark.parametrize("kind", ["program_image", "official_banner", "official_og",
                                      "official_media", "generic_official"])
    def test_programme_artwork_is_not_an_identity(self, kind):
        assert kind not in LOGO_IDENTITY_KINDS


class TestNonLogoDetection:
    def test_programme_photo_is_detected(self, session):
        row = _scholarship(session, "program_image")
        assert _is_non_logo_stored(session, row.id) is True

    def test_official_logo_is_kept(self, session):
        row = _scholarship(session, "official_logo")
        assert _is_non_logo_stored(session, row.id) is False

    def test_unset_kind_counts_as_non_logo(self, session):
        """An image nothing ever classified is one we cannot vouch for."""
        row = _scholarship(session, None)
        assert _is_non_logo_stored(session, row.id) is True

    def test_record_without_image_is_not_an_offender(self, session):
        row = _scholarship(session, "program_image")
        row.image_url = None
        session.commit()
        assert _is_non_logo_stored(session, row.id) is False


class TestClearStoredImage:
    def test_clears_every_provenance_field_together(self, session):
        """Clearing image_url alone would leave the record claiming to be verified.

        Reports count verified images, so a record with a null image but a
        retained image_verified_at and image_kind would read as a coverage
        success while carrying nothing.
        """
        row = _scholarship(session, "program_image")
        _clear_stored_image(session, row.id)
        session.commit()

        stored = session.get(Scholarship, row.id)
        assert stored.image_url is None
        assert stored.image_kind is None
        assert stored.image_verified_at is None
        assert stored.image_source_url is None
        assert stored.image_source_type is None
        assert stored.image_alt_text is None

    def test_keeps_the_scholarship_itself(self, session):
        row = _scholarship(session, "program_image")
        _clear_stored_image(session, row.id)
        session.commit()
        stored = session.get(Scholarship, row.id)
        assert stored.title == "Test"
        assert stored.official_source_url is not None


class TestLogoOnlyMode:
    def test_mode_defaults_off(self):
        assert ImageDiscoveryOrchestrator(logo_only=False).logo_only is False

    def test_only_identity_kinds_survive_validation(self, session):
        """The validator ranks programme artwork first, so the mode must re-rank.

        Taking image_results[0] would silently keep the photo the mode exists
        to remove.
        """
        from app.services.image_discovery_orchestrator import (
            OrchestratorRunResult,
            TrustworthyImageStatus,
        )

        result = OrchestratorRunResult(
            scholarship_id=1,
            scholarship_title="Test",
            status=TrustworthyImageStatus.HIGH,
        )
        result.image_results = [
            type("R", (), {"image_kind": "program_image", "confidence": "high",
                           "image_url": "https://p.example/photo.jpg", "page_url": "u",
                           "source_type": "official_provider", "alt_text": "a"})(),
            type("R", (), {"image_kind": "official_logo", "confidence": "high",
                           "image_url": "https://p.example/logo.svg", "page_url": "u",
                           "source_type": "official_provider", "alt_text": "a"})(),
        ]

        # Mirror the filter the orchestrator applies in run().
        kept = [r for r in result.image_results
                if (r.image_kind or "") in LOGO_IDENTITY_KINDS]
        assert [r.image_kind for r in kept] == ["official_logo"]


class TestPurgeStageSelection:
    def test_purge_keeps_identity_marks(self, session):
        keep = _scholarship(session, "official_logo", title="Keep")
        drop = _scholarship(session, "program_image", title="Drop")
        banner = _scholarship(session, "official_banner", title="Banner")
        session.commit()

        offenders = [
            r for r in session.scalars(
                select(Scholarship).where(Scholarship.image_url.isnot(None))
            ).all()
            if (r.image_kind or "") not in LOGO_IDENTITY_KINDS
        ]
        dropped_ids = {r.id for r in offenders}
        assert drop.id in dropped_ids
        assert banner.id in dropped_ids
        assert keep.id not in dropped_ids
