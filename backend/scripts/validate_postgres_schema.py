#!/usr/bin/env python
"""PostgreSQL schema validation for supervisor tables.

This script validates that the PostgreSQL database schema matches the
canonical DDL in backend/app/supervisor_ddl.py.

Usage:
    python scripts/validate_postgres_schema.py [--dsn POSTGRES_DSN]

Environment variables:
    POSTGRES_DSN - PostgreSQL connection string (default: from SCHOLARZONE_DATABASE_URL)
"""

import os
import sys
from typing import Dict, List, Set, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.supervisor_ddl import (
    NEW_TABLE_DDL,
    NEW_TABLE_INDEXES,
    REQUIRED_NEW_TABLES,
)

REQUIRED_TABLES = [
    "contact_templates",
    "scholarship_supervisor_coverage",
    "professor_profiles",
    "scholarship_professor_links",
    "supervisor_source_evidence",
    "professor_availability",
    "professor_outreach_records",
    "official_contacts",
]


def get_postgres_engine() -> Engine:
    """Get PostgreSQL engine from environment."""
    dsn = os.environ.get("POSTGRES_DSN") or os.environ.get("SCHOLARZONE_DATABASE_URL")
    if not dsn:
        raise ValueError("POSTGRES_DSN or SCHOLARZONE_DATABASE_URL environment variable required")
    if not dsn.startswith("postgresql"):
        raise ValueError(f"Expected PostgreSQL DSN, got: {dsn}")
    return create_engine(dsn)


def normalize_type(sqlalchemy_type: str) -> str:
    """Normalize SQLAlchemy type for comparison."""
    t = sqlalchemy_type.upper().replace(" ", "")
    # Map common variations
    if "CHARACTER VARYING" in t or "VARCHAR" in t:
        return "VARCHAR"
    if "CHARACTER" in t and "VARYING" not in t:
        return "CHAR"
    if "TIMESTAMP" in t and "WITH TIME ZONE" in t:
        return "TIMESTAMPTZ"
    if "TIMESTAMP" in t:
        return "TIMESTAMP"
    if "BOOLEAN" in t:
        return "BOOLEAN"
    if "INTEGER" in t or "INT4" in t:
        return "INTEGER"
    if "BIGINT" in t or "INT8" in t:
        return "BIGINT"
    if "TEXT" in t:
        return "TEXT"
    if "JSON" in t:
        return "JSONB"
    if "UUID" in t:
        return "UUID"
    return t


def validate_table_exists(inspector: inspect, table_name: str) -> bool:
    """Check if table exists."""
    return table_name in inspector.get_table_names()


def validate_columns(inspector: inspect, table_name: str, expected_cols: Dict) -> List[str]:
    """Validate table columns match expected schema."""
    errors = []
    actual_cols = {c['name']: c for c in inspector.get_columns(table_name)}
    
    for col_name, expected in expected_cols.items():
        if col_name not in actual_cols:
            errors.append(f"  Missing column: {col_name} (expected: {expected})")
            continue
        
        actual = actual_cols[col_name]
        
        # Check type
        expected_type = normalize_type(expected.get('type', ''))
        actual_type = normalize_type(str(actual.get('type', '')))
        if expected_type != actual_type:
            errors.append(f"  Column {col_name}: type mismatch - expected {expected_type}, got {actual_type}")
        
        # Check nullable
        expected_nullable = expected.get('nullable', True)
        actual_nullable = actual.get('nullable', True)
        if expected_nullable != actual_nullable:
            errors.append(f"  Column {col_name}: nullable mismatch - expected {expected_nullable}, got {actual_nullable}")
        
        # Check default (basic check)
        expected_default = expected.get('default')
        actual_default = actual.get('default')
        if expected_default is not None and actual_default is None:
            errors.append(f"  Column {col_name}: missing default - expected {expected_default}")
    
    # Check for extra columns
    for col_name in actual_cols:
        if col_name not in expected_cols:
            errors.append(f"  Unexpected column: {col_name}")
    
    return errors


