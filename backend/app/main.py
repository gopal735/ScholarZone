from contextlib import asynccontextmanager
import logging
import os
import re
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
    try:
        init_database()
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        _db_ready = True
    except Exception as exc:
        logger.exception("Database initialization failed: %s", exc)
        _db_init_error = str(exc)
        _db_ready = False
        return
    settings = get_settings()
    if settings.environment != "production":
        try:
            seed_database()
        except Exception:
            logger.exception("Database seeding failed", exc_info=True)
    else:
        logger.info("Skipping scholarship seeding in production; database is populated via migration.")


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
        if not _db_ready:
            detail = _db_init_error or "Database not ready"
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": detail, "revision": build_revision()},
            )
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return JSONResponse(
                status_code=200, content={"status": "ok", "revision": build_revision()}
            )
        except Exception as exc:
            logger.warning("Health check failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "Database unreachable",
                         "revision": build_revision()},
            )


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
