"""Structured discovery persistence and restoration regression tests."""

import itertools
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base, Scholarship, User
from app.services.auth import hash_password
from app.routers import mentor as mentor_router

PASSWORD = "struct-test-9"
_seq = itertools.count(1)


def _make_user(db):
    u = User(email=f"st{next(_seq)}@example.com", password_hash=hash_password(PASSWORD), is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_sch(db, **kw):
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
        "deadline_display": "Rolling",
    }
    vals.update(kw)
    s = Scholarship(**vals)
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_structured_discovery_persisted_and_restored(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 's.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    prev = app.dependency_overrides.get(get_db)
    # use generator override
    def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db
    mentor_router._reset_limiter()
    try:
        user = _make_user(session)
        _make_sch(session)
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            s = client.post(f"/mentor/conversations/{cid}/messages", json={"message": "Find PhD scholarships with stipend in Europe"})
            assert s.status_code == 200
            am = s.json()["assistant_message"]
            assert am["discovery_payload"] is not None
            dp = am["discovery_payload"]
            assert dp["result_count"] >= 1
            assert len(dp["potential_matches"]) >= 1
            # history restoration
            msgs = client.get(f"/mentor/conversations/{cid}/messages")
            assert msgs.status_code == 200
            restored = [m for m in msgs.json() if m["id"] == am["id"]][0]
            assert restored["discovery_payload"] is not None
            assert restored["discovery_payload"]["result_count"] == dp["result_count"]
            # pagination endpoint
            page = client.get(f"/mentor/conversations/{cid}/messages/{am['id']}/discovery?page=1&page_size=1")
            assert page.status_code == 200
            assert page.json()["pagination"]["page_size"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def test_legacy_message_discovery(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'l.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db
    mentor_router._reset_limiter()
    try:
        user = _make_user(session)
        _make_sch(session)
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            r2 = client.post("/mentor/message", json={"message": "Find PhD scholarships with stipend in Europe"})
            assert r2.status_code == 200
            data = r2.json()
            assert data["result_count"] >= 1
            assert data["pagination"] is not None
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()
