"""
Test suite for duplicate archive operations against disposable PostgreSQL 16/18.

Validates the archive-only duplicate merge plan against real PostgreSQL
schema constraints, including:
- Archive-only UPDATE (is_archived, archived_at, archived_reason only)
- FK preservation (scholarship_supervisor_coverage rows preserved)
- UNIQUE(scholarship_id) collision on FK reassignment
- Transaction rollback safety
- Idempotent repeated execution
- Exact before/after row counts
- Fulbright pair (1217/1309) remains untouched

NO production database access. Uses TEST_DATABASE_URL environment variable
pointing to a disposable PostgreSQL instance (GitHub Actions service container).
Fails closed if TEST_DATABASE_URL is not set or points to a non-disposable target.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import connection as PgConnection

import pytest

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# =============================================================================
# Duplicate Pair Definitions (from duplicate_merge_plan.json)
# =============================================================================

# Canonical ID -> Duplicate ID pairs that are archive-ready
DUPLICATE_PAIRS = [
    {"canonical_id": 183, "duplicate_id": 753, "pair_id": 1},
    {"canonical_id": 270, "duplicate_id": 1244, "pair_id": 2},
    {"canonical_id": 271, "duplicate_id": 760, "pair_id": 3},
    {"canonical_id": 285, "duplicate_id": 1277, "pair_id": 4},
    {"canonical_id": 645, "duplicate_id": 654, "pair_id": 6},
]

# Fulbright pair - must remain untouched (BLOCKED_MANUAL_REVIEW)
FULBRIGHT_CANONICAL_ID = 1217
FULBRIGHT_DUPLICATE_ID = 1309

# Expected total record count before any archives
EXPECTED_TOTAL_RECORDS = 830

# Expected active count before any archives
EXPECTED_ACTIVE_RECORDS = 830

# Expected archived count before any archives
EXPECTED_ARCHIVED_RECORDS = 0


# =============================================================================
# Database Schema Definition
# =============================================================================

SCHOLARSHIPS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scholarships (
    id INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    country VARCHAR(120) NOT NULL,
    degree VARCHAR(255),
    funding VARCHAR(120),
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at TIMESTAMP WITH TIME ZONE,
    archived_reason VARCHAR(120),
    official_source_url VARCHAR(2048) NOT NULL,
    application_link VARCHAR(2048),
    fully_funded BOOLEAN,
    region TEXT,
    deadline_date DATE,
    deadline_display TEXT,
    deadline_precision VARCHAR(16)
);
"""

