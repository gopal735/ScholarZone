"""Regression tests for PostgreSQL driver selection (psycopg v3).

Verifies that SQLAlchemy engine creation uses psycopg v3 (not psycopg2)
and that SQLite behavior is preserved.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings


def _reset_engine_cache():
    """Clear cached engine/session factory between tests."""
    from app.database import reset_database_connections
    reset_database_connections()


def test_postgresql_url_rewritten_to_psycopg():
    """postgresql:// URL should be rewritten to postgresql+psycopg://."""
    _reset_engine_cache()
    postgres_url = "postgresql://user:pass@localhost:5432/testdb"
    mock_engine = MagicMock()

    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "production",
        "SCHOLARZONE_DATABASE_URL": postgres_url,
    }):
        from app.database import get_engine
        with patch("app.database.create_engine", return_value=mock_engine) as mock_create:
            get_engine()
            # Verify create_engine was called with rewritten URL
            args, kwargs = mock_create.call_args
            assert args[0] == "postgresql+psycopg://user:pass@localhost:5432/testdb", \
                f"Expected postgresql+psycopg:// but got {args[0]}"

    _reset_engine_cache()


def test_postgresql_already_has_psycopg_driver():
    """postgresql+psycopg:// URL should NOT be double-rewritten."""
    _reset_engine_cache()
    original = "postgresql+psycopg://user:pass@localhost:5432/testdb"
    mock_engine = MagicMock()

    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "production",
        "SCHOLARZONE_DATABASE_URL": original,
    }):
        from app.database import get_engine
        with patch("app.database.create_engine", return_value=mock_engine) as mock_create:
            get_engine()
            args, kwargs = mock_create.call_args
            assert args[0] == original, f"URL should not be modified: {args[0]}"

    _reset_engine_cache()


def test_sqlite_url_not_modified():
    """SQLite URLs should not be rewritten."""
    _reset_engine_cache()
    sqlite_url = "sqlite:///./test.db"
    mock_engine = MagicMock()

    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "development",
        "SCHOLARZONE_DATABASE_URL": sqlite_url,
    }):
        from app.database import get_engine
        with patch("app.database.create_engine", return_value=mock_engine) as mock_create:
            get_engine()
            args, kwargs = mock_create.call_args
            assert args[0] == sqlite_url, f"SQLite URL should not be modified: {args[0]}"
            assert kwargs.get("connect_args", {}).get("check_same_thread") is False

    _reset_engine_cache()


def test_postgresql_sslmode_preserved():
    """Query parameters (sslmode=require) should be preserved during rewrite."""
    _reset_engine_cache()
    original = "postgresql://user:pass@host.neon.tech/dbname?sslmode=require"
    mock_engine = MagicMock()

    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "production",
        "SCHOLARZONE_DATABASE_URL": original,
    }):
        from app.database import get_engine
        with patch("app.database.create_engine", return_value=mock_engine) as mock_create:
            get_engine()
            args, kwargs = mock_create.call_args
            expected = "postgresql+psycopg://user:pass@host.neon.tech/dbname?sslmode=require"
            assert args[0] == expected, f"Query params lost: {args[0]}"

    _reset_engine_cache()


def test_production_sqlite_rejected():
    """Production with SQLite URL should still raise RuntimeError."""
    _reset_engine_cache()
    # Get the actual production DB path used by the safety check
    from app.database import _PRODUCTION_DB_PATH
    sqlite_url = f"sqlite:///{_PRODUCTION_DB_PATH}"

    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "test",
        "SCHOLARZONE_DATABASE_URL": sqlite_url,
    }):
        from app.database import _enforce_test_isolation
        with pytest.raises(RuntimeError, match="SAFETY VIOLATION"):
            _enforce_test_isolation(sqlite_url)

    _reset_engine_cache()


def test_pool_pre_ping_set_for_postgresql():
    """pool_pre_ping=True should be set for PostgreSQL engines."""
    _reset_engine_cache()
    postgres_url = "postgresql://user:pass@localhost:5432/testdb"
    mock_engine = MagicMock()

    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "production",
        "SCHOLARZONE_DATABASE_URL": postgres_url,
    }):
        from app.database import get_engine
        with patch("app.database.create_engine", return_value=mock_engine) as mock_create:
            get_engine()
            args, kwargs = mock_create.call_args
            assert kwargs.get("pool_pre_ping") is True

    _reset_engine_cache()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
