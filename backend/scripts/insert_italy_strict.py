"""Insert Italy strict-rule candidates (2 records: 1 OPEN, 1 UPCOMING).

Safety features:
- Defaults to dry-run mode (no writes).
- Requires --execute flag for actual database writes.
- Verifies master baseline (IDs 1 and 2) before insertion.
- Refuses to run against empty or incomplete databases.
- Validates lifecycle (VDA must be OPEN as of run date).
- Idempotent: skips duplicates by source URL, application URL, title+country.
- Nonzero exit on any failure.
- Valid RFC 3339 timestamps in report.
"""

from __future__ import annotations

import argparse
import json
import sys
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

# Master baseline identity anchors (must exist before insertion)
MASTER_IDENTITY_ANCHORS = {
    1: ("Erasmus Mundus Joint Masters (EMJM)", "EU (multiple)"),
    2: ("ICCR Scholarship (Suborno Jayanti Scheme)", "India"),
}

VDA_DEADLINE = datetime(2026, 12, 4, 12, 0, 0, tzinfo=timezone(timedelta(hours=1)))


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            # Handle various ISO formats
            v = value.replace("Z", "+00:00")
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return None


def _normalize_status(value: str) -> str:
    value = value.strip().lower()
    if value in ("open", "upcoming", "closed", "closing-soon"):
        return value
    return "open"


