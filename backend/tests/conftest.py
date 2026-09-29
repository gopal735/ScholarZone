import os

# NOTE: this file used to install a fake `app.scheduler` module. That module
# was a legacy APScheduler entry point that nothing in the application ever
# imported - it was dead, and APScheduler was not a production dependency - so
# the stub, which existed only to stop the dead module from building a
# development engine at import time, has been removed along with it.
#
# If a future test needs to prove something about a module that touches
# get_session_factory() at import time, that is a signal the module should not
# be doing that, not a signal to add a stub here.

# Safety net: If SCHOLARZONE_ENVIRONMENT=test is set but SCHOLARZONE_DATABASE_URL
# is not, default to an in-memory database. This prevents tests from accidentally
# using the production SQLite file.
if os.getenv("SCHOLARZONE_ENVIRONMENT") == "test" and not os.getenv("SCHOLARZONE_DATABASE_URL"):
    os.environ["SCHOLARZONE_DATABASE_URL"] = "sqlite:///:memory:"

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
