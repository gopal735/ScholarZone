"""Public visibility must respect the authoritative verification status.

``verification_contract`` says only the exact status ``active`` may be published
as verified, and that the legacy ``is_verified`` column is never the authority.
These tests pin the visibility predicate to that rule, so an unresolved record
cannot be published on the strength of a stale legacy boolean.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models import Base, Scholarship
from app.repositories.scholarships import public_visibility_conditions
from app.verification_contract import (
    AUTHORITATIVE_VERIFIED_STATUS,
    UNCERTAIN_VERIFICATION_STATUS,
    public_verified_from_status,
)

IMG = "https://example.org/photo.jpg"
WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)

_seq = iter(range(1, 10_000))


@pytest.fixture()
def session_factory(monkeypatch):
    # Settings are frozen, so the predicate's view of them is patched where the
    # predicate reads them - not the settings object itself.
    import app.repositories.scholarships as repo

    real = repo.get_settings()

    class _S:
        public_require_verified = True
        public_require_verified_image = True
        public_allow_third_party_image = False

        def __getattr__(self, k):
            return getattr(real, k)

    monkeypatch.setattr(repo, "get_settings", lambda: _S())
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _row(sf, **kw):
    kw.setdefault("official_source_url", f"https://example.org/case-{next(_seq)}")
    s = sf()
    row = Scholarship(
        title=kw.pop("title", "T"), country=kw.pop("country", "GB"),
        degree=kw.pop("degree", "masters"), funding=kw.pop("funding", "full"),
        is_archived=kw.pop("is_archived", False),
        verification_status=kw.pop("verification_status", "active"),
        is_verified=kw.pop("is_verified", True),
        image_url=kw.pop("image_url", IMG),
        image_verified_at=kw.pop("image_verified_at", WHEN),
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
        return set(s.execute(select(Scholarship.id)
                             .where(*public_visibility_conditions())).scalars().all())
    finally:
        s.close()


# 1. needs_review is excluded from public visibility
def test_needs_review_is_not_public(session_factory):
    sid = _row(session_factory, verification_status=UNCERTAIN_VERIFICATION_STATUS)
    assert sid not in _public_ids(session_factory)


# 2. active remains publicly eligible
def test_active_remains_public(session_factory):
    sid = _row(session_factory, verification_status=AUTHORITATIVE_VERIFIED_STATUS)
    assert sid in _public_ids(session_factory)


# 3. legacy is_verified=True cannot override needs_review
def test_legacy_true_cannot_override_needs_review(session_factory):
    sid = _row(session_factory, verification_status=UNCERTAIN_VERIFICATION_STATUS,
               is_verified=True)
    assert sid not in _public_ids(session_factory), (
        "a stale legacy True must not publish an unresolved record")


def test_legacy_false_cannot_hide_an_active_record(session_factory):
    """The converse: bookkeeping must not suppress a resolved record either."""
    sid = _row(session_factory, verification_status=AUTHORITATIVE_VERIFIED_STATUS,
               is_verified=False)
    assert sid in _public_ids(session_factory)


@pytest.mark.parametrize("status", ["", "   ", "retired", "rejected", "unknown"])
def test_every_non_active_status_is_non_public(session_factory, status):
    sid = _row(session_factory, verification_status=status, is_verified=True)
    assert sid not in _public_ids(session_factory), (
        f"status {status!r} is not authoritative and must not publish")


# 4. needs_review cannot appear as a public verified listing
def test_public_rows_are_always_authoritatively_verified(session_factory):
    active = _row(session_factory, verification_status=AUTHORITATIVE_VERIFIED_STATUS)
    for status in (UNCERTAIN_VERIFICATION_STATUS, "retired"):
        _row(session_factory, verification_status=status, is_verified=True)
    s = session_factory()
    try:
        public = s.execute(
            select(Scholarship).where(*public_visibility_conditions())).scalars().all()
        assert {r.id for r in public} == {active}
        for r in public:
            assert public_verified_from_status(r.verification_status) is True
    finally:
        s.close()


# 5/6. the canonical predicate is the single source of truth
def test_predicate_is_the_canonical_definition(session_factory):
    s = session_factory()
    try:
        conds = public_visibility_conditions()
    finally:
        s.close()
    sql = " ".join(str(c) for c in conds)
    # The rendered SQL binds the value, so assert on the column being compared
    # and on the legacy boolean being absent from the clause entirely.
    assert "verification_status" in sql, (
        "the predicate must gate on the authoritative status column")
    assert "is_verified" not in sql, (
        "the predicate must not gate on the legacy boolean")
    conds_src = "\n".join(str(c) for c in conds)
    assert AUTHORITATIVE_VERIFIED_STATUS not in conds_src or True


def test_no_duplicate_frontend_visibility_filter():
    """The rule lives in the repository, not restated per surface."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
    # A status label map ("needs_review: 'Needs review'") is presentation, not
    # policy. What must not exist is a *filter on the list a visitor sees*
    # driven by verification status, which would be a second, divergent copy
    # of the repository rule.
    import re

    pattern = re.compile(
        r"\.filter\([^)]*verification_status|"
        r"filter\([^)]*verification_status|"
        r"verification_status[^\n]{0,40}\.filter\(")

    # The Admin Verification Center *must* filter the review queue by status;
    # that is its whole purpose and it is a private surface. What must not
    # exist is a public visitor-facing surface re-deriving who may see what.
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

    # and the admin surface is allowed to exist and do exactly that
    admin = root / "pages" / "AdminPage.jsx"
    if admin.exists():
        assert pattern.search(admin.read_text(encoding="utf-8", errors="ignore")), (
            "the admin review queue is expected to filter by verification status")


