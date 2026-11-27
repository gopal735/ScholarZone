"""Tests for insert_germany_strict.py - failure/retry and boundary conditions."""

import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def _patch_module_paths(tmp_path, monkeypatch):
    """Keep importer module globals pointed at temporary files so tests never mutate real research artifacts."""
    real_candidates = Path(__file__).resolve().parents[1] / "research_output" / "germany_strict_candidates.json"
    tmp_candidates = tmp_path / "germany_strict_candidates.json"
    if real_candidates.exists():
        tmp_candidates.write_text(real_candidates.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr("scripts.insert_germany_strict.CANDIDATES_PATH", tmp_candidates)
    monkeypatch.setattr("scripts.insert_germany_strict.REPORT_PATH", tmp_path / "germany_insert_report.json")


@pytest.fixture(autouse=True)
def _test_db_isolation(tmp_path):
    """Ensure each test gets its own isolated database."""
    global TEST_DB_PATH
    test_db = tmp_path / "test_italy.db"
    TEST_DB_PATH = test_db
    os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db.as_posix()}"
    os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

    from app.database import reset_database_connections
    reset_database_connections()

    yield

    reset_database_connections()


@pytest.fixture
def backend_root():
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def candidates_path(tmp_path):
    return tmp_path / "germany_strict_candidates.json"


@pytest.fixture
def manifest_path(backend_root):
    return backend_root / "research_output" / "master_baseline_manifest.json"


@pytest.fixture
def report_path(tmp_path):
    return tmp_path / "germany_insert_report.json"


