"""Read-only SQLAlchemy engine and session for production manifest operations."""

import logging
from functools import lru_cache
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from .core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_readonly_engine():
    database_url = get_settings().database_url
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    if database_url.startswith("postgresql"):
        connect_args["connect_timeout"] = 10
        if "sslmode=" not in database_url:
            database_url += ("&" if "?" in database_url else "?") + "sslmode=require"
    engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
    if database_url.startswith("postgresql"):
        engine_kwargs["pool_timeout"] = 10
    engine = create_engine(database_url, **engine_kwargs)

    @event.listens_for(engine, "before_cursor_execute")
    def _enforce_readonly(conn, cursor, statement, parameters, context, executemany):
        stmt_upper = statement.strip().upper()
        if stmt_upper.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
                                   'TRUNCATE', 'COPY', 'GRANT', 'REVOKE', 'LOCK')):
            raise RuntimeError(
                f"READ-ONLY VIOLATION: Write operation blocked: {statement[:200]}"
            )

    if database_url.startswith("postgresql"):
        @event.listens_for(engine, "connect")
        def set_readonly(conn, record):
            conn.exec_driver_sql("SET DEFAULT_TRANSACTION_READ_ONLY = on")

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
        conn.exec_driver_sql("SELECT 1")
    logger.info("Read-only database connection verified")