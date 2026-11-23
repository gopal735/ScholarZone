"""Tests for the study planner API."""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base, User
from app.services.auth import hash_password

_seq = itertools.count(1)


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sp.db'}")
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_user(db, email):
    u = User(email=email, password_hash=hash_password("pw"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": "pw"})
    assert r.status_code == 200, r.text


def test_create_and_list_plan(client, db):
    u = _make_user(db, "sp1@example.com")
    _login(client, u.email)
    r = client.post("/study-plans", json={"title": "My Plan", "goal": "PhD"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r2 = client.get("/study-plans")
    assert r2.status_code == 200
    assert any(p["id"] == pid for p in r2.json())


def test_add_task_and_complete(client, db):
    u = _make_user(db, "sp2@example.com")
    _login(client, u.email)
    r = client.post("/study-plans", json={"title": "Plan"})
    pid = r.json()["id"]
    r2 = client.post(f"/study-plans/{pid}/tasks", json={"title": "Task A", "priority": "high"})
    assert r2.status_code == 201
    tid = r2.json()["id"]
    r3 = client.patch(f"/study-plans/tasks/{tid}", json={"status": "completed"})
    assert r3.status_code == 200
    assert r3.json()["status"] == "completed"
    assert r3.json()["completed_at"] is not None


def test_reopen_task(client, db):
    u = _make_user(db, "sp3@example.com")
    _login(client, u.email)
    r = client.post("/study-plans", json={"title": "Plan"})
    pid = r.json()["id"]
    r2 = client.post(f"/study-plans/{pid}/tasks", json={"title": "Task B"})
    tid = r2.json()["id"]
    client.patch(f"/study-plans/tasks/{tid}", json={"status": "completed"})
    r3 = client.patch(f"/study-plans/tasks/{tid}", json={"status": "reopened"})
    assert r3.status_code == 200
    assert r3.json()["status"] == "reopened"
    assert r3.json()["completed_at"] is None


def test_delete_plan_soft(client, db):
    u = _make_user(db, "sp4@example.com")
    _login(client, u.email)
    r = client.post("/study-plans", json={"title": "Plan"})
    pid = r.json()["id"]
    r2 = client.delete(f"/study-plans/{pid}")
    assert r2.status_code == 204
    r3 = client.get("/study-plans")
    assert not any(p["id"] == pid for p in r3.json())


def test_cross_user_isolation(client, db):
    u1 = _make_user(db, "sp5a@example.com")
    u2 = _make_user(db, "sp5b@example.com")
    _login(client, u1.email)
    r = client.post("/study-plans", json={"title": "Secret Plan"})
    pid = r.json()["id"]
    # login as u2
    client.post("/auth/logout")
    _login(client, u2.email)
    r2 = client.get(f"/study-plans/{pid}")
    assert r2.status_code == 404


def test_unauthenticated_returns_401(client, db):
    r = client.get("/study-plans")
    assert r.status_code == 401
