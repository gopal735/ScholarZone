import os
import sys

# Simulate production environment to test startup
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'production'
os.environ['SCHOLARZONE_DATABASE_URL'] = 'postgresql+psycopg://test:test@localhost:5432/test'
os.environ['SCHOLARZONE_VERIFICATION_SECRET'] = 'test_secret'

try:
    from app.main import app
    print('App import: OK')
    print(f'Routes: {[r.path for r in app.routes if hasattr(r, "path")]}')
except Exception as e:
    print(f'Import ERROR: {e}')
    import traceback
    traceback.print_exc()

try:
    from app.database import init_database
    print('Database init import: OK')
except Exception as e:
    print(f'Database import ERROR: {e}')

try:
    from app.scheduler_v2 import run_verification_round
    print('Scheduler import: OK')
except Exception as e:
    print(f'Scheduler import ERROR: {e}')

try:
    from app.core.config import get_settings
    settings = get_settings()
    print(f'Settings OK: env={settings.environment}')
    print(f'Config OK: database_url = {settings.database_url[:20]}***')
except Exception as e:
    print(f'Config ERROR: {e}')
    import traceback
    traceback.print_exc()
