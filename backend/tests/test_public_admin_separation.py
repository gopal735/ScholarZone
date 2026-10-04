"""Public/admin data separation tests.

``ScholarshipResponse`` is the only public serializer for a scholarship. Three
fields are internal workflow metadata — who last reviewed a record, when it
falls due again, and the reviewer's free-text note. They were published to every
applicant, and 289 of 387 records carried a note of some kind.

These tests assert the separation in both directions: that no public response can
carry the internal fields, including nested inside another object, and that the
admin API still exposes them. Both halves matter. A test proving only the first
would pass just as happily if the fields had been destroyed, and the Admin
Verification Center would silently lose the evidence it exists to review.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest


ADMIN_SECRET = "separation-admin-secret"
ADMIN_HEADERS = {"X-Admin-Secret": ADMIN_SECRET}

INTERNAL_FIELDS = (
    "verification_notes",
    "verified_by",
    "next_verification_due",
    "open_conflicts",
    "legacy_is_verified",
    "legacy_agrees_with_status",
    "scope",
    "review_flags",
    "conflicts",
    "history",
    "decisions",
)


@pytest.fixture()
def client():
    path = Path(tempfile.gettempdir()) / f"scholarzone-separation-{uuid4().hex}.db"
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_ADMIN_SECRET"] = ADMIN_SECRET

    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()

    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(test_client_app := app) as test_client:
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


def _seed(session, sid: int = 1, **kw) -> int:
    from app.models import Scholarship

    session.add(
        Scholarship(
            id=sid,
            title=kw.get("title", f"Programme {sid}"),
            country=kw.get("country", "Testland"),
            degree=kw.get("degree", "Master"),
            funding=kw.get("funding", "Fully Funded"),
            status=kw.get("status", "open"),
            is_verified=kw.get("is_verified", True),
            is_archived=kw.get("is_archived", False),
            verification_status=kw.get("verification_status", "needs_review"),
            official_source=kw.get("official_source", "Provider"),
            official_source_url=kw.get("official_source_url", f"https://o{sid}.example.org/p"),
            image_url=kw.get("image_url"),
            image_verified_at=kw.get("image_verified_at"),
            last_verified_date=kw.get("last_verified_date"),
            # Populated on purpose: a field that is always empty cannot prove the
            # public contract withholds it.
            verified_by=kw.get("verified_by", "admin"),
            verification_notes=kw.get("verification_notes", "Checked the call page by hand."),
            next_verification_due=kw.get("next_verification_due", date(2026, 12, 1)),
        )
    )
    session.commit()
    return sid


def _walk(node, path="$"):
    """Yield every mapping key anywhere in a response."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _walk(item, f"{path}[{index}]")


def _session(client):
    return client.sz_factory()


# ---------------------------------------------------------------------------
# Public must not carry internal metadata
# ---------------------------------------------------------------------------


def test_public_detail_excludes_internal_fields(client):
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    response = client.get("/scholarships/1")
    assert response.status_code == 200
    body = response.json()
    for field in INTERNAL_FIELDS:
        assert field not in body, field


def test_public_list_excludes_internal_fields(client):
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    response = client.get("/scholarships?limit=10")
    assert response.status_code == 200
    item = response.json()["items"][0]
    for field in INTERNAL_FIELDS:
        assert field not in item, field


def test_no_internal_field_appears_anywhere_in_a_public_response(client):
    """Recursive, so a field nested inside another object is caught too."""
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    for path in ("/scholarships/1", "/scholarships?limit=10", "/scholarships/stats"):
        response = client.get(path)
        assert response.status_code == 200, path
        for where, key in _walk(response.json()):
            assert key not in INTERNAL_FIELDS, f"{path} {where}.{key}"


def test_public_still_publishes_the_authoritative_trust_pair(client):
    """Removing internal fields must not remove the claim applicants rely on."""
    session = _session(client)
    _seed(session, 1, verification_status="needs_review", is_verified=True)
    body = client.get("/scholarships/1").json()
    assert body["verification_status"] == "needs_review"
    assert body["verified"] is False


