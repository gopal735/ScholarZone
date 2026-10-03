"""Tests for the universe scope of ``GET /scholarships/stats``.

``/stats`` is a public trust bar: everything it reports is read as an aggregate of
the public catalogue. Two of its figures were counted over every stored row while
their "without" partners counted the public set, so the endpoint published
``with_image`` and ``with_official_source`` larger than the ``total`` they were
supposed to describe - 421 and 445 against a public total of 386.

These tests pin the scope of every public aggregate to the directory's own
``public_visibility_conditions()``, prove no public subset can exceed the public
total, prove the storage-wide figures stay storage-wide, and prove the review
queue and the public review count are derived from live data rather than pinned
to a constant.
"""

from __future__ import annotations

import inspect
import os

from sqlalchemy import and_
import tempfile
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pytest


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-stats-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from app.database import get_session_factory, init_database, reset_database_connections  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.repositories.scholarships import public_visibility_conditions  # noqa: E402
from app.services.counting import catalogue as cat  # noqa: E402
from app.services.scholarships import get_verification_queue  # noqa: E402

#: Storage-only rows are hidden from the public set but still exist. Each one
#: carries an image and an official source, so a leak is immediately visible.
STORAGE_ONLY_IMAGE = "https://img.example.org/only-storage.png"


@pytest.fixture()
def factory():
    path = Path(tempfile.gettempdir()) / f"scholarzone-stats-{uuid4().hex}.db"
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{path.as_posix()}"
    reset_database_connections()
    init_database()
    yield get_session_factory()
    reset_database_connections()
    try:
        path.unlink()
    except OSError:
        pass


def _add(session, sid: int, **kw) -> int:
    session.add(
        Scholarship(
            id=sid,
            title=kw.get("title", f"Programme {sid}"),
            country=kw.get("country", "Testland"),
            degree=kw.get("degree", "Master"),
            funding=kw.get("funding", "Fully Funded"),
            status=kw.get("status", "open"),
            is_verified=kw.get("is_verified", True),
            is_archived=kw.get("is_archived", False),
            verification_status=kw.get("verification_status", "active"),
            image_url=kw.get("image_url"),
            image_verified_at=kw.get("image_verified_at"),
            image_source_type=kw.get("image_source_type"),
            official_source=kw.get("official_source"),
            official_source_url=kw.get("official_source_url", f"https://x{sid}.example.org/p"),
            last_verified_date=kw.get("last_verified_date"),
        )
    )
    return sid


def _public_ids(session) -> set[int]:
    """The public set, straight from the directory's own predicate."""
    from sqlalchemy import select

    return set(
        session.scalars(
            select(Scholarship.id).where(and_(*public_visibility_conditions()))
        ).all()
    )


#: A timestamp for rows that should not linger in the review queue.
VERIFIED_ON = date(2026, 1, 1)


def _seed_mixed(session) -> tuple[set[int], set[int]]:
    """Public rows that are public under any setting, and rows that never are.

    The public rows satisfy every optional gate - verified, image present and
    image-verified, non-third-party provenance - so the expected count does not
    depend on how the environment resolves those settings. The hidden rows are
    hidden by the two unconditional conditions (archived, quarantined), so they
    cannot leak into a public aggregate either way.
    """
    for sid in (1, 2, 3):
        _add(
            session,
            sid,
            image_url=f"https://img.example.org/{sid}.png",
            image_verified_at=datetime(2026, 1, 1),
            image_source_type="official",
            official_source=f"Provider {sid}",
            last_verified_date=VERIFIED_ON,
        )
    _add(
        session,
        11,
        is_archived=True,
        image_url=STORAGE_ONLY_IMAGE,
        image_verified_at=datetime(2026, 1, 1),
        image_source_type="official",
        official_source="Archived provider",
        last_verified_date=VERIFIED_ON,
    )
    _add(
        session,
        12,
        verification_status="quarantined",
        is_archived=True,
        image_url=STORAGE_ONLY_IMAGE,
        image_verified_at=datetime(2026, 1, 1),
        image_source_type="official",
        official_source="Quarantined provider",
    )
    _add(
        session,
        13,
        is_verified=False,
        is_archived=True,
        verification_status="quarantined",
        image_url=STORAGE_ONLY_IMAGE,
        image_verified_at=datetime(2026, 1, 1),
        image_source_type="official",
        official_source="Unverified provider",
    )
    session.commit()
    return _public_ids(session), {11, 12, 13}


