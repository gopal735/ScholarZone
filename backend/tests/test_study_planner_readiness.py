"""Regression tests for Study Planner runtime schema readiness."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base, User
from app.services.auth import hash_password


@pytest.fixture()
def ready_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ready.db'}")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def empty_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    yield engine
    engine.dispose()


def _session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return Session()


def _override(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db


def _clear():
    app.dependency_overrides.clear()


def test_missing_both_tables_returns_503(empty_engine):
    db = _session(empty_engine)
    _override(db)
    try:
        with TestClient(app) as client:
            r = client.get("/study-plans")
            assert r.status_code == 503
            assert r.json() == {"detail": "Study planner is not available."}
    finally:
        _clear()
        db.close()


def test_missing_study_plans_table_returns_503(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'missing_plans.db'}")
    # Create only study_plan_tasks by creating all then dropping study_plans.
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE study_plans"))
    db = _session(engine)
    _override(db)
    try:
        with TestClient(app) as client:
            r = client.post("/study-plans", json={"title": "Plan"})
            assert r.status_code == 503
    finally:
        _clear()
        db.close()
        engine.dispose()


def test_missing_study_plan_tasks_table_returns_503(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'missing_tasks.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE study_plan_tasks"))
    db = _session(engine)
    _override(db)
    try:
        with TestClient(app) as client:
            r = client.get("/study-plans")
            assert r.status_code == 503
    finally:
        _clear()
        db.close()
        engine.dispose()


def test_missing_required_column_returns_503(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'missing_col.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE study_plans DROP COLUMN version"))
    db = _session(engine)
    _override(db)
    try:
        with TestClient(app) as client:
            r = client.get("/study-plans")
            assert r.status_code == 503
            assert "version" not in r.text
    finally:
        _clear()
        db.close()
        engine.dispose()


def test_inspection_failure_returns_503(monkeypatch, ready_engine):
    db = _session(ready_engine)
    _override(db)
    monkeypatch.setattr("app.study_planner_readiness.sa_inspect", lambda bind: (_ for _ in ()).throw(RuntimeError("boom")))
    try:
        with TestClient(app) as client:
            r = client.get("/study-plans")
            assert r.status_code == 503
            assert "boom" not in r.text
    finally:
        _clear()
        db.close()


def test_recovery_without_restart(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'recover.db'}")
    db = _session(engine)
    _override(db)
    try:
        with TestClient(app) as client:
            r1 = client.get("/study-plans")
            assert r1.status_code == 503
            Base.metadata.create_all(bind=engine)

            def override2():
                yield db

            app.dependency_overrides[get_db] = override2
            r2 = client.get("/study-plans")
            assert r2.status_code in (200, 401)
    finally:
        _clear()
        db.close()
        engine.dispose()


def test_route_coverage_missing_schema(empty_engine):
    db = _session(empty_engine)
    _override(db)
    try:
        with TestClient(app) as client:
            assert client.get("/study-plans").status_code == 503
            assert client.post("/study-plans", json={"title": "P"}).status_code == 503
            assert client.get("/study-plans/1").status_code == 503
            assert client.patch("/study-plans/1", json={"title": "X", "version": 1}).status_code == 503
            assert client.delete("/study-plans/1").status_code == 503
            assert client.post("/study-plans/1/tasks", json={"title": "T"}).status_code == 503
            assert client.patch("/study-plans/tasks/1", json={"status": "completed", "version": 1}).status_code == 503
    finally:
        _clear()
        db.close()


def test_authenticated_access_preserved(ready_engine):
    db = _session(ready_engine)
    u = User(email="ready@example.com", password_hash=hash_password("pw"))
    db.add(u)
    db.commit()
    db.refresh(u)
    _override(db)
    try:
        with TestClient(app) as client:
            r = client.post("/auth/login", json={"email": u.email, "password": "pw"})
            assert r.status_code == 200
            r2 = client.get("/study-plans")
            assert r2.status_code == 200
            r3 = client.post("/study-plans", json={"title": "Plan"})
            assert r3.status_code == 201
    finally:
        _clear()
        db.close()


def test_unauthenticated_returns_401_when_healthy(ready_engine):
    db = _session(ready_engine)
    _override(db)
    try:
        with TestClient(app) as client:
            r = client.get("/study-plans")
            assert r.status_code == 401
    finally:
        _clear()
        db.close()


def test_public_api_isolation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'public.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE study_plan_tasks"))
        conn.execute(text("DROP TABLE study_plans"))
    db = _session(engine)
    _override(db)
    try:
        with TestClient(app) as client:
            assert client.get("/study-plans").status_code == 503
            r = client.get("/scholarships")
            assert r.status_code in (200, 404)
            r2 = client.get("/scholarships/stats")
            assert r2.status_code in (200, 404)
    finally:
        _clear()
        db.close()
        engine.dispose()
