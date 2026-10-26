"""Server-side student identity.

ScholarZone previously had no student identity at all: the only authenticated
principal was an administrator holding a shared secret. Supervisor outreach is
private per-student data, so it needs a real owner that the server derives itself
and never accepts from the client.

Three properties are load-bearing and are the reason this is not a token signed
with a secret:

* The session token is random, not a claim. It is stored server-side as a hash,
  so a session can be revoked and a stolen database does not hand over live
  sessions.
* The cookie is ``HttpOnly``, so page scripts cannot read it, and
  ``SameSite=lax``, which is what makes the unsafe methods below refuse a
  cross-site request without a second token mechanism.
* The student id is resolved from the cookie on every request. A body or query
  parameter naming a student is never an authority, so one student cannot reach
  another's records by asking for them.

Passwords use ``hashlib.scrypt`` from the standard library. No dependency was
added: the repository pins its requirements deliberately, and scrypt is a slow,
salted, memory-hard KDF that is sufficient here.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Student, StudentSession

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "sz_session"

#: Bounded so a hostile registration cannot turn password verification into a
#: memory-exhaustion vector, and so an unbounded body cannot become unbounded work.
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 200

#: Cost parameters. 128 * n * r bytes of memory per hash; deliberately modest
#: because login is on the interactive path.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 64 * 1024 * 1024
SCRYPT_DKLEN = 32

SESSION_TTL_DAYS = 30

#: Compared against when no student matched, so a missing account costs the same
#: work as a wrong password and cannot be detected by response timing.
_DUMMY_HASH = (
    "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA==$"
    "ZG8tbm90LWNvbXBhcmUtaGFzaC1vbmx5LTAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
)


class InvalidCredentialsError(Exception):
    """Raised when a login cannot be attributed to a student.

    Deliberately carries no detail. Distinguishing "no such account" from
    "wrong password" would turn registration into an account-existence oracle.
    """


def hash_password(password: str) -> str:
    """Return a self-describing scrypt digest for ``password``.

    The stored string carries its own cost parameters and salt, so raising the
    cost later does not make existing hashes unverifiable.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
        maxmem=SCRYPT_MAXMEM,
    )
    encode = base64.b64encode
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        encode(salt).decode("ascii"),
        encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    """Return whether ``password`` produced ``encoded``.

    A malformed or truncated stored hash returns ``False`` rather than raising:
    a row this function cannot understand must not authenticate anybody.
    """
    try:
        scheme, n_raw, r_raw, p_raw, salt_raw, digest_raw = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_raw)
        expected = base64.b64decode(digest_raw)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
            dklen=len(expected),
            maxmem=SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_session_token() -> tuple[str, str]:
    """Return ``(token, token_hash)`` for a new session.

    The plaintext token goes to the client in a cookie and is never persisted.
    Only its digest is stored, so the database cannot be replayed into sessions.
    """
    token = secrets.token_urlsafe(32)
    return token, hash_session_token(token)


def hash_session_token(token: str) -> str:
    # A plain digest, not a slow KDF: the token is already 256 bits of entropy,
    # so there is nothing to brute force, and login must stay cheap.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, student: Student) -> str:
    token, token_hash = generate_session_token()
    db.add(
        StudentSession(
            student_id=student.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS),
        )
    )
    db.commit()
    return token


def resolve_student(db: Session, token: str | None) -> Student | None:
    """Return the student owning ``token``, or ``None``.

    Expiry and revocation are both checked here rather than at write time, so a
    session that lapses stops working without needing a sweeper to notice.
    """
    if not token:
        return None
    row = db.execute(
        select(StudentSession).where(StudentSession.token_hash == hash_session_token(token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    expires_at = row.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
    return db.get(Student, row.student_id)


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    row = db.execute(
        select(StudentSession).where(StudentSession.token_hash == hash_session_token(token))
    ).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()


def authenticate(db: Session, email: str, password: str) -> Student:
    """Return the student for these credentials, or raise.

    Runs the same work on both failure paths so the answer cannot be inferred
    from how long the request took.
    """
    student = db.execute(
        select(Student).where(Student.email == normalize_email(email))
    ).scalar_one_or_none()
    if student is None:
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentialsError()
    if not verify_password(password, student.password_hash):
        raise InvalidCredentialsError()
    return student


def set_session_cookie(response: Response, token: str) -> None:
    from .config import get_settings

    secure = get_settings().environment == "production"
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def get_current_student(
    request: Request,
    db: Session = Depends(get_db),
) -> Student:
    """FastAPI dependency admitting only an authenticated student.

    Raises 401 rather than 403: without a valid session the caller has not
    established an identity, and a 403 would imply one exists. This mirrors
    ``require_admin_secret``, and keeps the two authentication surfaces
    independent - neither accepts the other's credential.
    """
    student = resolve_student(db, request.cookies.get(SESSION_COOKIE_NAME))
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return student


def get_optional_student(
    request: Request,
    db: Session = Depends(get_db),
) -> Student | None:
    """Like :func:`get_current_student`, but absence is not an error.

    Used only where the page renders differently for a signed-in visitor and
    still renders for everyone else.
    """
    return resolve_student(db, request.cookies.get(SESSION_COOKIE_NAME))


__all__ = [
    "SESSION_COOKIE_NAME",
    "SESSION_TTL_DAYS",
    "MIN_PASSWORD_LENGTH",
    "MAX_PASSWORD_LENGTH",
    "InvalidCredentialsError",
    "authenticate",
    "clear_session_cookie",
    "create_session",
    "get_current_student",
    "get_optional_student",
    "hash_password",
    "hash_session_token",
    "normalize_email",
    "resolve_student",
    "revoke_session",
    "set_session_cookie",
    "verify_password",
]