import re

with open('.github/workflows/ci.yml', 'r') as f:
    content = f.read()

# The schema-compat job needs to be completely replaced
# The job starts with "  schema-compat:" and ends before "  build-and-smoke:"
pattern = r'(  schema-compat:.*?)(?=\n  build-and-smoke:)'

replacement = '''  schema-compat:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: schema_compat_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5435:5432
        options: >-
          --health-cmd="pg_isready -U test -d schema_compat_test"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
    env:
      SCHOLARZONE_ENVIRONMENT: test
      SCHOLARZONE_DATABASE_URL: postgresql://test:test@localhost:5435/schema_compat_test?sslmode=disable
    steps:
    - name: Checkout
      uses: actions/checkout@v4
    - name: Install system dependencies
      run: sudo apt-get update && sudo apt-get install -y libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjp2-7-dev libtiff5-dev libwebp-dev postgresql-client
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - name: Cache pip dependencies
      uses: actions/cache@v4
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('backend/requirements.txt') }}
        restore-keys: |
          Linux-pip-
    - name: Install dependencies
      run: cd backend && pip install -r requirements.txt
    - name: Install purge preflight test dependencies
      run: cd backend && pip install -r requirements-purge-preflight.txt
    - name: Wait for PostgreSQL to be ready
      run: |
        for i in {1..30}; do
          if pg_isready -h localhost -p 5435 -U test -d schema_compat_test; then
            echo "PostgreSQL is ready"
            break
          fi
          echo "Waiting for PostgreSQL... ($i/30)"
          sleep 2
        done
    - name: Initialize database schema
      run: |
        cd backend
        python scripts/init_schema.py
    - name: Run schema compat check
      run: cd backend && python scripts/schema_compat_check.py 2>&1 | tee schema_compat_check.log
    - name: Verify initialization idempotency
      run: |
        cd backend
        python scripts/verify_idempotency.py
    - name: Run schema compat check again (idempotency)
      run: cd backend && python scripts/schema_compat_check.py 2>&1 | tee schema_compat_check_idempotency.log
    - name: Upload schema compat logs
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: schema-compat-logs
        path: backend/schema_compat_check*.log'''

with open('.github/workflows/ci.yml', 'r') as f:
    content = f.read()

pattern = r'(  schema-compat:.*?)(?=\n  build-and-smoke:)'

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('.github/workflows/ci.yml', 'w') as f:
    f.write(new_content)

print('Fixed')