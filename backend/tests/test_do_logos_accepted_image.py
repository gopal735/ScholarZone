"""Regression coverage for the proven ``do_logos`` image-destruction defect.

Production evidence (audit rows 3 and 5, 2026-10-04):

    08:35:23  id 14  writer_context=unknown           image SET to the ETHZ image
    08:38:28  id 14  writer_context=maintenance.logos image CLEARED to NULL

Every test drives the real stage through ``main(["--stage", "logos", ...])``
against a throwaway SQLite database. No test re-implements the production
predicate; the assertions are on observed before/after state only.

Harness note
------------
``do_logos`` decides whether to commit from its own counters, so a fixture whose
every row already carries an image produces no attachment and - before the fix -
discards its own clears. Tests that assert on a *clear* therefore seed one
logo-less record so the stage has real work to persist, exactly as production
does. ``test_clear_only_run_commits_its_clear`` deliberately omits it.
"""
from __future__ import annotations

import pathlib
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

ACCEPTED = ("program_image", "official_banner", "official_logo",
            "official_government", "official_university")

VERIFIED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
ETHZ = "https://ethz.ch/en/studies"


@pytest.fixture()
def logos_env(monkeypatch):
    path = pathlib.Path(tempfile.gettempdir()) / f"sz-logos-{uuid.uuid4().hex}.db"
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")

    from app.database import init_database, reset_database_connections
    from app.services.logo_fallback_resolver import OVERRIDE_PATH, load_overrides

    if not OVERRIDE_PATH.exists() or "ethz.ch" not in load_overrides():
        pytest.skip("ethz.ch override absent; these tests need the real override map")

    reset_database_connections()
    init_database()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{path.as_posix()}")
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        candidate = pathlib.Path(str(path) + suffix)
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass


def seed(factory, *, kind, image=True, verified_at=VERIFIED_AT, title="row"):
    """An ethz.ch record. ethz.ch is in the real override map, so do_logos
    takes the branch that touches it."""
    from app.models import Scholarship

    with factory() as s:
        row = Scholarship(
            title=f"{title} {kind}",
            country="CH", degree="masters", funding="full",
            official_source_url=f"{ETHZ}/{uuid.uuid4().hex}.html",
            verification_status="active", is_verified=True,
            image_url=(f"https://ethz.ch/img-{uuid.uuid4().hex}.jpg" if image else None),
            image_source_url="https://ethz.ch/en/studies/x.html",
            image_source_type="official_page",
            image_kind=kind if image else None,
            image_alt_text="campus" if image else None,
            image_verified_at=verified_at,
            image_evaluation_status="verified" if image else None,
            image_evaluated_at=VERIFIED_AT,
        )
        s.add(row)
        s.commit()
        return row.id


def read(factory, row_id: int) -> dict:
    from app.models import Scholarship

    with factory() as s:
        r = s.get(Scholarship, row_id)
        return {
            "image_url": r.image_url,
            "image_kind": r.image_kind,
            "image_source_url": r.image_source_url,
            "image_source_type": r.image_source_type,
            "image_alt_text": r.image_alt_text,
            "image_verified_at": r.image_verified_at,
            "image_evaluation_status": r.image_evaluation_status,
            "image_evaluated_at": r.image_evaluated_at,
        }


def run_stage(factory, *extra):
    """Execute the real production stage."""
    import app.database
    import app.jobs.scholarzone_maintenance as job

    original = app.database.get_session_factory
    app.database.get_session_factory = lambda: factory
    try:
        job.main(["--stage", "logos", *extra])
    finally:
        app.database.get_session_factory = original


# --- A: accepted images must survive ---------------------------------------

@pytest.mark.parametrize("kind", ACCEPTED)
def test_accepted_kind_survives(logos_env, kind):
    """A + cases 1-5: every ACCEPTED_IMAGE_KINDS member is preserved."""
    seed(logos_env, kind=kind, image=False)  # gives the stage something to attach
    row_id = seed(logos_env, kind=kind)
    run_stage(logos_env)
    after = read(logos_env, row_id)
    assert after["image_url"] is not None, f"{kind} was destroyed by do_logos"
    assert after["image_kind"] == kind
    assert after["image_verified_at"] is not None


def test_accepted_kind_without_timestamp_survives(logos_env):
    """C + case 7: acceptance is decided by kind, not by the timestamp.

    A missing timestamp is not licence to delete an accepted image.
    """
    seed(logos_env, kind="program_image", image=False)
    row_id = seed(logos_env, kind="program_image", verified_at=None)
    run_stage(logos_env)
    assert read(logos_env, row_id)["image_url"] is not None


