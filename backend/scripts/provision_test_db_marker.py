"""Provision a disposable PostgreSQL test-database identity marker.

Used only by the dedicated CI closed-deletion job. Reads all configuration
from environment variables. Never prints secrets.
"""

from __future__ import annotations

import os
import sys

import psycopg2


def main() -> int:
    host = os.environ.get("PROVISION_DB_HOST", "localhost")
    port = int(os.environ.get("PROVISION_DB_PORT", "5440"))
    user = os.environ.get("PROVISION_DB_USER", "test")
    password = os.environ.get("PROVISION_DB_PASSWORD", "test")
    dbname = os.environ.get("PROVISION_DB_NAME", "scholarzone_test")
    run_id = os.environ.get("SCHOLARZONE_EXPECTED_DB_RUN_ID")
    digest = os.environ.get("SCHOLARZONE_EXPECTED_DB_MARKER_DIGEST")
    if not run_id or not digest:
        print("missing run id or digest", file=sys.stderr)
        return 1
    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
    try:
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
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
