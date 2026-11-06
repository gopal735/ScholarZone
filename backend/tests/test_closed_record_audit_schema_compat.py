from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.closed_record_audit import _audit_scholarships, _classify_lifecycle


def test_closed_record_audit_uses_frontend_lifecycle_classifier():
    row = SimpleNamespace(
        id=1,
        status="open",
        is_archived=False,
        deadline_date=date(2000, 1, 1),
        deadline_display=None,
        deadline=None,
        deadline_precision="exact",
        application_period=None,
    )

    assert _classify_lifecycle([row])[1]["status"] == "closed"


def test_closed_record_audit_loads_without_optional_legacy_id_column():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE scholarships (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                is_verified BOOLEAN NOT NULL,
                is_archived BOOLEAN NOT NULL,
                archived_reason TEXT,
                status TEXT NOT NULL,
                deadline_date DATE,
                deadline_display TEXT,
                deadline_precision TEXT,
                application_period TEXT,
                official_source_url TEXT,
                catalogue_url TEXT,
                verification_notes TEXT,
                official_details TEXT,
                created_at DATETIME,
                last_verified_at DATE
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO scholarships (
                id, title, verification_status, is_verified, is_archived, status
            ) VALUES (1, 'Closed programme', 'retired', 0, 1, 'closed')
            """
        )

    try:
        with Session(engine) as session:
            row = session.scalars(_audit_scholarships()).one()
            assert row.id == 1
            assert row.title == "Closed programme"
            assert row.status == "closed"
    finally:
        engine.dispose()
