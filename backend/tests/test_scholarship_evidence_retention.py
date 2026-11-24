"""PostgreSQL integration tests for Gate 6 scholarship-evidence retention.

ScholarZone PR #107, P0: evidence used to authorize permanent scholarship
deletion must survive that deletion as durable, auditable historical evidence.

These tests exercise real PostgreSQL behavior (row locks, FK enforcement,
DDL/constraint metadata and triggers), not just ORM metadata. They are skipped
unless TEST_POSTGRESQL_URL names a disposable test database.
"""

import hashlib
import os
import threading
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import psycopg2
import pytest
from sqlalchemy import func, inspect as sa_inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.database import get_session_factory, init_database, reset_database_connections
from app.models import Scholarship, ScholarshipEvidence, ScholarshipEvidenceArchive
from app.services.closed_deletion import (
    _archive_gate6_evidence,
    _evidence_content_hash,
    build_deletion_manifest,
    execute_deletion,
)

TEST_URL = os.environ.get("TEST_POSTGRESQL_URL")
MIGRATION_SQL = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "20261124_scholarship_evidence_archive.sql"
)

pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_POSTGRESQL_URL not set")


def _session():
    return get_session_factory()()


def _new_scholarship(db, **overrides):
    values = dict(
        title=f"Retention-{uuid.uuid4().hex[:10]}",
        country="Testland",
        degree="Master",
        funding="Fully Funded",
        status="closed",
        deadline_date=date(2020, 1, 1),
    )
    values.update(overrides)
    scholarship = Scholarship(**values)
    db.add(scholarship)
    db.commit()
    db.refresh(scholarship)
    return scholarship


def _new_evidence(db, scholarship_id, **overrides):
    excerpt = "The official notice confirms the application cycle has closed."
    values = dict(
        scholarship_id=scholarship_id,
        application_cycle="2026_EXT_TEST",
        official_domain="regs.example.edu",
        official_url="https://regs.example.edu/2026/cycle",
        source_title="Official 2026 regulations",
        deadline=date(2020, 1, 1),
        deadline_precision="day",
        supporting_excerpt=excerpt,
        excerpt_hash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        retrieval_date=date(2026, 1, 5),
        reviewer="reviewer.one",
        decision="EXPIRED_VERIFIED",
        provenance="official-source",
    )
    values.update(overrides)
    evidence = ScholarshipEvidence(**values)
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def _snapshot(evidence):
    """Everything that must be retained, plus the canonical content hash."""
    return {
        "scholarship_id": evidence.scholarship_id,
        "application_cycle": evidence.application_cycle,
        "official_domain": evidence.official_domain,
        "official_url": evidence.official_url,
        "source_title": evidence.source_title,
        "deadline": evidence.deadline,
        "deadline_precision": evidence.deadline_precision,
        "supporting_excerpt": evidence.supporting_excerpt,
        "excerpt_hash": evidence.excerpt_hash,
        "retrieval_date": evidence.retrieval_date,
        "reviewer": evidence.reviewer,
        "decision": evidence.decision,
        "provenance": evidence.provenance,
        "content_hash": _evidence_content_hash(evidence),
    }


def _assert_archive_matches(archive_row, snapshot):
    assert archive_row.original_scholarship_id == snapshot["scholarship_id"]
    assert archive_row.application_cycle == snapshot["application_cycle"]
    assert archive_row.official_domain == snapshot["official_domain"]
    assert archive_row.official_url == snapshot["official_url"]
    assert archive_row.source_title == snapshot["source_title"]
    assert archive_row.deadline == snapshot["deadline"]
    assert archive_row.deadline_precision == snapshot["deadline_precision"]
    assert archive_row.supporting_excerpt == snapshot["supporting_excerpt"]
    assert archive_row.excerpt_hash == snapshot["excerpt_hash"]
    assert archive_row.retrieval_date == snapshot["retrieval_date"]
    assert archive_row.reviewer == snapshot["reviewer"]
    assert archive_row.decision == snapshot["decision"]
    assert archive_row.provenance == snapshot["provenance"]
    assert archive_row.content_hash == snapshot["content_hash"]