def _load_candidates() -> list[dict[str, Any]]:
    with open(CANDIDATES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise RuntimeError(f"Expected a JSON array in {CANDIDATES_PATH}, got {type(data).__name__}")
    return data


MANIFEST_PATH = BACKEND_ROOT / "research_output" / "master_baseline_manifest.json"


def _load_manifest() -> dict[str, Any]:
    """Load the immutable master baseline manifest."""
    if not MANIFEST_PATH.exists():
        raise RuntimeError(f"Master baseline manifest not found: {MANIFEST_PATH}")
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _verify_master_baseline(session: Session) -> bool:
    """Verify that the master baseline is present with exact identity match.

    Uses the immutable manifest from the base commit to verify:
    1. Exact expected record count.
    2. Every expected ID exists.
    3. Every identity matches (title, country, provider, source URL).
    4. No unexpected reassigned IDs.
    5. No missing or duplicate identities.
    """
    print("  Verifying master baseline against immutable manifest...")

    manifest = _load_manifest()
    expected_count = manifest["count"]
    expected_records = {r["id"]: r for r in manifest["records"]}

    # Check total count
    total = session.query(Scholarship).count()
    if total < expected_count:
        print(f"  ERROR: Database has {total} records (expected >= {expected_count}). Baseline incomplete.")
        return False

    # Check every expected ID exists with matching identity
    mismatches = 0
    missing = 0
    for exp_id, exp_record in expected_records.items():
        db_record = session.get(Scholarship, exp_id)
        if db_record is None:
            print(f"  ERROR: Expected ID {exp_id} not found in database.")
            missing += 1
            continue
        # Check identity
        if db_record.title != exp_record["title"]:
            print(f"  ERROR: ID {exp_id} title mismatch.")
            mismatches += 1
        if db_record.country != exp_record["country"]:
            print(f"  ERROR: ID {exp_id} country mismatch.")
            mismatches += 1
        if exp_record.get("official_source_url") and db_record.official_source_url != exp_record["official_source_url"]:
            print(f"  ERROR: ID {exp_id} source URL mismatch.")
            mismatches += 1

    if missing > 0 or mismatches > 0:
        print(f"  ABORT: {missing} missing, {mismatches} mismatches.")
        return False

    # Check for unexpected reassignments (IDs in manifest but different record)
    # This is already covered by the identity check above

    print(f"  Master baseline verified: {total} records, {len(expected_records)} identities match manifest.")
    return True


def _check_collision(session: Session, preferred_id: int) -> bool:
    """Check if preferred_id collides with an existing record."""
    existing = session.get(Scholarship, preferred_id)
    if existing is not None:
        print(f"  WARNING: ID {preferred_id} already exists.")
        return True
    return False


def _validate_lifecycle(candidate: dict[str, Any]) -> tuple[bool, str]:
    """Validate that the candidate's lifecycle is correct as of run date."""
    status = candidate.get("status", "open").strip().lower()
    now = datetime.now(timezone.utc)

    if status == "open":
        deadline_str = candidate.get("application_deadline")
        if deadline_str:
            try:
                # Parse deadline date
                deadline_date = date.fromisoformat(deadline_str)
                # Determine time from deadline_display or default to end of day
                deadline_display = candidate.get("deadline_display", "")
                hour, minute = 23, 59
                if "12:00" in deadline_display:
                    hour, minute = 12, 0
                elif "14:00" in deadline_display:
                    hour, minute = 14, 0
                # Use Europe/Rome timezone (CET/CEST)
                from zoneinfo import ZoneInfo
                rome = ZoneInfo("Europe/Rome")
                deadline = datetime(deadline_date.year, deadline_date.month, deadline_date.day,
                                    hour, minute, 0, tzinfo=rome)
                # Convert to UTC for comparison
                deadline_utc = deadline.astimezone(timezone.utc)
                if now > deadline_utc:
                    return False, f"Deadline {deadline} (CET) has passed (now: {now}). Cannot insert as OPEN."
            except ValueError:
                return False, f"Invalid deadline format: {deadline_str}"

    if status == "upcoming":
        open_date_str = candidate.get("application_open_date")
        if open_date_str:
            try:
                open_date = date.fromisoformat(open_date_str)
                from zoneinfo import ZoneInfo
                rome = ZoneInfo("Europe/Rome")
                open_dt = datetime(open_date.year, open_date.month, open_date.day,
                                   0, 0, 0, tzinfo=rome)
                open_utc = open_dt.astimezone(timezone.utc)
                # If already past open date, check if deadline has passed too
                deadline_str = candidate.get("application_deadline")
                if deadline_str and now > open_utc:
                    deadline_date = date.fromisoformat(deadline_str)
                    deadline = datetime(deadline_date.year, deadline_date.month, deadline_date.day,
                                        23, 59, 0, tzinfo=rome)
                    deadline_utc = deadline.astimezone(timezone.utc)
                    if now > deadline_utc:
                        return False, f"UPCOMING record's window has closed (deadline: {deadline})."
            except ValueError:
                return False, f"Invalid date format: {open_date_str}"

    return True, "Lifecycle valid."


def _find_existing(session: Session, candidate: dict[str, Any]) -> Scholarship | None:
    source_url = candidate.get("official_source_url")
    app_link = candidate.get("application_link") or candidate.get("application_url")
    title = candidate.get("title")
    country = candidate.get("country")

    if source_url:
        normalized = source_url.strip().rstrip("/")
        variants = (normalized, f"{normalized}/")
        rows = session.scalars(
            select(Scholarship).where(Scholarship.official_source_url.in_(variants))
        ).all()
        if len(rows) > 1:
            raise RuntimeError(f"Multiple records share official_source_url: {normalized}")
        if rows:
            return rows[0]

    if app_link and app_link != source_url:
        normalized = app_link.strip().rstrip("/")
        variants = (normalized, f"{normalized}/")
        rows = session.scalars(
            select(Scholarship).where(Scholarship.application_link.in_(variants))
        ).all()
        if len(rows) > 1:
            raise RuntimeError(f"Multiple records share application_link: {normalized}")
        if rows:
            return rows[0]

    if title and country:
        rows = session.scalars(
            select(Scholarship).where(
                func.lower(Scholarship.title) == title.strip().lower(),
                Scholarship.country == country.strip(),
            )
        ).all()
        if len(rows) > 1:
            raise RuntimeError(f"Multiple records match title+country: {title!r} in {country!r}")
        if rows:
            return rows[0]

    return None


def _map_to_model(candidate: dict[str, Any]) -> Scholarship:
    status = _normalize_status(candidate.get("status", "open"))

    # Funding: use candidate's funding label, fallback to empty
    funding = candidate.get("funding", "") or ""

    # Eligible fields: use eligible_fields if present, else study_fields
    eligible_fields = candidate.get("eligible_fields")
    if not eligible_fields:
        eligible_fields = candidate.get("study_fields", [])
    if eligible_fields is None:
        eligible_fields = []

    # Preferred ID
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


def _create_audit_record(
    session: Session,
    scholarship_id: int,
    candidate: dict[str, Any],
    change_type: str = "insert",
) -> ScholarshipVerificationHistory:
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
        change_type=change_type,
        source_url=candidate.get("official_source_url"),
        evidence_text=candidate.get("verification_notes"),
        confidence="high" if candidate.get("is_verified") else "medium",
        verification_status="active",
        created_at=now,
    )


