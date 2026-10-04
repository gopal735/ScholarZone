"""Password hashing and session tokens for student accounts.

Two decisions are load-bearing here.

**No new dependency.** ``passlib``/``bcrypt``/``argon2`` would all be reasonable
choices, and each one is a compiled or vendored cryptography package that becomes
a permanent supply-chain and upgrade obligation for a project that currently has
none. ``hashlib.pbkdf2_hmac`` is in the standard library, is the primitive FIPS
198 and RFC 8018 specify, and is what OpenSSL implements natively. The
iteration count is the security parameter, not the library.

**Sessions are stored, not signed.** The browser receives an opaque 256-bit
random token; the database keeps only its SHA-256 fingerprint. A signed
stateless token cannot be revoked before it expires, so signing a student out
would be a lie, and it would put account state in a bearer string. Storing the
fingerprint costs one row per session and makes sign-out real.

The password digest is encoded as a single self-describing string so the
iteration count and salt travel with it::

    pbkdf2_sha256$<iterations>$<salt_b64>$<digest_b64>

Verifying re-reads those parameters rather than assuming today's constants,
which means raising ``PBKDF2_ITERATIONS`` later does not lock out every account
registered before the change.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

#: 600,000 iterations is the OWASP-recommended floor for PBKDF2-HMAC-SHA256.
#: It costs roughly 0.3s per verification on commodity serverless hardware,
#: which is the point: it makes an offline cracking of a leaked table expensive
#: without making a real sign-in feel broken.
PBKDF2_ITERATIONS = 600_000
PBKDF2_ALGORITHM = "sha256"
SALT_BYTES = 16
DIGEST_BYTES = 32

#: Session lifetime. Long enough that a student is not signing in daily, short
#: enough that a stolen cookie has a bounded useful life.
SESSION_TTL_DAYS = 30

#: The cookie the browser is given. ``__Host-`` requires Secure and forbids
#: Domain, so it cannot be weakened by a subdomain or read by a sibling origin.
SESSION_COOKIE_NAME = "scholarzone_session"


def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2 digest for ``password``."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM, password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=DIGEST_BYTES
    )
    return "$".join(
        (
            "pbkdf2_sha256",
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    """Check ``password`` against a stored digest.

    Returns ``False`` rather than raising for a malformed digest: a row that
    cannot be parsed is a credential that does not verify, and treating it as
    anything else would turn a corrupt record into an authentication bypass.
    """
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM, password.encode("utf-8"), salt, int(iterations), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    # Constant-time: a byte-by-byte comparison leaks how much of a digest
    # matched, which is enough to narrow a search.
    return hmac.compare_digest(candidate, expected)


def generate_session_token() -> str:
    """Return a fresh opaque session token for the cookie."""
    return secrets.token_urlsafe(32)


def token_fingerprint(token: str) -> str:
    """Return the value stored in ``user_sessions.token_hash``.

    A plain digest, not a keyed MAC: the input already has 256 bits of entropy
    from ``secrets``, so there is nothing to brute force and therefore nothing
    for a key to protect. Hashing rather than storing the token means a
    database disclosure does not yield usable cookies.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalise_email(email: str) -> str:
    """Canonical form of an address for storage and comparison.

    Email addresses are case-insensitive in practice. Storing one canonical
    form is what lets the unique constraint prevent a duplicate account; the
    alternative is a functional index that both dialects would have to support.
    """
    return email.strip().lower()


def session_expiry(now: datetime | None = None) -> datetime:
    """When a session created now stops being valid."""
    reference = now or datetime.now(timezone.utc)
    return reference + timedelta(days=SESSION_TTL_DAYS)


def is_session_valid(record, now: datetime | None = None) -> bool:
    """Whether a ``UserSession`` row may still authenticate a request.

    Expiry is compared against an explicit ``now`` so the rule is testable and
    so the whole codebase keeps using one clock, injected the same way the
    matching engine takes its ``as_of``.
    """
    if record is None or record.revoked_at is not None:
        return False
    reference = now or datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at is None:
        return False
    # SQLite hands back naive datetimes for a tz-aware column; a naive
    # comparison against an aware ``now`` raises rather than returning a
    # verdict, so both sides are normalised before comparing.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > reference


__all__ = [
    "SESSION_COOKIE_NAME",
    "SESSION_TTL_DAYS",
    "generate_session_token",
    "hash_password",
    "is_session_valid",
    "normalise_email",
    "session_expiry",
    "token_fingerprint",
    "verify_password",
]