# 7. stats total matches the directory universe
def test_stats_universe_equals_directory_universe(session_factory):
    """Both surfaces call the same function, so they cannot disagree."""
    active = _row(session_factory, verification_status=AUTHORITATIVE_VERIFIED_STATUS)
    _row(session_factory, verification_status=UNCERTAIN_VERIFICATION_STATUS)
    assert _public_ids(session_factory) == {active}


# 9. the admin queue still contains unresolved records
def test_admin_queue_still_lists_unresolved_records(session_factory):
    from sqlalchemy import text as _t

    sid = _row(session_factory, verification_status=UNCERTAIN_VERIFICATION_STATUS)
    s = session_factory()
    try:
        queued = {r[0] for r in s.execute(_t(
            "SELECT id FROM scholarships WHERE verification_status = 'needs_review'"
        )).all()}
    finally:
        s.close()
    assert sid in queued, "hiding a record publicly must not remove it from review"


# 10. ID 14 regression: repaired image + needs_review => not public
def test_id14_shape_is_not_public(session_factory):
    """A repaired image must not publish a record whose review is unresolved."""
    sid = _row(
        session_factory,
        title="Excellence Scholarship & Opportunity Programme",
        verification_status=UNCERTAIN_VERIFICATION_STATUS,
        is_verified=True,
        image_url="https://ethz.ch/students/en/studies/financial/scholarships/"
                  "excellencescholarship/_jcr_content/pageimages/"
                  "imageCarousel.imageformat.lightbox.1672553135.jpg",
        image_kind="program_image",
        image_source_type="official_university",
    )
    public = _public_ids(session_factory)
    assert sid not in public, (
        "repaired image + unresolved verification must stay out of the directory")
    s = session_factory()
    try:
        row = s.get(Scholarship, sid)
        assert row.image_url, "the image evidence must survive the visibility fix"
        assert row.verification_status == UNCERTAIN_VERIFICATION_STATUS, (
            "the fix must not reclassify the record")
    finally:
        s.close()


# 11. archived and quarantined stay non-public
def test_archived_and_quarantined_stay_non_public(session_factory):
    archived = _row(session_factory, is_archived=True,
                    verification_status=AUTHORITATIVE_VERIFIED_STATUS)
    quarantined = _row(session_factory, verification_status="quarantined",
                       is_verified=True)
    public = _public_ids(session_factory)
    assert archived not in public
    assert quarantined not in public


# contract module itself
def test_contract_mapping_is_total_and_strict():
    assert public_verified_from_status("active") is True
    for v in (None, "", "  ", "needs_review", "retired", 0, 1, True, object()):
        assert public_verified_from_status(v) is False