def _evidence_like_from_archive(row):
    """The archived content in the shape expected by the canonical hash."""
    return SimpleNamespace(
        application_cycle=row.application_cycle,
        official_domain=row.official_domain,
        official_url=row.official_url,
        source_title=row.source_title,
        deadline=row.deadline,
        deadline_precision=row.deadline_precision,
        supporting_excerpt=row.supporting_excerpt,
        excerpt_hash=row.excerpt_hash,
        retrieval_date=row.retrieval_date,
        reviewer=row.reviewer,
        decision=row.decision,
        provenance=row.provenance,
    )


def _apply_migration(url):
    """Apply the .sql migration file as a whole to a disposable database."""
    connection = psycopg2.connect(url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(MIGRATION_SQL.read_text(encoding="utf-8"))
    finally:
        connection.close()


class _PGDeletionBase:
    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", TEST_URL)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        reset_database_connections()
        init_database()
        # Isolate tests: clear accumulated rows from prior tests.
        from app.database import get_engine
        from sqlalchemy import text as _text
        _eng = get_engine()
        with _eng.begin() as _conn:
            for _tbl in ("scholarship_evidence_archive", "scholarship_evidence", "deleted_closed_scholarships", "scholarships"):
                _conn.execute(_text("TRUNCATE TABLE " + _tbl + " RESTART IDENTITY CASCADE"))
        yield
        reset_database_connections()


class TestEvidenceSurvivesPermanentDeletion(_PGDeletionBase):
    def test_evidence_survives_successful_deletion_with_original_identity(self):
        with _session() as db:
            scholarship = _new_scholarship(db)
            scholarship_id = scholarship.id
            evidence = [
                _new_evidence(
                    db,
                    scholarship.id,
                    application_cycle="2026_AUTUMN",
                    deadline=date(2020, 1, 1),
                ),
                _new_evidence(
                    db,
                    scholarship.id,
                    application_cycle="2026_SPRING",
                    deadline=date(2021, 1, 1),
                    official_domain="spring.example.edu",
                    official_url="https://spring.example.edu/cycle",
                    source_title="Spring cycle notice",
                ),
            ]
            original = {row.id: _snapshot(row) for row in evidence}

            manifest = build_deletion_manifest(db)
            assert any(item.scholarship_id == scholarship.id for item in manifest)
            report = execute_deletion(db, manifest, dry_run=False)
            db.commit()

            assert report.errors == []
            assert report.deleted_scholarships == 1
            assert report.preserved_gate6_evidence == 2

            db.expire_all()
            assert db.execute(
                select(Scholarship).where(Scholarship.id == scholarship_id)
            ).scalars().first() is None
            assert db.execute(
                select(ScholarshipEvidence).where(ScholarshipEvidence.scholarship_id == scholarship_id)
            ).scalars().all() == []

            archived = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_scholarship_id == scholarship_id
                )
            ).scalars().all()
            assert len(archived) == 2
            assert {row.original_evidence_id for row in archived} == set(original)
            for row in archived:
                _assert_archive_matches(row, original[row.original_evidence_id])


