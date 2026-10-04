"""Public scholarship detail must live in the same universe as the public list.

`GET /api/scholarships/{id}` reached the row through a bare primary-key lookup
while every other public surface applied `public_visibility_conditions()`. The
consequence was that the catalogue's *list* and its *detail* were two different
universes: a record excluded from the list was still fully readable by guessing
or incrementing an id.

These tests are written against the real route, not the repository helper, because
the helper is shared with the internal verifier - which is required to reach
records that are deliberately not public, and must keep doing so. The bug was
never that the loader was permissive; it was that the *public* route used it.

Nothing here re-implements the visibility rule. Each case constructs a record
that is non-public for one canonical reason and asserts the route refuses it, so
this suite fails loudly if someone reintroduces a hand-rolled predicate instead of
calling the canonical one.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

ADMIN_SECRET = "visibility-admin-secret"
ADMIN_HEADERS = {"X-Admin-Secret": ADMIN_SECRET}


@pytest.fixture()
def client(monkeypatch):
    """A client whose public universe matches production's.

    ``tests/conftest.py`` deliberately switches ``SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED``
    and ``..._IMAGE`` off process-wide, because the long-standing seed rows carry
    no images and predate the gate. That is the right default for listing and
    pagination tests. It is the wrong universe for this suite: the question here
    is whether the detail endpoint honours the *same* rules as the list, and in
    production both gates are on. So they are switched back on here and restored
    afterwards, using the same mechanism as ``test_public_quality_gate.py``.
    """
    path = Path(tempfile.gettempdir()) / f"scholarzone-visibility-{uuid4().hex}.db"
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_ADMIN_SECRET", ADMIN_SECRET)
    # Production has both gates on; see the docstring above.
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE", "false")

    from app.core.config import get_settings
    from app.database import (
        get_session_factory,
        init_database,
        reset_database_connections,
    )

    # Defensive: this build re-reads the environment on every call, but the
    # settings helper is cached in some, and a stale one would silently disable
    # the gates this suite is about.
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()

    reset_database_connections()
    init_database()

    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        test_client.sz_factory = get_session_factory
        yield test_client

    reset_database_connections()
    # Best effort: on Windows a SQLite file that the engine still holds open
    # cannot be unlinked, and failing to tidy a temp file is not a test failure.
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass


def _seed(session, token: int = 0, **overrides):
    """Insert one record, public unless a test says otherwise.

    Public by construction means every clause of the canonical predicate is
    satisfied: not quarantined, not archived, authoritative status ``active``, a
    verified image, and a non-third-party image source. A case meant to be
    non-public therefore differs in exactly one clause, which is what makes the
    refusal attributable to that clause.

    No explicit id is set: ``init_database`` has already seeded rows, so a
    hard-coded id would collide. The database assigns one and callers use
    ``record.id``.
    """
    from app.models import Scholarship

    values = {
        "title": f"Public Scholarship {token}",
        "country": "Netherlands",
        "degree": "Master",
        "funding": "Full tuition",
        "official_source": f"Provider {token}",
        "official_source_url": f"https://provider{token}.example/",
        "verification_status": "active",
        "is_verified": True,
        "status": "open",
        "image_url": f"https://provider{token}.example/logo.png",
        "image_alt_text": "logo",
        "image_verified_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    values.update(overrides)
    record = Scholarship(**values)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _session(client):
    return client.sz_factory()()


# ---------------------------------------------------------------------------
# The bypass
# ---------------------------------------------------------------------------


class TestTheBypass:
    def test_an_archived_record_is_not_readable_by_direct_id(self, client):
        session = _session(client)
        record = _seed(session, 1, is_archived=True, title="ARCHIVED-CONFIDENTIAL-TITLE")

        response = client.get(f"/scholarships/{record.id}")

        assert response.status_code == 404
        assert "ARCHIVED-CONFIDENTIAL-TITLE" not in response.text

    def test_a_needs_review_record_is_not_readable_by_direct_id(self, client):
        session = _session(client)
        record = _seed(
            session,
            2,
            verification_status="needs_review",
            is_verified=True,
            title="NEEDS-REVIEW-CONFIDENTIAL-TITLE",
        )

        response = client.get(f"/scholarships/{record.id}")

        assert response.status_code == 404
        assert "NEEDS-REVIEW-CONFIDENTIAL-TITLE" not in response.text

    def test_a_quarantined_record_is_not_readable_by_direct_id(self, client):
        session = _session(client)
        record = _seed(
            session, 3, verification_status="quarantined", title="QUARANTINED-TITLE"
        )

        response = client.get(f"/scholarships/{record.id}")

        assert response.status_code == 404
        assert "QUARANTINED-TITLE" not in response.text

    def test_an_uncertain_record_is_not_readable_by_direct_id(self, client):
        """A status the catalogue does not define is not a public claim."""
        session = _session(client)
        record = _seed(session, 4, verification_status="uncertain", title="UNCERTAIN-TITLE")

        assert client.get(f"/scholarships/{record.id}").status_code == 404

    def test_a_record_without_a_verified_image_is_not_readable_by_direct_id(self, client):
        """The image gate is part of the canonical predicate, not an extra rule."""
        session = _session(client)
        record = _seed(
            session, 5, image_url=None, image_verified_at=None, title="NO-IMAGE-TITLE"
        )

        assert client.get(f"/scholarships/{record.id}").status_code == 404

    def test_a_third_party_image_only_record_is_not_readable_by_direct_id(self, client):
        session = _session(client)
        record = _seed(
            session,
            6,
            image_url="https://upload.wikimedia.org/logo.png",
            image_source_type="wikimedia",
            title="WIKIMEDIA-ONLY-TITLE",
        )

        assert client.get(f"/scholarships/{record.id}").status_code == 404

    def test_a_hidden_record_is_not_exposed_by_the_list_either(self, client):
        """List and detail must be one universe, not detail merely tightened."""
        session = _session(client)
        _seed(session, 7, is_archived=True, title="ARCHIVED-IN-LIST")
        public = _seed(session, 8, title="GENUINELY-PUBLIC")

        response = client.get("/scholarships?limit=100")
        assert response.status_code == 200
        listed = {item["id"] for item in response.json()["items"]}
        assert public.id in listed
        assert all("ARCHIVED-IN-LIST" != item["title"] for item in response.json()["items"])


# ---------------------------------------------------------------------------
# The corrected behaviour
# ---------------------------------------------------------------------------


class TestPublicDetailStaysOpen:
    def test_a_public_record_is_still_served(self, client):
        session = _session(client)
        record = _seed(session, 20)

        response = client.get(f"/scholarships/{record.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == record.id
        assert body["title"] == "Public Scholarship 20"

    def test_a_public_record_still_publishes_its_trust_pair(self, client):
        """The trust claim applicants rely on must survive the tightening.

        A publicly visible record is authoritative by definition, so the pair is
        ``active``/``True``. That ``verified`` tracks status exactly is asserted
        below on the admin surface, where a non-authoritative record is
        legitimately reachable.
        """
        session = _session(client)
        record = _seed(session, 21)

        body = client.get(f"/scholarships/{record.id}").json()

        assert body["verification_status"] == "active"
        assert body["verified"] is True

    def test_the_list_and_the_detail_agree_on_membership(self, client):
        session = _session(client)
        seeded = [
            _seed(session, 30 + index, is_archived=(index % 2 == 0))
            for index in range(6)
        ]

        listed = {
            item["id"]
            for item in client.get("/scholarships?limit=100").json()["items"]
        }
        for record in seeded:
            response = client.get(f"/scholarships/{record.id}")
            assert (response.status_code == 200) is (record.id in listed), record.id


class TestExistenceIsNotRevealed:
    def test_a_hidden_record_and_a_missing_record_answer_identically(self, client):
        """A 404 for a hidden id must be indistinguishable from a 404 for no id.

        Any difference in status, body or headers would confirm the record exists,
        which is the disclosure the boundary exists to prevent.
        """
        session = _session(client)
        record = _seed(session, 40, is_archived=True)

        hidden = client.get(f"/scholarships/{record.id}")
        missing = client.get("/scholarships/999999")

        assert hidden.status_code == missing.status_code == 404
        assert hidden.json() == missing.json()


# ---------------------------------------------------------------------------
# Public / internal separation
# ---------------------------------------------------------------------------


class TestInternalSurfacesKeepTheirAccess:
    def test_admin_verification_still_reaches_a_hidden_record(self, client):
        """An administrator must be able to verify what nobody else can see.

        Had the fix been made inside the shared loader this would 404 and the
        Admin Verification Center would be unable to do its job - which is why the
        fix belongs on the public route.
        """
        session = _session(client)
        record = _seed(session, 50, verification_status="needs_review")

        response = client.patch(
            f"/scholarships/{record.id}/verify",
            headers=ADMIN_HEADERS,
            json={"verification_status": "active", "verified_by": "admin"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["verification_status"] == "active"

    def test_admin_can_still_reach_a_quarantined_record(self, client):
        session = _session(client)
        record = _seed(session, 51, verification_status="quarantined")

        response = client.patch(
            f"/scholarships/{record.id}/verify",
            headers=ADMIN_HEADERS,
            json={"verification_status": "needs_review", "verified_by": "admin"},
        )

        assert response.status_code == 200, response.text

    def test_verification_write_still_requires_the_admin_secret(self, client):
        session = _session(client)
        record = _seed(session, 52, verification_status="needs_review")

        response = client.patch(
            f"/scholarships/{record.id}/verify",
            json={"verification_status": "active", "verified_by": "admin"},
        )

        assert response.status_code in (401, 403)

    def test_the_verification_queue_still_lists_hidden_records(self, client):
        """The queue is the one surface that *must* show non-public records.

        If the fix had leaked into a shared filter, this is where an operator
        would discover it: a quarantined record they are trying to resolve would
        simply not appear.
        """
        session = _session(client)
        record = _seed(session, 53, verification_status="needs_review")

        response = client.get(
            "/admin/verification/queue?limit=100", headers=ADMIN_HEADERS
        )

        assert response.status_code == 200
        payload = response.json()
        assert record.id in {row["id"] for row in payload["items"]}


# ---------------------------------------------------------------------------
# Field exposure, on both a public and a hidden record
# ---------------------------------------------------------------------------


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


class TestNoInternalFieldLeakage:
    def test_a_public_detail_response_carries_no_internal_field(self, client):
        session = _session(client)
        record = _seed(session, 60, verification_notes="INTERNAL-NOTE", verified_by="admin")

        body = client.get(f"/scholarships/{record.id}").json()

        for field in INTERNAL_FIELDS:
            assert field not in body, field
        assert "INTERNAL-NOTE" not in str(body)

    def test_a_hidden_record_returns_no_body_to_inspect(self, client):
        """The strongest form of the guarantee: nothing is serialised at all.

        A hidden record must not reach the serializer, so there is no payload in
        which a field could have leaked.
        """
        session = _session(client)
        record = _seed(
            session,
            61,
            is_archived=True,
            title="HIDDEN-TITLE",
            verification_notes="HIDDEN-INTERNAL-NOTE",
            verified_by="admin",
        )

        response = client.get(f"/scholarships/{record.id}")

        assert response.status_code == 404
        for field in INTERNAL_FIELDS:
            assert field not in response.text
        assert "HIDDEN-INTERNAL-NOTE" not in response.text
        assert "HIDDEN-TITLE" not in response.text

    def test_the_detail_route_still_rejects_a_non_numeric_id(self, client):
        assert client.get("/scholarships/not-a-number").status_code == 422


# ---------------------------------------------------------------------------
# Canonical predicate, not a re-implementation
# ---------------------------------------------------------------------------


class TestCanonicalPredicateIsTheOneUsed:
    def test_the_detail_query_applies_the_canonical_conditions(self):
        """A structural check, so a hand-rolled filter cannot pass the suite.

        The public read must go through ``public_visibility_conditions()``. Asserted
        on the source because a behavioural test cannot distinguish the canonical
        predicate from a faithful copy of it - and a copy is exactly the drift this
        codebase has already been bitten by.
        """
        import inspect

        from app.services import scholarships as service

        source = inspect.getsource(service.get_scholarship_details)
        assert "public_visibility_conditions" in source

    def test_the_shared_loader_is_left_untouched_for_internal_callers(self):
        """The permissive loader must stay permissive.

        The internal verifier has to reach quarantined and archived rows; that is
        its contract. Tightening it would break verification without closing the
        public hole.
        """
        import inspect

        from app.repositories import scholarships as repository

        source = inspect.getsource(repository.get_scholarship_by_id)
        assert "public_visibility_conditions" not in source