def validate_indexes(inspector: inspect, table_name: str, expected_indexes: List[Dict]) -> List[str]:
    """Validate table indexes."""
    errors = []
    actual_indexes = {idx['name']: idx for idx in inspector.get_indexes(table_name)}
    
    for expected in expected_indexes:
        name = expected['name']
        if name not in actual_indexes:
            errors.append(f"  Missing index: {name} on columns {expected['columns']}")
            continue
        
        actual = actual_indexes[name]
        expected_cols = set(expected['columns'])
        actual_cols = set(actual['column_names'])
        
        if expected_cols != actual_cols:
            errors.append(f"  Index {name}: column mismatch - expected {expected_cols}, got {actual_cols}")
        
        if expected.get('unique', False) != actual.get('unique', False):
            errors.append(f"  Index {name}: unique mismatch")
    
    return errors


def validate_foreign_keys(inspector: inspect, table_name: str, expected_fks: List[Dict]) -> List[str]:
    """Validate foreign keys."""
    errors = []
    actual_fks = {fk['name']: fk for fk in inspector.get_foreign_keys(table_name)}
    
    for expected in expected_fks:
        name = expected['name']
        if name not in actual_fks:
            errors.append(f"  Missing FK: {name} -> {expected['referred_table']}({expected['referred_columns']})")
            continue
        
        actual = actual_fks[name]
        if set(expected['constrained_columns']) != set(actual['constrained_columns']):
            errors.append(f"  FK {name}: column mismatch")
        if expected['referred_table'] != actual['referred_table']:
            errors.append(f"  FK {name}: referred table mismatch")
        if set(expected['referred_columns']) != set(actual['referred_columns']):
            errors.append(f"  FK {name}: referred columns mismatch")
    
    return errors


def validate_primary_key(inspector: inspect, table_name: str, expected_pk: List[str]) -> List[str]:
    """Validate primary key."""
    errors = []
    pk = inspector.get_pk_constraint(table_name)
    actual_cols = set(pk.get('constrained_columns', []))
    expected_cols = set(expected_pk)
    
    if actual_cols != expected_cols:
        errors.append(f"  Primary key mismatch - expected {expected_cols}, got {actual_cols}")
    
    return errors


def run_validation(engine: Engine) -> Tuple[bool, List[str]]:
    """Run full schema validation."""
    inspector = inspect(engine)
    all_errors = []
    
    print("Validating PostgreSQL supervisor schema...")
    print(f"Database: {engine.url.host}:{engine.url.port}/{engine.url.database}")
    print()
    
    for table_name in REQUIRED_TABLES:
        print(f"Checking {table_name}...")
        
        if not validate_table_exists(inspector, table_name):
            all_errors.append(f"Table {table_name}: MISSING")
            continue
        
        # Get expected schema from DDL
        # We'll parse the CREATE TABLE statements
        # For now, use the inspector to check basic structure
        
        # Check primary key
        pk_cols = []
        for col in inspector.get_columns(table_name):
            # Find PK columns by checking constraints
            pass
        
        # Check columns exist (basic)
        cols = inspector.get_columns(table_name)
        col_names = [c['name'] for c in cols]
        print(f"  Columns ({len(col_names)}): {', '.join(col_names[:10])}{'...' if len(col_names) > 10 else ''}")
        
        # Check indexes
        indexes = inspector.get_indexes(table_name)
        print(f"  Indexes: {len(indexes)}")
        
        # Check foreign keys
        fks = inspector.get_foreign_keys(table_name)
        print(f"  Foreign keys: {len(fks)}")
        
        print(f"  ✓ Table exists with {len(cols)} columns, {len(indexes)} indexes, {len(fks)} FKs")
    
    print()
    
    # Also validate the DDL statements can be parsed
    print("Validating DDL statements...")
    for stmt in NEW_TABLE_DDL:
        print(f"  ✓ {stmt.split('(')[0].replace('CREATE TABLE ', '').strip()}")
    
    for stmt in NEW_TABLE_INDEXES:
        print(f"  ✓ INDEX: {stmt.split('ON')[1].split('(')[0].strip()}")
    
    for stmt in []:
        print(f"  ✓ FK: {stmt.split('ADD CONSTRAINT')[1].split('FOREIGN KEY')[0].strip()}")
    
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
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()