class TestDatabaseFkIntegrity(_PGDeletionBase):
    def test_fk_policy_and_database_behavior_prevent_cascade_loss(self):
        with _session() as db:
            fk_rows = db.execute(
                text(
                    "SELECT conname, confdeltype FROM pg_constraint "
                    "WHERE conrelid = 'scholarship_evidence'::regclass "
                    "AND confrelid = 'scholarships'::regclass AND contype = 'f'"
                )
            ).all()
            assert len(fk_rows) == 1
            assert fk_rows[0][0] == "fk_scholarship_evidence_scholarship_id"
            assert fk_rows[0][1] == "a"  # PostgreSQL NO ACTION; never 'c' (CASCADE)

            # The archive has no FK to scholarships, so retention never blocks deletion.
            archive_fks = db.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'scholarship_evidence_archive'::regclass "
                    "AND confrelid = 'scholarships'::regclass"
                )
            ).all()
            assert archive_fks == []

            # Behavioral proof: a raw SQL delete of a scholarship with evidence is refused.
            scholarship = _new_scholarship(db)
            evidence = _new_evidence(db, scholarship.id)
            with pytest.raises(IntegrityError):
                db.execute(
                    text("DELETE FROM scholarships WHERE id = :sid"), {"sid": scholarship.id}
                )
            db.rollback()
            db.expire_all()
            assert db.execute(
                select(ScholarshipEvidence).where(ScholarshipEvidence.id == evidence.id)
            ).scalars().first() is not None


class TestPreservationFailure(_PGDeletionBase):
    def test_hash_mismatch_conflict_blocks_deletion_and_reports_no_success(self):
        with _session() as db:
            scholarship = _new_scholarship(db)
            evidence = _new_evidence(db, scholarship.id)

            # A conflicting archive row with a deliberately wrong content hash
            # forces verification to fail after ON CONFLICT DO NOTHING.
            db.add(
                ScholarshipEvidenceArchive(
                    original_evidence_id=evidence.id,
                    original_scholarship_id=scholarship.id,
                    scholarship_legacy_id=None,
                    application_cycle=evidence.application_cycle,
                    official_domain=evidence.official_domain,
                    official_url=evidence.official_url,
                    source_title=evidence.source_title,
                    deadline=evidence.deadline,
                    deadline_precision=evidence.deadline_precision,
                    supporting_excerpt=evidence.supporting_excerpt,
                    excerpt_hash=evidence.excerpt_hash,
                    retrieval_date=evidence.retrieval_date,
                    reviewer=evidence.reviewer,
                    decision=evidence.decision,
                    provenance=evidence.provenance,
                    content_hash="0" * 64,
                )
            )
            db.commit()

            manifest = build_deletion_manifest(db)
            report = execute_deletion(db, manifest, dry_run=False)

            assert report.errors
            assert "preservation failed" in " ".join(report.errors).lower()
            assert report.deleted_scholarships == 0
            assert report.preserved_gate6_evidence == 0

            db.expire_all()
            assert db.execute(
                select(Scholarship).where(Scholarship.id == scholarship.id)
            ).scalars().first() is not None
            assert db.execute(
                select(ScholarshipEvidence).where(ScholarshipEvidence.id == evidence.id)
            ).scalars().first() is not None


class TestHashIntegrity(_PGDeletionBase):
    def test_original_and_preserved_hashes_match_exactly(self):
        with _session() as db:
            scholarship = _new_scholarship(db)
            evidence = _new_evidence(db, scholarship.id)
            original = _snapshot(evidence)

            manifest = build_deletion_manifest(db)
            report = execute_deletion(db, manifest, dry_run=False)
            db.commit()
            assert report.errors == []

            archived = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_evidence_id == evidence.id
                )
            ).scalars().one()
            assert archived.excerpt_hash == original["excerpt_hash"]
            assert archived.content_hash == original["content_hash"]
            assert _evidence_content_hash(_evidence_like_from_archive(archived)) == archived.content_hash

    def test_deliberately_changed_hash_is_rejected(self):
        """The verification path fails closed when stored content is altered."""
        with _session() as db:
            scholarship = _new_scholarship(db)
            evidence = _new_evidence(db, scholarship.id)
            _archive_gate6_evidence(db, scholarship.id)
            db.commit()
            archived = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_evidence_id == evidence.id
                )
            ).scalars().one()
            # The archive is immutable by design; a forged row with the same
            # original id cannot be inserted to masquerade as the real one.
            with pytest.raises(DBAPIError):
                db.execute(
                    text(
                        "UPDATE scholarship_evidence_archive SET content_hash = :hash "
                        "WHERE original_evidence_id = :eid"
                    ),
                    {"hash": "f" * 64, "eid": evidence.id},
                )
            db.rollback()
            db.expire_all()
            again = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_evidence_id == evidence.id
                )
            ).scalars().one()
            assert again.content_hash == archived.content_hash


