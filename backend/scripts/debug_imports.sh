#!/usr/bin/env bash
# Debug script to test critical imports

cd backend

python -c "import psycopg; print('psycopg: OK')" 2>&1 || echo "psycopg: FAIL"
python -c "import sqlalchemy; print('sqlalchemy: OK')" 2>&1 || echo "sqlalchemy: FAIL"
python -c "import fastapi; print('fastapi: OK')" 2>&1 || echo "fastapi: FAIL"
python -c "import pydantic; print('pydantic: OK')" 2>&1 || echo "pydantic: FAIL"
python -c "import httpx; print('httpx: OK')" 2>&1 || echo "httpx: FAIL"
python -c "import PIL; print('PIL: OK')" 2>&1 || echo "PIL: FAIL"
python -c "import bs4; print('bs4: OK')" 2>&1 || echo "bs4: FAIL"
python -c "import apscheduler; print('apscheduler: OK')" 2>&1 || echo "apscheduler: FAIL"
python -c "import resend; print('resend: OK')" 2>&1 || echo "resend: FAIL"
python -c "import dotenv; print('dotenv: OK')" 2>&1 || echo "dotenv: FAIL"