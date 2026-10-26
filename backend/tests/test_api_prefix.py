"""The API must answer on /api/... as well as at the root.

Vercel Services routes public traffic and then hands the service the ORIGINAL
request path, so /api/scholarships arrived as /api/scholarships while every route
is declared at the root. FastAPI answered {"detail": "Not Found"} for every
request, which is indistinguishable from a broken database or a failed
deployment.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.middleware.api_prefix import StripApiPrefix


class TestPrefixStripping:
    def test_api_prefix_is_removed(self):
        stripped = {}

        async def inner(scope, receive, send):
            stripped.update(scope)

        middleware = StripApiPrefix(inner)
        scope = {"type": "http", "path": "/api/scholarships", "root_path": ""}
        import asyncio

        asyncio.run(middleware(scope, None, None))
        assert stripped["path"] == "/scholarships"

    def test_bare_prefix_becomes_root(self):
        captured = {}

        async def inner(scope, receive, send):
            captured.update(scope)

        import asyncio

        middleware = StripApiPrefix(inner)
        asyncio.run(middleware({"type": "http", "path": "/api"}, None, None))
        assert captured["path"] == "/"

    @pytest.mark.parametrize(
        "path", ["/health", "/scholarships", "/", "/apifoo", "/api-docs"]
    )
    def test_other_paths_are_untouched(self, path):
        captured = {}

        async def inner(scope, receive, send):
            captured.update(scope)

        import asyncio

        middleware = StripApiPrefix(inner)
        asyncio.run(middleware({"type": "http", "path": path}, None, None))
        assert captured["path"] == path

    def test_only_one_prefix_is_removed(self):
        # /api/api/health must not become /api/health, which would then 404.
        captured = {}

        async def inner(scope, receive, send):
            captured.update(scope)

        import asyncio

        middleware = StripApiPrefix(inner)
        asyncio.run(middleware({"type": "http", "path": "/api/api/health"}, None, None))
        assert captured["path"] == "/api/health"

    def test_non_http_scopes_pass_straight_through(self):
        seen = []

        async def inner(scope, receive, send):
            seen.append(scope["type"])

        import asyncio

        middleware = StripApiPrefix(inner)
        asyncio.run(middleware({"type": "lifespan", "path": "/api/x"}, None, None))
        assert seen == ["lifespan"]


class TestRoutedPaths:
    @pytest.fixture(scope="class")
    def client(self):
        with TestClient(app) as test_client:
            yield test_client

    def test_api_health_is_not_found_free(self, client):
        # Any status proves routing. 404 specifically would mean the prefix was
        # never stripped.
        response = client.get("/api/health")
        assert response.status_code != 404, response.text
        assert "status" in response.json()

    def test_api_scholarships_resolves_to_the_scholarships_route(self):
        # Checked against the router rather than by calling the endpoint. A live
        # call reaches the database, and the local development SQLite file is
        # older than the schema, so the test would fail on a missing column and
        # say nothing about routing.
        #
        # app.routes is not the place to look: this FastAPI version keeps an
        # included router as a single _IncludedRouter entry with no .path, so
        # asserting on app.routes finds only the six hand-written routes and
        # wrongly reports the scholarships router as absent.
        from app.routers.scholarships import router as scholarships_router

        paths = {getattr(route, "path", None) for route in scholarships_router.routes}
        assert "/scholarships" in paths
        assert "/scholarships/stats" in paths
        # No duplicated /api-prefixed copies exist; the middleware handles it.
        assert not any(p and p.startswith("/api/") for p in paths), (
            "the prefix is handled by middleware, not by duplicating routes"
        )

    def test_root_health_still_answers(self, client):
        # The deployment verification workflow checks /health, so stripping must
        # not remove the root routes it depends on.
        response = client.get("/health")
        assert response.status_code != 404, response.text

    def test_api_and_root_health_report_the_same_thing(self, client):
        assert client.get("/health").json().get("status") == (
            client.get("/api/health").json().get("status")
        )


class TestCorsOrigins:
    def test_named_vercel_frontends_are_allowed(self):
        from app.core.config import Settings, _split_origins  # noqa: F401

        import os

        os.environ.setdefault("SCHOLARZONE_ALLOWED_ORIGINS", "http://localhost:5173")
        from app.core import config as config_module

        settings = config_module.get_settings()
        assert "https://scholarzone-fwzj.vercel.app" in settings.allowed_origins
        assert "https://scholarzone.vercel.app" in settings.allowed_origins
        assert "http://localhost:5173" in settings.allowed_origins
        assert "https://gopal735.github.io" in settings.allowed_origins
        # Credentials are enabled on this middleware, so a wildcard would be
        # unsafe and is not used anywhere.
        assert "*" not in settings.allowed_origins


class TestEntrypointExports:
    def test_api_index_exposes_app(self):
        from api.index import app as entrypoint_app

        assert entrypoint_app is app
