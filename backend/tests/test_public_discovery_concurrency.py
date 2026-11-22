"""Regression tests for public discovery concurrency protection."""

from __future__ import annotations

import itertools
import threading

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Base, Scholarship, User
from app.routers import mentor as mentor_router
from app.services.auth import hash_password
from app.core.rate_limit import RateLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace

PASSWORD = "pubdisc-9"
_seq = itertools.count(1)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pubdisc.db'}")
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
def _reset_state():
    mentor_router._reset_limiter()
    # Reset semaphore
    while mentor_router._public_discovery_semaphore.acquire(blocking=False):
        pass
    # restore full capacity
    for _ in range(mentor_router._PUBLIC_DISCOVERY_MAX_IN_FLIGHT):
        mentor_router._public_discovery_semaphore.release()
    yield
    mentor_router._reset_limiter()
    while mentor_router._public_discovery_semaphore.acquire(blocking=False):
        pass
    for _ in range(mentor_router._PUBLIC_DISCOVERY_MAX_IN_FLIGHT):
        mentor_router._public_discovery_semaphore.release()


def make_sch(db):
    idx = next(_seq)
    s = Scholarship(
        title=f"Scholarship {idx}",
        country="Germany",
        degree="PhD",
        funding="Partial",
        official_source="Provider",
        official_source_url="https://example.com",
        verification_status="active",
        is_verified=True,
        status="open",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def fake_discovery():
    return SimpleNamespace(
        query_summary={"degree_level": "phd", "region": "Germany", "funding_intent": None},
        search_status="POTENTIAL_MATCHES_FOUND",
        potential_matches=[],
        diagnostics={},
    )


def test_rate_limit_exceeded_returns_429_with_retry_after(client, db, monkeypatch):
    def raise_rl(key):
        raise RateLimitExceeded(7)

    monkeypatch.setattr(mentor_router._public_discovery_limiter, "check", raise_rl)
    make_sch(db)
    r = client.post("/mentor/discovery", json={"message": "Show grants in Germany"})
    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "7"


def test_unexpected_exception_not_converted_to_429(client, db, monkeypatch):
    monkeypatch.setattr("app.services.mentor.discovery.run_discovery", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    make_sch(db)
    with pytest.raises(Exception):
        client.post("/mentor/discovery", json={"message": "Show grants in Germany"})


def test_capacity_exhausted_returns_503_and_does_not_run_discovery(client, db, monkeypatch):
    # exhaust capacity
    for _ in range(mentor_router._PUBLIC_DISCOVERY_MAX_IN_FLIGHT):
        assert mentor_router._public_discovery_semaphore.acquire(blocking=False)
    called = {"n": 0}

    def fake_run(*a, **k):
        called["n"] += 1
        return fake_discovery()

    monkeypatch.setattr("app.services.mentor.discovery.run_discovery", fake_run)
    make_sch(db)
    r = client.post("/mentor/discovery", json={"message": "Show grants in Germany"})
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == str(mentor_router._PUBLIC_DISCOVERY_RETRY_AFTER_SECONDS)
    assert called["n"] == 0
    # cleanup: release the slots we took
    for _ in range(mentor_router._PUBLIC_DISCOVERY_MAX_IN_FLIGHT):
        mentor_router._public_discovery_semaphore.release()


def test_capacity_released_after_success(client, db, monkeypatch):
    monkeypatch.setattr("app.services.mentor.discovery.run_discovery", lambda *a, **k: fake_discovery())
    make_sch(db)
    r = client.post("/mentor/discovery", json={"message": "Show grants in Germany"})
    assert r.status_code == 200
    # slot should be available again
    assert mentor_router._public_discovery_semaphore.acquire(blocking=False)
    mentor_router._public_discovery_semaphore.release()


def test_capacity_released_after_exception(client, db, monkeypatch):
    def boom(*a, **k):
        raise ValueError("boom")

    monkeypatch.setattr("app.services.mentor.discovery.run_discovery", boom)
    make_sch(db)
    with pytest.raises(Exception):
        client.post("/mentor/discovery", json={"message": "Show grants in Germany"})
    # slot released
    assert mentor_router._public_discovery_semaphore.acquire(blocking=False)
    mentor_router._public_discovery_semaphore.release()


def test_malformed_date_does_not_consume_slot(client, db, monkeypatch):
    monkeypatch.setattr("app.services.mentor.discovery.run_discovery", lambda *a, **k: fake_discovery())
    make_sch(db)
    r = client.post("/mentor/discovery", json={"message": "Show grants in Germany", "as_of": "not-a-date"})
    assert r.status_code == 422
    assert mentor_router._public_discovery_semaphore.acquire(blocking=False)
    mentor_router._public_discovery_semaphore.release()


def test_concurrent_requests_cannot_exceed_capacity(client, db, monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def blocking_run(*a, **k):
        started.set()
        release.wait(timeout=5)
        return fake_discovery()

    monkeypatch.setattr("app.services.mentor.discovery.run_discovery", blocking_run)
    make_sch(db)

    results = []

    def worker():
        r = client.post("/mentor/discovery", json={"message": "Show grants in Germany"})
        results.append(r.status_code)

    # First wave fills capacity
    threads = []
    for _ in range(mentor_router._PUBLIC_DISCOVERY_MAX_IN_FLIGHT):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    # Wait until at least one started
    started.wait(timeout=5)

    # Extra request should be rejected immediately
    extra = client.post("/mentor/discovery", json={"message": "Show grants in Germany"})
    assert extra.status_code == 503

    release.set()
    for t in threads:
        t.join(timeout=5)

    assert results.count(200) == mentor_router._PUBLIC_DISCOVERY_MAX_IN_FLIGHT

