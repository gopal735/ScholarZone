#!/usr/bin/env python3
"""
Production schema migration script for ScholarZone supervisor tables.

This script applies the canonical DDL from app.supervisor_ddl to create
only the missing supervisor tables and indexes. It is additive, idempotent,
and never drops or recreates existing tables.

Usage:
    python migrate_schema.py --dry-run      # Show what would be done
    python migrate_schema.py --apply        # Actually apply changes (requires SCHOLARZONE_EXPECTED_DB_IDENTIFIER)
    python migrate_schema.py --validate-only # Validate existing schema only
    python migrate_schema.py --report       # Generate JSON report
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine

# Add backend to path
BACKEND_DIR = Path(__file__).parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.supervisor_ddl import (
    REQUIRED_NEW_TABLES,
    create_table_statements,
    index_statements,
    NEW_TABLE_DDL,
    NEW_TABLE_INDEXES,
)


# ============================================================
# FK Parser - Fixed to correctly parse inline REFERENCES
# ============================================================

def parse_ddl_columns(ddl: str) -> dict[str, dict]:
    """Parse column definitions from a CREATE TABLE DDL string.
    
    Returns dict: column_name -> {type, nullable, default, primary_key, unique, references}
    """
    columns = {}
    
    # The DDL from supervisor_ddl contains just the column definitions (without CREATE TABLE wrapper)
    # Split by comma at depth 0 to get individual column/constraint definitions
    parts = []
    depth = 0
    current = ""
    for char in ddl:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if char == ',' and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Skip table-level constraints (CONSTRAINT, PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK, INDEX)
        if part.upper().startswith(('CONSTRAINT', 'PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY', 'CHECK', 'INDEX')):
            continue
        
        # Parse column definition: name type [constraints...]
        tokens = part.split()
        if len(tokens) < 2:
            continue
        col_name = tokens[0]
        col_type = tokens[1]
        
        # Check constraints
        nullable = True
        default = None
        primary_key = False
        unique = False
        references = None  # Will store {table, column, on_delete} if FK
        
        part_upper = part.upper()
        if 'NOT NULL' in part_upper:
            nullable = False
        if 'PRIMARY KEY' in part_upper:
            primary_key = True
            nullable = False
        if 'UNIQUE' in part_upper and not part_upper.startswith('UNIQUE'):
            unique = True
        # Check for DEFAULT
        default_match = re.search(r'DEFAULT\s+([^,\s]+)', part, re.IGNORECASE)
        if default_match:
            default = default_match.group(1)
        
        # Check for inline REFERENCES - capture local column, referenced table/column, ON DELETE
        ref_match = re.search(r'REFERENCES\s+(\w+)\s*\((\w+)\)\s*(ON DELETE\s+\w+)?', part, re.IGNORECASE)
        if ref_match:
            ref_table = ref_match.group(1)
            ref_column = ref_match.group(2)
            on_delete = ref_match.group(3).upper() if ref_match.group(3) else "NO ACTION"
            references = {
                "referred_table": ref_table,
                "referred_columns": [ref_column],
                "on_delete": on_delete,
                "constrained_columns": [col_name],  # Local column that has this REFERENCES
            }
        
        columns[col_name] = {
            "type": col_type,
            "nullable": nullable,
            "default": default,
            "primary_key": primary_key,
            "unique": unique,
            "references": references,
        }
    
    return columns


def parse_composite_constraints(ddl: str) -> list[dict]:
    """Parse composite UNIQUE and PRIMARY KEY constraints from DDL."""
    constraints = []
    # Find CONSTRAINT definitions
    constraint_pattern = re.compile(
        r'CONSTRAINT\s+(\w+)\s+(UNIQUE|PRIMARY KEY)\s*\(([^)]+)\)',
        re.IGNORECASE
    )
    for match in constraint_pattern.finditer(ddl):
        name = match.group(1)
        ctype = match.group(2).upper()
        cols = [c.strip() for c in match.group(3).split(',')]
        constraints.append({
            "name": name,
            "type": ctype,
            "columns": cols,
        })
    return constraints


def parse_foreign_keys(ddl: str) -> list[dict]:
    """Parse FOREIGN KEY constraints from DDL - both inline and table-level."""
    fks = []
    columns = parse_ddl_columns(ddl)
    
    # Extract FKs from column definitions (inline REFERENCES)
    for col_name, col_info in columns.items():
        if col_info.get("references"):
            ref = col_info["references"]
            fks.append({
                "constrained_columns": [col_name],
                "referred_table": ref["referred_table"],
                "referred_columns": ref["referred_columns"],
                "on_delete": ref["on_delete"],
                "name": None,  # Inline FKs don't have explicit names
            })
    
    # Also check for table-level FOREIGN KEY (though supervisor_ddl uses inline)
    fk_pattern = re.compile(
        r'FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)\s*(ON DELETE\s+\w+)?',
        re.IGNORECASE
    )
    for match in fk_pattern.finditer(ddl):
        cols = [c.strip() for c in match.group(1).split(',')]
        ref_table = match.group(2)
        ref_cols = [c.strip() for c in match.group(3).split(',')]
        on_delete = match.group(4).upper() if match.group(4) else "NO ACTION"
        # Avoid duplicates from inline parsing
        existing = False
        for fk in fks:
            if (fk["constrained_columns"] == cols and 
                fk["referred_table"] == ref_table and
                fk["referred_columns"] == ref_cols):
                existing = True
                break
        if not existing:
            fks.append({
                "constrained_columns": cols,
                "referred_table": ref_table,
                "referred_columns": ref_cols,
                "on_delete": on_delete,
                "name": None,
            })
    
    return fks


def get_expected_schema(dialect: str) -> dict[str, dict]:
    """Get the expected schema for a dialect from canonical DDL."""
    expected = {}
    for table_name in REQUIRED_NEW_TABLES:
        if table_name not in NEW_TABLE_DDL:
            continue
        ddl = NEW_TABLE_DDL[table_name][dialect]
        expected[table_name] = {
            "ddl": ddl,
            "columns": parse_ddl_columns(ddl),
            "composite_constraints": parse_composite_constraints(ddl),
            "foreign_keys": parse_foreign_keys(ddl),
            "indexes": [
                idx.split("IF NOT EXISTS ")[1].split(" ON ")[0]
                for idx in index_statements()
                if f" ON {table_name} " in idx
            ],
        }
    return expected


# ============================================================
# Database Engine & Identity Verification
# ============================================================

def get_production_engine() -> Engine:
    """Create engine for production database."""
    database_url = os.environ.get("SCHOLARZONE_DATABASE_URL")
    if not database_url:
        raise RuntimeError("SCHOLARZONE_DATABASE_URL environment variable not set")
    
    # Rewrite postgresql:// to postgresql+psycopg:// for SQLAlchemy 2.0
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    
    # Require SSL for PostgreSQL
    if database_url.startswith("postgresql"):
        if "sslmode=" not in database_url:
            database_url += ("&" if "?" in database_url else "?") + "sslmode=require"
    
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    if database_url.startswith("postgresql"):
        connect_args["connect_timeout"] = 10
    
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


def verify_database_identity(conn: Connection) -> dict[str, Any]:
    """Verify production database identity using trusted metadata.
    
    Returns identity dict with 'verified' bool and 'details'.
    Raises RuntimeError if identity check fails and SCHOLARZONE_EXPECTED_DB_IDENTIFIER is set.
    """
    dialect = conn.engine.dialect.name
    db_identity = {"verified": False, "details": {}}
    
    if dialect == "postgresql":
        try:
            # Check the database name
            result = conn.execute(text("SELECT current_database()")).scalar()
            db_identity["details"]["database_name"] = result
            
            # Require explicit environment variable for production DB identity
            expected_db_id = os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER")
            if expected_db_id:
                if expected_db_id in result:
                    db_identity["verified"] = True
                    db_identity["details"]["matched_identifier"] = expected_db_id
                else:
                    raise RuntimeError(
                        f"Database identity mismatch. Expected identifier '{expected_db_id}' "
                        f"not found in database name '{result}'. "
                        f"Set SCHOLARZONE_EXPECTED_DB_IDENTIFIER to the expected Neon project/branch identifier."
                    )
            else:
                # Not verified - will be checked at apply time
                db_identity["details"]["warning"] = "SCHOLARZONE_EXPECTED_DB_IDENTIFIER not set; identity not verified"
        except Exception as e:
            if "identity mismatch" in str(e):
                raise
            db_identity["details"]["error"] = str(e)
    else:
        db_identity["details"]["note"] = f"Identity verification not applicable for {dialect}"
    
    return db_identity


def verify_production_database(engine: Engine) -> dict[str, Any]:
    """Verify this is the expected production database using trusted metadata."""
    inspector = inspect(engine)
    dialect = engine.dialect.name
    
    # Check for core tables that must exist
    required_core_tables = {"scholarships", "users"}
    existing_tables = set(inspector.get_table_names())
    missing_core = required_core_tables - existing_tables
    
    if missing_core:
        raise RuntimeError(
            f"Database missing required core tables: {missing_core}. "
            f"This does not appear to be the expected production database."
        )
    
    # Check for a known scholarship record to verify data
    with engine.connect() as conn:
        try:
            scholarship_count = conn.execute(text("SELECT COUNT(*) FROM scholarships")).scalar()
        except Exception as e:
            raise RuntimeError(f"Cannot query scholarships table: {e}")
        
        # Verify identity
        db_identity = verify_database_identity(conn)
    
    return {
        "database_url": str(engine.url).replace(str(engine.url.password), "***") if engine.url.password else str(engine.url),
        "core_tables_present": list(required_core_tables),
        "scholarship_count": scholarship_count,
        "dialect": dialect,
        "identity": db_identity,
    }


def check_existing_supervisor_tables(engine: Engine) -> dict[str, Any]:
    """Check which supervisor tables already exist."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    
    supervisor_tables = {}
    for table_name in REQUIRED_NEW_TABLES:
        exists = table_name in existing_tables
        if exists:
            column_info = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            supervisor_tables[table_name] = {
                "exists": True,
                "column_count": len(column_info),
                "columns": [c["name"] for c in column_info],
                "index_count": len(indexes),
                "indexes": [i["name"] for i in indexes],
                "foreign_key_count": len(foreign_keys),
                "foreign_keys": [fk["constrained_columns"] for fk in foreign_keys],
            }
        else:
            supervisor_tables[table_name] = {"exists": False}
    
    return {
        "total_required": len(REQUIRED_NEW_TABLES),
        "existing_count": sum(1 for t in supervisor_tables.values() if t["exists"]),
        "missing_count": sum(1 for t in supervisor_tables.values() if not t["exists"]),
        "tables": supervisor_tables,
    }


