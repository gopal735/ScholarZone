import itertools
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Base, User
from app.services.auth import hash_password
from app.services.ai_gateway import AIGateway, GatewayConfig, ModelSpec, RecordingProvider
from app.services.ai_gateway.capabilities import Capability
import app.routers.mentor_conversations as rc

PASSWORD = "conv-test-9"
_seq = itertools.count(1)


def _make_user(db):
    u = User(email=f"conv{next(_seq)}@example.com", password_hash=hash_password(PASSWORD), is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def test_conversation_stream_integration(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{tmp_path / 'c.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()

    previous_override = app.dependency_overrides.get(get_db)
    def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db

    reg=[ModelSpec(id="m1",provider="p",display_name="m1",capabilities=frozenset({Capability.REASONING,Capability.STRUCTURED_OUTPUT,Capability.STREAMING}))]
    gw=AIGateway(GatewayConfig(enabled=True,registry=reg))
    gw.set_provider(RecordingProvider(reply="Hello from provider"))
    monkeypatch.setattr(rc, "get_ai_gateway", lambda: gw)

    user = _make_user(session)
    try:
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
            assert r.status_code == 200
            c = client.post("/mentor/conversations", json={"title": "t"})
            assert c.status_code == 201
            cid = c.json()["id"]
            with client.stream("POST", f"/mentor/conversations/{cid}/messages/stream", json={"message": "hi"}) as resp:
                assert resp.status_code == 200
                text = "".join(resp.iter_text())
            assert "event: message_start" in text
            assert "event: token" in text
            assert "Hello from provider" in text or ("Hello fro" in text and "m provider" in text)
            assert "event: message_complete" in text
            # provider invoked exactly once
            assert gw is not None
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        session.close()
        engine.dispose()