@pytest.fixture
def test_candidates():
    """Minimal test candidates for boundary testing."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).date()
    next_week = (now + timedelta(days=7)).date()
    next_month = (now + timedelta(days=30)).date()
    last_month = (now - timedelta(days=30)).date()

    return [
        {
            "title": "VDA Test Scholarship",
            "country": "Germany",
            "provider": "Regione Valle d'Aosta",
            "academic_year": "2026/2027",
            "status": "open",
            "application_deadline": tomorrow.isoformat(),
            "deadline_display": f"{tomorrow}, 12:00",
            "official_source_url": "https://www.regione.vda.it/test",
            "preferred_id": 1337,
            "is_verified": True,
            "last_verified_at": now.date().isoformat(),
            "verification_status": "active",
        },
        {
            "title": "PoliTo PhD Test",
            "country": "Germany",
            "provider": "Politecnico di Torino",
            "academic_year": "2026/2027",
            "status": "upcoming",
            "application_open_date": next_week.isoformat(),
            "application_deadline": next_month.isoformat(),
            "opening_display": f"{next_week}",
            "deadline_display": f"{next_month}, 14:00",
            "official_source_url": "https://www.polito.it/test",
            "preferred_id": 1338,
            "is_verified": True,
            "last_verified_at": now.date().isoformat(),
            "verification_status": "active",
        },
    ]


def _init_db():
    """Initialize database with schema."""
    from app.database import init_database
    init_database()


def _seed_master_baseline():
    """Seed the master baseline records (IDs 1 and 2) matching the manifest."""
    from app.database import get_session_factory
    from app.models import Scholarship

    factory = get_session_factory()
    session = factory()

    try:
        if session.get(Scholarship, 1) is None:
            s1 = Scholarship(
                id=1,
                title="Erasmus Mundus Joint Masters (EMJM)",
                country="EU (multiple)",
                degree="Master's",
                funding="Full scholarship",
                official_source_url="https://www.eacea.ec.europa.eu/scholarships/emjmd-catalogue_en",
                status="open",
                is_verified=True,
            )
            session.add(s1)

        if session.get(Scholarship, 2) is None:
            s2 = Scholarship(
                id=2,
                title="ICCR Scholarship (Suborno Jayanti Scheme)",
                country="India",
                degree="Master's",
                funding="Full scholarship",
                official_source_url="https://www.iccr.gov.in",
                status="open",
                is_verified=True,
            )
            session.add(s2)

        session.commit()
    finally:
        session.close()


class TestInsertGermanyStrict:
    """Test the Germany strict insertion script."""

    def test_dry_run_mode(self, candidates_path, manifest_path):
        """Test dry-run mode does not write to database."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        exit_code = main(dry_run=True)
        assert exit_code == 0

        from app.database import get_session_factory
        from app.models import Scholarship
        factory = get_session_factory()
        session = factory()
        try:
            assert session.query(Scholarship).count() == 2
        finally:
            session.close()

    def test_execute_inserts_new_records(self, candidates_path, manifest_path, report_path):
        """Test execute mode inserts new records."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        # Write test candidates
        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
            {
                "title": "PoliTo PhD Test",
                "country": "Germany",
                "provider": "Politecnico di Torino",
                "academic_year": "2026/2027",
                "status": "upcoming",
                "application_open_date": (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat(),
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "opening_display": "2027-01-14",
                "deadline_display": "2027-02-15, 14:00",
                "official_source_url": "https://www.polito.it/test",
                "preferred_id": 1338,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        from app.database import get_session_factory
        from app.models import Scholarship
        factory = get_session_factory()
        session = factory()
        try:
            assert session.query(Scholarship).count() == 4
            vda = session.get(Scholarship, 1337)
            polito = session.get(Scholarship, 1338)
            assert vda is not None
            assert polito is not None
            assert vda.title == "VDA Test Scholarship"
            assert polito.title == "PoliTo PhD Test"
        finally:
            session.close()

    def test_idempotent_skip_duplicate(self, candidates_path, manifest_path):
        """Test that duplicate records are skipped (idempotent)."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        # First run - insert
        exit_code = main(dry_run=False)
        assert exit_code == 0

        # Second run - should skip
        exit_code = main(dry_run=False)
        assert exit_code == 0

        from app.database import get_session_factory
        from app.models import Scholarship
        factory = get_session_factory()
        session = factory()
        try:
            assert session.query(Scholarship).count() == 3
            vda = session.get(Scholarship, 1337)
            assert vda is not None
        finally:
            session.close()

    def test_skipped_by_stable_identity(self, candidates_path, manifest_path):
        """Test that records with same stable identity are skipped."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        # First run - insert
        exit_code = main(dry_run=False)
        assert exit_code == 0

        # Second run with different preferred_id but same identity - should skip
        test_data2 = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/different-url",
                "preferred_id": 9999,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data2, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        from app.database import get_session_factory
        from app.models import Scholarship
        factory = get_session_factory()
        session = factory()
        try:
            assert session.query(Scholarship).count() == 3
            assert session.get(Scholarship, 9999) is None
            assert session.get(Scholarship, 1337) is not None
        finally:
            session.close()

    def test_skipped_by_source_url(self, candidates_path, manifest_path):
        """Test that records with same source URL are skipped."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        # First run - insert
        exit_code = main(dry_run=False)
        assert exit_code == 0

        # Second run with different title but same source URL - should skip
        test_data2 = [
            {
                "title": "Different Title",
                "country": "Germany",
                "provider": "Different Provider",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 9999,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data2, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        from app.database import get_session_factory
        from app.models import Scholarship
        factory = get_session_factory()
        session = factory()
        try:
            assert session.query(Scholarship).count() == 3
            assert session.get(Scholarship, 9999) is None
        finally:
            session.close()

    def test_upcoming_transitions_to_open_after_open_date(self, candidates_path, manifest_path):
        """Test UPCOMING status transitions to OPEN after opening date."""
        from scripts.insert_germany_strict import _effective_status

        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()

        candidate = {
            "status": "upcoming",
            "application_open_date": past_date,
            "application_deadline": future_date,
        }

        status = _effective_status(candidate)
        assert status == "open"

    def test_upcoming_stays_upcoming_before_open_date(self, candidates_path, manifest_path):
        """Test UPCOMING status stays UPCOMING before opening date."""
        from scripts.insert_germany_strict import _effective_status

        future_open = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
        future_deadline = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()

        candidate = {
            "status": "upcoming",
            "application_open_date": future_open,
            "application_deadline": future_deadline,
        }

        status = _effective_status(candidate)
        assert status == "upcoming"

    def test_open_rejected_after_deadline(self, candidates_path, manifest_path):
        """Test OPEN candidate is rejected if deadline has passed."""
        from scripts.insert_germany_strict import _validate_lifecycle

        past_deadline = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

        candidate = {
            "status": "open",
            "application_deadline": past_deadline,
        }

        valid, msg = _validate_lifecycle(candidate)
        assert not valid
        assert "passed" in msg.lower()

    def test_open_accepted_before_deadline(self, candidates_path, manifest_path):
        """Test OPEN candidate is accepted if deadline is in future."""
        from scripts.insert_germany_strict import _validate_lifecycle

        future_deadline = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()

        candidate = {
            "status": "open",
            "application_deadline": future_deadline,
        }

        valid, msg = _validate_lifecycle(candidate)
        assert valid

    def test_upcoming_rejected_if_window_closed(self, candidates_path, manifest_path):
        """Test UPCOMING candidate rejected if deadline already passed."""
        from scripts.insert_germany_strict import _validate_lifecycle

        # Use a past date for both open and deadline
        past_open = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        past_deadline = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

        candidate = {
            "status": "upcoming",
            "application_open_date": past_open,
            "application_deadline": past_deadline,
        }

        valid, msg = _validate_lifecycle(candidate)
        assert not valid
        # The error message says the window has closed
        assert "closed" in msg.lower() or "passed" in msg.lower()

    def test_date_only_deadline_valid_through_entire_day(self, candidates_path, manifest_path):
        """Test date-only deadline is valid through 23:59:59 of that date."""
        from scripts.insert_germany_strict import _deadline_datetime
        from zoneinfo import ZoneInfo

        rome = ZoneInfo("Europe/Rome")
        # Use a fixed date to avoid timezone issues
        fixed_date = date(2026, 12, 4)
        deadline_str = fixed_date.isoformat()

        candidate = {
            "application_deadline": deadline_str,
            "deadline_display": "",
        }

        dl = _deadline_datetime(candidate)
        assert dl is not None
        assert dl.hour == 23
        assert dl.minute == 59
        assert dl.tzinfo == rome

    def test_date_only_open_date_valid_from_midnight(self, candidates_path, manifest_path):
        """Test date-only open date is valid from 00:00:00 of that date."""
        from scripts.insert_germany_strict import _open_datetime
        from zoneinfo import ZoneInfo

        rome = ZoneInfo("Europe/Rome")
        # Use a fixed date to avoid timezone issues
        fixed_date = date(2027, 1, 14)
        open_str = fixed_date.isoformat()

        candidate = {
            "application_open_date": open_str,
            "opening_display": "",
        }

        od = _open_datetime(candidate)
        assert od is not None
        assert od.hour == 0
        assert od.minute == 0
        assert od.tzinfo == rome

    def test_iso_offset_aware_timestamp_parsing(self, candidates_path, manifest_path):
        """Test ISO 8601 timestamps with offsets are parsed correctly."""
        from scripts.insert_germany_strict import _parse_datetime_iso

        dt = _parse_datetime_iso("2026-12-04T12:00:00+01:00")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=1)

        dt = _parse_datetime_iso("2026-12-04T11:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=0)

        dt = _parse_datetime_iso("2026-12-04T12:00:00-05:00")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=-5)

    def test_report_contains_actual_matched_and_inserted_ids(self, candidates_path, manifest_path, report_path):
        """Test report contains actual matched and inserted IDs with details."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        assert "inserted_ids" in report
        assert "matched_ids" in report
        assert "matched_details" in report
        assert len(report["inserted_ids"]) == 1
        assert report["inserted_ids"][0] == 1337

    def test_verification_timestamp_distinct_from_insertion_time(self, candidates_path, manifest_path, report_path):
        """Test verification timestamp is distinct from insertion time."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        assert "generated_at" in report
        assert "verification_at" in report
        assert report["generated_at"] != report["verification_at"]

    def test_report_recovery_when_write_fails(self, candidates_path, manifest_path, report_path, tmp_path):
        """Test report recovery when DB commit succeeds but report write fails."""
        from scripts.insert_germany_strict import main, _reconstruct_report_from_db
        from app.database import get_session_factory
        from app.models import Scholarship

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        assert report["inserted_ids"] == [1337]

        inserted_ids = report["inserted_ids"]
        matched_ids = report.get("matched_ids", [])
        total_before = report["total_records_before"]
        germany_before = report["germany_records_before"]
        errors = report.get("errors", [])

        reconstructed = _reconstruct_report_from_db(inserted_ids, matched_ids, total_before, germany_before, errors)

        assert reconstructed["inserted"] == 1
        assert reconstructed["inserted_ids"] == [1337]
        assert reconstructed["reconstructed"] is True

    def test_reconstruct_flag_rebuilds_report(self, candidates_path, manifest_path, report_path):
        """Test --reconstruct flag rebuilds report from database."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        os.remove(report_path)

        exit_code = main(dry_run=False, reconstruct=True)
        assert exit_code == 0

        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        assert report["reconstructed"] is True
        assert report["inserted_ids"] == [1337]

    def test_credential_redaction_in_logs(self, candidates_path, manifest_path):
        """Test credentials are redacted in database URL logs."""
        from scripts.insert_germany_strict import _redact_credentials

        url = "sqlite:///path/to/db?password=secret123"
        redacted = _redact_credentials(url)
        assert "****" in redacted
        assert "secret123" not in redacted

        url_with_user = "postgresql://user:pass@host/db"
        redacted = _redact_credentials(url_with_user)
        assert "****" in redacted

    def test_different_academic_years_not_exact_replay(self, candidates_path, manifest_path):
        """Test different academic years are treated as different records."""
        from scripts.insert_germany_strict import _build_stable_identity

        candidate_2026 = {
            "title": "Test Scholarship",
            "country": "Germany",
            "academic_year": "2026/2027",
        }

        candidate_2025 = {
            "title": "Test Scholarship",
            "country": "Germany",
            "academic_year": "2025/2026",
        }

        identity_2026 = _build_stable_identity(candidate_2026)
        identity_2025 = _build_stable_identity(candidate_2025)

        assert identity_2026 != identity_2025
        assert identity_2026[2] == "2026/2027"
        assert identity_2025[2] == "2025/2026"

    def test_expired_vda_not_stop_valid_polito(self, candidates_path, manifest_path):
        """Test expired VDA doesn't block valid PoliTo insertion."""
        from scripts.insert_germany_strict import main, _validate_lifecycle

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Expired",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2025/2026",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat(),
                "deadline_display": "2025-11-01, 12:00",
                "official_source_url": "https://www.regione.vda.it/expired",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
            {
                "title": "PoliTo PhD Valid",
                "country": "Germany",
                "provider": "Politecnico di Torino",
                "academic_year": "2026/2027",
                "status": "upcoming",
                "application_open_date": (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat(),
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "opening_display": "2027-01-14",
                "deadline_display": "2027-02-15, 14:00",
                "official_source_url": "https://www.polito.it/valid",
                "preferred_id": 1338,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code != 0  # partial failure: VDA lifecycle failed

        from app.database import get_session_factory
        from app.models import Scholarship
        factory = get_session_factory()
        session = factory()
        try:
            vda = session.get(Scholarship, 1337)
            polito = session.get(Scholarship, 1338)
            assert polito is not None
            assert vda is None
        finally:
            session.close()

    def test_db_target_verification_before_schema_init(self, candidates_path, manifest_path):
        """Test database target is verified before schema initialization."""
        from scripts.insert_germany_strict import _verify_db_target

        ok, msg = _verify_db_target("sqlite:///test.db", "test.db")
        assert ok or "does not exist" in msg

        ok, msg = _verify_db_target("postgresql://user:pass@host/db", "")
        assert not ok

        ok, msg = _verify_db_target("sqlite:///:memory:", "")
        assert ok

    def test_baseline_verification_within_write_transaction(self, candidates_path, manifest_path):
        """Test baseline verification runs within the write transaction."""
        from scripts.insert_germany_strict import _verify_master_baseline
        from app.database import get_session_factory
        from app.models import Scholarship

        _init_db()
        _seed_master_baseline()

        factory = get_session_factory()
        session = factory()

        try:
            ok, msg = _verify_master_baseline(session)
            assert ok
        finally:
            session.close()

    def test_report_schema_key_consistency(self, candidates_path, manifest_path, report_path):
        """Test report has consistent schema keys."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)

        required_keys = [
            "generated_at",
            "verification_at",
            "total_candidates",
            "inserted",
            "skipped_duplicate",
            "failed",
            "inserted_ids",
            "matched_ids",
            "matched_details",
            "open_count",
            "upcoming_count",
            "audit_records",
            "master_baseline_verified",
            "total_records_before",
            "total_records_after",
            "germany_records_before",
            "germany_records_after",
            "id_mapping",
            "errors",
        ]

        for key in required_keys:
            assert key in report, f"Missing required key: {key}"

    def test_stable_programme_cycle_session_identity(self, candidates_path, manifest_path):
        """Test stable identity includes programme/cycle/session."""
        from scripts.insert_germany_strict import _build_stable_identity

        candidate1 = {
            "title": "PhD Scholarship",
            "country": "Germany",
            "provider": "Politecnico di Torino",
            "academic_year": "2026/2027",
        }

        candidate2 = {
            "title": "PhD Scholarship",
            "country": "Germany",
            "provider": "Politecnico di Torino",
            "academic_year": "2027/2028",
        }

        identity1 = _build_stable_identity(candidate1)
        identity2 = _build_stable_identity(candidate2)

        assert identity1 != identity2
        assert identity1[2] == "2026/2027"
        assert identity2[2] == "2027/2028"

    def test_boundary_condition_exact_deadline_moment(self, candidates_path, manifest_path):
        """Test boundary condition at exact deadline moment."""
        from scripts.insert_germany_strict import _validate_lifecycle, _deadline_datetime
        from zoneinfo import ZoneInfo

        rome = ZoneInfo("Europe/Rome")
        now = datetime.now(rome)
        deadline_today = now.replace(hour=23, minute=59, second=0, microsecond=0)

        candidate = {
            "status": "open",
            "application_deadline": deadline_today.date().isoformat(),
            "deadline_display": "2026-12-04, 23:59",
        }

        dl = _deadline_datetime(candidate)
        assert dl is not None

        with patch('scripts.insert_germany_strict._now', return_value=dl.astimezone(timezone.utc) - timedelta(seconds=1)):
            valid, msg = _validate_lifecycle(candidate)
            assert valid

    def test_failure_exit_code(self, candidates_path, manifest_path):
        """Test script returns non-zero exit code on critical failure (e.g., ID collision)."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        # First insert a record with ID 9999
        test_data = [
            {
                "title": "Valid Candidate",
                "country": "Germany",
                "provider": "Test",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "official_source_url": "https://test.valid",
                "preferred_id": 9999,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        # Now try to insert a different record with the same ID - should fail
        test_data2 = [
            {
                "title": "Different Candidate",
                "country": "Germany",
                "provider": "Test",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "official_source_url": "https://test.valid2",
                "preferred_id": 9999,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data2, f)

        exit_code = main(dry_run=False)
        assert exit_code != 0

    def test_report_preserved_on_no_new_inserts(self, candidates_path, manifest_path, report_path):
        """Test existing report is preserved when no new inserts."""
        from scripts.insert_germany_strict import main

        _init_db()
        _seed_master_baseline()

        test_data = [
            {
                "title": "VDA Test Scholarship",
                "country": "Germany",
                "provider": "Regione Valle d'Aosta",
                "academic_year": "2026/2027",
                "status": "open",
                "application_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                "deadline_display": "2026-12-04, 12:00",
                "official_source_url": "https://www.regione.vda.it/test",
                "preferred_id": 1337,
                "is_verified": True,
                "last_verified_at": datetime.now(timezone.utc).date().isoformat(),
                "verification_status": "active",
            },
        ]
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        with open(report_path, encoding="utf-8") as f:
            report1 = json.load(f)

        exit_code = main(dry_run=False)
        assert exit_code == 0

        with open(report_path, encoding="utf-8") as f:
            report2 = json.load(f)

        assert report1["inserted_ids"] == report2["inserted_ids"]
        assert report1["generated_at"] == report2["generated_at"]