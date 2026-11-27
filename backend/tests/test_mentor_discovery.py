"""Focused tests for Mentor catalogue discovery."""

from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base, Scholarship, User
from app.services.auth import hash_password
from app.services.mentor import intents
from app.routers import mentor as mentor_router


TODAY = date.today()
FUTURE = TODAY + timedelta(days=60)
PASSWORD = "disc-test-9"
_seq = itertools.count(1)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'disc.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_limiter():
    mentor_router._reset_limiter()
    yield
    mentor_router._reset_limiter()


def make_user(db):
    user = User(email=f"u{next(_seq)}@example.com", password_hash=hash_password(PASSWORD), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text


def make_sch(db, **kw):
    idx = next(_seq)
    vals = {
        "title": f"Scholarship {idx}",
        "country": "Germany",
        "degree": "PhD",
        "funding": "Partial (Monthly stipend + insurance)",
        "official_source": f"Provider {idx}",
        "official_source_url": f"https://provider{idx}.example/programme",
        "verification_status": "active",
        "is_verified": True,
        "status": "open",
        "deadline_date": FUTURE,
        "deadline_display": "Rolling",
        "deadline_precision": "month",
    }
    vals.update(kw)
    s = Scholarship(**vals)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_intent_primary():
    i = intents.classify("Find PhD scholarships with stipend in Europe")
    assert i.kind == "SCHOLARSHIP_DISCOVERY"
    assert i.unsupported is False


def test_primary_query_returns_results(client, db):
    user = make_user(db)
    s = make_sch(db)
    # a non-stipend European PhD
    make_sch(db, title="No stipend PhD", funding="Tuition only", country="France")
    # a closed record
    make_sch(db, title="Closed PhD", status="closed", country="Italy")
    login(client, user.email)
    r = client.post("/mentor/message", json={"message": "Find PhD scholarships with stipend in Europe"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["intent"] == "SCHOLARSHIP_DISCOVERY"
    assert data["search_status"] in ("POTENTIAL_MATCHES_FOUND", "NO_VERIFIED_STIPEND_MATCHES")
    assert data["result_count"] >= 1
    ids = [m["scholarship_id"] for m in data["potential_matches"]]
    assert s.id in ids
    assert data["diagnostics"]["region_candidates"] >= 1


def test_provider_parity(client, db):
    user = make_user(db)
    make_sch(db)
    login(client, user.email)
    r1 = client.post("/mentor/message", json={"message": "Find PhD scholarships with stipend in Europe"})
    assert r1.status_code == 200
    # disabled provider is default; search_status should be potential
    assert r1.json()["search_status"] in ("POTENTIAL_MATCHES_FOUND", "NO_VERIFIED_STIPEND_MATCHES")


def test_no_public_candidates(client, db):
    user = make_user(db)
    login(client, user.email)
    # make all public records closed by creating none; empty db
    r = client.post("/mentor/message", json={"message": "Find PhD scholarships with stipend in Europe"})
    assert r.status_code == 200
    data = r.json()
    assert data["search_status"] == "NO_PUBLIC_CANDIDATES"
    assert data["result_count"] == 0



def test_ambiguous_country_empty_result_contract(client, db):
    user = make_user(db)
    make_sch(db)
    login(client, user.email)
    r = client.post("/mentor/message", json={"message": "Find PhD scholarships in Germany and France"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["search_status"] == "AMBIGUOUS_FILTER"
    assert data["result_count"] == 0
    assert data["returned_count"] == 0
    assert data["potential_matches"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["total_pages"] == 0
    assert data["pagination"]["has_more"] is False
    assert data["pagination"]["returned"] == 0


def test_unsupported_country_empty_result_contract(client, db):
    user = make_user(db)
    make_sch(db)
    login(client, user.email)
    r = client.post("/mentor/message", json={"message": "Find PhD scholarships in Nepal"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["search_status"] == "UNSUPPORTED_FILTER"
    assert data["result_count"] == 0
    assert data["returned_count"] == 0
    assert data["potential_matches"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["total_pages"] == 0
    assert data["pagination"]["has_more"] is False
