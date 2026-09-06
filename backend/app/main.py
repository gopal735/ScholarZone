from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .database import close_database, init_database
from .routers.scholarships import router as scholarships_router
from .routers.verification import router as verification_router
from .routers.admin_image_review import router as admin_image_review_router
from .routers.discovery import router as discovery_router
from .routers.admin_dashboard import router as admin_dashboard_router
from .seed import seed_database


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    init_database()
    if settings.environment != "production":
        seed_database()
    else:
        logger.info("Skipping scholarship seeding in production; database is populated via migration.")
    yield
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
def health() -> dict[str, str]:
    return {"status": "ok"}


# NOTE: Legacy APScheduler is intentionally NOT started in production.
# Verification is triggered by the cloud cron job via /internal/verify/trigger.
# This prevents duplicate scheduler execution.


app.include_router(scholarships_router)
app.include_router(verification_router)
app.include_router(admin_image_review_router)
app.include_router(discovery_router)
app.include_router(admin_dashboard_router)
