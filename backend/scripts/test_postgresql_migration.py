#!/usr/bin/env python3
"""
PostgreSQL Migration Integration Test

Tests the _upgrade_postgresql_schema migration on a real PostgreSQL database.
"""

import os
import sys

# Set up environment
os.environ['SCHOLARZONE_DATABASE_URL'] = 'postgresql://test:test@localhost:5432/scholarzone_test'
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import reset_database_connections, init_database, get_session_factory, _upgrade_postgresql_schema
from app.models import Scholarship
from sqlalchemy import create_engine, text, inspect


def test_postgresql_migration():
    """Test the PostgreSQL migration on a real PostgreSQL database."""
    print("=" * 60)
    print("PostgreSQL Migration Integration Test")
    print("=" * 60)
    
    # Reset and initialize
    reset_database_connections()
    init_database()
    
    factory = get_session_factory()
    
    # 1. Check initial state - fully_funded should be NOT NULL DEFAULT FALSE
    print("\n1. Checking initial schema state...")
    with get_session_factory()() as session:
        cols = inspect(session.bind).get_columns('scholarships')
        for col in cols:
            if col['name'] == 'fully_funded':
                print(f"  Initial: {col}")
                assert col['nullable'] is False, 'fully_funded should be NOT NULL initially'
                assert col['default'] is not None, 'fully_funded should have DEFAULT initially'
                print("  ✓ Initial state: NOT NULL DEFAULT FALSE")
                break
    
    # 2. Run migration
    print("\n2. Running migration...")
    engine = create_engine('postgresql://test:test@localhost:5432/scholarzone_test')
    with engine.connect() as conn:
        _upgrade_postgresql_schema(conn)
        conn.commit()
    print("  ✓ Migration executed")
    
    # 3. Verify migration - fully_funded should be nullable
    print("\n3. Verifying migration...")
    with get_session_factory()() as session2:
        cols = inspect(session2.bind).get_columns('scholarships')
        for col in cols:
            if col['name'] == 'fully_funded':
                print(f"  After migration: {col}")
                assert col['nullable'] is True, 'fully_funded should be nullable after migration'
                print("  ✓ Migration successful: fully_funded is now nullable")
                break
    
    # 4. Test NULL insert
    print("\n4. Testing NULL insert...")
    with get_session_factory()() as session3:
        s = Scholarship(
            title='Test PG NULL',
            country='Test',
            degree='Master',
            funding='Test',
            fully_funded=None
        )
        session3.add(s)
        session3.commit()
        result = session3.query(Scholarship).filter_by(title='Test PG NULL').first()
        assert result.fully_funded is None
        print("  ✓ NULL insert: PASS")
    
    # 4b. Test True insert
    print("\n4b. Testing True insert...")
    with get_session_factory()() as session4:
        s = Scholarship(
            title='Test PG True',
            country='Test',
            degree='Master',
            funding='Test',
            fully_funded=True
        )
        session4.add(s)
        session4.commit()
        result = session4.query(Scholarship).filter_by(title='Test PG True').first()
        assert result.fully_funded is True
        print("  ✓ True insert: PASS")
    
    # 4c. Test False insert
    print("\n4c. Testing False insert...")
    with get_session_factory()() as session5:
        s = Scholarship(
            title='Test PG False',
            country='Test',
            degree='Master',
            funding='Test',
            fully_funded=False
        )
        session5.add(s)
        session5.commit()
        result = session5.query(Scholarship).filter_by(title='Test PG False').first()
        assert result.fully_funded is False
        print("  ✓ False insert: PASS")
    
    # 5. Test idempotency
    print("\n5. Testing idempotency...")
    engine = create_engine('postgresql://test:test@localhost:5432/scholarzone_test')
    with engine.connect() as conn:
        _upgrade_postgresql_schema(conn)
        conn.commit()
    print("  ✓ Idempotent migration: PASS")
    
    print("\n" + "=" * 60)
    print("ALL POSTGRESQL MIGRATION TESTS PASSED")
    print("=" * 60)
    return True


if __name__ == '__main__':
    import os
    from app.database import reset_database_connections, init_database, get_session_factory, _upgrade_postgresql_schema
    from app.models import Scholarship
    from sqlalchemy import create_engine, text, inspect
    
    # Set environment
    os.environ['SCHOLARZONE_DATABASE_URL'] = 'postgresql://test:test@localhost:5432/scholarzone_test'
    os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'
    
    # Import after env vars set
    from app.database import reset_database_connections, init_database, get_session_factory, _upgrade_postgresql_schema
    from app.models import Scholarship
    from sqlalchemy import create_engine, text, inspect
    
    test_postgresql_migration()