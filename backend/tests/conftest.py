import os
import sys
import types
from uuid import uuid4

# Prevent the real app.scheduler from being imported before the test database
# is configured. The real module calls get_session_factory() at import time,
# which would otherwise cache the development database engine.
fake_scheduler = types.ModuleType("app.scheduler")
fake_scheduler.start_scheduler = lambda: None
fake_scheduler.mark_due_for_review = lambda: None
sys.modules["app.scheduler"] = fake_scheduler

# Safety net: If SCHOLARZONE_ENVIRONMENT=test is set but SCHOLARZONE_DATABASE_URL
# is not, default to an in-memory database. This prevents tests from accidentally
# using the production SQLite file.
if os.getenv("SCHOLARZONE_ENVIRONMENT") == "test" and not os.getenv("SCHOLARZONE_DATABASE_URL"):
    os.environ["SCHOLARZONE_DATABASE_URL"] = "sqlite:///:memory:"
