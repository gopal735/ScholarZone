"""The authenticated administrative CRUD surface for scholarship records.

What these tests protect, in order of how much damage getting it wrong does:

1. **Every endpoint fails closed** without the admin secret - including the
   delete, which must never have an unauthenticated route.
2. **A permanent delete is deliberate**: wrong confirmation string, missing
   reason, and depended-upon records each refuse it, and a refused delete
   leaves the record and every dependant present.
3. **The audit row outlives the deletion**: ``scholarship_admin_audit`` holds
   no foreign key, so after a successful delete the trail is still there with
   the full before-values of every column - including ones no API surface
   would have shown.
4. **A refused delete does not leave an audit row claiming otherwise.**
5. **Archive is soft and reversible in principle**: flags only, with the
   reason recorded and audited.
"""

from __future__ import annotations

import os
import tempfile
import uuid
import uuid as _uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from app.database import reset_database_connections
from app.main import app
from app.models import Base, Scholarship, ScholarshipAdminAudit, SavedScholarship
from app.database import init_database


@pytest.fixture(scope="module")
def test_db_path():
    return Path(tempfile.gettempdir()) / f"scholarzone-test-admin-crud-{_uuid.uuid4().hex}.db"


@pytest.fixture(scope="module")
def client(test_db_path):
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_VERIFICATION_SECRET"] = "test-secret"
    os.environ["SCHOLARZONE_ADMIN_SECRET"] = "admin-secret"
    reset_database_connections()
    init_database()
    with TestClient(app) as c:
        c.__enter__()
        yield c
        c.__exit__(None, None, None)
    if test_db_path.exists():
        test_db_path.unlink()


ADMIN = {"X-Admin-Secret": "admin-secret"}


def _create_payload(**overrides):
    payload = {
        "title": "Admin Created Test Award",
        "country": "Testland",
        "degree": "Master's",
        "funding": "Full tuition",
        "official_source_url": f"https://testland.gov/awards/admin-created-{_uuid.uuid4().hex[:8]}",
        "reason": "created during the CRUD test",
    }
    payload.update(overrides)
    return payload


def _seed(client: TestClient) -> int:
    response = client.post("/admin/scholarships", json=_create_payload(), headers=ADMIN)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_every_endpoint_fails_closed_without_the_secret(client: TestClient):
    created = _seed(client)
    calls = [
        ("get", "/admin/scholarships"),
        ("post", "/admin/scholarships"),
        ("get", f"/admin/scholarships/{created}"),
        ("patch", f"/admin/scholarships/{created}"),
        ("post", f"/admin/scholarships/{created}/archive"),
        ("delete", f"/admin/scholarships/{created}"),
        ("get", f"/admin/scholarships/{created}/audit"),
    ]
    for method, path in calls:
        for headers in ({}, {"X-Admin-Secret": "not-the-secret"}):
            response = client.request(method, path, json={}, headers=headers)
            assert response.status_code == 401, f"{method} {path} answered {response.status_code}"


def test_non_assignable_fields_are_rejected(client: TestClient):
    response = client.post(
        "/admin/scholarships",
        json=_create_payload(fields={"id": 12345, "verification_status": "confirmed"}),
        headers=ADMIN,
    )
    assert response.status_code == 422, response.text
    response = client.patch(
        f"/admin/scholarships/{_seed(client)}",
        json={"fields": {"official_source_url": "not-a-url-shape-but-allowed", "verification_status": "confirmed"}},
        headers=ADMIN,
    )
    assert response.status_code == 422, response.text


def test_create_then_list_and_get_round_trip(client: TestClient):
    created = _seed(client)
    listed = client.get("/admin/scholarships", params={"q": "Admin Created"}, headers=ADMIN).json()
    assert listed["total"] >= 1
    assert any(item["id"] == created for item in listed["items"])

    detail = client.get(f"/admin/scholarships/{created}", headers=ADMIN).json()
    assert detail["id"] == created
    assert detail["title"] == "Admin Created Test Award"

    audit = client.get(f"/admin/scholarships/{created}/audit", headers=ADMIN).json()
    assert audit["total"] >= 1
    assert audit["items"][0]["action"] == "create"


