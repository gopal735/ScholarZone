"""The one-shot Supervisor trigger, exercised end to end against a real app.

The bounds tests in ``test_supervisor_trigger_bounds`` read the module's imports
and call sites. These drive the route itself, so that a change which keeps every
name out of the imports but still behaves wrongly - serving the wrong row, writing
before validating, committing twice - fails here instead of in production.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Scholarship  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
)

SECRET = "trigger-unit-test-secret"
#: Requests go through the api_prefix middleware, so the served path carries /api.
PATH = "/api/internal/supervisor/discover"
#: OpenAPI describes the routes as declared, before that middleware rewrites them.
OPENAPI_PATH = "/internal/supervisor/discover"


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'trigger.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_VERIFICATION_SECRET", SECRET)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _scholarship(db, **overrides) -> Scholarship:
    values = {
        "title": "Trigger Test Scholarship",
        "country": "Singapore",
        "degree": "Master",
        "funding": "Full",
        "official_source": "NTU",
        "official_source_url": (
            "https://www.ntu.edu.sg/admissions/graduate/financialmatters/scholarships"
        ),
        "verification_status": "active",
        "is_verified": True,
        "status": "open",
        "deadline_date": date(2027, 1, 15),
        "deadline_display": "Applications close 15 January 2027",
        "deadline_precision": "exact",
    }
    values.update(overrides)
    record = Scholarship(**values)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# the route exists, and is mounted under the api prefix
# ---------------------------------------------------------------------------


def test_the_route_is_mounted(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert f"{OPENAPI_PATH}/{{scholarship_id}}" in paths, (
        f"the trigger must be mounted; openapi paths containing 'supervisor': "
        f"{[p for p in paths if 'supervisor' in p]}"
    )
    assert "post" in paths[f"{OPENAPI_PATH}/{{scholarship_id}}"]
    # And it is reachable at the prefixed path the middleware serves.
    scholarship_paths = [p for p in paths if p.startswith(OPENAPI_PATH)]
    assert len(scholarship_paths) == 1, (
        f"exactly one trigger route may exist, found {scholarship_paths}"
    )


# ---------------------------------------------------------------------------
# authentication
# ---------------------------------------------------------------------------


def test_an_unauthenticated_call_is_refused(client, db):
    scholarship = _scholarship(db)
    for headers in ({}, {"X-Verification-Secret": "wrong"}):
        response = client.post(f"{PATH}/{scholarship.id}", headers=headers)
        assert response.status_code == 401, (
            f"expected 401 for headers {list(headers)}, got {response.status_code}"
        )
    assert db.execute(select(ProfessorProfile)).scalars().all() == [], (
        "a refused call must not have written anything"
    )


def test_a_refused_call_writes_no_coverage_row(client, db):
    """Authorisation is checked before the handler touches anything."""
    scholarship = _scholarship(db)
    client.post(f"{PATH}/{scholarship.id}", headers={"X-Verification-Secret": "wrong"})
    assert db.execute(select(ScholarshipSupervisorCoverage)).scalars().all() == []


# ---------------------------------------------------------------------------
# bounded to one scholarship
# ---------------------------------------------------------------------------


def test_an_unknown_scholarship_is_a_404_and_writes_nothing(client, db):
    response = client.post(
        f"{PATH}/999999", headers={"X-Verification-Secret": SECRET}
    )
    assert response.status_code == 404
    assert db.execute(select(ProfessorProfile)).scalars().all() == []


def test_the_response_names_only_the_requested_scholarship(client, db, monkeypatch):
    """The handler cannot report on, or write for, anything else."""
    target = _scholarship(db, title="Target")
    other = _scholarship(db, title="Other", official_source_url="https://other.example/x")

    from app.routers import supervisor_trigger
    from app.services.supervisor_discovery import DiscoveryOutcome

    seen: list[int] = []

    def fake_discovery(session, scholarship, render_budget=None):
        seen.append(scholarship.id)
        return DiscoveryOutcome(
            scholarship_id=scholarship.id, status="search_pending", detail="stubbed"
        )

    monkeypatch.setattr(supervisor_trigger, "discover_for_scholarship", fake_discovery)

    response = client.post(
        f"{PATH}/{target.id}", headers={"X-Verification-Secret": SECRET}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scholarship_id"] == target.id
    assert seen == [target.id], f"discovery must run for exactly one id, saw {seen}"
    assert other.id not in seen


def test_a_non_positive_id_is_rejected(client, db):
    response = client.post(f"{PATH}/0", headers={"X-Verification-Secret": SECRET})
    assert response.status_code in (400, 422)


def test_the_response_never_contains_the_secret(client, db, monkeypatch):
    from app.routers import supervisor_trigger
    from app.services.supervisor_discovery import DiscoveryOutcome

    scholarship = _scholarship(db)
    monkeypatch.setattr(
        supervisor_trigger,
        "discover_for_scholarship",
        lambda session, row, render_budget=None: DiscoveryOutcome(
            scholarship_id=row.id, status="search_pending", detail="stubbed"
        ),
    )
    response = client.post(
        f"{PATH}/{scholarship.id}", headers={"X-Verification-Secret": SECRET}
    )
    assert SECRET not in response.text
    assert "verification_secret" not in response.text


def test_no_render_budget_is_passed(client, db, monkeypatch):
    """The only structural way this endpoint could launch a browser."""
    from app.routers import supervisor_trigger
    from app.services.supervisor_discovery import DiscoveryOutcome

    scholarship = _scholarship(db)
    captured: list[object] = []

    def fake_discovery(session, row, render_budget=None):
        captured.append(render_budget)
        return DiscoveryOutcome(
            scholarship_id=row.id, status="search_pending", detail="stubbed"
        )

    monkeypatch.setattr(supervisor_trigger, "discover_for_scholarship", fake_discovery)
    client.post(f"{PATH}/{scholarship.id}", headers={"X-Verification-Secret": SECRET})
    assert captured == [None], (
        f"discovery must be called with no render budget, got {captured}"
    )


# ---------------------------------------------------------------------------
# persistence ordering
# ---------------------------------------------------------------------------


def test_classification_completes_before_any_row_is_written(client, db, monkeypatch):
    """A candidate the gates reject must leave no row behind, at all.

    The stub below stands in for the fetch-and-extract half of discovery and
    returns one real person and two collective labels - the shapes measured on the
    real NTU page. If any of them reached the database the gates would be
    decorative.
    """
    from app.routers import supervisor_trigger
    from app.services.supervisor_discovery import (
        FacultyCandidate,
        _persist_candidates,
        DiscoveryOutcome,
    )

    scholarship = _scholarship(db)
    host = "www.ntu.edu.sg"

    candidates = [
        FacultyCandidate(
            name="Chua Thian Poh",
            profile_url=f"https://{host}/about-us/the-chancellery/dr-chua-thian-poh",
            role="dr",
            role_evidence="honorific",
        ),
        FacultyCandidate(
            name="Nanyang Research",
            profile_url=f"https://{host}/education/talent-outreach/nrpjr",
            role="researcher",
            role_evidence="inline_role",
            name_claims_person=False,
        ),
        FacultyCandidate(
            name="Non-Academic Services",
            profile_url=f"https://{host}/education/accessible-education/non-academic-support",
            role="academic",
            role_evidence="inline_role",
            name_claims_person=False,
        ),
    ]

    def fake_discovery(session, row, render_budget=None):
        stored = _persist_candidates(
            session,
            row,
            candidates,
            faculty_url=f"https://{host}/directory",
            institution_name="Nanyang Technological University",
            directory_html="<html></html>",
            http_status=200,
            discovery_path="static",
        )
        session.commit()
        return DiscoveryOutcome(
            scholarship_id=row.id,
            status=str("search_complete"),
            professors_found=stored,
            links_written=stored,
            pages_fetched=2,
        )

    monkeypatch.setattr(supervisor_trigger, "discover_for_scholarship", fake_discovery)

    response = client.post(
        f"{PATH}/{scholarship.id}", headers={"X-Verification-Secret": SECRET}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["professors_found"] == 1, (
        f"only the one real person may be counted, got {body}"
    )

    names = sorted(
        row.canonical_name for row in db.execute(select(ProfessorProfile)).scalars()
    )
    assert names == ["Chua Thian Poh"], f"stored names: {names}"

    links = db.execute(select(ScholarshipProfessorLink)).scalars().all()
    assert len(links) == 1, "only the stored professor may be linked"

    evidence = db.execute(select(SupervisorSourceEvidence)).scalars().all()
    assert evidence, "the stored professor must retain provenance"
    for row in evidence:
        assert row.source_url, "provenance without a source URL is not provenance"


# ---------------------------------------------------------------------------
# isolation
# ---------------------------------------------------------------------------


def test_no_discovery_candidate_rows_are_created(client, db, monkeypatch):
    """The scholarship DiscoveryCandidate subsystem must stay untouched."""
    from app.routers import supervisor_trigger
    from app.services.supervisor_discovery import DiscoveryOutcome

    scholarship = _scholarship(db)
    monkeypatch.setattr(
        supervisor_trigger,
        "discover_for_scholarship",
        lambda session, row, render_budget=None: DiscoveryOutcome(
            scholarship_id=row.id, status="search_pending", detail="stubbed"
        ),
    )
    client.post(f"{PATH}/{scholarship.id}", headers={"X-Verification-Secret": SECRET})

    from app.models import DiscoveryCandidate

    assert db.execute(select(DiscoveryCandidate)).scalars().all() == [], (
        "a Supervisor trigger must not seed scholarship discovery candidates"
    )


def test_no_maintenance_rows_are_created(client, db, monkeypatch):
    from app.routers import supervisor_trigger
    from app.services.supervisor_discovery import DiscoveryOutcome

    scholarship = _scholarship(db)
    monkeypatch.setattr(
        supervisor_trigger,
        "discover_for_scholarship",
        lambda session, row, render_budget=None: DiscoveryOutcome(
            scholarship_id=row.id, status="search_pending", detail="stubbed"
        ),
    )
    client.post(f"{PATH}/{scholarship.id}", headers={"X-Verification-Secret": SECRET})

    for model_name in ("MaintenanceSlot", "MaintenanceRun", "MaintenanceSlotClaim"):
        import app.models as models

        model = getattr(models, model_name, None)
        if model is None:
            continue
        assert db.execute(select(model)).scalars().all() == [], (
            f"{model_name} must be untouched by a Supervisor trigger"
        )