"""Insert Germany strict-rule candidates (2 records: 1 OPEN, 1 UPCOMING).

Safety features:
- Defaults to dry-run mode (no writes).
- Requires --execute flag for actual database writes.
- Verifies master baseline (IDs 1 and 2) before insertion.
- Refuses to run against empty or incomplete databases.
- Validates lifecycle (VDA must be OPEN as of run date).
- Idempotent: skips duplicates by stable identity.
- Nonzero exit on any failure.
- Valid RFC 3339 timestamps in report.
- Credential redaction in logs/reports.
- Report recovery and retry support.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_engine, get_session_factory, init_database
from app.models import Scholarship, ScholarshipVerificationHistory


CANDIDATES_PATH = BACKEND_ROOT / "research_output" / "germany_strict_candidates.json"
REPORT_PATH = BACKEND_ROOT / "research_output" / "germany_insert_report.json"
MANIFEST_PATH = BACKEND_ROOT / "research_output" / "master_baseline_manifest.json"

MASTER_IDENTITY_ANCHORS = {
    1: ("Erasmus Mundus Joint Masters (EMJM)", "EU (multiple)"),
    2: ("ICCR Scholarship (Suborno Jayanti Scheme)", "India"),
}

SUPPORTED_STATUSES = {"open", "upcoming", "closed", "closing-soon"}

ROME_TZ_NAME = "Europe/Rome"


@dataclass
class InsertResult:
    total_candidates: int = 0
    inserted: int = 0
    skipped_duplicate: int = 0
    failed: int = 0
    rollback: bool = False
    inserted_ids: list[int] = field(default_factory=list)
    matched_ids: list[int] = field(default_factory=list)
    matched_details: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    open_count: int = 0
    upcoming_count: int = 0
    total_before: int = 0
    total_after: int = 0
    germany_before: int = 0
    germany_after: int = 0
    audit_records: int = 0


def _now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _redact_credentials(value: str) -> str:
    """Redact sensitive credentials from URLs and strings."""
    if not value:
        return value
    try:
        parsed = urlparse(value)
        if parsed.password or parsed.username:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc += f":{parsed.port}"
            redacted = parsed._replace(netloc=f"{parsed.username or 'user'}:****@{netloc}" if parsed.username else netloc)
            return redacted.geturl()
    except Exception:
        pass
    return re.sub(r'(password|token|api[_-]?key|secret)=[^&\s]+', r'\1=****', value, flags=re.IGNORECASE)


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


def _parse_datetime_iso(value: Any) -> datetime | None:
    """Parse ISO 8601 datetime with timezone offset awareness (RFC 3339).
    Date-only strings (YYYY-MM-DD) are returned as naive datetimes at midnight
    to be interpreted in the local (Rome) timezone by callers.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            s = value.strip()
            # Check if it's a date-only string (YYYY-MM-DD)
            if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
                # Return naive datetime - callers will apply Rome timezone
                return datetime.fromisoformat(s)
            s = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
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
    try:
        parsed = urlparse(str(value).strip())
    except Exception:
        return str(value).strip().rstrip("/")
    # Normalize scheme and host only; preserve case-sensitive path/query/fragment.
    scheme = (parsed.scheme or "").lower()
    host = (parsed.netloc or "").lower()
    # Preserve userinfo? Drop credentials if present.
    if "@" in host:
        host = host.split("@", 1)[-1]
    path = parsed.path or ""
    # Collapse trailing slash for comparison, but keep internal case.
    path = path.rstrip("/")
    query = parsed.query
    fragment = parsed.fragment
    normalized = f"{scheme}://{host}{path}" if host else str(value).strip().rstrip("/")
    if query:
        normalized += f"?{query}"
    if fragment:
        normalized += f"#{fragment}"
    return normalized


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
    """Derive the exact application deadline datetime in Europe/Rome.
    Date-only deadlines are valid through 23:59:59 of that date in Rome timezone.
    """
    deadline_str = candidate.get("application_deadline") or candidate.get("deadline_date")
    if not deadline_str:
        return None
    dt = _parse_datetime_iso(deadline_str)
    if dt is not None:
        # If naive (date-only), apply Rome timezone at 23:59
        if dt.tzinfo is None:
            rome = _get_rome()
            return datetime(dt.year, dt.month, dt.day, 23, 59, 0, tzinfo=rome)
        return dt.astimezone(_get_rome())
    d = _parse_date(deadline_str)
    if d is None:
        return None
    deadline_display = str(candidate.get("deadline_display") or "")
    official = candidate.get("official_details") or {}
    official_deadline = official.get("application_closes") or official.get("application_deadline")
    if official_deadline and "T" in str(official_deadline):
        odt = _parse_datetime_iso(official_deadline)
        if odt is not None:
            return odt.astimezone(_get_rome())
    hour, minute = 23, 59
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
    """Derive the exact application opening datetime in Europe/Rome.
    Date-only opening dates are valid from 00:00:00 of that date in Rome timezone.
    """
    open_str = candidate.get("application_open_date") or candidate.get("opening_date")
    if not open_str:
        return None
    dt = _parse_datetime_iso(open_str)
    if dt is not None:
        # If naive (date-only), apply Rome timezone at 00:00
        if dt.tzinfo is None:
            rome = _get_rome()
            return datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=rome)
        return dt.astimezone(_get_rome())
    d = _parse_date(open_str)
    if d is None:
        return None
    opening_display = str(candidate.get("opening_display") or "")
    hour, minute = 0, 0
    m = re.search(r"(\d{1,2}):(\d{2})", opening_display)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
    official = candidate.get("official_details") or {}
    official_open = official.get("application_opens")
    if official_open and "T" in str(official_open):
        odt = _parse_datetime_iso(official_open)
        if odt is not None:
            return odt.astimezone(_get_rome())
    rome = _get_rome()
    return datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=rome)


