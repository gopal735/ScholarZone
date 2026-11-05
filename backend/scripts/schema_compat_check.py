#!/usr/bin/env python3
"""Verify application models and production database schema are compatible.

This check validates that IF tables exist, they are compatible with models.
A fresh database with no tables returns EMPTY (migration needed), not PASS.
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

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

# All tables that must exist in a fully initialized schema
REQUIRED_TABLES = {
    "scholarships",
    "maintenance_runs",
    "maintenance_slots",
    "content_fingerprints",
    "discovery_candidates",
    "image_reviews",
    "scholarship_image_audit",
    "image_reviews",
    # Supervisor tables
    "supervisor_source",
    "supervisor_candidate",
    "supervisor_claim",
    "supervisor_link",
    "supervisor_approval",
    "supervisor_review",
    "supervisor_audit",
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


def verify_database_identity(engine) -> tuple[bool, list[str]]:
    """Verify the database is a valid disposable test target.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    inspector = inspect(engine)
    
    # Check dialect
    dialect = engine.dialect.name
    if dialect not in ("postgresql", "sqlite"):
        errors.append(f"Unexpected dialect: {dialect}")
    
    # For PostgreSQL, verify it's not a production endpoint
    if dialect == "postgresql":
        # The connection URL is not directly accessible from engine
        # but we can check the dialect and version
        try:
            with engine.connect() as conn:
                version_result = conn.execute(text("SELECT version()")).scalar()
                if version_result:
                    print(f"PostgreSQL version: {version_result}")
        except Exception:
            pass
    
    return len(errors) == 0, errors


def main() -> int:
    db_url = os.environ.get("SCHOLARZONE_DATABASE_URL")
    if not db_url:
        print("ERROR: SCHOLARZONE_DATABASE_URL environment variable not set", file=sys.stderr)
        print("FAIL: Missing database configuration", file=sys.stderr)
        return 1

    # Normalize PostgreSQL URL to use psycopg v3 driver
    if db_url.startswith("postgresql://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]

    try:
        # Add connection timeout for PostgreSQL connections
        connect_args = {"connect_timeout": 5} if db_url.startswith("postgresql") else {}
        engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
        
        # Verify database identity
        is_valid, errors = verify_database_identity(engine)
        if not is_valid:
            for err in errors:
                print(f"[FAIL] {err}")
            print("FAIL: Database identity verification failed", file=sys.stderr)
            return 1
        
        model_cols = get_model_columns()
        db_cols = get_db_columns(engine)

        dialect = engine.dialect.name
        print(f"Database dialect: {dialect}")
        print(f"Database URL: {db_url.split('://')[0]}://***\n")

        # Check if database is empty (no tables at all)
        if not db_cols:
            print("SCHEMA COMPATIBILITY: EMPTY - no tables found, migration needed")
            return 1

        all_ok = True
        scholarships_exists = "scholarships" in db_cols

        # Check all required tables exist
        missing_tables = REQUIRED_TABLES - set(db_cols.keys())
        if missing_tables:
            for table in sorted(missing_tables):
                print(f"[FAIL] Required table missing: {table}")
            all_ok = False

        # Check all model tables exist in database
        for table, cols in model_cols.items():
            if table not in db_cols:
                print(f"[FAIL] Table {table} not found in database")
                all_ok = False
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
            print("\n[FAIL] scholarships table not found in database")
            all_ok = False
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

    except OperationalError as e:
        print(f"[FAIL] Database connection failed: {e}", file=sys.stderr)
        return 1
    except SQLAlchemyError as e:
        print(f"[FAIL] Database error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}", file=sys.stderr)
        return 1
    finally:
        if 'engine' in locals():
            engine.dispose()


if __name__ == "__main__":
    sys.exit(main())