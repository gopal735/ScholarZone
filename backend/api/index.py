"""Vercel entrypoint for the existing FastAPI application.

Vercel's Python runtime imports this module and uses its ``app`` attribute. The
application itself is unchanged - it is still the same FastAPI instance built in
``app.main`` with the same routers, middleware, lifespan and startup behaviour.

Nothing is created or started here. In particular there is no schema creation,
no seeding and no background work at import time: on a serverless platform the
import happens in every cold start, and an import that touches the database
would make function initialisation depend on database reachability. The existing
lifespan handler already performs initialisation, and that behaviour is
preserved.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401

__all__ = ["app"]
