#!/usr/bin/env python3
"""Initialize database schema for schema compatibility testing."""

import os
import sys
from pathlib import Path

# Use environment variable if provided, otherwise default to schema_compat_test
os.environ.setdefault('SCHOLARZONE_DATABASE_URL', 'postgresql://test:test@localhost:5435/schema_compat_test?sslmode=disable')
os.environ.setdefault('SCHOLARZONE_ENVIRONMENT', 'test')

# Add backend to path - use relative path from script location
BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import init_database

def main():
    try:
        init_database()
        print('Database initialization completed successfully')
        return 0
    except Exception as e:
        print(f'Database initialization failed: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())