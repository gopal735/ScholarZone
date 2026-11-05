#!/usr/bin/env python3
"""Verify initialization idempotency for schema compatibility testing."""

import os
import sys

# Set environment variables
os.environ['SCHOLARZONE_DATABASE_URL'] = 'postgresql://test:test@localhost:5435/schema_compat_test?sslmode=disable'
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'test'

# Add backend to path
sys.path.insert(0, '/home/runner/work/ScholarZone/ScholarZone/backend')

from app.database import init_database

def main():
    try:
        init_database()
        print('Second initialization completed successfully (idempotency verified)')
        return 0
    except Exception as e:
        print(f'Second initialization failed: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())