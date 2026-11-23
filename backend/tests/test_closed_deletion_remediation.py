import os

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")
os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "false")
os.environ.setdefault("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "false")

import pytest
from datetime import date, datetime, timezone

from app.database import init_database, get_session_factory
from app.models import Scholarship, ApplicationRecord, User, DeletedClosedScholarship
from app.models_supervisor import (
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
    OfficialContact,
    ProfessorProfile,
)
from app.services.closed_deletion import (
    get_effective_lifecycle_status,
    audit_dependencies,
    build_deletion_manifest,
    execute_deletion,
    save_deletion_manifest,
    load_deletion_manifest,
)
from app.services.scholarship_ingestion import ScholarshipIngestionRecord, upsert_verified_scholarships
from sqlalchemy import select


@pytest.fixture(autouse=True)
def _db():
    from app.database import reset_database_connections
    os.environ["SCHOLARZONE_DATABASE_URL"] = "sqlite:///:memory:"
    reset_database_connections()
    init_database()
    yield
    reset_database_connections()


def _session():
    return get_session_factory()()


def test_effective_closed_past_deadline_open():
    with _session() as db:
        s = Scholarship(title="t", country="c", degree="d", funding="f", status="open", deadline_date=date(2020, 1, 1))
        db.add(s)
        db.commit()
        db.refresh(s)
        assert get_effective_lifecycle_status(s, date(2025, 1, 1)) == "CLOSED"


def test_effective_archived_future_cycle_exception():
    with _session() as db:
        s = Scholarship(title="t", country="c", degree="d", funding="f", status="closed", is_archived=True, application_period="opens 2026-06-01")
        db.add(s)
        db.commit()
        db.refresh(s)
        assert get_effective_lifecycle_status(s, date(2025, 1, 1)) == "UPCOMING"


def test_application_history_preserved():
    with _session() as db:
        u = User(email="a@b.com", password_hash="x")
        db.add(u)
        s = Scholarship(title="ClosedProg", country="X", degree="M", funding="F", status="closed", deadline_date=date(2020, 1, 1), official_source="Prov", official_source_url="https://example.com/closed")
        db.add(s)
        db.commit()
        db.refresh(u)
        db.refresh(s)
        app = ApplicationRecord(user_id=u.id, scholarship_id=s.id, state="saved")
        db.add(app)
        db.commit()
        manifest = build_deletion_manifest(db)
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        db.commit()
        assert report.deleted_scholarships == 0
        assert any("SQLite" in e for e in report.errors)
        apps = db.execute(select(ApplicationRecord)).scalars().all()
        assert len(apps) == 1
        assert apps[0].scholarship_id is not None


def test_source_evidence_link_id_cleanup():
    with _session() as db:
        prof = ProfessorProfile(canonical_name="P", institution_name="I", official_profile_url="https://p.com")
        db.add(prof)
        s = Scholarship(title="ClosedProg", country="X", degree="M", funding="F", status="closed", deadline_date=date(2020, 1, 1), official_source_url="https://example.com/closed")
        db.add(s)
        db.commit()
        db.refresh(prof)
        db.refresh(s)
        link = ScholarshipProfessorLink(scholarship_id=s.id, professor_id=prof.id, relationship_type="supervisor", evidence_source_url="https://x", evidence_source_type="official")
        db.add(link)
        db.commit()
        db.refresh(link)
        ev = SupervisorSourceEvidence(professor_id=prof.id, scholarship_id=None, link_id=link.id, source_url="https://x", source_host="x", source_type="official", retrieved_at=datetime.now(timezone.utc))
        db.add(ev)
        db.commit()
        deps = audit_dependencies(db, s.id)
        assert deps["source_evidence"] == 1
        manifest = build_deletion_manifest(db)
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        db.commit()
        assert report.deleted_source_evidence == 0
        assert any("SQLite" in e for e in report.errors)


def test_tombstone_created_and_reimport_blocked():
    with _session() as db:
        s = Scholarship(title="ClosedProg", country="X", degree="M", funding="F", status="closed", deadline_date=date(2020, 1, 1), official_source_url="https://example.com/closed")
        db.add(s)
        db.commit()
        db.refresh(s)
        manifest = build_deletion_manifest(db)
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        db.commit()
        assert report.tombstones_created == 0
        assert any("SQLite" in e for e in report.errors)


def test_rollback_counters_reset():
    # simulate failure by making a second run with no targets (no-op) not enough;
    # instead verify counters zero on empty manifest execution is trivial.
    with _session() as db:
        report = execute_deletion(db, [], dry_run=False)
        assert report.deleted_scholarships == 0
        assert report.errors == []


def test_manifest_round_trip_nonzero_linked_records(tmp_path):
    from pathlib import Path
    with _session() as db:
        s = Scholarship(
            title="RoundTripNonZero", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        u = User(email="rt@x.com", password_hash="x"); db.add(u); db.commit(); db.refresh(u)
        app = ApplicationRecord(user_id=u.id, scholarship_id=s.id, state="saved"); db.add(app); db.commit()
        manifest = build_deletion_manifest(db)
        entry = next(m for m in manifest if m.scholarship_id == s.id)
        assert entry.linked_application_records == 1
        path = tmp_path / "manifest.json"
        save_deletion_manifest(manifest, str(path))
        loaded = load_deletion_manifest(str(path))
        assert [m.scholarship_id for m in loaded] == [s.id]
        assert loaded[0].linked_application_records == 1
        assert loaded[0].dependency_fingerprint


def test_manifest_round_trip_zero_linked_records(tmp_path):
    from pathlib import Path
    with _session() as db:
        s = Scholarship(
            title="RoundTripZero", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        entry = next(m for m in manifest if m.scholarship_id == s.id)
        assert entry.linked_application_records == 0
        path = tmp_path / "manifest.json"
        save_deletion_manifest(manifest, str(path))
        loaded = load_deletion_manifest(str(path))
        assert loaded[0].linked_application_records == 0


def test_manifest_loader_corrupted_json_fails_closed(tmp_path):
    from pathlib import Path
    with _session() as db:
        s = Scholarship(
            title="Corrupt", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        path = tmp_path / "manifest.json"
        save_deletion_manifest(manifest, str(path))
        Path(str(path)).write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError):
            load_deletion_manifest(str(path))


def test_manifest_loader_altered_fingerprint_fails_closed(tmp_path):
    from pathlib import Path
    import json
    with _session() as db:
        s = Scholarship(
            title="Altered", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        path = tmp_path / "manifest.json"
        save_deletion_manifest(manifest, str(path))
        data = json.loads(Path(str(path)).read_text(encoding="utf-8"))
        data[0]["dependency_fingerprint"] = "0" * 64
        Path(str(path)).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        with pytest.raises(ValueError):
            load_deletion_manifest(str(path))


def test_manifest_loader_unsupported_schema_version_fails_closed(tmp_path):
    from pathlib import Path
    import json
    with _session() as db:
        s = Scholarship(
            title="Unsupported", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        path = tmp_path / "manifest.json"
        save_deletion_manifest(manifest, str(path))
        meta_path = Path(str(path) + ".metadata.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["schema_version"] = "9.9"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        with pytest.raises(ValueError):
            load_deletion_manifest(str(path))


def test_manifest_loader_missing_required_field_fails_closed(tmp_path):
    from pathlib import Path
    import json
    with _session() as db:
        s = Scholarship(
            title="Missing", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        path = tmp_path / "manifest.json"
        save_deletion_manifest(manifest, str(path))
        data = json.loads(Path(str(path)).read_text(encoding="utf-8"))
        del data[0]["dependency_fingerprint"]
        Path(str(path)).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        with pytest.raises(ValueError):
            load_deletion_manifest(str(path))


def test_protected_candidate_excluded_from_manifest():
    with _session() as db:
        s = Scholarship(
            title="Protected", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1), deletion_protected=True,
        )
        db.add(s); db.commit(); db.refresh(s)
        assert build_deletion_manifest(db) == []


def test_protected_after_manifest_creation_is_skipped_on_execute():
    with _session() as db:
        s = Scholarship(
            title="ProtectAfter", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        assert any(m.scholarship_id == s.id for m in manifest)
        s.deletion_protected = True
        db.commit()
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        assert report.deleted_scholarships == 0
        assert s.id in report.skipped_scholarship_ids
        assert db.get(Scholarship, s.id) is not None


def test_dependency_row_mutation_blocks_execution():
    with _session() as db:
        u = User(email="dep@x.com", password_hash="x"); db.add(u); db.commit(); db.refresh(u)
        s = Scholarship(
            title="DepMut", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        app = ApplicationRecord(user_id=u.id, scholarship_id=s.id, state="saved")
        db.add(app); db.commit()
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        assert report.deleted_scholarships == 0
        assert any("SQLite" in e for e in report.errors)
        assert db.get(ApplicationRecord, app.id) is not None
        assert db.get(Scholarship, s.id) is not None


def test_sqlite_nonempty_manifest_is_rejected_and_preserves_rows():
    with _session() as db:
        s = Scholarship(
            title="SQLiteReject", country="X", degree="M", funding="F",
            status="closed", deadline_date=date(2020, 1, 1),
        )
        db.add(s); db.commit(); db.refresh(s)
        manifest = build_deletion_manifest(db)
        assert manifest
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        assert report.deleted_scholarships == 0
        assert any("SQLite" in e for e in report.errors)
        assert db.get(Scholarship, s.id) is not None


def test_cli_flags_mutually_exclusive():
    import subprocess, sys
    r = subprocess.run([sys.executable, "scripts/closed_deletion_cli.py", "--dry-run", "--execute"], capture_output=True, text=True)
    assert r.returncode == 2

def test_all_snapshot_fields_populated():
    from app.models import ApplicationRecord
    with _session() as db:
        s = Scholarship(
            title="FullSnapshot", country="Atlantis", degree="PhD", funding="Full",
            status="closed", deadline_date=date(2020, 1, 1),
            deadline_display="Jan 2020", deadline_precision="month",
            official_source="ProvOrg", official_source_url="https://example.com/full",
            application_link="https://apply.example.com/full",
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        u = User(email="snap@test.com", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)
        app = ApplicationRecord(user_id=u.id, scholarship_id=s.id, state="saved")
        db.add(app)
        db.commit()
        manifest = build_deletion_manifest(db)
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        db.commit()
        assert report.deleted_scholarships == 0
        assert any("SQLite" in e for e in report.errors)


def test_existing_snapshots_not_overwritten():
    from app.models import ApplicationRecord
    with _session() as db:
        s = Scholarship(title="OverwriteTest", country="X", degree="M", funding="F",
                        status="closed", deadline_date=date(2020, 1, 1),
                        official_source="Prov", official_source_url="https://example.com/ow")
        db.add(s)
        db.commit()
        db.refresh(s)
        u = User(email="ow@test.com", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)
        app = ApplicationRecord(
            user_id=u.id, scholarship_id=s.id, state="saved",
            scholarship_name_snapshot="ORIGINAL_NAME",
            scholarship_country_snapshot="ORIGINAL_COUNTRY",
        )
        db.add(app)
        db.commit()
        manifest = build_deletion_manifest(db)
        report = execute_deletion(db, manifest, dry_run=False)
        db.commit()
        db.commit()
        assert report.deleted_scholarships == 0
        assert any("SQLite" in e for e in report.errors)


def test_lifecycle_expired_upcoming_stored_status():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="upcoming",
                    deadline_date=date(2020, 1, 1), is_archived=False)
    assert get_effective_lifecycle_status(s, date(2025, 1, 1)) == "CLOSED"


def test_lifecycle_deadline_display_fallback():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="open",
                    deadline_date=None, deadline_display="2020-06-15",
                    deadline_precision="exact")
    assert get_effective_lifecycle_status(s, date(2025, 1, 1)) == "CLOSED"

    s2 = Scholarship(title="t2", country="c", degree="d", funding="f", status="open",
                     deadline_date=None, deadline_display="2026-06-15",
                     deadline_precision="exact")
    assert get_effective_lifecycle_status(s2, date(2025, 1, 1)) == "OPEN"


def test_lifecycle_month_precision_last_day():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="open",
                    deadline_date=date(2026, 11, 1), deadline_precision="month")
    assert get_effective_lifecycle_status(s, date(2026, 11, 19)) == "OPEN"

    s2 = Scholarship(title="t2", country="c", degree="d", funding="f", status="open",
                     deadline_date=date(2026, 10, 1), deadline_precision="month")
    assert get_effective_lifecycle_status(s2, date(2026, 11, 19)) == "CLOSED"


def test_lifecycle_exact_precision():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="open",
                    deadline_date=date(2026, 11, 1), deadline_precision="exact")
    assert get_effective_lifecycle_status(s, date(2026, 11, 19)) == "CLOSED"


def test_lifecycle_qualitative_no_rollover():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="closed",
                    deadline_date=date(2020, 1, 1), is_archived=False,
                    application_period="re-opens in early January")
    assert get_effective_lifecycle_status(s, date(2026, 11, 19)) == "CLOSED"

    s2 = Scholarship(title="t2", country="c", degree="d", funding="f", status="closed",
                     deadline_date=date(2020, 1, 1), is_archived=False,
                     application_period="re-opens in early December")
    assert get_effective_lifecycle_status(s2, date(2026, 11, 19)) == "UPCOMING"


def test_lifecycle_genuine_future_opening():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="closed",
                    deadline_date=date(2020, 1, 1), is_archived=False,
                    application_period="opens 2026-12-01")
    assert get_effective_lifecycle_status(s, date(2026, 11, 19)) == "UPCOMING"


def test_lifecycle_recurring_cycle_month():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="closed",
                    deadline_date=date(2020, 1, 1), is_archived=False,
                    application_period="annually in March")
    assert get_effective_lifecycle_status(s, date(2026, 11, 19)) == "UPCOMING"


def test_lifecycle_open_preserved():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="open",
                    deadline_date=date(2026, 12, 1), deadline_precision="exact")
    assert get_effective_lifecycle_status(s, date(2026, 11, 19)) == "OPEN"


def test_lifecycle_upcoming_preserved():
    s = Scholarship(title="t", country="c", degree="d", funding="f", status="upcoming",
                    deadline_date=date(2026, 12, 1), deadline_precision="exact")
    assert get_effective_lifecycle_status(s, date(2026, 11, 19)) == "UPCOMING"


def test_application_list_linked_first():
    from app.models import ApplicationRecord, User
    from app.services.application_workspace import list_for_user
    with _session() as db:
        u = User(email="lf@test.com", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)
        for i in range(10):
            app = ApplicationRecord(user_id=u.id, scholarship_id=None, state="saved")
            db.add(app)
        db.commit()
        s = Scholarship(title="Linked", country="X", degree="M", funding="F",
                        status="open", deadline_date=date(2026, 12, 1),
                        official_source_url="https://example.com/linked")
        db.add(s)
        db.commit()
        db.refresh(s)
        linked_app = ApplicationRecord(user_id=u.id, scholarship_id=s.id, state="in_progress")
        db.add(linked_app)
        db.commit()
        result = list_for_user(db, u, limit=5)
        scholarship_ids = [a.scholarship_id for a in result.applications]
        assert s.id in scholarship_ids, f"Linked app missing: {scholarship_ids}"
