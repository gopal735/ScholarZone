"""Neon PostgreSQL migration script for ScholarZone.

Validates and executes migration_export.sql against Neon,
then verifies row counts, sequences, and data integrity.

Usage:
    python neon_migrate.py --validate-only --non-interactive   # Safe validation
    python neon_migrate.py                                     # Full migration
"""

import argparse
import os
import re
import sys
import time

from sqlalchemy import create_engine, inspect, text


def get_connection_url() -> str:
    """Get Neon connection URL from environment."""
    url = os.getenv("SCHOLARZONE_DATABASE_URL")
    if not url:
        print("ERROR: SCHOLARZONE_DATABASE_URL environment variable is not set.")
        print("Set it with: $env:SCHOLARZONE_DATABASE_URL=\"postgresql+psycopg://...\"")
        sys.exit(1)
    return url


def connect(url: str):
    """Create engine and test connection."""
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    engine = create_engine(url, pool_pre_ping=True, client_encoding="UTF8")
    with engine.connect() as conn:
        conn.execute(text("SET client_encoding = 'UTF8'"))
        server_enc = conn.execute(text("SHOW server_encoding")).scalar()
        client_enc = conn.execute(text("SHOW client_encoding")).scalar()
        print(f"Server encoding: {server_enc}")
        print(f"Client encoding: {client_enc}")
        version = conn.execute(text("SELECT version()")).scalar()
        print(f"Connected to: {version[:60]}...")
    return engine


def verify_schema(engine) -> list[str]:
    """Verify required tables exist. Returns list of found table names."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    required = [
        "scholarships",
        "scholarship_verification_history",
        "scholarship_reviews",
    ]
    missing = [t for t in required if t not in tables]
    if missing:
        print(f"ERROR: Missing tables: {missing}")
        return []
    print(f"Schema verified: {len(tables)} tables found: {tables}")
    return tables


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL into individual statements, respecting string literals and comments.

    Single-pass state machine that correctly handles:
    - Single-quoted strings with '' escaping (SQL standard)
    - Double-quoted identifiers with "" escaping (SQL standard)
    - Line comments (-- ...)
    - Block comments (/* ... */)
    - Semicolons inside string literals are NOT statement terminators

    Strips leading/trailing whitespace and removes empty statements.
    Returns a list of statement strings (without trailing semicolons).
    """
    statements = []
    buf = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    i = 0

    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            buf.append(char)
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buf.append(char)
            if char == "*" and next_char == "/":
                buf.append(next_char)
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_single_quote:
            buf.append(char)
            if char == "'":
                if next_char == "'":
                    # Escaped single quote: append the second quote and stay in string
                    buf.append(next_char)
                    i += 2
                    continue
                # Closing single quote
                in_single_quote = False
            i += 1
            continue

        if in_double_quote:
            buf.append(char)
            if char == '"':
                if next_char == '"':
                    # Escaped double quote: append second quote and stay in identifier
                    buf.append(next_char)
                    i += 2
                    continue
                # Closing double quote
                in_double_quote = False
            i += 1
            continue

        # Not in any quoted/comment context
        if char == "-" and next_char == "-":
            buf.append("--")
            in_line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            buf.append("/*")
            in_block_comment = True
            i += 2
            continue

        if char == "'":
            in_single_quote = True
            buf.append(char)
            i += 1
            continue

        if char == '"':
            in_double_quote = True
            buf.append(char)
            i += 1
            continue

        if char == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(char)
        i += 1

    # Don't forget the last statement
    stmt = "".join(buf).strip()
    if stmt:
        statements.append(stmt)

    return statements


def _strip_leading_comments(stmt: str) -> str:
    """Strip leading SQL line comments (--) and blank lines from a statement.

    Returns the remaining content with leading comments removed, so the first
    actual SQL token can be identified even when a comment header precedes it.
    """
    lines = stmt.split("\n")
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()
        if stripped.startswith("--") or stripped == "":
            idx += 1
        else:
            break
    return "\n".join(lines[idx:]).strip()


