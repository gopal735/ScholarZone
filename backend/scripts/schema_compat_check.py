#!/usr/bin/env python3
"""Verify application models and production database schema are compatible."""

import os
import sys
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REQUIRED_IMAGE_FIELDS = {
    "image_url",
    "image_kind",
    "image_source_type",
    "image_verified_at",
    "image_source_url",
}


def get_model_columns() -> dict[str, set[str]]:
    from app.models import Base

    columns = {}
    for table in Base.metadata.tables.values():
        columns[table.name] = {c.name for c in table.columns}
    return columns


def get_db_columns(engine) -> dict[str, set[str]]:
    inspector = inspect(engine)
    db_columns = {}
    for table_name in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        db_columns[table_name] = cols
    return db_columns


def main() -> int:
    db_url = os.environ.get("SCHOLARZONE_DATABASE_URL")
    if not db_url:
        default_db = os.path.join(BACKEND_DIR, "scholarzone.db")
        db_url = f"sqlite:///{default_db}"

    engine = create_engine(db_url)
    model_cols = get_model_columns()
    db_cols = get_db_columns(engine)

    dialect = engine.dialect.name
    print(f"Database dialect: {dialect}")
    print(f"Database URL: {db_url.split('://')[0]}://***\n")

    all_ok = True
    scholarships_exists = "scholarships" in db_cols

    for table, cols in model_cols.items():
        if table not in db_cols:
            print(f"[WARN] Table {table} not found in database (will be created by startup migration)")
            continue
        missing_in_db = cols - db_cols[table]
        extra_in_db = db_cols[table] - cols
        if missing_in_db:
            print(f"[FAIL] Table {table} missing columns in DB: {sorted(missing_in_db)}")
            all_ok = False
        else:
            print(f"[PASS] Table {table} columns present in DB")
        if extra_in_db:
            print(
                f"[WARN] Table {table} has extra DB columns not in model: {sorted(extra_in_db)}"
            )

    if not scholarships_exists:
        print("\n[WARN] scholarships table does not exist yet - schema migration has not run")
        print("  This is expected for a fresh database. The startup migration will create tables.")
        print("  Image field checks skipped until tables exist.")
    else:
        scholarships_db = db_cols.get("scholarships", set())
        for field in REQUIRED_IMAGE_FIELDS:
            if field in scholarships_db:
                print(f"[PASS] Image field present in DB: {field}")
            else:
                print(f"[FAIL] Image field missing in DB: {field}")
                all_ok = False

        if dialect == "sqlite":
            print("\nSQLite idempotent migration check:")
            missing = REQUIRED_IMAGE_FIELDS - scholarships_db
            if missing:
                print(f"  Would add columns via ALTER TABLE: {sorted(missing)}")
            else:
                print("  All required image columns already present.")

    if all_ok:
        print("\nSCHEMA COMPATIBILITY: PASS")
        return 0
    print("\nSCHEMA COMPATIBILITY: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
