
"""PostgreSQL integration tests for Study Planner FK handling in closed deletion.

ScholarZone PR #107. Verifies end-to-end that study_plans and study_plan_tasks
references to scholarships are DETACHED (not cascaded) during permanent deletion,
including rollback and late-dependency detection.
"""

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import select, text

from app.database import get_session_factory, init_database, reset_database_connections
from app.models import Scholarship, StudyPlan, StudyPlanTask, User
from app.test_db_safety import validate_disposable_postgres_url, verify_disposable_db_identity
from app.services.closed_deletion import (
    build_deletion_manifest,
    execute_deletion,
    _dependency_fingerprint,
    _unknown_fks_after_lock,
)
from app.services.purge_preflight.gate3_dependencies import run_gate3
from app.services.purge_preflight.database import create_accessor


TEST_URL = os.environ.get("TEST_POSTGRESQL_URL")


@pytest.mark.skipif(not TEST_URL, reason="TEST_POSTGRESQL_URL not set")
class TestStudyPlannerDeletionPostgreSQL:
    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        allow = os.environ.get("SCHOLARZONE_ALLOW_DESTRUCTIVE_TEST_DB")
        # Guard runs BEFORE any destructive SQL or DB init side effects.
        validate_disposable_postgres_url(TEST_URL, allow)
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", TEST_URL)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        reset_database_connections()
        init_database()
        from app.database import get_engine
        eng = get_engine()
        with eng.connect() as conn:
            verify_disposable_db_identity(conn, "scholarzone_test")
        with eng.begin() as conn:
            for tbl in (
                "study_plan_tasks", "study_plans", "deleted_closed_scholarships",
                "scholarship_evidence_archive", "scholarship_evidence", "scholarships",
                "users",
            ):
                conn.execute(text("TRUNCATE TABLE " + tbl + " RESTART IDENTITY CASCADE"))
        yield
        reset_database_connections()

    def _session(self):
        return get_session_factory()()

    def _make_user(self, db):
        u = User(email=f"u-{uuid.uuid4().hex}@example.com", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    def _make_closed_sch(self, db, **kw):
        vals = dict(
            title=f"Closed-{uuid.uuid4().hex[:8]}",
            country="Testland",
            degree="Master",
            funding="Fully Funded",
            status="closed",
            deadline_date=date(2020, 1, 1),
            official_source_url=f"https://example.edu/{uuid.uuid4().hex}",
        )
        vals.update(kw)
        s = Scholarship(**vals)
        db.add(s)
        db.commit()
        db.refresh(s)
        return s

    def test_study_planner_detach_preserves_rows(self):
        db = self._session()
        try:
            user = self._make_user(db)
            sch = self._make_closed_sch(db)
            sid = sch.id

            # study plan referencing scholarship
            plan = StudyPlan(user_id=user.id, title="Plan A", scholarship_id=sid)
            db.add(plan)
            db.commit()
            db.refresh(plan)
            pid = plan.id

            # task referencing scholarship + plan
            task = StudyPlanTask(
                plan_id=pid,
                title="Task 1",
                description="desc",
                priority="high",
                due_date=date(2021, 5, 5),
                status="open",
                related_scholarship_id=sid,
                position=3,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            tid = task.id

            # unrelated plan/task on another scholarship
            other_sch = self._make_closed_sch(db)
            other_plan = StudyPlan(user_id=user.id, title="Other Plan", scholarship_id=other_sch.id)
            db.add(other_plan)
            db.commit()
            db.refresh(other_plan)
            other_task = StudyPlanTask(
                plan_id=other_plan.id, title="Other Task", position=1,
                related_scholarship_id=other_sch.id,
            )
            db.add(other_task)
            db.commit()
            db.refresh(other_task)

            manifest = build_deletion_manifest(db)
            entry = next(m for m in manifest if m.scholarship_id == sid)
            assert entry.dependency_fingerprint

            # Gate 3 via accessor
            from app.services.purge_preflight.config import DatabaseConfig
            cfg = DatabaseConfig(readonly_url=TEST_URL)
            accessor = create_accessor(cfg)
            g3 = run_gate3(accessor, [sid])
            assert g3.status == "PASS", g3.error
            tables = { (r["table_schema"], r["table_name"]) for r in g3.fk_metadata }
            assert ("public", "study_plans") in tables
            assert ("public", "study_plan_tasks") in tables
            # policies explicit DETACH
            # (verified via source inspection; run_gate3 safe_to_delete implies policed)

            report = execute_deletion(db, [entry], dry_run=False)
            assert report.deleted_scholarships == 1, report.errors
            assert report.errors == []

            # plan preserved, scholarship_id null
            db.expire_all()
            p = db.get(StudyPlan, pid)
            assert p is not None
            assert p.scholarship_id is None
            assert p.title == "Plan A"
            assert p.user_id == user.id

            t = db.get(StudyPlanTask, tid)
            assert t is not None
            assert t.related_scholarship_id is None
            assert t.plan_id == pid
            assert t.title == "Task 1"
            assert t.description == "desc"
            assert t.priority == "high"
            assert t.due_date == date(2021, 5, 5)
            assert t.status == "open"
            assert t.position == 3

            # unrelated unaffected
            db.expire_all()
            op = db.get(StudyPlan, other_plan.id)
            assert op.scholarship_id == other_sch.id
            ot = db.get(StudyPlanTask, other_task.id)
            assert ot.related_scholarship_id == other_sch.id

            # scholarship deleted
            assert db.get(Scholarship, sid) is None
            # other scholarship remains
            assert db.get(Scholarship, other_sch.id) is not None

            # tombstone created
            from app.models import DeletedClosedScholarship
            ts = db.execute(select(DeletedClosedScholarship)).scalars().all()
            assert len(ts) >= 1
        finally:
            db.close()

    def test_study_planner_rollback_restores_fks(self, monkeypatch):
        db = self._session()
        try:
            user = self._make_user(db)
            sch = self._make_closed_sch(db)
            sid = sch.id

            plan = StudyPlan(user_id=user.id, title="Plan B", scholarship_id=sid)
            db.add(plan)
            db.commit()
            db.refresh(plan)
            pid = plan.id

            task = StudyPlanTask(
                plan_id=pid, title="Task R", position=1,
                related_scholarship_id=sid,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            tid = task.id

            manifest = build_deletion_manifest(db)
            entry = next(m for m in manifest if m.scholarship_id == sid)

            # inject failure during tombstone creation (after detachment)
            import app.services.closed_deletion as cd
            original_cls = cd.DeletedClosedScholarship

            def boom(*a, **k):
                raise RuntimeError("injected failure after detach")

            monkeypatch.setattr(cd, "DeletedClosedScholarship", boom)

            report = execute_deletion(db, [entry], dry_run=False)
            assert report.deleted_scholarships == 0
            assert report.errors, report.errors

            # rollback restored
            db.expire_all()
            assert db.get(Scholarship, sid) is not None
            p = db.get(StudyPlan, pid)
            assert p is not None
            assert p.scholarship_id == sid
            t = db.get(StudyPlanTask, tid)
            assert t is not None
            assert t.related_scholarship_id == sid
            # no partial tombstone
            from app.models import DeletedClosedScholarship
            assert db.execute(select(DeletedClosedScholarship)).scalars().all() == []
        finally:
            db.close()

    def test_study_planner_late_dependency_detected(self):
        db = self._session()
        try:
            user = self._make_user(db)
            sch = self._make_closed_sch(db)
            sid = sch.id

            # preflight: no study plan yet
            manifest = build_deletion_manifest(db)
            entry = next(m for m in manifest if m.scholarship_id == sid)
            fp_before = entry.dependency_fingerprint

            # introduce new study planner dependency after manifest
            plan = StudyPlan(user_id=user.id, title="Late Plan", scholarship_id=sid)
            db.add(plan)
            db.commit()
            db.refresh(plan)
            task = StudyPlanTask(
                plan_id=plan.id, title="Late Task", position=1,
                related_scholarship_id=sid,
            )
            db.add(task)
            db.commit()

            # fingerprint now differs
            fp_after = _dependency_fingerprint(db, sid)
            assert fp_after != fp_before

            report = execute_deletion(db, [entry], dry_run=False)
            # fail closed: skipped, no deletion
            assert report.deleted_scholarships == 0
            assert sid in report.skipped_scholarship_ids
            db.expire_all()
            assert db.get(Scholarship, sid) is not None
            # study plan preserved
            assert db.execute(select(StudyPlan).where(StudyPlan.scholarship_id == sid)).scalars().all()
        finally:
            db.close()

    def test_gate3_study_planner_unknown_fk_check(self):
        db = self._session()
        try:
            # _unknown_fks_after_lock should NOT flag study_plans/tasks
            # (they are in known set). With no rows still returns [].
            unknown = _unknown_fks_after_lock(db)
            flagged = [r for r in unknown if r["table_name"] in ("study_plans", "study_plan_tasks")]
            assert flagged == [], flagged
        finally:
            db.close()
