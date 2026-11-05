import re

with open('.github/workflows/ci.yml', 'r') as f:
    content = f.read()

# The schema-compat job needs to be completely replaced
# Find the schema-compat job section (from "schema-compat:" to "build-and-smoke:")
pattern = r'(  schema-compat:.*?)(?=\n  build-and-smoke:)'

replacement = '  schema-compat:\n    runs-on: ubuntu-latest\n    services:\n      postgres:\n        image: postgres:16\n        env:\n          POSTGRES_DB: schema_compat_test\n          POSTGRES_USER: test\n          POSTGRES_PASSWORD: test\n        ports:\n          - 5435:5432\n        options: >-\n          --health-cmd="pg_isready -U test -d schema_compat_test"\n          --health-interval=10s\n          --health-timeout=5s\n          --health-retries=5\n    env:\n      SCHOLARZONE_ENVIRONMENT: test\n      SCHOLARZONE_DATABASE_URL: postgresql://test:test@localhost:5435/schema_compat_test?sslmode=disable\n    steps:\n    - name: Checkout\n      uses: actions/checkout@v4\n    - name: Install system dependencies\n      run: sudo apt-get update && sudo apt-get install -y libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjp2-7-dev libtiff5-dev libwebp-dev postgresql-client\n    - name: Set up Python\n      uses: actions/setup-python@v5\n      with:\n        python-version: \'3.11\'\n    - name: Cache pip dependencies\n      uses: actions/cache@v4\n      with:\n        path: ~/.cache/pip\n        key: ${{ runner.os }}-pip-${{ hashFiles(\'backend/requirements.txt\') }}\n        restore-keys: |\n          Linux-pip-\n    - name: Install dependencies\n      run: cd backend && pip install -r requirements.txt\n    - name: Install purge preflight test dependencies\n      run: cd backend && pip install -r requirements-purge-preflight.txt\n    - name: Wait for PostgreSQL to be ready\n      run: |\n        for i in {1..30}; do\n          if pg_isready -h localhost -p 5435 -U test -d schema_compat_test; then\n            echo "PostgreSQL is ready"\n            break\n          fi\n          echo "Waiting for PostgreSQL... ($i/30)"\n          sleep 2\n        done\n    - name: Initialize database schema\n      run: |\n        cd backend\n        python -c "\nimport os\nos.environ[\'SCHOLARZONE_DATABASE_URL\'] = \'postgresql://test:test@localhost:5435/schema_compat_test?sslmode=disable\'\nos.environ[\'SCHOLARZONE_ENVIRONMENT\'] = \'test\'\nfrom app.database import init_database\ninit_database()\nprint(\'Database initialization completed successfully\')\n"\n    - name: Run schema compat check\n      run: cd backend && python scripts/schema_compat_check.py 2>&1 | tee schema_compat_check.log\n    - name: Verify initialization idempotency\n      run: |\n        cd backend\n        python -c "\nimport os\nos.environ[\'SCHOLARZONE_DATABASE_URL\'] = \'postgresql://test:test@localhost:5435/schema_compat_test?sslmode=disable\'\nos.environ[\'SCHOLARZONE_ENVIRONMENT\'] = \'test\'\nfrom app.database import init_database\ninit_database()\nprint(\'Second initialization completed successfully (idempotency verified)\')\n"\n    - name: Run schema compat check again (idempotency)\n      run: cd backend && python scripts/schema_compat_check.py 2>&1 | tee schema_compat_check_idempotency.log\n    - name: Upload schema compat logs\n      uses: actions/upload-artifact@v4\n      if: always()\n      with:\n        name: schema-compat-logs\n        path: backend/schema_compat_check*.log'

with open('.github/workflows/ci.yml', 'r') as f:
    content = f.read()

pattern = r'(  schema-compat:.*?)(?=\n  build-and-smoke:)'

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('.github/workflows/ci.yml', 'w') as f:
    f.write(new_content)

print('Fixed')