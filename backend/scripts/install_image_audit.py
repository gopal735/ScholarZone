"""Install the image mutation audit on production, and nothing else.

Runs the same idempotent statements the application already runs at startup.
Called explicitly because the audit is only useful once it exists: the trigger
that records an image mutation has to be in place before the next write.

This creates database objects and modifies no scholarship row. It inserts no
audit row, updates no image field, and touches no record other than through the
schema objects it creates. Re-running it is a no-op.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402
from app.image_audit import (  # noqa: E402
    AUDIT_TABLE,
    create_image_audit_schema,
)


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1

    with engine.begin() as connection:
        create_image_audit_schema(connection)
        table = connection.execute(
            text("SELECT count(*) FROM information_schema.tables "
                 "WHERE table_schema = 'public' AND table_name = :t"),
            {"t": AUDIT_TABLE},
        ).scalar()
        trigger = connection.execute(
            text("SELECT count(*) FROM pg_trigger "
                 "WHERE tgrelid = 'scholarships'::regclass "
                 "AND tgname = 'trg_scholarships_image_audit' AND NOT tgisinternal")
        ).scalar()
        rows = connection.execute(text(f"SELECT count(*) FROM {AUDIT_TABLE}")).scalar()

    print(f"  audit table installed: {'YES' if table else 'NO'}")
    print(f"  audit trigger armed:   {'YES' if trigger else 'NO'}")
    print(f"  audit rows so far:     {rows} (0 expected - no mutation was made)")
    return 0 if (table and trigger) else 1


if __name__ == "__main__":
    raise SystemExit(main())