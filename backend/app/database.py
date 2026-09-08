"""SQLAlchemy engine and session lifecycle utilities."""

import logging
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .core.config import get_settings

_PRODUCTION_DB_PATH = (Path(__file__).resolve().parents[2] / "scholarzone.db").as_posix()


def _enforce_test_isolation(database_url: str) -> None:
    """Prevent tests from accidentally connecting to the production SQLite database.

    When SCHOLARZONE_ENVIRONMENT=test, any attempt to use the production
    SQLite file (backend/scholarzone.db) is a fatal error. Tests MUST use
    an isolated database (temp file or in-memory).
    """
    settings = get_settings()
    if settings.environment != "test":
        return
    if database_url.startswith("sqlite"):
        normalized = database_url.replace("sqlite:///", "")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if Path(normalized).as_posix() == _PRODUCTION_DB_PATH:
            raise RuntimeError(
                "SAFETY VIOLATION: Tests must not use the production SQLite database. "
                "Set SCHOLARZONE_DATABASE_URL to a temp file or use sqlite:///:memory:."
            )


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().database_url
    _enforce_test_isolation(database_url)
    # SQLAlchemy 2.0 defaults postgresql:// to the psycopg2 driver.
    # The installed driver is psycopg (v3), so rewrite the URL scheme
    # to postgresql+psycopg:// when no explicit driver is specified.
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    if database_url.startswith("postgresql"):
        connect_args["connect_timeout"] = 10
    return create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_timeout=10,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_database() -> None:
    # Importing here prevents metadata/model import cycles during app setup.
    from .models import Base

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _upgrade_sqlite_schema(engine)
    elif engine.dialect.name == "postgresql":
        _upgrade_postgresql_schema(engine)
        _validate_postgresql_schema(engine)


def _upgrade_postgresql_schema(engine: Engine) -> None:
    """Apply idempotent schema changes required by newer models on Neon.

    Uses PostgreSQL-specific DDL with IF NOT EXISTS guards so this is safe
    to run on every application startup without dropping tables or modifying
    existing data.
    """
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(engine).get_columns("scholarships")}
        additions = {
            "image_url": "VARCHAR(2048)",
            "image_source_url": "VARCHAR(2048)",
            "image_source_type": "VARCHAR(32)",
            "image_kind": "VARCHAR(32)",
            "image_verified_at": "TIMESTAMPTZ",
            "image_alt_text": "VARCHAR(512)",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE scholarships ADD COLUMN IF NOT EXISTS {name} {definition}"))

        if not inspect(engine).has_table("image_reviews"):
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS image_reviews (
                    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                    scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
                    image_url VARCHAR(2048) NOT NULL,
                    image_kind VARCHAR(32) NOT NULL,
                    source_page VARCHAR(2048),
                    source_type VARCHAR(32),
                    relevance_evidence TEXT,
                    licensing_status VARCHAR(32),
                    licensing_evidence TEXT,
                    confidence VARCHAR(32) NOT NULL,
                    reason_for_review VARCHAR(255),
                    decision VARCHAR(16) NOT NULL DEFAULT 'pending',
                    reviewed_by VARCHAR(120),
                    reviewed_at TIMESTAMPTZ,
                    reviewer_note TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_image_reviews_scholarship_decision ON image_reviews (scholarship_id, decision)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_image_reviews_created_at ON image_reviews (created_at)"))


def _validate_postgresql_schema(engine: Engine) -> None:
    """Validate required PostgreSQL schema objects exist after startup migration.

    This is a read-only safety check. It does not modify data or schema.
    """
    logger = logging.getLogger(__name__)
    inspector = inspect(engine)

    image_kind_ok = any(
        column["name"] == "image_kind" for column in inspector.get_columns("scholarships")
    )
    image_reviews_ok = inspector.has_table("image_reviews")

    try:
        image_review_indexes = {index["name"] for index in inspector.get_indexes("image_reviews")}
    except Exception:
        image_review_indexes = set()

    idx_decision_ok = "ix_image_reviews_scholarship_decision" in image_review_indexes
    idx_created_ok = "ix_image_reviews_created_at" in image_review_indexes
    indexes_ok = idx_decision_ok and idx_created_ok

    logger.info("[SCHEMA VALIDATION] image_kind: %s", "OK" if image_kind_ok else "MISSING")
    logger.info("[SCHEMA VALIDATION] image_reviews: %s", "OK" if image_reviews_ok else "MISSING")
    logger.info("[SCHEMA VALIDATION] indexes: %s", "OK" if indexes_ok else "MISSING")

    if not (image_kind_ok and image_reviews_ok and indexes_ok):
        missing = []
        if not image_kind_ok:
            missing.append("scholarships.image_kind")
        if not image_reviews_ok:
            missing.append("image_reviews")
        if not idx_decision_ok:
            missing.append("ix_image_reviews_scholarship_decision")
        if not idx_created_ok:
            missing.append("ix_image_reviews_created_at")
        raise RuntimeError(
            "[SCHEMA VALIDATION] STATUS: INVALID - Missing: " + ", ".join(missing)
        )

    logger.info("[SCHEMA VALIDATION] STATUS: VALID")


def _upgrade_sqlite_schema(engine: Engine) -> None:
    """Keep the lightweight local database compatible as fields are added.

    Production PostgreSQL deployments should use a reviewed migration workflow.
    The statements below are static and only target a developer's SQLite database.
    """
    columns = {column["name"] for column in inspect(engine).get_columns("scholarships")}
    additions = {
        "status": "VARCHAR(20) NOT NULL DEFAULT 'open'",
        "last_verified_at": "DATE",
        "last_verified_date": "DATE",
        "region": "VARCHAR(255)",
        "duration": "TEXT",
        "application_period": "TEXT",
        "official_source": "VARCHAR(255)",
        "official_source_url": "VARCHAR(2048)",
        "catalogue_url": "VARCHAR(2048)",
        "official_updates_url": "VARCHAR(2048)",
        "application_link": "VARCHAR(2048)",
        "image_url": "VARCHAR(2048)",
        "image_source_url": "VARCHAR(2048)",
        "image_source_type": "VARCHAR(32)",
        "image_kind": "VARCHAR(32)",
        "image_verified_at": "DATETIME",
        "image_alt_text": "VARCHAR(512)",
        "eligibility": "JSON NOT NULL DEFAULT '[]'",
        "eligibility_summary": "TEXT",
        "benefits": "JSON NOT NULL DEFAULT '[]'",
        "coverage": "JSON NOT NULL DEFAULT '[]'",
        "requirements": "JSON NOT NULL DEFAULT '[]'",
        "documents": "JSON NOT NULL DEFAULT '[]'",
        "english_requirement": "TEXT",
        "application_method": "JSON NOT NULL DEFAULT '[]'",
        "selection_notes": "TEXT",
        "program_type": "VARCHAR(255)",
        "best_fit": "TEXT",
        "notes": "TEXT",
        "verification_status": "TEXT NOT NULL DEFAULT 'active'",
        "next_verification_due": "DATE",
        "verified_by": "VARCHAR(120)",
        "verification_notes": "TEXT",
    }

    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE scholarships ADD COLUMN {name} {definition}"))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_scholarships_status ON scholarships (status)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_scholarships_status_deadline ON scholarships (status, deadline_date)"))

        _create_content_fingerprints_table(connection)
        _upgrade_discovery_candidates_table(connection)
        _create_image_reviews_table(connection)

    schema = inspect(engine)
    unique_source_constraints = (
        list(schema.get_unique_constraints("scholarships"))
        + [index for index in schema.get_indexes("scholarships") if index.get("unique")]
    )
    has_unique_source_url = any(
        constraint.get("column_names") == ["official_source_url"]
        for constraint in unique_source_constraints
    )
    if not has_unique_source_url:
        with engine.begin() as connection:
            duplicate_source_urls = connection.execute(
                text(
                    "SELECT official_source_url FROM scholarships "
                    "WHERE official_source_url IS NOT NULL "
                    "GROUP BY official_source_url HAVING COUNT(*) > 1"
                )
            ).scalars().all()
            if duplicate_source_urls:
                raise RuntimeError(
                    "Cannot enforce official_source_url uniqueness while duplicate values exist: "
                    + ", ".join(duplicate_source_urls)
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_scholarships_official_source_url "
                    "ON scholarships (official_source_url)"
                )
            )