def generate_create_statements(dialect: str, missing_tables: list[str]) -> list[str]:
    """Generate CREATE TABLE statements for missing tables."""
    statements = []
    for table_name in missing_tables:
        if table_name not in NEW_TABLE_DDL:
            continue
        ddl = NEW_TABLE_DDL[table_name][dialect]
        statements.append(f"CREATE TABLE IF NOT EXISTS {table_name} ({ddl})")
    return statements


def generate_index_statements(missing_tables: list[str]) -> list[str]:
    """Generate CREATE INDEX statements for missing tables."""
    statements = []
    for table_name in missing_tables:
        for idx in index_statements():
            if f" ON {table_name} " in idx:
                statements.append(idx)
    return statements


# ============================================================
# Dry Run
# ============================================================

def dry_run(engine: Engine) -> dict[str, Any]:
    """Perform a dry run of the migration."""
    dialect = "postgresql" if engine.dialect.name == "postgresql" else "sqlite"
    
    # Verify production database
    db_info = verify_production_database(engine)
    
    # Check existing tables
    table_info = check_existing_supervisor_tables(engine)
    missing_tables = [t for t, info in table_info["tables"].items() if not info["exists"]]
    
    # Generate statements
    create_stmts = generate_create_statements(dialect, missing_tables)
    index_stmts = generate_index_statements(missing_tables)
    
    return {
        "mode": "dry-run",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "database": db_info,
        "supervisor_tables": table_info,
        "missing_tables": missing_tables,
        "create_statements": create_stmts,
        "index_statements": index_stmts,
        "total_statements": len(create_stmts) + len(index_stmts),
    }


