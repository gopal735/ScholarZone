"""Environment-driven application configuration."""

from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()


BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_DIRECTORY / 'scholarzone.db').as_posix()}"
DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def _split_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip().rstrip("/") for origin in value.split(",") if origin.strip())


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    allowed_origins: tuple[str, ...]
    resend_api_key: str | None = None
    verification_secret: str | None = None
    admin_secret: str | None = None
    # Public directory quality gate.
    #
    # When enabled, a scholarship is listed publicly only if it has been
    # verified and carries an image that passed image validation. This is a
    # deliberate product trade-off with a large, measurable cost: a record
    # whose official page simply has no findable logo becomes invisible rather
    # than being shown without one. It is a setting rather than a hardcoded
    # filter so the trade-off can be reversed without a code change, and so
    # what the gate hides is reportable rather than silently missing.
    public_require_verified: bool = True
    public_require_verified_image: bool = True


def get_settings() -> Settings:
    """Read non-secret configuration from the process environment.

    In production, SCHOLARZONE_DATABASE_URL is required and must point to a
    PostgreSQL (Neon) database. SQLite is never used as a fallback in
    production. For development and test environments, SQLite is used when
    the variable is unset.
    """
    environment = os.getenv("SCHOLARZONE_ENVIRONMENT", "development").strip().lower() or "development"

    if environment == "production":
        database_url = os.getenv("SCHOLARZONE_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError(
                "SCHOLARZONE_DATABASE_URL is required in production. "
                "Configure a PostgreSQL (Neon) connection string before starting the application."
            )
        if database_url.startswith("sqlite"):
            raise RuntimeError(
                "Production environment requires PostgreSQL (Neon), not SQLite. "
                "Set SCHOLARZONE_DATABASE_URL to a postgresql:// connection string."
            )
    else:
        database_url = os.getenv("SCHOLARZONE_DATABASE_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL

    allowed_origins = _split_origins(os.getenv("SCHOLARZONE_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS))
    if "https://gopal735.github.io" not in allowed_origins:
        allowed_origins = allowed_origins + ("https://gopal735.github.io",)

    return Settings(
        environment=environment,
        database_url=database_url,
        allowed_origins=allowed_origins,
        resend_api_key=os.getenv("RESEND_API_KEY"),
        verification_secret=os.getenv("SCHOLARZONE_VERIFICATION_SECRET"),
        admin_secret=os.getenv("SCHOLARZONE_ADMIN_SECRET"),
        public_require_verified=_as_bool(
            os.getenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED"), True
        ),
        public_require_verified_image=_as_bool(
            os.getenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"), True
        ),
    )
