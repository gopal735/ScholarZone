"""Tests for GET /internal/auth-check, the deployment gate's credential proof.

The deployment workflow used to send X-Verification-Secret to two endpoints that
never read the header, so the gate passed no matter what the secret contained.
These tests pin the replacement: a read-only endpoint that actually rejects a
wrong secret, and the workflow contract that depends on it.
"""

from __future__ import annotations

import inspect
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.database import init_database, reset_database_connections
from app.main import app
from app.models import Base, Scholarship

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

SECRET = "test-verification-secret"
AUTH_PATH = "/api/internal/auth-check"


def _make_test_db_path() -> Path:
    return Path(tempfile.gettempdir()) / f"scholarzone-test-auth-check-{uuid4().hex}.db"


@pytest.fixture(scope="module")
def test_db_path():
    return _make_test_db_path()


@pytest.fixture(scope="module")
def client(test_db_path):
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_VERIFICATION_SECRET"] = SECRET
    reset_database_connections()
    init_database()
    with TestClient(app) as c:
        c.__enter__()
        yield c
        c.__exit__(None, None, None)
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def session(test_db_path):
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    os.environ["SCHOLARZONE_VERIFICATION_SECRET"] = SECRET
    engine = create_engine(f"sqlite:///{test_db_path.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    engine.dispose()


def _make_scholarship(db) -> int:
    row = Scholarship(
        title=f"Auth Check Probe {uuid4().hex}",
        country="Testland",
        degree="Master",
        funding="Fully Funded",
        official_source_url=f"https://example.com/program/{uuid4().hex}",
    )
    db.add(row)
    db.commit()
    return row.id


class TestAuthentication:
    def test_correct_secret_returns_200(self, client):
        response = client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET})
        assert response.status_code == 200

    def test_missing_secret_returns_401(self, client):
        assert client.get(AUTH_PATH).status_code == 401

    def test_wrong_secret_returns_401(self, client):
        response = client.get(AUTH_PATH, headers={"X-Verification-Secret": "wrong"})
        assert response.status_code == 401

    def test_empty_secret_returns_401(self, client):
        response = client.get(AUTH_PATH, headers={"X-Verification-Secret": ""})
        assert response.status_code == 401

    def test_prefix_of_real_secret_returns_401(self, client):
        """A truncated secret must not pass, or the gate would accept a partial match."""
        response = client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET[:-1]})
        assert response.status_code == 401

    def test_secret_with_trailing_whitespace_returns_401(self, client):
        """No normalisation: the stored bytes are the only bytes accepted."""
        response = client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET + "\n"})
        assert response.status_code == 401

    def test_unconfigured_deployment_admits_nobody(self, client):
        with patch("app.routers.verification.get_settings") as mocked:
            mocked.return_value.verification_secret = None
            response = client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET})
        assert response.status_code == 401


class TestNoSecretExposure:
    def test_response_does_not_contain_the_secret(self, client):
        response = client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET})
        assert SECRET not in response.text

    def test_rejection_does_not_echo_the_secret(self, client):
        response = client.get(AUTH_PATH, headers={"X-Verification-Secret": "wrong-secret-value"})
        assert response.status_code == 401
        assert "wrong-secret-value" not in response.text

    def test_success_payload_is_minimal_and_non_sensitive(self, client):
        payload = client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET}).json()
        assert payload == {"status": "ok", "authenticated": True}

    def test_payload_carries_no_scholarship_data(self, client):
        body = client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET}).text.lower()
        for leak in ("scholarship", "title", "country", "deadline", "verified"):
            assert leak not in body


class TestReadOnly:
    def test_declares_no_database_dependency(self):
        """A dependency on a session would let the gate touch the database."""
        from app.routers.verification import auth_check

        signature = inspect.signature(auth_check)
        assert list(signature.parameters) == ["x_verification_secret"]

    def test_declares_no_scheduler_or_mutation_side_effect(self):
        """Bytecode-level check: the handler references no data or scheduler symbol.

        Prose in the docstring is ignored on purpose - only names the compiled
        function actually resolves can mutate state or start work.
        """
        from app.routers.verification import auth_check

        referenced = set(auth_check.__code__.co_names) | set(auth_check.__code__.co_varnames)
        forbidden = {
            "run_verification_round",
            "run_discovery_round",
            "get_db",
            "get_session_factory",
            "session",
            "db",
            "commit",
            "execute",
            "delete",
            "update",
        }
        assert not (referenced & forbidden), (
            f"auth-check must not touch data or start work: {referenced & forbidden}"
        )

    def test_repeated_calls_do_not_change_row_count(self, client, session):
        _make_scholarship(session)
        before = session.execute(select(func.count()).select_from(Scholarship)).scalar_one()
        for _ in range(5):
            client.get(AUTH_PATH, headers={"X-Verification-Secret": SECRET})
        session.expire_all()
        after = session.execute(select(func.count()).select_from(Scholarship)).scalar_one()
        assert before == after

    def test_other_http_methods_are_not_routed(self, client):
        for method in ("post", "put", "patch", "delete"):
            response = getattr(client, method)(AUTH_PATH,
                                               headers={"X-Verification-Secret": SECRET})
            assert response.status_code == 405


class TestDeployWorkflowUsesGuardedEndpoint:
    @pytest.fixture(scope="class")
    def workflow(self) -> str:
        assert DEPLOY_WORKFLOW.exists(), f"missing workflow: {DEPLOY_WORKFLOW}"
        return DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    def test_calls_the_guarded_auth_check_endpoint(self, workflow):
        assert "/internal/auth-check" in workflow

    def test_sends_the_secret_to_the_guarded_endpoint(self, workflow):
        header_line = re.search(
            r'-H "X-Verification-Secret: \$SCHOLARZONE_VERIFICATION_SECRET" \\\s*\n\s*'
            r'"\$SCHOLARZONE_API_URL/internal/auth-check"',
            workflow,
        )
        assert header_line, "the secret must be sent to the guarded endpoint"

    def test_fails_the_job_when_the_guarded_endpoint_rejects(self, workflow):
        guard = workflow.split("Validate the verification secret", 1)[1]
        guard = guard.split("- name:", 1)[0]
        assert '"$HTTP_CODE" != "200"' in guard
        assert "exit 1" in guard

    def test_never_presents_unauthenticated_endpoints_as_secret_proof(self, workflow):
        for unguarded in ("/scholarships/stats", "/internal/verify/status"):
            pattern = rf'-H "X-Verification-Secret:[^"]*"\s*\\\s*\n\s*"\$SCHOLARZONE_API_URL{re.escape(unguarded)}"'
            assert not re.search(pattern, workflow), (
                f"{unguarded} does not validate the header and must not be used as proof"
            )

    def test_does_not_print_the_secret_value(self, workflow):
        assert "--value" not in workflow
        assert "-v " not in workflow
        for echo in re.findall(r"echo\s+([^\n]+)", workflow):
            # Naming the variable in an error message is required for diagnosis.
            # What must never appear is the shell *expansion* of its value.
            assert '"$SCHOLARZONE_VERIFICATION_SECRET"' not in echo
            assert "${SCHOLARZONE_VERIFICATION_SECRET}" not in echo

    def test_never_echoes_the_request_header(self, workflow):
        assert not re.search(r'echo[^\n]*X-(Admin|Verification)-Secret:\s*\$', workflow)