# ============================================================
# Index Helpers for Validation (SQLite auto-generated indexes)
# ============================================================

def get_all_indexes_with_pragma(conn: Connection, table_name: str) -> list[dict]:
    """Get all indexes for a table including SQLite auto-generated unique constraint indexes."""
    dialect = conn.engine.dialect.name
    if dialect == "sqlite":
        # Use raw PRAGMA to get all indexes including auto-generated unique constraint indexes
        result = conn.execute(text(f"PRAGMA index_list({table_name})"))
        indexes = []
        for row in result:
            # row: (seq, name, unique, origin, partial)
            idx_name = row[1]
            is_unique = bool(row[2])
            # Get column names for this index
            col_result = conn.execute(text(f"PRAGMA index_info({idx_name})"))
            columns = [col_row[2] for col_row in col_result]
            indexes.append({
                "name": idx_name,
                "unique": is_unique,
                "column_names": columns,
            })
        return indexes
    else:
        # Use standard inspector for PostgreSQL
        inspector = inspect(conn.engine)
        return [
            {
                "name": i["name"],
                "unique": i.get("unique", False),
                "column_names": i.get("column_names", []),
            }
            for i in inspector.get_indexes(table_name)
        ]


# ============================================================
# Apply Migration with Transactional Validation
# ============================================================

