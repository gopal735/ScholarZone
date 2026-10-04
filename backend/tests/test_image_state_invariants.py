"""Image-state invariants: a record with no image is never 'complete'.

`image_verified_at` records when an image was verified. It is evidence about an
image, not the image itself, and it can outlive the image it described. These
tests pin the rule that the presence of the image - `image_url` - is the only
thing that makes a record complete, so stale residue can never strand a record
outside evaluation.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.image_coverage_runner import ImageCoverageRunner
from app.services.image_evaluation_status import ImageEvaluationStatus

STALE = datetime(2026, 1, 1, tzinfo=timezone.utc)

_seq = iter(range(1, 10_000))


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _row(session, **kw):
    kw.setdefault("official_source_url", f"https://example.org/case-{next(_seq)}")
    row = Scholarship(
        title=kw.pop("title", "T"), country=kw.pop("country", "GB"),
        degree=kw.pop("degree", "masters"), funding=kw.pop("funding", "full"),
        verification_status=kw.pop("verification_status", "active"),
        is_verified=kw.pop("is_verified", True), is_archived=False, **kw)
    session.add(row)
    session.commit()
    return row


def _runner(session, **kw):
    return ImageCoverageRunner(sessionmaker(bind=session.get_bind()), **kw)


def _in_scope(session, sid, **kw):
    return _runner(session, **kw)._in_scope_ids(
        ids=[sid], start_after=None, limit=None)[1]


# 1. only_missing selects on actual missing image state
def test_only_missing_selects_the_absent_image_not_the_timestamp(session):
    stale = _row(session, image_url=None, image_verified_at=STALE)
    assert _in_scope(session, stale.id, skip_terminally_evaluated=True) == 1


def test_record_with_an_image_is_not_selected(session):
    has = _row(session, image_url="https://example.org/a.png",
               image_verified_at=STALE, image_kind="program_image")
    assert _in_scope(session, has.id, skip_terminally_evaluated=True) == 0


# 2. stale image_verified_at cannot suppress evaluation
def test_stale_timestamp_does_not_suppress_evaluation(session):
    stale = _row(session, image_url=None, image_verified_at=STALE)
    assert _in_scope(session, stale.id) == 1
    assert _in_scope(session, stale.id, only_missing=False) == 1


# 3. verified status requires an image
def test_verified_without_an_image_is_never_treated_as_complete(session):
    broken = _row(session, image_url=None, image_evaluation_status="verified")
    assert _in_scope(session, broken.id, skip_terminally_evaluated=True) == 1, (
        "a verified-without-image record must stay eligible for recovery")


def test_verified_status_vocabulary_is_terminal_but_not_exempting(session):
    assert "verified" in {
        getattr(s, "value", s) for s in ImageEvaluationStatus}


# 4. image_url IS NULL keeps the record eligible
def test_no_image_keeps_record_eligible(session):
    for i in range(3):
        r = _row(session, image_url=None, image_verified_at=STALE if i else None)
        assert _in_scope(session, r.id) == 1


# 5. a valid persisted image carries consistent metadata
def test_valid_image_metadata_is_internally_consistent(session):
    r = _row(session, image_url="https://example.org/a.png",
             image_source_url="https://example.org/page",
             image_source_type="issuer_logo", image_kind="official_logo",
             image_verified_at=STALE,
             image_evaluation_status="verified")
    assert r.image_url and r.image_verified_at
    assert r.image_evaluation_status == "verified"
    assert _in_scope(session, r.id) == 0


# 6. source_blocked stays distinct from no_official_image
def test_source_blocked_is_distinct_from_no_official_image():
    assert (ImageEvaluationStatus.SOURCE_BLOCKED
            != ImageEvaluationStatus.NO_OFFICIAL_IMAGE)


# 7. evaluation recording is not suppressed by a stale timestamp
def test_evaluation_verdict_can_be_recorded_despite_stale_timestamp(session):
    stale = _row(session, image_url=None, image_verified_at=STALE)
    runner = _runner(session, dry_run=False)
    runner._record_evaluation(stale.id, str(ImageEvaluationStatus.SOURCE_BLOCKED))
    session.expire_all()
    assert stale.image_evaluation_status == str(ImageEvaluationStatus.SOURCE_BLOCKED)


def test_evaluation_verdict_is_not_overwritten_when_an_image_exists(session):
    has = _row(session, image_url="https://example.org/a.png",
               image_verified_at=STALE, image_evaluation_status="verified")
    runner = _runner(session, dry_run=False)
    runner._record_evaluation(has.id, str(ImageEvaluationStatus.NO_OFFICIAL_IMAGE))
    session.expire_all()
    assert has.image_evaluation_status == "verified", (
        "an existing verified image must keep its verdict")


# 8. repeated evaluation is idempotent
def test_repeated_scope_evaluation_is_idempotent(session):
    stale = _row(session, image_url=None, image_verified_at=STALE)
    runner = _runner(session, dry_run=False)
    for _ in range(3):
        runner._record_evaluation(stale.id, str(ImageEvaluationStatus.SOURCE_BLOCKED))
    session.expire_all()
    assert stale.image_evaluation_status == str(ImageEvaluationStatus.SOURCE_BLOCKED)
    assert _in_scope(session, stale.id) == 1, (
        "a blocked verdict must not remove the record from future attempts")


# 563-style residue specifically
def test_563_style_residue_is_recoverable(session):
    """image_url NULL, image_verified_at set, status NULL - must be selectable."""
    residue = _row(session, title="Alberta Innovates Graduate Student Scholarships",
                   image_url=None, image_verified_at=STALE,
                   image_evaluation_status=None,
                   verification_status="active")
    assert _in_scope(session, residue.id, skip_terminally_evaluated=True) == 1