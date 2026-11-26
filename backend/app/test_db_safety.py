"""Safety guards for disposable PostgreSQL integration test fixtures."""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy import text

APPROVED_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
APPROVED_TEST_DB_NAMES = {"scholarzone_test"}
APPROVED_SERVER_ADDRESSES = {"", "127.0.0.1", "::1", "localhost", None}


def validate_disposable_postgres_url(url: str, allow_flag: str | None) -> None:
    """Validate a PostgreSQL URL before any destructive test operation.

    Raises RuntimeError on any validation failure.
    """
    if allow_flag != "1":
        raise RuntimeError("SCHOLARZONE_ALLOW_DESTRUCTIVE_TEST_DB must be set to 1")
    if not url:
        raise RuntimeError("TEST_POSTGRESQL_URL is required")
    try:
        u = make_url(url)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"malformed database URL: {exc}") from exc
    if u.drivername not in ("postgresql", "postgresql+psycopg2", "postgresql+psycopg"):
        raise RuntimeError(f"non-PostgreSQL driver: {u.drivername}")
    host = u.host
    if not host:
        raise RuntimeError("database URL is missing a hostname")
    if host not in APPROVED_LOOPBACK_HOSTS:
        raise RuntimeError(f"non-loopback or unapproved host: {host}")
    db = u.database
    if db not in APPROVED_TEST_DB_NAMES:
        raise RuntimeError(f"database name is not an approved disposable test database: {db}")
    # Explicitly reject localhost.* lookalikes (already excluded by exact set, but assert)
    if host.startswith("localhost.") or host.startswith("localhost-"):
        raise RuntimeError(f"spoofed localhost hostname rejected: {host}")


def _is_approved_server_address(addr: str) -> bool:
    """Allow loopback and private (RFC1918) addresses used by local/CI containers."""
    if addr in {"", "127.0.0.1", "::1", "localhost"}:
        return True
    # RFC1918 private ranges
    if addr.startswith("10."):
        return True
    if addr.startswith("192.168."):
        return True
    if addr.startswith("172."):
        parts = addr.split(".")
        if len(parts) >= 2:
            try:
                second = int(parts[1])
            except ValueError:
                return False
            if 16 <= second <= 31:
                return True
    return False


def verify_disposable_db_identity(connection: Any, expected_dbname: str) -> None:
    """Verify the actually connected database before destructive SQL.

    Raises RuntimeError on mismatch.
    """
    row = connection.execute(
        text("SELECT current_database(), inet_server_addr()::text, current_setting('server_version_num')")
    ).fetchone()
    if row is None:
        raise RuntimeError("could not query database identity")
    actual_db = row[0]
    actual_addr = row[1]
    if actual_db != expected_dbname:
        raise RuntimeError(
            f"unexpected current_database(): {actual_db!r} != {expected_dbname!r}"
        )
    addr = (actual_addr or "").split("/")[0]
    if not _is_approved_server_address(addr):
        raise RuntimeError(f"unexpected server address: {actual_addr!r}")
