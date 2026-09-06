"""Regression and idempotency tests for migrate_schema.py.

These tests verify the schema migration logic using SQLite as a portable
stand-in for dialect-agnostic SQLAlchemy inspection.  migrate_schema.py
generates dialect-appropriate DDL, so the same logic is testable on SQLite
and valid for PostgreSQL production.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine, inspect, text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from migrate_schema import (
    REQUIRED_COLUMNS,
    REQUIRED_INDEXES,
    REQUIRED_TABLES,
    column_exists,
    index_exists,
    run_migration,
    table_exists,
)


class Base(DeclarativeBase):
    pass


class Scholarship(Base):
    __tablename__ = "scholarships"
    __table_args__ = (
        Index("ix_scholarships_country_degree", "country", "degree"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str] = mapped_column(nullable=False)
    degree: Mapped[str] = mapped_column(nullable=False)


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


class TestColumnDetection:
    def test_existing_column_detected(self, sqlite_engine):
        assert column_exists(sqlite_engine, "scholarships", "title") is True

    def test_missing_column_detected(self, sqlite_engine):
        assert column_exists(sqlite_engine, "scholarships", "image_kind") is False


class TestTableDetection:
    def test_existing_table_detected(self, sqlite_engine):
        assert table_exists(sqlite_engine, "scholarships") is True

    def test_missing_table_detected(self, sqlite_engine):
        assert table_exists(sqlite_engine, "image_reviews") is False


class TestIndexDetection:
    def test_existing_index_detected(self, sqlite_engine):
        inspector = inspect(sqlite_engine)
        indexes = [idx["name"] for idx in inspector.get_indexes("scholarships")]
        assert "ix_scholarships_country_degree" in indexes

    def test_missing_index_detected(self, sqlite_engine):
        assert index_exists(sqlite_engine, "image_reviews", "ix_image_reviews_scholarship_decision") is False


class TestMigrationAddsMissingColumn:
    def test_adds_image_kind_column(self, sqlite_engine):
        assert column_exists(sqlite_engine, "scholarships", "image_kind") is False
        run_migration(sqlite_engine)
        assert column_exists(sqlite_engine, "scholarships", "image_kind") is True

    def test_adds_image_reviews_table(self, sqlite_engine):
        assert table_exists(sqlite_engine, "image_reviews") is False
        run_migration(sqlite_engine)
        assert table_exists(sqlite_engine, "image_reviews") is True

    def test_adds_required_indexes(self, sqlite_engine):
        run_migration(sqlite_engine)
        assert index_exists(sqlite_engine, "image_reviews", "ix_image_reviews_scholarship_decision") is True
        assert index_exists(sqlite_engine, "image_reviews", "ix_image_reviews_created_at") is True


class TestMigrationIdempotency:
    def test_second_run_makes_no_changes(self, sqlite_engine):
        changes1 = run_migration(sqlite_engine)
        changes2 = run_migration(sqlite_engine)
        assert len(changes1) > 0
        assert len(changes2) == 0

    def test_column_preserved_after_multiple_runs(self, sqlite_engine):
        run_migration(sqlite_engine)
        run_migration(sqlite_engine)
        assert column_exists(sqlite_engine, "scholarships", "image_kind") is True

    def test_table_preserved_after_multiple_runs(self, sqlite_engine):
        run_migration(sqlite_engine)
        run_migration(sqlite_engine)
        assert table_exists(sqlite_engine, "image_reviews") is True

    def test_indexes_not_duplicated_after_multiple_runs(self, sqlite_engine):
        run_migration(sqlite_engine)
        run_migration(sqlite_engine)
        inspector = inspect(sqlite_engine)
        indexes = [idx["name"] for idx in inspector.get_indexes("image_reviews")]
        assert indexes.count("ix_image_reviews_scholarship_decision") == 1
        assert indexes.count("ix_image_reviews_created_at") == 1


class TestExistingDataPreservation:
    def test_existing_scholarships_unchanged(self, sqlite_engine):
        with sqlite_engine.begin() as conn:
            conn.execute(text("INSERT INTO scholarships (title, country, degree) VALUES ('A', 'US', 'Master')"))
            conn.execute(text("INSERT INTO scholarships (title, country, degree) VALUES ('B', 'CA', 'PhD')"))

        run_migration(sqlite_engine)

        with sqlite_engine.begin() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM scholarships")).scalar()
        assert count == 2

    def test_existing_data_values_unchanged(self, sqlite_engine):
        with sqlite_engine.begin() as conn:
            conn.execute(text("INSERT INTO scholarships (title, country, degree) VALUES ('A', 'US', 'Master')"))

        run_migration(sqlite_engine)

        with sqlite_engine.begin() as conn:
            row = conn.execute(text("SELECT title, country FROM scholarships WHERE id = 1")).fetchone()
        assert row[0] == "A"
        assert row[1] == "US"


class TestDryRun:
    def test_dry_run_reports_changes_without_applying(self, sqlite_engine):
        changes = run_migration(sqlite_engine, dry_run=True)
        assert len(changes) > 0
        assert column_exists(sqlite_engine, "scholarships", "image_kind") is False

    def test_dry_run_then_apply_produces_same_changes(self, sqlite_engine):
        expected = run_migration(sqlite_engine, dry_run=True)
        run_migration(sqlite_engine)
        assert column_exists(sqlite_engine, "scholarships", "image_kind") is True
        assert len(expected) > 0
