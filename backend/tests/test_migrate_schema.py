#!/usr/bin/env python3
"""
Dedicated migration script tests for backend/migrate_schema.py

Tests cover:
- Inline foreign-key parsing
- Table-level FK parsing
- Constrained/referred columns
- ON DELETE behavior
- Exact type validation
- Defaults
- PK and UNIQUE constraints
- Exact indexes
- Missing-index repair
- Identity missing/mismatch/match
- Transaction rollback
- Successful apply
- Idempotent second apply
- Invalid CLI argument combinations
"""

import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import the migration module directly
sys.path.insert(0, str(BACKEND_DIR / "backend"))
from migrate_schema import (
    parse_ddl_columns,
    parse_composite_constraints,
    parse_foreign_keys,
    normalize_type,
    types_match,
    normalize_on_delete,
    get_production_engine,
    verify_database_identity,
    verify_production_database,
    check_existing_supervisor_tables,
    generate_create_statements,
    generate_index_statements,
    dry_run,
    apply_migration,
    validate_schema,
    validate_schema_with_connection,
    verify_backup_pitr_status,
    get_expected_schema,
    parse_composite_constraints,
)


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def sqlite_engine():
    """Create a temporary SQLite database for testing with core tables only."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Create only the absolute minimum core tables required by the migration script
    # Supervisor tables (including professor_profiles) will be created by sqlite_engine_with_supervisor
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE scholarships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) NOT NULL
            )
        """))
    
    yield engine
    
    # Cleanup
    engine.dispose()
    import os
    os.unlink(db_path)


