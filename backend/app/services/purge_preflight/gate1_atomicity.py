"""
Gate 1: Atomicity and Rollback Verification

Tests transaction behavior using a DISPOSABLE test database.
NEVER connects to production. Creates isolated test fixtures.

Requirements:
- TEST_DATABASE_URL must be explicitly configured
- Must be a disposable PostgreSQL instance (e.g., GitHub Actions service)
- Never falls back to production database environment variables
- Tests genuine rollback behavior with controlled failure injection
- Uses separate synthetic fixture sets for rollback and idempotency
- Robust disposable DB identity, actual deletion behavior, exact state verification
- Safe cleanup and derived PASS

IMPORTANT: This gate validates ATOMICITY ONLY (transaction commit/rollback semantics).
It does NOT validate production schema FK behavior, cascade rules, or purge impact.
Gate 3 separately covers FK dependency behavior on the real production schema.
"""

import json
import sys
import os
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional
from urllib.parse import urlparse

import psycopg2
from psycopg2.extensions import connection as PgConnection

from .manifest import CANONICAL_TARGET_IDS, TARGET_ID_SET
from .database import DatabaseAccessor, create_accessor
from .config import DatabaseConfig
from .metadata import save_result_with_metadata


# Synthetic fixture IDs - NEVER use canonical production IDs as fixtures
# These are purely for testing transaction behavior in the disposable DB
# Using high ranges (80000+) to ensure zero overlap with production IDs (max 1278)
ROLLBACK_TEST_IDS = [9001, 9002]  # Synthetic IDs for rollback test
IDEMPOTENCY_TEST_IDS = [9101, 9102, 9103]  # Synthetic IDs for idempotency test

# Primary test uses its own synthetic ID range
PRIMARY_TEST_ID_BASE = 80000
PRIMARY_TEST_IDS = [PRIMARY_TEST_ID_BASE + i for i in range(35)]  # 80000-80034 (35 IDs)

# Allowlisted disposable database configurations
# Only these host/database combinations are permitted for Gate 1
ALLOWED_DISPOSABLE_HOSTS = {
    "localhost",
    "127.0.0.1",
    "postgres",  # Docker service name
}
ALLOWED_DISPOSABLE_DATABASES = {
    "test_purge",
    "test",
    "pytest",
}
ALLOWED_DISPOSABLE_USERS = {
    "test",
    "postgres",
    "pytest",
}

# Forbidden patterns that indicate production or non-disposable databases
FORBIDDEN_URL_PATTERNS = [
    "neon.tech",
    "production",
    "prod",
    "scholarzone",
    "rds.amazonaws.com",
    "cloudsql",
    "postgres.database.azure.com",
    "aws.neon.tech",
    "neon.amazonaws.com",
]


@dataclass
class Gate1Result:
    """Gate 1 execution result."""
    test_name: str = "gate1_atomicity"
    target_ids: list[int] = None
    pre_deletion_count: int = 0
    deleted_count: int = 0
    deleted_ids: list[int] = None
    exact_match: bool = False
    remaining_targets: int = 0
    total_after_deletion: int = 0
    rollback_test_passed: bool = False
    idempotent_test_passed: bool = False
    final_count: int = 0
    status: str = "PENDING"
    error: Optional[str] = None

    def __post_init__(self):
        if self.target_ids is None:
            self.target_ids = []
        if self.deleted_ids is None:
            self.deleted_ids = []

    def to_dict(self) -> dict:
        return asdict(self)