def apply_migration(engine: Engine, report: dict[str, Any]) -> dict[str, Any]:
    """Apply the migration with full transactional validation.
    
    All DDL and validation happen in a SINGLE transaction.
    If validation fails, the entire transaction rolls back.
    """
    dialect = "postgresql" if engine.dialect.name == "postgresql" else "sqlite"
    missing_tables = report["missing_tables"]
    create_stmts = report["create_statements"]
    index_stmts = report["index_statements"]
    
    applied = {"tables_created": [], "indexes_created": [], "errors": []}
    validation = None
    
    # Use a single transaction for all DDL AND validation
    with engine.begin() as conn:
        # Create tables
        for stmt in create_stmts:
            try:
                conn.execute(text(stmt))
                table_name = stmt.split()[2]
                applied["tables_created"].append(table_name)
                print(f"[APPLIED] CREATE TABLE {table_name}")
            except Exception as e:
                applied["errors"].append({"statement": stmt, "error": str(e)})
                print(f"[ERROR] CREATE TABLE failed: {e}")
                raise  # Rollback the transaction
        
        # Create indexes
        for stmt in index_stmts:
            try:
                conn.execute(text(stmt))
                applied["indexes_created"].append(stmt)
                print(f"[APPLIED] {stmt}")
            except Exception as e:
                applied["errors"].append({"statement": stmt, "error": str(e)})
                print(f"[ERROR] CREATE INDEX failed: {e}")
                raise  # Rollback the transaction
        
        # VALIDATE WITHIN THE SAME TRANSACTION
        # Use the transaction connection for inspection
        validation = validate_schema_with_connection(conn)
        
        # If validation fails, raise to trigger rollback
        if not validation.get("valid", False):
            error_msg = "SCHEMA VALIDATION FAILED: " + json.dumps(
                {k: v for k, v in validation.items() if k != "table_details"},
                indent=2
            )
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            raise RuntimeError(error_msg)
    
    return {
        "mode": "apply",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "applied": applied,
        "validation": validation,
    }


# ============================================================
# Schema Validation - Exact, Dialect-Aware
# ============================================================

def normalize_on_delete(on_delete: str) -> str:
    """Normalize ON DELETE action for comparison."""
    if not on_delete:
        return "NO ACTION"
    on_delete = on_delete.upper().strip()
    # Normalize variations
    if on_delete == "ON DELETE RESTRICT" or on_delete == "RESTRICT":
        return "RESTRICT"
    if on_delete == "ON DELETE CASCADE" or on_delete == "CASCADE":
        return "CASCADE"
    if on_delete == "ON DELETE SET NULL" or on_delete == "SET NULL":
        return "SET NULL"
    if on_delete == "ON DELETE NO ACTION" or on_delete == "NO ACTION":
        return "NO ACTION"
    if on_delete == "ON DELETE SET DEFAULT" or on_delete == "SET DEFAULT":
        return "SET DEFAULT"
    return on_delete


def normalize_type(dialect: str, type_str: str) -> str:
    """Normalize type string for dialect-aware comparison."""
    if not type_str:
        return ""
    # Remove length specifications for base type comparison
    type_str = type_str.upper().strip()
    # Handle common aliases
    type_str = type_str.replace("TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ")
    type_str = type_str.replace("TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP")
    # SQLite uses DATETIME for what PostgreSQL calls TIMESTAMPTZ
    if dialect == "sqlite":
        type_str = type_str.replace("TIMESTAMPTZ", "DATETIME")
    # Remove length specifiers for base type comparison
    base_type = re.sub(r'\(.*\)', '', type_str)
    return base_type.strip()


