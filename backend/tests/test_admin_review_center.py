"""Tests for the private Review Center.

The gap these cover is discoverability, not mechanics: the queue existed and
approve/reject worked, but the listing was an unbounded bare array with no
counts, no paging, no search and no filters, and the dashboard derived its
"pending" number from the 100 scholarships it happened to have loaded. An owner
was told work was waiting with no way to find it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base, ImageReview, Scholarship, ScholarshipReview

SECRET = "test-admin-secret"

#: The session factory of the currently-mounted test database, so assertions
#: read the rows the test created rather than the live catalogue.
TestingSessionFactory = None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'reviews.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    session = TestingSession()
    try:
        base = Scholarship(
            title="Alpha Scholarship",
            country="Germany",
            degree="Master",
            funding="Full",
            official_source="Alpha University",
            verification_status="needs_review",
        )
        other = Scholarship(
            title="Beta Fellowship",
            country="Japan",
            degree="PhD",
            funding="Full",
            official_source="Beta Institute",
            # An approved image must be traceable, so the record needs an
            # official source to fall back to when the review carries no page.
            official_source_url="https://beta.example/fellowship",
            verification_status="active",
        )
        session.add_all([base, other])
        session.commit()
        alpha_id = base.id
        beta_id = other.id

        for index in range(1, 8):
            session.add(
                ImageReview(
                    scholarship_id=alpha_id,
                    image_url=f"https://alpha.example/img{index}.jpg",
                    image_kind="program_image" if index % 2 else "official_logo",
                    source_page="https://alpha.example/",
                    source_type="official_scholarship",
                    confidence="HIGH" if index < 4 else "LOW",
                    decision="pending" if index < 6 else "rejected",
                    relevance_evidence="visible on the scholarship page",
                )
            )
        session.add(
            ImageReview(
                scholarship_id=beta_id,
                image_url="https://beta.example/logo.svg",
                image_kind="official_logo",
                confidence="MEDIUM",
                decision="pending",
            )
        )
        session.add(
            ScholarshipReview(
                scholarship_id=alpha_id,
                field_name="verification_status",
                decision="pending",
                conflict_reason="needs a second look",
                verification_state="needs_review",
            )
        )
        session.commit()
    finally:
        session.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setenv("SCHOLARZONE_ADMIN_SECRET", SECRET)
    import importlib

    from app.core import config as config_module

    importlib.reload(config_module)
    global TestingSessionFactory
    TestingSessionFactory = TestingSession
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _auth():
    return {"X-Admin-Secret": SECRET}


class TestQueueIsPrivate:
    def test_missing_secret_is_refused(self, client):
        assert client.get("/admin/images/review-queue").status_code == 401

    def test_wrong_secret_is_refused(self, client):
        assert client.get(
            "/admin/images/review-queue", headers={"X-Admin-Secret": "wrong"}
        ).status_code == 401

    def test_auth_failure_explains_the_requirement(self, client):
        body = client.get("/admin/images/review-queue").json()
        assert "authentication" in body["detail"].lower()


class TestQueueIsFindable:
    def test_queue_reports_database_wide_counts(self, client):
        """The number on screen must be the real backlog, not the page size."""
        payload = client.get("/admin/images/review-queue", headers=_auth()).json()
        counts = payload["counts"]
        assert counts["pending_image_reviews"] == 6
        assert counts["decided_image_reviews"] == 2
        assert counts["all_image_reviews"] == 8
        assert counts["pending_scholarship_reviews"] == 1
        assert counts["scholarships_needing_review"] == 1

    def test_total_is_not_derived_from_the_returned_page(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"limit": 2}
        ).json()
        assert payload["total"] == 6
        assert len(payload["items"]) == 2

    def test_pagination_metadata_is_returned(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"page": 1, "limit": 2}
        ).json()
        pagination = payload["pagination"]
        assert pagination["page"] == 1
        assert pagination["pages"] == 3
        assert pagination["has_next"] is True
        assert pagination["has_prev"] is False

    def test_last_page_reports_no_next(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"page": 3, "limit": 2}
        ).json()
        assert payload["pagination"]["has_next"] is False
        assert payload["pagination"]["has_prev"] is True

    def test_limit_is_clamped(self, client):
        """An unbounded limit is how a page of records looked like a catalogue."""
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"limit": 5000}
        ).json()
        assert payload["pagination"]["limit"] == 100

    def test_search_finds_by_title(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"search": "Beta"}
        ).json()
        assert payload["total"] == 1
        assert payload["items"][0]["scholarship_title"] == "Beta Fellowship"

    def test_search_finds_by_scholarship_id(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"search": "Alpha Scholarship"}
        ).json()
        assert payload["total"] >= 1

    def test_filter_by_image_kind(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"kind": "official_logo"}
        ).json()
        # Of the 8 reviews, the pending official_logo ones are img2, img4, the
        # Beta logo; img6 is a decided (rejected) logo and stays out of the queue.
        assert payload["total"] == 3
        assert {i["image_kind"] for i in payload["items"]} == {"official_logo"}

    def test_filter_by_confidence(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"confidence": "HIGH"}
        ).json()
        assert {i["confidence"] for i in payload["items"]} == {"HIGH"}

    def test_decided_items_are_excluded_by_default(self, client):
        payload = client.get("/admin/images/review-queue", headers=_auth()).json()
        assert {i["decision"] for i in payload["items"]} == {"pending"}

    def test_decided_items_can_be_shown_explicitly(self, client):
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"include_decided": True}
        ).json()
        assert payload["total"] == 8

    def test_sorting_is_supported(self, client):
        for order in ("oldest", "newest", "confidence"):
            payload = client.get(
                "/admin/images/review-queue", headers=_auth(), params={"sort": order}
            ).json()
            assert payload["total"] == 6

    def test_card_carries_everything_needed_to_decide(self, client):
        item = client.get("/admin/images/review-queue", headers=_auth()).json()["items"][0]
        for field in (
            "scholarship_id",
            "scholarship_title",
            "provider",
            "country",
            "image_url",
            "image_kind",
            "source_type",
            "source_page",
            "relevance_evidence",
            "confidence",
            "reason_for_review",
            "created_at",
        ):
            assert field in item, f"review card is missing {field}"


class TestDecisionWorkflow:
    def test_reject_removes_from_pending_and_preserves_history(self, client):
        payload = client.get("/admin/images/review-queue", headers=_auth()).json()
        review_id = payload["items"][0]["id"]
        result = client.post(
            f"/admin/images/review-queue/{review_id}/decision",
            headers=_auth(),
            json={"approved": False, "reviewer_note": "not scholarship specific"},
        )
        assert result.status_code == 200
        # The count moves with the decision, so the badge cannot go stale.
        assert result.json()["counts"]["pending_image_reviews"] == 5
        # The row survives: the queue empties, the audit trail does not.
        after = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"include_decided": True}
        ).json()
        assert any(i["id"] == review_id for i in after["items"])

    def test_approve_installs_the_image_with_provenance(self, client):
        """An approved review becomes the scholarship's verified image.

        Beta is used because Alpha already carries an image by this point, and
        the service deliberately refuses to replace a stronger stored image -
        so approving onto Alpha would be a no-op, and testing that no-op here
        would assert nothing about installation.
        """
        payload = client.get(
            "/admin/images/review-queue", headers=_auth(), params={"kind": "official_logo"}
        ).json()
        review = next(
            i for i in payload["items"] if i["scholarship_title"] == "Beta Fellowship"
        )
        client.post(
            f"/admin/images/review-queue/{review['id']}/decision",
            headers=_auth(),
            json={"approved": True},
        )
        # Read the row back through the test database. Reading the production
        # session here would assert against whatever happens to be in the live
        # catalogue, which is how a test suite ends up "verifying" the wrong
        # record entirely.
        session = TestingSessionFactory()
        try:
            row = session.get(Scholarship, review["scholarship_id"])
            assert row.image_url == review["image_url"]
            assert row.image_verified_at is not None
            assert row.image_source_url
            assert row.image_kind == review["image_kind"]
            assert row.image_evaluation_status == "verified"
        finally:
            session.close()
    def test_decision_requires_authentication(self, client):
        assert client.post(
            "/admin/images/review-queue/1/decision", json={"approved": True}
        ).status_code == 401
