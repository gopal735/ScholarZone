"""Run the closed-record audit with the connection itself forced read-only.

The audit script only issues SELECTs. This wrapper adds a second, independent
guarantee: the PostgreSQL session is put into a read-only transaction by the
driver, so even a bug in the audit - or a future edit that introduced a write -
is refused by the database rather than by our own discipline.

It lives in its own file rather than inline in the workflow because a heredoc
nested inside a YAML block scalar is a well-known source of indentation bugs
that only show up in CI.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


def _force_read_only_dsn(dsn: str) -> str:
    """Append ``default_transaction_read_only=on`` to the DSN.

    Applied only when the DSN does not already set ``options``, so an operator
    who has deliberately configured session options is not overridden.
    """
    if "options=" in dsn:
        return dsn
    separator = "&" if "?" in dsn else "?"
    return f"{dsn}{separator}options=-c%20default_transaction_read_only%3Don"


def main() -> int:
    dsn = os.environ.get("SCHOLARZONE_DATABASE_URL", "").strip()
    if not dsn:
        print(
            "SCHOLARZONE_DATABASE_URL is not set. This audit runs against the "
            "configured production database and refuses to guess one.",
            file=sys.stderr,
        )
        return 2

    os.environ["SCHOLARZONE_DATABASE_URL"] = _force_read_only_dsn(dsn)

    from scripts.closed_record_audit import main as audit_main

    return audit_main()


if __name__ == "__main__":
    raise SystemExit(main())
