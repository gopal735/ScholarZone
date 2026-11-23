"""Read-only SQLAlchemy engine and session for production manifest operations."""

import logging
import os
from functools import lru_cache
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


def _readonly_database_url() -> str:
    url = os.getenv("SCHOLARZONE_DATABASE_URL_RO", "").strip()
    if not url:
        raise RuntimeError(
            "SCHOLARZONE_DATABASE_URL_RO is required for read-only database access. "
            "Configure a read-only PostgreSQL (Neon) connection string."
        )
    return url


@lru_cache
def get_readonly_engine():
    database_url = _readonly_database_url()
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    if database_url.startswith("postgresql"):
        connect_args["connect_timeout"] = 10
        if "sslmode=" not in database_url:
            database_url += ("&" if "?" in database_url else "?") + "sslmode=verify-full"
    engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
    if database_url.startswith("postgresql"):
        engine_kwargs["pool_timeout"] = 10
    engine = create_engine(database_url, **engine_kwargs)

    @event.listens_for(engine, "before_cursor_execute")
    def _enforce_readonly(conn, cursor, statement, parameters, context, executemany):
        stmt_upper = (statement or "").strip().upper()
        if stmt_upper.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
                                   'TRUNCATE', 'COPY', 'GRANT', 'REVOKE', 'LOCK', 'MERGE')):
            raise RuntimeError(
                f"READ-ONLY VIOLATION: Write operation blocked: {statement[:200]}"
            )

    if database_url.startswith("postgresql"):
        @event.listens_for(engine, "connect")
        def set_readonly(conn, record):
            cur = conn.cursor()
            try:
                cur.execute("SET DEFAULT_TRANSACTION_READ_ONLY = on")
                conn.commit()
            finally:
                cur.close()

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_query_only(conn, record):
            cur = conn.cursor()
            try:
                cur.execute("PRAGMA query_only=ON")
            finally:
                cur.close()

    return engine


@lru_cache
def get_readonly_session_factory():
    return sessionmaker(
        bind=get_readonly_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session
    )


def get_readonly_session():
    return get_readonly_session_factory()()


def init_readonly_database():
    engine = get_readonly_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Read-only database connection verified")