def filter_migration_statements(statements: list[str]) -> list[str]:
    """Filter out BEGIN/COMMIT/transaction-control statements.

    SQLAlchemy's engine.begin() manages the transaction.
    The migration file has embedded BEGIN; and COMMIT; which would
    interfere with SQLAlchemy's transaction context manager.

    Leading SQL comment lines (-- ...) are stripped before checking the
    first token, so that statements like '-- header\nBEGIN' are still
    recognized as transaction-control and filtered out.
    """
    tx_keywords = {"BEGIN", "COMMIT", "ROLLBACK", "START", "SAVEPOINT", "RELEASE", "SET TRANSACTION"}
    filtered = []
    for stmt in statements:
        code_part = _strip_leading_comments(stmt)
        first_token = code_part.split(None, 1)[0].upper().rstrip(";") if code_part.split() else ""
        if first_token in tx_keywords:
            print(f"  Skipping transaction control statement: {stmt[:50]}")
            continue
        filtered.append(stmt)
    return filtered


def run_migration(engine, sql_file: str) -> bool:
    """Run migration SQL file inside a SQLAlchemy-managed transaction.

    - Reads the file as UTF-8
    - Sets client_encoding to UTF8 on the connection
    - Splits SQL into statements using a proper parser (not naive split)
    - Strips embedded BEGIN/COMMIT (SQLAlchemy manages the transaction)
    - Executes all statements inside engine.begin() (atomic)
    - If any statement fails, the entire transaction rolls back
    """
    with open(sql_file, "r", encoding="utf-8") as f:
        sql = f.read()

    print(f"Executing migration from {sql_file}...")
    print(f"  File size: {len(sql):,} chars")

    # Split into individual statements using safe parser
    all_statements = split_sql_statements(sql)
    print(f"  Parsed {len(all_statements)} SQL statements")

    # Filter out transaction control statements (BEGIN/COMMIT)
    statements = filter_migration_statements(all_statements)
    print(f"  Will execute {len(statements)} data statements")

    start = time.time()

    try:
        with engine.begin() as conn:
            # Ensure UTF-8 encoding
            conn.execute(text("SET client_encoding = 'UTF8'"))

            # Set search_path to public (default)
            conn.execute(text("SET search_path = public"))

            for i, stmt in enumerate(statements, 1):
                conn.execute(text(stmt))
                if i % 50 == 0:
                    print(f"  Executed {i}/{len(statements)} statements...")

    except Exception as e:
        elapsed = time.time() - start
        print(f"\nMIGRATION FAILED after {elapsed:.1f}s")
        print(f"Error: {e}")
        print("Transaction rolled back — no partial data written.")
        raise

    elapsed = time.time() - start
    print(f"Migration completed in {elapsed:.1f}s ({len(statements)} statements)")
    return True


def discover_sequences(engine) -> list[tuple[str, str]]:
    """Dynamically discover sequences for integer primary key columns.

    Uses pg_get_serial_sequence() to find the correct sequence name
    for each table's id column. This avoids hardcoding sequence names
    that may differ across PostgreSQL versions (e.g. <name>_id_seq vs
    <name>_<column>_seq).
    """
    inspector = inspect(engine)
    if inspector.dialect.name != "postgresql":
        print("  Not a PostgreSQL dialect — sequence discovery skipped")
        return []

    results = []
    with engine.connect() as conn:
        conn.execute(text("SET client_encoding = 'UTF8'"))
        for table in ["scholarships", "scholarship_reviews", "scholarship_verification_history"]:
            seq_name = conn.execute(
                text(f"SELECT pg_get_serial_sequence('{table}', 'id')")
            ).scalar()
            if seq_name:
                results.append((table, seq_name))
                print(f"  Found sequence: {table} -> {seq_name}")
            else:
                print(f"  No sequence found for {table}.id")
    return results


def synchronize_sequences(engine) -> bool:
    """Synchronize PostgreSQL sequences after explicit ID inserts.

    After importing rows with explicit IDs, the sequence must be
    advanced to MAX(id) so the next auto-generated INSERT doesn't
    collide with the highest imported ID.
    """
    sequences = discover_sequences(engine)

    if not sequences:
        print("No sequences to synchronize")
        return True

    with engine.begin() as conn:
        conn.execute(text("SET client_encoding = 'UTF8'"))
        for table, seq_name in sequences:
            # Verify rows exist before setting sequence
            max_id = conn.execute(text(f"SELECT MAX(id) FROM {table}")).scalar()
            if max_id is None:
                print(f"  {seq_name}: no rows in {table}, skipping")
                continue

            # setval with is_called=true means next nextval returns max_id + 1
            conn.execute(text(f"SELECT setval('{seq_name}', {max_id}, true)"))
            last_val = conn.execute(text(f"SELECT last_value FROM {seq_name}")).scalar()
            print(f"  {seq_name} set to {last_val} (next insert will use {last_val + 1})")

    return True


