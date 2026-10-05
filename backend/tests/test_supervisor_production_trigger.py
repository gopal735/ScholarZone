"""The bounded production trigger: its authentication, its bounds, and its workflow.

This is the test suite for the *entry point*, not for the discovery engine. The
engine's gating is pinned in ``test_supervisor_persistence_boundary.py``; what is
pinned here is that reaching it from production is possible, is authenticated,
and cannot be widened.

Most of this file asserts what is **absent**. That is the honest shape of the
requirement: the capability that matters is the capability that does not exist -
no country discovery, no batch, no caller-supplied URL, no database credential in
the workflow, no way to schedule it. Each absence is asserted so that adding it
later is a test failure rather than a review question.

No production secret is used, referenced or required. The tests set their own
throwaway values through the environment.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

import yaml  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base, Scholarship  # noqa: E402
from app.models_supervisor import ProfessorProfile, ScholarshipProfessorLink  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
WORKFLOWS = REPO / ".github" / "workflows"
PROOF_WORKFLOW = WORKFLOWS / "supervisor-discovery-proof.yml"

TEST_SECRET = "test-only-verification-secret-value"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def scholarship(db):
    row = Scholarship(
        title="MSc Computer Science",
        country="United Kingdom",
        degree="Master",
        funding="Fully Funded",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        benefits=[],
        coverage=[],
        requirements=[],
        documents=[],
        application_method=[],
        official_source="Test University",
        official_source_url="https://uni1.edu/programmes/msc",
        is_verified=True,
        verification_status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def client(db):
    """A TestClient bound to the in-memory database."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def discovery_enabled(monkeypatch):
    """Turn the bounded trigger on for this test only.

    Explicitly separate from the render flag, and the fixture says so: enabling
    discovery here must not enable rendering, which is asserted below.
    """
    from app.core.config import get_settings

    monkeypatch.setenv("SCHOLARZONE_VERIFICATION_SECRET", TEST_SECRET)
    monkeypatch.setenv("SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED", "true")
    # Re-read settings: get_settings is called per request, so nothing else needed.
    assert get_settings().supervisor_discovery_enabled is True


def _auth() -> dict[str, str]:
    return {"X-Verification-Secret": TEST_SECRET}


# ---------------------------------------------------------------------------
# The route exists, is bounded, and is the only one
# ---------------------------------------------------------------------------


