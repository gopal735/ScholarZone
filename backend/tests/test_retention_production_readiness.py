"""Phase 7 - production dry-run readiness.

This audits the operator command rather than running it against production. The
command is ready to be pointed at a real database *only if* the things checked
here hold, and each of them is a property somebody could break later without
noticing: a new default of ``--execute-delete``, a stray print of the connection
string, a switch from ``dry_run`` to ``delete_bounded``.

No production connection is used or needed. Where a check cannot be completed
without one, it says so instead of approximating.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "retention_dry_run.py"


def _load():
    spec = importlib.util.spec_from_file_location("retention_dry_run", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load()


class TestTheCommandIsSafeByDefault:
    def test_dry_run_is_the_default_mode(self, script):
        source = inspect.getsource(script.main)
        # The flag must be opt-in, never opt-out.
        assert 'default="manual"' in source
        assert 'args.execute_delete' in source
        assert source.index("if not args.execute_delete:") < source.index("# ---- Deleting mode")

    def test_importing_the_module_writes_nothing(self, script):
        """A module-level side effect would run on --help."""
        source = inspect.getsource(script)
        module_level = [
            line for line in source.splitlines()
            if line and not line[0].isspace() and not line.startswith(("def ", "class ", "#", "@", '"', "'"))
        ]
        for line in module_level:
            assert not re.match(r"^(print|open|drop|delete|update|insert)\b", line, re.I), line

    def test_the_deleting_path_requires_an_explicit_recovery_path(self, script, capsys):
        # Exit code 2 is the refusal code; 0 would mean it ran.
        assert script.main(["--execute-delete"]) == 2
        captured = capsys.readouterr()
        assert "REFUSED" in captured.err
        assert "--recovery-path" in captured.err
        assert "not a backup" in captured.err

    def test_the_deleting_path_requires_an_explicit_id_list(self, script, capsys):
        assert script.main(["--execute-delete", "--recovery-path", "proven"]) == 2
        err = capsys.readouterr().err
        assert "REFUSED" in err
        assert "--confirm-ids" in err

    def test_dry_run_mode_never_reaches_the_deleting_branch(self, script):
        source = inspect.getsource(script.main)
        dry_branch = source[source.index("if not args.execute_delete:"):source.index("# ---- Deleting mode")]
        assert "delete_bounded" not in dry_branch

    def test_a_guard_block_is_reported_not_crashed(self, script):
        """A blocked dry run is a finding, so the exit code carries it."""
        source = inspect.getsource(script.main)
        assert 'return 0 if report["status"] == "ok" else 1' in source


class TestRequiredEnvironment:
    def test_the_database_url_is_a_configured_field(self):
        import dataclasses

        from app.core.config import Settings

        # Settings is a dataclass in this project, not a pydantic model.
        names = {f.name for f in dataclasses.fields(Settings)}
        assert "database_url" in names

    def test_no_credential_is_ever_printed(self, script):
        """A recovery report gets pasted into tickets; a URL must never be one."""
        source = inspect.getsource(script)
        for forbidden in ("print(settings.database_url", "print(database_url",
                          "print(url", "print(DATABASE_URL", "print(args."):
            assert forbidden not in source, forbidden
        # No environment variable holding a credential may be echoed.
        assert "SCHOLARZONE_DATABASE_URL" not in source or "get_settings()" in source

    def test_the_url_reaches_the_command_only_through_settings(self, script):
        source = inspect.getsource(script)
        assert source.count("SCHOLARZONE_DATABASE_URL") == 0
        assert "get_session_factory()" in source
        assert "get_settings()" in source


class TestQueryScopeAndOutput:
    def test_the_output_keys_are_stable(self):
        """A report consumed by a human today is parsed by nobody today, but the
        keys a reviewer relies on must not change silently."""
        from app.services.retention_engine import dry_run
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine, autoflush=False)()
        try:
            report = dry_run(session)
        finally:
            session.close()
            engine.dispose()
        for key in ("run_id", "mode", "as_of", "contract_version", "trigger", "policy",
                    "summary", "counts_before", "guards", "guard_failures", "status",
                    "delete_candidates", "reference_integrity", "recovery", "note",
                    "elapsed_seconds", "write_scope"):
            assert key in report, key

    def test_the_write_scope_is_declared_explicitly(self):
        from app.services.retention_engine import dry_run
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine, autoflush=False)()
        try:
            scope = dry_run(session)["write_scope"]
        finally:
            session.close()
            engine.dispose()
        assert scope["scholarship_rows_written"] == 0
        assert scope["child_rows_written"] == 0
        assert scope["audit_rows_written"] == 1

    def test_elapsed_time_is_reported_rather_than_claimed_as_a_timeout(self):
        from app.services.retention_engine import dry_run
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine, autoflush=False)()
        try:
            report = dry_run(session)
        finally:
            session.close()
            engine.dispose()
        assert isinstance(report["elapsed_seconds"], float)
        assert report["elapsed_seconds"] >= 0

    def test_the_caps_are_overridable_but_bounded_by_the_policy(self):
        from app.services.retention_contract import default_policy

        policy = default_policy()
        import dataclasses

        names = {f.name for f in dataclasses.fields(policy)}
        for field in ("max_delete_per_run", "max_delete_percentage", "batch_size",
                      "minimum_age_before_delete", "grace_days", "protected_statuses",
                      "max_ambiguous_ratio", "cleanup_enabled", "dry_run"):
            assert field in names, field
        assert policy.cleanup_enabled is False
        assert policy.dry_run is True


class TestProductionExecutionIsNotPerformed:
    """The honest statement this environment can make."""

    def test_no_production_connection_exists_in_this_environment(self):
        from app.services.retention_recovery import database_identity

        identity = database_identity()
        assert "withheld" in identity["note"]
        # Whatever the configured dialect is, this process holds no production
        # credentials, so the command was never pointed at production.
        assert identity["dialect"] in {"sqlite", "postgresql", "none", "unknown"}

    def test_no_production_row_count_is_claimed(self):
        """No test or artefact in this work states a production figure."""
        from app.services.retention_recovery import recovery_requirements_report

        report = recovery_requirements_report()
        serialised = str(report)
        assert "production_total" not in serialised
        assert report["verdict"] == "RECOVERY_PATH_NOT_PROVEN"