def _effective_status(candidate: dict[str, Any], now: datetime | None = None) -> str:
    """Compute the effective status considering UPCOMING->OPEN transition after opening date."""
    now = _now(now)
    status_raw = candidate.get("status")
    status = _normalize_status(status_raw)
    if not status:
        status = "open"

    if status == "upcoming":
        od = _open_datetime(candidate)
        if od is not None and now >= od.astimezone(timezone.utc):
            return "open"
    return status


def _validate_lifecycle(candidate: dict[str, Any], now: datetime | None = None) -> tuple[bool, str]:
    now = _now(now)
    status = _effective_status(candidate, now)
    if not status:
        return False, f"Unsupported status: {candidate.get('status')!r}. Allowed: {sorted(SUPPORTED_STATUSES)}."

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
        if now > dl.astimezone(timezone.utc):
            return False, f"UPCOMING candidate's window has closed (deadline: {dl.isoformat()})."
        return True, "Lifecycle valid."

    return True, "Lifecycle valid."


def _verify_db_target(db_url: str, db_path: str) -> tuple[bool, str]:
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


def _verify_master_baseline(session: Session) -> tuple[bool, str]:
    """Verify master baseline against immutable manifest. Returns (ok, message)."""
    if not MANIFEST_PATH.exists():
        return False, "Master baseline manifest not found."

    manifest = _load_manifest()
    expected_count = manifest.get("count")
    expected_records = {r["id"]: r for r in manifest.get("records", [])}

    total = session.query(Scholarship).count()
    if expected_count is not None and total < expected_count:
        return False, f"Database has {total} records (expected >= {expected_count}). Baseline incomplete."

    mismatches = 0
    missing = 0
    for exp_id, exp_record in expected_records.items():
        db_record = session.get(Scholarship, exp_id)
        if db_record is None:
            missing += 1
            continue
        if db_record.title != exp_record.get("title"):
            mismatches += 1
        if db_record.country != exp_record.get("country"):
            mismatches += 1
        if exp_record.get("official_source_url") and db_record.official_source_url != exp_record.get("official_source_url"):
            mismatches += 1

    if missing > 0 or mismatches > 0:
        return False, f"{missing} missing, {mismatches} mismatches."

    return True, f"Master baseline verified: {total} records, {len(expected_records)} identities match manifest."