def confirm_empty(engine, non_interactive: bool = False) -> bool:
    """Confirm database is empty of scholarship data."""
    with engine.connect() as conn:
        conn.execute(text("SET client_encoding = 'UTF8'"))
        tables = ["scholarships", "scholarship_verification_history", "scholarship_reviews"]
        counts = {}
        for table in tables:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = result.scalar()

        total = sum(counts.values())
        print(f"Current row counts: {counts} (total: {total})")

        if total > 0:
            print("WARNING: Database is not empty!")

            # Show the existing rows for inspection
            rows = conn.execute(
                text(
                    "SELECT id, title, official_source_url, verification_status, "
                    "created_at, updated_at FROM scholarships ORDER BY id"
                )
            ).fetchall()
            for row in rows:
                print(
                    f"  Existing: id={row[0]}, title={row[1]}, "
                    f"url={row[2][:50] if row[2] else None}, "
                    f"status={row[3]}, created={row[4]}, updated={row[5]}"
                )

            if non_interactive:
                print("NON-INTERACTIVE MODE: Skipping migration to avoid data loss.")
                print("Clean the database first, then re-run.")
                return False

            response = input("Continue anyway? This will fail on duplicate IDs. (yes/no): ")
            if response.lower() != "yes":
                return False

        return True


def validate(engine) -> dict:
    """Validate migration results."""
    results = {}

    with engine.connect() as conn:
        conn.execute(text("SET client_encoding = 'UTF8'"))

        # Row counts
        for table in ["scholarships", "scholarship_verification_history", "scholarship_reviews"]:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            results[table] = result.scalar()

        # Max scholarship ID
        result = conn.execute(text("SELECT MAX(id) FROM scholarships"))
        results["max_scholarship_id"] = result.scalar()

        # Next sequence value
        result = conn.execute(text("SELECT pg_get_serial_sequence('scholarships', 'id')"))
        seq_name = result.scalar()
        if seq_name:
            result = conn.execute(text(f"SELECT last_value FROM {seq_name}"))
            results["scholarships_seq"] = result.scalar()
            result = conn.execute(text(f"SELECT last_value FROM {seq_name}"))
            # next would be last_value + 1

        # Test records (should be 0)
        result = conn.execute(
            text("SELECT COUNT(*) FROM scholarships WHERE title LIKE 'Test%' OR title LIKE '%test%'")
        )
        results["test_records"] = result.scalar()

        # Duplicate official_source_url (should be 0)
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "SELECT official_source_url FROM scholarships "
                "WHERE official_source_url IS NOT NULL "
                "GROUP BY official_source_url HAVING COUNT(*) > 1) AS dupes"
            )
        )
        results["duplicate_urls"] = result.scalar()

        # Foreign key integrity: reviews referencing non-existent scholarships
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM scholarship_reviews r "
                "LEFT JOIN scholarships s ON r.scholarship_id = s.id "
                "WHERE s.id IS NULL"
            )
        )
        results["orphaned_reviews"] = result.scalar()

        # Foreign key integrity: history referencing non-existent scholarships
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM scholarship_verification_history h "
                "LEFT JOIN scholarships s ON h.scholarship_id = s.id "
                "WHERE s.id IS NULL"
            )
        )
        results["orphaned_history"] = result.scalar()

        # Critical records preserved (EMJM, ICCR, DAAD)
        result = conn.execute(
            text("SELECT COUNT(*) FROM scholarships WHERE id IN (1, 2, 3)")
        )
        results["critical_records"] = result.scalar()

        # Country distribution
        result = conn.execute(
            text(
                "SELECT country, COUNT(*) FROM scholarships GROUP BY country "
                "ORDER BY COUNT(*) DESC LIMIT 10"
            )
        )
        results["top_countries"] = result.fetchall()

    return results


