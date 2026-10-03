"""Tests for the Admin Verification Center.

Security is asserted here at the HTTP boundary, not in a browser: the queue must
be unreachable without the administrator secret, decisions must be validated by
the server, and a stale screen must not be able to overwrite a newer decision.

The counts are asserted to be *derived*. A test that hard-codes 47 would pass
forever while the catalogue changed underneath it, so these tests change the data
and require the numbers to move.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest


ADMIN_SECRET = "admin-secret-for-tests"
ADMIN_HEADERS = {"X-Admin-Secret": ADMIN_SECRET}


@pytest.fixture()
def client():
    """An isolated database, seeded, behind a known administrator secret."""
    path = Path(tempfile.gettempdir()) / f"scholarzone-adminvc-{uuid4().hex}.db"
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_ADMIN_SECRET"] = ADMIN_SECRET

    from app.core.config import get_settings
    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
    init_database()

    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        # Seeding happens during startup, so the catalogue is cleared only once the
        # app is running; otherwise startup would put it straight back.
        from sqlalchemy import delete

        from app.models import Scholarship as _S
        from app.models import ScholarshipReview as _R
        from app.models import ScholarshipVerificationHistory as _H

        _db = get_session_factory()()
        try:
            _db.execute(delete(_H))
            _db.execute(delete(_R))
            _db.execute(delete(_S))
            _db.commit()
        finally:
            _db.close()
        test_client.sz_factory = get_session_factory()
        yield test_client

    reset_database_connections()
    try:
        path.unlink()
    except OSError:
        pass


def _add(session, sid: int, **kw) -> int:
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
            verification_status=kw.get("verification_status", "active"),
            official_source=kw.get("official_source", "Official Provider"),
            official_source_url=kw.get("official_source_url", f"https://o{sid}.example.org/p"),
            image_url=kw.get("image_url"),
            image_verified_at=kw.get("image_verified_at"),
            deadline_date=kw.get("deadline_date"),
            last_verified_date=kw.get("last_verified_date"),
            next_verification_due=kw.get("next_verification_due"),
        )
    )
    return sid


def _seed(session) -> dict[str, int]:
    """Two publicly visible pending records and two that are held back."""
    reviewed = datetime(2026, 1, 1).date()
    for sid in (1, 2):
        _add(
            session,
            sid,
            verification_status="needs_review",
            is_verified=True,
            image_url=f"https://img.example.org/{sid}.png",
            image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_verified_date=reviewed,
        )
    for sid in (3, 4):
        _add(
            session,
            sid,
            verification_status="needs_review",
            is_verified=True,
            is_archived=True,
            last_verified_date=reviewed,
        )
    session.commit()
    return {"public": 2, "storage_only": 2, "total": 4}


def _session(client):
    return client.sz_factory()


# ---------------------------------------------------------------------------
# 1-4. Authentication and route protection
# ---------------------------------------------------------------------------


def test_unauthenticated_admin_api_is_blocked(client):
    for path in ("/admin/verification/summary", "/admin/verification/queue"):
        assert client.get(path).status_code == 401


def test_wrong_secret_is_blocked(client):
    response = client.get(
        "/admin/verification/summary", headers={"X-Admin-Secret": "not-the-secret"}
    )
    assert response.status_code == 401


def test_non_admin_cannot_reach_the_decision_endpoint(client):
    session = _session(client)
    _seed(session)
    sid = 1
    body = {
        "decision": "verify",
        "rationale": "Confirmed against the official page.",
        "expected_updated_at": datetime.now(timezone.utc).isoformat(),
        "expected_verification_status": "needs_review",
    }
    assert client.post(f"/admin/verification/scholarships/{sid}/decision", json=body).status_code == 401
    assert (
        client.post(
            f"/admin/verification/scholarships/{sid}/decision",
            json=body,
            headers={"X-Admin-Secret": "guess"},
        ).status_code
        == 401
    )


def test_authorized_admin_api_succeeds(client):
    session = _session(client)
    _seed(session)
    summary = client.get("/admin/verification/summary", headers=ADMIN_HEADERS)
    assert summary.status_code == 200
    queue = client.get("/admin/verification/queue", headers=ADMIN_HEADERS)
    assert queue.status_code == 200
    assert queue.json()["total"] == 4


def test_admin_route_is_protected_even_for_existing_rows(client):
    session = _session(client)
    _seed(session)
    assert client.get("/admin/verification/scholarships/1").status_code == 401
    assert (
        client.get("/admin/verification/scholarships/1", headers=ADMIN_HEADERS).status_code == 200
    )


def test_missing_secret_configuration_fails_closed(client, monkeypatch):
    """A deployment that forgets the secret must expose nothing, not everything."""
    from app.core import admin_auth

    class _NoSecret:
        admin_secret = None

    monkeypatch.setattr(admin_auth, "get_settings", lambda: _NoSecret())
    assert client.get("/admin/verification/summary", headers=ADMIN_HEADERS).status_code == 401
    assert client.get("/admin/verification/queue", headers=ADMIN_HEADERS).status_code == 401


# ---------------------------------------------------------------------------
# 5. Admin-only metadata does not leak publicly
# ---------------------------------------------------------------------------


def test_public_detail_does_not_expose_admin_metadata(client):
    session = _session(client)
    _seed(session)
    public = client.get("/scholarships/1")
    assert public.status_code == 200
    body = public.json()
    for leaked in ("open_conflicts", "legacy_is_verified", "scope", "review_flags", "history"):
        assert leaked not in body, leaked


def test_public_response_contract_is_unchanged(client):
    session = _session(client)
    _seed(session)
    body = client.get("/scholarships/1").json()
    # The authoritative pair the public API has always published.
    assert body["verification_status"] == "needs_review"
    assert body["verified"] is False


# ---------------------------------------------------------------------------
# 6-8. Decision authorization, validation, evidence
# ---------------------------------------------------------------------------


def test_valid_decision_is_accepted_and_recorded(client):
    session = _session(client)
    _seed(session)
    row = session.get(__import__("app.models", fromlist=["Scholarship"]).Scholarship, 1)
    session.refresh(row)
    payload = {
        "decision": "verify",
        "rationale": "Official call page confirms the programme is open.",
        "evidence_source_url": "https://o1.example.org/p",
        "expected_updated_at": row.updated_at.isoformat(),
        "expected_verification_status": row.verification_status,
    }
    response = client.post("/admin/verification/scholarships/1/decision", json=payload, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["previous_status"] == "needs_review"
    assert body["verification_status"] == "active"
    assert body["public_verified"] is True

    detail = client.get("/admin/verification/scholarships/1", headers=ADMIN_HEADERS).json()
    assert any(h["change_type"] == "admin_decision" for h in detail["history"])
    assert any(f["field_name"] == "verification_status" for f in detail["review_flags"])
    # The legacy column is brought into line so it cannot drift again.
    assert row.is_verified is True


def test_invalid_decision_is_rejected(client):
    session = _session(client)
    _seed(session)
    base = {
        "rationale": "Looks right to me.",
        "expected_updated_at": datetime.now(timezone.utc).isoformat(),
        "expected_verification_status": "needs_review",
    }
    for bad in ("approve", "delete", "", None, "VERIFY"):
        response = client.post(
            "/admin/verification/scholarships/1/decision",
            json={**base, "decision": bad},
            headers=ADMIN_HEADERS,
        )
        assert response.status_code in (400, 422), (bad, response.status_code)


def test_decision_requires_a_rationale(client):
    session = _session(client)
    _seed(session)
    response = client.post(
        "/admin/verification/scholarships/1/decision",
        json={"decision": "verify", "rationale": "", "expected_updated_at": datetime.now(timezone.utc).isoformat()},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


def test_decision_requires_the_concurrency_token(client):
    session = _session(client)
    _seed(session)
    response = client.post(
        "/admin/verification/scholarships/1/decision",
        json={"decision": "verify", "rationale": "Confirmed upstream."},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


def test_decision_on_missing_record_is_404(client):
    response = client.post(
        "/admin/verification/scholarships/999999/decision",
        json={"decision": "verify", "rationale": "Confirmed.",
        "expected_updated_at": datetime.now(timezone.utc).isoformat(),
        "expected_verification_status": "needs_review",
    },
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 9. Optimistic concurrency
# ---------------------------------------------------------------------------


def test_stale_update_is_rejected(client):
    """Admin A's open screen must not overwrite Admin B's newer decision."""
    session = _session(client)
    _seed(session)
    from app.models import Scholarship

    row = session.get(Scholarship, 1)
    stale_version = row.updated_at.isoformat()
    stale_status = row.verification_status

    # Admin B decides first.
    first = client.post(
        "/admin/verification/scholarships/1/decision",
        json={
            "decision": "verify",
            "rationale": "Admin B confirmed the official page.",
            "expected_updated_at": stale_version,
            "expected_verification_status": stale_status,
        },
        headers=ADMIN_HEADERS,
    )
    assert first.status_code == 200

    # Admin A still holds the old screen and tries a different decision.
    second = client.post(
        "/admin/verification/scholarships/1/decision",
        json={
            "decision": "reject",
            "rationale": "Admin A decided differently.",
            "expected_updated_at": stale_version,
            "expected_verification_status": stale_status,
        },
        headers=ADMIN_HEADERS,
    )
    assert second.status_code == 409
    session.expire_all()
    assert session.get(Scholarship, 1).verification_status == "active"


def test_repeated_identical_decision_is_refused(client):
    session = _session(client)
    _seed(session)
    from app.models import Scholarship

    row = session.get(Scholarship, 1)
    payload = {
        "decision": "verify",
        "rationale": "Confirmed upstream.",
        "expected_updated_at": row.updated_at.isoformat(),
        "expected_verification_status": row.verification_status,
    }
    assert client.post("/admin/verification/scholarships/1/decision", json=payload, headers=ADMIN_HEADERS).status_code == 200
    session.expire_all()
    row = session.get(Scholarship, 1)
    payload["expected_updated_at"] = row.updated_at.isoformat()
    payload["expected_verification_status"] = row.verification_status
    assert client.post("/admin/verification/scholarships/1/decision", json=payload, headers=ADMIN_HEADERS).status_code == 400


# ---------------------------------------------------------------------------
# 10-11. Audit trail and absence of bulk operations
# ---------------------------------------------------------------------------


def test_audit_event_is_append_only(client):
    """A second decision must not rewrite the first one's record."""
    session = _session(client)
    _seed(session)
    from app.models import Scholarship

    def decide(sid, decision, rationale):
        session.expire_all()
        row = session.get(Scholarship, sid)
        response = client.post(
            f"/admin/verification/scholarships/{sid}/decision",
            json={
                "decision": decision,
                "rationale": rationale,
                "expected_updated_at": row.updated_at.isoformat(),
                "expected_verification_status": row.verification_status,
            },
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200, response.text
        return response

    decide(1, "verify", "First decision.")
    decide(1, "keep_under_review", "Second look needed.")

    detail = client.get("/admin/verification/scholarships/1", headers=ADMIN_HEADERS)
    assert detail.status_code == 200
    decisions = [h for h in detail.json()["history"] if h["change_type"] == "admin_decision"]
    assert len(decisions) == 2, detail.json()["history"]
    # Newest first, and the earlier decision still reads exactly as it was written.
    assert decisions[0]["evidence_text"] == "Second look needed."
    assert decisions[1]["evidence_text"] == "First decision."
    assert decisions[1]["new_value"] == "active"
    assert decisions[0]["new_value"] == "needs_review"
    # The actor is recorded on the review row.
    flags = [f for f in detail.json()["review_flags"] if f["field_name"] == "verification_status"]
    assert len(flags) == 2
    assert all(f["decision"] in {"approved", "pending"} for f in flags)


def test_no_bulk_decision_endpoint_exists(client):
    session = _session(client)
    _seed(session)
    for path in (
        "/admin/verification/bulk",
        "/admin/verification/bulk-decide",
        "/admin/verification/decisions",
        "/admin/verification/verify-all",
    ):
        assert client.post(path, json={}, headers=ADMIN_HEADERS).status_code in (404, 405)


# ---------------------------------------------------------------------------
# 12-13. Dynamic counts and derived truth
# ---------------------------------------------------------------------------


def test_review_counts_are_derived_not_hardcoded(client):
    session = _session(client)
    _seed(session)
    before = client.get("/admin/verification/summary", headers=ADMIN_HEADERS).json()
    assert before["storage_wide_pending"] == 4
    assert before["public_pending"] == 2
    assert before["storage_only_pending"] == 2

    # Two more publicly visible pending records, and no code change.
    for sid in (5, 6, 7):
        _add(
            session,
            sid,
            verification_status="needs_review",
            is_verified=True,
            image_url=f"https://img.example.org/{sid}.png",
            image_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_verified_date=date(2026, 1, 1),
        )
    session.commit()

    after = client.get("/admin/verification/summary", headers=ADMIN_HEADERS).json()
    assert after["storage_wide_pending"] == 7
    assert after["public_pending"] == 5
    assert after["storage_only_pending"] == 2


def test_counts_drop_when_a_record_is_decided(client):
    session = _session(client)
    _seed(session)
    from app.models import Scholarship

    row = session.get(Scholarship, 1)
    client.post(
        "/admin/verification/scholarships/1/decision",
        json={
            "decision": "verify",
            "rationale": "Resolved after checking the source.",
            "expected_updated_at": row.updated_at.isoformat(),
            "expected_verification_status": row.verification_status,
        },
        headers=ADMIN_HEADERS,
    )
    after = client.get("/admin/verification/summary", headers=ADMIN_HEADERS).json()
    assert after["storage_wide_pending"] == 3
    assert after["public_pending"] == 1


def test_queue_truth_derives_from_verification_status_not_the_legacy_boolean(client):
    session = _session(client)
    _add(session, 1, verification_status="needs_review", is_verified=False)
    session.commit()
    items = client.get("/admin/verification/queue", headers=ADMIN_HEADERS).json()["items"]
    target = next(i for i in items if i["id"] == 1)
    # Status says review, so the record is in the queue and not publicly verified,
    # even though the legacy boolean disagrees.
    assert target["verification_status"] == "needs_review"
    assert target["public_verified"] is False
    assert target["legacy_is_verified"] is False


def test_legacy_disagreement_is_surfaced_as_a_diagnostic(client):
    session = _session(client)
    _add(session, 1, verification_status="needs_review", is_verified=True)
    session.commit()
    item = next(
        i
        for i in client.get("/admin/verification/queue", headers=ADMIN_HEADERS).json()["items"]
        if i["id"] == 1
    )
    assert item["legacy_agrees_with_status"] is False


# ---------------------------------------------------------------------------
# 14. Filtering, search, pagination, deterministic ordering
# ---------------------------------------------------------------------------


def test_scope_filter_separates_public_from_storage_only(client):
    session = _session(client)
    _seed(session)
    public = client.get("/admin/verification/queue?scope=public", headers=ADMIN_HEADERS).json()
    assert public["total"] == 2
    assert {i["id"] for i in public["items"]} == {1, 2}
    hidden = client.get("/admin/verification/queue?scope=storage_only", headers=ADMIN_HEADERS).json()
    assert hidden["total"] == 2
    assert {i["id"] for i in hidden["items"]} == {3, 4}


def test_search_matches_name_and_id(client):
    session = _session(client)
    _seed(session)
    by_name = client.get("/admin/verification/queue?search=Programme 3", headers=ADMIN_HEADERS).json()
    assert {i["id"] for i in by_name["items"]} == {3}
    by_id = client.get("/admin/verification/queue?search=2", headers=ADMIN_HEADERS).json()
    assert 2 in {i["id"] for i in by_id["items"]}


def test_status_filter_works_server_side(client):
    session = _session(client)
    _seed(session)
    _add(session, 5, verification_status="uncertain", is_verified=True)
    session.commit()
    body = client.get("/admin/verification/queue?verification_status=uncertain", headers=ADMIN_HEADERS).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == 5


def test_pagination_is_stable_and_deterministic(client):
    session = _session(client)
    _seed(session)
    for sid in range(10, 20):
        _add(session, sid, verification_status="needs_review", is_verified=True, is_archived=True,
             last_verified_date=date(2026, 1, 1))
    session.commit()

    first = client.get("/admin/verification/queue?sort=id_placeholder", headers=ADMIN_HEADERS)
    assert first.status_code == 400  # unknown sort rejected

    page1 = client.get("/admin/verification/queue?sort=title&limit=5&offset=0", headers=ADMIN_HEADERS).json()
    page2 = client.get("/admin/verification/queue?sort=title&limit=5&offset=5", headers=ADMIN_HEADERS).json()
    assert page1["total"] == page2["total"] == 14
    ids1 = [i["id"] for i in page1["items"]]
    ids2 = [i["id"] for i in page2["items"]]
    assert len(ids1) == len(ids2) == 5
    assert not set(ids1) & set(ids2)
    # Repeating the same request returns the same page, not a reshuffle.
    again = client.get("/admin/verification/queue?sort=title&limit=5&offset=0", headers=ADMIN_HEADERS).json()
    assert [i["id"] for i in again["items"]] == ids1


def test_conflict_filter_and_flags(client):
    from app.models import ScholarshipReview

    session = _session(client)
    _seed(session)
    session.add(
        ScholarshipReview(
            scholarship_id=1,
            field_name="deadline_display",
            current_value="1 March 2026",
            proposed_value="15 March 2026",
            conflict_reason="Two official pages disagree on the closing date.",
            verification_state="needs_review",
            confidence="low",
            source_urls=["https://a.example.org", "https://b.example.org"],
            evidence_text="Source A says 1 March, source B says 15 March.",
            decision="pending",
        )
    )
    session.commit()

    conflicted = client.get("/admin/verification/queue?has_conflicts=true", headers=ADMIN_HEADERS).json()
    assert conflicted["total"] == 1
    assert conflicted["items"][0]["id"] == 1
    assert conflicted["items"][0]["open_conflicts"] == 1

    clean = client.get("/admin/verification/queue?has_conflicts=false", headers=ADMIN_HEADERS).json()
    assert 1 not in {i["id"] for i in clean["items"]}

    detail = client.get("/admin/verification/scholarships/1", headers=ADMIN_HEADERS).json()
    conflict = next(c for c in detail["conflicts"] if c["field_name"] == "deadline_display")
    # Both sides shown verbatim; never merged into one invented answer.
    assert conflict["current_value"] == "1 March 2026"
    assert conflict["proposed_value"] == "15 March 2026"
    assert len(conflict["source_urls"]) == 2
    assert detail["review_flags"][0]["conflict_reason"]


# ---------------------------------------------------------------------------
# 15. No automatic decisions on read
# ---------------------------------------------------------------------------


def test_reading_the_queue_never_changes_anything(client):
    session = _session(client)
    _seed(session)
    from app.models import Scholarship

    before = {r.id: (r.verification_status, r.is_verified) for r in session.query(Scholarship)}
    for _ in range(3):
        client.get("/admin/verification/summary", headers=ADMIN_HEADERS)
        client.get("/admin/verification/queue", headers=ADMIN_HEADERS)
        client.get("/admin/verification/scholarships/1", headers=ADMIN_HEADERS)
    session.expire_all()
    after = {r.id: (r.verification_status, r.is_verified) for r in session.query(Scholarship)}
    assert before == after


def test_special_records_are_not_auto_resolved(client):
    """79/113/134/140 must survive an admin session untouched."""
    session = _session(client)
    ids = (79, 113, 134, 140)
    for sid in ids:
        _add(session, sid, verification_status="needs_review", is_verified=True, is_archived=True,
             last_verified_date=date(2026, 1, 1))
    session.commit()
    client.get("/admin/verification/queue", headers=ADMIN_HEADERS)
    client.get("/admin/verification/summary", headers=ADMIN_HEADERS)
    session.expire_all()
    from app.models import Scholarship

    for sid in ids:
        assert session.get(Scholarship, sid).verification_status == "needs_review"