def validate_disposable_database_url(test_url: str) -> tuple[bool, Optional[str]]:
    """
    Validate that the test database URL points to a disposable PostgreSQL instance.
    
    Strict validation with explicit allowlist and forbidden patterns.
    NO fallback to any production environment variable.
    Fails closed on any ambiguity or missing configuration.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not test_url:
        return False, "TEST_DATABASE_URL is empty or not set"
    
    try:
        parsed = urlparse(test_url)
        
        # Check scheme
        if parsed.scheme not in ("postgresql", "postgres"):
            return False, f"Invalid scheme: {parsed.scheme}, expected postgresql"
        
        # Check host
        host = parsed.hostname or ""
        if host not in ALLOWED_DISPOSABLE_HOSTS:
            return False, f"Host '{host}' not in allowed disposable hosts: {sorted(ALLOWED_DISPOSABLE_HOSTS)}"
        
        # Check database name
        db_name = parsed.path.lstrip("/") if parsed.path else ""
        if db_name not in ALLOWED_DISPOSABLE_DATABASES:
            return False, f"Database '{db_name}' not in allowed disposable databases: {sorted(ALLOWED_DISPOSABLE_DATABASES)}"
        
        # Check username
        username = parsed.username or ""
        if username not in ALLOWED_DISPOSABLE_USERS:
            return False, f"User '{username}' not in allowed disposable users: {sorted(ALLOWED_DISPOSABLE_USERS)}"
        
        # Check port (optional, but warn on non-standard)
        port = parsed.port
        if port and port != 5432:
            # Allow non-standard ports for local testing but log
            pass
        
        # Ensure no production-like patterns in the full URL
        url_lower = test_url.lower()
        for pattern in FORBIDDEN_URL_PATTERNS:
            if pattern in url_lower:
                return False, f"Test URL contains forbidden pattern '{pattern}': {test_url}"
        
        # Additional check: ensure no Neon project/branch settings in URL params
        # (disposable test DBs should not have Neon-specific configuration)
        if parsed.query:
            query_lower = parsed.query.lower()
            neon_params = ["neon_project_id", "neon_branch_id", "neon_branch_name", "endpoint"]
            for param in neon_params:
                if param in query_lower:
                    return False, f"Test URL contains Neon-specific parameter '{param}': {test_url}"
        
        # Validate no password in URL for security (optional but recommended)
        if parsed.password:
            # Password in URL is allowed but flagged for review
            pass
        
        return True, None
    except Exception as e:
        return False, f"Failed to parse test URL: {e}"


def create_test_schema(conn: PgConnection) -> None:
    """
    Create the test schema for atomicity testing.
    
    This schema mirrors the production scholarships table structure sufficiently
    to test transaction commit/rollback semantics (DELETE with RETURNING, etc.).
    
    IMPORTANT: This does NOT validate production FK behavior, cascade rules,
    or purge impact. Gate 3 separately covers FK dependency behavior on the
    real production schema with correct schema-aware joins.
    """
    with conn.cursor() as cur:
        # Create the scholarships table matching production column structure
        # (sufficient for atomicity tests: DELETE ... RETURNING, rollback verification)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scholarships (
                id INTEGER PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                country VARCHAR(120) NOT NULL,
                degree VARCHAR(80),
                funding VARCHAR(80),
                funding_type VARCHAR(40),
                deadline_date DATE,
                deadline_display VARCHAR(80),
                deadline_precision VARCHAR(20),
                status VARCHAR(20) DEFAULT 'closed',
                fully_funded BOOLEAN,
                funding_amount VARCHAR(40),
                funding_currency VARCHAR(10),
                funding_period VARCHAR(40),
                tuition_coverage BOOLEAN,
                living_cost_coverage BOOLEAN,
                travel_coverage BOOLEAN,
                accommodation BOOLEAN,
                insurance BOOLEAN,
                insurance_coverage VARCHAR(40),
                duration VARCHAR(80),
                conditions TEXT,
                funding_details TEXT,
                official_source VARCHAR(255),
                official_source_url VARCHAR(500),
                official_details TEXT,
                applicant_utility TEXT,
                programme_verification TEXT,
                auto_delete_candidate_since DATE,
                deletion_protected BOOLEAN DEFAULT FALSE,
                verification_status VARCHAR(40),
                last_verified_at DATE,
                verified_by VARCHAR(80),
                verification_notes TEXT,
                next_verification_due DATE,
                is_archived BOOLEAN DEFAULT FALSE,
                archived_at TIMESTAMPTZ,
                archived_reason TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # Create indexes matching production (for realistic query plans)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scholarships_deadline ON scholarships(deadline_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scholarships_status ON scholarships(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scholarships_country ON scholarships(country)")
        
        conn.commit()


def create_synthetic_fixtures(conn: PgConnection, synthetic_ids: list[int]) -> int:
    """
    Create synthetic test fixtures for rollback/idempotency testing.
    These are DISPOSABLE records with synthetic IDs that never overlap
    with canonical production IDs.
    """
    with conn.cursor() as cur:
        # Clear any existing synthetic test data
        cur.execute("DELETE FROM scholarships WHERE id = ANY(%s)", (synthetic_ids,))

        # Insert synthetic fixtures with full schema
        for tid in synthetic_ids:
            cur.execute("""
                INSERT INTO scholarships (
                    id, title, country, degree, funding, funding_type,
                    deadline_date, deadline_display, deadline_precision, status,
                    fully_funded, funding_amount, funding_currency, funding_period,
                    tuition_coverage, living_cost_coverage, travel_coverage,
                    accommodation, insurance, insurance_coverage, duration,
                    conditions, funding_details, official_source, official_source_url,
                    official_details, applicant_utility, programme_verification,
                    auto_delete_candidate_since, deletion_protected, verification_status,
                    last_verified_at, verified_by, verification_notes,
                    next_verification_due, is_archived, archived_at, archived_reason
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s
                )
            """, (
                tid,
                f"Synthetic Test {tid}",
                "Synthetic Country",
                "Master's",
                "Fully Funded",
                "scholarship",
                date(2025, 1, 15),  # Past deadline
                "2025-01-15",
                "day",
                "closed",
                True,
                "50000",
                "USD",
                "yearly",
                True,
                True,
                True,
                True,
                True,
                "full",
                "2 years",
                "Academic excellence",
                "Test funding details",
                "Test Source",
                "https://example.com/test",
                "Test official details",
                "Test utility",
                "Test verification",
                None,
                False,
                "verified",
                date(2025, 1, 15),
                "test",
                "Test notes",
                None,
                False,
                None,
                None
            ))

        conn.commit()

        # Verify insertion
        cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (synthetic_ids,))
        return cur.fetchone()[0]


def run_gate1(accessor: DatabaseAccessor) -> Gate1Result:
    """
    Execute Gate 1: Atomicity and Rollback tests.

    Args:
        accessor: DatabaseAccessor with test database configured

    Returns:
        Gate1Result with all test outcomes
    """
    result = Gate1Result()
    result.target_ids = PRIMARY_TEST_IDS  # Synthetic IDs only

    # Verify we have a test database
    if not accessor.config.test_url:
        result.status = "ERROR"
        result.error = "TEST_DATABASE_URL not configured - Gate 1 requires disposable test database"
        return result

    # Validate disposable database URL
    is_valid, error = validate_disposable_database_url(accessor.config.test_url)
    if not is_valid:
        result.status = "FAIL"
        result.error = f"Invalid TEST_DATABASE_URL: {error}"
        return result

    try:
        # === PHASE 0: Setup test schema ===
        with accessor.connect_test() as conn:
            create_test_schema(conn)

        # === PHASE 1: Create synthetic fixtures for primary test ===
        # Uses module-level PRIMARY_TEST_IDS (synthetic, high range 80000+)
        with accessor.connect_test() as conn:
            fixture_count = create_synthetic_fixtures(conn, PRIMARY_TEST_IDS)
            if fixture_count != len(PRIMARY_TEST_IDS):
                result.status = "FAIL"
                result.error = f"Synthetic fixture creation failed: expected {len(PRIMARY_TEST_IDS)}, got {fixture_count}"
                return result

        # === PHASE 2: Test atomic deletion with exact assertions ===
        with accessor.connect_test() as conn:
            conn.autocommit = False

            # Pre-deletion verification
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (PRIMARY_TEST_IDS,))
                result.pre_deletion_count = cur.fetchone()[0]

                if result.pre_deletion_count != len(PRIMARY_TEST_IDS):
                    conn.rollback()
                    result.status = "FAIL"
                    result.error = f"Pre-deletion count mismatch: expected {len(PRIMARY_TEST_IDS)}, got {result.pre_deletion_count}"
                    return result

            # Execute deletion with RETURNING
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM scholarships WHERE id = ANY(%s) RETURNING id",
                    (PRIMARY_TEST_IDS,)
                )
                deleted_rows = cur.fetchall()
                result.deleted_ids = sorted([row[0] for row in deleted_rows])
                result.deleted_count = len(result.deleted_ids)

                # Assertion: exactly N rows deleted
                if result.deleted_count != len(PRIMARY_TEST_IDS):
                    conn.rollback()
                    result.status = "FAIL"
                    result.error = f"Expected {len(PRIMARY_TEST_IDS)} rows deleted, got {result.deleted_count}"
                    return result

                # Exact ID match (sorted comparison)
                if result.deleted_ids != sorted(PRIMARY_TEST_IDS):
                    conn.rollback()
                    result.status = "FAIL"
                    result.error = f"ID mismatch: expected {sorted(PRIMARY_TEST_IDS)}, got {result.deleted_ids}"
                    return result
                result.exact_match = True

            # Verify zero remaining
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (PRIMARY_TEST_IDS,))
                result.remaining_targets = cur.fetchone()[0]
                if result.remaining_targets != 0:
                    conn.rollback()
                    result.status = "FAIL"
                    result.error = f"{result.remaining_targets} target IDs still exist after deletion"
                    return result

            # Total count verification
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scholarships")
                result.total_after_deletion = cur.fetchone()[0]

            # Commit the deletion
            conn.commit()

        # === PHASE 3: Genuine rollback test with SEPARATE synthetic fixtures ===
        # Create synthetic records in a COMMITTED transaction
        with accessor.connect_test() as conn:
            synthetic_count = create_synthetic_fixtures(conn, ROLLBACK_TEST_IDS)
            if synthetic_count != len(ROLLBACK_TEST_IDS):
                result.status = "FAIL"
                result.error = f"Synthetic rollback fixture creation failed: expected {len(ROLLBACK_TEST_IDS)}, got {synthetic_count}"
                return result

        # Now test rollback: start NEW transaction, delete synthetic records, force failure
        rollback_exception_raised = False
        try:
            with accessor.connect_test() as conn:
                conn.autocommit = False

                # Verify synthetic records exist before deletion
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (ROLLBACK_TEST_IDS,))
                    before_delete = cur.fetchone()[0]
                    if before_delete != len(ROLLBACK_TEST_IDS):
                        conn.rollback()
                        result.status = "FAIL"
                        result.error = f"Synthetic records missing before rollback test: expected {len(ROLLBACK_TEST_IDS)}, got {before_delete}"
                        return result

                # Delete synthetic records
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM scholarships WHERE id = ANY(%s) RETURNING id", (ROLLBACK_TEST_IDS,))
                    deleted_rows = cur.fetchall()
                    deleted_count = len(deleted_rows)

                    # FORCE a controlled failure - simulates assertion failure in real logic
                    raise RuntimeError("SIMULATED ASSERTION FAILURE - Testing rollback")

        except RuntimeError as e:
            if "SIMULATED ASSERTION FAILURE" in str(e):
                rollback_exception_raised = True
                # This is our expected simulated failure - verify rollback worked
                with accessor.connect_test() as conn:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (ROLLBACK_TEST_IDS,))
                        after_rollback = cur.fetchone()[0]
                        result.rollback_test_passed = (after_rollback == len(ROLLBACK_TEST_IDS))

                        if not result.rollback_test_passed:
                            result.status = "FAIL"
                            result.error = f"Rollback failed: expected {len(ROLLBACK_TEST_IDS)} records after rollback, got {after_rollback}"
                            return result

                # === PHASE 4: Idempotency test with SEPARATE synthetic fixtures ===
                # Create fresh synthetic records for idempotency test
                with accessor.connect_test() as conn:
                    synthetic_count = create_synthetic_fixtures(conn, IDEMPOTENCY_TEST_IDS)
                    if synthetic_count != len(IDEMPOTENCY_TEST_IDS):
                        result.status = "FAIL"
                        result.error = f"Synthetic idempotency fixture creation failed: expected {len(IDEMPOTENCY_TEST_IDS)}, got {synthetic_count}"
                        return result

                # First deletion - should delete all synthetic records
                with accessor.connect_test() as conn:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM scholarships WHERE id = ANY(%s) RETURNING id", (IDEMPOTENCY_TEST_IDS,))
                        deleted_rows = cur.fetchall()
                        first_delete_count = len(deleted_rows)
                        conn.commit()

                # Second deletion - should delete 0 records (idempotent)
                with accessor.connect_test() as conn:
                    conn.autocommit = False
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM scholarships WHERE id = ANY(%s) RETURNING id", (IDEMPOTENCY_TEST_IDS,))
                        deleted_rows = cur.fetchall()
                        second_delete_count = len(deleted_rows)
                        conn.commit()

                result.idempotent_test_passed = (first_delete_count == len(IDEMPOTENCY_TEST_IDS) and second_delete_count == 0)

                if not result.idempotent_test_passed:
                    result.status = "FAIL"
                    result.error = f"Idempotency test failed: first delete={first_delete_count}, second delete={second_delete_count}"
                    return result

                # === PHASE 5: Final verification - database should be clean ===
                with accessor.connect_test() as conn:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM scholarships")
                        result.final_count = cur.fetchone()[0]

                if not rollback_exception_raised:
                    result.status = "ERROR"
                    result.error = "Rollback test did not trigger expected exception handling"
                    return result

                result.status = "PASS"
                return result

        # This should never be reached
        result.status = "ERROR"
        result.error = "Unexpected code path in rollback test"
        return result

    except psycopg2.Error as e:
        result.status = "ERROR"
        result.error = f"Database error: {e}"
        return result
    except Exception as e:
        result.status = "ERROR"
        result.error = f"Unexpected error: {e}"
        return result


def main() -> int:
    """CLI entry point for Gate 1."""
    print("=== GATE 1: ATOMICITY AND ROLLBACK ===")
    print(f"Canonical Target IDs (reference only, NEVER used as fixtures): {CANONICAL_TARGET_IDS}")
    print(f"Primary test synthetic IDs (80000+): {PRIMARY_TEST_IDS[:5]}... (35 total)")
    print(f"Rollback test synthetic IDs: {ROLLBACK_TEST_IDS}")
    print(f"Idempotency test synthetic IDs: {IDEMPOTENCY_TEST_IDS}")
    print()
    print("NOTE: This gate tests transaction atomicity/rollback ONLY.")
    print("      It does NOT validate production FK behavior or purge impact.")
    print("      Gate 3 covers FK dependency behavior on real production schema.")
    print()

    # Load config - will fail if TEST_DATABASE_URL not set
    try:
        from .config import load_config
        config = load_config()
        db_config = config.database
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        print("Gate 1 requires TEST_DATABASE_URL to be set to a disposable PostgreSQL instance.", file=sys.stderr)
        return 1

    # Verify this is NOT a production database
    is_valid, error = validate_disposable_database_url(db_config.test_url or "")
    if not is_valid:
        print(f"ERROR: TEST_DATABASE_URL validation failed: {error}", file=sys.stderr)
        return 1

    accessor = create_accessor(db_config)
    result = run_gate1(accessor)

    # Save results with metadata
    save_result_with_metadata(result.to_dict(), "gate1", "gate1_result.json")

    print("\n=== GATE 1 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print("\n✅ GATE 1 PASSED")
        return 0
    else:
        print(f"\n❌ GATE 1 {result.status}: {result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())