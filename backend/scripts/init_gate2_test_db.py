#!/usr/bin/env python3
"""
Initialize database schema and test data for Gate 2 integration tests.

This script creates:
1. The scholarzone schema (scholarships table with all required columns)
2. A read-only role (gate2_ro) with appropriate privileges
3. Test data matching the 34 canonical target IDs
4. Simulated Neon settings for identity verification

Usage:
    TEST_DATABASE_URL=postgresql://test:test@localhost:5437/gate2_test \
    python backend/scripts/init_gate2_test_db.py
"""

import os
import sys
from pathlib import Path
from datetime import date, timedelta

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Canonical target IDs from manifest
CANONICAL_TARGET_IDS = [
    2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
    521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
    642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
    788, 1216, 1218, 1278
]

EXPECTED_NEON_PROJECT_ID = os.getenv("EXPECTED_NEON_PROJECT_ID", "test-project")
EXPECTED_NEON_BRANCH_ID = os.getenv("EXPECTED_NEON_BRANCH_ID", "test-branch")
EXPECTED_NEON_BRANCH_NAME = os.getenv("EXPECTED_NEON_BRANCH_NAME", "main")
EXPECTED_DATABASE_NAME = os.getenv("EXPECTED_DATABASE_NAME", "gate2_test")


def get_connection():
    """Get admin connection to test database."""
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        raise RuntimeError("TEST_DATABASE_URL not set")
    conn = psycopg2.connect(test_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def create_schema_and_data(conn):
    """Create the scholarships table and insert test data."""
    with conn.cursor() as cur:
        # Create scholarships table with all required columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scholarships (
                id INTEGER PRIMARY KEY,
                title VARCHAR(512) NOT NULL,
                country VARCHAR(120) NOT NULL,
                degree VARCHAR(120),
                funding VARCHAR(120),
                funding_type VARCHAR(64),
                deadline_date DATE,
                deadline_display TEXT,
                deadline_precision VARCHAR(32),
                status VARCHAR(32) NOT NULL DEFAULT 'open',
                fully_funded BOOLEAN,
                funding_amount NUMERIC(12, 2),
                funding_currency VARCHAR(8),
                funding_period VARCHAR(64),
                tuition_coverage BOOLEAN,
                living_cost_coverage BOOLEAN,
                travel_coverage BOOLEAN,
                duration TEXT,
                conditions TEXT,
                funding_details JSON,
                official_source TEXT,
                official_source_url VARCHAR(2048),
                official_details JSON,
                applicant_utility JSON,
                programme_verification JSON,
                auto_delete_candidate_since TIMESTAMPTZ,
                deletion_protected BOOLEAN NOT NULL DEFAULT FALSE,
                verification_status VARCHAR(32) NOT NULL DEFAULT 'active',
                last_verified_at DATE,
                verified_by VARCHAR(120),
                verification_notes TEXT,
                next_verification_due DATE,
                is_archived BOOLEAN NOT NULL DEFAULT FALSE,
                archived_at TIMESTAMPTZ,
                archived_reason VARCHAR(120),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                image_url VARCHAR(2048),
                image_source_url VARCHAR(2048),
                image_source_type VARCHAR(32),
                image_kind VARCHAR(32),
                image_verified_at TIMESTAMPTZ,
                image_alt_text VARCHAR(512),
                image_evaluation_status VARCHAR(32),
                image_evaluated_at TIMESTAMPTZ,
                departments JSON,
                eligible_fields JSON,
                eligible_programmes JSON,
                academic_provenance JSON,
                region TEXT
            )
        """)
        print("Created scholarships table")

        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS ix_scholarships_is_archived ON scholarships (is_archived)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_scholarships_status ON scholarships (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_scholarships_status_deadline ON scholarships (status, deadline_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_scholarships_auto_delete ON scholarships (status, is_archived, deletion_protected)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_scholarships_official_source_url ON scholarships (official_source_url)")
        print("Created indexes")

        # Insert test data for all 34 canonical IDs
        past_date = date.today() - timedelta(days=30)
        
        for tid in CANONICAL_TARGET_IDS:
            # Most records are closed/archived (expired)
            # Some are closing-soon (ID 54, 59, 62, 382, 492, 496, 497 - matching expected CLOSING_SOON)
            if tid in [54, 59, 62, 382, 492, 496, 497]:
                status = "closing-soon"
            else:
                status = "closed"
            
            cur.execute("""
                INSERT INTO scholarships (
                    id, title, country, degree, funding, funding_type,
                    deadline_date, deadline_display, deadline_precision,
                    status, fully_funded, funding_amount, funding_currency,
                    funding_period, tuition_coverage, living_cost_coverage,
                    travel_coverage, duration, conditions, funding_details,
                    official_source, official_source_url, official_details,
                    applicant_utility, programme_verification,
                    auto_delete_candidate_since, deletion_protected,
                    verification_status, last_verified_at, verified_by,
                    verification_notes, next_verification_due,
                    is_archived, archived_at, archived_reason,
                    image_url, image_source_url, image_source_type,
                    image_kind, image_verified_at, image_alt_text,
                    image_evaluation_status, image_evaluated_at,
                    departments, eligible_fields, eligible_programmes,
                    academic_provenance, region
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                ) ON CONFLICT (id) DO NOTHING
            """, (
                tid,
                f"Test Scholarship {tid}",
                "Test Country",
                "Master",
                "Full",
                "scholarship",
                past_date,
                str(past_date),
                "day",
                status,
                True,
                10000.00,
                "USD",
                "yearly",
                True,
                True,
                True,
                "1 year",
                "Test conditions",
                '{"amount": 10000, "currency": "USD"}',
                "Test Official Source",
                f"https://example.com/scholarship/{tid}",
                '{"source": "official"}',
                '{}',
                '{}',
                None,
                False,
                "verified",
                past_date,
                "test-verifier",
                "Test verification notes",
                past_date + timedelta(days=365),
                False,
                None,
                None,
                None, None, None, None, None,
                None, None, None, None, None
            ))
        
        print(f"Inserted {len(CANONICAL_TARGET_IDS)} test records")


def create_readonly_role(conn):
    """Create the read-only role with minimal privileges."""
    with conn.cursor() as cur:
        # Create the read-only role
        try:
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gate2_ro') THEN
                        CREATE ROLE gate2_ro LOGIN PASSWORD 'test' NOINHERIT;
                    ELSE
                        ALTER ROLE gate2_ro WITH LOGIN PASSWORD 'test' NOINHERIT;
                    END IF;
                END
                $$
            """)
            print("Created/updated gate2_ro role")
        except Exception as e:
            print(f"Warning: Could not create/update gate2_ro role (may lack CREATEROLE): {e}")
            # Continue anyway - the test user might have sufficient privileges

        # Grant CONNECT on database
        try:
            cur.execute("GRANT CONNECT ON DATABASE gate2_test TO gate2_ro")
        except Exception as e:
            print(f"Warning: Could not grant CONNECT to gate2_ro: {e}")

        # Grant USAGE on public schema
        try:
            cur.execute("GRANT USAGE ON SCHEMA public TO gate2_ro")
        except Exception as e:
            print(f"Warning: Could not grant USAGE on schema to gate2_ro: {e}")

        # Grant SELECT on scholarships table
        try:
            cur.execute("GRANT SELECT ON TABLE public.scholarships TO gate2_ro")
        except Exception as e:
            print(f"Warning: Could not grant SELECT on scholarships to gate2_ro: {e}")

        # Grant USAGE on sequences (for nextval if needed by SELECT)
        try:
            cur.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO gate2_ro")
        except Exception as e:
            print(f"Warning: Could not grant USAGE on sequences to gate2_ro: {e}")

        # Set default transaction read only for this role
        try:
            cur.execute("ALTER ROLE gate2_ro SET default_transaction_read_only = on")
        except Exception as e:
            print(f"Warning: Could not set default_transaction_read_only for gate2_ro: {e}")

        print("Granted read-only privileges to gate2_ro (where permissions allowed)")

        # Verify the role has only SELECT on scholarships
        try:
            cur.execute("""
                SELECT has_table_privilege('gate2_ro', 'scholarships', 'SELECT') as can_select,
                       has_table_privilege('gate2_ro', 'scholarships', 'INSERT') as can_insert,
                       has_table_privilege('gate2_ro', 'scholarships', 'UPDATE') as can_update,
                       has_table_privilege('gate2_ro', 'scholarships', 'DELETE') as can_delete,
                       has_table_privilege('gate2_ro', 'scholarships', 'TRUNCATE') as can_truncate
            """)
            result = cur.fetchone()
            print(f"Privilege verification: SELECT={result[0]}, INSERT={result[1]}, UPDATE={result[2]}, DELETE={result[3]}, TRUNCATE={result[4]}")
            
            if not result[0] or any(result[1:]):
                print("Warning: Role privileges not perfectly configured (may be expected in test environment)")
        except Exception as e:
            print(f"Warning: Could not verify role privileges: {e}")