class TestTheRouteIsBounded:
    def test_the_route_is_mounted_at_the_documented_path(self):
        from app.main import app

        schema = app.openapi()
        path = "/internal/supervisor/discover/{scholarship_id}"
        assert path in schema["paths"], sorted(schema["paths"])
        methods = schema["paths"][path]
        assert set(methods) == {"post"}, (
            f"the trigger must be POST only; it also exposes {sorted(methods)}"
        )

    def test_it_takes_one_path_parameter_and_no_body(self):
        from app.main import app

        schema = app.openapi()
        operation = schema["paths"]["/internal/supervisor/discover/{scholarship_id}"]["post"]
        parameters = {
            parameter["name"]: parameter
            for parameter in operation.get("parameters", [])
        }
        # Exactly two inputs: the target in the path, and the credential in a
        # header. Nothing else - no query parameter, no body.
        assert set(parameters) == {"scholarship_id", "X-Verification-Secret"}
        assert parameters["scholarship_id"]["required"] is True
        assert parameters["scholarship_id"]["in"] == "path"
        # The positive-integer bound is in the schema itself, so an out-of-range id
        # is rejected before a handler runs rather than by a check inside one.
        assert parameters["scholarship_id"]["schema"]["minimum"] == 1
        assert parameters["scholarship_id"]["schema"]["type"] == "integer"
        assert parameters["X-Verification-Secret"]["in"] == "header"
        # No request body schema at all: there is nowhere to put a URL, a country
        # or a list.
        assert "requestBody" not in operation, (
            "the trigger must not accept a body; a body is where a source URL "
            "would arrive"
        )

    def test_no_supervisor_route_can_broaden_the_scope(self):
        """The whole internal Supervisor surface is exactly one operation."""
        from app.main import app

        schema = app.openapi()
        supervisor_paths = [
            path
            for path in schema["paths"]
            if path.startswith("/internal/supervisor")
        ]
        assert supervisor_paths == ["/internal/supervisor/discover/{scholarship_id}"]

    def test_the_router_does_not_import_maintenance_or_scheduler_code(self):
        """The trigger cannot dispatch maintenance or the verification cron.

        Checked as an import closure rather than by reading the body, because an
        import is how such a coupling would actually be introduced.
        """
        import ast

        source = (BACKEND / "app" / "routers" / "supervisor_internal.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
                for alias in node.names:
                    imported.append(f"{node.module}.{alias.name}")
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)

        forbidden = (
            "maintenance_dispatch",
            "scholarzone_maintenance",
            "scheduler_engine",
            "scheduler_v2",
            "verification",
            "discovery_engine",
            "supervisor_render",
        )
        for name in imported:
            for needle in forbidden:
                assert needle not in name, (
                    f"the Supervisor trigger imports {name!r}; it must stay separate "
                    "from maintenance, the scheduler and verification"
                )

    def test_it_does_not_enable_rendering(self):
        """Calling the trigger must not make the browser available."""
        body = _router_text()
        # It never imports the renderer and never builds a budget - so the renderer
        # reports itself unavailable and a client-side directory stays
        # SOURCE_REQUIRES_RENDERING rather than being quietly rendered.
        assert "supervisor_render" not in body
        assert "RenderBudget" not in body
        assert "render_budget" not in body
        # And it changes no environment setting, so it cannot switch the render
        # flag on as a side effect. (The flag's *name* appears once, in the 503
        # message, to tell an operator which two settings they are confusing.)
        assert "os.environ" not in body and "getenv" not in body and "setenv" not in body

    def test_it_does_not_reach_the_scholarship_discovery_subsystem(self):
        """It must not seed DiscoveryCandidate rows for new scholarships."""
        body = _router_text()
        for needle in ("DiscoveryCandidate", "run_discovery_round", "run_discovery_batch"):
            assert needle not in body


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestAuthentication:
    def test_a_missing_secret_is_refused(self, client, db, scholarship, discovery_enabled):
        response = client.post(f"/internal/supervisor/discover/{scholarship.id}")
        assert response.status_code == 401

    def test_a_wrong_secret_is_refused(self, client, db, scholarship, discovery_enabled):
        response = client.post(
            f"/internal/supervisor/discover/{scholarship.id}",
            headers={"X-Verification-Secret": "not-the-secret"},
        )
        assert response.status_code == 401

    def test_a_secret_of_the_wrong_length_is_refused(self, client, db, scholarship, discovery_enabled):
        for candidate in (TEST_SECRET[:-1], TEST_SECRET + "x", ""):
            response = client.post(
                f"/internal/supervisor/discover/{scholarship.id}",
                headers={"X-Verification-Secret": candidate},
            )
            assert response.status_code == 401, f"accepted a {len(candidate)}-char secret"

    def test_an_unconfigured_deployment_admits_nobody(self, client, db, scholarship, monkeypatch):
        """Fail closed. No secret configured means no caller, not any caller."""
        from app.core.config import get_settings

        monkeypatch.setenv("SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED", "true")
        # The variable is simply absent, which is how a deployment that forgets to
        # provision it looks.
        monkeypatch.delenv("SCHOLARZONE_VERIFICATION_SECRET", raising=False)
        assert get_settings().verification_secret is None

        response = client.post(
            f"/internal/supervisor/discover/{scholarship.id}",
            headers=_auth(),
        )
        assert response.status_code == 401

    def test_the_secret_is_compared_in_constant_time(self):
        source = (BACKEND / "app" / "routers" / "supervisor_internal.py").read_text(
            encoding="utf-8"
        )
        assert "compare_digest" in source, (
            "a plain == leaks length and prefix through the rejection's timing"
        )
        assert not re.search(r"secret\s*==\s*x_verification_secret", source)
        # The secret is a header, never a query parameter, so it cannot end up in
        # an access log or a browser history.
        assert "Query(" not in source


# ---------------------------------------------------------------------------
# The feature flag
# ---------------------------------------------------------------------------


class TestTheFeatureFlag:
    def test_it_defaults_to_off(self, monkeypatch):
        from app.core.config import Settings, get_settings

        monkeypatch.delenv("SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED", raising=False)
        assert get_settings().supervisor_discovery_enabled is False
        # And the dataclass default, which is what a frozen Settings falls back to.
        assert "supervisor_discovery_enabled: bool = False" in (
            BACKEND / "app" / "core" / "config.py"
        ).read_text(encoding="utf-8")

    def test_a_valid_secret_is_still_refused_while_it_is_off(self, client, db, scholarship, monkeypatch):
        """Authentication and capability are two separate conditions."""
        from app.core.config import get_settings

        monkeypatch.setenv("SCHOLARZONE_VERIFICATION_SECRET", TEST_SECRET)
        monkeypatch.delenv("SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED", raising=False)
        assert get_settings().supervisor_discovery_enabled is False

        response = client.post(
            f"/internal/supervisor/discover/{scholarship.id}",
            headers=_auth(),
        )
        assert response.status_code == 503
        assert "disabled" in response.json()["detail"].lower()

    def test_it_is_a_different_switch_from_rendering(self):
        """The two must not be confusable, by name or by effect."""
        from app.services import supervisor_render

        discovery_flag = "SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED"
        assert discovery_flag != supervisor_render.RENDER_ENABLED_ENV

        config = (BACKEND / "app" / "core" / "config.py").read_text(encoding="utf-8")
        # Application configuration owns the discovery flag...
        assert f'os.getenv("{discovery_flag}")' in config
        # ...and must not read the render flag. That one belongs to
        # supervisor_render, so routing it through Settings here would be the first
        # step towards the two collapsing into one switch.
        assert f'os.getenv("{supervisor_render.RENDER_ENABLED_ENV}")' not in config
        assert f"os.environ.get({supervisor_render.RENDER_ENABLED_ENV}" not in config


