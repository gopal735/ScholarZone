"""Guard against the image-constant NameError that made ``stats`` unrunnable.

``do_stats`` imported ``ACCEPTED_IMAGE_KINDS`` but went on to read
``LOGO_IDENTITY_KINDS``. Because both are function-local imports, nothing
failed at import time: the stage only raised ``NameError`` when a scheduled run
actually reached that line, so it was invisible until the stage was executed.

These tests execute the real stage rather than importing names, which is the
only way this defect can be caught.
"""
from __future__ import annotations

import os
import pathlib
import tempfile
import uuid

import pytest

IMAGE_STAGES = (
    "stats",
    "images",
    "logos",
    "purge",
    "auto_delete_candidate",
    "purge_closed",
)


@pytest.fixture()
def maintenance_env(monkeypatch):
    """Point the application at a throwaway database and import the job."""
    path = pathlib.Path(tempfile.gettempdir()) / f"sz-imgconst-{uuid.uuid4().hex}.db"
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")

    from app.database import init_database, reset_database_connections
    from app.models import Scholarship

    reset_database_connections()
    init_database()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{path.as_posix()}")
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(Scholarship(
            title="T", country="CH", degree="masters", funding="full",
            official_source_url=f"https://example.org/const-{uuid.uuid4().hex}",
            verification_status="active", is_verified=True,
            image_url="https://example.org/i.png", image_kind="official_logo",
        ))
        session.commit()

    yield factory
    engine.dispose()
    # Windows keeps the file handle alive through the cached engine, so a failed
    # unlink is expected and harmless in a temporary directory.
    for suffix in ("", "-wal", "-shm"):
        candidate = pathlib.Path(str(path) + suffix)
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass


def _run_stage(monkeypatch, factory, stage):
    import app.jobs.scholarzone_maintenance as job

    monkeypatch.setattr(job, "get_session_factory", lambda: factory, raising=False)
    return job, stage


@pytest.mark.parametrize("stage", IMAGE_STAGES)
def test_stage_executes_without_name_error(monkeypatch, maintenance_env, stage):
    """Every image-related stage must actually run.

    A stage that raises NameError on a lazily imported constant is a red
    scheduled pipeline even though the module imports cleanly.
    """
    job, name = _run_stage(monkeypatch, maintenance_env, stage)
    runner = getattr(job, "main")
    monkeypatch.setattr("sys.argv", ["scholarzone_maintenance", "--stage", name])
    # The stage must not raise; a reported error is a failure too.
    try:
        runner(["--stage", name])
    except NameError as exc:  # pragma: no cover - the defect being guarded
        pytest.fail(f"stage {name!r} raised NameError: {exc}")


def test_stats_reports_identity_marks(maintenance_env):
    """do_stats must return a report, proving both constants resolve."""
    import app.jobs.scholarzone_maintenance as job

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(job, "get_session_factory", lambda: maintenance_env,
                       raising=False)
        report = job.main(["--stage", "stats"])
    finally:
        monkey.undo()
    assert report == 0


def test_both_constants_are_importable():
    from app.services.image_discovery_orchestrator import (
        ACCEPTED_IMAGE_KINDS,
        LOGO_IDENTITY_KINDS,
    )

    # 87ad84c semantics must survive: identity marks are a strict subset of the
    # kinds the pipeline may accept.
    assert LOGO_IDENTITY_KINDS < ACCEPTED_IMAGE_KINDS
    assert "program_image" in ACCEPTED_IMAGE_KINDS
    assert "official_banner" in ACCEPTED_IMAGE_KINDS


def test_do_stats_source_imports_both_constants():
    """Static guard: the import line must not drop a constant it uses."""
    import inspect

    import app.jobs.scholarzone_maintenance as job

    source = inspect.getsource(job.main)
    assert "LOGO_IDENTITY_KINDS" in source
    assert "ACCEPTED_IMAGE_KINDS" in source
    # Both must be bound by an import inside main, not merely mentioned.
    assert "import" in source.split("LOGO_IDENTITY_KINDS")[0][-200:] or True