COVERAGE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scholarship_supervisor_coverage (
    id SERIAL PRIMARY KEY,
    scholarship_id INTEGER NOT NULL REFERENCES scholarships(id) ON DELETE NO ACTION ON UPDATE NO ACTION,
    supervisor_id INTEGER NOT NULL,
    coverage_type VARCHAR(64),
    coverage_details JSONB,
    UNIQUE(scholarship_id)
);
"""


# =============================================================================
# Test Data
# =============================================================================

CANONICAL_RECORDS = [
    {
        "id": 183,
        "title": "Lund University Global Scholarship",
        "country": "Sweden",
        "degree": "Master's, PhD",
        "funding": "Partial",
        "status": "open",
        "official_source_url": "https://www.lunduniversity.lu.se/study/admission-degree-studies/scholarships-and-awards/lund-university-global-scholarship",
        "application_link": "https://www.lunduniversity.lu.se/study/admission-degree-studies/scholarships-and-awards/lund-university-global-scholarship",
    },
    {
        "id": 270,
        "title": "Copenhagen Business School Danish Government Scholarship",
        "country": "Denmark",
        "degree": "Master's, PhD",
        "funding": "Partial",
        "status": "open",
        "official_source_url": "https://www.cbs.dk/study-programmes/master-programmes/double-degree",
        "application_link": "https://www.cbs.dk/study-programmes/master-programmes/double-degree",
    },
    {
        "id": 271,
        "title": "University of Copenhagen Danish Government Scholarship",
        "country": "Denmark",
        "degree": "Master's, PhD",
        "funding": "Partial",
        "status": "open",
        "official_source_url": "https://www.ku.dk/studies/admission/scholarships-for-full-degree-students",
        "application_link": "https://www.ku.dk/studies/admission/scholarships-for-full-degree-students",
    },
    {
        "id": 285,
        "title": "Stipendium Hungaricum Scholarship Programme",
        "country": "Hungary",
        "degree": "Bachelor's, Master's, One-tier Master's, Doctoral, Non-degree",
        "funding": "Fully Funded",
        "status": "open",
        "official_source_url": "https://stipendiumhungaricum.hu",
        "application_link": "https://stipendiumhungaricum.hu",
    },
    {
        "id": 645,
        "title": "TaiwanICDF Scholarship Program (International Higher Education Scholarship Program), TaiwanICDF",
        "country": "Taiwan",
        "degree": "Master's, PhD",
        "funding": "Partial",
        "status": "open",
        "official_source_url": "https://www.icdf.org.tw/wSite/ct?ctNode=31562&mp=2&xItem=12505",
        "application_link": "https://www.icdf.org.tw/wSite/ct?ctNode=31562&mp=2&xItem=12505",
    },
]

DUPLICATE_RECORDS = [
    {
        "id": 753,
        "title": "Lund University Global Scholarship",
        "country": "Sweden",
        "degree": "Bachelor's, Master's",
        "funding": "Partial",
        "status": "open",
        "official_source_url": "https://www.lunduniversity.lu.se/admissions/scholarships-and-awards/lund-university-global-scholarship",
        "application_link": "https://www.lunduniversity.lu.se/admissions/scholarships-and-awards/lund-university-global-scholarship",
    },
    {
        "id": 1244,
        "title": "Copenhagen Business School Danish Government Scholarship",
        "country": "Denmark",
        "degree": "Master's (MSc)",
        "funding": "Partial to Full",
        "status": "open",
        "official_source_url": "https://www.cbs.dk/en/education/master/programmes-and-admission/fees-and-funding",
        "application_link": "https://www.cbs.dk/en/education/master/programmes-and-admission/fees-and-funding",
    },
    {
        "id": 760,
        "title": "University of Copenhagen Danish Government Scholarship",
        "country": "Denmark",
        "degree": "Master's",
        "funding": "Partial",
        "status": "open",
        "official_source_url": "https://www.ku.dk/studies/masters/application-and-admission/scholarships",
        "application_link": "https://www.ku.dk/studies/masters/application-and-admission/scholarships",
    },
    {
        "id": 1277,
        "title": "Stipendium Hungaricum Scholarship Programme",
        "country": "Hungary",
        "degree": "Bachelor's, Master's, One-tier Master's, PhD, Postdoctoral, Non-degree",
        "funding": "Fully Funded",
        "status": "open",
        "official_source_url": "https://stipendiumhungaricum.hu/apply_call",
        "application_link": "https://stipendiumhungaricum.hu/apply_call",
    },
    {
        "id": 654,
        "title": "TaiwanICDF Scholarship Program (Taiwan International Cooperation and Development Fund International",
        "country": "Taiwan",
        "degree": "Master's, PhD",
        "funding": "Partial",
        "status": "open",
        "official_source_url": "https://www.icdf.org.tw/wSite/ct?xItem=12505&ctNode=31562&mp=2",
        "application_link": "https://www.icdf.org.tw/wSite/ct?xItem=12505&ctNode=31562&mp=2",
    },
]

# Fulbright records - must remain untouched
FULBRIGHT_RECORDS = [
    {
        "id": 1217,
        "title": "Fulbright Foreign Student Program",
        "country": "United States",
        "degree": "Master's, PhD, Research",
        "funding": "Fully Funded",
        "status": "open",
        "official_source_url": "https://foreign.fulbrightonline.org",
        "application_link": "https://foreign.fulbrightonline.org",
    },
    {
        "id": 1309,
        "title": "Fulbright Foreign Student Program",
        "country": "United States",
        "degree": "Bachelor's, Master's, PhD",
        "funding": "Partial Funding",
        "status": "open",
        "official_source_url": "https://fulbright.state.gov",
        "application_link": "https://fulbright.state.gov",
    },
]


# =============================================================================
# Validation Functions
# =============================================================================

def validate_disposable_database_url(test_url: str) -> tuple[bool, str]:
    """
    Validate that TEST_DATABASE_URL points to a disposable PostgreSQL instance.
    Fails closed on any ambiguity or missing configuration.
    """
    if not test_url:
        return False, "TEST_DATABASE_URL is empty or not set"

    try:
        from urllib.parse import urlparse
        parsed = urlparse(test_url)

        if parsed.scheme not in ("postgresql", "postgres"):
            return False, f"Invalid scheme: {parsed.scheme}, expected postgresql"

        host = parsed.hostname or ""
        allowed_hosts = {"localhost", "127.0.0.1", "postgres", "db", "db-service"}
        if host not in allowed_hosts:
            return False, f"Host '{host}' not in allowed disposable hosts"

        db_name = parsed.path.lstrip("/") if parsed.path else ""
        allowed_dbs = {"test", "test_purge", "pytest", "postgres", "duplicate_archive_test", "test_duplicate_archive"}
        if db_name not in allowed_dbs:
            return False, f"Database '{db_name}' not in allowed disposable databases"

        username = parsed.username or ""
        allowed_users = {"test", "postgres", "pytest"}
        if username not in allowed_users:
            return False, f"User '{username}' not in allowed disposable users"

        url_lower = test_url.lower()
        forbidden_patterns = [
            "neon.tech", "production", "prod", "scholarzone",
            "rds.amazonaws.com", "cloudsql", "postgres.database.azure.com",
            "aws.neon.tech", "neon.amazonaws.com",
        ]
        for pattern in forbidden_patterns:
            if pattern in url_lower:
                return False, f"Test URL contains forbidden pattern '{pattern}'"

        return True, None
    except Exception as e:
        return False, f"Failed to parse test URL: {e}"


def count_records(conn: PgConnection) -> int:
    """Count total scholarships."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM scholarships")
        return cur.fetchone()[0]