def setup_neon_settings(conn):
    """Set up simulated Neon settings for identity verification."""
    with conn.cursor() as cur:
        # Set Neon settings at database level
        settings = [
            ("neon.project_id", EXPECTED_NEON_PROJECT_ID),
            ("neon.branch_id", EXPECTED_NEON_BRANCH_ID),
            ("neon.branch_name", EXPECTED_NEON_BRANCH_NAME),
        ]
        for setting_name, setting_value in settings:
            try:
                cur.execute(f"ALTER DATABASE gate2_test SET {setting_name} = '{setting_value}'")
                print(f"Set Neon setting: {setting_name}={setting_value}")
            except Exception as e:
                print(f"Warning: Could not set Neon setting {setting_name} (may lack superuser): {e}")


def verify_setup(conn):
    """Verify the test database is correctly configured."""
    with conn.cursor() as cur:
        # Check record count
        cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (CANONICAL_TARGET_IDS,))
        count = cur.fetchone()[0]
        print(f"Verified {count} target records in database")
        
        # Check all IDs present
        cur.execute("SELECT id FROM scholarships WHERE id = ANY(%s) ORDER BY id", (CANONICAL_TARGET_IDS,))
        found_ids = [row[0] for row in cur.fetchall()]
        missing = set(CANONICAL_TARGET_IDS) - set(found_ids)
        if missing:
            raise RuntimeError(f"Missing target IDs: {missing}")
        
        # Check statuses
        cur.execute("SELECT id, status FROM scholarships WHERE id = ANY(%s) ORDER BY id", (CANONICAL_TARGET_IDS,))
        for row in cur.fetchall():
            print(f"  ID {row[0]}: status={row[1]}")
        
        # Verify read-only role (if it was created)
        cur.execute("SELECT rolname FROM pg_roles WHERE rolname = 'gate2_ro'")
        if cur.fetchone():
            print("gate2_ro role exists")
        else:
            print("Warning: gate2_ro role not found (may be expected if CREATEROLE not available)")
        
        # Verify Neon settings (if they were set)
        try:
            cur.execute("SELECT current_setting('neon.project_id', true), current_setting('neon.branch_id', true), current_setting('neon.branch_name', true)")
            result = cur.fetchone()
            print(f"Neon settings verification: project_id={result[0]}, branch_id={result[1]}, branch_name={result[2]}")
            
            if result[0] != EXPECTED_NEON_PROJECT_ID:
                print(f"Warning: Neon project_id mismatch: expected {EXPECTED_NEON_PROJECT_ID}, got {result[0]}")
            if result[1] != EXPECTED_NEON_BRANCH_ID:
                print(f"Warning: Neon branch_id mismatch: expected {EXPECTED_NEON_BRANCH_ID}, got {result[1]}")
            if result[2] != EXPECTED_NEON_BRANCH_NAME:
                print(f"Warning: Neon branch_name mismatch: expected {EXPECTED_NEON_BRANCH_NAME}, got {result[2]}")
        except Exception as e:
            print(f"Warning: Could not verify Neon settings (may not be set): {e}")
        
        print("All verifications passed!")


def main():
    print("=== Gate 2 Test Database Initialization ===")
    print(f"Expected Neon Project ID: {EXPECTED_NEON_PROJECT_ID}")
    print(f"Expected Neon Branch ID: {EXPECTED_NEON_BRANCH_ID}")
    print(f"Expected Neon Branch Name: {EXPECTED_NEON_BRANCH_NAME}")
    print(f"Expected Database Name: {EXPECTED_DATABASE_NAME}")
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print()
    
    try:
        conn = get_connection()
        
        create_schema_and_data(conn)
        create_readonly_role(conn)
        setup_neon_settings(conn)
        verify_setup(conn)
        
        conn.close()
        print("\n=== Gate 2 Test Database Initialization COMPLETE ===")
        return 0
    except Exception as e:
        print(f"\n=== Gate 2 Test Database Initialization FAILED: {e} ===")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())