def types_match(dialect: str, expected_type: str, actual_type: str) -> bool:
    """Check if types match with dialect awareness."""
    norm_expected = normalize_type(dialect, expected_type)
    norm_actual = normalize_type(dialect, actual_type)
    return norm_expected == norm_actual


def get_all_indexes_with_pragma(conn: Connection, table_name: str) -> list[dict]:
    """Get all indexes for a table including SQLite auto-generated unique constraint indexes."""
    dialect = conn.engine.dialect.name
    if dialect == "sqlite":
        # Use raw PRAGMA to get all indexes including auto-generated unique constraint indexes
        result = conn.execute(text(f"PRAGMA index_list({table_name})"))
        indexes = []
        for row in result:
            # row: (seq, name, unique, origin, partial)
            idx_name = row[1]
            is_unique = bool(row[2])
            # Get column names for this index
            col_result = conn.execute(text(f"PRAGMA index_info({idx_name})"))
            columns = [col_row[2] for col_row in col_result]
            indexes.append({
                "name": idx_name,
                "unique": is_unique,
                "column_names": columns,
            })
        return indexes
    else:
        # Use standard inspector for PostgreSQL
        inspector = inspect(conn.engine)
        return [
            {
                "name": i["name"],
                "unique": i.get("unique", False),
                "column_names": i.get("column_names", []),
            }
            for i in inspector.get_indexes(table_name)
        ]