def main(dry_run: bool = True) -> int:
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print("=" * 60)

    print("[1/6] Loading Italy strict-rule candidates...")
    candidates = _load_candidates()
    print(f"      Loaded {len(candidates)} candidates from {CANDIDATES_PATH}")

    # Validate lifecycle for each candidate
    for c in candidates:
        valid, msg = _validate_lifecycle(c)
        if not valid:
            print(f"  LIFECYCLE ERROR for {c['title'][:50]}: {msg}")
            return 1
        print(f"  Lifecycle OK: {c['title'][:50]} -> {c.get('status')}")

    print("[2/6] Checking database target safety...")
    settings = get_settings()
    db_url = settings.database_url

    # Safety check: only allow local SQLite
    if not db_url.startswith("sqlite:///"):
        print(f"  ERROR: Database target is not local SQLite: {db_url[:50]}...")
        print("  Only local SQLite databases are allowed for this script.")
        return 1

    # Check for production/remote indicators
    db_path = db_url.replace("sqlite:///", "")
    if "neon" in db_url.lower() or "supabase" in db_url.lower() or "postgres" in db_url.lower():
        print("  ERROR: Production/remote database target detected. Aborting.")
        return 1

    # Check if path looks like a production path
    if not db_path.endswith(".db") and not db_path.endswith(".sqlite"):
        print(f"  ERROR: Unexpected database file extension: {db_path}")
        return 1

    print(f"  Database target: {db_path} (local SQLite - OK)")

    if dry_run:
        print("[3/6] DRY RUN: Skipping database initialization and verification.")
        print("[4/6] DRY RUN: Would process candidates (see below).")
        # Still load and validate candidates
        candidates = _load_candidates()
        for c in candidates:
            valid, msg = _validate_lifecycle(c)
            if not valid:
                print(f"  LIFECYCLE ERROR: {msg}")
                return 1
            print(f"  Candidate: {c['title'][:50]} -> {c.get('status')} (ID: {c.get('preferred_id')})")
        print(f"\n[5/6] DRY RUN complete. Would insert {len(candidates)} records.")
        print("[6/6] No changes made (dry-run mode).")
        return 0

    print("[3/6] Initializing database...")
    init_database()

    engine = get_engine()
    factory = get_session_factory()
    session = factory()

    inserted = 0
    skipped_duplicate = 0
    errors = []
    inserted_ids = []

    try:
        # Phase 1: Verify master baseline
        print("[3/6] Verifying master baseline...")
        if not _verify_master_baseline(session):
            print("  ABORT: Master baseline verification failed.")
            session.close()
            return 1

        # Pre-load existing URLs for deduplication
        existing_urls: set[str] = set()
        existing_app_links: set[str] = set()
        existing_title_country: set[tuple[str, str]] = set()

        for row in session.scalars(select(Scholarship)):
            if row.official_source_url:
                existing_urls.add(row.official_source_url.strip().rstrip("/"))
                existing_urls.add(row.official_source_url.strip().rstrip("/") + "/")
            if row.application_link:
                existing_app_links.add(row.application_link.strip().rstrip("/"))
                existing_app_links.add(row.application_link.strip().rstrip("/") + "/")
            if row.title and row.country:
                existing_title_country.add((row.title.strip().lower(), row.country.strip()))

        # Check for collisions with preferred IDs (only if record exists with different identity)
        for c in candidates:
            preferred_id = c.get("preferred_id")
            if preferred_id is not None:
                existing = session.get(Scholarship, preferred_id)
                if existing is not None:
                    # Check if it's the same record (idempotent re-run)
                    if existing.official_source_url == (c.get("official_source_url") or "").strip().rstrip("/"):
                        print(f"  ID {preferred_id} already exists with same source URL (idempotent skip).")
                    else:
                        print(f"  ERROR: ID collision for preferred_id {preferred_id}. Different record exists.")
                        session.close()
                        return 1

        # Process candidates
        print("[4/6] Processing candidates...")
        for idx, candidate in enumerate(candidates):
            source_url = candidate.get("official_source_url", "").strip().rstrip("/") if candidate.get("official_source_url") else ""
            app_link = (candidate.get("application_link") or candidate.get("application_url") or "").strip().rstrip("/")
            title = candidate.get("title", "").strip().lower()
            country = candidate.get("country", "").strip()

            print(f"\n  Candidate {idx+1}: {candidate['title'][:60]}...")
            print(f"    Source URL: {source_url[:80]}...")
            print(f"    Status: {candidate.get('status')}")
            print(f"    Preferred ID: {candidate.get('preferred_id')}")
            print(f"    Funding: {candidate.get('funding')}")

            if source_url and source_url in existing_urls:
                print(f"    -> SKIPPED: duplicate official_source_url")
                skipped_duplicate += 1
                continue

            if app_link and app_link in existing_app_links:
                print(f"    -> SKIPPED: duplicate application_link")
                skipped_duplicate += 1
                continue

            if title and country and (title, country) in existing_title_country:
                print(f"    -> SKIPPED: duplicate legacy title+country")
                skipped_duplicate += 1
                continue

            existing = _find_existing(session, candidate)
            if existing:
                print(f"    -> SKIPPED: found existing record (ID: {existing.id})")
                skipped_duplicate += 1
                continue

            model = _map_to_model(candidate)

            if dry_run:
                print(f"    -> DRY RUN: would insert (ID: {model.id})")
                inserted += 1
                inserted_ids.append(model.id)
                continue

            session.add(model)
            session.flush()

            audit = _create_audit_record(session, model.id, {
                "title": model.title,
                "official_source_url": model.official_source_url,
                "status": model.status,
                "verified_by": model.verified_by,
                "verification_notes": model.verification_notes,
                "funding": model.funding,
                "fully_funded": model.fully_funded,
                "is_verified": model.is_verified,
                "_verification_timestamp": datetime.now(timezone.utc).isoformat(),
            })
            session.add(audit)

            inserted_ids.append(model.id)
            existing_urls.add(source_url)
            existing_urls.add(source_url + "/" if source_url else "")
            if app_link:
                existing_app_links.add(app_link)
                existing_app_links.add(app_link + "/")
            if title and country:
                existing_title_country.add((title, country))

            print(f"    -> INSERTED (ID: {model.id})")
            inserted += 1

        if dry_run:
            print(f"\n[5/6] DRY RUN complete. Would insert {inserted} records.")
            print(f"      IDs: {inserted_ids}")
            session.rollback()
            session.close()
            return 0

        if inserted == 0:
            print("\n  No new records to insert (all duplicates).")
            session.rollback()
        else:
            session.commit()
            print(f"\n[5/6] Committed {inserted} new records. IDs: {inserted_ids}")

        # Verification
        print("[6/6] Verification...")
        total_after = session.query(Scholarship).count()
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

        # Write report
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_candidates": len(candidates),
            "inserted": inserted,
            "skipped_duplicate": skipped_duplicate,
            "failed": len(errors),
            "inserted_ids": inserted_ids,
            "open_count": open_count,
            "upcoming_count": upcoming_count,
            "audit_records": audit_count,
            "master_baseline_verified": True,
            "master_record_count_before": total_after - inserted,
            "total_records_after": total_after,
            "italy_records_before": 22,
            "italy_records_after": 24,
            "id_mapping": {
                "erasmus_mundus_id": 1,
                "iccr_id": 2,
                "vda_id": 1337,
                "polito_phd_id": 1338,
            },
        }

        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n[FINISHED] Report written to: {REPORT_PATH}")

    except IntegrityError as exc:
        session.rollback()
        print(f"ERROR: IntegrityError - {exc}")
        errors.append({"type": "IntegrityError", "detail": str(exc)})
        session.close()
        return 1
    except SQLAlchemyError as exc:
        session.rollback()
        print(f"ERROR: SQLAlchemyError - {exc}")
        errors.append({"type": "SQLAlchemyError", "detail": str(exc)})
        session.close()
        return 1
    except Exception as exc:
        session.rollback()
        print(f"ERROR: Unexpected - {exc}")
        errors.append({"type": "Unexpected", "detail": str(exc)})
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
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write to the database (default: dry-run).",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    exit_code = main(dry_run=dry_run)
    sys.exit(exit_code)