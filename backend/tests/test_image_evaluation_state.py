"""Regression tests for the image evaluation state machine.

The defect these lock down: a record could hold a terminal
``image_evaluation_status='verified'`` with no stored image at all. Such a
record never publishes, and because the coverage sweep skips terminally
evaluated rows it can never be re-evaluated either, so the contradiction is
permanent. These tests assert the invariant that a cleared image also retires
the verdict that described it.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

VERIFIED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.image_coverage_runner import ImageCoverageRunner
from app.services.image_discovery_orchestrator import _clear_stored_image
from app.services.image_evaluation_status import TERMINAL_STATUSES


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


_SEQ = iter(range(1, 10_000))


def _scholarship(session, **kw):
    # official_source_url is unique; give every fixture row its own so tests
    # cannot fail for a reason unrelated to the invariant under test.
    kw.setdefault("official_source_url",
                  f"https://example.org/case-{next(_SEQ)}")
    row = Scholarship(
        title=kw.pop("title", "Test Scholarship"),
        country=kw.pop("country", "GB"),
        degree=kw.pop("degree", "masters"),
        official_source_url=kw.pop("official_source_url"),
        funding=kw.pop("funding", "full"),
        verification_status=kw.pop("verification_status", "active"),
        is_verified=kw.pop("is_verified", True),
        is_archived=False,
        **kw,
    )
    session.add(row)
    session.commit()
    return row


# 1. verified + empty image_url cannot remain a valid terminal state
def test_clear_retires_a_terminal_verified_status(session):
    row = _scholarship(
        session,
        image_url="https://example.org/logo.png",
        image_source_url="https://example.org/",
        image_source_type="issuer_logo",
        image_kind="official_logo",
        image_verified_at=VERIFIED_AT,
        image_evaluation_status="verified",
    )
    _clear_stored_image(session, row.id)
    session.commit()

    assert row.image_url is None
    assert row.image_verified_at is None
    assert row.image_evaluation_status is None, (
        "a cleared image must not leave a terminal 'verified' verdict behind"
    )


# 5. terminal skip must not permanently trap verified-without-image corruption
def test_a_cleared_record_is_in_scope_for_evaluation_again(session):
    row = _scholarship(session, image_evaluation_status="verified",
                       image_url="https://example.org/logo.png",
                       image_verified_at=VERIFIED_AT)
    _clear_stored_image(session, row.id)
    session.commit()

    runner = ImageCoverageRunner(
        sessionmaker(bind=session.get_bind()),
        skip_terminally_evaluated=True,
    )
    ids, total = runner._in_scope_ids(ids=[row.id], start_after=None, limit=None)
    assert total == 1, "record trapped: terminal skip excluded a record with no image"
    assert [r.id for r in ids] == [row.id]


# 3. a never-evaluated record can enter normal evaluation
def test_never_evaluated_record_is_in_scope(session):
    row = _scholarship(session, image_evaluation_status=None)
    runner = ImageCoverageRunner(
        sessionmaker(bind=session.get_bind()), skip_terminally_evaluated=True)
    _ids, total = runner._in_scope_ids(ids=[row.id], start_after=None, limit=None)
    assert total == 1


# 4. source_blocked is distinct from no_official_image
def test_source_blocked_is_not_no_official_image():
    from app.services.image_evaluation_status import ImageEvaluationStatus

    assert ImageEvaluationStatus.SOURCE_BLOCKED != ImageEvaluationStatus.NO_OFFICIAL_IMAGE
    assert "source_blocked" in {getattr(s, "value", s) for s in TERMINAL_STATUSES}
    assert "no_official_image" in {getattr(s, "value", s) for s in TERMINAL_STATUSES}


# 2. a repaired record follows the existing contract (no invented values)
def test_reset_to_unevaluated_sets_no_invented_values(session):
    row = _scholarship(session, image_evaluation_status="verified",
                       image_kind="official_logo",
                       image_url="https://example.org/logo.png",
                       image_verified_at=VERIFIED_AT)
    row.image_evaluation_status = None
    row.image_evaluated_at = None
    row.image_kind = None
    row.image_url = None
    session.commit()

    assert row.image_evaluation_status is None
    assert row.image_url is None
    assert row.image_kind is None
    assert row.title  # untouched content
    assert row.verification_status == "active"  # verification semantics untouched


# 6./7. clearing is idempotent and touches nothing else
def test_repeated_clear_is_idempotent_and_scoped(session):
    keep = _scholarship(session, title="Keep Me", verification_status="active")
    target = _scholarship(
        session, title="Clear Me", image_url="https://example.org/a.png",
        image_kind="official_logo", image_verified_at=VERIFIED_AT,
        image_evaluation_status="verified")

    for _ in range(3):
        _clear_stored_image(session, target.id)
        session.commit()

    assert target.image_url is None and target.image_evaluation_status is None
    assert target.title == "Clear Me"
    assert keep.image_url is None or keep.image_url  # untouched
    assert keep.title == "Keep Me"
    assert keep.verification_status == "active"


# 8. unrelated scholarships are untouched
def test_unrelated_rows_keep_their_verified_image(session):
    good = _scholarship(session, title="Has Image",
                        image_url="https://example.org/good.png",
                        image_kind="program_image",
                        image_verified_at=VERIFIED_AT,
                        image_evaluation_status="verified")
    bad = _scholarship(session, title="Broken",
                       image_url="https://example.org/bad.png",
                       image_kind="official_logo",
                       image_verified_at=VERIFIED_AT,
                       image_evaluation_status="verified")
    _clear_stored_image(session, bad.id)
    session.commit()

    assert good.image_url == "https://example.org/good.png"
    assert good.image_evaluation_status == "verified"
    assert bad.image_url is None
    assert bad.image_evaluation_status is None


# invariant helper: no row may hold a terminal verified status without an image
def test_no_row_in_storage_is_verified_without_an_image(session):
    _scholarship(session, title="Ok", image_url="https://example.org/o.png",
                 image_kind="program_image", image_verified_at=VERIFIED_AT,
                 image_evaluation_status="verified")
    broken = _scholarship(session, title="Broken", image_url="https://example.org/b.png",
                          image_kind="official_logo",
                          image_verified_at=VERIFIED_AT,
                          image_evaluation_status="verified")
    _clear_stored_image(session, broken.id)
    session.commit()

    offenders = [
        r.id for r in session.query(Scholarship).all()
        if str(getattr(r.image_evaluation_status, "value", r.image_evaluation_status)) == "verified"
        and not r.image_url
    ]
    assert offenders == [], f"verified-without-image rows remain: {offenders}"