def _create_content_fingerprints_table(connection) -> None:
    """Create the content_fingerprints table if it doesn't exist."""
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS content_fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url VARCHAR(2048) NOT NULL,
            normalized_content_hash VARCHAR(64) NOT NULL,
            content_length INTEGER NOT NULL DEFAULT 0,
            etag VARCHAR(255),
            last_modified VARCHAR(255),
            algorithm_version VARCHAR(16) NOT NULL DEFAULT 'v1',
            generated_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_fingerprints_source_url ON content_fingerprints (source_url)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_fingerprints_source_hash ON content_fingerprints (source_url, normalized_content_hash)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_fingerprints_generated ON content_fingerprints (source_url, generated_at)"))


def _upgrade_discovery_candidates_table(connection) -> None:
    """Add missing columns to discovery_candidates table if needed."""
    columns = {column["name"] for column in inspect(connection).get_columns("discovery_candidates")}
    additions = {
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "last_error": "VARCHAR(255)",
        "fetched_at": "DATETIME",
        "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE discovery_candidates ADD COLUMN {name} {definition}"))


def _create_image_reviews_table(connection) -> None:
    """Create the image_reviews table if it doesn't exist."""
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS image_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL,
            image_url VARCHAR(2048) NOT NULL,
            image_kind VARCHAR(32) NOT NULL,
            source_page VARCHAR(2048),
            source_type VARCHAR(32),
            relevance_evidence TEXT,
            licensing_status VARCHAR(32),
            licensing_evidence TEXT,
            confidence VARCHAR(32) NOT NULL,
            reason_for_review VARCHAR(255),
            decision VARCHAR(16) NOT NULL DEFAULT 'pending',
            reviewed_by VARCHAR(120),
            reviewed_at DATETIME,
            reviewer_note TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scholarship_id) REFERENCES scholarships (id)
        )
    """))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_image_reviews_scholarship_decision ON image_reviews (scholarship_id, decision)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_image_reviews_created_at ON image_reviews (created_at)"))


def close_database() -> None:
    get_engine().dispose()


def reset_database_connections() -> None:
    """Clear cached database connections for isolated tests only."""
    close_database()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
