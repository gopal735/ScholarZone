from contextlib import asynccontextmanager
import logging
import os
import re
import sys
from threading import Lock, Thread

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .core.config import get_settings
from .database import close_database, get_engine, init_database
from .middleware.api_prefix import StripApiPrefix
from .routers.scholarships import router as scholarships_router
from .routers.verification import router as verification_router
from .routers.admin_image_review import router as admin_image_review_router
from .routers.discovery import router as discovery_router
from .routers.admin_dashboard import router as admin_dashboard_router
from .routers.enrichment import router as enrichment_router
from .seed import seed_database


logger = logging.getLogger(__name__)

# Log to stdout, which is the only stream a serverless platform collects.
#
# Without this, a database initialisation failure was raised, caught, stored and
# reported to /health as the bare string "Database not ready" while the exception
# that caused it went to the root logger's default handler - lastResort - and
# was never captured. The deployment was undebuggable: a 503 with no cause
# anywhere. basicConfig is a no-op when a handler already exists, so this does
# not override an application's existing configuration.
logging.basicConfig(
    level=os.getenv("SCHOLARZONE_LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)


def build_revision() -> str:
    """Short git SHA of the running build, or ``dev``/``unknown``.

    Resolved once at import, from the platform's own deployment identity.

    Order matters. The platform identifier comes first because it cannot be
    falsified by hand: Vercel injects ``VERCEL_GIT_COMMIT_SHA`` for the exact
    commit it built, so the value describes the artefact actually running rather
    than a label somebody remembered to set. An operator-supplied variable is
    accepted only as a fallback, because a build that is told what revision to
    claim will happily claim it while serving older code - which is precisely
    the failure this endpoint exists to make detectable.

    A production build with no identifiable commit reports ``unknown``, and the
    deployment verification treats anything that is not the expected SHA as a
    failure. A healthy process serving the wrong commit must never be reported
    as a successful deployment.
    """
    for variable in ("VERCEL_GIT_COMMIT_SHA", "VERCEL_GIT_COMMIT_REF"):
        raw = (os.getenv(variable) or "").strip()
        if raw and re.fullmatch(r"[0-9a-fA-F]{7,64}", raw):
            return raw[:12]
    raw = (os.getenv("SCHOLARZONE_BUILD_REVISION") or "").strip()
    if raw and re.fullmatch(r"[0-9a-fA-F]{7,64}", raw):
        return raw[:12]
    if get_settings().environment != "production":
        return "dev"
    return "unknown"

_db_ready = False
_db_init_error: str | None = None
_db_lock = Lock()


def _run_init() -> None:
    global _db_ready, _db_init_error
    settings = get_settings()
    try:
        if settings.environment == "production":
            # Production verifies connectivity and nothing else. It does not run
            # the schema migration.
            #
            # create_all plus the ALTER TABLE and CREATE INDEX statements take
            # ACCESS EXCLUSIVE locks on scholarships and carry no statement
            # timeout, so on a serverless cold start they wait on any concurrent
            # maintenance job and never return. The deployment answered 503 with
            # "Database not ready" indefinitely, with no exception anywhere,
            # because the thread was blocked rather than failing.
            #
            # The schema is owned by the GitHub Actions maintenance pipeline,
            # which runs the same migration deliberately and can afford to wait.
            # A read path re-running it on every cold start is both wrong and
            # the reason the API could not start.
            logger.info("Production: verifying database connectivity, not migrating schema")
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            _db_ready = True
            logger.info("Production: database reachable")
            return

        init_database()
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        _db_ready = True
    except Exception as exc:
        logger.exception("Database initialization failed: %s", exc)
        _db_init_error = str(exc)
        _db_ready = False
        return
    try:
        seed_database()
    except Exception:
        logger.exception("Database seeding failed", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.environment == "test":
        _run_init()
        yield
        close_database()
    else:
        thread = Thread(target=_run_init, daemon=True)
        thread.start()
        yield
        thread.join(timeout=5)
        close_database()


app = FastAPI(
    title="ScholarZone API",
    version="1.0.0",
    docs_url="/docs" if get_settings().environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

allowed_origins = get_settings().allowed_origins
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

# Added last so it runs outermost: it has to see the path as the platform sent
# it, before anything else inspects it.
app.add_middleware(StripApiPrefix)

# Logged here rather than at import so the revision is resolved and so the line
# lands after the application object exists.
logger.info("ScholarZone API configured, revision %s", build_revision())


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Invalid request parameters."})


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred."})


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Welcome to ScholarZone"}


@app.get("/health")
def health() -> JSONResponse:
    """Liveness plus build identity.

    A healthy container is not the same as a current one. This deployment had
    a stale build serving traffic for hours while every health check passed,
    because the check only asked "is the process up?". It now also reports
    which revision is running, so a deployment verification can prove the
    container is serving the commit that was just pushed.

    The revision is a short git SHA supplied at build time. It is not a secret
    and contains nothing about configuration or credentials.
    """
    with _db_lock:
        # Verify the dependency when asked, rather than reporting a flag that a
        # background thread was supposed to set.
        #
        # The lifespan starts initialisation on a daemon thread, and on this
        # serverless runtime that thread does not reliably run: the deployment
        # answered 503 "Database not ready" forever while /api/scholarships
        # served live records from the same database. A health check that
        # reports a cached startup flag rather than the actual state of the thing
        # it exists to check is worse than no health check, because it reports a
        # failure that is not happening and a success that might not be.
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return JSONResponse(
                status_code=200,
                content={"status": "ok", "revision": build_revision()},
            )
        except Exception as exc:
            logger.warning("Health check failed: %s", exc)
            content = {
                "status": "error",
                "detail": "Database unreachable",
                "revision": build_revision(),
            }
            if _db_init_error:
                content["init_error"] = _db_init_error
            return JSONResponse(status_code=503, content=content)


# NOTE: Legacy APScheduler is intentionally NOT started in production.
# Verification is triggered by the cloud cron job via /internal/verify/trigger.
# This prevents duplicate scheduler execution.


app.include_router(scholarships_router)
app.include_router(verification_router)
app.include_router(admin_image_review_router)
app.include_router(discovery_router)
app.include_router(admin_dashboard_router)
app.include_router(enrichment_router)


@app.get("/debug/fix-null-lists")
def debug_fix_null_lists_main():
    # This writes to the production database, on a GET, with no authentication.
    # That was survivable only while the API was not internet-facing from a
    # platform anyone could reach; on a public serverless runtime it is an
    # unauthenticated write endpoint. It is reachable outside production only.
    if get_settings().environment == "production":
        raise HTTPException(status_code=404, detail="Not found.")
    from sqlalchemy import text
    from app.database import get_session_factory
    session_factory = get_session_factory()
    session = session_factory()
    try:
        null_eligibility = session.execute(
            text("SELECT id FROM scholarships WHERE eligibility IS NULL")
        ).fetchall()
        null_application_method = session.execute(
            text("SELECT id FROM scholarships WHERE application_method IS NULL")
        ).fetchall()

        fixed = []
        for row in null_eligibility + null_application_method:
            sid = row[0]
            from app.models import Scholarship
            scholarship = session.get(Scholarship, sid)
            if scholarship.eligibility is None:
                scholarship.eligibility = []
            if scholarship.application_method is None:
                scholarship.application_method = []
            fixed.append(sid)

        session.commit()
        return {
            "fixed_ids": fixed,
            "null_eligibility_count": len(null_eligibility),
            "null_application_method_count": len(null_application_method),
        }
    finally:
        session.close()