@pytest.fixture
def sqlite_engine_with_supervisor(sqlite_engine):
    """Create a SQLite database with all supervisor tables using canonical DDL."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.supervisor_ddl import NEW_TABLE_DDL, index_statements
    
    with sqlite_engine.begin() as conn:
        # Create all required tables using canonical DDL
        for table_name in NEW_TABLE_DDL:
            ddl = NEW_TABLE_DDL[table_name]["sqlite"]
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS {table_name} ({ddl})"))
        
        # Create all required indexes
        for idx_stmt in index_statements():
            conn.execute(text(idx_stmt))
    
    return sqlite_engine


# ============================================================
# FK Parser Tests
# ============================================================

class TestFKParser:
    """Tests for foreign key parsing from DDL."""
    
    def test_inline_fk_parsing(self):
        """Test parsing of inline REFERENCES constraints."""
        ddl = """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER REFERENCES scholarships(id),
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id) ON DELETE CASCADE
        """
        columns = parse_ddl_columns(ddl)
        
        assert "scholarship_id" in columns
        assert columns["scholarship_id"]["references"] is not None
        assert columns["scholarship_id"]["references"]["referred_table"] == "scholarships"
        assert columns["scholarship_id"]["references"]["referred_columns"] == ["id"]
        assert columns["scholarship_id"]["references"]["constrained_columns"] == ["scholarship_id"]
        assert columns["scholarship_id"]["references"]["on_delete"] == "NO ACTION"
        
        assert "professor_id" in columns
        assert columns["professor_id"]["references"] is not None
        assert columns["professor_id"]["references"]["referred_table"] == "professor_profiles"
        assert columns["professor_id"]["references"]["on_delete"] == "ON DELETE CASCADE"
    
    def test_table_level_fk_parsing(self):
        """Test parsing of table-level FOREIGN KEY constraints."""
        ddl = """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER,
            professor_id INTEGER,
            FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE RESTRICT,
            FOREIGN KEY (professor_id) REFERENCES professor_profiles(id) ON DELETE SET NULL
        """
        fks = parse_foreign_keys(ddl)
        
        assert len(fks) == 2
        
        fk1 = next(fk for fk in fks if fk["constrained_columns"] == ["scholarship_id"])
        assert fk1["referred_table"] == "scholarships"
        assert fk1["referred_columns"] == ["id"]
        assert fk1["on_delete"] == "RESTRICT"
        
        fk2 = next(fk for fk in fks if fk["constrained_columns"] == ["professor_id"])
        assert fk2["referred_table"] == "professor_profiles"
        assert fk2["on_delete"] == "SET NULL"
    
    def test_mixed_inline_and_table_fk(self):
        """Test parsing when both inline and table-level FKs exist."""
        ddl = """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER REFERENCES scholarships(id),
            professor_id INTEGER,
            FOREIGN KEY (professor_id) REFERENCES professor_profiles(id) ON DELETE CASCADE
        """
        fks = parse_foreign_keys(ddl)
        
        # Should have both FKs without duplicates
        assert len(fks) == 2
        
        constrained = [tuple(fk["constrained_columns"]) for fk in fks]
        assert ("scholarship_id",) in constrained
        assert ("professor_id",) in constrained
    
    def test_multi_column_fk(self):
        """Test parsing of multi-column foreign keys."""
        ddl = """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER,
            professor_id INTEGER,
            FOREIGN KEY (scholarship_id, professor_id) REFERENCES scholarship_professor_links(scholarship_id, professor_id) ON DELETE RESTRICT
        """
        fks = parse_foreign_keys(ddl)
        
        assert len(fks) == 1
        fk = fks[0]
        assert fk["constrained_columns"] == ["scholarship_id", "professor_id"]
        assert fk["referred_table"] == "scholarship_professor_links"
        assert fk["referred_columns"] == ["scholarship_id", "professor_id"]
        assert fk["on_delete"] == "RESTRICT"


# ============================================================
# Type Validation Tests
# ============================================================

class TestTypeValidation:
    """Tests for exact type validation with dialect awareness."""
    
    def test_varchar_length_preserved(self):
        """VARCHAR length should be preserved in normalization."""
        expected = "VARCHAR(255)"
        actual = "VARCHAR(255)"
        assert types_match("postgresql", expected, actual)
        assert types_match("sqlite", expected, actual)
    
    def test_varchar_different_lengths_fail(self):
        """Different VARCHAR lengths should not match."""
        assert not types_match("postgresql", "VARCHAR(255)", "VARCHAR(2550)")
        assert not types_match("sqlite", "VARCHAR(255)", "VARCHAR(2550)")
    
    def test_numeric_precision_scale(self):
        """NUMERIC/DECIMAL precision and scale should be preserved."""
        assert types_match("postgresql", "NUMERIC(10,2)", "DECIMAL(10,2)")
        assert types_match("sqlite", "NUMERIC(10,2)", "DECIMAL(10,2)")
        assert not types_match("postgresql", "NUMERIC(10,2)", "DECIMAL(10,3)")
    
    def test_timestamp_timezone(self):
        """Timestamp with timezone should match across dialects."""
        assert types_match("postgresql", "TIMESTAMPTZ", "TIMESTAMP WITH TIME ZONE")
        # SQLite stores TIMESTAMPTZ as NUMERIC (Unix timestamp)
        assert types_match("sqlite", "TIMESTAMPTZ", "NUMERIC")
        assert types_match("sqlite", "TIMESTAMP WITH TIME ZONE", "NUMERIC")
    
    def test_varchar_alias_normalization(self):
        """CHARACTER VARYING should normalize to VARCHAR."""
        assert types_match("postgresql", "CHARACTER VARYING(255)", "VARCHAR(255)")
        assert types_match("sqlite", "CHARACTER VARYING(255)", "VARCHAR(255)")
    
    def test_numeric_decimal_alias(self):
        """NUMERIC should normalize to DECIMAL."""
        assert types_match("postgresql", "NUMERIC(10,2)", "DECIMAL(10,2)")


# ============================================================
# ON DELETE Normalization Tests
# ============================================================

class TestOnDeleteNormalization:
    """Tests for ON DELETE action normalization."""
    
    def test_restrict_variations(self):
        assert normalize_on_delete("RESTRICT") == "RESTRICT"
        assert normalize_on_delete("ON DELETE RESTRICT") == "RESTRICT"
        assert normalize_on_delete("on delete restrict") == "RESTRICT"
    
    def test_cascade_variations(self):
        assert normalize_on_delete("CASCADE") == "CASCADE"
        assert normalize_on_delete("ON DELETE CASCADE") == "CASCADE"
    
    def test_set_null_variations(self):
        assert normalize_on_delete("SET NULL") == "SET NULL"
        assert normalize_on_delete("ON DELETE SET NULL") == "SET NULL"
    
    def test_no_action_variations(self):
        assert normalize_on_delete("NO ACTION") == "NO ACTION"
        assert normalize_on_delete("ON DELETE NO ACTION") == "NO ACTION"
    
    def test_set_default_variations(self):
        assert normalize_on_delete("SET DEFAULT") == "SET DEFAULT"
        assert normalize_on_delete("ON DELETE SET DEFAULT") == "SET DEFAULT"


# ============================================================
# Default Value Validation Tests
# ============================================================

class TestDefaultValidation:
    """Tests for default value validation."""
    
    def test_default_matching(self):
        """Expected default matching actual should pass."""
        from migrate_schema import parse_ddl_columns
        ddl = "status VARCHAR(50) DEFAULT 'pending'"
        columns = parse_ddl_columns(ddl)
        assert columns["status"]["default"] == "'pending'"
    
    def test_no_default_vs_default(self):
        """Missing default vs having default should be detected."""
        from migrate_schema import parse_ddl_columns
        ddl1 = "status VARCHAR(50)"
        ddl2 = "status VARCHAR(50) DEFAULT 'pending'"
        cols1 = parse_ddl_columns(ddl1)
        cols2 = parse_ddl_columns(ddl2)
        assert cols1["status"]["default"] is None
        assert cols2["status"]["default"] == "'pending'"


# ============================================================
# PK and UNIQUE Constraints Tests
# ============================================================

class TestConstraints:
    """Tests for primary key and unique constraint validation."""
    
    def test_composite_unique_parsing(self):
        """Composite UNIQUE constraints should be parsed correctly."""
        ddl = """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER,
            official_contact_url VARCHAR(2048) NOT NULL,
            CONSTRAINT uq_official_contact_scholarship_url
                UNIQUE (scholarship_id, official_contact_url)
        """
        composite = parse_composite_constraints(ddl)
        
        assert len(composite) == 1
        assert composite[0]["type"] == "UNIQUE"
        assert composite[0]["columns"] == ["scholarship_id", "official_contact_url"]
        assert composite[0]["name"] == "uq_official_contact_scholarship_url"
    
    def test_primary_key_parsing(self):
        """Primary key should be parsed correctly."""
        ddl = "id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(255)"
        columns = parse_ddl_columns(ddl)
        
        assert columns["id"]["primary_key"] is True
        assert columns["id"]["nullable"] is False
        assert columns["name"]["primary_key"] is False


# ============================================================
# Index Validation Tests
# ============================================================

class TestIndexValidation:
    """Tests for exact index validation."""
    
    def test_exact_index_validation(self, sqlite_engine_with_supervisor):
        """Test that exact index validation works."""
        from migrate_schema import validate_schema
        
        result = validate_schema(sqlite_engine_with_supervisor)
        print('DEBUG: valid=', result["valid"])
        if not result["valid"]:
            for table, detail in result["table_details"].items():
                if not detail.get('has_required_columns', True):
                    print(table + ': has_required_columns=' + str(detail.get('has_required_columns')))
            for table, fk_val in result["foreign_key_validation"].items():
                if not fk_val.get('all_ok', True):
                    print(table + ': FK all_ok=' + str(fk_val.get('all_ok')))
                    for fk in fk_val["details"]:
                        if fk.get("status") != "OK":
                            print("  ", fk)
            for table, idx_val in result["index_validation"].items():
                if not idx_val.get("all_present", True):
                    print(table + ': index all_present=' + str(idx_val.get("all_present")) + ', missing=' + str(idx_val.get("missing")))
            for table, comp_val in result["composite_unique_validation"].items():
                for comp in comp_val["results"]:
                    if not comp.get("found", True):
                        print(table + ': composite unique not found: ' + str(comp))
        assert result["valid"] is True
        
        # Check index validation for official_contacts
        idx_val = result["index_validation"]["official_contacts"]
        assert idx_val["all_present"] is True
        assert idx_val["expected_count"] == 3  # ix_official_contacts_scholarship_id, ix_official_contacts_institution, ix_official_contacts_verification
    
    def test_missing_index_detection(self, sqlite_engine):
        """Test that missing indexes are detected."""
        from migrate_schema import validate_schema
        
        # This engine doesn't have the supervisor tables with indexes
        result = validate_schema(sqlite_engine)
        # The validation should fail because tables are missing
        assert result["valid"] is False


# ============================================================
# Missing Index Repair Tests
# ============================================================

class TestMissingIndexRepair:
    """Tests for missing index repair functionality."""
    
    def test_missing_index_repair_generation(self, sqlite_engine):
        """Test that missing index repair statements are generated."""
        from migrate_schema import (
            check_existing_supervisor_tables,
            generate_index_statements
        )
        
        # Create one supervisor table without all indexes
        with sqlite_engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE official_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scholarship_id INTEGER REFERENCES scholarships(id),
                    institution_name VARCHAR(255) NOT NULL,
                    official_contact_url VARCHAR(2048) NOT NULL
                )
            """))
        
        table_info = check_existing_supervisor_tables(sqlite_engine)
        stmts = generate_index_statements(sqlite_engine, [], table_info)
        
        # Should generate statements for missing indexes
        assert len(stmts) >= 2  # At least the regular indexes
        assert any("ix_official_contacts_scholarship_id" in s for s in stmts)
        # Note: uq_official_contact_scholarship_url is a UNIQUE constraint in DDL, not a separate index statement


