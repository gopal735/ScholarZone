"""Probe the real append-only enforcement, then roll everything back.

Reports three separate things, because they are not the same:

  * privilege   - what PostgreSQL grants the connected role
  * guard       - whether an actual UPDATE/DELETE/TRUNCATE is rejected
  * owner       - whether the connected role owns the table

A table owner cannot have its own privileges revoked in PostgreSQL, so onNeon,
where the application connects as the owner, privilege denial is not reachable.
The guard trigger is therefore the real enforcement. This script proves what the
guard does rather than assuming it.

Every statement runs inside one transaction that is always rolled back. Row
counts are compared before and after to demonstrate nothing changed.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402

AUDIT = "scholarship_image_audit"


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1

    conn = engine.connect()
    trans = conn.begin()
    try:
        role = conn.execute(text("SELECT current_user")).scalar()
        owner = conn.execute(
            text("SELECT tableowner FROM pg_tables "
                 "WHERE schemaname='public' AND tablename=:t"), {"t": AUDIT},
        ).scalar()
        print(f"  connected role : {role}")
        print(f"  table owner    : {owner}")
        print(f"  role is owner  : {'YES' if role == owner else 'no'}")

        before = conn.execute(text(f"SELECT count(*) FROM {AUDIT}")).scalar()
        print(f"  audit rows before: {before}")

        print("  guards present on the audit table:")
        for trg, definition in conn.execute(text(
            "SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger "
            "WHERE tgrelid = :t::regclass AND NOT tgisinternal ORDER BY tgname"
        ), {"t": AUDIT}):
            fires = "ROW" if "FOR EACH ROW" in definition else "STATEMENT"
            when = "BEFORE" if definition.strip().startswith("BEFORE") else "AFTER"
            print(f"    {trg}: {when} {fires}")

        for label, sql in (
            ("UPDATE", f"UPDATE {AUDIT} SET writer_context = 'probe'"),
            ("DELETE", f"DELETE FROM {AUDIT}"),
            ("TRUNCATE", f"TRUNCATE {AUDIT}"),
        ):
            try:
                conn.execute(text(sql))
                print(f"  {label:9}: NOT BLOCKED  <-- gap")
            except Exception as exc:
                first = str(exc).splitlines()[0][:90]
                print(f"  {label:9}: blocked ({first})")

        after = conn.execute(text(f"SELECT count(*) FROM {AUDIT}")).scalar()
        print(f"  audit rows after : {after} (unchanged: {before == after})")
    finally:
        if trans.is_active:
            trans.rollback()
        conn.close()

    print("  ROLLED BACK - no audit row was altered or removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())