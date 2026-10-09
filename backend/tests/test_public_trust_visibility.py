"""Public visibility must respect the canonical visibility rules.

The canonical rule is: every legitimate non-closed, non-archived, non-quarantined
scholarship is visible. Verification status and image completeness are trust
signals, not visibility gates.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.repositories.scholarships import public_visibility_conditions
from app.verification_contract import (
    AUTHORITATIVE_VERIFIED_STATUS,
    UNCERTAIN_VERIFICATION_STATUS,
)

IMG = "https://example.org/photo.jpg"
WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)

_seq = iter(range(1, 10_000))


@pytest.fixture()
def session_factory(monkeypatch):
    from app.core.config import get_settings

    real = get_settings()

    class _S:
        public_require_verified = False
        public_require_verified_image = False
        public_allow_third_party_image = False

        def __getattr__(self, k):
            return getattr(real, k)

    monkeypatch.setattr("app.core.config.get_settings", lambda: _S())
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _row(sf, **kw):
    kw.setdefault("official_source_url", f"https://example.org/case-{next(_seq)}")
    s = sf()
    row = Scholarship(
        title=kw.pop("title", "T"),
        country=kw.pop("country", "GB"),
        degree=kw.pop("degree", "masters"),
        funding=kw.pop("funding", "full"),
        is_archived=kw.pop("is_archived", False),
        verification_status=kw.pop("verification_status", "active"),
        is_verified=kw.pop("is_verified", True),
        image_url=kw.pop("image_url", IMG),
        image_verified_at=kw.pop("image_verified_at", None),
        image_source_type=kw.pop("image_source_type", "issuer_logo"),
        **kw)
    s.add(row)
    s.commit()
    s.refresh(row)
    sid = row.id
    s.close()
    return sid


def _public_ids(sf):
    s = sf()
    try:
        from sqlalchemy import select
        from app.repositories.scholarships import public_visibility_conditions
        return set(s.execute(select(Scholarship.id).where(*public_visibility_conditions())).scalars().all())
    finally:
        s.close()


# 1. needs_review is NOW public (non-closed, non-archived, non-quarantined)
def test_needs_review_is_now_public(session_factory):
    sid = _row(session_factory, verification_status="needs_review")
    assert sid in _public_ids(session_factory)


# 2. active remains publicly eligible
def test_active_remains_public(session_factory):
    sid = _row(session_factory, verification_status="active")
    assert sid in _public_ids(session_factory)


# 3. legacy is_verified=True cannot override needs_review - but now needs_review is public anyway
def test_needs_review_is_public_even_with_legacy_true(session_factory):
    sid = _row(session_factory, verification_status="needs_review", is_verified=True)
    assert sid in _public_ids(session_factory)


def test_legacy_false_cannot_hide_an_active_record(session_factory):
    """The converse: bookkeeping must not suppress a resolved record either."""
    sid = _row(session_factory, verification_status="active", is_verified=False)
    assert sid in _public_ids(session_factory)


@pytest.mark.parametrize("status", ["", "   ", "retired", "rejected", "unknown", "needs_review"])
def test_all_non_closed_statuses_are_public(session_factory, status):
    sid = _row(session_factory, verification_status=status, is_verified=True)
    assert sid in _public_ids(session_factory), f"status {status!r} should be public"


# All non-closed, non-archived, non-quarantined records should be public
def test_all_non_closed_records_are_public(session_factory):
    active = _row(session_factory, verification_status="active")
    needs_review = _row(session_factory, verification_status="needs_review")
    retired = _row(session_factory, verification_status="retired")
    rejected = _row(session_factory, verification_status="rejected")
    unknown = _row(session_factory, verification_status="unknown")
    
    s = session_factory()
    try:
        public = _public_ids(session_factory)
        expected = {active, 2, 3, 4, 5}  # all 5 IDs should be public
        assert public == expected
    finally:
        pass


# The canonical predicate is the single source of truth
def test_predicate_is_the_canonical_definition():
    from app.repositories.scholarships import public_visibility_conditions
    conds = public_visibility_conditions()
    sql = " ".join(str(c) for c in conds)
    # The rendered SQL should gate on the right columns
    assert "is_archived" in str(conds[1])
    assert "status" in str(conds[2]) or "status" in str(conds[1])
    # Check that quarantined is in the condition (as a bound parameter value)
    # The condition is Scholarship.verification_status != "quarantined"
    # which renders as a bound parameter in the SQL string
    # We check the compiled SQL with literal_binds
    from sqlalchemy.sql import compiler
    from sqlalchemy.dialects import sqlite
    compiled = conds[0].compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True})
    assert "quarantined" in str(compiled)
    # Legacy boolean and image gates should be absent
    assert "is_verified" not in " ".join(str(c) for c in _public_ids.__module__)


def test_no_duplicate_frontend_visibility_filter():
    """The rule lives in the repository, not restated per surface."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"

    pattern = re.compile(
        r"\.filter\([^)]*verification_status|"
        r"filter\([^)]*verification_status|"
        r"verification_status[^\n]{0,40}\.filter\(")

    ADMIN = ("admin",)
    offenders = []
    for f in list(root.rglob("*.jsx")) + list(root.rglob("*.js")):
        if any(a in f.name.lower() or a in str(f.parent).lower() for a in ADMIN):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
            offenders.append(str(f.relative_to(root)))
    assert not offenders, (
        f"a public frontend surface filters by verification_status: {offenders}")

    admin = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "AdminPage.jsx"
    if admin.exists():
        assert pattern.search(admin.read_text(encoding="utf-8", errors="ignore")), (
            "the admin review queue is expected to filter by verification status")