def main():
    parser = argparse.ArgumentParser(description="ScholarZone Neon Migration")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only verify connection and schema, do not import data",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip interactive prompts (for CI/automation)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ScholarZone Neon Migration")
    if args.validate_only:
        print("MODE: VALIDATION ONLY (no data will be modified)")
    print("=" * 60)

    # Step 1: Get connection
    url = get_connection_url()
    engine = connect(url)

    # Step 2: Verify schema
    print("\n--- Schema Verification ---")
    tables = verify_schema(engine)
    if not tables:
        sys.exit(1)

    # Step 3: Confirm empty / show current state
    print("\n--- Empty State Check ---")
    if not confirm_empty(engine, non_interactive=args.non_interactive):
        if not args.validate_only:
            sys.exit(1)

    if args.validate_only:
        print("\n" + "=" * 60)
        print("VALIDATION COMPLETE - No data was modified")
        print("VERDICT: A) CONNECTION AND SCHEMA OK - READY FOR MIGRATION")
        print("=" * 60)
        engine.dispose()
        sys.exit(0)

    # Step 4: Run migration
    print("\n--- Migration ---")
    sql_file = os.path.join(os.path.dirname(__file__), "migration_export.sql")
    try:
        if not run_migration(engine, sql_file):
            sys.exit(1)
    except Exception:
        print("\nMigration failed. Transaction rolled back.")
        engine.dispose()
        sys.exit(1)

    # Step 5: Synchronize sequences
    print("\n--- Sequence Synchronization ---")
    synchronize_sequences(engine)

    # Step 6: Validate
    print("\n--- Validation ---")
    results = validate(engine)

    print(f"\nRow counts:")
    print(f"  scholarships: {results['scholarships']}")
    print(f"  scholarship_verification_history: {results['scholarship_verification_history']}")
    print(f"  scholarship_reviews: {results['scholarship_reviews']}")
    print(f"  total: {sum(results[t] for t in ['scholarships', 'scholarship_verification_history', 'scholarship_reviews'])}")
    print(f"\nMax scholarship ID: {results['max_scholarship_id']}")
    if "scholarships_seq" in results:
        print(f"  next sequence value: {results['scholarships_seq'] + 1}")
    print(f"Test records: {results['test_records']}")
    print(f"Duplicate URLs: {results['duplicate_urls']}")
    print(f"Orphaned reviews: {results['orphaned_reviews']}")
    print(f"Orphaned history: {results['orphaned_history']}")
    print(f"Critical records (1,2,3): {results['critical_records']}")
    print(f"\nTop countries:")
    for country, count in results["top_countries"]:
        print(f"  {country}: {count}")

    # Final verdict
    expected = {
        "scholarships": 303,
        "scholarship_verification_history": 6,
        "scholarship_reviews": 625,
    }

    all_ok = (
        results["scholarships"] == expected["scholarships"]
        and results["scholarship_verification_history"] == expected["scholarship_verification_history"]
        and results["scholarship_reviews"] == expected["scholarship_reviews"]
        and results["max_scholarship_id"] == 304
        and results["test_records"] == 0
        and results["duplicate_urls"] == 0
        and results["orphaned_reviews"] == 0
        and results["orphaned_history"] == 0
        and results["critical_records"] == 3
    )

    print("\n" + "=" * 60)
    if all_ok:
        print("VERDICT: A) NEON MIGRATION COMPLETE AND VALIDATED")
    else:
        print("VERDICT: B) MIGRATION BLOCKED — validation failed")
        if results["scholarships"] != expected["scholarships"]:
            print(f"  - Expected {expected['scholarships']} scholarships, got {results['scholarships']}")
        if results["scholarship_verification_history"] != expected["scholarship_verification_history"]:
            print(f"  - Expected {expected['scholarship_verification_history']} history, got {results['scholarship_verification_history']}")
        if results["scholarship_reviews"] != expected["scholarship_reviews"]:
            print(f"  - Expected {expected['scholarship_reviews']} reviews, got {results['scholarship_reviews']}")
        if results["max_scholarship_id"] != 304:
            print(f"  - Expected max ID 304, got {results['max_scholarship_id']}")
    print("=" * 60)

    engine.dispose()


if __name__ == "__main__":
    main()
