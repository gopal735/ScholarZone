"""Idempotent schema migration for ScholarZone PostgreSQL.

Adds missing columns and tables required by the Image-Kind + Admin Review
feature without dropping or modifying existing data.

Usage:
    python migrate_schema.py                     # Run migration
    python migrate_schema.py --dry-run            # Show what would be executed
    python migrate_schema.py --validate-only      # Verify schema without changes
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import NoSuchTableError


REQUIRED_COLUMNS = {
    "scholarships": {
        "image_kind": "VARCHAR(32) NULL",
    },
}

REQUIRED_TABLES = {
    "image_reviews": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            image_url VARCHAR(2048) NOT NULL,
            image_kind VARCHAR(32) NOT NULL,
            source_page VARCHAR(2048),
            source_type VARCHAR(32),
            relevance_evidence TEXT,
            licensing_status VARCHAR(32),
            licensing_evidence TEXT,
            confidence VARCHAR(32) NOT NULL,
            reason_for_review VARCHAR(255),
            decision VARCHAR(16) NOT NULL DEFAULT 'pending',
            reviewed_by VARCHAR(120),
            reviewed_at TIMESTAMPTZ,
            reviewer_note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            image_url VARCHAR(2048) NOT NULL,
            image_kind VARCHAR(32) NOT NULL,
            source_page VARCHAR(2048),
            source_type VARCHAR(32),
            relevance_evidence TEXT,
            licensing_status VARCHAR(32),
            licensing_evidence TEXT,
            confidence VARCHAR(32) NOT NULL,
            reason_for_review VARCHAR(255),
            decision VARCHAR(16) NOT NULL DEFAULT 'pending',
            reviewed_by VARCHAR(120),
            reviewed_at DATETIME,
            reviewer_note TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        """,
    },
    # Student dashboard. Five new tables, none of which touches the scholarship
    # catalogue: they hold accounts, sessions and one student's own records.
    # Nothing here alters or reads scholarships, so applying this migration
    # cannot change a single published fact.
    "users": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            email VARCHAR(254) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_users_email UNIQUE (email)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(254) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_users_email UNIQUE (email)
        """,
    },
    "user_sessions": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            CONSTRAINT uq_user_sessions_token_hash UNIQUE (token_hash)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token_hash VARCHAR(64) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            revoked_at DATETIME,
            CONSTRAINT uq_user_sessions_token_hash UNIQUE (token_hash)
        """,
    },
    "student_profiles": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            payload JSON NOT NULL DEFAULT '{}'::json,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_student_profiles_user UNIQUE (user_id)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            payload JSON NOT NULL DEFAULT '{}',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_student_profiles_user UNIQUE (user_id)
        """,
    },
    "saved_scholarships": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_saved_scholarships_user_scholarship UNIQUE (user_id, scholarship_id)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_saved_scholarships_user_scholarship UNIQUE (user_id, scholarship_id)
        """,
    },
    "application_records": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            state VARCHAR(16) NOT NULL DEFAULT 'saved',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_application_records_user_scholarship UNIQUE (user_id, scholarship_id)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            state VARCHAR(16) NOT NULL DEFAULT 'saved',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_application_records_user_scholarship UNIQUE (user_id, scholarship_id)
        """,
    },
}

REQUIRED_INDEXES = {
    "image_reviews": [
        "ix_image_reviews_scholarship_decision ON image_reviews (scholarship_id, decision)",
        "ix_image_reviews_created_at ON image_reviews (created_at)",
    ],
    "users": [
        "ix_users_email ON users (email)",
    ],
    "user_sessions": [
        "ix_user_sessions_token_hash ON user_sessions (token_hash)",
        "ix_user_sessions_expires_at ON user_sessions (expires_at)",
        "ix_user_sessions_user_expires ON user_sessions (user_id, expires_at)",
    ],
    "student_profiles": [
        "ix_student_profiles_user_id ON student_profiles (user_id)",
    ],
    "saved_scholarships": [
        "ix_saved_scholarships_user_created ON saved_scholarships (user_id, created_at)",
    ],
    "application_records": [
        "ix_application_records_user_updated ON application_records (user_id, updated_at)",
        "ix_application_records_state ON application_records (state)",
    ],
}


def get_engine():
    url = os.getenv("SCHOLARZONE_DATABASE_URL")
    if not url:
        print("ERROR: SCHOLARZONE_DATABASE_URL is not set.")
        sys.exit(1)
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return create_engine(url, pool_pre_ping=True, client_encoding="UTF8")


def column_exists(engine, table_name: str, column_name: str) -> bool:
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(engine, table_name: str) -> bool:
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def index_exists(engine, table_name: str, index_name: str) -> bool:
    inspector = inspect(engine)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    except NoSuchTableError:
        return False
    return index_name in indexes


def _dialect_name(engine) -> str:
    return engine.dialect.name


def run_migration(engine, dry_run: bool = False) -> list[str]:
    changes: list[str] = []
    dialect = _dialect_name(engine)

    with engine.begin() as conn:
        for table_name, columns in REQUIRED_COLUMNS.items():
            for column_name, definition in columns.items():
                if not column_exists(engine, table_name, column_name):
                    if dialect == "postgresql":
                        sql = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {definition}"
                    else:
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                    changes.append(sql)
                    if not dry_run:
                        conn.execute(text(sql))

        for table_name, ddl_map in REQUIRED_TABLES.items():
            if not table_exists(engine, table_name):
                ddl = ddl_map.get(dialect, ddl_map.get("postgresql", ""))
                sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({ddl})"
                changes.append(sql)
                if not dry_run:
                    conn.execute(text(sql))

        for table_name, index_defs in REQUIRED_INDEXES.items():
            for index_def in index_defs:
                index_name = index_def.split(" ON ")[0].strip()
                if not index_exists(engine, table_name, index_name):
                    sql = f"CREATE INDEX IF NOT EXISTS {index_def}"
                    changes.append(sql)
                    if not dry_run:
                        conn.execute(text(sql))

    return changes


def validate_schema(engine) -> bool:
    ok = True
    for table_name, columns in REQUIRED_COLUMNS.items():
        for column_name in columns:
            if not column_exists(engine, table_name, column_name):
                print(f"MISSING: {table_name}.{column_name}")
                ok = False
            else:
                print(f"OK: {table_name}.{column_name}")

    for table_name in REQUIRED_TABLES:
        if not table_exists(engine, table_name):
            print(f"MISSING TABLE: {table_name}")
            ok = False
        else:
            print(f"OK TABLE: {table_name}")

    for table_name, index_defs in REQUIRED_INDEXES.items():
        for index_def in index_defs:
            index_name = index_def.split(" ON ")[0].strip()
            if not index_exists(engine, table_name, index_name):
                print(f"MISSING INDEX: {index_name}")
                ok = False
            else:
                print(f"OK INDEX: {index_name}")

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotent schema migration for ScholarZone")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--validate-only", action="store_true", help="Verify schema without changes")
    args = parser.parse_args()

    engine = get_engine()

    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
            print(f"Connected to: {version[:80]}...")
    except Exception as exc:
        print(f"ERROR: Could not connect to database: {exc}")
        sys.exit(1)

    if args.validate_only:
        ok = validate_schema(engine)
        sys.exit(0 if ok else 1)

    changes = run_migration(engine, dry_run=args.dry_run)

    if not changes:
        print("Schema is already up to date. No changes needed.")
    else:
        print(f"Migration {'would apply' if args.dry_run else 'applied'} {len(changes)} change(s):")
        for sql in changes:
            print(f"  -> {sql}")

    engine.dispose()


if __name__ == "__main__":
    main()
