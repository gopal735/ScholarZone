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


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    allowed_origins: tuple[str, ...]
    resend_api_key: str | None = None
    verification_secret: str | None = None
    admin_secret: str | None = None


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

    return Settings(
        environment=environment,
        database_url=database_url,
        allowed_origins=_split_origins(os.getenv("SCHOLARZONE_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)),
        resend_api_key=os.getenv("RESEND_API_KEY"),
        verification_secret=os.getenv("SCHOLARZONE_VERIFICATION_SECRET"),
        admin_secret=os.getenv("SCHOLARZONE_ADMIN_SECRET"),
    )
