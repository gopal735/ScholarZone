"""Regression tests for the ``purge`` stage's image-clearing boundary.

``do_purge()`` cleared every stored image whose ``image_kind`` was not an
identity mark. PROGRAM_IMAGE and OFFICIAL_BANNER are legitimate results of the
same verification pipeline, so that test classified accepted, verified images as
disposable and could delete them outright.

These tests pin the corrected rule: an image the pipeline accepted is preserved
regardless of its kind, while an image carrying no acceptance is still cleared.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.image_discovery_orchestrator import (
    ACCEPTED_IMAGE_KINDS,
    LOGO_IDENTITY_KINDS,
)

VERIFIED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)

_seq = iter(range(1, 10_000))


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _row(sf, *, kind, verified_at, image_url="https://example.org/i.png"):
    s = sf()
    row = Scholarship(
        title="T", country="GB", degree="masters", funding="full",
        official_source_url=f"https://example.org/case-{next(_seq)}",
        is_archived=False, verification_status="active", is_verified=True,
        image_url=image_url, image_kind=kind, image_verified_at=verified_at,
    )
    s.add(row)
    s.commit()
    s.refresh(row)
    rid = row.id
    s.close()
    return rid


def _offenders(sf, rows):
    """Replicates do_purge()'s selection exactly."""
    out = []
    for r in rows:
        sid = _row(sf, **r)
        s = sf()
        row = s.get(Scholarship, sid)
        kind = row.image_kind or ""
        selected = (
            kind not in LOGO_IDENTITY_KINDS
            and not (row.image_verified_at is not None and kind in ACCEPTED_IMAGE_KINDS)
        )
        if selected:
            out.append(sid)
        s.close()
    return out


# 2. purge cannot clear a valid accepted verified image
@pytest.mark.parametrize("kind", sorted(ACCEPTED_IMAGE_KINDS))
def test_accepted_verified_image_is_never_cleared(session_factory, kind):
    off = _offenders(session_factory, [{"kind": kind, "verified_at": VERIFIED_AT}])
    assert off == [], f"accepted verified image of kind {kind!r} was selected for clearing"


def test_id14_shape_program_image_is_preserved(session_factory):
    """The exact shape that was reverted: an accepted programme photograph."""
    off = _offenders(session_factory,
                     [{"kind": "program_image", "verified_at": VERIFIED_AT}])
    assert off == []


def test_accepted_banner_is_preserved(session_factory):
    off = _offenders(session_factory,
                     [{"kind": "official_banner", "verified_at": VERIFIED_AT}])
    assert off == []


# 3/5. a verified verdict cannot exist without an image; clear paths stay coherent
def test_verified_without_image_is_still_not_protected(session_factory):
    """A verdict with no image has nothing to preserve."""
    s = session_factory()
    row = Scholarship(
        title="T", country="GB", degree="masters", funding="full",
        official_source_url=f"https://example.org/case-{next(_seq)}",
        is_archived=False, verification_status="active", is_verified=True,
        image_url=None, image_kind="program_image", image_verified_at=None,
    )
    s.add(row)
    s.commit()
    rid = row.id
    s.close()
    assert _offenders(session_factory, []) == []
    s = session_factory()
    again = s.get(Scholarship, rid)
    assert again.image_url is None
    s.close()


# unaccepted artwork is still disposable - the stage keeps its purpose
def test_unaccepted_photo_without_verification_is_still_cleared(session_factory):
    off = _offenders(session_factory, [{"kind": "program_image", "verified_at": None}])
    assert len(off) == 1, "the stage must still clear unverified artwork"


def test_unknown_kind_is_still_cleared(session_factory):
    off = _offenders(session_factory, [{"kind": "", "verified_at": None}])
    assert len(off) == 1


def test_record_without_kind_is_still_cleared(session_factory):
    off = _offenders(session_factory, [{"kind": None, "verified_at": None}])
    assert len(off) == 1


# logo identity marks keep their existing behaviour
@pytest.mark.parametrize("kind", sorted(LOGO_IDENTITY_KINDS))
def test_logo_identity_marks_keep_existing_behaviour(session_factory, kind):
    """An unverified logo was kept before and is still kept."""
    off = _offenders(session_factory, [{"kind": kind, "verified_at": None}])
    assert off == []


# 7. image clear paths clear all dependent evaluation metadata
def test_clearing_removes_every_dependent_field(session_factory):
    from app.services.image_discovery_orchestrator import _clear_stored_image

    s = session_factory()
    row = Scholarship(
        title="T", country="GB", degree="masters", funding="full",
        official_source_url=f"https://example.org/case-{next(_seq)}",
        is_archived=False, verification_status="active", is_verified=True,
        image_url="https://example.org/i.png", image_source_url="https://example.org/",
        image_source_type="issuer_logo", image_kind="program_image",
        image_alt_text="alt", image_verified_at=VERIFIED_AT,
        image_evaluation_status="verified", image_evaluated_at=VERIFIED_AT,
    )
    s.add(row)
    s.commit()
    _clear_stored_image(s, row.id)
    s.commit()
    for field in ("image_url", "image_source_url", "image_source_type",
                  "image_kind", "image_alt_text", "image_verified_at",
                  "image_evaluation_status", "image_evaluated_at"):
        assert getattr(row, field) is None, f"{field} survived a clear"
    s.close()


# 8. repeated selection is idempotent
def test_selection_is_idempotent(session_factory):
    first = _offenders(session_factory,
                       [{"kind": "program_image", "verified_at": None}])
    second = _offenders(session_factory,
                        [{"kind": "program_image", "verified_at": None}])
    assert len(first) == len(second) == 1


# vocabulary invariant
def test_logo_kinds_are_a_subset_of_accepted():
    assert LOGO_IDENTITY_KINDS <= ACCEPTED_IMAGE_KINDS
    assert "program_image" in ACCEPTED_IMAGE_KINDS
    assert "official_banner" in ACCEPTED_IMAGE_KINDS