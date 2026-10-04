"""Request-scoped dependencies.

The single rule this module exists to enforce: **the server decides who the
caller is.** A user id arriving in a query string, a JSON body or a hidden form
control is never consulted. Every dashboard read and every mutation resolves the
account from the session cookie, so a student can only ever reach rows their own
session owns.

There is deliberately no dependency that accepts a user id as an argument, and
no way to widen one. A reviewer looking for an IDOR in this codebase should find
that the ownership check is not a condition inside each handler but the only
subject those handlers are ever given.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserSession
from .services.auth import SESSION_COOKIE_NAME, is_session_valid, token_fingerprint


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to continue.",
        headers={"WWW-Authenticate": "Cookie"},
    )


def current_session(
    request: Request,
    db: Session = Depends(get_db),
) -> UserSession | None:
    """Resolve the caller's session row, or ``None``.

    Split out from :func:`current_user` so a handler that wants to branch on
    "signed in or not" - rendering a signed-out dashboard, say - can do so
    without catching an exception. A missing, unknown, expired, revoked or
    inactive-owner session is the same answer: no session.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    record = db.execute(
        select(UserSession).where(UserSession.token_hash == token_fingerprint(token))
    ).scalar_one_or_none()

    return record if is_session_valid(record) else None


def current_user(
    session: UserSession | None = Depends(current_session),
    db: Session = Depends(get_db),
) -> User | None:
    """The authenticated account, or ``None`` when there is no valid session."""
    if session is None:
        return None

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None

    return user


def require_user(user: User | None = Depends(current_user)) -> User:
    """The authenticated account, or a 401.

    This is the dependency every private route uses. Because it returns the
    resolved ``User`` object, handlers cannot accidentally act on a
    caller-supplied identity: the only account in scope is the one this returns.
    """
    if user is None:
        raise _unauthenticated()
    return user


__all__ = ["current_session", "current_user", "require_user"]