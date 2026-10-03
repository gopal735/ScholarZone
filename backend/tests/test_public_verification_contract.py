"""Tests for the public verification-state contract.

``ScholarshipResponse`` is the only public serializer for a scholarship, and both
the list and the detail contract inherit it. It used to publish a legacy
``verified`` boolean taken straight from the stored ``is_verified`` column, which
meant a record under human review could answer ``verification_status:
"needs_review"`` and ``verified: true`` in the same payload. The frontend had
already been migrated to read the status, so the contradiction reached API
consumers only.

``verification_status`` is now the single authority: the public boolean is derived
from it in one place and any supplied legacy value is ignored.

These tests pin the mapping, both directions of the invariant, the null and
unexpected states, and the real deployed rows the defect was observed on.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pytest


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-verify-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

from starlette.testclient import TestClient  # noqa: E402

from app.database import get_session_factory, reset_database_connections  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.schemas import ScholarshipDetailResponse, ScholarshipResponse  # noqa: E402
from app.seed import seed_database  # noqa: E402
from app.verification_contract import (  # noqa: E402
    AUTHORITATIVE_VERIFIED_STATUS,
    public_verified_from_status,
)

SNAPSHOT = Path(__file__).resolve().parents[2] / "verification" / "live_raw.json"
needs_snapshot = pytest.mark.skipif(
    not SNAPSHOT.exists(), reason="deployed-row snapshot not present in this checkout"
)

#: The records the contradiction was observed on in production: 79, 113, 134 and
#: 140 are all awaiting human review while their legacy boolean still says True.
#: 16 is the control, a genuinely active record.
REVIEW_RECORD_IDS = (79, 113, 134, 140)
ACTIVE_CONTROL_ID = 16


MINIMAL_ROW = {
    "id": 1,
    "title": "Test Scholarship",
    "name": "Test Scholarship",
    "country": "Nigeria",
    "degree": "BSc",
    "degree_levels": "BSc",
    "funding": "Full",
    "funding_type": "Full",
    "deadline": "2026-12-01",
    "deadline_precision": "day",
    "status": "open",
    "updated_at": datetime(2026, 1, 1),
}


def project(row: dict) -> ScholarshipResponse:
    """Project a stored row onto the public contract, the way the router does."""
    payload = {**MINIMAL_ROW, **{k: v for k, v in row.items() if k in ScholarshipResponse.model_fields}}
    if "verified" not in payload and "is_verified" in row:
        payload["verified"] = row["is_verified"]
    return ScholarshipResponse(**payload)


# ---------------------------------------------------------------------------
# The rule itself
# ---------------------------------------------------------------------------


def test_active_status_is_verified():
    assert public_verified_from_status(AUTHORITATIVE_VERIFIED_STATUS) is True


@pytest.mark.parametrize(
    "status",
    ["needs_review", "uncertain", "failed", "quarantined", "pending", "approved"],
)
def test_every_non_active_status_is_not_verified(status):
    assert public_verified_from_status(status) is False


@pytest.mark.parametrize("value", [None, "", "   ", 1, True, [], object()])
def test_absent_or_unusable_status_is_never_verified(value):
    assert public_verified_from_status(value) is False


def test_status_match_is_exact_not_fuzzy():
    assert public_verified_from_status("Active") is False
    assert public_verified_from_status(" active") is False
    assert public_verified_from_status("active ") is False


# ---------------------------------------------------------------------------
# The public contract
# ---------------------------------------------------------------------------


def test_active_status_publishes_verified_true():
    assert project({"verification_status": "active", "is_verified": True}).verified is True


def test_needs_review_publishes_verified_false():
    assert (
        project({"verification_status": "needs_review", "is_verified": True}).verified
        is False
    )


def test_contradictory_legacy_boolean_cannot_override_status():
    """The defect: needs_review beside a legacy True must publish False."""
    payload = project({"verification_status": "needs_review", "is_verified": True})
    assert payload.verification_status == "needs_review"
    assert payload.verified is False


def test_active_wins_over_a_false_legacy_boolean():
    """Status is the authority, so a stale legacy False must not unverify a record."""
    assert project({"verification_status": "active", "is_verified": False}).verified is True


def test_missing_status_never_defaults_to_verified():
    payload = project({"is_verified": True})
    assert payload.verified is False
    assert payload.verification_status == "needs_review"


def test_null_status_never_defaults_to_verified():
    payload = project({"verification_status": None, "is_verified": True})
    assert payload.verified is False
    assert payload.verification_status == "needs_review"


def test_verified_is_never_true_for_a_non_active_status():
    for status in ("needs_review", "uncertain", "failed", "quarantined"):
        assert project({"verification_status": status, "is_verified": True}).verified is False


def test_both_directions_of_the_invariant_hold_for_every_case():
    cases = ["active", "needs_review", "uncertain", "failed", None, "", "approved"]
    for status in cases:
        for legacy in (True, False):
            payload = project({"verification_status": status, "is_verified": legacy})
            if payload.verification_status == AUTHORITATIVE_VERIFIED_STATUS:
                assert payload.verified is True, (status, legacy)
            else:
                assert payload.verified is False, (status, legacy)


def test_detail_contract_inherits_the_same_rule():
    row = {
        "id": 1,
        "title": "T",
        "name": "T",
        "country": "Nigeria",
        "degree": "BSc",
        "degree_levels": "BSc",
        "funding": "Full",
        "funding_type": "Full",
        "deadline": "2026-12-01",
        "deadline_date": date(2026, 12, 1),
        "deadline_precision": "day",
        "status": "open",
        "verification_status": "needs_review",
        "is_verified": True,
        "updated_at": datetime(2026, 1, 1),
        "eligibility": ["Nigeria"],
        "benefits": ["Stipend"],
        "coverage": ["Tuition"],
        "application_method": ["Online"],
    }
    payload = ScholarshipDetailResponse(**{k: v for k, v in row.items() if k in ScholarshipDetailResponse.model_fields})
    assert payload.verification_status == "needs_review"
    assert payload.verified is False


def test_status_is_reported_unchanged():
    for status in ("active", "needs_review", "uncertain", "approved"):
        assert project({"verification_status": status}).verification_status == status


# ---------------------------------------------------------------------------
# The real deployed rows
# ---------------------------------------------------------------------------


@needs_snapshot
@pytest.mark.parametrize("sid", REVIEW_RECORD_IDS)
def test_production_review_records_publish_verified_false(sid):
    row = json.loads(SNAPSHOT.read_text(encoding="utf-8"))[str(sid)]
    assert row["verification_status"] == "needs_review"
    assert row["is_verified"] is True, "the legacy boolean is expected to still be True"
    assert project(row).verified is False


@needs_snapshot
def test_production_active_control_publishes_verified_true():
    row = json.loads(SNAPSHOT.read_text(encoding="utf-8"))[str(ACTIVE_CONTROL_ID)]
    assert row["verification_status"] == "active"
    assert project(row).verified is True


@needs_snapshot
def test_no_public_row_contradicts_its_status():
    raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    contradictions = [
        sid
        for sid, row in raw.items()
        if project(row).verification_status != AUTHORITATIVE_VERIFIED_STATUS
        and project(row).verified is True
    ]
    assert contradictions == []


@needs_snapshot
def test_review_classification_is_untouched_by_the_contract():
    """Serialising must not rewrite what is stored."""
    raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for sid in REVIEW_RECORD_IDS:
        assert raw[str(sid)]["verification_status"] == "needs_review"


# ---------------------------------------------------------------------------
# The live API
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    reset_database_connections()
    with TestClient(app) as test_client:
        seed_database()
        yield test_client
    if TEST_DATABASE_PATH.exists():
        TEST_DATABASE_PATH.unlink()


def _set_status(sid: int, status: str) -> None:
    session = get_session_factory()()
    try:
        row = session.get(Scholarship, sid)
        row.verification_status = status
        session.commit()
    finally:
        session.close()


def _first_public_id() -> int:
    session = get_session_factory()()
    try:
        return session.query(Scholarship.id).order_by(Scholarship.id).first()[0]
    finally:
        session.close()


def test_api_detail_never_contradicts_its_status(client):
    sid = _first_public_id()
    for status, expected in (("active", True), ("needs_review", False), ("uncertain", False)):
        _set_status(sid, status)
        response = client.get(f"/scholarships/{sid}")
        assert response.status_code == 200
        body = response.json()
        assert body["verification_status"] == status
        assert body["verified"] is expected, (status, body["verified"])
        assert (body["verified"] is True) == (status == "active")


def test_api_list_never_contradicts_its_status(client):
    sid = _first_public_id()
    _set_status(sid, "needs_review")
    response = client.get("/scholarships?limit=100")
    assert response.status_code == 200
    for item in response.json()["items"]:
        if item["verification_status"] != "active":
            assert item["verified"] is False, item["id"]