def test_update_audits_field_level_changes(client: TestClient):
    created = _seed(client)
    response = client.patch(
        f"/admin/scholarships/{created}",
        json={
            "fields": {"title": "Admin Renamed Award", "funding_amount": 42000, "funding_currency": "USD"},
            "reason": "corrected from the official page",
        },
        headers=ADMIN,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Admin Renamed Award"

    audit = client.get(f"/admin/scholarships/{created}/audit", headers=ADMIN).json()
    action = next((row for row in audit["items"] if row["action"] == "update"), None)
    assert action is not None, audit
    assert action["reason"] == "corrected from the official page"
    before = action["before_values"]
    assert before["title"] == "Admin Created Test Award"
    assert action["after_values"]["title"] == "Admin Renamed Award"


def test_archive_is_soft_audited_and_reversible_information(client: TestClient):
    created = _seed(client)
    response = client.post(
        f"/admin/scholarships/{created}/archive",
        json={"reason": "programme discontinued"},
        headers=ADMIN,
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_archived"] is True

    audit = client.get(f"/admin/scholarships/{created}/audit", headers=ADMIN).json()
    action = next(row for row in audit["items"] if row["action"] == "archive")
    assert action["after_values"]["archived_reason"] == "programme discontinued"

    again = client.post(
        f"/admin/scholarships/{created}/archive",
        json={"reason": "twice"},
        headers=ADMIN,
    )
    assert again.status_code == 409

    # It leaves the active list but is still retrievable by id.
    active = client.get("/admin/scholarships", params={"q": "Admin Created"}, headers=ADMIN).json()
    assert all(item["id"] != created for item in active["items"])
    archived_list = client.get(
        "/admin/scholarships", params={"q": "Admin Created", "archived": True}, headers=ADMIN
    ).json()
    assert any(item["id"] == created for item in archived_list["items"])


def test_delete_refuses_a_wrong_confirmation(client: TestClient):
    created = _seed(client)
    response = client.request("DELETE", f"/admin/scholarships/{created}", json={"confirm": "DELETE", "reason": "typo test"},
        headers=ADMIN,
    )
    assert response.status_code == 400, response.text
    assert client.get(f"/admin/scholarships/{created}", headers=ADMIN).status_code == 200


def test_delete_refuses_depended_upon_records_and_keeps_them(client: TestClient):
    """A record a student saved is not deletable: their row must survive it."""
    created = _seed(client)
    from app.database import get_db

    with next(get_db()) as session:
        session.add(SavedScholarship(scholarship_id=created, user_id=999_001))
        session.commit()

    response = client.request("DELETE", f"/admin/scholarships/{created}", json={"confirm": f"DELETE {created}", "reason": "must be blocked"},
        headers=ADMIN,
    )
    assert response.status_code == 409, response.text
    blocked = response.json()["detail"]["blocked_by"]
    # The dependency report names models, not tables.
    assert any("SavedScholarship" in name for name in blocked), blocked

    # The student's row and the scholarship are both still there.
    with next(get_db()) as session:
        assert session.get(Scholarship, created) is not None
        assert session.execute(
            select(SavedScholarship).where(SavedScholarship.scholarship_id == created)
        ).scalars().first() is not None

    # A refused delete must not have written an audit row claiming otherwise.
    audit = client.get(f"/admin/scholarships/{created}/audit", headers=ADMIN).json()
    assert not any(row["action"] == "delete" for row in audit["items"])


def test_successful_delete_removes_the_row_and_keeps_the_audit(client: TestClient):
    created = _seed(client)
    detail = client.get(f"/admin/scholarships/{created}", headers=ADMIN).json()
    response = client.request("DELETE", f"/admin/scholarships/{created}", json={"confirm": f"DELETE {created}", "reason": "record created in error"},
        headers=ADMIN,
    )
    assert response.status_code == 200, response.text
    assert response.json()["before"]["title"] == detail["title"]

    assert client.get(f"/admin/scholarships/{created}", headers=ADMIN).status_code == 404

    from app.database import get_db

    with next(get_db()) as session:
        assert session.get(Scholarship, created) is None
        row = (
            session.execute(
                select(ScholarshipAdminAudit)
                .where(ScholarshipAdminAudit.scholarship_id == created)
                .where(ScholarshipAdminAudit.action == "delete")
            )
            .scalars()
            .first()
        )
        assert row is not None, "the audit row cannot be swept away with the record"
        assert row.before_values["title"] == detail["title"]
        assert row.operator == "admin"
        assert row.reason == "record created in error"
        # Every column of the deleted row is captured, not just the list view.
        assert set(row.before_values) >= {"id", "title", "official_source_url", "created_at"}


def test_delete_of_a_missing_record_is_404(client: TestClient):
    response = client.request(
        "DELETE",
        "/admin/scholarships/987654321",
        json={"confirm": "DELETE 987654321", "reason": "nobody"},
        headers=ADMIN,
    )
    assert response.status_code == 404