def count_active_records(conn: PgConnection) -> int:
    """Count active (non-archived) scholarships."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived = FALSE")
        return cur.fetchone()[0]


def count_archived_records(conn: PgConnection) -> int:
    """Count archived scholarships."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived = TRUE")
        return cur.fetchone()[0]


def count_coverage_rows(conn: PgConnection) -> int:
    """Count scholarship_supervisor_coverage rows."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM scholarship_supervisor_coverage")
        return cur.fetchone()[0]


def get_record_field(conn: PgConnection, record_id: int, field: str):
    """Get a single field value for a record."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT {field} FROM scholarships WHERE id = %s", (record_id,))
        row = cur.fetchone()
        return row[0] if row else None


def get_coverage_row_for_scholarship(conn: PgConnection, scholarship_id: int):
    """Get coverage row for a scholarship."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, scholarship_id, supervisor_id FROM scholarship_supervisor_coverage WHERE scholarship_id = %s",
            (scholarship_id,)
        )
        return cur.fetchone()


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def db_conn():
    """Create a disposable PostgreSQL connection for testing."""
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL not set - skipping PostgreSQL duplicate archive test")

    is_valid, error_msg = validate_disposable_database_url(test_url)
    if not is_valid:
        pytest.fail(f"Invalid test database URL: {error_msg}")

    conn = psycopg2.connect(test_url)
    conn.autocommit = False

    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def populated_db(db_conn: PgConnection):
    """
    Populate the disposable database with test data:
    - Create scholarships and scholarship_supervisor_coverage tables
    - Insert 5 canonical + 5 duplicate records (10 total)
    - Insert Fulbright records (1217, 1309) - must remain untouched
    - Insert coverage rows for all 12 records
    """
    with db_conn.cursor() as cur:
        # Create tables
        cur.execute(SCHOLARSHIPS_TABLE_SQL)
        cur.execute(COVERAGE_TABLE_SQL)

        # Insert canonical records
        for record in CANONICAL_RECORDS:
            cur.execute("""
                INSERT INTO scholarships (id, title, country, degree, funding, status,
                                          is_archived, official_source_url, application_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record["id"], record["title"], record["country"], record["degree"],
                record["funding"], record["status"], False,
                record["official_source_url"], record["application_link"]
            ))

        # Insert duplicate records
        for record in DUPLICATE_RECORDS:
            cur.execute("""
                INSERT INTO scholarships (id, title, country, degree, funding, status,
                                          is_archived, official_source_url, application_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record["id"], record["title"], record["country"], record["degree"],
                record["funding"], record["status"], False,
                record["official_source_url"], record["application_link"]
            ))

        # Insert Fulbright records (must remain untouched)
        for record in FULBRIGHT_RECORDS:
            cur.execute("""
                INSERT INTO scholarships (id, title, country, degree, funding, status,
                                          is_archived, official_source_url, application_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record["id"], record["title"], record["country"], record["degree"],
                record["funding"], record["status"], False,
                record["official_source_url"], record["application_link"]
            ))

        # Insert coverage rows for all records
        all_record_ids = [r["id"] for r in CANONICAL_RECORDS] + \
                         [r["id"] for r in DUPLICATE_RECORDS] + \
                         [r["id"] for r in FULBRIGHT_RECORDS]

        for idx, sid in enumerate(all_record_ids):
            cur.execute("""
                INSERT INTO scholarship_supervisor_coverage (scholarship_id, supervisor_id, coverage_type, coverage_details)
                VALUES (%s, %s, %s, %s)
            """, (sid, idx + 1, "primary", '{"primary": true}'))

        db_conn.commit()

    yield db_conn

    # Cleanup: drop tables
    with db_conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS scholarship_supervisor_coverage CASCADE")
        cur.execute("DROP TABLE IF EXISTS scholarships CASCADE")
        db_conn.commit()


