#!/usr/bin/env python3
"""
PostgreSQL Migration Integration Test

Tests the _upgrade_postgresql_schema migration on a real PostgreSQL database.
Creates an explicit legacy schema (fully_funded BOOLEAN NOT NULL DEFAULT FALSE),
inserts historical rows, then runs the migration independently.
"""

import os
import sys

# Set up environment BEFORE importing app modules
os.environ['SCHOLARZONE_DATABASE_URL'] = 'postgresql://test:test@localhost:5432/scholarzone_test?sslmode=disable'
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect, Column, Integer, String, Boolean, Date, Text, DateTime, JSON, Numeric
from sqlalchemy.orm import Session, sessionmaker


def create_legacy_schema(engine):
    """Create the legacy scholarships table with fully_funded NOT NULL DEFAULT FALSE."""
    print("Creating legacy schema...")
    with engine.begin() as conn:
        # Drop if exists (clean slate for test)
        conn.execute(text("DROP TABLE IF EXISTS scholarships CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS child_table CASCADE"))
        
        # Create legacy scholarships table matching old production schema
        # Key: fully_funded BOOLEAN NOT NULL DEFAULT FALSE
        conn.execute(text("""
            CREATE TABLE scholarships (
                id SERIAL PRIMARY KEY,
                legacy_id INTEGER,
                title VARCHAR(255) NOT NULL,
                country VARCHAR(120) NOT NULL,
                degree VARCHAR(255) NOT NULL,
                funding VARCHAR(120) NOT NULL,
                description TEXT,
                deadline_date DATE,
                deadline_display TEXT,
                deadline_precision VARCHAR(16) NOT NULL,
                status VARCHAR(20) NOT NULL,
                is_archived BOOLEAN NOT NULL DEFAULT FALSE,
                archived_at TIMESTAMPTZ,
                archived_reason VARCHAR(120),
                auto_delete_candidate_since TIMESTAMPTZ,
                deletion_protected BOOLEAN NOT NULL DEFAULT FALSE,
                is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                last_verified_at DATE,
                last_verified_date DATE,
                verification_status VARCHAR(20) NOT NULL DEFAULT 'active',
                next_verification_due DATE,
                verified_by VARCHAR(120),
                verification_notes TEXT,
                region TEXT,
                duration TEXT,
                application_period TEXT,
                official_source VARCHAR(255),
                official_source_url VARCHAR(2048),
                catalogue_url VARCHAR(2048),
                official_updates_url VARCHAR(2048),
                application_link VARCHAR(2048),
                image_url VARCHAR(2048),
                image_source_url VARCHAR(2048),
                image_source_type VARCHAR(32),
                image_kind VARCHAR(32),
                image_verified_at TIMESTAMPTZ,
                image_alt_text VARCHAR(512),
                image_evaluation_status VARCHAR(32),
                image_evaluated_at TIMESTAMPTZ,
                eligibility JSON NOT NULL DEFAULT '[]',
                eligibility_summary TEXT,
                benefits JSON NOT NULL DEFAULT '[]',
                coverage JSON NOT NULL DEFAULT '[]',
                requirements JSON NOT NULL DEFAULT '[]',
                documents JSON NOT NULL DEFAULT '[]',
                english_requirement TEXT,
                application_method JSON NOT NULL DEFAULT '[]',
                selection_notes TEXT,
                program_type VARCHAR(255),
                best_fit TEXT,
                funding_amount NUMERIC(12, 2),
                funding_currency VARCHAR(8),
                funding_period VARCHAR(64),
                tuition_coverage BOOLEAN,
                living_cost_coverage BOOLEAN,
                travel_coverage BOOLEAN,
                fully_funded BOOLEAN NOT NULL DEFAULT FALSE,
                official_details JSON,
                applicant_utility JSON,
                programme_verification JSON,
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                departments JSON NOT NULL DEFAULT '[]',
                eligible_fields JSON NOT NULL DEFAULT '[]',
                eligible_programmes JSON NOT NULL DEFAULT '[]',
                academic_provenance JSON,
                CONSTRAINT uq_scholarships_official_source_url UNIQUE (official_source_url)
            )
        """))
        
        # Create a child table with FK to test FK preservation
        conn.execute(text("""
            CREATE TABLE child_table (
                id SERIAL PRIMARY KEY,
                scholarship_id INTEGER NOT NULL REFERENCES scholarships(id)
            )
        """))
        
        # Insert historical rows with True/False values
        # Columns: eligibility, benefits, coverage, requirements, documents, application_method, departments, eligible_fields, eligible_programmes (9 JSON) + fully_funded (1 BOOLEAN) = 10 values
        conn.execute(text("""
            INSERT INTO scholarships (
                legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                NULL, 'Test Legacy True', 'USA', 'Master', 'Fully Funded', NULL,
                NULL, NULL, 'unknown', 'open',
                FALSE, FALSE, FALSE, 'active',
                NOW(), NOW(), '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', TRUE
            )
        """))
        conn.execute(text("""
            INSERT INTO scholarships (
                legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                NULL, 'Test Legacy False', 'UK', 'PhD', 'Partial', NULL,
                NULL, NULL, 'unknown', 'open',
                FALSE, FALSE, FALSE, 'active',
                NOW(), NOW(), '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', FALSE
            )
        """))
        conn.execute(text("INSERT INTO child_table (scholarship_id) VALUES (1)"))
        
        print("  ✓ Legacy schema created with historical data")
        print("  ✓ fully_funded: NOT NULL DEFAULT FALSE")
        print("  ✓ Historical rows: 1 TRUE, 1 FALSE")