# ---------------------------------------------------------------------------
# Target validation
# ---------------------------------------------------------------------------


class TestTargetValidation:
    def test_an_unknown_scholarship_is_a_404(self, client, db, discovery_enabled):
        response = client.post("/internal/supervisor/discover/999999", headers=_auth())
        assert response.status_code == 404

    @pytest.mark.parametrize("target", ["0", "-1", "abc", "1,2", "1-5", "1%20OR%201=1"])
    def test_a_non_positive_or_non_integer_target_is_refused(self, client, db, scholarship, discovery_enabled, target):
        response = client.post(f"/internal/supervisor/discover/{target}", headers=_auth())
        assert response.status_code == 422, (
            f"{target!r} should not resolve to a scholarship"
        )

    @pytest.mark.parametrize("target", ["../1", "1/../2", "%2e%2e%2f1"])
    def test_a_traversal_target_never_reaches_a_scholarship(self, client, db, scholarship, discovery_enabled, target):
        """Path traversal must not resolve to a different scholarship.

        Either the router rejects the shape or the transport normalises the path
        into something that matches no route. Both are acceptable; what matters is
        that neither reads or writes a scholarship.
        """
        response = client.post(f"/internal/supervisor/discover/{target}", headers=_auth())
        assert response.status_code in (404, 422)
        assert "Grace Hopper" not in response.text

    def test_a_list_of_targets_cannot_be_passed(self, client, db, scholarship, discovery_enabled):
        """There is no list form, so a comma-joined id is not a batch request."""
        response = client.post(f"/internal/supervisor/discover/{scholarship.id},2", headers=_auth())
        assert response.status_code == 422

    def test_a_country_cannot_be_a_target(self, client, db, discovery_enabled):
        response = client.post("/internal/supervisor/discover/united-kingdom", headers=_auth())
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# The bounded run itself
# ---------------------------------------------------------------------------


