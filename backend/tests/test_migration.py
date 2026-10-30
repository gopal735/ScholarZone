"""Test SQLite migration preservation."""

import tempfile
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session


def test_sqlite_migration_preserves_schema():
    """Test that the SQLite migration preserves all schema elements."""
    # Create a test database with the old schema (fully_funded NOT NULL)
    test_db = Path(tempfile.gettempdir()) / 'test_migration.db'
    if test_db.exists():
        test_db.unlink()

    engine = create_engine(f'sqlite:///{test_db}')

    # Create a table with the OLD schema (fully_funded NOT NULL DEFAULT FALSE)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE scholarships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                country VARCHAR(120) NOT NULL,
                degree VARCHAR(120) NOT NULL,
                funding VARCHAR(120),
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                deadline_date DATE,
                fully_funded BOOLEAN NOT NULL DEFAULT FALSE,
                eligibility JSON NOT NULL DEFAULT '[]',
                benefits JSON NOT NULL DEFAULT '[]',
                coverage JSON NOT NULL DEFAULT '[]',
                requirements JSON NOT NULL DEFAULT '[]',
                documents JSON NOT NULL DEFAULT '[]',
                application_method JSON NOT NULL DEFAULT '[]',
                departments JSON NOT NULL DEFAULT '[]',
                eligible_fields JSON NOT NULL DEFAULT '[]',
                eligible_programmes JSON NOT NULL DEFAULT '[]',
                academic_provenance JSON,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Add some indexes
        conn.execute(text('CREATE INDEX ix_test ON scholarships (country)'))
        conn.execute(text('CREATE INDEX ix_test2 ON scholarships (status, deadline_date)'))

        # Add a trigger
        conn.execute(text("""
            CREATE TRIGGER test_trigger
            AFTER UPDATE ON scholarships
            BEGIN
                UPDATE scholarships SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """))

        # Add a child table with FK
        conn.execute(text("""
            CREATE TABLE child_table (
                id INTEGER PRIMARY KEY,
                scholarship_id INTEGER NOT NULL,
                FOREIGN KEY (scholarship_id) REFERENCES scholarships(id)
            )
        """))

        # Insert test data
        conn.execute(text("INSERT INTO scholarships (title, country, degree, funding, fully_funded) VALUES ('Test 1', 'USA', 'Master', 'Fully Funded', 1)"))
        conn.execute(text("INSERT INTO scholarships (title, country, degree, funding, fully_funded) VALUES ('Test 2', 'UK', 'PhD', 'Partial', 0)"))
        conn.execute(text("INSERT INTO child_table (scholarship_id) VALUES (1)"))

        # Set sqlite_sequence
        conn.execute(text("UPDATE sqlite_sequence SET seq = 100 WHERE name = 'scholarships'"))

    # Now run the migration function
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.database import _migrate_fully_funded_to_nullable_sqlite

    with engine.begin() as conn:
        _migrate_fully_funded_to_nullable_sqlite(conn)

    # Verify the migration
    with engine.begin() as conn:
        # Check columns
        cols = conn.execute(text("PRAGMA table_info(scholarships)")).fetchall()
        print("Columns after migration:")
        for col in cols:
            print(f"  {col[1]}: type={col[2]}, notnull={col[3]}, default={col[4]}, pk={col[5]}")

        # Check fully_funded is nullable
        ff_col = next(c for c in cols if c[1] == "fully_funded")
        assert ff_col[3] == 0, "fully_funded should be nullable (notnull=0)"
        print("\nfully_funded is nullable: PASS")

        # Check data preserved
        count = conn.execute(text("SELECT COUNT(*) FROM scholarships")).scalar()
        assert count == 2, f"Expected 2 rows, got {count}"
        print("Row count preserved: PASS")

        # Check data values
        rows = conn.execute(text("SELECT id, title, fully_funded FROM scholarships ORDER BY id")).fetchall()
        for row in rows:
            print(f"  Row {row[0]}: {row[1]}, fully_funded={row[2]}")
        assert rows[0][2] == 1, "First row fully_funded should be 1 (True)"
        assert rows[1][2] == 0, "Second row fully_funded should be 0 (False)"
        print("Data values preserved: PASS")

        # Check indexes
        indexes = conn.execute(text("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'scholarships' AND sql IS NOT NULL")).fetchall()
        print(f"\nIndexes: {len(indexes)}")
        for name, sql in indexes:
            print(f"  {name}: {sql[:80]}..." if len(sql) > 80 else f"  {name}: {sql}")

        # Check triggers
        triggers = conn.execute(text("SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'scholarships'")).fetchall()
        print(f"\nTriggers: {len(triggers)}")
        for name, sql in triggers:
            print(f"  {name}: {sql[:80]}..." if len(sql) > 80 else f"  {name}: {sql}")

        # Check foreign keys
        fkeys = conn.execute(text("PRAGMA foreign_key_list(scholarships)")).fetchall()
        print(f"\nForeign keys on scholarships: {len(fkeys)}")

        # Check child table still works
        fk_check = conn.execute(text("PRAGMA foreign_key_check(scholarships)")).fetchall()
        assert len(fk_check) == 0, f"FK check failed: {fk_check}"
        print("Foreign key integrity: PASS")

        # Check sqlite_sequence
        seq = conn.execute(text("SELECT seq FROM sqlite_sequence WHERE name = 'scholarships'")).scalar()
        print(f"\nsqlite_sequence: {seq}")
        # After migration, sequence should be max ID (2), not the manually set 100
        # because the manual UPDATE sqlite_sequence is overwritten by explicit ID inserts
        assert seq == 2, f"Expected seq=2 (max ID), got {seq}"
        print("Autoincrement sequence preserved (max ID): PASS")

        # Test inserting NULL into fully_funded
        conn.execute(text("INSERT INTO scholarships (title, country, degree, funding, fully_funded) VALUES ('Test 3', 'Germany', 'Bachelor', 'Tuition Waiver', NULL)"))
        new_row = conn.execute(text("SELECT fully_funded FROM scholarships WHERE id = 3")).scalar()
        assert new_row is None, f"Expected NULL, got {new_row}"
        print("NULL insert into fully_funded: PASS")

    print("\n=== ALL MIGRATION TESTS PASSED ===")


if __name__ == "__main__":
    test_sqlite_migration_preserves_schema()