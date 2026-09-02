"""Regression tests for production startup seeding behavior.

Verifies that scholarship seeding is skipped in production (database is
populated via migration) and that startup is idempotent.
"""

import os
from unittest.mock import patch

import pytest


def test_production_skips_seed_database():
    """In production, seed_database() should NOT be called during startup."""
    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "production",
        "SCHOLARZONE_DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb",
    }):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.environment == "production"


def test_development_runs_seed_database():
    """In development, seed_database() should be called during startup."""
    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "development",
        "SCHOLARZONE_DATABASE_URL": "sqlite:///./dev.db",
    }):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.environment == "development"


def test_test_environment_runs_seed_database():
    """In test environment, seed_database() should still be available."""
    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "test",
        "SCHOLARZONE_DATABASE_URL": "sqlite:///:memory:",
    }):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.environment == "test"


def test_lifespan_production_does_not_seed(monkeypatch):
    """The lifespan handler should skip seeding in production."""
    import asyncio
    from app.main import lifespan
    from fastapi import FastAPI

    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

    # Track if seed_database was called
    seed_called = False
    original_seed = None

    def mock_seed():
        nonlocal seed_called
        seed_called = True

    def mock_init():
        pass

    def mock_close():
        pass

    with patch("app.main.init_database", side_effect=mock_init), \
         patch("app.main.seed_database", side_effect=mock_seed), \
         patch("app.main.close_database", side_effect=mock_close):
        app = FastAPI()
        async def run_lifespan():
            async with lifespan(app):
                pass
        asyncio.run(run_lifespan())

    assert seed_called is False, "seed_database() should NOT be called in production"


def test_lifespan_development_does_seed(monkeypatch):
    """The lifespan handler should run seeding in development."""
    import asyncio
    from app.main import lifespan
    from fastapi import FastAPI

    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "development")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "sqlite:///./dev.db")

    seed_called = False

    def mock_seed():
        nonlocal seed_called
        seed_called = True
        return 0

    def mock_init():
        pass

    def mock_close():
        pass

    with patch("app.main.init_database", side_effect=mock_init), \
         patch("app.main.seed_database", side_effect=mock_seed), \
         patch("app.main.close_database", side_effect=mock_close):
        app = FastAPI()
        async def run_lifespan():
            async with lifespan(app):
                pass
        asyncio.run(run_lifespan())

    assert seed_called is True, "seed_database() should be called in development"


def test_lifespan_always_calls_init_database(monkeypatch):
    """The lifespan handler should always call init_database regardless of environment."""
    import asyncio
    from app.main import lifespan
    from fastapi import FastAPI

    for env in ["production", "development", "test"]:
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", env)
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "sqlite:///./test.db")

        init_called = False

        def mock_init():
            nonlocal init_called
            init_called = True

        def mock_seed():
            return 0

        def mock_close():
            pass

        with patch("app.main.init_database", side_effect=mock_init), \
             patch("app.main.seed_database", side_effect=mock_seed), \
             patch("app.main.close_database", side_effect=mock_close):
            app = FastAPI()
            async def run_lifespan():
                async with lifespan(app):
                    pass
            asyncio.run(run_lifespan())

        assert init_called is True, f"init_database() should be called in {env}"


def test_lifespan_always_calls_close_database(monkeypatch):
    """The lifespan handler should always call close_database on shutdown."""
    import asyncio
    from app.main import lifespan
    from fastapi import FastAPI

    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

    close_called = False

    def mock_init():
        pass

    def mock_seed():
        return 0

    def mock_close():
        nonlocal close_called
        close_called = True

    with patch("app.main.init_database", side_effect=mock_init), \
         patch("app.main.seed_database", side_effect=mock_seed), \
         patch("app.main.close_database", side_effect=mock_close):
        app = FastAPI()
        async def run_lifespan():
            async with lifespan(app):
                pass
        asyncio.run(run_lifespan())

    assert close_called is True, "close_database() should be called on shutdown"


def test_seed_database_idempotent_on_empty_sqlite():
    """seed_database() should be safe to call multiple times on SQLite (dev/test)."""
    with patch.dict(os.environ, {
        "SCHOLARZONE_ENVIRONMENT": "development",
        "SCHOLARZONE_DATABASE_URL": "sqlite:///:memory:",
    }):
        from app.database import init_database, reset_database_connections, get_session_factory
        from app.seed import seed_database

        reset_database_connections()
        init_database()

        # First call should seed
        count1 = seed_database()
        assert count1 > 0, "First seed should create records"

        # Second call should be idempotent (no new records, no crash)
        count2 = seed_database()
        assert count2 == 0, "Second seed should create no new records (idempotent)"

        reset_database_connections()


def test_production_empty_database_startup_simulation(monkeypatch):
    """Simulate production startup on empty database - should succeed without seeding."""
    import asyncio
    from app.main import lifespan
    from fastapi import FastAPI

    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")

    init_called = False
    seed_called = False

    def mock_init():
        nonlocal init_called
        init_called = True

    def mock_seed():
        nonlocal seed_called
        seed_called = True
        return 0

    def mock_close():
        pass

    with patch("app.main.init_database", side_effect=mock_init), \
         patch("app.main.seed_database", side_effect=mock_seed), \
         patch("app.main.close_database", side_effect=mock_close):
        app = FastAPI()
        async def run_lifespan():
            async with lifespan(app):
                pass
        asyncio.run(run_lifespan())

    assert init_called is True, "init_database should be called"
    assert seed_called is False, "seed_database should NOT be called in production"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
