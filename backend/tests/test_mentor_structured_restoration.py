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


def _setup(tmp_path, name):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    prev = app.dependency_overrides.get(get_db)
    def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db
    mentor_router._reset_limiter()
    return engine, TestingSession, session, prev


def _teardown(engine, session, prev):
    if prev is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = prev
    session.close()
    engine.dispose()


def test_structured_discovery_persisted_and_restored(tmp_path):
    engine, TS, session, prev = _setup(tmp_path, "s.db")
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
            # pagination endpoint (snapshot-backed)
            page = client.get(f"/mentor/conversations/{cid}/messages/{am['id']}/discovery?page=1&page_size=1")
            assert page.status_code == 200
            assert page.json()["pagination"]["page_size"] == 1
            assert page.json()["potential_matches"]  # non-empty
    finally:
        _teardown(engine, session, prev)


def test_multi_page_snapshot(tmp_path):
    engine, TS, session, prev = _setup(tmp_path, "mp.db")
    try:
        user = _make_user(session)
        ids = []
        for _ in range(5):
            sch = _make_sch(session)
            ids.append(sch.id)
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            s = client.post(f"/mentor/conversations/{cid}/messages", json={"message": "Find PhD scholarships with stipend in Europe"})
            assert s.status_code == 200
            am = s.json()["assistant_message"]
            dp = am["discovery_payload"]
            assert dp["result_count"] == 5
            # page 1
            p1 = client.get(f"/mentor/conversations/{cid}/messages/{am['id']}/discovery?page=1&page_size=2")
            assert p1.status_code == 200
            d1 = p1.json()
            assert d1["pagination"]["total"] == 5
            assert d1["pagination"]["total_pages"] == 3
            assert d1["returned_count"] == 2
            assert d1["pagination"]["has_more"] is True
            p1_ids = [m["scholarship_id"] for m in d1["potential_matches"]]
            # page 2
            p2 = client.get(f"/mentor/conversations/{cid}/messages/{am['id']}/discovery?page=2&page_size=2")
            assert p2.status_code == 200
            d2 = p2.json()
            assert d2["returned_count"] == 2
            p2_ids = [m["scholarship_id"] for m in d2["potential_matches"]]
            # disjoint + covers
            assert set(p1_ids).isdisjoint(set(p2_ids))
            # page 3
            p3 = client.get(f"/mentor/conversations/{cid}/messages/{am['id']}/discovery?page=3&page_size=2")
            d3 = p3.json()
            assert d3["returned_count"] == 1
            assert d3["pagination"]["has_more"] is False
            all_ids = p1_ids + p2_ids + [m["scholarship_id"] for m in d3["potential_matches"]]
            assert sorted(all_ids) == sorted(ids)
    finally:
        _teardown(engine, session, prev)


def test_historical_mutation_preserved(tmp_path):
    engine, TS, session, prev = _setup(tmp_path, "hm.db")
    try:
        user = _make_user(session)
        sch = _make_sch(session, title="Original Title")
        sid = sch.id
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            s = client.post(f"/mentor/conversations/{cid}/messages", json={"message": "Find PhD scholarships with stipend in Europe"})
            assert s.status_code == 200
            am = s.json()["assistant_message"]
            # mutate catalogue after original discovery
            sch2 = session.get(Scholarship, sid)
            sch2.title = "Changed Title"
            sch2.funding = "Full tuition only (no stipend)"
            session.add(sch2); session.commit()
            # add a new eligible scholarship
            _make_sch(session)
            # historical page must still show original title
            page = client.get(f"/mentor/conversations/{cid}/messages/{am['id']}/discovery?page=1&page_size=50")
            assert page.status_code == 200
            d = page.json()
            titles = [m["title"] for m in d["potential_matches"]]
            assert "Original Title" in titles
            assert "Changed Title" not in titles
            # total unchanged (original snapshot)
            assert d["pagination"]["total"] == 1
    finally:
        _teardown(engine, session, prev)


def test_independent_session_restoration(tmp_path):
    engine, TS, session, prev = _setup(tmp_path, "is.db")
    try:
        user = _make_user(session)
        _make_sch(session)
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            s = client.post(f"/mentor/conversations/{cid}/messages", json={"message": "Find PhD scholarships with stipend in Europe"})
            am = s.json()["assistant_message"]
            am_id = am["id"]
            dp = am["discovery_payload"]
        # close session and create a new one
        session.close()
        new_session = TS()
        def new_override():
            yield new_session
        app.dependency_overrides[get_db] = new_override
        with TestClient(app) as client:
            # re-login not needed? auth uses DB too; user exists. Need login again.
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            msgs = client.get(f"/mentor/conversations/{cid}/messages")
            assert msgs.status_code == 200
            restored = [m for m in msgs.json() if m["id"] == am_id][0]
            assert restored["discovery_payload"]["result_count"] == dp["result_count"]
            page = client.get(f"/mentor/conversations/{cid}/messages/{am_id}/discovery?page=1&page_size=1")
            assert page.status_code == 200
        new_session.close()
    finally:
        # restore prev
        if prev is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = prev
        engine.dispose()


def test_legacy_message_discovery(tmp_path):
    engine, TS, session, prev = _setup(tmp_path, "l.db")
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
        _teardown(engine, session, prev)


def test_legacy_snapshot_unavailable(tmp_path):
    """A message without discovery_payload must not fabricate history."""
    engine, TS, session, prev = _setup(tmp_path, "legacy.db")
    try:
        user = _make_user(session)
        _make_sch(session)
        # create a conversation + assistant message manually without payload
        from app.models import MentorConversation, MentorMessage
        conv = MentorConversation(user_id=user.id, title="t")
        session.add(conv); session.commit(); session.refresh(conv)
        um = MentorMessage(conversation_id=conv.id, user_id=user.id, role="user", content="hi", status="completed", sequence_number=1)
        session.add(um); session.commit(); session.refresh(um)
        am = MentorMessage(conversation_id=conv.id, user_id=user.id, role="assistant", content="answer", status="completed", sequence_number=2, source_user_message_id=um.id)
        session.add(am); session.commit(); session.refresh(am)
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            page = client.get(f"/mentor/conversations/{conv.id}/messages/{am.id}/discovery?page=1&page_size=5")
            assert page.status_code == 404
            assert page.json()["detail"] == "historical_discovery_unavailable"
    finally:
        _teardown(engine, session, prev)
