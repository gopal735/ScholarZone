"""Tests for the RAG retrieval foundation."""

import tempfile
from pathlib import Path

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.rag.retrieval import retrieve, _score_chunk


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "rag-test.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
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
    s3 = Scholarship(
        title="Archived Award",
        country="Germany",
        degree="Bachelor's",
        funding="Partial",
        description="Archived scholarship.",
        status="open",
        is_archived=True,
        fully_funded=False,
        eligibility=["All"],
        official_source_url="https://example.com/archived",
    )
    session.add_all([s1, s2, s3])
    session.commit()
    yield session
    session.close()
    engine.dispose()


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


def test_phrase_boundary_no_false_bonus():
    score_false = _score_chunk(["art", "grant"], "Part grants", [])
    assert score_false < 2.0
    score_contig = _score_chunk(["art", "grant"], "art grant funding", [])
    assert score_contig >= 2.0


def test_literal_percent_filter(db_session):
    results = retrieve(db_session, "", country="%")
    assert results == []


def test_literal_underscore_filter(db_session):
    results = retrieve(db_session, "", country="_")
    assert results == []


def test_archived_excluded_at_query_level(db_session):
    results = retrieve(db_session, "Germany", include_archived=False)
    titles = [r.title for r in results]
    assert "Archived Award" not in titles


def test_archived_included_when_requested(db_session):
    results = retrieve(db_session, "Germany", include_archived=True)
    titles = [r.title for r in results]
    assert "Archived Award" in titles


def test_nonmatching_chunk_cannot_win_via_field_bonus(db_session):
    from app.models import Scholarship

    s = Scholarship(
        title="Music Award",
        country="Germany",
        degree="Bachelor's",
        funding="Partial",
        description="Music funding.",
        status="open",
        is_archived=False,
        fully_funded=False,
        eligibility=["All"],
        official_source_url="https://example.com/music",
    )
    db_session.add(s)
    db_session.commit()
    results = retrieve(db_session, "chemistry", country="Germany")
    titles = [r.title for r in results]
    assert "Music Award" not in titles


def test_empty_query_structured_retrieval(db_session):
    results = retrieve(db_session, "", country="Germany")
    titles = [r.title for r in results]
    assert "DAAD Scholarship" in titles


def test_zero_limit_returns_empty(db_session):
    assert retrieve(db_session, "Germany", limit=0) == []


def test_negative_limit_returns_empty(db_session):
    assert retrieve(db_session, "Germany", include_archived=True, limit=-1) == []


def test_pending_caller_edit_survives(db_session):
    s = db_session.query(Scholarship).filter(Scholarship.title == "DAAD Scholarship").first()
    original_title = s.title
    s.title = "Pending Unflushed Edit"
    # do not commit
    retrieve(db_session, "Germany")
    assert s.title == "Pending Unflushed Edit"


def test_evidence_reflects_fresh_database_values(db_session):
    from sqlalchemy import text

    db_session.execute(
        text("UPDATE scholarships SET country='France' WHERE title='DAAD Scholarship'")
    )
    db_session.commit()
    results = retrieve(db_session, "France")
    assert any(r.title == "DAAD Scholarship" and r.country == "France" for r in results)