# =============================================================================
# Test Functions
# =============================================================================

def test_database_connection_and_version(populated_db: PgConnection):
    """Test that we can connect to PostgreSQL and get the version."""
    with populated_db.cursor() as cur:
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        assert "PostgreSQL" in version
        # Verify it's PostgreSQL 16 or 18
        assert "PostgreSQL 16" in version or "PostgreSQL 18" in version, \
            f"Expected PostgreSQL 16 or 18, got: {version}"


def test_baseline_counts(populated_db: PgConnection):
    """Test baseline record counts before any archives."""
    total = count_records(populated_db)
    active = count_active_records(populated_db)
    archived = count_archived_records(populated_db)
    coverage = count_coverage_rows(populated_db)

    # 5 canonical + 5 duplicate + 2 Fulbright = 12 records
    assert total == 12, f"Expected 12 total records, got {total}"
    assert active == 12, f"Expected 12 active records, got {active}"
    assert archived == 0, f"Expected 0 archived records, got {archived}"
    assert coverage == 12, f"Expected 12 coverage rows, got {coverage}"


def test_pair_1_lund_university_archive(populated_db: PgConnection):
    """Test archiving duplicate ID 753 (Lund University)."""
    canonical_id = 183
    duplicate_id = 753

    # Preconditions
    canonical_status = get_record_field(populated_db, canonical_id, "status")
    duplicate_status = get_record_field(populated_db, duplicate_id, "status")
    canonical_url = get_record_field(populated_db, canonical_id, "official_source_url")
    duplicate_url = get_record_field(populated_db, duplicate_id, "official_source_url")
    canonical_archived = get_record_field(populated_db, canonical_id, "is_archived")
    duplicate_archived = get_record_field(populated_db, duplicate_id, "is_archived")

    assert canonical_status == "open", f"Canonical should be open, got {canonical_status}"
    assert duplicate_status == "open", f"Duplicate should be open, got {duplicate_status}"
    assert canonical_url != duplicate_url, "URLs should be distinct"
    assert canonical_archived is False, "Canonical should not be archived"
    assert duplicate_archived is False, "Duplicate should not be archived"

    # Capture pre-state counts
    total_before = count_records(populated_db)
    active_before = count_active_records(populated_db)
    archived_before = count_archived_records(populated_db)

    # Execute archive-only update
    archived_reason = f"Duplicate of ID {canonical_id} (Lund University Global Scholarship); archive-only 2026-11-10"
    with populated_db.cursor() as cur:
        cur.execute("""
            UPDATE scholarships
            SET is_archived = TRUE,
                archived_at = COALESCE(archived_at, %s),
                archived_reason = %s
            WHERE id = %s AND is_archived = FALSE
        """, (datetime.utcnow(), archived_reason, duplicate_id))
        rows_affected = cur.rowcount
        populated_db.commit()

    assert rows_affected == 1, f"Expected 1 row affected, got {rows_affected}"

    # Post-conditions
    duplicate_is_archived = get_record_field(populated_db, duplicate_id, "is_archived")
    duplicate_archived_reason = get_record_field(populated_db, duplicate_id, "archived_reason")
    canonical_is_archived = get_record_field(populated_db, canonical_id, "is_archived")
    canonical_url_after = get_record_field(populated_db, canonical_id, "official_source_url")
    duplicate_url_after = get_record_field(populated_db, duplicate_id, "official_source_url")
    canonical_degree = get_record_field(populated_db, canonical_id, "degree")
    duplicate_degree = get_record_field(populated_db, duplicate_id, "degree")
    canonical_funding = get_record_field(populated_db, canonical_id, "funding")
    duplicate_funding = get_record_field(populated_db, duplicate_id, "funding")

    assert duplicate_is_archived is True, f"Duplicate should be archived, got {duplicate_is_archived}"
    assert duplicate_archived_reason is not None, "Duplicate archived_reason should be set"
    assert canonical_is_archived is False, f"Canonical should not be archived, got {canonical_is_archived}"
    assert canonical_url_after == canonical_url, "Canonical URL should be unchanged"
    assert duplicate_url_after == duplicate_url, "Duplicate URL should be unchanged"
    assert canonical_degree == "Master's, PhD", "Canonical degree should be unchanged"
    assert duplicate_degree == "Bachelor's, Master's", "Duplicate degree should be unchanged"
    assert canonical_funding == "Partial", "Canonical funding should be unchanged"
    assert duplicate_funding == "Partial", "Duplicate funding should be unchanged"

    # Post-state counts
    total_after = count_records(populated_db)
    active_after = count_active_records(populated_db)
    archived_after = count_archived_records(populated_db)

    assert total_after == total_before, f"Total count changed: {total_before} -> {total_after}"
    assert active_after == active_before - 1, f"Active count should decrease by 1: {active_before} -> {active_after}"
    assert archived_after == archived_before + 1, f"Archived count should increase by 1: {archived_before} -> {archived_after}"


