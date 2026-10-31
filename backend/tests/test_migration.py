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

    # Create a table with the OLD schema matching production (fully_funded NOT NULL DEFAULT FALSE)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE scholarships (
id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                is_archived BOOLEAN NOT NULL,
                archived_at DATETIME,
                archived_reason VARCHAR(120),
                auto_delete_candidate_since DATETIME,
                deletion_protected BOOLEAN NOT NULL,
                is_verified BOOLEAN NOT NULL,
                last_verified_at DATE,
                last_verified_date DATE,
                verification_status VARCHAR(20) NOT NULL,
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
                image_verified_at DATETIME,
                image_alt_text VARCHAR(512),
                image_evaluation_status VARCHAR(32),
                image_evaluated_at DATETIME,
                eligibility JSON NOT NULL,
                eligibility_summary TEXT,
                benefits JSON NOT NULL,
                coverage JSON NOT NULL,
                requirements JSON NOT NULL,
                documents JSON NOT NULL,
                english_requirement TEXT,
                application_method JSON NOT NULL,
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                departments JSON NOT NULL DEFAULT '[]',
                eligible_fields JSON NOT NULL DEFAULT '[]',
                eligible_programmes JSON NOT NULL DEFAULT '[]',
                academic_provenance JSON,
                CONSTRAINT uq_scholarships_official_source_url UNIQUE (official_source_url)
            )
        """))

        # Add some indexes matching production
        conn.execute(text('CREATE UNIQUE INDEX ix_scholarships_legacy_id ON scholarships (legacy_id)'))
        conn.execute(text('CREATE INDEX ix_scholarships_title ON scholarships (title)'))
        conn.execute(text('CREATE INDEX ix_scholarships_updated_at ON scholarships (updated_at)'))
        conn.execute(text('CREATE INDEX ix_scholarships_deadline_date ON scholarships (deadline_date)'))
        conn.execute(text('CREATE INDEX ix_scholarships_degree ON scholarships (degree)'))
        conn.execute(text('CREATE INDEX ix_scholarships_country_degree ON scholarships (country, degree)'))
        conn.execute(text('CREATE INDEX ix_scholarships_is_archived ON scholarships (is_archived)'))
        conn.execute(text('CREATE INDEX ix_scholarships_country ON scholarships (country)'))
        conn.execute(text('CREATE INDEX ix_scholarships_status ON scholarships (status)'))
        conn.execute(text('CREATE INDEX ix_scholarships_status_deadline ON scholarships (status, deadline_date)'))
        conn.execute(text('CREATE INDEX ix_scholarships_auto_delete ON scholarships (status, is_archived, deletion_protected)'))

        # Add a trigger matching production pattern
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

        # Insert test data with all required NOT NULL columns
        conn.execute(text("""
            INSERT INTO scholarships (
                id, legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                1, NULL, 'Test 1', 'USA', 'Master', 'Fully Funded', NULL,
                NULL, NULL, 'unknown', 'open',
                0, 0, 0, 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', 1
            )
        """))
        conn.execute(text("""
            INSERT INTO scholarships (
                id, legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                2, NULL, 'Test 2', 'UK', 'PhD', 'Partial', NULL,
                NULL, NULL, 'unknown', 'open',
                0, 0, 0, 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', 0
            )
        """))
        conn.execute(text("INSERT INTO child_table (scholarship_id) VALUES (1)"))

        # Set sqlite_sequence to a value greater than max ID
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
        
        # Verify key indexes exist
        index_names = [idx[0] for idx in indexes]
        assert "ix_scholarships_legacy_id" in index_names, "Unique index on legacy_id missing"
        assert "ix_scholarships_title" in index_names, "Index on title missing"
        print("Key indexes preserved: PASS")

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

        # Check sqlite_sequence is preserved (should be 100, the high-water mark)
        seq = conn.execute(text("SELECT seq FROM sqlite_sequence WHERE name = 'scholarships'")).scalar()
        print(f"\nsqlite_sequence: {seq}")
        assert seq == 100, f"Expected seq=100 (high-water mark), got {seq}"
        print("Autoincrement high-water mark preserved: PASS")

        # Test inserting NULL into fully_funded
        conn.execute(text("""
            INSERT INTO scholarships (
                id, legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                3, NULL, 'Test 3', 'Germany', 'Bachelor', 'Tuition Waiver', NULL,
                NULL, NULL, 'unknown', 'open',
                0, 0, 0, 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', NULL
            )
        """))
        new_row = conn.execute(text("SELECT fully_funded FROM scholarships WHERE id = 3")).scalar()
        assert new_row is None, f"Expected NULL, got {new_row}"
        print("NULL insert into fully_funded: PASS")

        # Test inserting True into fully_funded
        conn.execute(text("""
            INSERT INTO scholarships (
                id, legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                4, NULL, 'Test 4', 'France', 'Master', 'Full', NULL,
                NULL, NULL, 'unknown', 'open',
                0, 0, 0, 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', 1
            )
        """))
        new_row = conn.execute(text("SELECT fully_funded FROM scholarships WHERE id = 4")).scalar()
        assert new_row == 1, f"Expected 1, got {new_row}"
        print("True insert into fully_funded: PASS")

        # Test inserting False into fully_funded
        conn.execute(text("""
            INSERT INTO scholarships (
                id, legacy_id, title, country, degree, funding, description,
                deadline_date, deadline_display, deadline_precision, status,
                is_archived, deletion_protected, is_verified, verification_status,
                created_at, updated_at, eligibility, benefits, coverage,
                requirements, documents, application_method, departments,
                eligible_fields, eligible_programmes, fully_funded
            ) VALUES (
                5, NULL, 'Test 5', 'Spain', 'PhD', 'None', NULL,
                NULL, NULL, 'unknown', 'open',
                0, 0, 0, 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '[]', '[]', '[]',
                '[]', '[]', '[]', '[]', '[]', '[]', 0
            )
        """))
        new_row = conn.execute(text("SELECT fully_funded FROM scholarships WHERE id = 5")).scalar()
        assert new_row == 0, f"Expected 0, got {new_row}"
        print("False insert into fully_funded: PASS")

        # Verify UNIQUE constraint on official_source_url still exists
        create_sql = conn.execute(text('SELECT sql FROM sqlite_master WHERE type = "table" AND name = "scholarships"')).fetchone()[0]
        assert "UNIQUE (official_source_url)" in create_sql, "UNIQUE constraint on official_source_url missing"
        print("UNIQUE constraint preserved: PASS")

        # Verify child table FK still works
        fk_check = conn.execute(text("PRAGMA foreign_key_check(child_table)")).fetchall()
        assert len(fk_check) == 0, f"Child table FK check failed: {fk_check}"
        print("Child table FK preserved: PASS")

        # Test idempotency - run migration again
        from app.database import _migrate_fully_funded_to_nullable_sqlite
        _migrate_fully_funded_to_nullable_sqlite(conn)
        print("Idempotent migration: PASS")

    print("\n=== ALL MIGRATION TESTS PASSED ===")


if __name__ == "__main__":
    test_sqlite_migration_preserves_schema()