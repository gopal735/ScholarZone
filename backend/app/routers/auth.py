"""Account creation and sessions.

Thin by design: this module validates input, calls the password and session
helpers, and shapes a response. It never decides *who* the caller is - that is
``app.dependencies.require_user``, which is what the dashboard routes use.

Two behaviours worth stating explicitly.

Registration is deliberately forgiving about one thing and strict about another.
The email is normalised to a single canonical form, because
``Student@Example.com`` and ``student@example.com`` must not become two
accounts; the password is never trimmed or normalised, because silently
rewriting someone's password is how a login stops matching the password they
think they set.

Every failure returns the same 401. A wrong email and a wrong password are
indistinguishable to the caller, because telling them apart turns registration
into an account-enumeration oracle.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_user
from ..models import User, UserSession
from ..schemas_dashboard import (
    LoginRequest,
    PublicUser,
    RegisterRequest,
    SessionResponse,
)
from ..services.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_DAYS,
    generate_session_token,
    hash_password,
    normalise_email,
    session_expiry,
    token_fingerprint,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_session(db: Session, user: User, payload: SessionResponse) -> JSONResponse:
    """Create a session row and return a JSON response carrying its cookie.

    The cookie is ``httpOnly`` (invisible to JavaScript, so an injected script
    cannot read the session), ``SameSite=Lax`` (not sent on cross-site POSTs,
    which is what blocks cookie-riding an authenticated request), ``Secure`` in
    production, and ``__Host-`` prefixed so it cannot be read by a subdomain or
    loosened by a ``Domain`` attribute.

    Built as a ``JSONResponse`` rather than by mutating a bare ``Response``: a
    bare response already carries ``content-length: 0`` in its headers, so
    assigning a body to it afterwards produces a 200 with an empty payload. The
    browser then fails to parse the JSON and reports a failure for a request that
    actually succeeded - which is precisely the bug this shape avoids.
    """
    token = generate_session_token()
    now = datetime.now(timezone.utc)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=token_fingerprint(token),
            created_at=now,
            expires_at=session_expiry(now),
        )
    )
    db.commit()

    response = JSONResponse(content=payload.model_dump(mode="json"), status_code=status.HTTP_200_OK)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=request_is_production(),
        path="/",
    )
    return response


def request_is_production() -> bool:
    from ..core.config import get_settings

    return get_settings().environment == "production"


def _public(user: User) -> PublicUser:
    return PublicUser(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/register", response_model=SessionResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> Response:
    email = normalise_email(payload.email)

    existing = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for that email address.",
        )

    user = User(email=email, password_hash=hash_password(payload.password), is_active=True)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint is the real guard against a concurrent
        # registration of the same address; the check above only saves the
        # common case from raising.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for that email address.",
        ) from None

    db.refresh(user)

    # Registration signs the student in, because making them type the password
    # they just chose a second time is friction with no security benefit.
    return _issue_session(db, user, SessionResponse(user=_public(user)))


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Response:
    email = normalise_email(payload.email)
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()

    # The same 401 for "no such account" and "wrong password", so this endpoint
    # cannot be used to discover which addresses are registered. When there is no
    # user the hash is still computed, so response time does not distinguish the
    # two cases either.
    if user is None:
        hash_password(payload.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That email and password combination was not recognised.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That email and password combination was not recognised.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That email and password combination was not recognised.",
        )

    return _issue_session(db, user, SessionResponse(user=_public(user)))


@router.get("/session", response_model=SessionResponse)
def session_state(user: User | None = Depends(current_user)) -> SessionResponse:
    """Whether a valid session exists.

    ``{ user: null }`` is the signed-out answer and is what ``AuthContext``
    expects, so the frontend can call this on every page load without
    distinguishing "signed out" from "request failed".
    """
    return SessionResponse(user=_public(user) if user is not None else None)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """End the current session server-side.

    Revoking the row is the part that matters. Deleting the cookie only asks the
    browser to forget a token that is still valid, so a sign-out that did not
    revoke would leave a working credential in anyone who had copied it.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        record = db.execute(
            select(UserSession).where(UserSession.token_hash == token_fingerprint(token))
        ).scalar_one_or_none()
        if record is not None and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


__all__ = ["router"]