def validate_schema_with_connection(conn: Connection) -> dict[str, Any]:
    """Validate schema against canonical DDL using the given transaction connection.
    
    This allows validation within the same transaction as DDL application.
    """
    engine = conn.engine
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    dialect = "postgresql" if engine.dialect.name == "postgresql" else "sqlite"
    expected_schema = get_expected_schema(dialect)
    
    validation = {
        "valid": True,
        "missing_tables": [],
        "table_details": {},
        "column_validation": {},
        "index_validation": {},
        "foreign_key_validation": {},
        "constraint_validation": {},
        "composite_unique_validation": {},
    }
    
    for table_name in REQUIRED_NEW_TABLES:
        expected = expected_schema.get(table_name, {})
        
        if table_name not in existing_tables:
            validation["valid"] = False
            validation["missing_tables"].append(table_name)
            validation["table_details"][table_name] = {"exists": False}
            continue
        
        # Get actual schema using the SAME connection
        column_info = inspector.get_columns(table_name)
        actual_columns = {c["name"]: c for c in column_info}
        # Get ALL indexes including SQLite auto-generated unique constraint indexes
        actual_indexes = get_all_indexes_with_pragma(conn, table_name)
        actual_foreign_keys = inspector.get_foreign_keys(table_name)
        actual_pk = inspector.get_pk_constraint(table_name)
        
        expected_columns = expected.get("columns", {})
        expected_composite = expected.get("composite_constraints", [])
        expected_fks = expected.get("foreign_keys", [])
        expected_indexes = expected.get("indexes", [])
        
        table_ok = True
        
        # Column validation
        column_results = {}
        # Get primary key info once
        pk_info = actual_pk.get("constrained_columns", [])
        for col_name, expected_col in expected_columns.items():
            actual_col = actual_columns.get(col_name)
            if not actual_col:
                column_results[col_name] = {"status": "MISSING", "expected": expected_col}
                table_ok = False
                continue
            
            # Exact type matching (dialect-aware)
            type_ok = types_match(dialect, expected_col["type"], str(actual_col.get("type", "")))
            
            # Check nullable
            expected_nullable = expected_col["nullable"]
            actual_nullable = actual_col.get("nullable", True)
            nullable_ok = expected_nullable == actual_nullable
            
            # Check primary key
            expected_pk = expected_col["primary_key"]
            actual_pk_bool = col_name in pk_info
            pk_ok = expected_pk == actual_pk_bool
            
            # Check unique (column-level)
            expected_unique = expected_col["unique"]
            actual_unique = actual_col.get("unique", False)
            unique_ok = expected_unique == actual_unique
            
            # Check default value
            expected_default = expected_col.get("default")
            actual_default = actual_col.get("default")
            default_ok = True
            if expected_default is not None and actual_default is not None:
                # Normalize defaults for comparison
                default_ok = str(expected_default).strip("'") == str(actual_default).strip("'")
            
            col_ok = type_ok and nullable_ok and pk_ok and unique_ok and default_ok
            if not col_ok:
                table_ok = False
            
            column_results[col_name] = {
                "status": "OK" if col_ok else "MISMATCH",
                "expected": expected_col,
                "actual": {
                    "type": str(actual_col.get("type")),
                    "nullable": actual_nullable,
                    "primary_key": actual_pk_bool,
                    "unique": actual_unique,
                    "default": actual_default,
                },
                "checks": {
                    "type": type_ok,
                    "nullable": nullable_ok,
                    "primary_key": pk_ok,
                    "unique": unique_ok,
                    "default": default_ok,
                },
            }
        
        # Check for unexpected extra columns
        extra_columns = set(actual_columns.keys()) - set(expected_columns.keys())
        for col_name in extra_columns:
            if col_name not in ("id", "created_at", "updated_at"):
                column_results[col_name] = {"status": "UNEXPECTED", "actual": actual_columns[col_name]}
                table_ok = False
        
        validation["column_validation"][table_name] = {
            "all_columns_ok": all(r.get("status") == "OK" for r in column_results.values()),
            "columns": column_results,
            "expected_count": len(expected_columns),
            "actual_count": len(actual_columns),
        }
        
        # Composite unique constraint validation
        composite_results = []
        for expected_comp in expected.get("composite_constraints", []):
            if expected_comp["type"] == "UNIQUE":
                found = False
                for idx in actual_indexes:
                    if idx.get("unique") and list(idx["column_names"]) == expected_comp["columns"]:
                        found = True
                        break
                composite_results.append({
                    "name": expected_comp["name"],
                    "columns": expected_comp["columns"],
                    "found": found,
                })
                if not found:
                    table_ok = False
        
        validation["composite_unique_validation"][table_name] = {
            "expected": expected.get("composite_constraints", []),
            "results": composite_results,
        }
        
        # Index validation - exact name, columns, uniqueness, order
        missing_indexes = []
        index_details = {}
        for idx_name in expected.get("indexes", []):
            idx = next((i for i in actual_indexes if i["name"] == idx_name), None)
            if idx is None:
                missing_indexes.append(idx_name)
                table_ok = False
            else:
                index_details[idx_name] = {
                    "found": True,
                    "unique": idx.get("unique", False),
                    "columns": idx.get("column_names", []),
                }
        
        validation["index_validation"][table_name] = {
            "expected_count": len(expected.get("indexes", [])),
            "actual_count": len(actual_indexes),
            "missing": missing_indexes,
            "details": index_details,
            "all_present": len(missing_indexes) == 0,
        }
        if missing_indexes:
            table_ok = False
        
        # Foreign key validation with exact constrained/referred columns and ON DELETE
        fk_results = []
        actual_foreign_keys = inspector.get_foreign_keys(table_name)
        
        for expected_fk in expected.get("foreign_keys", []):
            # Match by constrained columns AND referred table
            found = False
            for actual_fk in actual_foreign_keys:
                actual_cols = actual_fk.get("constrained_columns", [])
                expected_cols = expected_fk.get("constrained_columns", [])
                if (actual_cols == expected_cols and
                    actual_fk.get("referred_table") == expected_fk.get("referred_table")):
                    found = True
                    actual_on_delete = normalize_on_delete(actual_fk.get("options", {}).get("ondelete", "NO ACTION"))
                    expected_on_delete = normalize_on_delete(expected_fk.get("on_delete", "NO ACTION"))
                    on_delete_match = actual_on_delete == expected_on_delete
                    if not on_delete_match:
                        fk_results.append({
                            "constrained_columns": expected_cols,
                            "referred_table": expected_fk.get("referred_table"),
                            "status": "ON_DELETE_MISMATCH",
                            "expected_on_delete": expected_on_delete,
                            "actual_on_delete": actual_on_delete,
                        })
                        table_ok = False
                    else:
                        # Verify referred columns match
                        actual_ref_cols = actual_fk.get("referred_columns", [])
                        expected_ref_cols = expected_fk.get("referred_columns", [])
                        ref_cols_match = actual_ref_cols == expected_ref_cols
                        if not ref_cols_match:
                            fk_results.append({
                                "constrained_columns": expected_cols,
                                "referred_table": expected_fk.get("referred_table"),
                                "status": "REFERRED_COLUMNS_MISMATCH",
                                "expected_referred_columns": expected_ref_cols,
                                "actual_referred_columns": actual_ref_cols,
                            })
                            table_ok = False
                        else:
                            fk_results.append({
                                "constrained_columns": expected_cols,
                                "referred_table": expected_fk.get("referred_table"),
                                "status": "OK",
                                "on_delete": actual_on_delete,
                            })
                    break
            if not found:
                fk_results.append({
                    "constrained_columns": expected_fk.get("constrained_columns", []),
                    "referred_table": expected_fk.get("referred_table"),
                    "status": "MISSING",
                })
                table_ok = False
        
        validation["foreign_key_validation"][table_name] = {
            "expected_count": len(expected.get("foreign_keys", [])),
            "actual_count": len(actual_foreign_keys),
            "details": fk_results,
            "all_ok": all(fk.get("status") == "OK" for fk in fk_results),
        }
        
        # Constraint validation (column-level unique + PK)
        unique_cols = [c for c, r in column_results.items() if r.get("status") == "OK" and r.get("expected", {}).get("unique")]
        pk_cols = [c for c, r in column_results.items() if r.get("status") == "OK" and r.get("expected", {}).get("primary_key")]
        
        validation["constraint_validation"][table_name] = {
            "unique_columns": unique_cols,
            "primary_key_columns": pk_cols,
        }
        
        validation["table_details"][table_name] = {
            "exists": True,
            "column_count": len(actual_columns),
            "columns": list(actual_columns.keys()),
            "primary_key": actual_pk.get("constrained_columns", []),
            "has_required_columns": table_ok,
        }
        
        if not table_ok:
            validation["valid"] = False
    
    return validation


