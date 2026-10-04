"""Server-side administrator authorization.

ScholarZone has one administration model, and this module is its single
implementation: a shared secret presented in the ``X-Admin-Secret`` request
header and compared against ``SCHOLARZONE_ADMIN_SECRET``.

The secret is never accepted from the client as a decision input, never compared
with ``==`` (which leaks length and prefix through timing), and never trusted
because a UI happened to render. Authorization is decided here, on the server,
before a handler sees a row.

When no secret is configured the answer is always "no". Failing closed matters
more than convenience: a deployment that forgets to set the variable must not
silently expose the verification queue.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException, status

from .config import get_settings

logger = logging.getLogger(__name__)

ADMIN_SECRET_HEADER = "X-Admin-Secret"


def admin_secret_is_valid(provided_secret: str | None) -> bool:
    """Return whether the presented secret matches the configured one.

    Uses ``secrets.compare_digest`` so a wrong guess cannot be refined by
    measuring how long the rejection took.
    """
    expected = getattr(get_settings(), "admin_secret", None)
    if not expected or not provided_secret:
        return False
    return secrets.compare_digest(provided_secret, expected)


def require_admin_secret(
    x_admin_secret: str | None = Header(None, alias=ADMIN_SECRET_HEADER),
) -> str:
    """FastAPI dependency that admits only an authenticated administrator.

    Raises 401 rather than 403: without a valid secret the caller has not
    established an identity at all, and a 403 would imply one exists.
    """
    if admin_secret_is_valid(x_admin_secret):
        return x_admin_secret
    logger.warning("Rejected unauthenticated administrator request.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Administrator authentication required.",
        headers={"WWW-Authenticate": ADMIN_SECRET_HEADER},
    )


__all__ = [
    "ADMIN_SECRET_HEADER",
    "admin_secret_is_valid",
    "require_admin_secret",
]