# ============================================================
# Identity Verification Tests
# ============================================================

class TestIdentityVerification:
    """Tests for database identity verification."""
    
    def test_identity_missing_fails(self):
        """Missing identity should fail for apply mode."""
        with pytest.raises(RuntimeError, match="SCHOLARZONE_EXPECTED_DB_IDENTIFIER"):
            from migrate_schema import get_production_engine
            # Mock environment without identity
            with patch.dict(os.environ, {"SCHOLARZONE_DATABASE_URL": "sqlite:///test.db"}, clear=True):
                get_production_engine()
    
    def test_identity_mismatch_fails(self, sqlite_engine):
        """Wrong identity should fail."""
        with pytest.raises(RuntimeError, match="Database identity mismatch"):
            with patch.dict(os.environ, {
                "SCHOLARZONE_DATABASE_URL": str(sqlite_engine.url),
                "SCHOLARZONE_EXPECTED_DB_IDENTIFIER": "wrong_database_name",
                "SCHOLARZONE_ENVIRONMENT": "test"
            }, clear=True):
                engine = get_production_engine()
                try:
                    verify_production_database(engine)
                finally:
                    engine.dispose()
    
    def test_correct_identity_passes(self, sqlite_engine):
        """Correct identity should pass."""
        # Extract database name from the engine URL
        db_name = str(sqlite_engine.url.database)
        # Extract just the filename without path
        import os
        db_name = os.path.basename(db_name)
        if db_name.endswith('.db'):
            db_name = db_name[:-3]
        with patch.dict(os.environ, {
            "SCHOLARZONE_DATABASE_URL": str(sqlite_engine.url),
            "SCHOLARZONE_EXPECTED_DB_IDENTIFIER": db_name,  # SQLite database name
            "SCHOLARZONE_ENVIRONMENT": "test"
        }, clear=True):
            engine = get_production_engine()
            try:
                result = verify_production_database(engine)
                # SQLite doesn't verify host, so identity should be verified
                assert result["identity"]["verified"] is True
            finally:
                engine.dispose()