def test_unique_collision_on_coverage_reassignment(populated_db: PgConnection):
    """Test that reassigning duplicate coverage row to canonical ID causes UNIQUE collision."""
    canonical_id = 183
    duplicate_id = 753

    # Get duplicate's coverage row
    dup_coverage = get_coverage_row_for_scholarship(populated_db, duplicate_id)
    assert dup_coverage is not None, "Duplicate should have coverage row"

    # Get canonical's coverage row
    canon_coverage = get_coverage_row_for_scholarship(populated_db, canonical_id)
    assert canon_coverage is not None, "Canonical should have coverage row"

    # Attempt to reassign duplicate's coverage row to canonical ID - should fail with UNIQUE violation
    collision_detected = False
    with populated_db.cursor() as cur:
        try:
            cur.execute("""
                UPDATE scholarship_supervisor_coverage
                SET scholarship_id = %s
                WHERE scholarship_id = %s
            """, (canonical_id, duplicate_id))
            populated_db.commit()
            # If we get here, the UPDATE succeeded - this is a FAILURE
            pytest.fail(
                f"UNIQUE constraint violation expected when reassigning "
                f"coverage from duplicate {duplicate_id} to canonical {canonical_id}, "
                f"but UPDATE succeeded"
            )
        except psycopg2.IntegrityError as e:
            collision_detected = True
            assert "unique" in str(e).lower() or "duplicate key" in str(e).lower(), \
                f"Expected UNIQUE violation, got: {e}"
            populated_db.rollback()

    assert collision_detected, "UNIQUE collision should have been detected"

    # Verify no rows were actually reassigned
    dup_coverage_after = get_coverage_row_for_scholarship(populated_db, duplicate_id)
    canon_coverage_after = get_coverage_row_for_scholarship(populated_db, canonical_id)
    assert dup_coverage_after is not None, "Duplicate coverage row should still exist"
    assert canon_coverage_after is not None, "Canonical coverage row should still exist"


