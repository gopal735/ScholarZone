"""Security tests proving the removed internal automation is not exposed.

The verification, discovery, enrichment, image verify/revalidate, supervisor
discovery, maintenance dispatcher, admin verification and admin image review
endpoints were removed as part of abandoning internal automation. Every one of
them must return 404 (not 401/403): the routes themselves are gone rather than
merely re-guarded. Public routes still work.

The deploy workflow must no longer reference the removed guarded endpoints or
the verification secret.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

REMOVED_PATHS = [
    # verification router (/internal)
    "/internal/auth-check",
    "/internal/verify/trigger",
    "/internal/verify/status",
    "/internal/discover/trigger",
    "/internal/discover/next-cycle",
    "/internal/discover/batch-next-cycle",
    "/internal/discover/country/US",
    "/internal/discover/pending",
    "/internal/discover/approve/1",
    "/internal/discover/reject/1",
    "/internal/images/verify",
    "/internal/images/revalidate",
    # enrichment router (/internal/enrich)
    "/internal/enrich/trigger",
    "/internal/enrich/images",
    "/internal/enrich/status",
    # internal maintenance dispatcher (/internal/maintenance)
    "/internal/maintenance/dispatch",
    "/internal/maintenance/status",
    # supervisor discovery trigger (/internal/supervisor)
    "/internal/supervisor/discover/1",
    # admin verification (/admin/verification)
    "/admin/verification/summary",
    "/admin/verification/queue",
    "/admin/verification/scholarships/1",
    "/admin/verification/scholarships/1/decision",
    # admin image review (/admin/images)
    "/admin/images/review-queue",
    "/admin/images/review/1/approve",
    "/admin/images/review/1/reject",
    "/admin/images/review-queue/1/decision",
    # supervisor outreach (/outreach)
    "/outreach/",
    # supervisor email (/supervisor-email)
    "/supervisor-email/templates",
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", REMOVED_PATHS)
def test_removed_endpoint_returns_404(client, path):
    response = client.get(path)
    assert response.status_code == 404, (
        f"{path} must be removed (404), got {response.status_code}"
    )


@pytest.mark.parametrize("path", [
    "/internal/auth-check",
    "/internal/verify/trigger",
    "/internal/images/verify",
    "/admin/verification/summary",
    "/admin/images/review-queue",
    "/outreach/",
])
def test_removed_endpoint_post_returns_404(client, path):
    response = client.post(path)
    assert response.status_code == 404, (
        f"POST {path} must be removed (404), got {response.status_code}"
    )


def test_public_routes_still_work(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200


def test_deploy_workflow_no_longer_references_removed_endpoints():
    assert DEPLOY_WORKFLOW.exists(), f"missing workflow: {DEPLOY_WORKFLOW}"
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert "/internal/auth-check" not in workflow
    assert "/internal/verify/status" not in workflow
    assert "X-Verification-Secret" not in workflow
    assert "SCHOLARZONE_VERIFICATION_SECRET" not in workflow