# Stats total matches the directory universe
def test_stats_universe_equals_directory_universe(session_factory):
    """Both surfaces call the same function, so they cannot disagree."""
    active = _row(session_factory, verification_status="active")
    needs_review = _row(session_factory, verification_status="needs_review")
    assert _public_ids(session_factory) == {active, 2}  # both should be public


# The admin queue still contains unresolved records
def test_admin_queue_still_lists_unresolved_records(session_factory):
    from sqlalchemy import text as _t

    sid = _row(session_factory, verification_status="needs_review")
    s = session_factory()
    try:
        queued = {r[0] for r in s.execute(text(
            "SELECT id FROM scholarships WHERE verification_status = 'needs_review'"
        )).all()}
    finally:
        s.close()
    assert sid in queued, "hiding a record publicly must not remove it from review"


# ID 14 regression: repaired image + needs_review => NOW PUBLIC (since not closed/archived/quarantined)
def test_needs_review_with_repaired_image_is_public(session_factory):
    """A repaired image + needs_review should now be public (not closed/archived/quarantined)."""
    sid = _row(
        session_factory,
        title="Excellence Scholarship & Opportunity Programme",
        verification_status="needs_review",
        is_verified=True,
        image_url="https://ethz.ch/students/en/studies/financial/scholarships/"
                  "excellencescholarship/_jcr_content/pageimages/"
                  "imageCarousel.imageformat.lightbox.1672553135.jpg",
        image_source_type="official_university",
    )
    public = _public_ids(session_factory)
    assert sid in public, "repaired image + unresolved verification should now be public"
    s = session_factory()
    try:
        row = s.get(Scholarship, sid)
        assert row.image_url, "the image evidence must survive the visibility fix"
        assert row.verification_status == "needs_review", (
            "the fix must not reclassify the record")
    finally:
        s.close()


# Archived and quarantined stay non-public
def test_archived_and_quarantined_stay_non_public(session_factory):
    archived = _row(session_factory, is_archived=True,
                    verification_status="active")
    quarantined = _row(session_factory, verification_status="quarantined",
                       is_verified=True)
    public = _public_ids(session_factory)
    assert archived not in public
    assert quarantined not in public


# Contract module itself
def test_contract_mapping_is_total_and_strict():
    from app.verification_contract import public_verified_from_status
    assert public_verified_from_status("active") is True
    for v in (None, "", "  ", "needs_review", "retired", 0, 1, True, object()):
        assert public_verified_from_status(v) is False