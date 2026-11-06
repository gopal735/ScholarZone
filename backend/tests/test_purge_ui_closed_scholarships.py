from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
)
import pytest

from scripts.purge_ui_closed_scholarships import PurgeSafetyError, purge


def build_database():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    scholarships = Table(
        "scholarships",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String, nullable=False),
        Column("status", String, nullable=False),
        Column("deadline_date", Date),
        Column("deadline_display", String),
        Column("deadline_precision", String),
        Column("application_period", String),
        Column("related_scholarship_id", ForeignKey("scholarships.id")),
        Column("is_archived", Integer, nullable=False, default=0),
    )
    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email", String, nullable=False),
    )
    applications = Table(
        "applications",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("scholarship_id", ForeignKey("scholarships.id"), nullable=False),
        Column("user_id", ForeignKey("users.id"), nullable=False),
    )
    checklist = Table(
        "application_checklist",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("application_id", ForeignKey("applications.id"), nullable=False),
    )
    saved = Table(
        "saved_scholarships",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("scholarship_id", ForeignKey("scholarships.id"), nullable=False),
        Column("user_id", ForeignKey("users.id"), nullable=False),
    )
    metadata.create_all(engine)
    return engine, {
        "scholarships": scholarships,
        "users": users,
        "applications": applications,
        "application_checklist": checklist,
        "saved_scholarships": saved,
    }


def seed(connection, tables):
    connection.execute(
        insert(tables["scholarships"]),
        [
            {
                "id": 1,
                "title": "Expired scholarship",
                "status": "open",
                "deadline_date": date(2000, 1, 1),
                "deadline_precision": "exact",
                "is_archived": 0,
            },
            {
                "id": 2,
                "title": "Future scholarship",
                "status": "open",
                "deadline_date": date(2099, 1, 1),
                "deadline_precision": "exact",
                "is_archived": 0,
            },
        ],
    )
    connection.execute(insert(tables["users"]), {"id": 10, "email": "student@example.test"})
    connection.execute(
        insert(tables["applications"]),
        {"id": 20, "scholarship_id": 1, "user_id": 10},
    )
    connection.execute(
        insert(tables["application_checklist"]),
        {"id": 30, "application_id": 20},
    )
    connection.execute(
        insert(tables["saved_scholarships"]),
        {"id": 40, "scholarship_id": 1, "user_id": 10},
    )


def test_dry_run_counts_closed_rows_and_all_linked_data_without_deleting():
    engine, tables = build_database()
    try:
        with engine.begin() as connection:
            seed(connection, tables)
        with engine.connect() as connection:
            transaction = connection.begin()
            report = purge(connection, apply=False)
            transaction.rollback()
            assert report["closed_scholarship_ids"] == [1]
            assert report["rows_by_table"] == {
                "application_checklist": 1,
                "applications": 1,
                "saved_scholarships": 1,
                "scholarships": 1,
            }
        with engine.connect() as connection:
            assert connection.scalar(select(tables["scholarships"].c.id).where(tables["scholarships"].c.id == 1)) == 1
            assert connection.scalar(select(tables["applications"].c.id)) == 20
            assert connection.scalar(select(tables["users"].c.id)) == 10
    finally:
        engine.dispose()


def test_apply_deletes_only_ui_closed_scholarship_and_descendant_rows():
    engine, tables = build_database()
    try:
        with engine.begin() as connection:
            seed(connection, tables)
        with engine.begin() as connection:
            report = purge(connection, apply=True)
            assert report["closed_scholarship_ids"] == [1]
        with engine.connect() as connection:
            assert connection.scalar(select(tables["scholarships"].c.id).where(tables["scholarships"].c.id == 1)) is None
            assert connection.scalar(select(tables["scholarships"].c.id).where(tables["scholarships"].c.id == 2)) == 2
            for table_name in ("applications", "application_checklist", "saved_scholarships"):
                assert connection.scalar(select(tables[table_name].c.id)) is None
            assert connection.scalar(select(tables["users"].c.id)) == 10
    finally:
        engine.dispose()


def test_non_closed_scholarship_reference_aborts_without_expanding_purge_set():
    engine, tables = build_database()
    try:
        with engine.begin() as connection:
            seed(connection, tables)
            connection.execute(
                tables["scholarships"]
                .update()
                .where(tables["scholarships"].c.id == 2)
                .values(related_scholarship_id=1)
            )
        with engine.begin() as connection:
            with pytest.raises(PurgeSafetyError, match="non-closed scholarship"):
                purge(connection, apply=True)
        with engine.connect() as connection:
            assert connection.scalar(select(tables["scholarships"].c.id).where(tables["scholarships"].c.id == 1)) == 1
            assert connection.scalar(select(tables["scholarships"].c.id).where(tables["scholarships"].c.id == 2)) == 2
    finally:
        engine.dispose()