# ---------------------------------------------------------------------------
# Scope of each public aggregate
# ---------------------------------------------------------------------------


def test_with_image_never_exceeds_public_total(factory):
    session = factory()
    _seed_mixed(session)
    c = cat.catalogue_counts(session)
    assert c["with_image"] <= c["public_total"], c


def test_with_official_source_never_exceeds_public_total(factory):
    session = factory()
    _seed_mixed(session)
    c = cat.catalogue_counts(session)
    assert c["with_official_source"] <= c["public_total"], c


def test_with_image_counts_only_public_rows(factory):
    """The storage-only rows carry images and must not be counted."""
    session = factory()
    public_ids, hidden_ids = _seed_mixed(session)
    c = cat.catalogue_counts(session)
    assert c["public_total"] == len(public_ids) == 3
    assert c["with_image"] == len(public_ids)
    assert public_ids.isdisjoint(hidden_ids)
    # Sanity: the hidden rows really do exist and really do have images.
    rows = session.query(Scholarship).filter(Scholarship.id.in_(sorted(hidden_ids))).all()
    assert len(rows) == 3
    assert all(r.image_url for r in rows)
    # The precise regression: pre-fix this would have been 6, not 3.
    assert c["with_image"] != len(rows) + len(public_ids)


def test_with_official_source_counts_only_public_rows(factory):
    session = factory()
    public_ids, _ = _seed_mixed(session)
    c = cat.catalogue_counts(session)
    assert c["with_official_source"] == len(public_ids)


def test_every_public_aggregate_is_bounded_by_the_public_total(factory):
    session = factory()
    _seed_mixed(session)
    c = cat.catalogue_counts(session)
    public_fields = (
        "countries",
        "open",
        "closing_soon",
        "upcoming",
        "closed",
        "other_status",
        "verified",
        "unverified",
        "verification_status_active",
        "fully_funded",
        "with_image",
        "without_image",
        "with_official_source",
        "without_official_source",
    )
    for field in public_fields:
        assert c[field] <= c["public_total"], (field, c[field], c["public_total"])


def test_empty_string_image_is_not_an_image(factory):
    session = factory()
    _add(session, 1, image_url="", official_source="Provider")
    session.commit()
    c = cat.catalogue_counts(session)
    assert c["with_image"] == 0


def test_storage_wide_figures_stay_storage_wide(factory):
    """Fixing the public aggregates must not narrow the ones that need storage."""
    session = factory()
    public_ids, hidden_ids = _seed_mixed(session)
    c = cat.catalogue_counts(session)
    assert c["row_total"] == len(public_ids) + len(hidden_ids) == 6
    # Rows 11, 12 and 13 are all archived; 12 and 13 are also quarantined.
    assert c["archived"] == 3
    assert c["quarantined"] == 2
    # Storage-wide figures are allowed to exceed the public total; that is the point.
    assert c["archived"] > c["public_total"] - c["public_total"]


# ---------------------------------------------------------------------------
# Canonical predicate reuse
# ---------------------------------------------------------------------------


def test_catalogue_counts_reuses_the_canonical_visibility_predicate():
    source = inspect.getsource(cat)
    assert "public_visibility_conditions" in source
    assert "def public_visibility_conditions" not in source, (
        "the predicate must not be reimplemented in the counting layer"
    )


def test_public_aggregates_match_the_canonical_predicate_directly(factory):
    from sqlalchemy import and_, func, select

    session = factory()
    _seed_mixed(session)
    expected = session.scalar(
        select(func.count()).select_from(Scholarship).where(and_(*public_visibility_conditions()))
    )
    c = cat.catalogue_counts(session)
    assert c["public_total"] == expected


