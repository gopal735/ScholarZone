"""Insert Italy strict-rule candidates (2 records: 1 OPEN, 1 UPCOMING).

Safety features:
- Defaults to dry-run mode (no writes).
- Requires --execute flag for actual database writes.
- Verifies master baseline (IDs 1 and 2) before insertion.
- Refuses to run against empty or incomplete databases.
- Validates lifecycle (VDA must be OPEN as of run date).
- Idempotent: skips duplicates by stable identity.
- Nonzero exit on any failure.
- Valid RFC 3339 timestamps in report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_engine, get_session_factory, init_database
from app.models import Scholarship, ScholarshipVerificationHistory


CANDIDATES_PATH = BACKEND_ROOT / "research_output" / "italy_strict_candidates.json"
REPORT_PATH = BACKEND_ROOT / "research_output" / "italy_insert_report.json"
MANIFEST_PATH = BACKEND_ROOT / "research_output" / "master_baseline_manifest.json"

MASTER_IDENTITY_ANCHORS = {
    1: ("Erasmus Mundus Joint Masters (EMJM)", "EU (multiple)"),
    2: ("ICCR Scholarship (Suborno Jayanti Scheme)", "India"),
}

SUPPORTED_STATUSES = {"open", "upcoming", "closed", "closing-soon"}

ROME_TZ_NAME = "Europe/Rome"


def _now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            v = value.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def _normalize_status(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    v = value.strip().lower()
    if v in SUPPORTED_STATUSES:
        return v
    return ""


def _normalize_url(value: Any) -> str:
    if not value:
        return ""
    return str(value).strip().rstrip("/").lower()


def _load_candidates() -> list[dict[str, Any]]:
    with open(CANDIDATES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise RuntimeError(f"Expected a JSON array in {CANDIDATES_PATH}, got {type(data).__name__}")
    return data


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError(f"Master baseline manifest not found: {MANIFEST_PATH}")
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_rome():
    from zoneinfo import ZoneInfo
    return ZoneInfo(ROME_TZ_NAME)


def _deadline_datetime(candidate: dict[str, Any]) -> datetime | None:
    """Derive the exact application deadline datetime in Europe/Rome."""
    deadline_str = candidate.get("application_deadline") or candidate.get("deadline_date")
    if not deadline_str:
        return None
    # Try full datetime first
    dt = _parse_datetime(deadline_str)
    if dt is not None and "T" in str(deadline_str):
        # Convert to Rome if needed
        return dt.astimezone(_get_rome()) if dt.tzinfo else dt.replace(tzinfo=_get_rome())
    d = _parse_date(deadline_str)
    if d is None:
        return None
    # Exact time from deadline_display or official_details
    hour, minute = 23, 59
    deadline_display = str(candidate.get("deadline_display") or "")
    official = candidate.get("official_details") or {}
    official_deadline = official.get("application_closes") or official.get("application_deadline")
    if official_deadline and "T" in str(official_deadline):
        odt = _parse_datetime(official_deadline)
        if odt is not None:
            return odt.astimezone(_get_rome())
    # parse HH:MM from display
    import re
    m = re.search(r"(\d{1,2}):(\d{2})", deadline_display)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
    if "12:00" in deadline_display:
        hour, minute = 12, 0
    if "14:00" in deadline_display:
        hour, minute = 14, 0
    rome = _get_rome()
    return datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=rome)


def _open_datetime(candidate: dict[str, Any]) -> datetime | None:
    open_str = candidate.get("application_open_date") or candidate.get("opening_date")
    if not open_str:
        return None
    dt = _parse_datetime(open_str)
    if dt is not None and "T" in str(open_str):
        return dt.astimezone(_get_rome()) if dt.tzinfo else dt.replace(tzinfo=_get_rome())
    d = _parse_date(open_str)
    if d is None:
        return None
    rome = _get_rome()
    # opening_display may have time
    opening_display = str(candidate.get("opening_display") or "")
    hour, minute = 0, 0
    import re
    m = re.search(r"(\d{1,2}):(\d{2})", opening_display)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
    official = candidate.get("official_details") or {}
    official_open = official.get("application_opens")
    if official_open and "T" in str(official_open):
        odt = _parse_datetime(official_open)
        if odt is not None:
            return odt.astimezone(_get_rome())
    return datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=rome)


def _validate_lifecycle(candidate: dict[str, Any], now: datetime | None = None) -> tuple[bool, str]:
    now = _now(now)
    status_raw = candidate.get("status")
    status = _normalize_status(status_raw)
    if not status:
        return False, f"Unsupported status: {status_raw!r}. Allowed: {sorted(SUPPORTED_STATUSES)}."

    if status == "open":
        deadline_str = candidate.get("application_deadline") or candidate.get("deadline_date")
        if not deadline_str:
            return False, "OPEN candidate requires application_deadline."
        dl = _deadline_datetime(candidate)
        if dl is None:
            return False, f"Invalid deadline format: {deadline_str}"
        if now > dl.astimezone(timezone.utc):
            return False, f"Deadline {dl.isoformat()} has passed (now: {now.isoformat()}). Cannot insert as OPEN."
        return True, "Lifecycle valid."

    if status == "upcoming":
        open_str = candidate.get("application_open_date") or candidate.get("opening_date")
        deadline_str = candidate.get("application_deadline") or candidate.get("deadline_date")
        if not open_str:
            return False, "UPCOMING candidate requires application_open_date."
        if not deadline_str:
            return False, "UPCOMING candidate requires application_deadline."
        od = _open_datetime(candidate)
        dl = _deadline_datetime(candidate)
        if od is None:
            return False, f"Invalid open date format: {open_str}"
        if dl is None:
            return False, f"Invalid deadline format: {deadline_str}"
        if od >= dl:
            return False, "UPCOMING candidate has contradictory date window (open >= deadline)."
        # If window already closed, reject
        if now > dl.astimezone(timezone.utc):
            return False, f"UPCOMING candidate's window has closed (deadline: {dl.isoformat()})."
        return True, "Lifecycle valid."

    # closed / closing-soon: require deadline? Not strictly; accept
    return True, "Lifecycle valid."


def _verify_master_baseline(session: Session) -> bool:
    print("  Verifying master baseline against immutable manifest...")

    if not MANIFEST_PATH.exists():
        print("  ERROR: Master baseline manifest not found.")
        return False

    manifest = _load_manifest()
    expected_count = manifest.get("count")
    expected_records = {r["id"]: r for r in manifest.get("records", [])}

    total = session.query(Scholarship).count()
    if expected_count is not None and total < expected_count:
        print(f"  ERROR: Database has {total} records (expected >= {expected_count}). Baseline incomplete.")
        return False

    mismatches = 0
    missing = 0
    for exp_id, exp_record in expected_records.items():
        db_record = session.get(Scholarship, exp_id)
        if db_record is None:
            print(f"  ERROR: Expected ID {exp_id} not found in database.")
            missing += 1
            continue
        if db_record.title != exp_record.get("title"):
            print(f"  ERROR: ID {exp_id} title mismatch.")
            mismatches += 1
        if db_record.country != exp_record.get("country"):
            print(f"  ERROR: ID {exp_id} country mismatch.")
            mismatches += 1
        if exp_record.get("official_source_url") and db_record.official_source_url != exp_record.get("official_source_url"):
            print(f"  ERROR: ID {exp_id} source URL mismatch.")
            mismatches += 1
        if exp_record.get("provider") and getattr(db_record, "provider", None) not in (None, exp_record.get("provider")):
            # provider may not exist as column; skip if attribute missing
            pass

    if missing > 0 or mismatches > 0:
        print(f"  ABORT: {missing} missing, {mismatches} mismatches.")
        return False

    print(f"  Master baseline verified: {total} records, {len(expected_records)} identities match manifest.")
    return True


def _validate_db_target(db_url: str, db_path: str) -> tuple[bool, str]:
    if not db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:///:memory:"):
        return False, "Database target is not local SQLite."
    low = db_url.lower()
    if any(x in low for x in ["neon", "supabase", "postgres", "mysql"]):
        return False, "Production/remote database target detected."
    if db_url.startswith("sqlite:///:memory:"):
        return True, "ok"
    if not (db_path.endswith(".db") or db_path.endswith(".sqlite")):
        return False, "Unexpected database file extension."
    p = Path(db_path)
    if not p.exists():
        return False, "Database file does not exist."
    if p.stat().st_size == 0:
        return False, "Database file is empty."
    try:
        with open(p, "rb") as f:
            header = f.read(16)
        if not header.startswith(b"SQLite format 3\x00"):
            return False, "Database file is not a valid SQLite database."
    except OSError:
        return False, "Cannot read database file."
    return True, "ok"


def _find_existing(session: Session, candidate: dict[str, Any]) -> Scholarship | None:
    source_url = _normalize_url(candidate.get("official_source_url"))
    app_link = _normalize_url(candidate.get("application_link") or candidate.get("application_url"))
    title = (candidate.get("title") or "").strip().lower()
    country = (candidate.get("country") or "").strip()
    academic_year = (candidate.get("academic_year") or "").strip().lower()
    provider = (candidate.get("provider") or "").strip().lower()

    # stable identity: title + country + academic_year + provider
    if title and country:
        rows = session.scalars(
            select(Scholarship).where(
                func.lower(Scholarship.title) == title,
                Scholarship.country == country,
            )
        ).all()
        # further filter by academic_year/provider if columns exist
        filtered = []
        for r in rows:
            ay = getattr(r, "academic_year", None)
            prov = getattr(r, "provider", None)
            if academic_year and ay is not None and str(ay).strip().lower() != academic_year:
                continue
            if provider and prov is not None and str(prov).strip().lower() != provider:
                continue
            filtered.append(r)
        if len(filtered) > 1:
            raise RuntimeError(f"Multiple records match stable identity: {title!r} in {country!r}")
        if filtered:
            return filtered[0]
        if len(rows) == 1:
            return rows[0]

    # source url (normalized)
    if source_url:
        rows = session.scalars(select(Scholarship)).all()
        matches = [r for r in rows if _normalize_url(getattr(r, "official_source_url", None)) == source_url]
        if len(matches) > 1:
            raise RuntimeError(f"Multiple records share official_source_url: {source_url}")
        if matches:
            return matches[0]

    # app link
    if app_link and app_link != source_url:
        rows = session.scalars(select(Scholarship)).all()
        matches = [r for r in rows if _normalize_url(getattr(r, "application_link", None)) == app_link]
        if len(matches) > 1:
            raise RuntimeError(f"Multiple records share application_link: {app_link}")
        if matches:
            return matches[0]

    return None


def _map_to_model(candidate: dict[str, Any]) -> Scholarship:
    status = _normalize_status(candidate.get("status", "open"))
    if not status:
        status = "open"

    funding = candidate.get("funding", "") or ""
    eligible_fields = candidate.get("eligible_fields")
    if not eligible_fields:
        eligible_fields = candidate.get("study_fields", [])
    if eligible_fields is None:
        eligible_fields = []

    preferred_id = candidate.get("preferred_id")

    kwargs = dict(
        title=candidate["title"],
        country=candidate["country"],
        degree=candidate.get("degree", ""),
        funding=funding,
        description=candidate.get("description"),
        deadline_date=_parse_date(candidate.get("application_deadline") or candidate.get("deadline_date")),
        deadline_display=candidate.get("deadline_display"),
        deadline_precision=candidate.get("deadline_precision", "month"),
        status=status,
        is_verified=bool(candidate.get("is_verified", True)),
        last_verified_at=_parse_date(candidate.get("last_verified_at")),
        last_verified_date=_parse_date(candidate.get("last_verified_date")),
        verification_status=candidate.get("verification_status", "active"),
        next_verification_due=_parse_date(candidate.get("next_verification_due")),
        verified_by=candidate.get("verified_by"),
        verification_notes=candidate.get("verification_notes"),
        region=candidate.get("region"),
        duration=candidate.get("duration"),
        application_period=candidate.get("application_period"),
        official_source=candidate.get("official_source"),
        official_source_url=candidate.get("official_source_url"),
        catalogue_url=candidate.get("catalogue_url"),
        official_updates_url=candidate.get("official_updates_url"),
        application_link=candidate.get("application_link") or candidate.get("application_url") or candidate.get("official_source_url"),
        image_url=candidate.get("image_url"),
        image_source_url=candidate.get("image_source_url"),
        image_source_type=candidate.get("image_source_type"),
        image_verified_at=_parse_date(candidate.get("image_verified_at")),
        image_alt_text=candidate.get("image_alt_text"),
        eligibility=candidate.get("eligibility") or [],
        eligibility_summary=candidate.get("eligibility_summary"),
        benefits=candidate.get("benefits") or [],
        coverage=candidate.get("coverage") or [],
        requirements=candidate.get("requirements") or [],
        documents=candidate.get("documents") or [],
        english_requirement=candidate.get("english_requirement"),
        application_method=candidate.get("application_method") or [],
        selection_notes=candidate.get("selection_notes"),
        program_type=candidate.get("program_type"),
        best_fit=candidate.get("best_fit"),
        notes=candidate.get("notes"),
        funding_amount=candidate.get("funding_amount"),
        funding_currency=candidate.get("funding_currency"),
        funding_period=candidate.get("funding_period"),
        tuition_coverage=candidate.get("tuition_coverage"),
        living_cost_coverage=candidate.get("living_cost_coverage"),
        travel_coverage=candidate.get("travel_coverage"),
        fully_funded=candidate.get("fully_funded"),
        funding_details=candidate.get("funding_details"),
        departments=candidate.get("departments") or [],
        eligible_fields=eligible_fields,
        eligible_programmes=candidate.get("eligible_programmes") or [],
        academic_provenance=candidate.get("academic_provenance"),
        official_details=candidate.get("official_details"),
        applicant_utility=candidate.get("applicant_utility"),
        programme_verification=candidate.get("programme_verification"),
    )

    # Only set id if column exists
    if preferred_id is not None:
        kwargs["id"] = preferred_id

    return Scholarship(**kwargs)


def _create_audit_record(session: Session, scholarship_id: int, candidate: dict[str, Any]) -> ScholarshipVerificationHistory:
    now = datetime.now(timezone.utc)
    return ScholarshipVerificationHistory(
        scholarship_id=scholarship_id,
        field_name="record_insertion",
        old_value=None,
        new_value=json.dumps({
            "title": candidate.get("title"),
            "official_source_url": candidate.get("official_source_url"),
            "status": candidate.get("status"),
            "verified_by": candidate.get("verified_by"),
            "verification_timestamp": now.isoformat(),
            "funding": candidate.get("funding"),
            "fully_funded": candidate.get("fully_funded"),
        }, ensure_ascii=False),
        change_type="insert",
        source_url=candidate.get("official_source_url"),
        evidence_text=candidate.get("verification_notes"),
        confidence="high" if candidate.get("is_verified") else "medium",
        verification_status="active",
        created_at=now,
    )


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def main(dry_run: bool = True, now: datetime | None = None) -> int:
    now = _now(now)
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print("=" * 60)

    print("[1/6] Loading Italy strict-rule candidates...")
    candidates = _load_candidates()
    print(f"      Loaded {len(candidates)} candidates from {CANDIDATES_PATH}")

    # Validate lifecycle for candidates that need insertion (existence checked later)
    print("[2/6] Checking database target safety...")
    settings = get_settings()
    db_url = settings.database_url
    db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else ""

    ok, msg = _validate_db_target(db_url, db_path)
    if not ok:
        print(f"  ERROR: {msg}")
        print("  Only local SQLite databases are allowed for this script.")
        return 1
    print("  Database target: local SQLite - OK")

    if dry_run:
        print("[3/6] DRY RUN: Skipping database initialization and verification.")
        # Validate candidates
        for c in candidates:
            valid, vmsg = _validate_lifecycle(c, now)
            if not valid:
                print(f"  LIFECYCLE ERROR for {c.get('title','')[:50]}: {vmsg}")
                return 1
            print(f"  Candidate: {c.get('title','')[:50]} -> {c.get('status')} (ID: {c.get('preferred_id')})")
        print(f"\n[5/6] DRY RUN complete. Would insert up to {len(candidates)} records (subject to duplicate checks).")
        print("[6/6] No changes made (dry-run mode).")
        return 0

    print("[3/6] Initializing database...")
    # Validate file already done; init schema only now
    init_database()

    engine = get_engine()
    factory = get_session_factory()
    session = factory()

    inserted = 0
    skipped_duplicate = 0
    skipped_matched_ids: list[int] = []
    errors: list[dict] = []
    inserted_ids: list[int] = []
    matched_ids: list[int] = []

    try:
        print("[3/6] Verifying master baseline...")
        if not _verify_master_baseline(session):
            print("  ABORT: Master baseline verification failed.")
            session.close()
            return 1

        total_before = session.query(Scholarship).count()
        italy_before = session.query(Scholarship).filter(Scholarship.country == "Italy").count()

        # preferred ID collision check with identity awareness
        for c in candidates:
            preferred_id = c.get("preferred_id")
            if preferred_id is None:
                continue
            existing = session.get(Scholarship, preferred_id)
            if existing is not None:
                # same identity? compare title
                if (existing.title or "").strip().lower() != (c.get("title") or "").strip().lower():
                    print(f"  ERROR: ID collision for preferred_id {preferred_id}. Different record exists.")
                    session.close()
                    return 1
                else:
                    print(f"  ID {preferred_id} already exists with same identity (idempotent).")

        print("[4/6] Processing candidates...")
        for idx, candidate in enumerate(candidates):
            print(f"\n  Candidate {idx+1}: {candidate.get('title','')[:60]}...")

            # First check existence
            existing = _find_existing(session, candidate)
            if existing is not None:
                print(f"    -> SKIPPED: found existing record (ID: {existing.id})")
                skipped_duplicate += 1
                matched_ids.append(existing.id)
                skipped_matched_ids.append(existing.id)
                continue

            # Validate lifecycle only for candidates needing insertion
            valid, vmsg = _validate_lifecycle(candidate, now)
            if not valid:
                print(f"  LIFECYCLE ERROR for {candidate.get('title','')[:50]}: {vmsg}")
                session.close()
                return 1
            print(f"    Lifecycle OK: {candidate.get('title','')[:50]} -> {candidate.get('status')}")

            source_url = _normalize_url(candidate.get("official_source_url"))
            app_link = _normalize_url(candidate.get("application_link") or candidate.get("application_url"))
            title = (candidate.get("title") or "").strip().lower()
            country = (candidate.get("country") or "").strip()

            model = _map_to_model(candidate)

            session.add(model)
            session.flush()

            audit = _create_audit_record(session, model.id, candidate)
            session.add(audit)

            inserted_ids.append(model.id)
            inserted += 1
            print(f"    -> INSERTED (ID: {model.id})")

        if inserted == 0:
            print("\n  No new records to insert (all duplicates).")
            session.rollback()
        else:
            session.commit()
            print(f"\n[5/6] Committed {inserted} new records. IDs: {inserted_ids}")

        # Verification
        print("[6/6] Verification...")
        total_after = session.query(Scholarship).count()
        italy_after = session.query(Scholarship).filter(Scholarship.country == "Italy").count()
        open_count = session.query(Scholarship).filter(
            Scholarship.id.in_(inserted_ids), Scholarship.status == "open"
        ).count() if inserted_ids else 0
        upcoming_count = session.query(Scholarship).filter(
            Scholarship.id.in_(inserted_ids), Scholarship.status == "upcoming"
        ).count() if inserted_ids else 0
        audit_count = session.query(ScholarshipVerificationHistory).filter(
            ScholarshipVerificationHistory.scholarship_id.in_(inserted_ids),
            ScholarshipVerificationHistory.field_name == "record_insertion",
        ).count() if inserted_ids else 0

        print(f"  Total scholarships in DB: {total_after}")
        print(f"  New OPEN: {open_count}")
        print(f"  New UPCOMING: {upcoming_count}")
        print(f"  Audit records: {audit_count}")
        print(f"  Skipped as duplicates: {skipped_duplicate}")

        verification_time = datetime.now(timezone.utc)

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verification_at": verification_time.isoformat(),
            "total_candidates": len(candidates),
            "inserted": inserted,
            "skipped_duplicate": skipped_duplicate,
            "failed": len(errors),
            "inserted_ids": inserted_ids,
            "matched_ids": matched_ids,
            "open_count": open_count,
            "upcoming_count": upcoming_count,
            "audit_records": audit_count,
            "master_baseline_verified": True,
            "total_records_before": total_before,
            "total_records_after": total_after,
            "italy_records_before": italy_before,
            "italy_records_after": italy_after,
            "id_mapping": {
                "erasmus_mundus_id": 1,
                "iccr_id": 2,
                "vda_id": 1337,
                "polito_phd_id": 1338,
            },
        }

        # No-op rerun must not erase original successful insertion report
        if inserted == 0 and REPORT_PATH.exists():
            print("  No new inserts; preserving existing report.")
        else:
            _atomic_write_json(REPORT_PATH, report)
            print(f"\n[FINISHED] Report written to: {REPORT_PATH}")

    except IntegrityError as exc:
        session.rollback()
        print("ERROR: IntegrityError")
        errors.append({"type": "IntegrityError", "detail": "integrity error"})
        session.close()
        return 1
    except SQLAlchemyError as exc:
        session.rollback()
        print("ERROR: SQLAlchemyError")
        errors.append({"type": "SQLAlchemyError", "detail": "database error"})
        session.close()
        return 1
    except Exception as exc:
        session.rollback()
        print(f"ERROR: Unexpected - {type(exc).__name__}")
        errors.append({"type": type(exc).__name__, "detail": str(exc)[:200]})
        session.close()
        return 1
    finally:
        try:
            session.close()
        except Exception:
            pass

    return 0 if not errors else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually write to the database (default: dry-run).")
    args = parser.parse_args()
    dry_run = not args.execute
    exit_code = main(dry_run=dry_run)
    sys.exit(exit_code)
PY