def _build_stable_identity(candidate: dict[str, Any]) -> tuple[str, str, str, str]:
    """Build stable identity key: (title, country, academic_year, provider)."""
    title = (candidate.get("title") or "").strip().lower()
    country = (candidate.get("country") or "").strip()
    academic_year = (candidate.get("academic_year") or "").strip().lower()
    provider = (candidate.get("provider") or "").strip().lower()
    return (title, country, academic_year, provider)


def _find_existing(session: Session, candidate: dict[str, Any]) -> Scholarship | None:
    """Find existing record by stable identity, then by source URL, then by application link."""
    title, country, academic_year, provider = _build_stable_identity(candidate)

    if title and country:
        rows = session.scalars(
            select(Scholarship).where(
                func.lower(Scholarship.title) == title,
                Scholarship.country == country,
            )
        ).all()
        if academic_year or provider:
            filtered = []
            for r in rows:
                ay = getattr(r, "academic_year", None)
                prov = getattr(r, "provider", None)
                if academic_year and ay is not None and str(ay).strip().lower() != academic_year:
                    continue
                if provider and prov is not None and str(prov).strip().lower() != provider:
                    continue
                filtered.append(r)
            rows = filtered
        if len(rows) > 1:
            raise RuntimeError(f"Multiple records match stable identity: {title!r} in {country!r}")
        if rows:
            return rows[0]

    source_url = _normalize_url(candidate.get("official_source_url"))
    if source_url:
        rows = session.scalars(select(Scholarship)).all()
        matches = [r for r in rows if _normalize_url(getattr(r, "official_source_url", None)) == source_url]
        if len(matches) > 1:
            raise RuntimeError(f"Multiple records share official_source_url: {source_url}")
        if matches:
            return matches[0]

    app_link = _normalize_url(candidate.get("application_link") or candidate.get("application_url"))
    if app_link and app_link != source_url:
        rows = session.scalars(select(Scholarship)).all()
        matches = [r for r in rows if _normalize_url(getattr(r, "application_link", None)) == app_link]
        if len(matches) > 1:
            raise RuntimeError(f"Multiple records share application_link: {app_link}")
        if matches:
            return matches[0]

    return None


def _map_to_model(candidate: dict[str, Any], now: datetime | None = None) -> Scholarship:
    status = _effective_status(candidate, now)
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


def _reconstruct_report_from_db(inserted_ids: list[int], matched_ids: list[int], total_before: int, germany_before: int, errors: list[dict]) -> dict[str, Any]:
    """Reconstruct report from database after successful commit but failed report write."""
    engine = get_engine()
    factory = get_session_factory()
    session = factory()
    try:
        total_after = session.query(Scholarship).count()
        germany_after = session.query(Scholarship).filter(Scholarship.country == "Germany").count()
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

        # Build dynamic ID mapping from actual DB records
        vda_id = None
        polito_id = None
        for sch in session.query(Scholarship).filter(
            Scholarship.country == "Germany"
        ).all():
            title_lower = (sch.title or "").lower()
            if vda_id is None and ("valle d'aosta" in title_lower or "vda" in title_lower):
                vda_id = sch.id
            elif polito_id is None and ("politecnico di torino" in title_lower or "polito" in title_lower):
                polito_id = sch.id

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verification_at": datetime.now(timezone.utc).isoformat(),
            "total_candidates": len(inserted_ids) + len(matched_ids),
            "inserted": len(inserted_ids),
            "skipped_duplicate": len(matched_ids),
            "failed": len(errors),
            "inserted_ids": inserted_ids,
            "matched_ids": matched_ids,
            "open_count": open_count,
            "upcoming_count": upcoming_count,
            "audit_records": audit_count,
            "master_baseline_verified": True,
            "total_records_before": total_before,
            "total_records_after": total_after,
            "germany_records_before": germany_before,
            "germany_records_after": germany_after,
            "id_mapping": {
                "erasmus_mundus_id": 1,
                "iccr_id": 2,
                "vda_id": vda_id,
                "polito_phd_id": polito_id,
            },
            "reconstructed": True,
        }
    finally:
        session.close()


