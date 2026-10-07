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
    public_require_verified: bool = False
    public_require_verified_image: bool = False
    # The image gate hides a record when it has no *verified official* image.
    #
    # A third-party-hosted image (currently Wikimedia) is not an official
    # image and must never satisfy this gate. If the owner later wants those
    # records listed, that is an explicit product decision made here, not
    # something the resolver may decide for itself.
    public_allow_third_party_image: bool = False
    # Whether the bounded Supervisor discovery trigger may run at all.
    #
    # This is a *discovery execution* switch and nothing else. It gates one
    # endpoint that runs supervisor discovery for one named scholarship. It does
    # not enable browser rendering, and it is not the same switch as
    # SCHOLARZONE_SUPERVISOR_RENDER_ENABLED, which is read by
    # app.services.supervisor_render and governs whether a client-side directory
    # may be rendered with a browser at all.
    #
    # They are kept apart on purpose. Conflating them would mean that turning on
    # discovery also turned on Playwright in production, which is a far larger
    # change in blast radius than "run one discovery pass". Turning this on does
    # not make the renderer available, and turning the renderer on does not make
    # this endpoint reachable.
    #
    # Default OFF in every environment. An unconfigured deployment refuses the
    # trigger, so the capability is opt-in rather than something a deploy
    # inherits by being reachable.
    supervisor_discovery_enabled: bool = False


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
    # GitHub Pages stays in the allowed set while it remains the rollback path.
    # A Vercel preview origin is added as well, because every preview deployment
    # gets its own unique host and the frontend E2E checks have to be able to
    # call the API from one. Credentials are enabled on this middleware, so the
    # list is explicit origins and never "*".
    if "https://gopal735.github.io" not in allowed_origins:
        allowed_origins = allowed_origins + ("https://gopal735.github.io",)

    # Named deployments, listed explicitly. VERCEL_URL only covers whichever
    # host the current build is on, so the production frontend and the current
    # preview are both named here and are not dependent on that variable being
    # set at build time.
    for fixed in (
        "https://scholarzone-fwzj.vercel.app",
        "https://scholarzone.vercel.app",
    ):
        if fixed not in allowed_origins:
            allowed_origins = allowed_origins + (fixed,)

    vercel_origin = os.getenv("VERCEL_URL", "").strip().removeprefix("https://").strip()
    if vercel_origin and f"https://{vercel_origin}" not in allowed_origins:
        allowed_origins = allowed_origins + (f"https://{vercel_origin}",)

    return Settings(
        environment=environment,
        database_url=database_url,
        allowed_origins=allowed_origins,
        resend_api_key=os.getenv("RESEND_API_KEY"),
        verification_secret=os.getenv("SCHOLARZONE_VERIFICATION_SECRET"),
        # The deployment already provisions SCHOLARZONE_VERIFICATION_SECRET, but
        # only this name was ever read here, so admin_secret resolved to None and
        # every administrator endpoint refused everyone - including the real
        # administrator. The existing secret is reused rather than replaced: no
        # new credential, no rotation, and nothing printed or committed. An
        # explicitly provided SCHOLARZONE_ADMIN_SECRET still takes precedence.
admin_secret=os.getenv("SCHOLARZONE_ADMIN_SECRET")
          or os.getenv("SCHOLARZONE_VERIFICATION_SECRET"),
        public_require_verified=_as_bool(
            os.getenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED"), False
        ),
        public_require_verified_image=_as_bool(
            os.getenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"), False
        ),
        public_allow_third_party_image=_as_bool(
            os.getenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE"), False
        ),
        supervisor_discovery_enabled=_as_bool(
            os.getenv("SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED"), False
        ),
    )