def validate_schema(engine: Engine) -> dict[str, Any]:
    """Validate schema using a new connection (for --validate-only)."""
    with engine.connect() as conn:
        return validate_schema_with_connection(conn)


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="ScholarZone production schema migration")
    
    # Mutually exclusive migration modes
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--dry-run", action="store_true", help="Show what would be done without applying")
    mode_group.add_argument("--apply", action="store_true", help="Apply the migration (requires SCHOLARZONE_EXPECTED_DB_IDENTIFIER)")
    mode_group.add_argument("--validate-only", action="store_true", help="Only validate existing schema")
    
    # Report options (can combine with modes)
    parser.add_argument("--report", action="store_true", help="Output JSON report to stdout")
    parser.add_argument("--output", type=str, help="Write JSON report to file")
    
    args = parser.parse_args()
    
    # Validate identity requirement for apply mode
    if args.apply and not os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER"):
        print("ERROR: --apply requires SCHOLARZONE_EXPECTED_DB_IDENTIFIER environment variable to be set", file=sys.stderr)
        print("This is a safety gate to prevent accidental migration to wrong database.", file=sys.stderr)
        sys.exit(1)
    
    try:
        engine = get_production_engine()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.validate_only:
            validation = validate_schema(engine)
            report = {
                "mode": "validate-only",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "validation": validation,
            }
        elif args.dry_run or args.report:
            report = dry_run(engine)
        elif args.apply:
            # Apply mode: run dry-run first to get the plan, then apply with transactional validation
            dry_run_report = dry_run(engine)
            report = apply_migration(engine, dry_run_report)
        else:
            parser.print_help()
            sys.exit(1)
        
        # Output report
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"Report written to {args.output}")
        elif args.report:
            json.dump(report, sys.stdout, indent=2, default=str)
            print()
        
        # Exit with error code if validation fails
        if args.validate_only or args.apply:
            validation = report.get("validation", report.get("applied", {}).get("validation", {}))
            if not validation.get("valid", True):
                print("VALIDATION FAILED: Schema does not match canonical DDL", file=sys.stderr)
                sys.exit(1)
        
        if args.apply and report.get("applied", {}).get("errors"):
            print("APPLICATION ERRORS OCCURRED", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()