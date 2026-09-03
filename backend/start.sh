#!/bin/bash
# ScholarZone Production Startup Script
#
# This script starts the ScholarZone API server with production configuration.
# It is used both for local testing and cloud deployment.
#
# Safety validations:
# - SCHOLARZONE_DATABASE_URL must be set
# - In production, DATABASE_URL must point to PostgreSQL (not SQLite)
# - SCHOLARZONE_VERIFICATION_SECRET should be set for production

set -e

# Load environment variables from .env if it exists (supports container deployments
# that mount .env as a file rather than setting individual env vars)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Also check parent directory for .env (common in Docker deployments)
if [ -f "../.env" ]; then
    set -a
    source ../.env
    set +a
fi

# Default values
export SCHOLARZONE_ENVIRONMENT="${SCHOLARZONE_ENVIRONMENT:-production}"
export PORT="${PORT:-8000}"

# Validate required environment variables
if [ -z "$SCHOLARZONE_DATABASE_URL" ]; then
    echo "ERROR: SCHOLARZONE_DATABASE_URL is not set"
    echo "Set it with: export SCHOLARZONE_DATABASE_URL=postgresql+psycopg://username:password@host:5432/scholarzone"
    exit 1
fi

# In production, require PostgreSQL (not SQLite)
if [ "$SCHOLARZONE_ENVIRONMENT" = "production" ]; then
    if [[ "$SCHOLARZONE_DATABASE_URL" == sqlite:* ]]; then
        echo "ERROR: Production environment requires PostgreSQL database, not SQLite"
        echo "SCHOLARZONE_DATABASE_URL=$SCHOLARZONE_DATABASE_URL"
        exit 1
    fi
    if [ -z "$SCHOLARZONE_VERIFICATION_SECRET" ]; then
        echo "WARNING: SCHOLARZONE_VERIFICATION_SECRET is not set in production"
        echo "The /internal/verify/trigger endpoint will be disabled"
    fi
fi

echo "Starting ScholarZone API..."
echo "Environment: $SCHOLARZONE_ENVIRONMENT"
echo "Port: $PORT"
echo "Database: ${SCHOLARZONE_DATABASE_URL%%:*}://***"  # Only show driver, hide credentials

# Initialize database
echo "Initializing database..."
python -c "
from app.database import init_database
init_database()
print('Database initialized successfully')
"

# Start uvicorn
echo "Starting uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --log-level info \
    --access-log
