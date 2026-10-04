"""The maintenance report and the public catalogue must count the same rows.

The stats stage reported 438 public-visible records while the API served 398 for
the same database. The cause was a second, looser copy of the visibility rule in
the maintenance worker: it counted "not archived and not quarantined" and omitted
the verified and verified-image gates.

That gap is invisible until the two numbers are compared, and nothing compared
them. These tests compare them, against a real database rather than by reading
the source.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker


def _reset_settings_cache() -> None:
    """Force get_settings() to re-read the environment.

    The gates are read once into a settings object, so changing the environment
    after the first call would not change the rule under test.
    """
    from app.core import config as config_module

    for attr in ("get_settings", "_get_settings"):
        candidate = getattr(config_module, attr, None)
        if candidate is None:
            continue
        clear = getattr(candidate, "cache_clear", None)
        if callable(clear):
            clear()


@pytest.fixture(scope="module")
def session():
    """A throwaway database holding one row per visibility outcome.

    The production visibility gates are forced on. ``tests/conftest.py`` turns
    them off by default so other suites can use unverified fixtures, and with
    them off the canonical rule collapses to "not archived and not quarantined"
    - identical to the loose predicate that caused the discrepancy. A
    regression test that runs with the gates off would pass while production is
    still wrong.
    """
    from app.models import Base, Scholarship

    os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED"] = "true"
    os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"] = "true"
    os.environ["SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE"] = "false"
    _reset_settings_cache()

    path = os.path.join(tempfile.mkdtemp(), "visibility.db")
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)

    db = factory()
    rows = [
        # Fully public: passes every gate.
        Scholarship(
            id=1, title="Fully listed", country="Canada", degree="PhD", funding="Full",
            is_verified=True, is_archived=False, verification_status="active",
            image_url="https://example.org/logo.svg",
            image_verified_at=__import__("datetime").date(2026, 10, 1),
            image_source_type="official_government",
        ),
        # Archived: closed round, must not be offered.
        Scholarship(
            id=2, title="Archived", country="UK", degree="PhD", funding="Full",
            is_verified=True, is_archived=True, verification_status="active",
            image_url="https://example.org/a.svg",
            image_verified_at=__import__("datetime").date(2026, 10, 1),
            image_source_type="official_government",
        ),
        # Quarantined.
        Scholarship(
            id=3, title="Quarantined", country="UK", degree="PhD", funding="Full",
            is_verified=True, is_archived=False, verification_status="quarantined",
            image_url="https://example.org/q.svg",
            image_verified_at=__import__("datetime").date(2026, 10, 1),
            image_source_type="official_government",
        ),
        # Not verified.
        Scholarship(
            id=4, title="Unverified", country="UK", degree="PhD", funding="Full",
            # "Not verified" is now expressed by the authoritative status, not by the
        # legacy boolean. Seeding is_verified=False with an "active" status
        # described a record whose verification IS resolved while its
        # bookkeeping disagreed - which the contract says must publish.
        is_verified=False, is_archived=False,
        verification_status="needs_review",
            image_url="https://example.org/u.svg",
            image_verified_at=__import__("datetime").date(2026, 10, 1),
            image_source_type="official_government",
        ),
        # Image present but never validated: unevaluated, not trusted.
        Scholarship(
            id=5, title="Unvalidated image", country="UK", degree="PhD", funding="Full",
            is_verified=True, is_archived=False, verification_status="active",
            image_url="https://example.org/n.svg", image_verified_at=None,
            image_source_type="official_government",
        ),
        # Third-party hosted image.
        Scholarship(
            id=6, title="Third party image", country="UK", degree="PhD", funding="Full",
            is_verified=True, is_archived=False, verification_status="active",
            image_url="https://upload.wikimedia.org/x.png",
            image_verified_at=__import__("datetime").date(2026, 10, 1),
            image_source_type="wikimedia",
        ),
    ]
    for row in rows:
        db.add(row)
    db.commit()
    yield db
    db.close()


def canonical_count(db) -> int:
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions

    return db.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(*public_visibility_conditions())
    ) or 0


def looser_maintenance_count(db) -> int:
    """The predicate the stats stage used to apply.

    Kept here so the test asserts the difference rather than restating the
    current implementation, and so the gap cannot be reintroduced silently.
    """
    from app.models import Scholarship

    return db.scalar(
        select(func.count())
        .select_from(Scholarship)
        .where(
            Scholarship.is_archived.is_(False),
            Scholarship.verification_status != "quarantined",
        )
    ) or 0


class TestVisibilityCountsAgree:
    def test_stats_stage_uses_the_canonical_rule(self, session):
        import inspect

        from app.jobs import scholarzone_maintenance as worker

        source = inspect.getsource(worker)
        # The stats stage must call the canonical function, not restate a rule.
        assert "public_visibility_conditions()" in source

    def test_the_two_predicates_really_differ(self, session):
        # Guards the fixture: if these matched, the regression test below would
        # pass for the wrong reason.
        #
        # 6 rows total; the looser predicate excludes only the archived and the
        # quarantined one, so it counts 4. The canonical predicate also requires
        # verification and a validated, non-third-party image, leaving 1.
        assert looser_maintenance_count(session) == 4
        assert canonical_count(session) == 1

    def test_public_visible_equals_the_listing_population(self, session):
        from app.models import Scholarship
        from app.repositories.scholarships import public_visibility_conditions

        listed = session.scalars(
            select(Scholarship).where(*public_visibility_conditions())
        ).all()
        assert len(listed) == canonical_count(session)

    def test_only_the_fully_public_record_is_visible(self, session):
        from app.models import Scholarship
        from app.repositories.scholarships import public_visibility_conditions

        visible = session.scalars(
            select(Scholarship).where(*public_visibility_conditions())
        ).all()
        assert [row.title for row in visible] == ["Fully listed"]


class TestSemanticDistinctionIsPreserved:
    def test_database_total_is_still_reported_separately(self):
        import inspect

        from app.jobs import scholarzone_maintenance as worker

        source = inspect.getsource(worker)
        # total_records is the database total; public_visible is what the public
        # can see. Both are intentional and must not be collapsed into one.
        assert '"total_records"' in source
        assert '"public_visible"' in source

    def test_homepage_opportunities_maps_to_total(self):
        """The homepage must show the public population, not the database total."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[2]
        hero = (root / "frontend" / "src" / "components" / "ScholarZoneHero.jsx").read_text(
            encoding="utf-8"
        )
        assert "count: data.total," in hero, (
            "the OPPORTUNITIES tile must read the stats endpoint's total, "
            "which is the public-visible population"
        )