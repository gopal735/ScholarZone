#!/usr/bin/env python3
"""Test PostgreSQL migration for fully_funded column.

This test verifies that the _upgrade_postgresql_schema migration correctly
handles the fully_funded column transition from NOT NULL DEFAULT FALSE
to nullable with no default, preserving historical data.

Supports both SQLite (local testing) and PostgreSQL (CI).
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text, Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

# Add backend to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import _upgrade_maintenance_slot_schema, _upgrade_postgresql_schema
from app.supervisor_ddl import create_table_statements, index_statements, REQUIRED_NEW_TABLES

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id = Column(Integer, primary_key=True)
    email = Column(String(254), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class Scholarship(Base):
    """Legacy scholarships table with fully_funded NOT NULL DEFAULT FALSE."""
    __tablename__ = "scholarships"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    country = Column(String(120))
    degree = Column(String(64))
    funding = Column(String(64))
    official_source = Column(String(255))
    official_source_url = Column(String(2048))
    application_link = Column(String(2048))
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_status = Column(String(32), nullable=False, default="unverified")
    status = Column(String(32), nullable=False, default="unknown")
    deadline_precision = Column(String(16), nullable=False, default="unknown")
    deadline_date = Column(DateTime(timezone=True))  # Required for indexes
    # Legacy fully_funded: NOT NULL DEFAULT FALSE
    fully_funded = Column(Boolean, nullable=False, default=False, server_default="false")


class MaintenanceRun(Base):
    __tablename__ = "maintenance_runs"

    id = Column(Integer, primary_key=True)
    slot_name = Column(String(64))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(32))
    details = Column(String(1000))


def is_postgresql(engine):
    """Check if the engine is PostgreSQL."""
    return engine.dialect.name == "postgresql"


def is_sqlite(engine):
    """Check if the engine is SQLite."""
    return engine.dialect.name == "sqlite"


def create_legacy_schema(engine):
    """Create the legacy schema with fully_funded NOT NULL DEFAULT FALSE."""
    Base.metadata.create_all(bind=engine)
    
    # Verify the legacy column definition
    with engine.begin() as conn:
        if is_sqlite(engine):
            result = conn.execute(text("PRAGMA table_info(scholarships)")).fetchall()
            fully_funded_col = None
            for col in result:
                if col[1] == 'fully_funded':
                    fully_funded_col = col
                    break
            assert fully_funded_col is not None, "fully_funded column not found"
            # SQLite: cid, name, type, notnull, dflt_value, pk
            assert fully_funded_col[3] == 1, f"fully_funded should be NOT NULL (notnull=1), got {fully_funded_col[3]}"
            dflt_val = str(fully_funded_col[4]).strip("'").lower()
            assert dflt_val in ('0', 'false', '0.0'), f"fully_funded should have DEFAULT FALSE, got {fully_funded_col[4]}"
            print(f"[PASS] Legacy fully_funded column (SQLite): notnull={fully_funded_col[3]}, dflt_value={fully_funded_col[4]}")
        elif is_postgresql(engine):
            cols = inspect(conn).get_columns('scholarships')
            for col in cols:
                if col['name'] == 'fully_funded':
                    assert col['nullable'] is False, f"fully_funded should be NOT NULL, got nullable={col['nullable']}"
                    assert col['default'] is not None, f"fully_funded should have DEFAULT, got {col['default']}"
                    print(f"[PASS] Legacy fully_funded column (PostgreSQL): nullable={col['nullable']}, default={col['default']}")
                    break


def insert_historical_data(engine):
    """Insert historical True/False rows."""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        scholarships_data = [
            {"title": "Full Funded Scholarship", "country": "Germany", "fully_funded": True},
            {"title": "Partial Funded Scholarship", "country": "France", "fully_funded": False},
            {"title": "Another Full Funded", "country": "USA", "fully_funded": True},
            {"title": "No Funding Info", "country": "UK", "fully_funded": False},
        ]
        for data in scholarships_data:
            sch = Scholarship(**data)
            session.add(sch)
        session.commit()
        
        count = session.query(Scholarship).count()
        true_count = session.query(Scholarship).filter(Scholarship.fully_funded == True).count()
        false_count = session.query(Scholarship).filter(Scholarship.fully_funded == False).count()
        print(f"[PASS] Inserted {count} historical rows: {true_count} TRUE, {false_count} FALSE")
        return count, true_count, false_count
    finally:
        session.close()


def run_migration(engine):
    """Run the migration."""
    # Run maintenance slot schema upgrade (idempotent)
    _upgrade_maintenance_slot_schema(engine)
    
    # Create supervisor tables
    with engine.begin() as conn:
        dialect = "postgresql" if is_postgresql(engine) else "sqlite"
        for statement in create_table_statements(dialect):
            conn.execute(text(statement))
        for statement in index_statements():
            conn.execute(text(statement))
    
    # For PostgreSQL, run the actual migration that alters fully_funded column
    if is_postgresql(engine):
        _upgrade_postgresql_schema(engine)
    
    # Verify fully_funded column state after migration
    with engine.begin() as conn:
        if is_sqlite(engine):
            result = conn.execute(text("PRAGMA table_info(scholarships)")).fetchall()
            fully_funded_col = None
            for col in result:
                if col[1] == 'fully_funded':
                    fully_funded_col = col
                    break
            assert fully_funded_col is not None, "fully_funded column not found after migration"
            print(f"[PASS] After migration fully_funded (SQLite): notnull={fully_funded_col[3]}, dflt_value={fully_funded_col[4]}")
        elif is_postgresql(engine):
            cols = inspect(conn).get_columns('scholarships')
            for col in cols:
                if col['name'] == 'fully_funded':
                    assert col['nullable'] is True, f"fully_funded should be nullable after migration, got nullable={col['nullable']}"
                    # Default should be removed
                    print(f"[PASS] After migration fully_funded (PostgreSQL): nullable={col['nullable']}, default={col['default']}")
                    break


def verify_historical_data_preserved(engine, expected_count, expected_true, expected_false):
    """Verify historical rows are preserved after migration."""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        count = session.query(Scholarship).count()
        true_count = session.query(Scholarship).filter(Scholarship.fully_funded == True).count()
        false_count = session.query(Scholarship).filter(Scholarship.fully_funded == False).count()
        
        assert count == expected_count, f"Row count changed: {count} != {expected_count}"
        assert true_count == expected_true, f"TRUE count changed: {true_count} != {expected_true}"
        assert false_count == expected_false, f"FALSE count changed: {false_count} != {expected_false}"
        print(f"[PASS] Historical data preserved: {count} total, {true_count} TRUE, {false_count} FALSE")
    finally:
        session.close()


def test_true_false_inserts(engine):
    """Test that TRUE and FALSE can be inserted after migration."""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        sch1 = Scholarship(title="Test TRUE", country="Test", fully_funded=True)
        session.add(sch1)
        sch2 = Scholarship(title="Test FALSE", country="Test", fully_funded=False)
        session.add(sch2)
        session.commit()
        
        t = session.query(Scholarship).filter(Scholarship.title == "Test TRUE").first()
        f = session.query(Scholarship).filter(Scholarship.title == "Test FALSE").first()
        assert t is not None and t.fully_funded == True, "TRUE insert failed"
        assert f is not None and f.fully_funded == False, "FALSE insert failed"
        print("[PASS] TRUE/FALSE inserts work after migration")
    finally:
        session.close()


def test_null_insert(engine):
    """Test that NULL can be inserted and retrieved as NULL after migration (PostgreSQL only)."""
    if not is_postgresql(engine):
        print("[SKIP] NULL insert test only for PostgreSQL")
        return
    
    # Use raw SQL to bypass ORM server_default and test actual database behavior
    with engine.begin() as conn:
        # Insert with explicit NULL for fully_funded
        conn.execute(text("""
            INSERT INTO scholarships (title, country, fully_funded)
            VALUES ('Test NULL Insert', 'Test', NULL)
        """))
        
        # Verify the row was inserted and fully_funded is actually NULL
        result = conn.execute(text("""
            SELECT id, title, fully_funded FROM scholarships 
            WHERE title = 'Test NULL Insert'
        """)).fetchone()
        
        assert result is not None, "NULL insert failed - row not found"
        assert result[2] is None, f"Expected NULL for fully_funded, got {result[2]}"
        print(f"[PASS] NULL insert and retrieval verified: id={result[0]}, fully_funded={result[2]}")
        
        # Also test inserting with DEFAULT keyword (should also be NULL since default was dropped)
        conn.execute(text("""
            INSERT INTO scholarships (title, country, fully_funded)
            VALUES ('Test DEFAULT', 'Test', DEFAULT)
        """))
        
        result = conn.execute(text("""
            SELECT id, title, fully_funded FROM scholarships 
            WHERE title = 'Test DEFAULT'
        """)).fetchone()
        
        assert result is not None, "DEFAULT insert failed - row not found"
        # After migration, DEFAULT should be NULL (no default)
        assert result[2] is None, f"Expected NULL for fully_funded with DEFAULT, got {result[2]}"
        print(f"[PASS] DEFAULT insert resolves to NULL: id={result[0]}, fully_funded={result[2]}")


def test_idempotency(engine):
    """Test that running migration twice is a no-op."""
    _upgrade_maintenance_slot_schema(engine)
    
    with engine.begin() as conn:
        dialect = "postgresql" if is_postgresql(engine) else "sqlite"
        for statement in create_table_statements(dialect):
            conn.execute(text(statement))
        for statement in index_statements():
            conn.execute(text(statement))
    
    if is_postgresql(engine):
        _upgrade_postgresql_schema(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        count = session.query(Scholarship).count()
        true_count = session.query(Scholarship).filter(Scholarship.fully_funded == True).count()
        false_count = session.query(Scholarship).filter(Scholarship.fully_funded == False).count()
        print(f"[PASS] Idempotency: {count} total, {true_count} TRUE, {false_count} FALSE")
    finally:
        session.close()


def test_supervisor_tables_created(engine):
    """Verify all required supervisor tables are created."""
    with engine.begin() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        for required_table in REQUIRED_NEW_TABLES:
            assert required_table in tables, f"Required table {required_table} not created"
        
        print(f"[PASS] All {len(REQUIRED_NEW_TABLES)} supervisor tables created: {', '.join(REQUIRED_NEW_TABLES)}")


def main():
    """Run the full migration test."""
    print("=" * 60)
    print("PostgreSQL Migration Test - fully_funded Column")
    print("=" * 60)
    
    # Use database URL from environment or default to SQLite
    db_url = os.environ.get("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")
    print(f"Testing against: {db_url.split('@')[0]}...")
    
    # For PostgreSQL, use psycopg v3 driver
    if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        print(f"Using psycopg v3 driver: {db_url.split('@')[0]}...")
    
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
    
    try:
        # Step 1: Create legacy schema
        print("\n[1] Creating legacy schema...")
        create_legacy_schema(engine)
        
        # Step 2: Insert historical data
        print("\n[2] Inserting historical data...")
        count, true_count, false_count = insert_historical_data(engine)
        
        # Step 3: Run migration
        print("\n[3] Running migration...")
        run_migration(engine)
        
        # Step 4: Verify historical data preserved
        print("\n[4] Verifying historical data preserved...")
        verify_historical_data_preserved(engine, count, true_count, false_count)
        
        # Step 5: Test TRUE/FALSE inserts
        print("\n[5] Testing TRUE/FALSE inserts...")
        test_true_false_inserts(engine)
        
        # Step 6: Test NULL insert (PostgreSQL only)
        if is_postgresql(engine):
            print("\n[6] Testing NULL insert (PostgreSQL)...")
            test_null_insert(engine)
        
        # Step 7: Test idempotency
        print("\n[7] Testing idempotency...")
        test_idempotency(engine)
        
        # Step 8: Verify supervisor tables
        print("\n[8] Verifying supervisor tables...")
        test_supervisor_tables_created(engine)
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())