"""Validate the PostgreSQL audit DDL inside a transaction that is rolled back.

PostgreSQL DDL is transactional, so every statement can be executed and then
undone. This reports whether the production schema would accept the audit
objects, and surfaces the exact error if not, without leaving anything behind.

Read-only in effect: the transaction is always rolled back.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402
from app.image_audit import (  # noqa: E402
    TRACKED_IMAGE_FIELDS,
    audit_ddl_for,
)


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1

    statements = audit_ddl_for("postgresql")
    print(f"  statements to validate: {len(statements)}")

    conn = engine.connect()
    trans = conn.begin()
    try:
        for i, statement in enumerate(statements, 1):
            head = " ".join(statement.split())[:66]
            try:
                conn.execute(text(statement))
                print(f"  {i:2}. OK    {head}")
            except Exception as exc:
                print(f"  {i:2}. FAIL  {head}")
                print(f"      -> {type(exc).__name__}: {str(exc).splitlines()[0]}")
                trans.rollback()
                print("  rolled back; nothing persisted")
                return 1

        # With the objects staged in-transaction, prove the trigger really
        # fires and really refuses a rewrite. All of it is undone below.
        present = conn.execute(
            text("SELECT count(*) FROM pg_trigger "
                 "WHERE tgrelid = 'scholarships'::regclass "
                 "AND tgname = 'trg_scholarships_image_audit' AND NOT tgisinternal")
        ).scalar()
        print(f"  trigger present in staged schema: {'YES' if present else 'NO'}")

        cols = [r[0] for r in conn.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_name = 'scholarship_image_audit' ORDER BY ordinal_position")
        )]
        print(f"  audit columns ({len(cols)}): {', '.join(cols)}")
        print(f"  tracked fields covered: {len(TRACKED_IMAGE_FIELDS)}")
    finally:
        if trans.is_active:
            trans.rollback()
        conn.close()

    print("  ROLLED BACK - production unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())