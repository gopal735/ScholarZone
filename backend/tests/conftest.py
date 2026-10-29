import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent

# Ensure the tests directory is on sys.path so that test modules can import
# from each other (e.g., test_counting_core importing test_matching_v2).
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

#: The single opt-in. Everything else about the target is checked against
#: this test's own rules; this one variable is what a deliberate, informed
#: run sets.
OPT_IN_VARIABLE = "SCHOLARZONE_TEST_ALLOW_EXTERNAL_DB"


class UnsafeTestDatabaseTarget(RuntimeError):
    """A test run pointed at a database that must never be written by tests."""


def enforce_test_isolation(
    *, environment: str | None = None, database_url: str | None = None
) -> None:
    """Refuse a test run whose database target is not a throwaway one.

    Three targets are refused, in order of how much damage they do:

    ``production`` — the mode that says this is the live system. A test run
    that names it has already lost track of what it is running against.

    A ``postgresql://`` URL of any kind — the working catalogue, a Neon
    branch, anyone's staging database. The scheme alone is enough to refuse,
    because the danger is exactly that a developer exports
    ``SCHOLARZONE_DATABASE_URL`` from a shell, forgets it, and runs pytest.

    The working SQLite file — ``scholarzone.db`` next to this backend — by
    resolved path, so the same file reached through a relative spelling, a
    symlink or a different casing is still refused.

    The refusal names the opt-in variable rather than repointing the run: a
    boundary that silently redirected would let the run pass against a
    database nobody chose, which is worse than a run that stops.
    """
    environment = os.getenv("SCHOLARZONE_ENVIRONMENT", "test").strip().lower()
    database_url = os.getenv("SCHOLARZONE_DATABASE_URL", "").strip()
    opt_in = os.getenv(OPT_IN_VARIABLE, "").strip()
    if opt_in:
        # Opting in is allowed. Opting in quietly is not: the run that has set
        # this variable is by definition pointed at something that outlives it,
        # so the one thing it must never do is look identical to an ordinary
        # run in the logs. The warning goes to stderr, where a test harness
        # still shows it, and names the variable that authorised it.
        print(
            "WARNING: SCHOLARZONE_TEST_ALLOW_EXTERNAL_DB is set - this test run "
            "may write a database that outlives it. Unset it unless that is "
            "exactly what you intend.",
            file=__import__("sys").stderr,
        )
        return

    if environment == "production":
        raise UnsafeTestDatabaseTarget(
            "SCHOLARZONE_ENVIRONMENT=production: a test run must never resolve "
            f"production settings. Set {OPT_IN_VARIABLE}=1 only for a deliberate, "
            "informed run."
        )

    if database_url.startswith(("postgres://", "postgresql://")):
        raise UnsafeTestDatabaseTarget(
            f"SCHOLARZONE_DATABASE_URL points at a PostgreSQL database "
            f"({database_url.split('@')[-1] or 'the configured host'}): a test run "
            "must never reach a database that outlives it. Set "
            f"{OPT_IN_VARIABLE}=1 only for a deliberate, informed run."
        )

    if database_url.startswith(("sqlite://", "sqlite+pysqlite://")):
        target = database_url.split("///", 1)[-1]
        if target and target != ":memory:":
            resolved = Path(target)
            if not resolved.is_absolute():
                resolved = BACKEND_DIR / resolved
            working = BACKEND_DIR / "scholarzone.db"
            try:
                same_file = resolved.resolve() == working.resolve()
            except OSError:
                same_file = str(resolved).endswith("scholarzone.db")
            if same_file:
                raise UnsafeTestDatabaseTarget(
                    f"SCHOLARZONE_DATABASE_URL points at the working catalogue "
                    f"({working}). A test run must never write it. Set "
                    f"{OPT_IN_VARIABLE}=1 only for a deliberate, informed run."
                )


enforce_test_isolation()


# NOTE: this file used to install a fake `app.scheduler` module. That module
# was a legacy APScheduler entry point that nothing in the application ever
# imported - it was dead, and APScheduler was not a production dependency - so
# the stub, which existed only to stop the dead module from building a
# development engine at import time, has been removed along with it.
#
# If a future test needs to prove something about a module that touches
# get_session_factory() at import time, that is a signal the module should not
# be doing that, not a signal to add a stub here.

# A test process is a test process whether or not the caller said so.
#
# This is the isolation boundary, and it has one job: a bare `pytest` run
# must not be able to reach the working catalogue. The safety net below used
# to default only the database URL, and only when the environment was already
# declared `test` - so the boundary held exactly when the caller had already
# opted in, and did nothing for the invocation that actually needed it. The
# regression it was meant to prevent was written by a bare run.
#
# So the environment itself defaults here, before anything in `app` can read
# it. An explicit value still wins: `SCHOLARZONE_ENVIRONMENT=production`
# remains refused, and `development` remains honoured for a deliberate local
# run. What no longer happens is an undeclared run resolving to `development`
# and therefore to the working database.
if os.getenv("SCHOLARZONE_ENVIRONMENT") is None:
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

# With the environment declared, a test run that names no database gets an
# isolated in-memory one. This prevents tests from accidentally using the
# production SQLite file.
if os.getenv("SCHOLARZONE_ENVIRONMENT") == "test" and not os.getenv("SCHOLARZONE_DATABASE_URL"):
    os.environ["SCHOLARZONE_DATABASE_URL"] = "sqlite:///:memory:"

# The public directory quality gate (verified + a validated image) is ON by
# default in every environment, including production.
#
# It is turned OFF here because the long-standing test fixtures are legacy
# seed rows that carry no image: they predate the gate and were written to
# exercise listing, pagination, sorting and filtering - not the gate itself.
# Inventing image URLs for them would fabricate data just to satisfy a filter.
#
# The gate is therefore tested directly, and with the gate on, in
# tests/test_public_quality_gate.py, which seeds the three states it cares
# about explicitly.
os.environ.setdefault("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "false")
os.environ.setdefault("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "false")

import pytest


@pytest.fixture(autouse=True)
def _clear_shared_page_cache():
    """Keep the process-wide discovery page cache out of test isolation.

    The cache exists so a catalogue sweep does not re-fetch the same provider
    page for every record on that domain. It is deliberately process-wide, so
    without this fixture one test's fetched page would satisfy another test's
    request and mask real behaviour.
    """
    from app.services.image_discovery import clear_shared_page_cache

    clear_shared_page_cache()
    yield
    clear_shared_page_cache()
