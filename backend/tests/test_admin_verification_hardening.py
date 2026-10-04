"""Regression tests for the administrative verification boundary.

Three endpoints on the public scholarships router used to be reachable with no
secret at all: the review queue (which published every pending record and its
internal fields), the verify mutation (which changed what the public catalogue
claimed), and two debug routes, one of which committed a database write on a GET.

These tests assert the boundary is closed, that authorization is centralized
rather than re-implemented per router, and that closing it did not change the
public contract or the review semantics.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest


ADMIN_SECRET = "hardening-admin-secret"
ADMIN_HEADERS = {"X-Admin-Secret": ADMIN_SECRET}


@pytest.fixture()
def client():
    path = Path(tempfile.gettempdir()) / f"scholarzone-hardening-{uuid4().hex}.db"
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_ADMIN_SECRET"] = ADMIN_SECRET

    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()

    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        from sqlalchemy import delete

        from app.models import Scholarship
        from app.models import ScholarshipReview
        from app.models import ScholarshipVerificationHistory

        db = get_session_factory()()
        try:
            db.execute(delete(ScholarshipVerificationHistory))
            db.execute(delete(ScholarshipReview))
            db.execute(delete(Scholarship))
            db.commit()
        finally:
            db.close()
        test_client.sz_factory = get_session_factory()
        yield test_client

    reset_database_connections()
    try:
        path.unlink()
    except OSError:
        pass


def _seed_pending(session, count: int = 3, start: int = 0) -> list[int]:
    from datetime import date

    from app.models import Scholarship

    ids = []
    for index in range(count):
        sid = 100 + start + index
        session.add(
            Scholarship(
                id=sid,
                title=f"Programme {sid}",
                country="Testland",
                degree="Master",
                funding="Fully Funded",
                status="open",
                is_verified=True,
                verification_status="needs_review",
                official_source="Provider",
                official_source_url=f"https://o{sid}.example.org/p",
                image_url=f"https://img.example.org/{sid}.png",
                image_verified_at=__import__("datetime").datetime(2026, 1, 1),
                last_verified_date=date(2026, 1, 1),
            )
        )
        ids.append(sid)
    session.commit()
    return ids


def _session(client):
    return client.sz_factory()


# ---------------------------------------------------------------------------
# 1-3. The legacy endpoint is closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/scholarships/verification-queue", "/scholarships/debug/raw/100", "/scholarships/debug/fix-null-lists"]
)
def test_legacy_admin_paths_require_authentication(client, path):
    assert client.get(path).status_code == 401


def test_legacy_queue_rejects_a_wrong_secret(client):
    response = client.get("/scholarships/verification-queue", headers={"X-Admin-Secret": "wrong"})
    assert response.status_code == 401


def test_legacy_queue_leaks_nothing_anonymously(client):
    """The regression itself: this used to answer 200 with every review record."""
    session = _session(client)
    _seed_pending(session)
    response = client.get("/scholarships/verification-queue")
    assert response.status_code == 401
    # Nothing resembling a record may appear in the refusal.
    assert "Programme" not in response.text
    assert "verification_notes" not in response.text


def test_authorized_admin_can_still_use_the_legacy_queue(client):
    """Compatibility is preserved: the path works, behind the same secret."""
    session = _session(client)
    ids = _seed_pending(session)
    response = client.get("/scholarships/verification-queue", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == set(ids)


# ---------------------------------------------------------------------------
# 4. The unauthenticated write is closed
# ---------------------------------------------------------------------------


def test_verify_mutation_requires_authentication(client):
    """A 401, not merely a validation error: the request must not reach the write."""
    session = _session(client)
    _seed_pending(session, 1)
    body = {"verification_status": "active", "verified": True, "notes": "should never apply"}
    response = client.patch("/scholarships/100/verify", json=body)
    assert response.status_code == 401

    session.expire_all()
    from app.models import Scholarship

    # The rejected request must not have changed the record.
    assert session.get(Scholarship, 100).verification_status == "needs_review"


def test_authorized_admin_can_verify(client):
    session = _session(client)
    _seed_pending(session, 1)
    body = {"verification_status": "active", "verified": True}
    response = client.patch("/scholarships/100/verify", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["verification_status"] == "active"


def test_debug_write_endpoint_requires_authentication(client):
    """It commits a repair, so an anonymous GET must never trigger it."""
    assert client.get("/scholarships/debug/fix-null-lists").status_code == 401


def test_debug_raw_requires_authentication(client):
    session = _session(client)
    _seed_pending(session, 1)
    assert client.get("/scholarships/debug/raw/100").status_code == 401
    assert client.get("/scholarships/debug/raw/100", headers=ADMIN_HEADERS).status_code == 200


# ---------------------------------------------------------------------------
# 5-6. Centralized auth, fail closed
# ---------------------------------------------------------------------------


def test_every_admin_path_uses_the_central_dependency():
    """No router should re-implement the secret comparison."""
    import inspect

    from app.core import admin_auth
    from app.routers import admin_verification, scholarships

    assert "secrets.compare_digest" in inspect.getsource(admin_auth)
    assert "compare_digest" not in inspect.getsource(scholarships)

    source = inspect.getsource(scholarships)
    assert "require_admin_secret" in source
    assert "admin_secret ==" not in source
    assert "provided_secret ==" not in source

    # And the central helper is what both routers resolve to.
    assert scholarships.require_admin_secret is admin_auth.require_admin_secret
    assert admin_verification.require_admin_secret is admin_auth.require_admin_secret


def test_missing_secret_configuration_fails_closed(client, monkeypatch):
    from app.core import admin_auth

    class _Unset:
        admin_secret = None

    monkeypatch.setattr(admin_auth, "get_settings", lambda: _Unset())
    for path in ("/scholarships/verification-queue", "/admin/verification/summary"):
        assert client.get(path, headers=ADMIN_HEADERS).status_code == 401


# ---------------------------------------------------------------------------
# 7. Public schema excludes admin-only concepts
# ---------------------------------------------------------------------------


def test_public_response_excludes_admin_only_metadata(client):
    session = _session(client)
    _seed_pending(session, 1)
    body = client.get("/scholarships/100").json()
    for field in ("open_conflicts", "legacy_is_verified", "scope", "review_flags", "history", "conflicts"):
        assert field not in body, field


def test_public_contract_is_unchanged(client):
    """Closing the boundary must not alter what applicants are shown."""
    session = _session(client)
    _seed_pending(session, 1)
    body = client.get("/scholarships/100").json()
    assert body["verification_status"] == "needs_review"
    assert body["verified"] is False
    assert isinstance(body["eligibility"], list)


# ---------------------------------------------------------------------------
# 8-9. Admin decision boundary still holds
# ---------------------------------------------------------------------------


def test_admin_decision_remains_server_authorized(client):
    session = _session(client)
    _seed_pending(session, 1)
    row = session.get(__import__("app.models", fromlist=["Scholarship"]).Scholarship, 100)
    body = {
        "decision": "verify",
        "rationale": "Official page confirms the programme.",
        "expected_updated_at": row.updated_at.isoformat(),
        "expected_verification_status": row.verification_status,
    }
    assert client.post("/admin/verification/scholarships/100/decision", json=body).status_code == 401
    assert (
        client.post(
            "/admin/verification/scholarships/100/decision", json=body, headers=ADMIN_HEADERS
        ).status_code
        == 200
    )


def test_stale_update_still_conflicts(client):
    session = _session(client)
    _seed_pending(session, 1)
    from app.models import Scholarship

    row = session.get(Scholarship, 100)
    stale_time, stale_status = row.updated_at.isoformat(), row.verification_status
    first = client.post(
        "/admin/verification/scholarships/100/decision",
        json={
            "decision": "verify",
            "rationale": "Confirmed upstream.",
            "expected_updated_at": stale_time,
            "expected_verification_status": stale_status,
        },
        headers=ADMIN_HEADERS,
    )
    assert first.status_code == 200
    second = client.post(
        "/admin/verification/scholarships/100/decision",
        json={
            "decision": "reject",
            "rationale": "A different conclusion.",
            "expected_updated_at": stale_time,
            "expected_verification_status": stale_status,
        },
        headers=ADMIN_HEADERS,
    )
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# 10-12. Counts, trust semantics, and test isolation
# ---------------------------------------------------------------------------


def test_queue_counts_are_dynamic(client):
    session = _session(client)
    _seed_pending(session, 2)
    headers = ADMIN_HEADERS
    before = client.get("/admin/verification/summary", headers=headers).json()
    assert before["storage_wide_pending"] == 2

    _seed_pending(session, 2, start=10)  # two more, disjoint ids
    after = client.get("/admin/verification/summary", headers=headers).json()
    assert after["storage_wide_pending"] == 4
    # The three populations must reconcile exactly.
    assert (
        after["storage_wide_pending"]
        == after["public_pending"] + after["storage_only_pending"]
    )


def test_trust_semantics_unchanged(client):
    session = _session(client)
    _seed_pending(session, 1)
    from app.models import Scholarship

    row = session.get(Scholarship, 100)
    row.verification_status = "active"
    session.commit()
    assert client.get("/scholarships/100").json()["verified"] is True
    row.verification_status = "needs_review"
    session.commit()
    assert client.get("/scholarships/100").json()["verified"] is False


def test_special_records_are_not_touched_by_the_suite(client):
    """79/113/134/140 stay needs_review; the suite resolves nothing."""
    session = _session(client)
    from datetime import date

    from app.models import Scholarship

    for sid in (79, 113, 134, 140):
        session.add(
            Scholarship(
                id=sid,
                title=f"Real record {sid}",
                country="UK",
                degree="PhD",
                funding="Partial",
                status="open",
                is_verified=True,
                verification_status="needs_review",
                last_verified_date=date(2026, 1, 1),
            )
        )
    session.commit()

    client.get("/scholarships/verification-queue", headers=ADMIN_HEADERS)
    client.get("/admin/verification/queue", headers=ADMIN_HEADERS)
    client.get("/admin/verification/summary", headers=ADMIN_HEADERS)

    session.expire_all()
    for sid in (79, 113, 134, 140):
        assert session.get(Scholarship, sid).verification_status == "needs_review"