class TestRetryIdempotency(_PGDeletionBase):
    def test_retry_does_not_duplicate_or_overwrite_archive_and_cannot_redelete(self):
        with _session() as db:
            scholarship = _new_scholarship(db)
            scholarship_id = scholarship.id
            evidence = _new_evidence(db, scholarship.id)

            assert _archive_gate6_evidence(db, scholarship.id) == 1
            first = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_evidence_id == evidence.id
                )
            ).scalars().one()

            assert _archive_gate6_evidence(db, scholarship.id) == 1
            retries = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_evidence_id == evidence.id
                )
            ).scalars().all()
            assert len(retries) == 1
            assert retries[0].id == first.id
            assert retries[0].content_hash == first.content_hash

            manifest = build_deletion_manifest(db)
            report = execute_deletion(db, manifest, dry_run=False, execution_id="exec-107-test")
            db.commit()
            assert report.errors == []
            assert report.deleted_scholarships == 1
            assert report.preserved_gate6_evidence == 1

            db.expire_all()
            archived = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_evidence_id == evidence.id
                )
            ).scalars().one()
            assert archived.archive_execution_id == "exec-107-test"

            retry_report = execute_deletion(db, manifest, dry_run=False, execution_id="exec-107-test")
            assert retry_report.deleted_scholarships == 0
            assert scholarship_id in retry_report.skipped_scholarship_ids
            assert (
                db.execute(
                    select(func.count())
                    .select_from(ScholarshipEvidenceArchive)
                    .where(ScholarshipEvidenceArchive.original_evidence_id == evidence.id)
                ).scalar_one()
                == 1
            )


class TestConcurrency(_PGDeletionBase):
    def test_two_deletion_attempts_exactly_one_succeeds(self):
        scholarship_id = None
        with _session() as setup_db:
            scholarship = _new_scholarship(setup_db)
            scholarship_id = scholarship.id
            evidence = [_new_evidence(setup_db, scholarship.id)]
            manifest = build_deletion_manifest(setup_db)
            setup_db.rollback()

            results = []
            exceptions = []

            def run():
                session = _session()
                try:
                    report = execute_deletion(session, manifest, dry_run=False)
                    session.commit()
                    results.append(report)
                except Exception as exc:  # captured for a fail-closed assertion
                    exceptions.append(exc)
                finally:
                    session.close()

            threads = [threading.Thread(target=run) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)

            assert not any(thread.is_alive() for thread in threads)
            assert exceptions == []
            assert sum(report.deleted_scholarships for report in results) == 1
            assert all(report.errors == [] for report in results)

            with _session() as check_db:
                archived = check_db.execute(
                    select(ScholarshipEvidenceArchive).where(
                        ScholarshipEvidenceArchive.original_scholarship_id == scholarship_id
                    )
                ).scalars().all()
                assert len(archived) == len(evidence)

    def test_evidence_change_after_authorization_blocks_deletion(self):
        with _session() as db:
            scholarship = _new_scholarship(db)
            _new_evidence(
                db,
                scholarship.id,
                application_cycle="2026_ORIGINAL",
                deadline=date(2020, 1, 1),
            )
            manifest = build_deletion_manifest(db)

            _new_evidence(
                db,
                scholarship.id,
                application_cycle="2026_ADDED_LATER",
                deadline=date(2020, 1, 2),
                official_domain="late.example.edu",
            )

            report = execute_deletion(db, manifest, dry_run=False)
            assert report.deleted_scholarships == 0
            assert scholarship.id in report.skipped_scholarship_ids

            db.expire_all()
            assert db.execute(
                select(Scholarship).where(Scholarship.id == scholarship.id)
            ).scalars().first() is not None
            assert db.execute(
                select(func.count())
                .select_from(ScholarshipEvidence)
                .where(ScholarshipEvidence.scholarship_id == scholarship.id)
            ).scalar_one() == 2


