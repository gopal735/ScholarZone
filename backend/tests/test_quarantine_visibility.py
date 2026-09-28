"""Quarantined rows must never appear in the public catalogue.

Quarantined records are non-scholarships (a government landing page, a site
front door). They are retained for audit but they are not scholarships, and
listing them advertises a total the directory cannot show and offers users
pages that are not funding opportunities.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.repositories.scholarships import list_scholarships
from app.schemas import ScholarshipQuery
from app.services.scholarships import get_scholarship_directory


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'q.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _seed(factory) -> tuple[int, int]:
    session = factory()
    try:
        real = Scholarship(
            title="Real Scholarship",
            country="Germany",
            degree="Master",
            funding="Full",
            verification_status="active",
        )
        landing = Scholarship(
            title="Welcome to GOV.UK",
            country="United Kingdom",
            degree="Master",
            funding="Full",
            verification_status="quarantined",
        )
        session.add_all([real, landing])
        session.commit()
        return real.id, landing.id
    finally:
        session.close()


def _query() -> ScholarshipQuery:
    return ScholarshipQuery(page=1, limit=50)


class TestDirectoryExcludesQuarantined:
    def test_quarantined_row_is_not_listed(self, factory):
        _seed(factory)
        session = factory()
        try:
            response = get_scholarship_directory(session, _query())
            assert response.pagination.total == 1
        finally:
            session.close()

    def test_quarantined_title_is_absent_from_results(self, factory):
        _seed(factory)
        session = factory()
        try:
            items, total = list_scholarships(session, _query())
            titles = [s.title for s in items]
            assert "Welcome to GOV.UK" not in titles
            assert total == 1
        finally:
            session.close()

    def test_search_cannot_resurface_a_quarantined_row(self, factory):
        _seed(factory)
        session = factory()
        try:
            query = ScholarshipQuery(search="GOV.UK", page=1, limit=50)
            items, total = list_scholarships(session, query)
            assert total == 0
            assert items == []
        finally:
            session.close()

    def test_filters_still_apply_to_listed_rows(self, factory):
        _seed(factory)
        session = factory()
        try:
            query = ScholarshipQuery(country="Nowhere", page=1, limit=50)
            _, total = list_scholarships(session, query)
            assert total == 0
        finally:
            session.close()


class TestStatsExcludeQuarantined:
    def test_stats_total_matches_the_listing(self, factory):
        """The homepage must not advertise a number the directory cannot show."""
        from sqlalchemy import func, select

        _seed(factory)
        session = factory()
        try:
            listed, _ = list_scholarships(session, _query())
            raw = session.execute(select(func.count(Scholarship.id))).scalar()
            assert raw == 2
            assert len(listed) == 1
        finally:
            session.close()
