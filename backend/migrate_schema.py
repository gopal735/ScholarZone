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
import socket
import sys
from datetime import date, datetime, timezone
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
        r'FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)\s*(ON DELETE\s+(?:RESTRICT|CASCADE|SET NULL|SET DEFAULT|NO ACTION))?',
        re.IGNORECASE
    )
    for match in fk_pattern.finditer(ddl):
        cols = [c.strip() for c in match.group(1).split(',')]
        ref_table = match.group(2)
        ref_cols = [c.strip() for c in match.group(3).split(',')]
        on_delete = normalize_on_delete(match.group(4)) if match.group(4) else "NO ACTION"
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


def _normalize_index_predicate(predicate: str | None) -> str | None:
    if predicate is None:
        return None
    value = str(predicate).strip().rstrip(";")
    if not value:
        return None
    # Strip balanced outer parentheses commonly added by reflection/catalog renderers.
    changed = True
    while changed and value.startswith("(") and value.endswith(")"):
        changed = False
        depth = 0
        balanced = True
        for i, ch in enumerate(value):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(value) - 1:
                    balanced = False
                    break
                if depth < 0:
                    balanced = False
                    break
        if balanced and depth == 0:
            inner = value[1:-1].strip()
            if inner:
                value = inner
                changed = True
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _parse_index_definition(idx_def: str) -> dict[str, Any] | None:
    """Parse an index definition from NEW_TABLE_INDEXES.

    Supports forms such as:
      ix_name ON table (col1, col2)
      UNIQUE ix_name ON table (col1) WHERE predicate
      CREATE [UNIQUE] INDEX [IF NOT EXISTS] ix_name ON table (col1) [WHERE ...]
    """
    if not idx_def:
        return None
    raw = str(idx_def).strip().rstrip(";")
    raw = re.sub(
        r"^CREATE\s+(?:(UNIQUE)\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?",
        lambda m: ("UNIQUE " if m.group(1) else ""),
        raw,
        flags=re.IGNORECASE,
    ).strip()

    unique = False
    if raw.upper().startswith("UNIQUE "):
        unique = True
        raw = raw[7:].strip()

    match = re.match(
        r'(?P<name>"?\w+"?)\s+ON\s+(?P<table>"?\w+"?(?:\."?\w+"?)?)\s*\((?P<cols>.+?)\)(?:\s+WHERE\s+(?P<predicate>.+))?$',
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        match = re.match(
            r'(?P<name>"?\w+"?)\s*\((?P<cols>.+?)\)(?:\s+WHERE\s+(?P<predicate>.+))?$',
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if not match:
        return None

    cols = [c.strip().strip('"') for c in re.split(r",\s*(?![^()]*\))", match.group("cols")) if c.strip()]
    predicate = _normalize_index_predicate(match.groupdict().get("predicate"))
    return {
        "name": match.group("name").strip().strip('"'),
        "columns": cols,
        "unique": unique,
        "predicate": predicate,
    }


def get_expected_schema(dialect: str) -> dict[str, dict]:
    """Get the expected schema for a dialect from canonical DDL."""
    expected = {}
    for table_name in REQUIRED_NEW_TABLES:
        if table_name not in NEW_TABLE_DDL:
            continue
        ddl = NEW_TABLE_DDL[table_name][dialect]
        indexes = []
        for idx_def in NEW_TABLE_INDEXES.get(table_name, []):
            parsed = _parse_index_definition(idx_def)
            if parsed:
                indexes.append(parsed)
        expected[table_name] = {
            "ddl": ddl,
            "columns": parse_ddl_columns(ddl),
            "composite_constraints": parse_composite_constraints(ddl),
            "foreign_keys": parse_foreign_keys(ddl),
            "indexes": indexes,
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

    # For production use, require expected database identity
    # Check if we're in a test environment
    is_test = os.environ.get("SCHOLARZONE_ENVIRONMENT", "").lower() == "test"
    if not is_test:
        expected_db_id = os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER")
        if not expected_db_id:
            raise RuntimeError(
                "SCHOLARZONE_EXPECTED_DB_IDENTIFIER environment variable must be set for production use. "
                "This is a safety gate to prevent accidental migration to the wrong database. "
                "Set this secret in the GitHub Actions environment (production) to the exact database identifier "
                "(e.g., the Neon database name). Contact the repository owner to configure this secret."
            )

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

            # Check the host/endpoint
            host_result = conn.execute(text("SELECT inet_server_addr()")).scalar()
            db_identity["details"]["host"] = str(host_result) if host_result else "unknown"

            # Require explicit environment variable for production DB identity
            expected_db_id = os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER")
            expected_host = os.environ.get("SCHOLARZONE_EXPECTED_DB_HOST")

            if expected_db_id:
                if expected_db_id == result:
                    db_identity["details"]["database_name_match"] = True
                else:
                    db_identity["details"]["database_name_match"] = False
                    raise RuntimeError(
                        f"Database identity mismatch. Expected identifier '{expected_db_id}' "
                        f"not found in database name '{result}'. "
                        f"Set SCHOLARZONE_EXPECTED_DB_IDENTIFIER to the exact expected database name."
                    )
            else:
                db_identity["details"]["warning"] = "SCHOLARZONE_EXPECTED_DB_IDENTIFIER not set; database name not verified"

            if expected_host:
                # SCHOLARZONE_EXPECTED_DB_HOST may be either the PostgreSQL server IP
                # returned by inet_server_addr() or a resolvable hostname. Resolve
                # hostnames safely so operators can use the Neon endpoint name
                # without weakening the check.
                resolved_expected = expected_host
                if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", expected_host):
                    try:
                        resolved_expected = socket.gethostbyname(expected_host)
                    except (socket.gaierror, OSError) as exc:
                        raise RuntimeError(
                            f"Database host could not be resolved: {expected_host!r}: {exc}"
                        ) from exc
                if resolved_expected == str(host_result):
                    db_identity["details"]["host_match"] = True
                    db_identity["details"]["resolved_expected_host"] = resolved_expected
                else:
                    db_identity["details"]["host_match"] = False
                    raise RuntimeError(
                        f"Database host mismatch. Expected '{expected_host}' (resolved to '{resolved_expected}'), "
                        f"got '{host_result}'. Set SCHOLARZONE_EXPECTED_DB_HOST to the expected database host or IP."
                    )
            else:
                db_identity["details"]["warning"] = (db_identity["details"].get("warning", "") +
                    " SCHOLARZONE_EXPECTED_DB_HOST not set; host not verified").strip()

            # Overall verification: both database name and host must match if provided
            name_ok = db_identity["details"].get("database_name_match", False)
            host_ok = db_identity["details"].get("host_match", False) if os.environ.get("SCHOLARZONE_EXPECTED_DB_HOST") else True
            db_identity["verified"] = name_ok and host_ok

            if not db_identity["verified"] and (os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER") or os.environ.get("SCHOLARZONE_EXPECTED_DB_HOST")):
                raise RuntimeError("Database identity verification failed.")

        except Exception as e:
            if "identity mismatch" in str(e).lower() or "mismatch" in str(e).lower() or "verification failed" in str(e).lower():
                raise
            db_identity["details"]["error"] = str(e)
    elif dialect == "sqlite":
        # For SQLite, verify the database file name matches expected identifier
        try:
            # Get the database file path from PRAGMA database_list
            result = conn.execute(text("PRAGMA database_list")).fetchall()
            if result:
                db_file_path = result[0][2]  # Third column is the file path
                # Extract just the filename without path
                db_filename = os.path.basename(db_file_path)
                # Remove .db extension if present
                db_name = db_filename
                if db_name.endswith('.db'):
                    db_name = db_name[:-3]
                db_identity["details"]["database_name"] = db_name
                db_identity["details"]["database_file_path"] = db_file_path

                # Require explicit environment variable for production DB identity
                expected_db_id = os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER")
                if expected_db_id:
                    # Match against filename (without path) or full path
                    if expected_db_id == db_filename or expected_db_id == db_file_path or expected_db_id == os.path.splitext(db_filename)[0]:
                        db_identity["verified"] = True
                        db_identity["details"]["matched_identifier"] = expected_db_id
                    else:
                        raise RuntimeError(
                            f"Database identity mismatch. Expected identifier '{expected_db_id}' "
                            f"not found in database name '{db_filename}' or file path '{db_file_path}'. "
                            f"Set SCHOLARZONE_EXPECTED_DB_IDENTIFIER to the expected database filename or path."
                        )
                else:
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

        # Fail closed if identity cannot be positively verified when expected identifier is configured
        expected_db_id = os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER")
        if expected_db_id and not db_identity.get("verified", False):
            error_detail = db_identity.get("details", {}).get("error", "identity not verified")
            raise RuntimeError(
                f"Database identity verification failed for {dialect}: {error_detail}. "
                f"Expected identifier: '{expected_db_id}'. "
                f"Cannot proceed with migration against an unverified database."
            )

    return {
        "database_url": str(engine.url).replace(str(engine.url.password), "***") if engine.url.password else str(engine.url),
        "core_tables_present": list(required_core_tables),
        "scholarship_count": scholarship_count,
        "dialect": dialect,
        "identity": db_identity,
    }


def verify_backup_pitr_status(conn: Connection) -> dict[str, Any]:
    """Verify backup/PITR status for the production database.

    This is a placeholder function that documents what needs to be verified.
    Actual verification requires Neon API access or manual confirmation.

    For production use, this should be called with verified credentials from the
    workflow, which should have already performed the backup/PITR verification
    via Neon API or manual attestation.

    Returns a dict with verification status and evidence reference.
    """
    backup_info = {
        "verified": False,
        "details": {
            "note": "Backup/PITR verification requires Neon API access or manual attestation. "
                   "This script cannot automatically verify backup status. "
                   "The workflow must set SCHOLARZONE_BACKUP_VERIFIED=true after verification.",
            "neon_api_check": "not_implemented_in_script",
            "requires_manual_attestation": True,
        }
    }

    # A configured boolean alone is not a sufficient gate. Require a recent,
    # non-future restore test date and a traceable evidence reference before
    # any DDL. This remains an operator attestation: automatic verification
    # requires provider API access that this script does not have.
    backup_verified = os.environ.get("SCHOLARZONE_BACKUP_VERIFIED", "").strip().lower() == "true"
    restore_test_date = os.environ.get("SCHOLARZONE_RESTORE_TEST_DATE", "").strip()
    evidence_ref = os.environ.get("SCHOLARZONE_BACKUP_EVIDENCE_REF", "").strip()
    date_error = None
    try:
        restore_date = datetime.strptime(restore_test_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        restore_date = None
        date_error = "SCHOLARZONE_RESTORE_TEST_DATE must be a valid ISO date (YYYY-MM-DD)"

    today = datetime.now(timezone.utc).date()
    if restore_date and restore_date > today:
        date_error = "SCHOLARZONE_RESTORE_TEST_DATE cannot be in the future"
    elif restore_date and (today - restore_date).days > 30:
        date_error = "restore test evidence is older than 30 days"

    verified = backup_verified and restore_date is not None and bool(evidence_ref) and date_error is None
    backup_info["details"].update({
        "manual_attestation": True,
        "verification_method": "operator_attestation",
        "date_error": date_error,
        "backup_verified": backup_verified,
        "restore_test_date": restore_test_date,
        "evidence_ref": evidence_ref,
    })
    if verified:
        backup_info["verified"] = True
        backup_info["details"]["note"] = "Backup/PITR prerequisites passed via operator attestation."
    else:
        backup_info["details"]["note"] = date_error or (
            "SCHOLARZONE_BACKUP_VERIFIED must be true and backup evidence reference must be supplied"
        )

    return backup_info


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


def generate_index_statements(engine: Engine, missing_tables: list[str], existing_tables_info: dict = None) -> list[str]:
    """Generate CREATE INDEX statements for missing tables AND existing tables with missing indexes.

    Args:
        engine: Database engine for inspecting existing indexes
        missing_tables: List of table names that don't exist yet
        existing_tables_info: Optional dict from check_existing_supervisor_tables with index info

    Returns:
        List of CREATE INDEX IF NOT EXISTS statements
    """
    statements = []
    inspector = inspect(engine)

    # First, generate indexes for completely missing tables
    for table_name in missing_tables:
        for idx in index_statements():
            if f" ON {table_name} " in idx:
                statements.append(idx)

    # Then, check existing tables for missing required indexes
    if existing_tables_info:
        for table_name, info in existing_tables_info.get("tables", {}).items():
            if not info.get("exists", False):
                continue

            # Get actual indexes for this table
            existing_indexes = {i["name"]: i for i in inspector.get_indexes(table_name)}

            # Check each required index for this table
            for idx in index_statements():
                if f" ON {table_name} " not in idx:
                    continue

                idx_name = idx.split("IF NOT EXISTS ")[1].split(" ON ")[0]
                if idx_name not in existing_indexes:
                    statements.append(idx)
                    print(f"[REPAIR] Missing index {idx_name} on {table_name} will be created")

    return statements



def _index_has_predicate(index_info: dict) -> bool:
    """Return True when an index is partial/restricted."""
    if index_info.get("predicate") is not None:
        return True
    options = index_info.get("dialect_options") or {}
    for key, value in options.items():
        if value is not None and ("where" in key or "predicate" in key):
            return True
    return False


# ============================================================
# Full-schema reconciliation: scholarships columns, image_reviews
# ============================================================

SCHOLARSHIP_ADDITIONS: dict[str, str] = {
    "legacy_id": "INTEGER",
    "image_url": "VARCHAR(2048)",
    "image_source_url": "VARCHAR(2048)",
    "image_source_type": "VARCHAR(32)",
    "image_kind": "VARCHAR(32)",
    "image_verified_at": "TIMESTAMPTZ",
    "image_alt_text": "VARCHAR(512)",
    "image_evaluation_status": "VARCHAR(32)",
    "image_evaluated_at": "TIMESTAMPTZ",
    "is_archived": "BOOLEAN NOT NULL DEFAULT FALSE",
    "archived_at": "TIMESTAMPTZ",
    "archived_reason": "VARCHAR(120)",
    "funding_amount": "NUMERIC(12, 2)",
    "funding_currency": "VARCHAR(8)",
    "funding_period": "VARCHAR(64)",
    "tuition_coverage": "BOOLEAN",
    "living_cost_coverage": "BOOLEAN",
    "travel_coverage": "BOOLEAN",
    "fully_funded": "BOOLEAN",
    "funding_details": "JSON",
    "official_details": "JSON",
    "applicant_utility": "JSON",
    "programme_verification": "JSON",
    "auto_delete_candidate_since": "TIMESTAMPTZ",
    "deletion_protected": "BOOLEAN NOT NULL DEFAULT FALSE",
    "departments": "JSON",
    "eligible_fields": "JSON",
    "eligible_programmes": "JSON",
    "academic_provenance": "JSON",
}

SCHOLARSHIP_UNIQUE_INDEXES: list[str] = [
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_scholarships_legacy_id ON scholarships (legacy_id)",
]


IMAGE_REVIEWS_DDL: dict[str, str] = {
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
}

IMAGE_REVIEWS_INDEXES: list[str] = [
    "ix_image_reviews_scholarship_decision ON image_reviews (scholarship_id, decision)",
    "ix_image_reviews_created_at ON image_reviews (created_at)",
]

ADDITIONAL_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS ix_scholarships_is_archived ON scholarships (is_archived)",
    "CREATE INDEX IF NOT EXISTS ix_maintenance_runs_slot_id ON maintenance_runs (slot_id)",
]

IMAGE_REVIEWS_COLUMNS: dict[str, str] = {
    "id": "INTEGER PRIMARY KEY",
    "scholarship_id": "INTEGER NOT NULL",
    "image_url": "VARCHAR(2048) NOT NULL",
    "image_kind": "VARCHAR(32) NOT NULL",
    "source_page": "VARCHAR(2048)",
    "source_type": "VARCHAR(32)",
    "relevance_evidence": "TEXT",
    "licensing_status": "VARCHAR(32)",
    "licensing_evidence": "TEXT",
    "confidence": "VARCHAR(32) NOT NULL",
    "reason_for_review": "VARCHAR(255)",
    "decision": "VARCHAR(16) NOT NULL DEFAULT 'pending'",
    "reviewed_by": "VARCHAR(120)",
    "reviewed_at": "TIMESTAMPTZ",
    "reviewer_note": "TEXT",
    "created_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
}


def check_existing_scholarship_columns(engine: Engine) -> dict[str, bool]:
    """Return presence of each scholarship additional column."""
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("scholarships")}
    return {name: name in columns for name in SCHOLARSHIP_ADDITIONS}


def generate_scholarship_column_statements(missing_columns: list[str]) -> list[str]:
    """Generate ALTER TABLE statements for missing scholarship columns."""
    return [
        f"ALTER TABLE scholarships ADD COLUMN {name} {SCHOLARSHIP_ADDITIONS[name]}"
        for name in missing_columns
    ]


def check_existing_image_reviews(engine: Engine) -> dict[str, Any]:
    """Inspect image_reviews table existence and indexes."""
    inspector = inspect(engine)
    exists = inspector.has_table("image_reviews")
    indexes = set()
    if exists:
        indexes = {i["name"] for i in inspector.get_indexes("image_reviews")}
    return {"exists": exists, "indexes": indexes}


def generate_image_reviews_statements(dialect: str, exists: bool, existing_indexes: set[str]) -> tuple[list[str], list[str]]:
    """Generate image_reviews create/index statements."""
    create_stmts = []
    index_stmts = []
    if not exists:
        ddl = IMAGE_REVIEWS_DDL[dialect]
        create_stmts.append(f"CREATE TABLE IF NOT EXISTS image_reviews ({ddl})")
    for idx in IMAGE_REVIEWS_INDEXES:
        idx_name = idx.split(" ON ")[0]
        if idx_name not in existing_indexes:
            index_stmts.append(f"CREATE INDEX IF NOT EXISTS {idx}")
    return create_stmts, index_stmts


# ============================================================
# Dry Run
# ============================================================
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
    index_stmts = generate_index_statements(engine, missing_tables, table_info)

    # Scholarship column reconciliation
    scholarship_columns = check_existing_scholarship_columns(engine)
    missing_scholarship_columns = [name for name, present in scholarship_columns.items() if not present]
    scholarship_column_stmts = generate_scholarship_column_statements(missing_scholarship_columns)

    # Scholarship unique indexes (legacy_id)
    scholarship_unique_index_stmts = []
    inspector = inspect(engine)
    existing_scholarship_indexes = {i["name"] for i in inspector.get_indexes("scholarships")} if inspector.has_table("scholarships") else set()
    for stmt in SCHOLARSHIP_UNIQUE_INDEXES:
        idx_name = stmt.split("IF NOT EXISTS ")[1].split(" ON ")[0]
        if idx_name not in existing_scholarship_indexes:
            scholarship_unique_index_stmts.append(stmt)

    # image_reviews reconciliation
    image_reviews_info = check_existing_image_reviews(engine)
    image_reviews_create_stmts, image_reviews_index_stmts = generate_image_reviews_statements(
        dialect, image_reviews_info["exists"], image_reviews_info["indexes"]
    )

    # Additional required indexes (scholarships, maintenance_runs)
    inspector = inspect(engine)
    additional_index_stmts = []
    for stmt in ADDITIONAL_INDEXES:
        idx_name = stmt.split("IF NOT EXISTS ")[1].split(" ON ")[0]
        table_name = stmt.split(" ON ")[1].split(" (")[0]
        if not inspector.has_table(table_name):
            continue
        existing_indexes = {i["name"] for i in inspector.get_indexes(table_name)}
        if idx_name not in existing_indexes:
            additional_index_stmts.append(stmt)

    # Read-only validation result, so operators can review incorrect existing
    # objects before apply.
    validation = validate_schema(engine)

    return {
        "mode": "dry-run",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "database": db_info,
        "validation": validation,
        "supervisor_tables": table_info,
        "missing_tables": missing_tables,
        "create_statements": create_stmts,
        "index_statements": index_stmts,
        "scholarship_columns": scholarship_columns,
        "missing_scholarship_columns": missing_scholarship_columns,
        "scholarship_column_statements": scholarship_column_stmts,
        "scholarship_unique_index_statements": scholarship_unique_index_stmts,
        "image_reviews": image_reviews_info,
        "missing_image_reviews_indexes": [idx.split(" ON ")[0] for idx in IMAGE_REVIEWS_INDEXES if idx.split(" ON ")[0] not in image_reviews_info["indexes"]],
        "image_reviews_create_statements": image_reviews_create_stmts,
        "image_reviews_index_statements": image_reviews_index_stmts,
        "additional_index_statements": additional_index_stmts,
        "total_statements": len(create_stmts) + len(index_stmts) + len(scholarship_column_stmts) + len(scholarship_unique_index_stmts) + len(image_reviews_create_stmts) + len(image_reviews_index_stmts) + len(additional_index_stmts),
    }


# ============================================================
# Index Helpers for Validation (SQLite auto-generated indexes)
# ============================================================



def apply_migration(engine: Engine, report: dict[str, Any]) -> dict[str, Any]:
    """Apply the migration with full transactional validation.

    All DDL and validation happen in a SINGLE transaction.
    If validation fails, the entire transaction rolls back.
    """
    dialect = "postgresql" if engine.dialect.name == "postgresql" else "sqlite"

    # PRE-APPLY SAFETY GATE: Verify production database identity immediately before mutation.
    db_info = verify_production_database(engine)

    # PRE-APPLY SAFETY GATE: Verify backup/PITR status before any DDL
    with engine.connect() as conn:
        backup_status = verify_backup_pitr_status(conn)
        if not backup_status["verified"]:
            error_msg = "BACKUP/PITR VERIFICATION FAILED: " + json.dumps(backup_status, indent=2, default=str)
            print(f"[ERROR] {error_msg}", file=sys.stderr)
            raise RuntimeError(f"Backup/PITR gate failed: {error_msg}")
        print(f"[INFO] Backup/PITR verification passed: {backup_status['details'].get('evidence_ref', 'unknown')}")

    # Build the reviewed plan from the dry-run report when available, otherwise
    # recompute it from the live schema. This keeps apply aligned with dry-run
    # while remaining safe if a stale report is supplied.
    missing_tables = report.get("missing_tables")
    create_stmts = report.get("create_statements")
    index_stmts = report.get("index_statements")
    scholarship_column_stmts = report.get("scholarship_column_statements")
    scholarship_unique_index_stmts = report.get("scholarship_unique_index_statements")
    image_reviews_create_stmts = report.get("image_reviews_create_statements")
    image_reviews_index_stmts = report.get("image_reviews_index_statements")
    additional_index_stmts = report.get("additional_index_statements")

    if missing_tables is None:
        table_info = check_existing_supervisor_tables(engine)
        missing_tables = [t for t, info in table_info["tables"].items() if not info["exists"]]
    if create_stmts is None:
        create_stmts = generate_create_statements(dialect, missing_tables)
    if index_stmts is None:
        table_info = check_existing_supervisor_tables(engine)
        index_stmts = generate_index_statements(engine, missing_tables, table_info)
    if scholarship_column_stmts is None:
        missing_scholarship_columns = [name for name, present in check_existing_scholarship_columns(engine).items() if not present]
        scholarship_column_stmts = generate_scholarship_column_statements(missing_scholarship_columns)
    if scholarship_unique_index_stmts is None:
        inspector = inspect(engine)
        existing_scholarship_indexes = {i["name"] for i in inspector.get_indexes("scholarships")} if inspector.has_table("scholarships") else set()
        scholarship_unique_index_stmts = [stmt for stmt in SCHOLARSHIP_UNIQUE_INDEXES if stmt.split("IF NOT EXISTS ")[1].split(" ON ")[0] not in existing_scholarship_indexes]
    if image_reviews_create_stmts is None or image_reviews_index_stmts is None:
        ir_info = check_existing_image_reviews(engine)
        image_reviews_create_stmts, image_reviews_index_stmts = generate_image_reviews_statements(
            dialect, ir_info["exists"], ir_info["indexes"]
        )
    if additional_index_stmts is None:
        inspector = inspect(engine)
        additional_index_stmts = []
        for stmt in ADDITIONAL_INDEXES:
            idx_name = stmt.split("IF NOT EXISTS ")[1].split(" ON ")[0]
            table_name = stmt.split(" ON ")[1].split(" (")[0]
            if not inspector.has_table(table_name):
                continue
            existing_indexes = {i["name"] for i in inspector.get_indexes(table_name)}
            if idx_name not in existing_indexes:
                additional_index_stmts.append(stmt)

    applied = {"tables_created": [], "indexes_created": [], "columns_added": [], "errors": []}
    validation = None

    # Use a single transaction for all DDL AND validation.
    if dialect == "sqlite":
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                for stmt in create_stmts:
                    try:
                        conn.execute(text(stmt))
                        table_name = stmt.split()[2]
                        applied["tables_created"].append(table_name)
                        print(f"[APPLIED] CREATE TABLE {table_name}")
                    except Exception as e:
                        applied["errors"].append({"statement": stmt, "error": str(e)})
                        print(f"[ERROR] CREATE TABLE failed: {e}")
                        raise

                for stmt in index_stmts:
                    try:
                        conn.execute(text(stmt))
                        applied["indexes_created"].append(stmt)
                        print(f"[APPLIED] {stmt}")
                    except Exception as e:
                        applied["errors"].append({"statement": stmt, "error": str(e)})
                        print(f"[ERROR] CREATE INDEX failed: {e}")
                        raise

                for stmt in scholarship_column_stmts:
                    try:
                        conn.execute(text(stmt))
                        applied["columns_added"].append(stmt)
                        print(f"[APPLIED] {stmt}")
                    except Exception as e:
                        applied["errors"].append({"statement": stmt, "error": str(e)})
                        print(f"[ERROR] ADD COLUMN failed: {e}")
                        raise

                for stmt in scholarship_unique_index_stmts:
                    try:
                        conn.execute(text(stmt))
                        applied["indexes_created"].append(stmt)
                        print(f"[APPLIED] {stmt}")
                    except Exception as e:
                        applied["errors"].append({"statement": stmt, "error": str(e)})
                        print(f"[ERROR] CREATE INDEX failed: {e}")
                        raise

                for stmt in image_reviews_create_stmts:
                    try:
                        conn.execute(text(stmt))
                        applied["tables_created"].append("image_reviews")
                        print(f"[APPLIED] {stmt}")
                    except Exception as e:
                        applied["errors"].append({"statement": stmt, "error": str(e)})
                        print(f"[ERROR] CREATE TABLE failed: {e}")
                        raise
                for stmt in image_reviews_index_stmts:
                    try:
                        conn.execute(text(stmt))
                        applied["indexes_created"].append(stmt)
                        print(f"[APPLIED] {stmt}")
                    except Exception as e:
                        applied["errors"].append({"statement": stmt, "error": str(e)})
                        print(f"[ERROR] CREATE INDEX failed: {e}")
                        raise

                for stmt in additional_index_stmts:
                    try:
                        conn.execute(text(stmt))
                        applied["indexes_created"].append(stmt)
                        print(f"[APPLIED] {stmt}")
                    except Exception as e:
                        applied["errors"].append({"statement": stmt, "error": str(e)})
                        print(f"[ERROR] CREATE INDEX failed: {e}")
                        raise

                validation = validate_schema_with_connection(conn)
                if not validation.get("valid", False):
                    error_msg = "SCHEMA VALIDATION FAILED: " + json.dumps(
                        {k: v for k, v in validation.items() if k != "table_details"},
                        indent=2
                    )
                    print(f"[ERROR] {error_msg}", file=sys.stderr)
                    raise RuntimeError(error_msg)

                trans.commit()
            except Exception:
                if trans.is_active:
                    trans.rollback()
                raise
    else:
        with engine.begin() as conn:
            for stmt in create_stmts:
                try:
                    conn.execute(text(stmt))
                    table_name = stmt.split()[2]
                    applied["tables_created"].append(table_name)
                    print(f"[APPLIED] CREATE TABLE {table_name}")
                except Exception as e:
                    applied["errors"].append({"statement": stmt, "error": str(e)})
                    print(f"[ERROR] CREATE TABLE failed: {e}")
                    raise

            for stmt in index_stmts:
                try:
                    conn.execute(text(stmt))
                    applied["indexes_created"].append(stmt)
                    print(f"[APPLIED] {stmt}")
                except Exception as e:
                    applied["errors"].append({"statement": stmt, "error": str(e)})
                    print(f"[ERROR] CREATE INDEX failed: {e}")
                    raise

            for stmt in scholarship_column_stmts:
                try:
                    conn.execute(text(stmt))
                    applied["columns_added"].append(stmt)
                    print(f"[APPLIED] {stmt}")
                except Exception as e:
                    applied["errors"].append({"statement": stmt, "error": str(e)})
                    print(f"[ERROR] ADD COLUMN failed: {e}")
                    raise

            for stmt in scholarship_unique_index_stmts:
                try:
                    conn.execute(text(stmt))
                    applied["indexes_created"].append(stmt)
                    print(f"[APPLIED] {stmt}")
                except Exception as e:
                    applied["errors"].append({"statement": stmt, "error": str(e)})
                    print(f"[ERROR] CREATE INDEX failed: {e}")
                    raise

            for stmt in image_reviews_create_stmts:
                try:
                    conn.execute(text(stmt))
                    applied["tables_created"].append("image_reviews")
                    print(f"[APPLIED] {stmt}")
                except Exception as e:
                    applied["errors"].append({"statement": stmt, "error": str(e)})
                    print(f"[ERROR] CREATE TABLE failed: {e}")
                    raise
            for stmt in image_reviews_index_stmts:
                try:
                    conn.execute(text(stmt))
                    applied["indexes_created"].append(stmt)
                    print(f"[APPLIED] {stmt}")
                except Exception as e:
                    applied["errors"].append({"statement": stmt, "error": str(e)})
                    print(f"[ERROR] CREATE INDEX failed: {e}")
                    raise

            for stmt in additional_index_stmts:
                try:
                    conn.execute(text(stmt))
                    applied["indexes_created"].append(stmt)
                    print(f"[APPLIED] {stmt}")
                except Exception as e:
                    applied["errors"].append({"statement": stmt, "error": str(e)})
                    print(f"[ERROR] CREATE INDEX failed: {e}")
                    raise

            validation = validate_schema_with_connection(conn)
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
        "database": db_info,
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


def normalize_type(dialect: str, type_str: Any) -> str:
    """Normalize type string for dialect-aware comparison.

    Preserves length specifications for relevant type dimensions:
    - VARCHAR length
    - NUMERIC precision/scale
    - timestamp timezone
    - dialect-specific equivalent types
    """
    if type_str is None:
        return ""

    text_value = str(type_str).upper().strip()

    # Handle common aliases first
    text_value = text_value.replace("TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ")
    text_value = text_value.replace("TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP")
    text_value = text_value.replace("CHARACTER VARYING", "VARCHAR")
    text_value = text_value.replace("CHAR VARYING", "VARCHAR")

    # SQLite uses NUMERIC for what PostgreSQL calls TIMESTAMPTZ (Unix timestamp)
    # and commonly reflects timestamps as DATETIME.
    if dialect == "sqlite":
        text_value = text_value.replace("TIMESTAMPTZ", "NUMERIC")
        text_value = text_value.replace("TIMESTAMP", "DATETIME")
        text_value = text_value.replace("NUMERIC", "DECIMAL")
    else:
        text_value = text_value.replace("NUMERIC", "DECIMAL")

    return re.sub(r"\s+", " ", text_value).strip()


def types_match(dialect: str, expected_type: str, actual_type: Any) -> bool:
    """Check if types match with dialect awareness."""
    norm_expected = normalize_type(dialect, expected_type)
    actual_text = str(actual_type)
    # SQLAlchemy renders both PostgreSQL TIMESTAMP variants as ``TIMESTAMP``
    # in str(); the timezone flag is the distinguishing schema detail.
    if (
        dialect == "postgresql"
        and actual_text.upper().startswith("TIMESTAMP")
        and getattr(actual_type, "timezone", False)
    ):
        actual_text = "TIMESTAMP WITH TIME ZONE"
    norm_actual = normalize_type(dialect, actual_text)
    return norm_expected == norm_actual


def defaults_match(expected: Any, actual: Any) -> bool:
    """Compare defaults while normalizing harmless PostgreSQL rendering."""
    if expected is None or actual is None:
        return expected is actual

    def canonical(value: Any) -> str:
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        rendered = re.sub(r"\s+", " ", str(value).strip())
        if rendered == "0":
            return "FALSE"
        if rendered == "1":
            return "TRUE"
        if rendered.lower() in {"true", "false"}:
            return rendered.upper()
        if re.fullmatch(r"now\(\)(?:::timestamp(?: with time zone)?)?", rendered, re.IGNORECASE):
            return "NOW()"
        if rendered.lower() == "current_timestamp":
            return "NOW()"
        literal = re.fullmatch(
            r"('(?:''|[^'])*')(?:\s*::\s*[a-z_][a-z_ ]*(?:\(\d+(?:,\s*\d+)?\))?)?",
            rendered,
            re.IGNORECASE,
        )
        if literal:
            return literal.group(1)
        return rendered

    return canonical(expected) == canonical(actual)





# ============================================================
# Index Helpers for Validation
# ============================================================

def _sqlite_index_sql(conn: Connection, index_name: str) -> str | None:
    row = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='index' AND name = :name"),
        {"name": index_name},
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def _extract_sqlite_index_predicate(index_sql: str | None) -> str | None:
    if not index_sql:
        return None
    match = re.search(r"\bWHERE\s+(.+)$", str(index_sql), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _normalize_index_predicate(match.group(1))


def _postgresql_index_predicate_info(
    conn: Connection, schema: str | None, table_name: str, index_name: str
) -> tuple[str | None, bool]:
    """Return (predicate, predicate_known).

    predicate_known is False when PostgreSQL reports the index as partial but the
    predicate expression cannot be retrieved from authoritative catalog metadata.
    """
    schema = schema or "public"
    row = conn.execute(
        text(
            """
            SELECT pg_get_expr(i.indpred, i.indrelid) AS predicate, i.indpred IS NOT NULL AS is_partial
            FROM pg_index i
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_class tbl ON tbl.oid = i.indrelid
            JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
            WHERE ns.nspname = :schema AND tbl.relname = :table_name AND idx.relname = :index_name
            """
        ),
        {"schema": schema, "table_name": table_name, "index_name": index_name},
    ).fetchone()
    if not row:
        # If not found in catalog, treat as unrestricted/known absent predicate.
        return None, True
    is_partial = bool(row[1])
    predicate = _normalize_index_predicate(row[0]) if row[0] is not None else None
    if is_partial and predicate is None:
        return None, False
    return predicate, True


def get_all_indexes_with_pragma(conn: Connection, table_name: str) -> list[dict]:
    """Get all indexes with normalized columns, uniqueness, predicate, and predicate_known.

    Uses the provided connection so validation can observe uncommitted DDL within
    the same transaction. Does not treat missing predicate metadata as proof that
    an index is unrestricted when partiality is indicated but the predicate cannot
    be recovered.
    """
    dialect = conn.engine.dialect.name
    if dialect == "sqlite":
        result = conn.execute(text(f'PRAGMA index_list("{table_name}")'))
        indexes = []
        for row in result:
            # PRAGMA index_list: (seq, name, unique, origin, partial)
            idx_name = row[1]
            is_unique = bool(row[2])
            partial_flag = bool(row[4]) if len(row) > 4 else False
            col_result = conn.execute(text(f'PRAGMA index_info("{idx_name}")'))
            columns = [col_row[2] for col_row in col_result]
            predicate = None
            predicate_known = True
            if partial_flag:
                predicate = _extract_sqlite_index_predicate(_sqlite_index_sql(conn, idx_name))
                predicate_known = predicate is not None
            indexes.append({
                "name": idx_name,
                "unique": is_unique,
                "column_names": columns,
                "predicate": predicate,
                "predicate_known": predicate_known,
                "partial": partial_flag,
            })
        return indexes

    # PostgreSQL (and others via inspector + PG catalog fallback for predicate)
    inspector = inspect(conn)
    schema = getattr(inspector, "default_schema_name", None) or "public"
    indexes = []
    for i in inspector.get_indexes(table_name):
        name = i.get("name")
        dialect_options = i.get("dialect_options") or {}
        pg_opts = dialect_options.get("postgresql", {}) if isinstance(dialect_options, dict) else {}
        predicate = None
        predicate_known = True

        if "where" in pg_opts and pg_opts.get("where") is not None:
            predicate = _normalize_index_predicate(pg_opts.get("where"))
        elif i.get("predicate") is not None:
            predicate = _normalize_index_predicate(i.get("predicate"))
        else:
            predicate, predicate_known = _postgresql_index_predicate_info(conn, schema, table_name, name)

        indexes.append({
            "name": name,
            "unique": bool(i.get("unique", False)),
            "column_names": list(i.get("column_names") or []),
            "predicate": predicate,
            "predicate_known": predicate_known,
        })
    return indexes



def validate_schema_with_connection(conn: Connection) -> dict[str, Any]:
    """Validate schema against canonical DDL using the given transaction connection.

    This allows validation within the same transaction as DDL application.
    """
    # Use the connection directly for inspection to see uncommitted DDL
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    dialect = "postgresql" if conn.engine.dialect.name == "postgresql" else "sqlite"
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
        pk_info = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        for col_name, expected_col in expected_columns.items():
            actual_col = actual_columns.get(col_name)
            if not actual_col:
                column_results[col_name] = {"status": "MISSING", "expected": expected_col}
                table_ok = False
                continue

            # Exact type matching (dialect-aware)
            actual_type = actual_col.get("type", "")
            type_ok = types_match(dialect, expected_col["type"], actual_type)

            # Check nullable
            expected_nullable = expected_col["nullable"]
            actual_nullable = actual_col.get("nullable", True)
            nullable_ok = expected_nullable == actual_nullable

            # Check primary key
            expected_pk = expected_col["primary_key"]
            actual_pk_bool = col_name in pk_info
            pk_ok = expected_pk == actual_pk_bool

            # Primary key columns are implicitly NOT NULL
            if expected_pk:
                nullable_ok = True

            # Validate PostgreSQL GENERATED ALWAYS AS IDENTITY for canonical ID columns
            identity_ok = True
            identity_actual = actual_col.get("identity")
            if dialect == "postgresql" and expected_pk and col_name == "id":
                always = None
                if identity_actual is None or identity_actual is False:
                    identity_ok = False
                elif isinstance(identity_actual, str):
                    upper = identity_actual.upper()
                    identity_ok = upper == "ALWAYS"
                    if upper == "BY DEFAULT":
                        always = False
                elif isinstance(identity_actual, dict):
                    if "always" in identity_actual:
                        always = identity_actual.get("always")
                        identity_ok = bool(always) is True
                    elif "generated" in identity_actual:
                        gen = str(identity_actual.get("generated", "")).upper()
                        identity_ok = gen == "ALWAYS"
                        if gen == "BY DEFAULT":
                            always = False
                    else:
                        identity_ok = False
                else:
                    # SQLAlchemy 2.x may reflect an Identity object
                    if hasattr(identity_actual, "always"):
                        try:
                            always = getattr(identity_actual, "always")
                        except Exception:
                            always = None
                        identity_ok = bool(always) is True
                    elif hasattr(identity_actual, "get"):
                        try:
                            if "always" in identity_actual:
                                always = identity_actual.get("always")
                                identity_ok = bool(always) is True
                            elif "generated" in identity_actual:
                                gen = str(identity_actual.get("generated", "")).upper()
                                identity_ok = gen == "ALWAYS"
                                if gen == "BY DEFAULT":
                                    always = False
                            else:
                                identity_ok = False
                        except Exception:
                            identity_ok = False
                    else:
                        identity_ok = False
                # Reject missing identity, BY DEFAULT, or unrecognized metadata.
                if always is False:
                    identity_ok = False

            # Check unique (column-level)
            expected_unique = expected_col["unique"]
            actual_unique = actual_col.get("unique", False)
            unique_ok = expected_unique == actual_unique

            # Check default value
            expected_default = expected_col.get("default")
            actual_default = actual_col.get("default")
            default_ok = True

            # Default validation: both expected and actual must match exactly
            # If expected has a default, actual must have the same default
            # If expected has no default, actual must not have a default
            default_ok = defaults_match(expected_default, actual_default)

            actual_type_label = str(actual_type)
            if (
                dialect == "postgresql"
                and actual_type_label.upper().startswith("TIMESTAMP")
                and getattr(actual_type, "timezone", False)
            ):
                actual_type_label = "TIMESTAMP WITH TIME ZONE"

            col_ok = type_ok and nullable_ok and pk_ok and unique_ok and default_ok and identity_ok
            if not col_ok:
                table_ok = False

            column_results[col_name] = {
                "status": "OK" if col_ok else "MISMATCH",
                "expected": expected_col,
                "actual": {
                    "type": actual_type_label,
                    "nullable": actual_nullable,
                    "primary_key": actual_pk_bool,
                    "unique": actual_unique,
                    "default": actual_default,
                    "identity": actual_col.get("identity") if dialect == "postgresql" and expected_pk and col_name == "id" else None,
                },
                "checks": {
                    "type": type_ok,
                    "nullable": nullable_ok,
                    "primary_key": pk_ok,
                    "unique": unique_ok,
                    "default": default_ok,
                    "identity": identity_ok,
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
            if expected_comp.get("type") != "UNIQUE":
                continue
            found = False
            rejected_partial = False
            expected_cols = list(expected_comp.get("columns") or [])
            # Search ALL matching unique indexes. We must continue searching after
            # rejecting a partial unique index, because a later unrestricted
            # matching unique index may satisfy the constraint.
            for idx in actual_indexes:
                if not bool(idx.get("unique")):
                    continue
                if list(idx.get("column_names") or []) != expected_cols:
                    continue
                predicate = _normalize_index_predicate(idx.get("predicate"))
                predicate_known = bool(idx.get("predicate_known", True))
                # An unrestricted UNIQUE constraint is required. Reject partial unique
                # indexes and reject indeterminate indexes where partiality cannot be
                # proven absent from authoritative metadata.
                if predicate is not None or not predicate_known:
                    # This matching unique index is partial or indeterminate; it cannot
                    # satisfy the unrestricted UNIQUE constraint. Continue searching.
                    rejected_partial = True
                    continue
                # Found a valid unrestricted unique index matching the constraint.
                found = True
                break
            if found:
                composite_results.append({
                    "name": expected_comp.get("name"),
                    "columns": expected_cols,
                    "found": True,
                })
            else:
                composite_results.append({
                    "name": expected_comp.get("name"),
                    "columns": expected_cols,
                    "found": False,
                    "reason": "partial_unique_index_rejected" if rejected_partial else "no_matching_index",
                })
                table_ok = False

        validation["composite_unique_validation"][table_name] = {
            "expected": expected.get("composite_constraints", []),
            "results": composite_results,
        }

        # Index validation - exact columns, order, uniqueness, and predicate.
        # Match by attributes, not just name.
        missing_indexes = []
        index_details = {}
        expected_indexes_list = expected.get("indexes", [])
        for expected_idx in expected_indexes_list:
            expected_cols = list(expected_idx.get("columns", []))
            expected_unique = bool(expected_idx.get("unique", False))
            expected_predicate = _normalize_index_predicate(expected_idx.get("predicate"))
            expected_name = expected_idx.get("name")

            found = False
            for actual_idx in actual_indexes:
                actual_cols = list(actual_idx.get("column_names") or [])
                actual_unique = bool(actual_idx.get("unique", False))
                actual_predicate = _normalize_index_predicate(actual_idx.get("predicate"))
                actual_predicate_known = bool(actual_idx.get("predicate_known", True))

                if actual_cols != expected_cols or actual_unique != expected_unique:
                    continue

                if expected_predicate is None:
                    # Unrestricted index required: reject partial or indeterminate indexes.
                    if actual_predicate is not None or not actual_predicate_known:
                        continue
                else:
                    # Partial index required: predicate must be known and match (normalized).
                    if not actual_predicate_known or actual_predicate != expected_predicate:
                        continue

                found = True
                index_details[expected_name] = {
                    "found": True,
                    "unique": actual_unique,
                    "columns": actual_cols,
                    "predicate": actual_predicate,
                }
                break

            if not found:
                missing_indexes.append(expected_name)
                table_ok = False
                index_details[expected_name] = {
                    "found": False,
                    "expected_columns": expected_cols,
                    "expected_unique": expected_unique,
                    "expected_predicate": expected_predicate,
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
        dialect = "postgresql" if conn.engine.dialect.name == "postgresql" else "sqlite"

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

                    # For SQLite, RESTRICT in DDL maps to NO ACTION in actual (SQLite doesn't support ON DELETE RESTRICT)
                    if dialect == "sqlite" and expected_on_delete == "RESTRICT" and actual_on_delete == "NO ACTION":
                        on_delete_match = True
                    else:
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
            "primary_key": inspector.get_pk_constraint(table_name).get("constrained_columns", []),
            "has_required_columns": table_ok,
        }

        if not table_ok:
            validation["valid"] = False

    # Scholarship additional columns validation
    scholarship_column_results = {}
    scholarship_columns_ok = True
    try:
        actual_scholarship_columns = {c["name"]: c for c in inspector.get_columns("scholarships")}
    except Exception:
        actual_scholarship_columns = {}
    for col_name, col_type in SCHOLARSHIP_ADDITIONS.items():
        actual = actual_scholarship_columns.get(col_name)
        if actual is None:
            scholarship_column_results[col_name] = {"status": "MISSING"}
            scholarship_columns_ok = False
            continue
        expected_type_match = re.match(r"^([A-Za-z_]+(?:\([^)]*\))?)", col_type.strip())
        expected_type = expected_type_match.group(1) if expected_type_match else col_type.split()[0]
        expected_nullable = "NOT NULL" not in col_type.upper() and "PRIMARY KEY" not in col_type.upper()
        expected_unique = "UNIQUE" in col_type.upper()
        default_match = re.search(r"DEFAULT\s+(.+)", col_type, re.IGNORECASE)
        expected_default = default_match.group(1).strip() if default_match else None

        actual_type_obj = actual.get("type", "")
        actual_type = str(actual_type_obj)
        if dialect == "postgresql":
            type_ok = types_match(dialect, expected_type, actual_type_obj)
        else:
            # SQLite reflects TIMESTAMPTZ columns as DATETIME in this schema.
            if expected_type == "TIMESTAMPTZ" and actual_type.upper() in {"DATETIME", "TIMESTAMP", "NUMERIC"}:
                type_ok = True
            else:
                type_ok = types_match(dialect, expected_type, actual_type_obj)
        nullable_ok = (expected_nullable == actual.get("nullable", True)) or ("PRIMARY KEY" in col_type.upper())

        actual_unique = bool(actual.get("unique", False))
        if expected_unique:
            if not actual_unique:
                try:
                    actual_unique = any(
                        idx.get("unique")
                        and idx.get("column_names") == [col_name]
                        and not _index_has_predicate(idx)
                        for idx in inspector.get_indexes("scholarships")
                    )
                except Exception:
                    actual_unique = False
            if not actual_unique:
                try:
                    actual_unique = any(
                        (uc.get("column_names") or []) == [col_name]
                        for uc in inspector.get_unique_constraints("scholarships")
                    )
                except Exception:
                    actual_unique = False
        else:
            # Do not accept an unexpected uniqueness constraint as a match.
            pass
        unique_ok = (expected_unique == actual_unique)

        default_ok = defaults_match(expected_default, actual.get("default"))
        col_ok = type_ok and nullable_ok and unique_ok and default_ok
        if not col_ok:
            scholarship_columns_ok = False
        scholarship_column_results[col_name] = {
            "status": "OK" if col_ok else "MISMATCH",
            "expected_type": col_type,
            "actual_type": str(actual.get("type", "")),
            "type_ok": type_ok,
            "nullable_ok": nullable_ok,
            "unique_ok": unique_ok,
            "default_ok": default_ok,
        }
    validation["scholarship_column_validation"] = {
        "all_ok": scholarship_columns_ok,
        "columns": scholarship_column_results,
        "expected_count": len(SCHOLARSHIP_ADDITIONS),
        "actual_count": len(actual_scholarship_columns),
    }
    if not scholarship_columns_ok:
        validation["valid"] = False

    # Additional indexes validation (scholarships, maintenance_runs)
    additional_index_results = {}
    additional_indexes_ok = True
    for stmt in ADDITIONAL_INDEXES:
        idx_name = stmt.split("IF NOT EXISTS ")[1].split(" ON ")[0]
        table_name = stmt.split(" ON ")[1].split(" (")[0]
        expected_cols = [c.strip() for c in stmt.split("(")[1].rstrip(")").split(",")]
        if not inspector.has_table(table_name):
            additional_index_results[idx_name] = {"status": "TABLE_MISSING_SKIPPED"}
            continue
        actual_indexes = {i["name"]: i for i in inspector.get_indexes(table_name)}
        actual = actual_indexes.get(idx_name)
        if actual is None:
            additional_index_results[idx_name] = {"status": "MISSING"}
            additional_indexes_ok = False
            continue
        actual_cols = actual.get("column_names", [])
        actual_unique = bool(actual.get("unique", False))
        expected_unique = "UNIQUE" in stmt.upper()
        actual_partial = _index_has_predicate(actual)
        if actual_cols != expected_cols or actual_unique != expected_unique or actual_partial:
            additional_index_results[idx_name] = {
                "status": "MISMATCH",
                "expected_columns": expected_cols,
                "actual_columns": actual_cols,
                "expected_unique": expected_unique,
                "actual_unique": actual_unique,
                "actual_partial": actual_partial,
            }
            additional_indexes_ok = False
        else:
            additional_index_results[idx_name] = {"status": "OK"}

    validation["additional_index_validation"] = {
        "expected_count": len(ADDITIONAL_INDEXES),
        "indexes": additional_index_results,
        "all_ok": additional_indexes_ok,
    }
    if not additional_indexes_ok:
        validation["valid"] = False

    # image_reviews validation: columns, PK, FK, indexes
    image_reviews_exists = inspector.has_table("image_reviews")
    image_reviews_ok = image_reviews_exists
    image_reviews_column_results = {}
    image_reviews_pk_ok = False
    image_reviews_fk_ok = False
    image_reviews_index_results = {}

    if image_reviews_exists:
        actual_ir_columns = {c["name"]: c for c in inspector.get_columns("image_reviews")}
        for col_name, col_type in IMAGE_REVIEWS_COLUMNS.items():
            actual = actual_ir_columns.get(col_name)
            if actual is None:
                image_reviews_column_results[col_name] = {"status": "MISSING"}
                image_reviews_ok = False
                continue
            expected_type_match = re.match(r"^([A-Za-z_]+(?:\([^)]*\))?)", col_type.strip())
            expected_type = expected_type_match.group(1) if expected_type_match else col_type.split()[0]
            expected_nullable = "NOT NULL" not in col_type.upper() and "PRIMARY KEY" not in col_type.upper()
            default_match = re.search(r"DEFAULT\s+(.+)", col_type, re.IGNORECASE)
            expected_default = default_match.group(1).strip() if default_match else None
            actual_type_obj = actual.get("type", "")
            actual_type = str(actual_type_obj)
            if dialect == "postgresql":
                type_ok = types_match(dialect, expected_type, actual_type_obj)
            elif expected_type == "TIMESTAMPTZ" and actual_type.upper() in {"DATETIME", "TIMESTAMP", "NUMERIC"}:
                type_ok = True
            else:
                type_ok = types_match(dialect, expected_type, actual_type_obj)
            nullable_ok = (expected_nullable == actual.get("nullable", True)) or ("PRIMARY KEY" in col_type.upper())
            default_ok = defaults_match(expected_default, actual.get("default"))
            col_ok = type_ok and nullable_ok and default_ok
            if not col_ok:
                image_reviews_ok = False
            image_reviews_column_results[col_name] = {
                "status": "OK" if col_ok else "MISMATCH",
                "type_ok": type_ok,
                "nullable_ok": nullable_ok,
                "default_ok": default_ok,
            }

        # PK
        pk = inspector.get_pk_constraint("image_reviews")
        pk_cols = pk.get("constrained_columns", []) if pk else []
        image_reviews_pk_ok = (pk_cols == ["id"])
        if not image_reviews_pk_ok:
            image_reviews_ok = False

        # FK
        actual_fks = inspector.get_foreign_keys("image_reviews")
        fk_ok = any(
            fk.get("constrained_columns") == ["scholarship_id"]
            and fk.get("referred_table") == "scholarships"
            and fk.get("referred_columns") == ["id"]
            and (fk.get("options", {}).get("ondelete") or "NO ACTION").upper().replace("_", " ") == "NO ACTION"
            for fk in actual_fks
        )
        image_reviews_fk_ok = fk_ok
        if not fk_ok:
            image_reviews_ok = False

        # Indexes
        actual_ir_indexes = {i["name"]: i for i in inspector.get_indexes("image_reviews")}
        for idx in IMAGE_REVIEWS_INDEXES:
            idx_name = idx.split(" ON ")[0]
            if idx_name not in actual_ir_indexes:
                image_reviews_ok = False
                image_reviews_index_results[idx_name] = {"status": "MISSING"}
                continue
            actual_idx = actual_ir_indexes[idx_name]
            expected_cols = idx.split("(")[1].rstrip(")").split(",")
            expected_cols = [c.strip() for c in expected_cols]
            actual_cols = actual_idx.get("column_names", [])
            actual_unique = bool(actual_idx.get("unique", False))
            actual_partial = _index_has_predicate(actual_idx)
            if actual_cols != expected_cols or actual_unique or actual_partial:
                image_reviews_ok = False
                image_reviews_index_results[idx_name] = {
                    "status": "MISMATCH",
                    "expected_columns": expected_cols,
                    "actual_columns": actual_cols,
                    "expected_unique": False,
                    "actual_unique": actual_unique,
                    "actual_partial": actual_partial,
                }
            else:
                image_reviews_index_results[idx_name] = {"status": "OK"}

    validation["image_reviews_validation"] = {
        "exists": image_reviews_exists,
        "columns": image_reviews_column_results,
        "primary_key_ok": image_reviews_pk_ok,
        "foreign_key_ok": image_reviews_fk_ok,
        "indexes": image_reviews_index_results,
        "all_ok": image_reviews_ok,
    }
    if not image_reviews_ok:
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

    # Production apply needs both halves of the database identity. Requiring
    # only the database name allowed the endpoint check in
    # verify_database_identity() to become optional.
    is_production = os.environ.get("SCHOLARZONE_ENVIRONMENT", "").lower() == "production"
    database_url = os.environ.get("SCHOLARZONE_DATABASE_URL", "").strip().lower()
    if args.apply and not os.environ.get("SCHOLARZONE_EXPECTED_DB_IDENTIFIER", "").strip():
        print("ERROR: --apply requires SCHOLARZONE_EXPECTED_DB_IDENTIFIER environment variable to be set", file=sys.stderr)
        print("This is a safety gate to prevent accidental migration to wrong database.", file=sys.stderr)
        sys.exit(1)
    # Production schema changes are supported only on PostgreSQL. Reject all
    # other URLs before opening a connection, including SQLite and unknown
    # dialects.
    if args.apply and is_production and not database_url.startswith(("postgresql://", "postgresql+")):
        print("ERROR: production --apply requires a PostgreSQL database URL", file=sys.stderr)
        sys.exit(1)
    if args.apply and is_production and not os.environ.get("SCHOLARZONE_EXPECTED_DB_HOST", "").strip():
        print("ERROR: production --apply requires SCHOLARZONE_EXPECTED_DB_HOST", file=sys.stderr)
        sys.exit(1)

    # All production modes require and verify database identity before proceeding.
    if is_production:
        for env_name in ("SCHOLARZONE_EXPECTED_DB_IDENTIFIER", "SCHOLARZONE_EXPECTED_DB_HOST"):
            if not os.environ.get(env_name, "").strip():
                print(f"ERROR: production mode requires {env_name} environment variable to be set", file=sys.stderr)
                print("This is a safety gate to prevent accidental migration to the wrong database.", file=sys.stderr)
                sys.exit(1)

    try:
        engine = get_production_engine()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.validate_only:
            # Verify identity before any schema inspection and retain the
            # non-secret verification result in the JSON report.
            db_info = verify_production_database(engine)
            validation = validate_schema(engine)
            report = {
                "mode": "validate-only",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "database": db_info,
                "validation": validation,
            }
        elif args.dry_run:
            # Verify identity before generating a migration plan.
            verify_production_database(engine)
            report = dry_run(engine)
        elif args.apply:
            # Verify identity before generating the plan and again immediately
            # before mutation (apply_migration re-verifies).
            verify_production_database(engine)
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
        if args.report:
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