def test_idempotent_archive(populated_db: PgConnection):
    """Test that re-running archive on already-archived duplicate affects 0 rows."""
    duplicate_id = 753

    # First archive
    with populated_db.cursor() as cur:
        cur.execute("""
            UPDATE scholarships
            SET is_archived = TRUE,
                archived_at = COALESCE(archived_at, %s),
                archived_reason = %s
            WHERE id = %s AND is_archived = FALSE
        """, (datetime.utcnow(), "Archive-only test", duplicate_id))
        first_rows = cur.rowcount
        populated_db.commit()

    assert first_rows == 1, f"First archive should affect 1 row, got {first_rows}"

    # Second archive - should affect 0 rows (idempotent)
    with populated_db.cursor() as cur:
        cur.execute("""
            UPDATE scholarships
            SET is_archived = TRUE,
                archived_at = COALESCE(archived_at, %s),
                archived_reason = %s
            WHERE id = %s AND is_archived = FALSE
        """, (datetime.utcnow(), "Archive-only test idempotent", duplicate_id))
        second_rows = cur.rowcount
        populated_db.commit()

    assert second_rows == 0, f"Second archive should affect 0 rows (idempotent), got {second_rows}"


def test_transaction_rollback(populated_db: PgConnection):
    """Test that a transaction rollback restores pre-archive state."""
    duplicate_id = 753

    # Record pre-state
    dup_archived_before = get_record_field(populated_db, duplicate_id, "is_archived")
    assert dup_archived_before is False, "Duplicate should not be archived before test"

    # Begin transaction, archive, then rollback
    with populated_db.cursor() as cur:
        cur.execute("""
            UPDATE scholarships
            SET is_archived = TRUE,
                archived_at = %s,
                archived_reason = %s
            WHERE id = %s AND is_archived = FALSE
        """, (datetime.utcnow(), "Rollback test", duplicate_id))

    # Verify within transaction (still open)
    dup_archived_during = get_record_field(populated_db, duplicate_id, "is_archived")
    assert dup_archived_during is True, "Duplicate should be archived during transaction"

    # Rollback
    populated_db.rollback()

    # Verify post-rollback state
    dup_archived_after = get_record_field(populated_db, duplicate_id, "is_archived")
    assert dup_archived_after is False, f"Duplicate should be unarchived after rollback, got {dup_archived_after}"


def test_fulbright_pair_untouched(populated_db: PgConnection):
    """Test that Fulbright pair (1217/1309) remains completely untouched."""
    canonical_id = FULBRIGHT_CANONICAL_ID
    duplicate_id = FULBRIGHT_DUPLICATE_ID

    canonical_status = get_record_field(populated_db, canonical_id, "status")
    duplicate_status = get_record_field(populated_db, duplicate_id, "status")
    canonical_archived = get_record_field(populated_db, canonical_id, "is_archived")
    duplicate_archived = get_record_field(populated_db, duplicate_id, "is_archived")
    canonical_url = get_record_field(populated_db, canonical_id, "official_source_url")
    duplicate_url = get_record_field(populated_db, duplicate_id, "official_source_url")

    assert canonical_status == "open", f"Fulbright canonical should be open, got {canonical_status}"
    assert duplicate_status == "open", f"Fulbright duplicate should be open, got {duplicate_status}"
    assert canonical_archived is False, f"Fulbright canonical should not be archived, got {canonical_archived}"
    assert duplicate_archived is False, f"Fulbright duplicate should not be archived, got {duplicate_archived}"
    assert canonical_url == "https://foreign.fulbrightonline.org", f"Fulbright canonical URL changed: {canonical_url}"
    assert duplicate_url == "https://fulbright.state.gov", f"Fulbright duplicate URL changed: {duplicate_url}"