class TestTheBoundedRun:
    def test_it_discovery_one_scholarship_and_reports_both_sides(self, client, db, scholarship, discovery_enabled, monkeypatch):
        from app.services import supervisor_discovery as worker

        programme = """
            <html><body><a href="/people/faculty">Our Faculty</a></body></html>
        """
        directory = """
            <html><body><h1>Faculty</h1><ul>
              <li><a href="/people/grace-hopper">Professor Grace Hopper</a></li>
              <li><a href="/people/apply-now">Apply Now</a></li>
            </ul></body></html>
        """
        profile = "<html><body><h1>Professor Grace Hopper</h1><p>Professor of Computing</p></body></html>"

        def fake_fetch(url: str):
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            body = {
                "https://uni1.edu/programmes/msc": programme,
                "https://uni1.edu/people/faculty": directory,
                "https://uni1.edu/people/grace-hopper": profile,
            }.get(url.split("#")[0])
            if body is None:
                return None
            return OfficialSourceFetchResult(
                success=True,
                status_code=200,
                final_url=url,
                content=body,
                content_type="text/html",
            )

        monkeypatch.setattr(worker, "polite_fetch", fake_fetch)

        response = client.post(f"/internal/supervisor/discover/{scholarship.id}", headers=_auth())
        assert response.status_code == 200, response.text
        report = response.json()

        assert report["scholarship_id"] == scholarship.id
        assert report["professors_written"] == 1
        assert report["approved"] == 1
        # "Apply Now" reaches the gates and is refused on role evidence, so the
        # run reports both sides rather than only its successes.
        assert report["rejected"] == 1
        assert report["rejected_by_gate"] == {"role_evidence": 1}
        assert sum(report["rejected_by_gate"].values()) == report["rejected"]
        assert report["render_requested"] is False
        assert report["status"] in ("verified_supervisors", "no_verified_supervisor_found")

        # Exactly one professor was written, and it is the valid one.
        names = db.execute(select(ProfessorProfile.canonical_name)).scalars().all()
        assert list(names) == ["Grace Hopper"]
        assert db.execute(select(func.count(ScholarshipProfessorLink.id))).scalar_one() == 1

    def test_it_does_not_touch_any_other_scholarship(self, client, db, scholarship, discovery_enabled, monkeypatch):
        from app.services import supervisor_discovery as worker

        other = Scholarship(
            title="BSc Mathematics",
            country="United Kingdom",
            degree="Bachelor",
            funding="Varies",
            status="open",
            deadline_date=date(2027, 6, 30),
            deadline_precision="exact",
            eligibility=[],
            benefits=[],
            coverage=[],
            requirements=[],
            documents=[],
            application_method=[],
            official_source="Other University",
            official_source_url="https://uni2.edu/programmes/bsc",
            is_verified=True,
            verification_status="active",
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        monkeypatch.setattr(worker, "polite_fetch", lambda url: None)

        response = client.post(f"/internal/supervisor/discover/{scholarship.id}", headers=_auth())
        assert response.status_code == 200

        from app.models_supervisor import ScholarshipSupervisorCoverage

        covered = set(
            db.execute(
                select(ScholarshipSupervisorCoverage.scholarship_id)
            ).scalars().all()
        )
        assert covered == {scholarship.id}, (
            f"coverage was written for {covered}, not only the target"
        )

    def test_the_report_never_echoes_the_secret(self, client, db, scholarship, discovery_enabled, monkeypatch):
        from app.services import supervisor_discovery as worker

        monkeypatch.setattr(worker, "polite_fetch", lambda url: None)
        response = client.post(f"/internal/supervisor/discover/{scholarship.id}", headers=_auth())
        assert TEST_SECRET not in response.text


# ---------------------------------------------------------------------------
# The workflow
# ---------------------------------------------------------------------------


def _workflow_text() -> str:
    return PROOF_WORKFLOW.read_text(encoding="utf-8")


def _code_only(text: str) -> str:
    """Strip whole-line YAML comments.

    Several assertions below look for the *absence* of a string. This module's
    prose deliberately names the things it refuses to do - "not a batch", "not
    country-wide" - because that documentation is the point. Checking the raw file
    would fail on the explanation rather than on the behaviour, so the comments
    are removed first and only executable content is judged.

    Mirrors ``_code_only`` in ``test_autonomous_maintenance.py``.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _router_text() -> str:
    """The router's source with its module docstring removed, for the same reason."""
    source = (BACKEND / "app" / "routers" / "supervisor_internal.py").read_text(
        encoding="utf-8"
    )
    _, _, body = source.partition('"""')
    _, _, body = body.partition('"""')
    return body


def _workflow() -> dict:
    return yaml.safe_load(_workflow_text())


def _triggers() -> dict:
    document = _workflow()
    # PyYAML parses the bare key `on` as the boolean True under YAML 1.1.
    return document.get("on", document.get(True))


class TestTheWorkflowIsDispatchOnly:
    def test_the_file_exists(self):
        assert PROOF_WORKFLOW.exists()

    def test_workflow_dispatch_is_the_only_trigger(self):
        assert set(_triggers()) == {"workflow_dispatch"}

    def test_there_is_no_schedule_and_no_matrix(self):
        code = _code_only(_workflow_text())
        assert "schedule:" not in code
        assert "cron:" not in code
        for trigger in ("push:", "pull_request:", "repository_dispatch:", "schedule:"):
            assert trigger not in code
        assert "strategy:" not in code, "a matrix would allow many targets per run"
        assert "matrix" not in code

    def test_it_takes_exactly_one_input_and_validates_it(self):
        inputs = _triggers()["workflow_dispatch"]["inputs"]
        assert list(inputs) == ["scholarship_id"]
        assert inputs["scholarship_id"]["required"] is True

        code = _code_only(_workflow_text())
        # Digits-only validation, so a list, a range, a URL or a shell fragment
        # cannot be smuggled through the one input that exists.
        assert "'^[0-9]+$'" in code
        assert "grep -Eq" in code

    def test_it_calls_only_the_bounded_endpoint(self):
        """The workflow makes exactly one request, to exactly one route.

        Asserted over the URLs actually built rather than over prose: the error
        messages legitimately *name* the things that are unavailable, and a
        substring ban would fail on the explanation.
        """
        code = _code_only(_workflow_text())
        paths = set(re.findall(r"/internal/[A-Za-z0-9_/{}$-]*", code))
        assert paths == {
            "/internal/supervisor/discover/$TARGET_SCHOLARSHIP_ID",
        }, f"the proof workflow addresses {sorted(paths)}"
        assert code.count("curl ") == 1, "one run, one request"
        # One host, and it is a variable: no literal hostname is embedded
        # anywhere, so the workflow cannot be pointed somewhere else by an edit
        # that hardcodes a deployment.
        assert "$SCHOLARZONE_API_URL" in code
        assert "https://" not in code, "the host must come from the variable, not a literal"

    def test_it_has_concurrency_protection(self):
        concurrency = _workflow()["concurrency"]
        assert concurrency["group"] == "supervisor-discovery-proof"
        # Queued rather than cancelled: cancelling a proof in flight destroys the
        # evidence it was run to collect.
        assert concurrency["cancel-in-progress"] is False

    def test_permissions_are_minimised_and_a_timeout_is_set(self):
        assert _workflow()["permissions"] == {"contents": "read"}
        assert "write-all" not in _code_only(_workflow_text())
        assert _workflow()["jobs"]["prove"]["timeout-minutes"]


class TestTheWorkflowCannotReachTheDatabase:
    def test_it_is_never_given_the_database_url(self):
        assert "SCHOLARZONE_DATABASE_URL" not in _code_only(_workflow_text()), (
            "the proof must go through the authenticated endpoint, not the database"
        )

    def test_it_takes_only_the_two_inputs_and_a_target(self):
        env = _workflow()["jobs"]["prove"]["env"]
        assert set(env) == {
            "SCHOLARZONE_API_URL",
            "SCHOLARZONE_VERIFICATION_SECRET",
            "TARGET_SCHOLARSHIP_ID",
        }


class TestTheWorkflowNeverPrintsTheSecret:
    def test_the_secret_comes_from_the_repository_secret_at_runtime(self):
        env = _workflow()["jobs"]["prove"]["env"]
        assert env["SCHOLARZONE_VERIFICATION_SECRET"] == (
            "${{ secrets.SCHOLARZONE_VERIFICATION_SECRET }}"
        )

    def test_the_secret_is_not_interpolated_into_a_command_line(self):
        """Job-level ``env:`` is the only place the secret is referenced.

        A ``${{ secrets.* }}`` expansion inside a ``run:`` block would be
        rendered into the script text itself, where it can appear in a trace, an
        error message or a log line. Bound to the environment instead, the value
        reaches curl as ``$SCHOLARZONE_VERIFICATION_SECRET`` and is never rendered.
        """
        text = _workflow_text()
        for step in _workflow()["jobs"]["prove"]["steps"]:
            if "run" not in step:
                continue
            assert "${{" not in step["run"], (
                f"step {step.get('name')!r} interpolates an expression into a "
                "command line"
            )
        assert "${{ secrets." in text

    def test_shell_tracing_is_not_enabled(self):
        assert "set -x" not in _code_only(_workflow_text()), (
            "shell tracing would echo the expanded header"
        )

    def test_no_command_prints_the_secret_value(self):
        code = _code_only(_workflow_text())
        for echo in re.findall(r"echo\s+([^\n]+)", code):
            assert '"$SCHOLARZONE_VERIFICATION_SECRET"' not in echo
            assert "${SCHOLARZONE_VERIFICATION_SECRET}" not in echo

    def test_the_request_header_is_never_echoed(self):
        code = _code_only(_workflow_text())
        assert not re.search(r"echo[^\n]*X-(Admin|Verification)-Secret:\s*\$", code)

    def test_curl_does_not_echo_the_request(self):
        code = _code_only(_workflow_text())
        assert "--value" not in code
        assert not re.search(r"curl[^\n]*\s-v\b", code)

    def test_failure_is_loud_and_non_zero(self):
        code = _code_only(_workflow_text())
        assert "set -euo pipefail" in code
        # A non-200 is an explicit failure, not a warning.
        assert 'if [ "$HTTP_CODE" != "200" ]; then' in code
        assert code.count("exit 1") >= 3


class TestTheWorkflowIsHostAgnostic:
    def test_the_host_comes_from_a_repository_variable_not_a_literal(self):
        env = _workflow()["jobs"]["prove"]["env"]
        assert env["SCHOLARZONE_API_URL"] == "${{ vars.SCHOLARZONE_API_URL }}"
        code = _code_only(_workflow_text())
        for forbidden in ("snapdeploy", "containers.snapdeploy", "render.com"):
            assert forbidden not in code

    def test_an_unset_host_fails_closed(self):
        assert 'if [ -z "$SCHOLARZONE_API_URL" ]; then' in _code_only(_workflow_text())