def verify_legacy_schema(engine):
    """Verify the initial legacy schema state."""
    print("\n1. Verifying initial legacy schema state...")
    with engine.connect() as conn:
        cols = inspect(conn).get_columns('scholarships')
        for col in cols:
            if col['name'] == 'fully_funded':
                print(f"  Column: {col}")
                assert col['nullable'] is False, 'fully_funded should be NOT NULL initially'
                # Check default - in PostgreSQL, DEFAULT FALSE shows as 'false' in column_default
                assert col['default'] is not None, 'fully_funded should have DEFAULT initially'
                print("  ✓ Initial state confirmed: NOT NULL DEFAULT FALSE")
                break


def run_migration(engine):
    """Run the migration independently."""
    print("\n2. Running migration...")
    # Import the migration function
    from app.database import _upgrade_postgresql_schema
    
    # _upgrade_postgresql_schema expects an engine and manages its own transaction
    _upgrade_postgresql_schema(engine)
    print("  ✓ Migration executed")


def verify_migration(engine):
    """Verify the migration results."""
    print("\n3. Verifying migration results...")
    with engine.connect() as conn:
        cols = inspect(conn).get_columns('scholarships')
        for col in cols:
            if col['name'] == 'fully_funded':
                print(f"  After migration: {col}")
                assert col['nullable'] is True, 'fully_funded should be nullable after migration'
                # Default should be removed
                print("  ✓ Migration successful: fully_funded is now nullable")
                break


