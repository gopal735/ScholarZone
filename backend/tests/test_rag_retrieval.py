"""Tests for the RAG retrieval foundation."""

import os
import tempfile
from pathlib import Path

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.rag.retrieval import retrieve


@pytest.fixture()
def db_session():
    db_path = Path(tempfile.gettempdir()) / "rag-test.db"
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Seed two scholarships
    s1 = Scholarship(
        title="DAAD Scholarship",
        country="Germany",
        degree="Master's",
        funding="Fully funded",
        description="Funding for international students in Germany.",
        status="open",
        is_archived=False,
        fully_funded=True,
        eligibility=["International students", "Bachelor's degree"],
        official_source_url="https://www.daad.de",
    )
    s2 = Scholarship(
        title="Erasmus Mundus",
        country="Europe",
        degree="Master's",
        funding="Fully funded",
        description="Joint master programmes across Europe.",
        status="closed",
        is_archived=False,
        fully_funded=True,
        eligibility=["EU and non-EU students"],
        official_source_url="https://erasmus-plus.ec.europa.eu",
    )
    session.add_all([s1, s2])
    session.commit()
    yield session
    session.close()
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


def test_retrieve_english_query(db_session):
    results = retrieve(db_session, "Germany master scholarship")
    assert len(results) >= 1
    assert results[0].title == "DAAD Scholarship"
    assert results[0].official_source_url == "https://www.daad.de"


def test_closed_excluded_by_default(db_session):
    results = retrieve(db_session, "Europe master")
    titles = [r.title for r in results]
    assert "Erasmus Mundus" not in titles


def test_closed_included_when_requested(db_session):
    results = retrieve(db_session, "Europe master", include_closed=True)
    titles = [r.title for r in results]
    assert "Erasmus Mundus" in titles


def test_fully_funded_preserved(db_session):
    results = retrieve(db_session, "Germany")
    assert results[0].fully_funded is True


def test_provenance_chunk_id(db_session):
    results = retrieve(db_session, "Germany")
    assert ":" in results[0].chunk_id
    assert results[0].chunk_text