def test_id14_failure_shape_is_prevented(logos_env):
    """Case 13: the exact proven production transition must not occur."""
    seed(logos_env, kind="program_image", image=False)
    row_id = seed(logos_env, kind="program_image")
    before = read(logos_env, row_id)
    assert before["image_kind"] == "program_image" and before["image_verified_at"]

    run_stage(logos_env)

    after = read(logos_env, row_id)
    assert after["image_url"] == before["image_url"], "ID 14 shape reoccurred"
    assert after["image_kind"] == "program_image"
    assert after["image_verified_at"] == before["image_verified_at"]
    assert after["image_source_url"] is not None
    assert after["image_alt_text"] is not None


# --- B/D: legitimate cleanup must survive the fix --------------------------

def test_non_accepted_image_is_still_cleared(logos_env):
    """B + case 6: a non-accepted kind remains eligible for logo replacement."""
    seed(logos_env, kind="program_image", image=False)
    row_id = seed(logos_env, kind="unrelated_banner")
    run_stage(logos_env)
    after = read(logos_env, row_id)
    assert after["image_url"] is None, "legitimate cleanup was disabled"
    assert after["image_kind"] is None
    assert after["image_source_url"] is None


def test_verified_non_accepted_image_does_not_survive_on_timestamp_alone(logos_env):
    """D: image_verified_at alone must not grant immunity.

    Guards against 'fixing' this by trusting the timestamp, which would protect
    exactly the unaccepted artwork the stage exists to replace.
    """
    seed(logos_env, kind="program_image", image=False)
    row_id = seed(logos_env, kind="unrelated_banner", verified_at=VERIFIED_AT)
    assert read(logos_env, row_id)["image_verified_at"] is not None
    run_stage(logos_env)
    assert read(logos_env, row_id)["image_url"] is None


# --- E: attachment still works ---------------------------------------------

def test_genuine_logo_attachment_still_works(logos_env):
    """E + case 8: a record with no image receives the audited logo."""
    row_id = seed(logos_env, kind=None, image=False)
    run_stage(logos_env)
    after = read(logos_env, row_id)
    assert after["image_url"], "logo attachment regressed"
    assert after["image_kind"] == "official_logo"
    assert after["image_verified_at"] is not None


# --- F: clear-only transaction semantics -----------------------------------

def test_clear_only_run_commits_its_clear(logos_env):
    """F + case 9: a run whose only mutation is a clear must persist it.

    This is the transaction-coupling defect. Nothing is attached here, so before
    the fix the stage reached no commit and the clear was discarded.
    """
    row_id = seed(logos_env, kind="unrelated_banner")
    run_stage(logos_env)
    assert read(logos_env, row_id)["image_url"] is None, (
        "clear-only run silently discarded its mutation"
    )


def test_dry_run_never_persists(logos_env):
    """Case 10."""
    logo_less = seed(logos_env, kind=None, image=False)
    accepted = seed(logos_env, kind="program_image")
    run_stage(logos_env, "--dry-run")
    assert read(logos_env, logo_less)["image_url"] is None, "dry-run attached a logo"
    assert read(logos_env, accepted)["image_url"] is not None


def test_no_op_run_changes_nothing(logos_env):
    """Case 11: identity marks alone must be inert."""
    row_id = seed(logos_env, kind="official_logo")
    before = read(logos_env, row_id)
    run_stage(logos_env)
    assert read(logos_env, row_id) == before


# --- invariants -------------------------------------------------------------

def test_metadata_stays_coherent(logos_env):
    """Case 12: a clear must not strand a verdict describing an absent image."""
    seed(logos_env, kind="program_image", image=False)
    row_id = seed(logos_env, kind="unrelated_banner")
    run_stage(logos_env)
    after = read(logos_env, row_id)
    if after["image_url"] is None:
        assert after["image_evaluation_status"] is None
        assert after["image_evaluated_at"] is None
        assert after["image_verified_at"] is None


def test_real_stage_executes_without_runtime_error(logos_env):
    """Case 14."""
    seed(logos_env, kind="program_image", image=False)
    seed(logos_env, kind="unrelated_banner")
    run_stage(logos_env)


def test_accepted_kinds_are_the_canonical_set():
    """Pins the vocabulary the fix relies on."""
    from app.services.image_discovery_orchestrator import (
        ACCEPTED_IMAGE_KINDS,
        LOGO_IDENTITY_KINDS,
    )

    assert LOGO_IDENTITY_KINDS < ACCEPTED_IMAGE_KINDS
    for kind in ACCEPTED:
        assert kind in ACCEPTED_IMAGE_KINDS