"""Provision a disposable PostgreSQL test-database identity marker.

Used only by the dedicated CI closed-deletion job. Reads all configuration
from environment variables. Never prints secrets.
"""

from __future__ import annotations

import os
import sys

# Make backend importable when run from repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import psycopg2

from app.test_db_safety import (
    validate_disposable_postgres_url,
    verify_disposable_db_identity,
    verify_expected_pg_version,
)


def main() -> int:
    allow = os.environ.get("SCHOLARZONE_ALLOW_DESTRUCTIVE_TEST_DB")
    url = os.environ.get("PROVISION_DATABASE_URL") or os.environ.get("TEST_POSTGRESQL_URL")
    if not url:
        print("PROVISION_DATABASE_URL/TEST_POSTGRESQL_URL is required", file=sys.stderr)
        return 1

    expected_port = int(os.environ.get("PROVISION_DB_PORT", "0")) or None
    # 1. Validate URL before any connection.
    try:
        validate_disposable_postgres_url(url, allow, expected_port)
    except Exception as exc:  # noqa: BLE001
        print(f"invalid provisioning URL: {exc}", file=sys.stderr)
        return 1

    run_id = os.environ.get("SCHOLARZONE_EXPECTED_DB_RUN_ID")
    digest = os.environ.get("SCHOLARZONE_EXPECTED_DB_MARKER_DIGEST")
    expected_version = os.environ.get("SCHOLARZONE_EXPECTED_PG_VERSION_NUM")
    if not run_id or not digest:
        print("missing run id or digest", file=sys.stderr)
        return 1

    # Parse validated URL.
    from sqlalchemy.engine import make_url

    u = make_url(url)
    host = u.host or "localhost"
    port = u.port or 5432
    user = u.username or "test"
    password = u.password or "test"
    dbname = u.database or "scholarzone_test"

    conn = None
    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
        # 2. Verify identity BEFORE any DDL/DML.
        class _Conn:
            def __init__(self, c):
                self._c = c

            def execute(self, stmt):
                cur = self._c.cursor()
                cur.execute(str(stmt))
                return cur

        # Use a lightweight adapter exposing fetchone/fetchall via cursor.
        adapter = _ProvisionConn(conn)
        verify_disposable_db_identity(adapter, dbname)
        verify_expected_pg_version(adapter, expected_version)

        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS sz_test_instance_attestation "
                "(run_id text NOT NULL, marker_digest text NOT NULL, "
                "created_at timestamptz DEFAULT now())"
            )
            cur.execute("TRUNCATE sz_test_instance_attestation")
            cur.execute(
                "INSERT INTO sz_test_instance_attestation (run_id, marker_digest) "
                "VALUES (%s, %s)",
                (run_id, digest),
            )
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"provisioning failed: {exc}", file=sys.stderr)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
    return 0


class _ProvisionConn:
    """Adapter exposing SQLAlchemy-like execute() over psycopg2."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, stmt):
        cur = self._conn.cursor()
        cur.execute(str(stmt))
        # Wrap cursor to provide fetchone/fetchall
        return _CursorWrapper(cur)


class _CursorWrapper:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


if __name__ == "__main__":
    raise SystemExit(main())
