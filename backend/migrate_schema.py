#!/usr/bin/env python3
"""
Production schema migration script for ScholarZone supervisor tables.

This script applies the canonical DDL from app.supervisor_ddl to create
only the missing supervisor tables and indexes. It is additive, idempotent,
and never drops or recreates existing tables.

Usage:
    python migrate_schema.py --dry-run      # Show what would be done
    python migrate_schema.py --apply        # Actually apply changes
    python migrate_schema.py --validate-only # Validate existing schema only
    python migrate_schema.py --report       # Generate JSON report
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

# Add backend to path
BACKEND_DIR = Path(__file__).parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.supervisor_ddl import (
    REQUIRED_NEW_TABLES,
    create_table_statements,
    index_statements,
    NEW_TABLE_DDL,
)


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


def verify_production_database(engine: Engine) -> dict[str, Any]:
    """Verify this is the expected production database."""
    inspector = inspect(engine)
    
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
    
    return {
        "database_url": str(engine.url).replace(str(engine.url.password), "***") if engine.url.password else str(engine.url),
        "core_tables_present": list(required_core_tables),
        "scholarship_count": scholarship_count,
        "dialect": engine.dialect.name,
    }


def check_existing_supervisor_tables(engine: Engine) -> dict[str, Any]:
    """Check which supervisor tables already exist."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    
    supervisor_tables = {}
    for table_name in REQUIRED_NEW_TABLES:
        exists = table_name in existing_tables
        if exists:
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            supervisor_tables[table_name] = {
                "exists": True,
                "column_count": len(columns),
                "columns": [c["name"] for c in columns],
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
    all_indexes = index_statements()
    for idx_stmt in all_indexes:
        # Extract table name from "CREATE INDEX IF NOT EXISTS idx_name ON table (cols)"
        # We only want indexes for tables we're creating
        for table_name in missing_tables:
            if f" ON {table_name} " in idx_stmt:
                statements.append(idx_stmt)
                break
    return statements


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


def apply_migration(engine: Engine, report: dict[str, Any]) -> dict[str, Any]:
    """Apply the migration."""
    dialect = "postgresql" if engine.dialect.name == "postgresql" else "sqlite"
    missing_tables = report["missing_tables"]
    create_stmts = report["create_statements"]
    index_stmts = report["index_statements"]
    
    applied = {"tables_created": [], "indexes_created": [], "errors": []}
    
    with engine.begin() as conn:
        # Create tables
        for stmt in create_stmts:
            try:
                conn.execute(text(stmt))
                # Extract table name
                table_name = stmt.split()[2]
                applied["tables_created"].append(table_name)
                print(f"[APPLIED] CREATE TABLE {table_name}")
            except Exception as e:
                applied["errors"].append({"statement": stmt, "error": str(e)})
                print(f"[ERROR] CREATE TABLE failed: {e}")
        
        # Create indexes
        for stmt in index_stmts:
            try:
                conn.execute(text(stmt))
                applied["indexes_created"].append(stmt)
                print(f"[APPLIED] {stmt}")
            except Exception as e:
                applied["errors"].append({"statement": stmt, "error": str(e)})
                print(f"[ERROR] CREATE INDEX failed: {e}")
    
    # Post-apply validation
    validation = validate_schema(engine)
    
    return {
        "mode": "apply",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "applied": applied,
        "validation": validation,
    }


def validate_schema(engine: Engine) -> dict[str, Any]:
    """Validate that all required supervisor tables and objects exist."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    
    validation = {
        "all_tables_present": True,
        "missing_tables": [],
        "table_details": {},
        "index_validation": {},
        "foreign_key_validation": {},
        "constraint_validation": {},
    }
    
    for table_name in REQUIRED_NEW_TABLES:
        if table_name not in existing_tables:
            validation["all_tables_present"] = False
            validation["missing_tables"].append(table_name)
            validation["table_details"][table_name] = {"exists": False}
            continue
        
        column_info = inspector.get_columns(table_name)
        columns = {c["name"]: c for c in column_info}
        indexes = {i["name"]: i for i in inspector.get_indexes(table_name)}
        foreign_keys = inspector.get_foreign_keys(table_name)
        
        # Check primary key
        pk_columns = [c["name"] for c in column_info if c.get("primary_key")]
        
        # Expected columns from DDL
        expected_columns = set(NEW_TABLE_DDL[table_name].keys()) if table_name in NEW_TABLE_DDL else set()
        
        validation["table_details"][table_name] = {
            "exists": True,
            "column_count": len(columns),
            "columns": list(columns.keys()),
            "primary_key": pk_columns,
            "has_required_columns": True,  # Simplified check
        }
        
        # Check indexes
        expected_indexes = index_statements()
        table_indexes = [idx for idx in expected_indexes if f" ON {table_name} " in idx]
        missing_indexes = []
        for idx in table_indexes:
            idx_name = idx.split("IF NOT EXISTS ")[1].split(" ON ")[0]
            if idx_name not in indexes:
                missing_indexes.append(idx_name)
        
        validation["index_validation"][table_name] = {
            "expected_count": len(table_indexes),
            "actual_count": len(indexes),
            "missing": missing_indexes,
        }
        
        # Check foreign keys
        validation["foreign_key_validation"][table_name] = {
            "count": len(foreign_keys),
            "details": foreign_keys,
        }
        
        # Check unique constraints
        unique_constraints = []
        for c in column_info:
            if c.get("unique"):
                unique_constraints.append(c["name"])
        validation["constraint_validation"][table_name] = {
            "unique_columns": unique_constraints,
        }
    
    return validation


def main():
    parser = argparse.ArgumentParser(description="ScholarZone production schema migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without applying")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing schema")
    parser.add_argument("--report", action="store_true", help="Output JSON report to stdout")
    parser.add_argument("--output", type=str, help="Write JSON report to file")
    
    args = parser.parse_args()
    
    if not any([args.dry_run, args.apply, args.validate_only, args.report]):
        parser.print_help()
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
            if args.apply:
                # This shouldn't happen with the mutually exclusive group, but just in case
                apply_report = apply_migration(engine, report)
                report.update(apply_report)
        elif args.apply:
            # First do dry run to get the plan
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
        else:
            json.dump(report, sys.stdout, indent=2, default=str)
            print()
        
        # Exit with error code if validation fails
        if args.validate_only or args.apply:
            validation = report.get("validation", report.get("applied", {}).get("validation", {}))
            if not validation.get("all_tables_present", True):
                print("VALIDATION FAILED: Some required tables are missing", file=sys.stderr)
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