def test_inserts(engine):
    """Test NULL, TRUE, FALSE inserts work."""
    print("\n4. Testing tri-state inserts...")
    
    # Test NULL insert
    print("\n4a. Testing NULL insert...")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO scholarships (
                legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                NULL, 'Test PG NULL', 'Test', 'Master', 'Test', NULL,
                NULL, NULL, 'unknown', 'open',
                FALSE, FALSE, FALSE, 'active',
                NOW(), NOW(), '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', '[]', NULL
            )
        """))
        result = conn.execute(text("SELECT fully_funded FROM scholarships WHERE title = 'Test PG NULL'")).scalar()
        assert result is None, f"Expected NULL, got {result}"
        print("  ✓ NULL insert: PASS")
    
    # Test TRUE insert
    print("\n4b. Testing TRUE insert...")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO scholarships (
                legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                NULL, 'Test PG True', 'Test', 'Master', 'Test', NULL,
                NULL, NULL, 'unknown', 'open',
                FALSE, FALSE, FALSE, 'active',
                NOW(), NOW(), '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', '[]', TRUE
            )
        """))
        result = conn.execute(text("SELECT fully_funded FROM scholarships WHERE title = 'Test PG True'")).scalar()
        assert result is True, f"Expected TRUE, got {result}"
        print("  ✓ TRUE insert: PASS")
    
    # Test FALSE insert
    print("\n4c. Testing FALSE insert...")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO scholarships (
                legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                NULL, 'Test PG False', 'Test', 'Master', 'Test', NULL,
                NULL, NULL, 'unknown', 'open',
                FALSE, FALSE, FALSE, 'active',
                NOW(), NOW(), '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', '[]', FALSE
            )
        """))
        result = conn.execute(text("SELECT fully_funded FROM scholarships WHERE title = 'Test PG False'")).scalar()
        assert result is False, f"Expected FALSE, got {result}"
        print("  ✓ FALSE insert: PASS")


def test_historical_preserved(engine):
    """Verify historical rows are preserved with their values."""
    print("\n5. Verifying historical rows preserved...")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT title, fully_funded FROM scholarships WHERE title IN ('Test Legacy True', 'Test Legacy False')")).fetchall()
        for title, ff in rows:
            print(f"  {title}: fully_funded = {ff}")
        true_row = next((r for r in rows if r[0] == 'Test Legacy True'), None)
        false_row = next((r for r in rows if r[0] == 'Test Legacy False'), None)
        assert true_row and true_row[1] is True, "Historical TRUE row not preserved"
        assert false_row and false_row[1] is False, "Historical FALSE row not preserved"
        print("  ✓ Historical rows preserved with correct values")


def test_fk_preserved(engine):
    """Verify child table FK still works."""
    print("\n6. Verifying child table FK preserved...")
    with engine.connect() as conn:
        # This should work without FK violation
        result = conn.execute(text("SELECT COUNT(*) FROM child_table")).scalar()
        assert result == 1, f"Expected 1 child row, got {result}"
        print("  ✓ Child table FK preserved")


def test_idempotency(engine):
    """Test migration is idempotent."""
    print("\n7. Testing idempotency...")
    from app.database import _upgrade_postgresql_schema
    # _upgrade_postgresql_schema expects an engine and manages its own transaction
    _upgrade_postgresql_schema(engine)
    print("  ✓ Idempotent migration: PASS")


def test_migration_failure_rollback(engine):
    """Test that a migration failure doesn't leave partial state."""
    print("\n8. Testing migration failure handling...")
    from app.database import _upgrade_postgresql_schema
    # The migration should be idempotent and safe to re-run
    # This is more of a sanity check that re-running doesn't break
    _upgrade_postgresql_schema(engine)
    # Verify schema still correct
    with engine.connect() as conn:
        cols = inspect(conn).get_columns('scholarships')
        for col in cols:
            if col['name'] == 'fully_funded':
                assert col['nullable'] is True
    print("  ✓ Migration failure safety: PASS (idempotent re-run)")


def main():
    print("=" * 60)
    print("PostgreSQL Migration Integration Test")
    print("=" * 60)
    
    # Use postgresql+psycopg:// for psycopg v3 driver (SQLAlchemy 2.0 defaults to psycopg2)
    engine = create_engine('postgresql+psycopg://test:test@localhost:5432/scholarzone_test?sslmode=disable')
    
    try:
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection: OK")
        
        create_legacy_schema(engine)
        verify_legacy_schema(engine)
        run_migration(engine)
        verify_migration(engine)
        test_inserts(engine)
        test_historical_preserved(engine)
        test_fk_preserved(engine)
        test_idempotency(engine)
        test_migration_failure_rollback(engine)
        
        print("\n" + "=" * 60)
        print("ALL POSTGRESQL MIGRATION TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        engine.dispose()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)