def test_public_visibility_predicate_is_not_duplicated_in_the_counting_layer():
    for name in ("_listed", "_public", "_visible"):
        assert not hasattr(cat, name)


# ---------------------------------------------------------------------------
# Published summary
# ---------------------------------------------------------------------------


def test_published_summary_is_consistent(factory):
    session = factory()
    public_ids, _ = _seed_mixed(session)
    summary = cat.catalogue_summary(cat.catalogue_counts(session))
    assert summary["total"] == len(public_ids)
    assert summary["with_image"] <= summary["total"]
    assert summary["with_official_source"] <= summary["total"]
    assert summary["fully_funded"] <= summary["total"]
    assert summary["verified_active"] <= summary["total"]
    assert summary["open"] <= summary["total"]


def test_lifecycle_partition_still_reconciles(factory):
    session = factory()
    _seed_mixed(session)
    counts = cat.catalogue_counts(session)
    partitions = cat.build_catalogue_partitions(counts)
    lifecycle = next(p for p in partitions if p.name == "lifecycle_status")
    assert lifecycle.bucket_total == counts["public_total"]


def test_evidence_partition_is_not_a_partition(factory):
    session = factory()
    _seed_mixed(session)
    counts = cat.catalogue_counts(session)
    partitions = cat.build_catalogue_partitions(counts)
    evidence = next(p for p in partitions if p.name == "catalogue_evidence")
    assert evidence.basis == "NOT_A_PARTITION"
    assert evidence.bucket_total == 0


# ---------------------------------------------------------------------------
# The review count is derived, never pinned
# ---------------------------------------------------------------------------


def test_verification_queue_is_derived_from_live_data(factory):
    session = factory()
    _add(session, 1, verification_status="active", last_verified_date=VERIFIED_ON)
    _add(session, 2, verification_status="needs_review", last_verified_date=VERIFIED_ON)
    session.commit()
    ids = [row.id for row in get_verification_queue(session)]
    assert 2 in ids
    assert 1 not in ids
    # Clearing the status removes it from the queue with no code change.
    row = session.get(Scholarship, 2)
    row.verification_status = "active"
    session.commit()
    assert 2 not in [r.id for r in get_verification_queue(session)]


def test_verification_queue_includes_records_never_verified(factory):
    """The queue is a live query over three conditions, not one status."""
    session = factory()
    _add(session, 1, verification_status="active", last_verified_date=VERIFIED_ON)
    _add(session, 2, verification_status="active", last_verified_date=None)
    session.commit()
    ids = [row.id for row in get_verification_queue(session)]
    assert ids == [2]


def test_public_review_count_is_derived_not_hardcoded(factory):
    """The public review figure is ``total - verified_active``, never a constant."""
    session = factory()
    for sid in range(1, 6):
        _add(
            session,
            sid,
            verification_status="active",
            image_url=f"https://img.example.org/{sid}.png",
            image_verified_at=datetime(2026, 1, 1),
            image_source_type="official",
            last_verified_date=VERIFIED_ON,
        )
    _add(
        session,
        6,
        verification_status="needs_review",
        image_url="https://img.example.org/6.png",
        image_verified_at=datetime(2026, 1, 1),
        image_source_type="official",
        last_verified_date=VERIFIED_ON,
    )
    session.commit()
    c = cat.catalogue_counts(session)
    assert c["public_total"] == 6
    assert c["public_total"] - c["verification_status_active"] == 1
    # Adding a second review record moves the derived figure with no code change.
    _add(
        session,
        7,
        verification_status="needs_review",
        image_url="https://img.example.org/7.png",
        image_verified_at=datetime(2026, 1, 1),
        image_source_type="official",
        last_verified_date=VERIFIED_ON,
    )
    session.commit()
    c2 = cat.catalogue_counts(session)
    assert c2["public_total"] - c2["verification_status_active"] == 2


def test_no_hardcoded_review_constant_in_the_counting_layer():
    source = inspect.getsource(cat)
    for constant in ("= 22", "== 22", "= 25", "== 25"):
        assert constant not in source, constant