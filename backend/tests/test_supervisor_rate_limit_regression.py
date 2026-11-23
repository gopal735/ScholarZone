"""Regression tests for the Supervisor production-hardening remediation.

Covers the P1 rate-limiter fixes (expired-bucket reclamation, capacity sweep,
active-client retention, bounded key space, per-caller isolation, concurrency)
and the trusted-proxy identity rules that go with them, plus the shared public
limiter behaviour behind the dynamic supervisor read paths.

Every expectation here is written against the fail-closed design. No limit is
weakened to make a test pass, and expiry windows are advanced explicitly so the
tests do not depend on real time.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.core import config as config_module  # noqa: E402
from app.core.rate_limit import (  # noqa: E402
    InProcessRateLimiter,
    RateLimitExceeded,
    client_identifier,
    public_api_key,
    public_api_limiter,
    supervisor_read_limiter,
)
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Scholarship, User  # noqa: E402


GATE_VARS = (
    "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED",
    "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE",
    "SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE",
)


def _reset_settings_cache() -> None:
    for attr in ("get_settings", "_get_settings"):
        candidate = getattr(config_module, attr, None)
        clear = getattr(candidate, "cache_clear", None)
        if callable(clear):
            clear()


@pytest.fixture
def pin_gates():
    previous = {name: os.environ.get(name) for name in GATE_VARS}
    for name in GATE_VARS:
        os.environ[name] = "false"
    _reset_settings_cache()
    yield
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    _reset_settings_cache()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(pin_gates, db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    supervisor_read_limiter.reset()
    public_api_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    supervisor_read_limiter.reset()
    public_api_limiter.reset()


# ---------------------------------------------------------------------------
# In-process limiter: expiry reclamation and capacity
# ---------------------------------------------------------------------------


def test_expired_buckets_are_reclaimed_after_the_window_ages_out():
    limiter = InProcessRateLimiter(limit=1, window_seconds=60, max_keys=100)

    limiter.check("read:1.2.3.4:7", now=0.0)
    with pytest.raises(RateLimitExceeded):
        # Still inside the first window.
        limiter.check("read:1.2.3.4:7", now=30.0)

    # The window has fully aged out, so the next read starts a fresh budget.
    limiter.check("read:1.2.3.4:7", now=60.0)


def test_expired_keys_free_capacity_for_legitimate_new_clients():
    limiter = InProcessRateLimiter(limit=1, window_seconds=60, max_keys=2)

    limiter.check("read:1.2.3.4:7", now=0.0)
    limiter.check("read:1.2.3.4:8", now=0.0)
    # Both slots are live, so a third caller is refused under the fail-closed cap.
    with pytest.raises(RateLimitExceeded):
        limiter.check("read:1.2.3.4:9", now=0.0)

    # Advancing past the window reclaims the aged-out bucket, freeing the slot.
    limiter.check("read:1.2.3.4:7", now=61.0)
    # The previously refused caller now gets a fresh window.
    limiter.check("read:1.2.3.4:9", now=61.0)


def test_active_clients_keep_their_budget_and_new_clients_get_a_fresh_window():
    limiter = InProcessRateLimiter(limit=2, window_seconds=60)

    limiter.check("read:1.2.3.4:7", now=0.0)
    limiter.check("read:1.2.3.4:7", now=10.0)
    with pytest.raises(RateLimitExceeded):
        limiter.check("read:1.2.3.4:7", now=20.0)

    # A different caller is unaffected by the first caller's exhaustion.
    limiter.check("read:5.6.7.8:7", now=20.0)


def test_concurrent_checkers_never_exceed_the_limit():
    limiter = InProcessRateLimiter(limit=5, window_seconds=60)

    def _attempt() -> bool:
        try:
            limiter.check("read:1.2.3.4:7")
            return True
        except RateLimitExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        allowed = list(pool.map(lambda _: _attempt(), range(20)))

    assert sum(allowed) == 5


# ---------------------------------------------------------------------------
# Shared public limiter: dynamic path keys
# ---------------------------------------------------------------------------


def test_public_api_key_folds_dynamic_path_segments():
    # Dynamic segments fold onto a placeholder, so rotating unknown scholarship
    # ids cannot mint a fresh bucket per identifier against the shared limiter.
    assert public_api_key("203.0.113.9", "/scholarships/12/supervisors") == (
        public_api_key("203.0.113.9", "/scholarships/13/supervisors")
    )
    assert public_api_key("203.0.113.9", "/scholarships/12/supervisors") != public_api_key(
        "203.0.113.10", "/scholarships/12/supervisors"
    )
    assert public_api_key("203.0.113.9", "/scholarships/stats") == public_api_key(
        "203.0.113.9", "/scholarships/stats"
    )


# ---------------------------------------------------------------------------
# Trusted proxy identity
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, host: str, forwarded: str | None = None) -> None:
        self.client = type("Client", (), {"host": host})()
        self.headers = {"x-forwarded-for": forwarded} if forwarded is not None else {}


def test_client_identifier_ignores_forwarded_for_from_an_untrusted_peer():
    request = _FakeRequest("203.0.113.77", forwarded="198.51.100.10")
    assert client_identifier(request, trusted_proxies=()) == "203.0.113.77"


def test_client_identifier_honours_forwarded_for_from_a_trusted_proxy():
    request = _FakeRequest("203.0.113.77", forwarded="198.51.100.10, 203.0.113.77")
    assert client_identifier(request, trusted_proxies=("203.0.113.77",)) == "198.51.100.10"


def test_client_identifier_skips_trusted_proxy_hops():
    request = _FakeRequest("203.0.113.77", forwarded="10.0.0.5, 198.51.100.10")
    assert client_identifier(request, trusted_proxies=("10.0.0.5", "203.0.113.77")) == "198.51.100.10"


def test_client_identifier_uses_the_actual_peer_without_a_forwarded_header():
    assert client_identifier(_FakeRequest("203.0.113.77"), trusted_proxies=("203.0.113.77",)) == "203.0.113.77"


# ---------------------------------------------------------------------------
# Public supervisor service: unknown scholarship ids and the shared limiter
# ---------------------------------------------------------------------------


def _record(index: int) -> dict:
    return {
        "title": f"Test Scholarship {index}",
        "country": "Germany",
        "degree": "Master",
        "funding": "Fully Funded",
        "status": "open",
        "deadline_date": date(2027, 6, 30),
        "deadline_precision": "exact",
        "eligibility": [],
        "coverage": [],
        "requirements": [],
        "documents": [],
        "official_source": f"Test University {index}",
        "official_source_url": f"https://uni{index}.edu/programmes/{index}",
        "is_verified": True,
        "verification_status": "active",
        "image_url": f"https://uni{index}.edu/logo.png",
    }


def test_unknown_scholarship_ids_do_not_exhaust_the_shared_public_budget(client, db):
    # One caller rotating unknown scholarship ids through dynamic paths must
    # not be able to spend an unbounded key space against the shared public
    # limiter; the folded key keeps the whole rotation inside one bucket.
    statuses = [
        client.get(f"/scholarships/{9000000 + index}/supervisors").status_code
        for index in range(320)
    ]
    # The shared public limiter answers 429 once its own budget is spent.
    assert 429 in statuses


def test_a_fresh_caller_is_still_served_after_the_public_budget_is_spent(client, db, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_TRUSTED_PROXIES", "testclient")
    _reset_settings_cache()
    try:
        statuses = [client.get("/scholarships/stats").status_code for _ in range(61)]
        # The shared stats budget (60 per window) is spent by this caller.
        assert 429 in statuses
        # A different caller keeps its own budget and is still served.
        other = client.get("/scholarships/stats", headers={"X-Forwarded-For": "203.0.113.55"})
        assert other.status_code == 200
    finally:
        _reset_settings_cache()


# ---------------------------------------------------------------------------
# Existing 429 behaviour remains correct
# ---------------------------------------------------------------------------


def test_supervisor_read_limit_still_answers_429_with_retry_after(client, db):
    scholarship = Scholarship(**_record(1))
    db.add(scholarship)
    db.commit()
    db.refresh(scholarship)

    statuses = [
        client.get(f"/scholarships/{scholarship.id}/supervisor-summary").status_code
        for _ in range(125)
    ]
    assert 429 in statuses
    assert statuses[0] == 200