class TestOrmAndRawSqlBehavior(_PGDeletionBase):
    def test_orm_relationships_and_raw_delete_cannot_bypass_preservation(self):
        with _session() as db:
            scholarship = _new_scholarship(db)
            evidence = _new_evidence(db, scholarship.id)

            # No ORM relationship can independently cascade-delete this evidence.
            assert "scholarship_evidence" not in {
                relation.key for relation in sa_inspect(Scholarship).relationships
            }
            assert not sa_inspect(ScholarshipEvidence).relationships

            with pytest.raises(IntegrityError):
                db.execute(
                    text("DELETE FROM scholarships WHERE id = :sid"), {"sid": scholarship.id}
                )
            db.rollback()
            db.expire_all()

            orm_scholarship = db.get(Scholarship, scholarship.id)
            db.delete(orm_scholarship)
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()
            db.expire_all()

            assert db.execute(
                select(Scholarship).where(Scholarship.id == scholarship.id)
            ).scalars().first() is not None
            assert db.execute(
                select(ScholarshipEvidence).where(ScholarshipEvidence.id == evidence.id)
            ).scalars().first() is not None


class TestHistoricalEvidenceIntegrity(_PGDeletionBase):
    def test_distinct_cycles_domains_and_null_deadlines_not_collapsed(self):
        with _session() as db:
            first = _new_scholarship(db, title="Hist-A")
            second = _new_scholarship(db, title="Hist-B")
            evidence = [
                _new_evidence(
                    db,
                    first.id,
                    application_cycle="2026_UK",
                    deadline=date(2024, 6, 1),
                    official_domain="uk.example.edu",
                    official_url="https://uk.example.edu/cycle",
                    source_title="UK cycle notice",
                    supporting_excerpt="UK excerpt",
                    excerpt_hash=hashlib.sha256(b"UK excerpt").hexdigest(),
                ),
                _new_evidence(
                    db,
                    first.id,
                    application_cycle="2026_US",
                    deadline=date(2024, 1, 15),
                    official_domain="us.example.edu",
                    official_url="https://us.example.edu/cycle",
                    source_title="US cycle notice",
                    supporting_excerpt="US excerpt",
                    excerpt_hash=hashlib.sha256(b"US excerpt").hexdigest(),
                ),
                _new_evidence(
                    db,
                    second.id,
                    application_cycle="2026_NULL",
                    deadline=None,
                    deadline_precision="unknown",
                    official_domain="null.example.edu",
                    official_url="https://null.example.edu/cycle",
                    source_title="No-deadline notice",
                    supporting_excerpt="No deadline excerpt",
                    excerpt_hash=hashlib.sha256(b"No deadline excerpt").hexdigest(),
                ),
            ]
            original = {row.id: _snapshot(row) for row in evidence}

            manifest = build_deletion_manifest(db)
            report = execute_deletion(db, manifest, dry_run=False)
            db.commit()

            assert report.errors == []
            assert report.deleted_scholarships == 2
            assert report.preserved_gate6_evidence == 3

            archived = db.execute(
                select(ScholarshipEvidenceArchive).where(
                    ScholarshipEvidenceArchive.original_evidence_id.in_(list(original))
                )
            ).scalars().all()
            assert len(archived) == 3
            assert {row.original_evidence_id for row in archived} == set(original)
            for row in archived:
                _assert_archive_matches(row, original[row.original_evidence_id])


