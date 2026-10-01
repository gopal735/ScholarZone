"""The Vercel deployment must declare exactly two services.

Vercel's auto-detector previously treated ``backend/app`` as a third standalone
service alongside the API and the frontend, and built three things instead of
two. The root ``vercel.json`` is what pins the count, so the count is asserted
here rather than assumed: a file that silently loses its ``services`` key falls
back to auto-detection, which is how the third service appeared.
"""

from __future__ import annotations

import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
ROOT_VERCEL = REPO / "vercel.json"


@pytest.fixture(scope="module")
def root_config() -> dict:
    return json.loads(ROOT_VERCEL.read_text(encoding="utf-8"))


class TestExactlyTwoServices:
    def test_services_key_is_present(self, root_config):
        # Without this key Vercel ignores services entirely and auto-detects.
        assert "services" in root_config, (
            "root vercel.json has no services key; Vercel falls back to "
            "auto-detection, which is what added backend/app as a third service"
        )

    def test_exactly_two_services(self, root_config):
        assert sorted(root_config["services"]) == ["backend", "frontend"]

    def test_no_service_root_escapes_the_repo(self, root_config):
        for name, service in root_config["services"].items():
            root = service["root"]
            assert not pathlib.PurePosixPath(root).is_absolute(), (
                f"{name} root must be relative to the repository"
            )
            assert ".." not in pathlib.PurePosixPath(root).parts, name

    def test_roots_point_at_the_two_apps(self, root_config):
        services = root_config["services"]
        assert services["backend"]["root"] == "backend"
        assert services["frontend"]["root"] == "frontend"

    def test_frameworks_are_declared(self, root_config):
        services = root_config["services"]
        assert services["backend"]["framework"] == "fastapi"
        assert services["frontend"]["framework"] == "vite"

    def test_backend_entrypoint_is_declared_explicitly(self, root_config):
        # Left to auto-detection, the backend either resolves to the wrong
        # module or builds and then 404s on every route, with the build log
        # looking clean. The entrypoint is the one thing that must be right.
        entry = root_config["services"]["backend"].get("entrypoint")
        assert entry == "api.index:app", (
            f"backend entrypoint is {entry!r}; api/index.py exposes app"
        )

    def test_entrypoint_target_exists_and_exposes_app(self):
        entry = REPO / "backend" / "api" / "index.py"
        assert entry.exists()
        source = entry.read_text(encoding="utf-8")
        assert "from app.main import app" in source

    def test_backend_app_is_not_a_service_of_its_own(self, root_config):
        # The regression that started this: backend/app treated as a service.
        for name, service in root_config["services"].items():
            assert service["root"] != "backend/app", name


class TestRouting:
    def test_api_paths_reach_the_backend_first(self, root_config):
        rewrites = root_config["rewrites"]
        assert rewrites[0]["source"] == "/api/(.*)"
        assert rewrites[0]["destination"]["service"] == "backend"

    def test_everything_else_reaches_the_frontend(self, root_config):
        catch_all = root_config["rewrites"][-1]
        assert catch_all["destination"]["service"] == "frontend"
        # The catch-all serves the SPA shell so a shared deep link such as
        # /scholarships/12 does not 404 on a hard load.
        assert catch_all["destination"].get("path") == "/index.html"

    def test_catch_all_does_not_swallow_real_files(self, root_config):
        # Without the negative lookahead the shell would also be served for the
        # hashed asset URLs, so every stylesheet and script would come back as
        # index.html and the app would render nothing.
        catch_all = root_config["rewrites"][-1]["source"]
        assert catch_all.startswith("/((?!")
        for excluded in ("api/", "assets/"):
            assert excluded in catch_all, f"{excluded} must not fall through to the shell"

    def test_api_is_excluded_from_the_spa_shell(self, root_config):
        catch_all = root_config["rewrites"][-1]["source"]
        assert "api/" in catch_all

    def test_backend_strips_the_api_prefix(self, root_config):
        # Vercel hands a service the ORIGINAL request path, so /api/health would
        # arrive as /api/health. FastAPI routes live at the root, so without this
        # transform every API call 404s while the deploy still reports success.
        routes = root_config["services"]["backend"].get("routes") or []
        transform = None
        for rule in routes:
            for candidate in rule.get("transforms", []):
                if candidate.get("type") == "request.path":
                    transform = candidate
        assert transform is not None, (
            "backend service has no request.path transform; /api/health would "
            "reach FastAPI as /api/health and 404"
        )
        assert transform["op"] == "set"
        assert transform["args"] == "/$1"


class TestTopLevelKeysAreValidInServicesMode:
    def test_no_build_keys_at_the_top_level(self, root_config):
        # In services mode these have no single owner and are rejected.
        forbidden = {
            "functions",
            "buildCommand",
            "installCommand",
            "devCommand",
            "ignoreCommand",
            "outputDirectory",
            "framework",
        }
        present = forbidden & set(root_config)
        assert not present, f"invalid at the top level in services mode: {sorted(present)}"

    def test_routing_keys_are_top_level(self, root_config):
        assert "rewrites" in root_config


class TestPerServiceConfigsAgreeWithTheRoot:
    def test_backend_config_does_not_redeclare_the_framework(self):
        backend = json.loads((REPO / "backend" / "vercel.json").read_text(encoding="utf-8"))
        # The service already declares framework: fastapi. A null here reads as
        # "override to nothing" rather than "not specified".
        assert "framework" not in backend

    def test_frontend_keeps_the_spa_fallback(self):
        frontend = json.loads(
            (REPO / "frontend" / "vercel.json").read_text(encoding="utf-8")
        )
        destinations = [rule["destination"] for rule in frontend.get("rewrites", [])]
        assert "/index.html" in destinations, (
            "a direct visit to a deep link would 404 without the SPA fallback"
        )

    def test_frontend_no_longer_proxies_api(self):
        frontend = json.loads(
            (REPO / "frontend" / "vercel.json").read_text(encoding="utf-8")
        )
        for rule in frontend.get("rewrites", []):
            assert "vercel.app" not in str(rule.get("destination", ""))
            assert "snapdeploy" not in str(rule.get("destination", ""))

    def test_no_per_service_config_targets_the_old_split_projects(self):
        for relative in ("backend/vercel.json", "frontend/vercel.json"):
            raw = (REPO / relative).read_text(encoding="utf-8")
            assert "separate Vercel project" not in raw, (
                f"{relative} still describes the old two-project split"
            )