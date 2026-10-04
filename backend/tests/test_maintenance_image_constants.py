"""Regression tests for the maintenance job's image-kind constant imports.

``do_stats()`` and ``do_purge()`` each import from
``app.services.image_discovery_orchestrator`` inside the function body. Both once
imported only one of the two constants while referencing the other, so a
production maintenance cycle died part-way with ``NameError``:
``stats`` on ``LOGO_IDENTITY_KINDS`` and ``purge`` on ``ACCEPTED_IMAGE_KINDS``.

The policy itself was already covered by ``test_purge_image_safety.py``, which
re-derives the rule locally. That is why the break survived review: nothing ever
called the two stage functions, so the code that actually runs in production was
never executed by a test.

These tests close that gap. They invoke the real stages, pin the structural
invariant that a stage may not reference an image-kind constant it has not
imported, and pin the canonical constant values so a future edit cannot quietly
weaken which images purge is allowed to keep.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.jobs import scholarzone_maintenance as worker
from app.services.image_discovery_orchestrator import (
    ACCEPTED_IMAGE_KINDS,
    LOGO_IDENTITY_KINDS,
)

ORCHESTRATOR_MODULE = "app.services.image_discovery_orchestrator"
IMAGE_KIND_CONSTANTS = {"LOGO_IDENTITY_KINDS", "ACCEPTED_IMAGE_KINDS"}
STAGES_USING_IMAGE_KINDS = ("do_stats", "do_purge", "do_logos")
JOB_SOURCE = Path(worker.__file__)


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    )

    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()
    yield get_session_factory()


def _job_tree() -> ast.Module:
    return ast.parse(JOB_SOURCE.read_text(encoding="utf-8"))


def _stage(name: str) -> ast.FunctionDef:
    return next(
        n
        for n in ast.walk(_job_tree())
        if isinstance(n, ast.FunctionDef) and n.name == name
    )


def _orchestrator_imports(fn: ast.FunctionDef) -> set[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(fn)
        if isinstance(node, ast.ImportFrom) and node.module == ORCHESTRATOR_MODULE
        for alias in node.names
    }


def _bound_names(fn: ast.FunctionDef) -> set[str]:
    bound: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
    return bound


class TestStagesExecute:
    """The two stages that raised NameError must run to completion."""

    def test_stats_stage_runs_without_a_name_error(self, factory, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        assert worker.main(["--stage", "stats", "--dry-run"]) == worker.EXIT_OK

    def test_purge_stage_runs_without_a_name_error(self, factory, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        assert worker.main(["--stage", "purge", "--dry-run"]) == worker.EXIT_OK

    def test_logos_stage_runs_without_a_name_error(self, factory, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        assert worker.main(["--stage", "logos", "--dry-run"]) == worker.EXIT_OK

    @pytest.mark.parametrize("stage", ["stats", "purge", "logos"])
    def test_stage_output_mentions_no_name_error(self, factory, monkeypatch, stage, capsys):
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        worker.main(["--stage", stage, "--dry-run"])
        assert "NameError" not in capsys.readouterr().out


class TestLocalImportInvariant:
    """No stage may reference an image-kind constant it has not imported."""

    def test_no_stage_uses_an_unimported_image_kind_constant(self):
        offenders: list[str] = []
        for fn in (n for n in ast.walk(_job_tree()) if isinstance(n, ast.FunctionDef)):
            loaded = {
                n.id
                for n in ast.walk(fn)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            }
            bound = _bound_names(fn)
            for name in sorted(IMAGE_KIND_CONSTANTS & loaded - bound):
                offenders.append(f"{fn.name}() uses {name} without importing it")
        assert not offenders, "; ".join(offenders)

    @pytest.mark.parametrize("stage", STAGES_USING_IMAGE_KINDS)
    def test_stage_imports_exactly_the_constants_it_uses(self, stage):
        """Catches both directions: a missing import and a stale one."""
        fn = _stage(stage)
        used = {
            n.id
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        } & IMAGE_KIND_CONSTANTS
        imported = _orchestrator_imports(fn)
        assert used <= imported, f"{stage}() uses {sorted(used - imported)} unimported"
        assert imported <= used, f"{stage}() imports unused {sorted(imported - used)}"


class TestCanonicalConstantsUnchanged:
    """Imports may be fixed; the policy itself must not drift."""

    def test_logo_identity_kinds_canonical_membership(self):
        assert LOGO_IDENTITY_KINDS == frozenset(
            {"official_logo", "official_government", "official_university"}
        )

    def test_accepted_kinds_is_a_superset_of_identity_kinds(self):
        assert LOGO_IDENTITY_KINDS <= ACCEPTED_IMAGE_KINDS

    @pytest.mark.parametrize("kind", ["program_image", "official_banner"])
    def test_non_identity_accepted_kinds_are_still_protected(self, kind):
        """The 87ad84c rule: an accepted image survives regardless of its kind."""
        assert kind in ACCEPTED_IMAGE_KINDS
        assert kind not in LOGO_IDENTITY_KINDS

    def test_accepted_kinds_has_exactly_two_non_identity_members(self):
        assert len(ACCEPTED_IMAGE_KINDS - LOGO_IDENTITY_KINDS) == 2


class TestPurgeRuleStillProtectsAcceptedImages:
    """Execute the purge rule itself, not a local re-derivation of it."""

    def test_purge_keeps_accepted_non_identity_kinds(self, factory):
        from datetime import datetime, timezone

        from app.models import Scholarship

        verified_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for index, kind in enumerate(sorted(ACCEPTED_IMAGE_KINDS)):
            session = factory()
            row = Scholarship(
                title=f"Purge Guard {kind}",
                country="GB",
                degree="masters",
                funding="full",
                official_source_url=f"https://example.org/guard-{index}-{kind}",
                is_archived=False,
                verification_status="active",
                is_verified=True,
                image_url=f"https://example.org/img-{index}-{kind}.png",
                image_kind=kind,
                image_verified_at=verified_at,
            )
            session.add(row)
            session.commit()
            session.close()

        worker.main(["--stage", "purge", "--dry-run"])

        session = factory()
        cleared = [
            r.image_kind
            for r in session.query(Scholarship).all()
            if r.image_url is None
        ]
        session.close()
        assert not cleared, f"purge would clear accepted image kinds: {sorted(cleared)}"