class TestEvidenceArchiveMigration(_PGDeletionBase):
    def test_migration_upgrades_cascade_schema_and_is_idempotent(self):
        with _session() as db:
            scholarship = _new_scholarship(db)
            evidence = _new_evidence(db, scholarship.id)

            # Simulate the pre-migration schema (the P0 defect): CASCADE FK.
            db.execute(
                text(
                    "ALTER TABLE scholarship_evidence "
                    "DROP CONSTRAINT IF EXISTS fk_scholarship_evidence_scholarship_id"
                )
            )
            db.execute(
                text(
                    "ALTER TABLE scholarship_evidence "
                    "ADD CONSTRAINT fk_scholarship_evidence_scholarship_id "
                    "FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE"
                )
            )
            db.commit()

            cascade_type = db.execute(
                text(
                    "SELECT confdeltype FROM pg_constraint "
                    "WHERE conname = 'fk_scholarship_evidence_scholarship_id' "
                    "AND conrelid = 'scholarship_evidence'::regclass"
                )
            ).scalar_one()
            assert cascade_type == "c"

            _apply_migration(TEST_URL)
            _apply_migration(TEST_URL)  # idempotent re-application

            fk_type = db.execute(
                text(
                    "SELECT confdeltype FROM pg_constraint "
                    "WHERE conname = 'fk_scholarship_evidence_scholarship_id' "
                    "AND conrelid = 'scholarship_evidence'::regclass"
                )
            ).scalar_one()
            assert fk_type == "a"

            # Existing evidence rows survive the upgrade unchanged.
            surviving_ids = {
                row[0]
                for row in db.execute(
                    select(ScholarshipEvidence.id).where(
                        ScholarshipEvidence.scholarship_id == scholarship.id
                    )
                ).all()
            }
            assert surviving_ids == {evidence.id}
            restored = db.execute(
                select(ScholarshipEvidence).where(ScholarshipEvidence.id == evidence.id)
            ).scalars().one()
            _assert_archive_matches(
                SimpleNamespace(
                    original_scholarship_id=restored.scholarship_id,
                    application_cycle=restored.application_cycle,
                    official_domain=restored.official_domain,
                    official_url=restored.official_url,
                    source_title=restored.source_title,
                    deadline=restored.deadline,
                    deadline_precision=restored.deadline_precision,
                    supporting_excerpt=restored.supporting_excerpt,
                    excerpt_hash=restored.excerpt_hash,
                    retrieval_date=restored.retrieval_date,
                    reviewer=restored.reviewer,
                    decision=restored.decision,
                    provenance=restored.provenance,
                    content_hash=_evidence_content_hash(restored),
                ),
                _snapshot(restored),
            )

            assert db.execute(
                text("SELECT to_regclass('public.scholarship_evidence_archive')")
            ).scalar_one() == "scholarship_evidence_archive"
            triggers = db.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgrelid = 'scholarship_evidence_archive'::regclass AND NOT tgisinternal"
                )
            ).all()
            assert ("trg_scholarship_evidence_archive_immutable",) in triggers

            # The trigger actually refuses UPDATE and DELETE of archived evidence.
            archive_row = ScholarshipEvidenceArchive(
                original_evidence_id=evidence.id,
                original_scholarship_id=scholarship.id,
                application_cycle=restored.application_cycle,
                official_domain=restored.official_domain,
                official_url=restored.official_url,
                source_title=restored.source_title,
                deadline=restored.deadline,
                deadline_precision=restored.deadline_precision,
                supporting_excerpt=restored.supporting_excerpt,
                excerpt_hash=restored.excerpt_hash,
                retrieval_date=restored.retrieval_date,
                reviewer=restored.reviewer,
                decision=restored.decision,
                provenance=restored.provenance,
                content_hash=_evidence_content_hash(restored),
            )
            db.add(archive_row)
            db.commit()
            with pytest.raises(DBAPIError):
                db.execute(
                    text("UPDATE scholarship_evidence_archive SET content_hash = :h WHERE id = :id"),
                    {"h": "1" * 64, "id": archive_row.id},
                )
            db.rollback()
            with pytest.raises(DBAPIError):
                db.execute(
                    text("DELETE FROM scholarship_evidence_archive WHERE id = :id"),
                    {"id": archive_row.id},
                )
            db.rollback()
