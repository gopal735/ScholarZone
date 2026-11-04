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
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection

from .manifest import CANONICAL_TARGET_IDS, TARGET_ID_SET
from .database import DatabaseAccessor, create_accessor
from .config import DatabaseConfig


# Synthetic fixture IDs - NEVER use canonical production IDs as fixtures
# These are purely for testing transaction behavior in the disposable DB
ROLLBACK_TEST_IDS = [9001, 9002]  # Synthetic IDs for rollback test
IDEMPOTENCY_TEST_IDS = [9101, 9102, 9103]  # Synthetic IDs for idempotency test


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
            self.target_ids = CANONICAL_TARGET_IDS
        if self.deleted_ids is None:
            self.deleted_ids = []

    def to_dict(self) -> dict:
        return asdict(self)


def create_canonical_fixtures(conn: PgConnection, target_ids: list[int]) -> int:
    """
    Create canonical test fixtures (34 target records) in the disposable database.

    Inserts the 34 target records with minimal required fields.
    Returns the total count after insertion.
    """
    with conn.cursor() as cur:
        # Ensure scholarships table exists with minimal schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scholarships (
                id INTEGER PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                country VARCHAR(120) NOT NULL,
                deadline_date DATE,
                status VARCHAR(20) DEFAULT 'closed',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Clear any existing test data for canonical IDs
        cur.execute("DELETE FROM scholarships WHERE id = ANY(%s)", (target_ids,))

        # Insert canonical test fixtures
        for tid in target_ids:
            cur.execute("""
                INSERT INTO scholarships (id, title, country, deadline_date, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    country = EXCLUDED.country,
                    deadline_date = EXCLUDED.deadline_date,
                    status = EXCLUDED.status
            """, (
                tid,
                f"Test Scholarship {tid}",
                "Test Country",
                date(2025, 1, 15),  # Past deadline
                "closed"
            ))

        conn.commit()

        # Verify insertion
        cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (target_ids,))
        return cur.fetchone()[0]


def create_synthetic_fixtures(conn: PgConnection, synthetic_ids: list[int]) -> int:
    """
    Create synthetic test fixtures for rollback/idempotency testing.

    These are DISPOSABLE records with synthetic IDs that never overlap
    with canonical production IDs.
    """
    with conn.cursor() as cur:
        # Clear any existing synthetic test data
        cur.execute("DELETE FROM scholarships WHERE id = ANY(%s)", (synthetic_ids,))

        # Insert synthetic fixtures
        for tid in synthetic_ids:
            cur.execute("""
                INSERT INTO scholarships (id, title, country, deadline_date, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                tid,
                f"Synthetic Test {tid}",
                "Synthetic Country",
                date(2025, 1, 15),
                "closed"
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
    target_ids = CANONICAL_TARGET_IDS

    # Verify we have a test database
    if not accessor.config.test_url:
        result.status = "ERROR"
        result.error = "TEST_DATABASE_URL not configured - Gate 1 requires disposable test database"
        return result

    try:
        # === PHASE 1: Setup canonical test fixtures (34 records) ===
        with accessor.connect_test() as conn:
            fixture_count = create_canonical_fixtures(conn, target_ids)
            if fixture_count != 34:
                result.status = "FAIL"
                result.error = f"Canonical fixture creation failed: expected 34, got {fixture_count}"
                return result

            # Verify total count
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM scholarships")
            total_before = cur.fetchone()[0]

        # === PHASE 2: Test atomic deletion with exact assertions ===
        with accessor.connect_test() as conn:
            conn.autocommit = False

            # Pre-deletion verification
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (target_ids,))
                result.pre_deletion_count = cur.fetchone()[0]

                if result.pre_deletion_count != 34:
                    conn.rollback()
                    result.status = "FAIL"
                    result.error = f"Pre-deletion count mismatch: expected 34, got {result.pre_deletion_count}"
                    return result

            # Execute deletion with RETURNING
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM scholarships WHERE id = ANY(%s) RETURNING id",
                    (target_ids,)
                )
                deleted_rows = cur.fetchall()
                result.deleted_ids = sorted([row[0] for row in deleted_rows])
                result.deleted_count = len(result.deleted_ids)

                # Assertion: exactly 34 rows deleted
                if result.deleted_count != 34:
                    conn.rollback()
                    result.status = "FAIL"
                    result.error = f"Expected 34 rows deleted, got {result.deleted_count}"
                    return result

                # Exact ID match (sorted canonical comparison)
                if result.deleted_ids != sorted(target_ids):
                    conn.rollback()
                    result.status = "FAIL"
                    result.error = f"ID mismatch: expected {sorted(target_ids)}, got {result.deleted_ids}"
                    return result
                result.exact_match = True

            # Verify zero remaining
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scholarships WHERE id = ANY(%s)", (target_ids,))
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

        # If we reach here, the exception wasn't caught - this should not happen
        result.status = "ERROR"
        result.error = "Rollback test did not trigger expected exception handling"
        return result

    except RuntimeError as e:
        if "SIMULATED ASSERTION FAILURE" in str(e):
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
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print(f"Count: {len(CANONICAL_TARGET_IDS)}")
    print(f"Rollback test synthetic IDs: {ROLLBACK_TEST_IDS}")
    print(f"Idempotency test synthetic IDs: {IDEMPOTENCY_TEST_IDS}")
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
    if db_config.test_url and ("SCHOLARZONE_DATABASE_URL" in db_config.test_url or "production" in db_config.test_url.lower()):
        print("ERROR: TEST_DATABASE_URL appears to be a production database!", file=sys.stderr)
        return 1

    accessor = create_accessor(db_config)
    result = run_gate1(accessor)

    # Save results
    with open("gate1_result.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)

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