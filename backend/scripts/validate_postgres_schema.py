"""PostgreSQL schema validation for supervisor tables.

Validates that the PostgreSQL database schema matches the canonical DDL
in backend/app/supervisor_ddl.py.

Usage:
    python scripts/validate_postgres_schema.py [--dsn POSTGRES_DSN]

Environment variables:
    POSTGRES_DSN - PostgreSQL connection string (default: from SCHOLARZONE_DATABASE_URL)
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.supervisor_ddl import (
    NEW_TABLE_DDL,
    NEW_TABLE_INDEXES,
    REQUIRED_NEW_TABLES,
)


def get_postgres_engine() -> Engine:
    """Get PostgreSQL engine from environment."""
    dsn = os.environ.get("POSTGRES_DSN") or os.environ.get("SCHOLARZONE_DATABASE_URL")
    if not dsn:
        raise ValueError("POSTGRES_DSN or SCHOLARZONE_DATABASE_URL environment variable required")
    if not dsn.startswith("postgresql"):
        raise ValueError(f"Expected PostgreSQL DSN, got: {dsn.split('://')[0]}://***")
    return create_engine(dsn)


def parse_index_definition(index_str: str) -> tuple[str, str, list[str]]:
    """Parse an index definition string like 'ix_name ON table (col1, col2)'.

    Returns (index_name, table_name, column_list).
    """
    match = re.match(r"(\w+)\s+ON\s+(\w+)\s*\(([^)]+)\)", index_str)
    if not match:
        raise ValueError(f"Cannot parse index definition: {index_str}")
    name = match.group(1)
    table = match.group(2)
    cols = [c.strip() for c in match.group(3).split(",")]
    return name, table, cols


def validate_table_exists(inspector, table_name: str) -> bool:
    """Check if table exists."""
    return table_name in inspector.get_table_names()


def validate_columns(inspector, table_name: str, expected_sql: str) -> list[str]:
    """Validate table columns against expected DDL."""
    errors = []
    actual_cols = {c["name"]: c for c in inspector.get_columns(table_name)}

    # Parse column names from DDL
    # Extract column definitions from CREATE TABLE statement
    match = re.search(r"CREATE TABLE \w+ \((.+)\)", expected_sql, re.DOTALL)
    if not match:
        return [f"  Cannot parse DDL for {table_name}"]

    body = match.group(1)
    # Split by commas, but be careful with nested parentheses
    # Simple approach: find column names (first word before type)
    expected_col_names = set()
    for line in body.split(","):
        line = line.strip()
        if not line:
            continue
        # Skip constraint definitions
        if line.upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT")):
            continue
        # First token is column name
        parts = line.split()
        if parts:
            col_name = parts[0].strip('"').strip("'")
            if col_name and not col_name.startswith("("):
                expected_col_names.add(col_name)

    # Check all expected columns exist
    for col_name in expected_col_names:
        if col_name not in actual_cols:
            errors.append(f"  Missing column: {col_name}")

    # Check for unexpected columns (only warn, don't error)
    for col_name in actual_cols:
        if col_name not in expected_col_names:
            errors.append(f"  Unexpected column: {col_name}")

    return errors


def validate_indexes(inspector, table_name: str, expected_indexes: list[str]) -> list[str]:
    """Validate table indexes."""
    errors = []
    actual_indexes = {idx["name"]: idx for idx in inspector.get_indexes(table_name)}

    for index_str in expected_indexes:
        name, table, cols = parse_index_definition(index_str)
        if table != table_name:
            continue

        if name not in actual_indexes:
            errors.append(f"  Missing index: {name} on columns {cols}")
            continue

        actual = actual_indexes[name]
        actual_cols = actual.get("column_names", [])
        if set(cols) != set(actual_cols):
            errors.append(
                f"  Index {name}: column mismatch - expected {cols}, got {actual_cols}"
            )

    return errors


def validate_primary_key(inspector, table_name: str) -> list[str]:
    """Validate primary key exists."""
    errors = []
    pk = inspector.get_pk_constraint(table_name)
    if not pk.get("constrained_columns"):
        errors.append(f"  Missing primary key on {table_name}")
    return errors


def validate_foreign_keys(inspector, table_name: str) -> list[str]:
    """Validate foreign keys exist (informational)."""
    # We don't enforce specific FKs, just report
    return []


def run_validation(engine: Engine) -> tuple[bool, list[str]]:
    """Run full schema validation."""
    inspector = inspect(engine)
    all_errors = []

    print("Validating PostgreSQL supervisor schema...")
    print(f"Database: {engine.url.host}:{engine.url.port}/{engine.url.database}")
    print()

    for table_name in REQUIRED_NEW_TABLES:
        print(f"Checking {table_name}...")

        if not validate_table_exists(inspector, table_name):
            all_errors.append(f"Table {table_name}: MISSING")
            print(f"  ✗ Table missing")
            continue

        cols = inspector.get_columns(table_name)
        indexes = inspector.get_indexes(table_name)
        fks = inspector.get_foreign_keys(table_name)
        pk = inspector.get_pk_constraint(table_name)

        print(f"  Columns: {len(cols)}, Indexes: {len(indexes)}, FKs: {len(fks)}, PK: {pk.get('constrained_columns', [])}")

        # Validate columns
        expected_ddl = NEW_TABLE_DDL.get(table_name, "")
        col_errors = validate_columns(inspector, table_name, expected_ddl)
        all_errors.extend([f"Table {table_name}:{e}" for e in col_errors])

        # Validate primary key
        pk_errors = validate_primary_key(inspector, table_name)
        all_errors.extend([f"Table {table_name}:{e}" for e in pk_errors])

        # Validate indexes
        expected_indexes = NEW_TABLE_INDEXES.get(table_name, [])
        idx_errors = validate_indexes(inspector, table_name, expected_indexes)
        all_errors.extend([f"Table {table_name}:{e}" for e in idx_errors])

        if not col_errors and not pk_errors and not idx_errors:
            print(f"  ✓ Valid")

    print()
    print("=" * 60)
    if all_errors:
        print("VALIDATION FAILED:")
        for err in all_errors:
            print(f"  {err}")
        return False, all_errors
    else:
        print("VALIDATION PASSED: All supervisor tables exist with expected structure")
        return True, []


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate PostgreSQL supervisor schema")
    parser.add_argument("--dsn", help="PostgreSQL DSN (overrides env)")
    args = parser.parse_args()

    if args.dsn:
        os.environ["POSTGRES_DSN"] = args.dsn

    try:
        engine = get_postgres_engine()
        success, errors = run_validation(engine)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()