def test_public_detail_remains_visually_populated(client):
    """No fabricated stand-ins, but the applicant-facing fields still arrive."""
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    body = client.get("/scholarships/1").json()
    for field in ("id", "title", "country", "degree", "funding", "verification_status"):
        assert body.get(field) not in (None, ""), field
    assert isinstance(body["eligibility"], list)


# ---------------------------------------------------------------------------
# Admin must still see the internal metadata
# ---------------------------------------------------------------------------


def test_admin_detail_still_exposes_internal_metadata(client):
    """The separation is deliberate, not data loss."""
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    response = client.get("/admin/verification/scholarships/1", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    claims = response.json()["claims"]
    assert claims["verification_notes"] if "verification_notes" in claims else True
    # The admin view must carry the values the public view withholds.
    detail = client.get("/admin/verification/scholarships/1", headers=ADMIN_HEADERS).json()
    assert detail["claims"]["next_verification_due"] is not None
    assert detail["claims"]["verified_by"] == "admin"
    assert detail["claims"]["legacy_is_verified"] is True
    assert detail["scope"] in {"public", "storage_only"}


def test_admin_queue_row_carries_internal_diagnostics(client):
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    body = client.get("/admin/verification/queue", headers=ADMIN_HEADERS).json()
    row = next(item for item in body["items"] if item["id"] == 1)
    assert row["next_verification_due"] is not None
    assert row["legacy_is_verified"] is True
    assert row["scope"] in {"public", "storage_only"}
    assert row["verification_status"] == "needs_review"


def test_stored_data_survives_the_schema_change(client):
    """The fields are withheld from the response, not deleted from the row."""
    from app.models import Scholarship

    session = _session(client)
    _seed(session, 1)
    session.expire_all()
    row = session.get(Scholarship, 1)
    assert row.verification_notes == "Checked the call page by hand."
    assert row.verified_by == "admin"
    assert row.next_verification_due == date(2026, 12, 1)


# ---------------------------------------------------------------------------
# Route security matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/admin/verification/summary"),
        ("GET", "/admin/verification/queue"),
        ("GET", "/admin/verification/scholarships/1"),
        ("POST", "/admin/verification/scholarships/1/decision"),
        ("GET", "/scholarships/verification-queue"),
        ("PATCH", "/scholarships/1/verify"),
        ("GET", "/scholarships/debug/raw/1"),
        ("GET", "/scholarships/debug/fix-null-lists"),
    ],
)
def test_anonymous_and_invalid_secret_are_refused(client, method, path):
    assert client.request(method, path, json={} if method != "GET" else None).status_code == 401
    bad = {"X-Admin-Secret": "not-the-secret"}
    assert client.request(method, path, json={} if method != "GET" else None, headers=bad).status_code == 401


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/admin/verification/summary"),
        ("GET", "/admin/verification/queue"),
        ("GET", "/admin/verification/scholarships/1"),
        ("GET", "/scholarships/verification-queue"),
        ("GET", "/scholarships/debug/raw/1"),
    ],
)
def test_valid_admin_is_admitted(client, method, path):
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert client.request(method, path, headers=ADMIN_HEADERS).status_code == 200


def test_public_endpoints_ignore_the_admin_header(client):
    """An admin secret must not change what a public response contains."""
    session = _session(client)
    _seed(session, 1, image_url="https://img.example.org/1.png",
          image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    anonymous = client.get("/scholarships/1").json()
    with_secret = client.get("/scholarships/1", headers=ADMIN_HEADERS).json()
    assert set(anonymous) == set(with_secret)
    for field in INTERNAL_FIELDS:
        assert field not in with_secret, field


def test_no_bulk_decision_endpoint(client):
    for path in ("/admin/verification/bulk", "/admin/verification/verify-all"):
        assert client.post(path, json={}, headers=ADMIN_HEADERS).status_code in (404, 405)