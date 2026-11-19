"""PostgreSQL integration tests for closed scholarship deletion race conditions.

These tests require a running PostgreSQL instance and are skipped unless
TEST_POSTGRESQL_URL is set.
"""

import os
import uuid
from datetime import date

import pytest

from app.database import init_database, reset_database_connections
from app.models import Scholarship, ApplicationRecord, User
from app.services.closed_deletion import build_deletion_manifest, execute_deletion


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRESQL_URL"),
    reason="TEST_POSTGRESQL_URL not set",
)
class TestPostgreSQLDeletionRace:
    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        pg_url = os.environ.get("TEST_POSTGRESQL_URL")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", pg_url)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        reset_database_connections()
        init_database()
        yield
        reset_database_connections()

    @pytest.fixture
    def pg_sessions(self):
        from app.database import get_session_factory

        sf = get_session_factory()
        s1 = sf()
        s2 = sf()
        yield s1, s2
        s1.close()
        s2.close()

    def test_reopened_scholarship_skipped_with_row_lock(self, pg_sessions):
        s1, s2 = pg_sessions
        uid = uuid.uuid4().hex

        # Create a CLOSED scholarship in session 1
        sch = Scholarship(
            title=f"RaceTest-{uid}",
            country="Testland",
            degree="Master",
            funding="Fully Funded",
            status="closed",
            deadline_date=date(2020, 1, 1),
            official_source_url=f"https://example.edu/race-{uid}",
        )
        s1.add(sch)
        s1.commit()
        s1.refresh(sch)
        sid = sch.id

        # Build manifest while CLOSED (in s1)
        manifest = build_deletion_manifest(s1)
        assert len(manifest) >= 1
        assert any(m.scholarship_id == sid for m in manifest)

        # Concurrent transaction: reopen the scholarship in s2
        sch2 = s2.get(Scholarship, sid)
        sch2.status = "open"
        sch2.deadline_date = date(2026, 12, 31)
        s2.commit()

        # Execute deletion in s1 - should skip because reopened
        report = execute_deletion(s1, manifest, dry_run=False)
        assert report.deleted_scholarships == 0
        assert sid in report.skipped_scholarship_ids
        assert report.errors == []

        # Verify scholarship still exists (expire identity map first)
        s1.expire_all()
        remaining = s1.get(Scholarship, sid)
        assert remaining is not None
        assert remaining.status == "open"

        # Cleanup
        s1.query(Scholarship).filter(Scholarship.id == sid).delete()
        s1.commit()

    def test_future_cycle_added_skips_deletion(self, pg_sessions):
        s1, s2 = pg_sessions
        uid = uuid.uuid4().hex

        sch = Scholarship(
            title=f"RaceTest2-{uid}",
            country="Testland",
            degree="Master",
            funding="Fully Funded",
            status="closed",
            deadline_date=date(2020, 1, 1),
            official_source_url=f"https://example.edu/race2-{uid}",
        )
        s1.add(sch)
        s1.commit()
        s1.refresh(sch)
        sid = sch.id

        manifest = build_deletion_manifest(s1)
        assert any(m.scholarship_id == sid for m in manifest)

        # Add future cycle in s2
        sch2 = s2.get(Scholarship, sid)
        sch2.application_period = "opens 2026-06-01"
        sch2.status = "closed"
        s2.commit()

        report = execute_deletion(s1, manifest, dry_run=False)
        assert report.deleted_scholarships == 0
        assert sid in report.skipped_scholarship_ids

        # Cleanup
        s1.query(Scholarship).filter(Scholarship.id == sid).delete()
        s1.commit()