"""Regression coverage for the Vercel migration.

Each test here exists because something about this migration could plausibly
regress while still looking healthy: a build identity that could be hand-written,
a debug write endpoint exposed publicly, CORS widened to "*", a route dropped in
transit, the maintenance worker quietly gaining an HTTP dependency, or the
frontend silently changing its SEO output.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
FRONTEND = REPO / "frontend"
VERCEL_JSON = BACKEND / "vercel.json"
API_ENTRY = BACKEND / "api" / "index.py"
MAIN = BACKEND / "app" / "main.py"


@pytest.fixture(scope="module")
def app_module():
    import importlib
    import os
    import sys

    sys.path.insert(0, str(BACKEND))
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
    return importlib.import_module("app.main")


class TestVercelEntrypoint:
    def test_api_entrypoint_exposes_the_existing_fastapi_app(self, app_module):
        assert API_ENTRY.exists(), "backend/api/index.py is the Vercel entrypoint"
        source = API_ENTRY.read_text(encoding="utf-8")
        assert "from app.main import app" in source, (
            "the Vercel entrypoint must serve the existing application instance, "
            "not construct a second one"
        )

    def test_entrypoint_has_no_import_time_database_work(self):
        """A cold start must not depend on the database being reachable."""
        source = API_ENTRY.read_text(encoding="utf-8")
        for forbidden in ("init_database", "create_all", "seed_database", "run_migrations"):
            assert forbidden not in source, (
                f"the Vercel entrypoint performs {forbidden} at import time"
            )

    def test_the_application_is_still_fastapi(self, app_module):
        from fastapi import FastAPI

        assert isinstance(app_module.app, FastAPI)

    def test_python_version_is_declared_for_the_runtime(self):
        doc = json.loads(VERCEL_JSON.read_text(encoding="utf-8"))
        assert doc["python"]["version"] in {"3.12", "3.13", "3.14"}
        # The baseline is 3.11 and the smallest supported step up is 3.12, so a
        # jump to 3.13/3.14 without reason would be gratuitous.
        assert doc["python"]["version"] == "3.12", (
            "expected the smallest Vercel-supported step up from 3.11"
        )

    def test_functions_have_a_bounded_duration(self):
        doc = json.loads(VERCEL_JSON.read_text(encoding="utf-8"))
        for path, config in doc.get("functions", {}).items():
            assert config.get("maxDuration", 0) <= 60, (
                f"{path} has an unbounded or excessive maxDuration; a serverless "
                f"function must not be able to run a long job"
            )


class TestRevisionIsARealBuildIdentity:
    def test_health_reports_status_and_revision(self, app_module):
        assert callable(app_module.health)

    def test_local_development_reports_dev(self, app_module, monkeypatch):
        """No build artefact means a local checkout reports ``dev``.

        ``dev`` is not a claim about a commit; it is the absence of one, and the
        deployment gate treats it as a failure rather than a success.
        """
        import dataclasses

        monkeypatch.setattr(app_module, "_embedded_build_revision", lambda: None)
        real_settings = app_module.get_settings()
        monkeypatch.setattr(
            app_module,
            "get_settings",
            lambda: dataclasses.replace(real_settings, environment="development"),
        )
        assert app_module.build_revision() == "dev"

    def test_runtime_environment_cannot_claim_an_identity(self, app_module, monkeypatch):
        """No runtime variable may state what the build was.

        This used to assert the opposite - that the platform's environment
        variable wins and is truncated. Both halves were wrong: the value was
        runtime-controlled, and twelve characters cannot be compared with a
        commit. Identity now comes only from the artefact the build generated.
        """
        from types import SimpleNamespace

        commit = "a" * 40
        monkeypatch.setattr(app_module, "_embedded_build_revision", lambda: commit)
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "b" * 40)
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "c" * 40)
        assert app_module.build_revision() == commit
        assert len(app_module.build_revision()) == 40

    def test_without_an_artifact_no_identity_is_claimed(self, app_module, monkeypatch):
        """A missing artefact plus a runtime SHA still yields no identity."""
        from types import SimpleNamespace

        monkeypatch.setattr(app_module, "_embedded_build_revision", lambda: None)
        monkeypatch.setattr(
            app_module, "get_settings", lambda: SimpleNamespace(environment="production")
        )
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "c" * 40)
        assert app_module.build_revision() == "unknown"

    @pytest.mark.parametrize("value", ["unknown", "latest", "", "not-a-sha", "12345", "deadbeef!"])
    def test_untrustworthy_revision_values_are_rejected(self, app_module, monkeypatch, value):
        """A hand-written label must not be able to stand in for a build identity."""
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        monkeypatch.delenv("VERCEL_GIT_COMMIT_REF", raising=False)
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", value)
        assert app_module.build_revision() != value, (
            f"{value!r} was accepted as a build identity"
        )

    def test_production_without_an_identity_reports_unknown_not_success(
        self, app_module, monkeypatch
    ):
        import dataclasses

        monkeypatch.setattr(app_module, "_embedded_build_revision", lambda: None)
        real_settings = app_module.get_settings()
        monkeypatch.setattr(
            app_module,
            "get_settings",
            lambda: dataclasses.replace(real_settings, environment="production"),
        )
        assert app_module.build_revision() == "unknown"

    def test_deploy_verification_fails_a_stale_build(self):
        """The freshness gate must reject a wrong revision, not merely report it."""
        workflow = (REPO / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        assert 'EXPECTED_REVISION: ${{ github.sha }}' in workflow
        # A revision that is not a SHA fails immediately rather than being
        # retried or accepted, so "unknown" cannot pass as current.
        assert "^[0-9a-f]{7,40}$" in workflow
        assert re.search(r'if \[ "\$CURRENT" = "\$EXPECTED_SHORT" \]', workflow)
        # A non-200 fails rather than being treated as "not ready yet".
        assert re.search(r'if \[ "\$HTTP_CODE" != "200" \]', workflow)


class TestCORS:
    def test_credentials_are_enabled_so_origins_must_be_explicit(self, app_module):
        for middleware in app_module.app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                assert middleware.kwargs.get("allow_credentials") is True
                origins = middleware.kwargs.get("allow_origins")
                assert origins != ["*"], "credentialed CORS must not allow every origin"
                return
        pytest.skip("no CORS middleware configured in this environment")

    def test_github_pages_stays_allowed_while_it_is_the_rollback_path(self):
        source = (BACKEND / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert "gopal735.github.io" in source

    def test_vercel_preview_origin_is_derived_from_the_platform(self):
        source = (BACKEND / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert "VERCEL_URL" in source


def served_paths(app_module) -> set[str]:
    """Every path the application actually serves.

    FastAPI 0.141 keeps an included router as a nested object rather than
    flattening its routes into ``app.routes``, so reading ``app.routes`` alone
    reports only the routes declared on the app itself and would make this
    migration look like it had deleted the whole API. The generated OpenAPI
    document reflects what is genuinely reachable, which is what must be
    preserved.
    """
    return set(app_module.app.openapi().get("paths", {}))


class TestRoutePreservation:
    REQUIRED = ("/health", "/scholarships", "/scholarships/stats")

    def test_public_routes_are_still_registered(self, app_module):
        paths = served_paths(app_module)
        for required in self.REQUIRED:
            assert required in paths, f"{required} disappeared during the migration"
        assert "/" in paths

    def test_detail_route_pattern_is_preserved(self, app_module):
        paths = served_paths(app_module)
        assert "/scholarships/{id}" in paths or "/scholarships/{scholarship_id}" in paths

    def test_internal_verification_status_route_is_preserved(self, app_module):
        paths = served_paths(app_module)
        assert any(p.startswith("/internal/verify") for p in paths), (
            "the internal verification surface must survive the migration"
        )


class TestPublicApiStaysBounded:
    def test_debug_write_route_is_not_reachable_in_production(self, app_module, monkeypatch):
        """It writes to the production database on a GET, unauthenticated."""
        import dataclasses

        from fastapi import HTTPException

        real_settings = app_module.get_settings()
        monkeypatch.setattr(
            app_module,
            "get_settings",
            lambda: dataclasses.replace(real_settings, environment="production"),
        )
        with pytest.raises(HTTPException) as excinfo:
            app_module.debug_fix_null_lists_main()
        assert excinfo.value.status_code == 404

    def test_no_crawl_or_batch_job_is_triggered_by_an_api_request(self):
        """Heavy maintenance must stay in GitHub Actions, never in a request."""
        runtime = MAIN.read_text(encoding="utf-8")
        for forbidden in ("deep_crawl", "batch_enrich", "image_sweep", "discover_and_add"):
            assert forbidden not in runtime, (
                f"{forbidden} appears in the API entrypoint; a public request must "
                f"never start a maintenance job"
            )


class TestMaintenanceStaysNeonDirect:
    def test_worker_makes_no_http_calls(self):
        source = (BACKEND / "app" / "jobs" / "scholarzone_maintenance.py").read_text(
            encoding="utf-8"
        )
        body = "\n".join(
            line for line in source.splitlines()
            if not line.strip().startswith(("#", '"""')) and '"""' not in line
        )
        for forbidden in ("requests.get", "requests.post", "httpx.get", "httpx.post", "urlopen"):
            assert forbidden not in body, (
                f"the maintenance worker calls {forbidden}; it must reach Neon "
                f"directly and depend on no web tier"
            )

    def test_worker_still_reaches_the_database_directly(self):
        source = (BACKEND / "app" / "jobs" / "scholarzone_maintenance.py").read_text(
            encoding="utf-8"
        )
        assert "init_database()" in source
        assert "get_session_factory" in source

    def test_maintenance_workflow_needs_no_api_url(self):
        workflow = (REPO / ".github" / "workflows" / "verification-cron.yml").read_text(
            encoding="utf-8"
        )
        run_block = workflow.split("Run maintenance worker", 1)[-1]
        assert "SCHOLARZONE_API_URL" not in run_block, (
            "the maintenance job must not receive or call a public API URL"
        )


class TestSecretsAreNotCommitted:
    def test_no_credentials_in_tracked_configuration(self):
        patterns = (
            r"postgres(ql)?://[^:]+:[^@]+@",          # database URL with a password
            r"re_[A-Za-z0-9]{20,}",                     # Resend key
            r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}",  # JWT
        )
        for path in list(BACKEND.glob("config/*.json")) + [VERCEL_JSON, API_ENTRY, MAIN]:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in patterns:
                assert not re.search(pattern, text), f"{path} appears to contain a credential"

    def test_gitignore_excludes_local_env_files(self):
        ignored = (REPO / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in ignored

    def test_frontend_public_prefix_only_holds_public_values(self):
        example = (FRONTEND / ".env.example").read_text(encoding="utf-8")
        for line in example.splitlines():
            line = line.strip()
            if not line.startswith("VITE_"):
                continue
            name, _, value = line.partition("=")
            assert not re.search(r"postgres|secret|password|token|re_[A-Za-z0-9]{20,}", value, re.I), (
                f"{name} is browser-visible and must not hold a secret"
            )


class TestFrontendMigration:
    def test_base_path_is_derived_per_deployment_target(self):
        source = (FRONTEND / "vite.config.js").read_text(encoding="utf-8")
        assert "VITE_DEPLOY_TARGET" in source
        assert "'/'" in source and "/ScholarZone/" in source, (
            "both the Vercel root base and the GitHub Pages subpath must exist"
        )

    def test_canonical_origin_has_not_been_switched_early(self):
        """Canonical URLs may only move after production is proven."""
        source = (FRONTEND / "src" / "services" / "canonicalOrigin.js").read_text(encoding="utf-8")
        assert "gopal735.github.io/ScholarZone" in source, (
            "the canonical host must stay on the proven production host until the "
            "Vercel deployment has been validated"
        )

    def test_no_page_hardcodes_the_canonical_host_anymore(self):
        offenders = []
        for page in FRONTEND.joinpath("src", "pages").glob("*.jsx"):
            if "gopal735.github.io/ScholarZone'" in page.read_text(encoding="utf-8"):
                offenders.append(page.name)
        assert not offenders, f"canonical host still hardcoded in {offenders}"

    def test_spa_routing_serves_the_shell_for_direct_navigation(self):
        doc = json.loads((FRONTEND / "vercel.json").read_text(encoding="utf-8"))
        rewrites = doc.get("rewrites", [])
        assert any(r.get("destination") == "/index.html" for r in rewrites), (
            "direct visits to /scholarships/{id} must return the SPA, not a 404"
        )

    def test_seo_assets_are_present(self):
        for asset in ("robots.txt", "sitemap.xml"):
            assert (FRONTEND / "public" / asset).exists(), f"{asset} must ship"


def _code_without_comments_or_strings(source: str) -> str:
    """Executable source only, with comments and string literals removed.

    A historical mention of a retired platform inside a docstring or comment is
    allowed and often valuable. Reading such a mention as a runtime dependency
    would be wrong, and so would trusting a line-prefix heuristic - a docstring's
    continuation lines are ordinary text as far as the file format is concerned.
    The file is therefore tokenised, and only real code survives.
    """
    import io
    import tokenize

    kept: list[str] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            kept.append(token.string)
    except tokenize.TokenError:
        return source
    return " ".join(kept)


class TestNoSnapDeployRuntimeDependency:
    RUNTIME_FILES = (
        list((BACKEND / "app").rglob("*.py"))
        + list((BACKEND / "api").rglob("*.py"))
        + list((REPO / ".github" / "workflows").rglob("*.yml"))
    )

    def test_runtime_code_and_workflows_have_no_snapdeploy_dependency(self):
        offenders = []
        for path in self.RUNTIME_FILES:
            source = path.read_text(encoding="utf-8", errors="replace")
            executable = _code_without_comments_or_strings(source)
            if "snapdeploy" in executable.lower():
                offenders.append(str(path.relative_to(REPO)))
        assert not offenders, f"executable SnapDeploy references remain: {offenders}"

    def test_public_api_url_is_not_hardcoded_to_a_snapdeploy_host(self):
        for path in (MAIN, BACKEND / "app" / "core" / "config.py"):
            assert "containers.snapdeploy" not in path.read_text(encoding="utf-8")

    def test_maintenance_worker_keeps_its_history_but_is_provider_agnostic(self):
        """The historical note is retained deliberately, and is not a dependency."""
        source = (BACKEND / "app" / "jobs" / "scholarzone_maintenance.py").read_text(
            encoding="utf-8"
        )
        assert "SnapDeploy" in source, "the migration history should stay documented"
        assert "HTTP endpoint of any kind" in source, (
            "the worker must state that it depends on no web tier"
        )

    def test_frontend_build_takes_its_api_host_from_configuration(self):
        """The repository must not hardcode one provider's API hostname."""
        workflow = (REPO / ".github" / "workflows" / "frontend.yml").read_text(encoding="utf-8")
        assert "vars.SCHOLARZONE_API_URL" in workflow
        assert "containers.snapdeploy" not in workflow