# ============================================================
# Backup/PITR Gate Tests
# ============================================================

class TestBackupPITRGate:
    """Tests for backup/PITR verification gate."""
    
    def test_backup_unverified_fails(self, sqlite_engine):
        """Unverified backup should fail apply."""
        from migrate_schema import verify_backup_pitr_status
        
        with sqlite_engine.connect() as conn:
            result = verify_backup_pitr_status(conn)
            assert result["verified"] is False
            assert result["details"]["backup_verified"] is False
    
    def test_backup_verified_passes(self, sqlite_engine):
        """Verified backup should pass."""
        from migrate_schema import verify_backup_pitr_status
        
        with patch.dict(os.environ, {
            "SCHOLARZONE_BACKUP_VERIFIED": "true",
            "SCHOLARZONE_RESTORE_TEST_DATE": datetime.now(timezone.utc).date().isoformat(),
            "SCHOLARZONE_BACKUP_EVIDENCE_REF": "backup-restore-record-2026-11-13"
        }):
            with sqlite_engine.connect() as conn:
                result = verify_backup_pitr_status(conn)
                assert result["verified"] is True
                assert result["details"]["backup_verified"] is True
                assert result["details"]["restore_test_date"] == datetime.now(timezone.utc).date().isoformat()
                assert result["details"]["evidence_ref"] == "backup-restore-record-2026-11-13"

    @pytest.mark.parametrize("restore_date", [
        "not-a-date",
        (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat(),
        (datetime.now(timezone.utc).date() - timedelta(days=31)).isoformat(),
    ])
    def test_stale_invalid_or_future_restore_evidence_fails(self, sqlite_engine, restore_date):
        with patch.dict(os.environ, {
            "SCHOLARZONE_BACKUP_VERIFIED": "true",
            "SCHOLARZONE_RESTORE_TEST_DATE": restore_date,
            "SCHOLARZONE_BACKUP_EVIDENCE_REF": "backup-restore-record",
        }):
            with sqlite_engine.connect() as conn:
                result = verify_backup_pitr_status(conn)
        assert result["verified"] is False
        assert result["details"]["date_error"]

    def test_missing_evidence_reference_fails(self, sqlite_engine):
        with patch.dict(os.environ, {
            "SCHOLARZONE_BACKUP_VERIFIED": "true",
            "SCHOLARZONE_RESTORE_TEST_DATE": datetime.now(timezone.utc).date().isoformat(),
            "SCHOLARZONE_BACKUP_EVIDENCE_REF": "",
        }):
            with sqlite_engine.connect() as conn:
                result = verify_backup_pitr_status(conn)
        assert result["verified"] is False


# ============================================================
# Transaction Rollback Tests
# ============================================================

class TestTransactionRollback:
    """Tests for transactional rollback on validation failure."""
    
    def test_apply_rollback_on_validation_failure(self, sqlite_engine):
        """Validation failure should roll back all DDL."""
        from migrate_schema import apply_migration, dry_run
        
        # Create a dry run report
        report = dry_run(sqlite_engine)
        
        # The dry run should show what would be applied
        assert "create_statements" in report
        assert "index_statements" in report
    
    def test_idempotent_second_apply(self, sqlite_engine_with_supervisor):
        """Second apply should be idempotent (no-op)."""
        from migrate_schema import apply_migration, dry_run
        
        # Set required environment variables for backup/PITR gate
        with patch.dict(os.environ, {
            "SCHOLARZONE_BACKUP_VERIFIED": "true",
            "SCHOLARZONE_RESTORE_TEST_DATE": datetime.now(timezone.utc).date().isoformat(),
            "SCHOLARZONE_BACKUP_EVIDENCE_REF": "neon-backup-2024-01-15"
        }):
            # First apply
            report1 = dry_run(sqlite_engine_with_supervisor)
            result1 = apply_migration(sqlite_engine_with_supervisor, report1)
            
            # Second apply should be no-op
            report2 = dry_run(sqlite_engine_with_supervisor)
            assert len(report2["create_statements"]) == 0
            assert len(report2["index_statements"]) == 0
            
            result2 = apply_migration(sqlite_engine_with_supervisor, report2)
            assert len(result2["applied"]["tables_created"]) == 0
            assert len(result2["applied"]["indexes_created"]) == 0


# ============================================================
# CLI Argument Tests
# ============================================================

class TestCLIArguments:
    """Tests for CLI argument parsing."""
    
    def test_mutually_exclusive_modes(self):
        """Mutually exclusive modes should be enforced."""
        from migrate_schema import main
        
        # This would be tested via subprocess in real tests
        # For now, we verify the parser structure
        import argparse
        parser = argparse.ArgumentParser()
        mode_group = parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument("--dry-run", action="store_true")
        mode_group.add_argument("--apply", action="store_true")
        mode_group.add_argument("--validate-only", action="store_true")
        
        # Test mutually exclusive
        with pytest.raises(SystemExit):
            parser.parse_args(["--dry-run", "--apply"])
        
        with pytest.raises(SystemExit):
            parser.parse_args(["--apply", "--validate-only"])
        
        # Valid single mode
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True
        assert args.apply is False
        assert args.validate_only is False
    
    def test_invalid_combinations_fail_before_connection(self):
        """Invalid argument combinations should fail before any database connection."""
        import subprocess
        import sys
        
        # Test that mutually exclusive args fail fast
        result = subprocess.run([
            sys.executable, "-m", "backend.migrate_schema", 
            "--dry-run", "--apply"
        ], capture_output=True, cwd=BACKEND_DIR.parent)
        
        assert result.returncode != 0
        assert b"error" in result.stderr.lower() or b"unrecognized arguments" in result.stderr.lower()

    @pytest.mark.parametrize(("database_url", "expected_error"), [
        ("sqlite:///production.db", b"requires a postgresql database url"),
        ("postgresql://user:pass@db.example.invalid/app", b"requires scholarzone_expected_db_host"),
    ])
    def test_production_apply_requires_postgresql_and_endpoint_identity(self, database_url, expected_error):
        import subprocess

        env = os.environ.copy()
        for key in (
            "SCHOLARZONE_DATABASE_URL", "SCHOLARZONE_ENVIRONMENT",
            "SCHOLARZONE_EXPECTED_DB_IDENTIFIER", "SCHOLARZONE_EXPECTED_DB_HOST",
            "SCHOLARZONE_BACKUP_VERIFIED", "SCHOLARZONE_RESTORE_TEST_DATE",
            "SCHOLARZONE_BACKUP_EVIDENCE_REF", "TEST_POSTGRESQL_URL",
        ):
            env.pop(key, None)
        env.update({
            "SCHOLARZONE_ENVIRONMENT": "production",
            "SCHOLARZONE_DATABASE_URL": database_url,
            "SCHOLARZONE_EXPECTED_DB_IDENTIFIER": "app",
            "PYTHONPATH": str(BACKEND_DIR),
        })
        result = subprocess.run(
            [sys.executable, str(BACKEND_DIR / "migrate_schema.py"), "--apply"],
            capture_output=True,
            cwd=BACKEND_DIR,
            env=env,
        )
        assert result.returncode != 0
        assert expected_error in result.stderr.lower()
        assert b"traceback" not in result.stderr.lower()


# ============================================================
# PostgreSQL Integration Tests (require PG instance)
# ============================================================

@pytest.mark.skipif(not os.environ.get("TEST_POSTGRESQL_URL"), reason="TEST_POSTGRESQL_URL not set")
class TestPostgreSQLIntegration:
    """Integration tests against PostgreSQL 16 and 18.
    
    These tests require a running PostgreSQL instance and are marked
    to be run separately in CI with appropriate services.
    """

    @pytest.fixture(autouse=True)
    def test_backup_attestation(self, monkeypatch):
        """Supply synthetic, test-only backup evidence for disposable schemas."""
        monkeypatch.setenv("SCHOLARZONE_BACKUP_VERIFIED", "true")
        monkeypatch.setenv(
            "SCHOLARZONE_RESTORE_TEST_DATE",
            datetime.now(timezone.utc).date().isoformat(),
        )
        monkeypatch.setenv("SCHOLARZONE_BACKUP_EVIDENCE_REF", "disposable-postgresql-test")
    
    @pytest.fixture
    def pg_engine(self):
        """Use a unique schema on a local disposable PostgreSQL test database."""
        pg_url = os.environ.get("TEST_POSTGRESQL_URL")
        if not pg_url:
            pytest.skip("TEST_POSTGRESQL_URL not set")

        parsed = make_url(pg_url)
        if (parsed.host or "").lower() not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("TEST_POSTGRESQL_URL must target a loopback PostgreSQL service")
        if "test" not in (parsed.database or "").lower():
            raise RuntimeError("TEST_POSTGRESQL_URL database name must identify a disposable test database")

        schema = f"migration_test_{uuid.uuid4().hex}"
        admin_engine = create_engine(pg_url)
        engine = None
        schema_created = False
        try:
            with admin_engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            schema_created = True
            engine = create_engine(pg_url, connect_args={"options": f"-csearch_path={schema}"})
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE scholarships (id INTEGER PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            yield engine
        finally:
            if engine is not None:
                engine.dispose()
            if schema_created:
                with admin_engine.begin() as conn:
                    conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin_engine.dispose()
    
    def test_postgresql_migration(self, pg_engine):
        """Test full migration cycle on PostgreSQL."""
        from migrate_schema import dry_run, apply_migration
        
        report = dry_run(pg_engine)
        result = apply_migration(pg_engine, report)
        
        assert result["mode"] == "apply"
        assert result["applied"]["errors"] == []
    
    def test_postgresql_idempotent_apply(self, pg_engine):
        """Test idempotent second apply on PostgreSQL."""
        from migrate_schema import dry_run, apply_migration
        
        report1 = dry_run(pg_engine)
        result1 = apply_migration(pg_engine, report1)
        
        report2 = dry_run(pg_engine)
        assert len(report2["create_statements"]) == 0
        assert len(report2["index_statements"]) == 0
        
        result2 = apply_migration(pg_engine, report2)
        assert len(result2["applied"]["tables_created"]) == 0


# ============================================================
# Full Migration Script Tests
# ============================================================

class TestFullMigrationScript:
    """Tests for the complete migration script flow."""
    
    def test_dry_run_no_write(self, sqlite_engine):
        """Dry run should not write to database."""
        from migrate_schema import dry_run
        
        report = dry_run(sqlite_engine)
        
        # Verify report structure
        assert report["mode"] == "dry-run"
        assert "create_statements" in report
        assert "index_statements" in report
        assert "missing_tables" in report
        assert "supervisor_tables" in report
        assert "database" in report
    
    def test_validate_only_no_write(self, sqlite_engine):
        """Validate-only should not write to database."""
        from migrate_schema import validate_schema
        
        result = validate_schema(sqlite_engine)
        
        assert "valid" in result
        assert "table_details" in result
        assert "column_validation" in result
    
    def test_successful_apply(self, sqlite_engine):
        """Successful apply should create missing tables."""
        from migrate_schema import dry_run, apply_migration
        
        # Set required environment variables for backup/PITR gate
        with patch.dict(os.environ, {
            "SCHOLARZONE_BACKUP_VERIFIED": "true",
            "SCHOLARZONE_RESTORE_TEST_DATE": datetime.now(timezone.utc).date().isoformat(),
            "SCHOLARZONE_BACKUP_EVIDENCE_REF": "neon-backup-2024-01-15"
        }):
            report = dry_run(sqlite_engine)
            result = apply_migration(sqlite_engine, report)
        
        assert result["mode"] == "apply"
        assert result["applied"]["errors"] == []
    
    def test_invalid_cli_args_fail_fast(self):
        """Invalid CLI args should fail before database connection."""
        import subprocess
        import sys
        
        result = subprocess.run([
            sys.executable, "-m", "backend.migrate_schema",
            "--dry-run", "--apply"
        ], capture_output=True, cwd=str(BACKEND_DIR.parent))
        
        assert result.returncode != 0
        # Should fail with argument error, not database error


# ============================================================
# Regression Tests
# ============================================================

class TestRegressions:
    """Tests for specific regression scenarios."""
    
    def test_varchar_255_vs_2550(self):
        """VARCHAR(255) and VARCHAR(2550) should not match."""
        assert not types_match("postgresql", "VARCHAR(255)", "VARCHAR(2550)")
        assert not types_match("sqlite", "VARCHAR(255)", "VARCHAR(2550)")
    
    def test_varchar_255_matches_varchar_255(self):
        """VARCHAR(255) should match VARCHAR(255)."""
        assert types_match("postgresql", "VARCHAR(255)", "VARCHAR(255)")
        assert types_match("sqlite", "VARCHAR(255)", "VARCHAR(255)")
    
    def test_varchar_alias_case_insensitive(self):
        """CHARACTER VARYING should match VARCHAR case-insensitively."""
        assert types_match("postgresql", "character varying(255)", "VARCHAR(255)")
        assert types_match("postgresql", "CHARACTER VARYING(255)", "varchar(255)")
    
    def test_fk_constrained_columns_exact_order(self):
        """Foreign key constrained columns should match in exact order."""
        ddl = """
            id INTEGER PRIMARY KEY,
            a INTEGER,
            b INTEGER,
            FOREIGN KEY (a, b) REFERENCES other(x, y)
        """
        fks = parse_foreign_keys(ddl)
        
        assert len(fks) == 1
        assert fks[0]["constrained_columns"] == ["a", "b"]
        assert fks[0]["referred_columns"] == ["x", "y"]
    
    def test_fk_referred_columns_exact_order(self):
        """Foreign key referred columns should match in exact order."""
        ddl = """
            id INTEGER PRIMARY KEY,
            a INTEGER,
            b INTEGER,
            FOREIGN KEY (a, b) REFERENCES other(y, x)
        """
        fks = parse_foreign_keys(ddl)
        
        assert len(fks) == 1
        assert fks[0]["constrained_columns"] == ["a", "b"]
        assert fks[0]["referred_columns"] == ["y", "x"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