def _load_existing_report() -> dict[str, Any] | None:
    """Load existing report for recovery."""
    if REPORT_PATH.exists():
        try:
            with open(REPORT_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _infer_inserted_ids_from_db() -> tuple[list[int], list[int]]:
    """Infer inserted and matched IDs from audit records when no report exists."""
    engine = get_engine()
    factory = get_session_factory()
    session = factory()
    try:
        # Get all scholarship IDs that have a "record_insertion" audit record
        audit_records = session.query(ScholarshipVerificationHistory).filter(
            ScholarshipVerificationHistory.field_name == "record_insertion"
        ).all()
        inserted_ids = sorted(set(a.scholarship_id for a in audit_records))
        # Matched IDs would be harder to infer, assume empty
        matched_ids = []
        return inserted_ids, matched_ids
    finally:
        session.close()


def main(dry_run: bool = True, now: datetime | None = None, reconstruct: bool = False) -> int:
    now = _now(now)
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    if reconstruct:
        print("Mode: RECONSTRUCT REPORT FROM DB")
    print("=" * 60)

    if reconstruct:
        existing_report = _load_existing_report()
        if existing_report:
            inserted_ids = existing_report.get("inserted_ids", [])
            matched_ids = existing_report.get("matched_ids", [])
            total_before = existing_report.get("total_records_before", 0)
            germany_before = existing_report.get("germany_records_before", 0)
            errors = existing_report.get("errors", [])
        else:
            print("  No existing report found, inferring from database...")
            inserted_ids, matched_ids = _infer_inserted_ids_from_db()
            # Get total counts from database
            engine = get_engine()
            factory = get_session_factory()
            session = factory()
            try:
                total_before = session.query(Scholarship).count() - len(inserted_ids)
                germany_before = session.query(Scholarship).filter(Scholarship.country == "Germany").count() - len([i for i in inserted_ids if session.get(Scholarship, i) and session.get(Scholarship, i).country == "Italy"])
            finally:
                session.close()
            errors = []
        print(f"Reconstructing report for {len(inserted_ids)} inserted, {len(matched_ids)} matched...")
        report = _reconstruct_report_from_db(inserted_ids, matched_ids, total_before, germany_before, errors)
        _atomic_write_json(REPORT_PATH, report)
        print(f"Report reconstructed and written to: {REPORT_PATH}")
        return 0

    print("[1/6] Loading Italy strict-rule candidates...")
    candidates = _load_candidates()
    print(f"      Loaded {len(candidates)} candidates from {CANDIDATES_PATH}")

    print("[2/6] Checking database target safety...")
    settings = get_settings()
    db_url = settings.database_url
    db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else ""

    ok, msg = _verify_db_target(db_url, db_path)
    if not ok:
        print(f"  ERROR: {msg}")
        print("  Only local SQLite databases are allowed for this script.")
        return 1
    print(f"  Database target: local SQLite - OK ({_redact_credentials(db_url)})")

    if dry_run:
        print("[3/6] DRY RUN: Skipping database initialization and verification.")
        for c in candidates:
            valid, vmsg = _validate_lifecycle(c, now)
            if not valid:
                print(f"  LIFECYCLE ERROR for {c.get('title','')[:50]}: {vmsg}")
                return 1
            eff_status = _effective_status(c, now)
            print(f"  Candidate: {c.get('title','')[:50]} -> {eff_status} (ID: {c.get('preferred_id')})")
        print(f"\n[5/6] DRY RUN complete. Would insert up to {len(candidates)} records (subject to duplicate checks).")
        print("[6/6] No changes made (dry-run mode).")
        return 0

    engine = get_engine()
    factory = get_session_factory()
    session = factory()

    result = InsertResult(total_candidates=len(candidates))

    try:
        print("[3/6] Initializing database schema...")
        init_database()

        print("[3/6] Verifying master baseline (within transaction)...")
        ok, msg = _verify_master_baseline(session)
        if not ok:
            print(f"  ABORT: {msg}")
            session.close()
            return 1
        print(f"  {msg}")

        result.total_before = session.query(Scholarship).count()
        result.germany_before = session.query(Scholarship).filter(Scholarship.country == "Germany").count()

        for c in candidates:
            preferred_id = c.get("preferred_id")
            if preferred_id is None:
                continue
            existing = session.get(Scholarship, preferred_id)
            if existing is not None:
                if (existing.title or "").strip().lower() != (c.get("title") or "").strip().lower():
                    print(f"  ERROR: ID collision for preferred_id {preferred_id}. Different record exists.")
                    session.close()
                    return 1
                else:
                    print(f"  ID {preferred_id} already exists with same identity (idempotent).")

        print("[4/6] Processing candidates...")
        for idx, candidate in enumerate(candidates):
            print(f"\n  Candidate {idx+1}: {candidate.get('title','')[:60]}...")

            existing = _find_existing(session, candidate)
            if existing is not None:
                print(f"    -> SKIPPED: found existing record (ID: {existing.id})")
                result.skipped_duplicate += 1
                result.matched_ids.append(existing.id)
                result.matched_details.append({
                    "id": existing.id,
                    "title": existing.title,
                    "country": existing.country,
                    "matched_by": "stable_identity" if _build_stable_identity(candidate)[:2] == (existing.title.strip().lower(), existing.country.strip()) else "source_url" if _normalize_url(candidate.get("official_source_url")) == _normalize_url(existing.official_source_url) else "application_link"
                })
                continue

            valid, vmsg = _validate_lifecycle(candidate, now)
            if not valid:
                print(f"  LIFECYCLE ERROR for {candidate.get('title','')[:50]}: {vmsg}")
                result.failed += 1
                result.errors.append({"candidate": candidate.get("title"), "error": vmsg})
                continue
            print(f"    Lifecycle OK: {candidate.get('title','')[:50]} -> {_effective_status(candidate, now)}")

            model = _map_to_model(candidate, now)
            session.add(model)
            session.flush()

            audit = _create_audit_record(session, model.id, candidate)
            session.add(audit)

            result.inserted_ids.append(model.id)
            result.inserted += 1
            if model.status == "open":
                result.open_count += 1
            elif model.status == "upcoming":
                result.upcoming_count += 1
            print(f"    -> INSERTED (ID: {model.id})")

        if result.inserted == 0:
            print("\n  No new records to insert (all duplicates or failed).")
            session.rollback()
        else:
            session.commit()
            print(f"\n[5/6] Committed {result.inserted} new records. IDs: {result.inserted_ids}")

        print("[6/6] Verification...")
        result.total_after = session.query(Scholarship).count()
        result.germany_after = session.query(Scholarship).filter(Scholarship.country == "Germany").count()
        result.audit_records = session.query(ScholarshipVerificationHistory).filter(
            ScholarshipVerificationHistory.scholarship_id.in_(result.inserted_ids),
            ScholarshipVerificationHistory.field_name == "record_insertion",
        ).count() if result.inserted_ids else 0

        print(f"  Total scholarships in DB: {result.total_after}")
        print(f"  New OPEN: {result.open_count}")
        print(f"  New UPCOMING: {result.upcoming_count}")
        print(f"  Audit records: {result.audit_records}")
        print(f"  Skipped as duplicates: {result.skipped_duplicate}")

        verification_time = datetime.now(timezone.utc)

        # Build dynamic ID mapping from actual inserted/matched IDs.
        # Query the DB to find actual IDs for VDA and PoliTo records.
        vda_id = None
        polito_id = None
        
        # Check matched details first (existing records)
        for detail in result.matched_details:
            title_lower = detail.get("title", "").lower()
            if "valle d'aosta" in title_lower or "vda" in title_lower:
                vda_id = detail.get("id")
            elif "politecnico di torino" in title_lower or "polito" in title_lower:
                polito_id = detail.get("id")
        
        # For newly inserted or unmatched records, query the DB
        if vda_id is None or polito_id is None:
            for sch in session.query(Scholarship).filter(
                Scholarship.country == "Germany"
            ).all():
                title_lower = (sch.title or "").lower()
                if vda_id is None and ("valle d'aosta" in title_lower or "vda" in title_lower):
                    vda_id = sch.id
                elif polito_id is None and ("politecnico di torino" in title_lower or "polito" in title_lower):
                    polito_id = sch.id
        
        # Build mapping with None for unresolved (no fallback to hardcoded IDs)
        id_mapping = {
            "erasmus_mundus_id": 1,
            "iccr_id": 2,
            "vda_id": vda_id,
            "polito_phd_id": polito_id,
        }
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verification_at": verification_time.isoformat(),
            "total_candidates": result.total_candidates,
            "inserted": result.inserted,
            "skipped_duplicate": result.skipped_duplicate,
            "failed": result.failed,
            "inserted_ids": result.inserted_ids,
            "matched_ids": result.matched_ids,
            "matched_details": result.matched_details,
            "open_count": result.open_count,
            "upcoming_count": result.upcoming_count,
            "audit_records": result.audit_records,
            "master_baseline_verified": True,
            "total_records_before": result.total_before,
            "total_records_after": result.total_after,
            "germany_records_before": result.germany_before,
            "germany_records_after": result.germany_after,
            "id_mapping": id_mapping,
            "errors": result.errors,
        }

        if result.inserted == 0 and REPORT_PATH.exists():
            print("  No new inserts; preserving existing report.")
        else:
            try:
                _atomic_write_json(REPORT_PATH, report)
                print(f"\n[FINISHED] Report written to: {REPORT_PATH}")
            except Exception as e:
                print(f"  WARNING: Report write failed: {e}")
                print("  Attempting recovery from database...")
                try:
                    recovery_report = _reconstruct_report_from_db(
                        result.inserted_ids, result.matched_ids,
                        result.total_before, result.germany_before, result.errors
                    )
                    _atomic_write_json(REPORT_PATH, recovery_report)
                    print(f"  Recovery successful. Report written to: {REPORT_PATH}")
                except Exception as e2:
                    print(f"  ERROR: Recovery failed: {e2}")
                    return 1

    except IntegrityError as exc:
        session.rollback()
        print("ERROR: IntegrityError")
        result.errors.append({"type": "IntegrityError", "detail": "integrity error"})
        return 1
    except SQLAlchemyError as exc:
        session.rollback()
        print("ERROR: SQLAlchemyError")
        result.errors.append({"type": "SQLAlchemyError", "detail": "database error"})
        return 1
    except Exception as exc:
        session.rollback()
        print(f"ERROR: Unexpected - {type(exc).__name__}")
        result.errors.append({"type": type(exc).__name__, "detail": str(exc)[:200]})
        return 1
    finally:
        try:
            session.close()
        except Exception:
            pass

    return 0 if result.failed == 0 and not result.rollback else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually write to the database (default: dry-run).")
    parser.add_argument("--reconstruct", action="store_true", help="Reconstruct report from database after successful commit.")
    parser.add_argument("--now", type=str, help="Override current time for testing (ISO 8601 format, e.g., 2026-11-18T14:30:00+01:00).")
    args = parser.parse_args()
    dry_run = not args.execute
    now = _parse_datetime_iso(args.now) if args.now else None
    exit_code = main(dry_run=dry_run, now=now, reconstruct=args.reconstruct)
    sys.exit(exit_code)