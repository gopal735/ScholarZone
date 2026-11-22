"""DB-level regression tests for grant discovery and auth/public parity."""

from __future__ import annotations

import itertools

import pytest

from app.database import get_db
from app.main import app
from app.models import Base, Scholarship, User
from app.services.auth import hash_password
from app.routers import mentor as mentor_router
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


TODAY = None
from datetime import date, timedelta

TODAY = date.today()
FUTURE = TODAY + timedelta(days=60)
PASSWORD = "grant-test-9"
_seq = itertools.count(1)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'grant.db'}")
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
    user = User(email=f"g{next(_seq)}@example.com", password_hash=hash_password(PASSWORD), is_active=True)
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


def test_grant_query_preserves_country_and_degree(client, db):
    make_sch(db, country="Germany", degree="Master's")
    make_sch(db, country="France", degree="PhD")
    # anonymous public discovery
    r = client.post("/mentor/discovery", json={"message": "Grants for Master's in Germany"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["search_status"] in ("POTENTIAL_MATCHES_FOUND", "NO_VERIFIED_STIPEND_MATCHES", "NO_REGION_MATCHES", "NO_DEGREE_MATCHES")
    qs = data["query_summary"]
    assert qs["region"] == "Germany"
    assert qs["degree_level"] == "masters"
    # no France leakage
    for m in data["potential_matches"]:
        assert m["country"] == "Germany"


def test_grant_query_does_not_become_worldwide(client, db):
    make_sch(db, country="Germany", degree="PhD")
    make_sch(db, country="France", degree="PhD")
    r = client.post("/mentor/discovery", json={"message": "Show grants in Germany"})
    data = r.json()
    assert data["query_summary"]["region"] == "Germany"
    for m in data["potential_matches"]:
        assert m["country"] == "Germany"


def test_authenticated_and_public_discovery_parity(client, db):
    make_sch(db, country="Germany", degree="PhD")
    user = make_user(db)
    login(client, user.email)
    msg = "Show grants in Germany"
    r_auth = client.post("/mentor/message", json={"message": msg})
    r_pub = client.post("/mentor/discovery", json={"message": msg})
    assert r_auth.status_code == 200
    assert r_pub.status_code == 200
    a = r_auth.json()
    p = r_pub.json()
    assert a["search_status"] == p["search_status"]
    assert a["query_summary"] == p["query_summary"]
    assert a["result_count"] == p["result_count"]


def test_bare_show_does_not_trigger_discovery(client, db):
    make_sch(db, country="Germany", degree="PhD")
    user = make_user(db)
    login(client, user.email)
    r = client.post("/mentor/message", json={"message": "show"})
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] != "SCHOLARSHIP_DISCOVERY"
    assert data["supported"] is False
