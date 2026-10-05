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
from .build_provenance import ProvenanceError, read_embedded_revision
from . import build_provenance
from .database import close_database, get_engine, init_database
from .middleware.api_prefix import StripApiPrefix
from .routers.scholarships import router as scholarships_router
from .routers.match import router as match_router
from .routers.counts import router as counts_router
from .routers.verification import router as verification_router
from .routers.admin_image_review import router as admin_image_review_router
from .routers.discovery import router as discovery_router
from .routers.admin_dashboard import router as admin_dashboard_router
from .routers.admin_verification import router as admin_verification_router
from .routers.enrichment import router as enrichment_router
from .routers.auth import router as auth_router
from .routers.dashboard import router as dashboard_router
from .routers.applications import router as applications_router
from .routers.mentor import router as mentor_router
from .routers.supervisors import router as supervisors_router
from .routers.outreach import router as outreach_router
from .routers.supervisor_email import router as supervisor_email_router
from .services.application_workspace import WorkspaceError
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
    """The full git SHA this artefact was built from, or ``dev``.

    Read from an artefact embedded in the package at build time, never from the
    runtime environment. The previous implementation read
    ``VERCEL_GIT_COMMIT_SHA`` at runtime on the assumption that a platform
    identifier cannot be falsified by hand. That assumption was wrong here: a
    preview built from ``00bc39d`` reported ``4edd154a3037`` while Vercel's own
    deployment metadata recorded ``00bc39d``. A runtime variable describes the
    function's environment, not the build that produced the code, so it cannot
    prove what is running.

    The full forty-character SHA is returned and never truncated. A twelve-
    character prefix is not an identity: two commits can share one, and a gate
    that compares prefixes will happily accept the wrong build.

    Nothing here consults an environment variable or a request header, so no
    caller and no operator can make this process claim a revision it was not
    built from. In production a missing or malformed artefact raises, which
    fails ``/health`` rather than publishing a healthy response with an
    unverified identity.
    """
    try:
        return read_embedded_revision()
    except ProvenanceError as error:
        # A missing artefact means "nobody built this", which is normal on a
        # developer's machine and fatal in production. A *corrupt* artefact means
        # a build ran and produced something unusable - that is always wrong, so
        # it always raises. Letting a corrupt artefact degrade to "dev" would let
        # a broken deployment answer "ok" on exactly the endpoint whose job is to
        # notice.
        if not build_provenance.ARTIFACT.exists() and get_settings().environment != "production":
            logger.error("No build artefact present (development): %s", error)
            return "dev"
        raise


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
        # GET and POST cover the read-only public catalogue plus the stateless
        # Match endpoint. PUT and DELETE were added for the student dashboard's
        # own state - saving a scholarship and moving an application forward -
        # which are the first authenticated writes this API has. The method list
        # is still explicit rather than a wildcard, and the origin list is
        # unchanged.
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Accept", "Content-Type"],
    )

# Added last so it runs outermost: it has to see the path as the platform sent
# it, before anything else inspects it.
app.add_middleware(StripApiPrefix)

# Logged here rather than at import so the revision is resolved and so the line
# lands after the application object exists.
#
# Guarded so a corrupt or missing build artefact is *reported* at startup rather
# than preventing the process from booting. /health still fails on the same
# condition, which is where a wrong revision must be caught: an unbootable
# service takes every endpoint down with it and turns a diagnosable packaging
# fault into an outage.
try:
    logger.info("ScholarZone API configured, revision %s", build_revision())
except ProvenanceError as error:
    logger.error("ScholarZone API has NO verified build identity: %s", error)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Invalid request parameters."})


@app.exception_handler(WorkspaceError)
async def workspace_error_handler(_: Request, exc: WorkspaceError) -> JSONResponse:
    """Map a domain failure onto its HTTP status.

    The application service raises one exception type carrying the status it
    means, so the service can express "this is a conflict" without importing
    FastAPI. The routing layer decides what that becomes on the wire.

    A conflict is logged at warning level with the status and nothing else. The
    message names states and versions, never note contents or credentials, so a
    log line can be pasted into a bug report without leaking a student's private
    work.
    """
    if exc.status_code >= 500:
        logger.error("Workspace failure (%s)", exc.status_code)
    elif exc.status_code == 409:
        logger.info("Workspace conflict: %s", exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


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

The revision is the full forty-character git SHA embedded in the package
      at build time. It is not a secret and contains nothing about configuration
      or credentials. It cannot be influenced by an environment variable or a
      request header, so a caller cannot make a stale build look current.
      """
    # Provenance is resolved first, and separately from the database. A build
    # that cannot name its own commit is not a healthy build, and it must not be
    # reported as a database problem: the detail has to say what is actually
    # wrong or the failure gets misdiagnosed as an outage.
    try:
        revision = build_revision()
    except ProvenanceError as exc:
        logger.error("Health check failed: no verified build identity: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "Build identity unavailable"},
        )

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
                content={"status": "ok", "revision": revision},
            )
        except Exception as exc:
            logger.warning("Health check failed: %s", exc)
            content = {
                "status": "error",
                "detail": "Database unreachable",
                "revision": revision,
            }
            if _db_init_error:
                content["init_error"] = _db_init_error
            return JSONResponse(status_code=503, content=content)


# NOTE: Legacy APScheduler is intentionally NOT started in production.
# Verification is triggered by the cloud cron job via /internal/verify/trigger.
# This prevents duplicate scheduler execution.


# The match router is registered before the scholarships router. Starlette
# resolves a path match with the wrong method as a *partial* match and keeps
# scanning, so the dynamic GET /scholarships/{scholarship_id} route would not
# actually shadow POST /scholarships/match. Registering match first makes that
# independence structural rather than dependent on the router's scan order.
app.include_router(match_router)
# The count intelligence router is registered before the scholarships router so its
# literal /v2/counts paths are resolved by their own router rather than being
# scanned past, and because the counting layer depends on the Match engine rather
# than the other way round.
app.include_router(counts_router)
# The supervisor router is registered before the scholarships router for the same
# reason the match router is: its paths are /scholarships/{id}/supervisors, so
# registering it first makes that independence structural rather than dependent on
# scan order.
app.include_router(supervisors_router)
app.include_router(scholarships_router)
app.include_router(verification_router)
app.include_router(admin_image_review_router)
app.include_router(admin_verification_router)
app.include_router(discovery_router)
app.include_router(admin_dashboard_router)
app.include_router(enrichment_router)
# The student dashboard is registered last and behind a session dependency, so
# it cannot shadow a public route and it resolves the caller from the session
# cookie rather than from anything the browser sends.
app.include_router(auth_router)
app.include_router(dashboard_router)
# The application workspace is registered last, behind the same session
# dependency as the dashboard. It owns no route that could shadow a public one:
# its literal prefix is /applications and its only dynamic segment follows it.
app.include_router(applications_router)
# The mentor is registered last of all, behind the same session dependency. Its
# prefix is /mentor and its routes are two literals, so it cannot shadow a
# public route - but registering it last keeps that structural rather than
# dependent on scan order, which is the same discipline the match router uses
# for /scholarships/match.
app.include_router(mentor_router)
# Supervisor outreach and email drafting sit behind the same session dependency as
# the dashboard and workspace. Their prefixes are /outreach and /supervisor-email
# with no public counterpart, so registering them last cannot shadow anything.
# No authentication router is added here: master already owns /auth.
app.include_router(outreach_router)
app.include_router(supervisor_email_router)


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
