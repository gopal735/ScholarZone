"""Safety guards for disposable PostgreSQL integration test fixtures."""

from __future__ import annotations

import hmac

from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy import text

APPROVED_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
APPROVED_TEST_DB_PORTS = {5432, 5433, 5434, 5439, 5440}
APPROVED_TEST_DB_NAMES = {"scholarzone_test"}
APPROVED_SERVER_ADDRESSES = {"", "127.0.0.1", "::1", "localhost", None}


def validate_disposable_postgres_url(url: str, allow_flag: str | None, expected_port: int | None = None) -> None:
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
    if expected_port is not None and u.port != expected_port:
        raise RuntimeError(f"unexpected port: {u.port} != {expected_port}")
    if u.port is not None and u.port not in APPROVED_TEST_DB_PORTS:
        raise RuntimeError(f"unapproved port: {u.port}")
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


def verify_disposable_db_marker(connection: Any, expected_run_id: str | None, expected_digest: str | None) -> None:
    """Verify the independently provisioned per-job attestation marker."""
    if not expected_run_id or not expected_digest:
        raise RuntimeError("expected database marker identity is not configured")
    try:
        row = connection.execute(
            text("SELECT run_id, marker_digest FROM sz_test_instance_attestation")
        ).fetchone()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"could not read database attestation marker: {exc}") from exc
    if row is None:
        raise RuntimeError("database attestation marker is missing")
    actual_run_id = row[0]
    actual_digest = row[1]
    if actual_run_id != expected_run_id:
        raise RuntimeError("database attestation run id mismatch")
    if not hmac.compare_digest(str(actual_digest), str(expected_digest)):
        raise RuntimeError("database attestation marker digest mismatch")


def verify_expected_pg_version(connection: Any, expected_version_num: str | None) -> None:
    if not expected_version_num:
        return
    row = connection.execute(text("SELECT current_setting('server_version_num')")).fetchone()
    actual = str(row[0]) if row else ""
    expected = str(expected_version_num)
    if actual[:2] != expected[:2]:
        raise RuntimeError(
            f"unexpected PostgreSQL version: {actual} != {expected}"
        )
