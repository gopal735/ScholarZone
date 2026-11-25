import itertools
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Base, User
from app.services.auth import hash_password
from app.services.ai_gateway import AIGateway, GatewayConfig, ModelSpec, RecordingProvider
from app.services.ai_gateway.capabilities import Capability
import app.routers.mentor_conversations as rc

PASSWORD = "sse-test-9"
_seq = itertools.count(1000)


def _make_user(db):
    u = User(email=f"sse{next(_seq)}@example.com", password_hash=hash_password(PASSWORD), is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _setup(tmp_path, monkeypatch, reply="Hello from provider"):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{tmp_path / 's.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    previous_override = app.dependency_overrides.get(get_db)
    def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db
    reg=[ModelSpec(id="m1",provider="p",display_name="m1",capabilities=frozenset({Capability.REASONING,Capability.STRUCTURED_OUTPUT,Capability.STREAMING}))]
    gw=AIGateway(GatewayConfig(enabled=True,registry=reg))
    gw.set_provider(RecordingProvider(reply=reply))
    monkeypatch.setattr(rc, "get_ai_gateway", lambda: gw)
    user = _make_user(session)
    return engine, session, previous_override, user, gw


def _teardown(engine, session, previous_override):
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override
    session.close()
    engine.dispose()


def test_sse_provider_token_real_delimiters(tmp_path, monkeypatch):
    engine, session, prev, user, gw = _setup(tmp_path, monkeypatch, reply="Hello from provider")
    try:
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            with client.stream("POST", f"/mentor/conversations/{cid}/messages/stream", json={"message": "hi"}) as resp:
                assert resp.status_code == 200
                raw = b"".join(resp.iter_bytes())
        text = raw.decode("utf-8")
        assert "event: token\\ndata:" not in text
        assert "event: token\ndata:" in text
        assert "Hello" in text and "provider" in text
    finally:
        _teardown(engine, session, prev)


def test_sse_citation_parseable(tmp_path, monkeypatch):
    engine, session, prev, user, gw = _setup(tmp_path, monkeypatch, reply="Hello")
    try:
        with TestClient(app) as client:
            client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            with client.stream("POST", f"/mentor/conversations/{cid}/messages/stream", json={"message": "hi"}) as resp:
                raw = b"".join(resp.iter_bytes())
        text = raw.decode("utf-8")
        if "citation" in text:
            assert "event: citation\ndata:" in text
    finally:
        _teardown(engine, session, prev)


def test_sse_message_complete_parseable(tmp_path, monkeypatch):
    engine, session, prev, user, gw = _setup(tmp_path, monkeypatch, reply="Hello")
    try:
        with TestClient(app) as client:
            client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            with client.stream("POST", f"/mentor/conversations/{cid}/messages/stream", json={"message": "hi"}) as resp:
                raw = b"".join(resp.iter_bytes())
        text = raw.decode("utf-8")
        assert "event: message_complete\ndata:" in text
    finally:
        _teardown(engine, session, prev)


def test_sse_replay_helper(tmp_path, monkeypatch):
    from app.sse import format_sse
    out = format_sse("message_start", {"replay": True})
    assert out.endswith("\n\n")
    assert "event: message_start\ndata:" in out


def test_sse_unicode_and_injection():
    from app.sse import format_sse
    payload = {"content": "line1\nline2\nevent: evil\ndata: x"}
    out = format_sse("token", payload)
    assert out.count("\n\n") == 1


def test_sse_empty_provider_fallback(tmp_path, monkeypatch):
    engine, session, prev, user, gw = _setup(tmp_path, monkeypatch, reply="   ")
    try:
        with TestClient(app) as client:
            client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            c = client.post("/mentor/conversations", json={"title": "t"})
            cid = c.json()["id"]
            with client.stream("POST", f"/mentor/conversations/{cid}/messages/stream", json={"message": "hi"}) as resp:
                raw = b"".join(resp.iter_bytes())
        text = raw.decode("utf-8")
        assert "event: message_complete" in text
    finally:
        _teardown(engine, session, prev)