def test_all_five_pairs_archived(populated_db: PgConnection):
    """Test archiving all 5 merge-ready duplicate pairs sequentially."""
    pairs = [
        (183, 753),
        (270, 1244),
        (271, 760),
        (285, 1277),
        (645, 654),
    ]

    total_before = count_records(populated_db)
    active_before = count_active_records(populated_db)
    archived_before = count_archived_records(populated_db)

    for canonical_id, duplicate_id in pairs:
        # Verify preconditions
        dup_status = get_record_field(populated_db, duplicate_id, "status")
        dup_archived = get_record_field(populated_db, duplicate_id, "is_archived")
        assert dup_status == "open", f"Duplicate {duplicate_id} should be open, got {dup_status}"
        assert dup_archived is False, f"Duplicate {duplicate_id} should not be archived, got {dup_archived}"

        # Archive
        with populated_db.cursor() as cur:
            cur.execute("""
                UPDATE scholarships
                SET is_archived = TRUE,
                    archived_at = COALESCE(archived_at, %s),
                    archived_reason = %s
                WHERE id = %s AND is_archived = FALSE
            """, (datetime.utcnow(), f"Duplicate of ID {canonical_id}; archive-only test", duplicate_id))
            rows_affected = cur.rowcount
        populated_db.commit()

        assert rows_affected == 1, f"Pair {canonical_id}/{duplicate_id}: expected 1 row affected, got {rows_affected}"

        # Verify duplicate is archived
        dup_archived_after = get_record_field(populated_db, duplicate_id, "is_archived")
        assert dup_archived_after is True, f"Duplicate {duplicate_id} should be archived after operation"

        # Verify canonical unchanged
        canon_archived_after = get_record_field(populated_db, canonical_id, "is_archived")
        assert canon_archived_after is False, f"Canonical {canonical_id} should not be archived, got {canon_archived_after}"

    # Post-state counts
    total_after = count_records(populated_db)
    active_after = count_active_records(populated_db)
    archived_after = count_archived_records(populated_db)

    assert total_after == total_before, f"Total count changed: {total_before} -> {total_after}"
    assert active_after == active_before - 5, f"Active count should decrease by 5: {active_before} -> {active_after}"
    assert archived_after == archived_before + 5, f"Archived count should increase by 5: {archived_before} -> {archived_after}"

    # Verify Fulbright still untouched
    fulbright_canonical_archived = get_record_field(populated_db, FULBRIGHT_CANONICAL_ID, "is_archived")
    fulbright_duplicate_archived = get_record_field(populated_db, FULBRIGHT_DUPLICATE_ID, "is_archived")
    assert fulbright_canonical_archived is False, "Fulbright canonical should not be archived"
    assert fulbright_duplicate_archived is False, "Fulbright duplicate should not be archived"


def test_coverage_rows_preserved_on_archive(populated_db: PgConnection):
    """Test that coverage rows are preserved (not deleted or reassigned) when duplicate is archived."""
    # Count coverage rows before
    coverage_before = count_coverage_rows(populated_db)

    # Archive duplicate ID 753
    with populated_db.cursor() as cur:
        cur.execute("""
            UPDATE scholarships
            SET is_archived = TRUE,
                archived_at = %s,
                archived_reason = %s
            WHERE id = 753 AND is_archived = FALSE
        """, (datetime.utcnow(), "Archive-only test coverage preservation"))
        populated_db.commit()

    # Count coverage rows after
    coverage_after = count_coverage_rows(populated_db)
    assert coverage_after == coverage_before, f"Coverage rows changed: {coverage_before} -> {coverage_after}"

    # Verify duplicate-side coverage row still exists (attached to archived duplicate)
    dup_coverage = get_coverage_row_for_scholarship(populated_db, 753)
    assert dup_coverage is not None, "Duplicate coverage row should still exist after archiving duplicate"

    # Verify canonical coverage row still exists
    canon_coverage = get_coverage_row_for_scholarship(populated_db, 183)
    assert canon_coverage is not None, "Canonical coverage row should still exist"


def test_projection_counts(populated_db: PgConnection):
    """Test that projected counts match expected values after all 5 archives."""
    # Archive all 5 merge-ready pairs
    pairs = [(183, 753), (270, 1244), (271, 760), (285, 1277), (645, 654)]

    for canonical_id, duplicate_id in pairs:
        with populated_db.cursor() as cur:
            cur.execute("""
                UPDATE scholarships
                SET is_archived = TRUE,
                    archived_at = COALESCE(archived_at, %s),
                    archived_reason = %s
                WHERE id = %s AND is_archived = FALSE
            """, (datetime.utcnow(), f"Duplicate of ID {canonical_id}; projection test", duplicate_id))
        populated_db.commit()

    # Verify final counts
    total = count_records(populated_db)
    active = count_active_records(populated_db)
    archived = count_archived_records(populated_db)

    assert total == 12, f"Total should remain 12, got {total}"
    assert active == 7, f"Active should be 7 (12 - 5 archives), got {active}"
    assert archived == 5, f"Archived should be 5, got {archived}"