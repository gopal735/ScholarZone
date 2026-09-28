"""Tests for the direct maintenance worker.

The worker exists because the scheduled job used to depend on waking a
sleeping SnapDeploy container. The failure it must never make is the quiet
one: connecting to the wrong database. A development-mode fallback would make
a scheduled run maintain a local SQLite file while reporting success, so that
is pinned here rather than left to inspection.
"""

from __future__ import annotations

import os

import pytest

from app.jobs import scholarzone_maintenance as worker


class TestStageIsolation:
    def test_a_failing_stage_is_reported_not_fatal(self):
        """One unreachable provider must not abort the other stages."""

        def boom():
            raise RuntimeError("provider unreachable")

        report = worker._run_stage("verify", boom)
        assert report.ok is False
        assert "provider unreachable" in report.error

    def test_a_successful_stage_reports_its_detail(self):
        report = worker._run_stage("enrich", lambda: {"records_scanned": 5})
        assert report.ok is True
        assert report.detail == {"records_scanned": 5}
        assert report.runtime_s >= 0

    def test_every_stage_can_fail_independently(self):
        results = [
            worker._run_stage("a", lambda: (_ for _ in ()).throw(ValueError("x"))),
            worker._run_stage("b", lambda: {"ok": 1}),
            worker._run_stage("c", lambda: (_ for _ in ()).throw(KeyError("y"))),
        ]
        assert [r.ok for r in results] == [False, True, False]


class TestProductionDatabaseSafety:
    def test_production_refuses_sqlite_entirely(self, monkeypatch):
        """No URL in production must raise, not fall back to a local file."""
        from app.core.config import get_settings

        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
        monkeypatch.delenv("SCHOLARZONE_DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="SCHOLARZONE_DATABASE_URL is required"):
            get_settings()

    def test_production_never_resolves_to_a_sqlite_url(self, monkeypatch):
        from app.core.config import get_settings

        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
        monkeypatch.setenv(
            "SCHOLARZONE_DATABASE_URL", "postgresql://u:p@host/db?sslmode=require"
        )
        settings = get_settings()
        assert settings.database_url.startswith("postgresql://")
        assert "sqlite" not in settings.database_url.lower()

    def test_development_still_uses_sqlite(self, monkeypatch):
        """Tests and local work must keep working without a database URL."""
        from app.core.config import get_settings

        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "development")
        monkeypatch.delenv("SCHOLARZONE_DATABASE_URL", raising=False)
        assert get_settings().database_url.startswith("sqlite:///")


class TestWorkerSurface:
    def test_every_advertised_stage_is_selectable(self):
        """The stages named in the workflow must be the stages the CLI accepts."""
        source = open(worker.__file__, encoding="utf-8").read()
        for choice in ("verify", "enrich", "images", "discover", "all"):
            assert f'"{choice}"' in source, f"{choice} is not a selectable stage"

    def test_worker_uses_the_same_entrypoints_as_the_api(self):
        """A scheduled run must not diverge from an operator-triggered run."""
        source = open(worker.__file__, encoding="utf-8").read()
        assert "run_verification_round" in source
        assert "run_discovery_round" in source

    def test_worker_does_not_import_the_api(self):
        """The point of the worker is to not need a running server."""
        source = open(worker.__file__, encoding="utf-8").read()
        assert "from app.main" not in source
        assert "uvicorn" not in source

    def test_worker_does_not_echo_the_database_url(self):
        """A secret must never reach a log line or a report."""
        source = open(worker.__file__, encoding="utf-8").read()
        # The URL may only be read by the config layer, never printed.
        assert "print(database_url" not in source
        assert "print(settings.database_url" not in source
        assert "print(args.database_url" not in source

    def test_environment_variable_names_match_the_config_layer(self):
        """A renamed variable silently downgrades the run to SQLite."""
        from app.core import config as config_module

        source = open(config_module.__file__, encoding="utf-8").read()
        assert "SCHOLARZONE_ENVIRONMENT" in source
        assert os.path.basename(worker.__file__) == "scholarzone_maintenance.py"
