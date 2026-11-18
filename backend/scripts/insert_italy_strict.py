"""Insert Italy strict-rule candidates (2 records: 1 OPEN, 1 UPCOMING)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
import sys

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

    return Scholarship(
        title=candidate["title"],
        country=candidate["country"],
        degree=candidate.get("degree", ""),
        funding=candidate.get("funding", ""),
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
        # Structured fields
        funding_amount=candidate.get("funding_amount"),
        funding_currency=candidate.get("funding_currency"),
        funding_period=candidate.get("funding_period"),
        tuition_coverage=candidate.get("tuition_coverage"),
        living_cost_coverage=candidate.get("living_cost_coverage"),
        travel_coverage=candidate.get("travel_coverage"),
        fully_funded=candidate.get("fully_funded"),
        funding_details=candidate.get("funding_details"),
        departments=candidate.get("departments") or [],
        eligible_fields=candidate.get("eligible_fields") or [],
        eligible_programmes=candidate.get("eligible_programmes") or [],
        academic_provenance=candidate.get("academic_provenance"),
        official_details=candidate.get("official_details"),
        applicant_utility=candidate.get("applicant_utility"),
        programme_verification=candidate.get("programme_verification"),
    )


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
            "verification_timestamp": candidate.get("_verification_timestamp"),
        }, ensure_ascii=False),
        change_type=change_type,
        source_url=candidate.get("official_source_url"),
        evidence_text=candidate.get("verification_notes"),
        confidence="high" if candidate.get("is_verified") else "medium",
        verification_status="active",
        created_at=now,
    )


def main() -> None:
    print("[1/4] Loading Italy strict-rule candidates...")
    candidates = _load_candidates()
    print(f"      Loaded {len(candidates)} candidates from {CANDIDATES_PATH}")

    print("[2/4] Initializing database...")
    init_database()

    engine = get_engine()
    factory = get_session_factory()
    session = factory()

    inserted = 0
    skipped_duplicate = 0
    errors = []
    inserted_ids = []

    try:
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

        for idx, candidate in enumerate(candidates):
            source_url = candidate.get("official_source_url", "").strip().rstrip("/") if candidate.get("official_source_url") else ""
            app_link = (candidate.get("application_link") or candidate.get("application_url") or "").strip().rstrip("/")
            title = candidate.get("title", "").strip().lower()
            country = candidate.get("country", "").strip()

            print(f"\n  Processing candidate {idx+1}: {candidate['title'][:60]}...")
            print(f"    Source URL: {source_url[:80]}...")
            print(f"    Status: {candidate.get('status')}")

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

            # Check database directly too
            existing = _find_existing(session, candidate)
            if existing:
                print(f"    -> SKIPPED: found existing record (ID: {existing.id})")
                skipped_duplicate += 1
                continue

            model = _map_to_model(candidate)
            session.add(model)
            session.flush()

            audit = _create_audit_record(session, model.id, {
                "title": model.title,
                "official_source_url": model.official_source_url,
                "status": model.status,
                "verified_by": model.verified_by,
                "verification_notes": model.verification_notes,
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

        if inserted == 0:
            print("\n  No new records to insert.")
            session.rollback()
        else:
            session.commit()
            print(f"\n[3/4] Committed {inserted} new records.")

        print("[4/4] Verification...")
        total_after = session.query(Scholarship).count()
        open_count = session.query(Scholarship).filter(
            Scholarship.id.in_(inserted_ids), Scholarship.status == "open"
        ).count()
        upcoming_count = session.query(Scholarship).filter(
            Scholarship.id.in_(inserted_ids), Scholarship.status == "upcoming"
        ).count()
        audit_count = session.query(ScholarshipVerificationHistory).filter(
            ScholarshipVerificationHistory.scholarship_id.in_(inserted_ids),
            ScholarshipVerificationHistory.field_name == "record_insertion",
        ).count()

        print(f"  Total scholarships in DB: {total_after}")
        print(f"  New OPEN: {open_count}")
        print(f"  New UPCOMING: {upcoming_count}")
        print(f"  Audit records: {audit_count}")
        print(f"  Skipped as duplicates: {skipped_duplicate}")

        # Report
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "total_candidates": len(candidates),
            "inserted": inserted,
            "skipped_duplicate": skipped_duplicate,
            "failed": len(errors),
            "inserted_ids": inserted_ids,
            "open_count": open_count,
            "upcoming_count": upcoming_count,
            "audit_records": audit_count,
            "errors": errors,
        }

        report_path = BACKEND_ROOT / "research_output" / "italy_insert_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n[FINISHED] Report written to: {report_path}")

    except IntegrityError as exc:
        session.rollback()
        print(f"ERROR: IntegrityError - {exc}")
        errors.append({"type": "IntegrityError", "detail": str(exc)})
    except SQLAlchemyError as exc:
        session.rollback()
        print(f"ERROR: SQLAlchemyError - {exc}")
        errors.append({"type": "SQLAlchemyError", "detail": str(exc)})
    except Exception as exc:
        session.rollback()
        print(f"ERROR: Unexpected - {exc}")
        errors.append({"type": "Unexpected", "detail": str(exc)})
    finally:
        session.close()


if __name__ == "__main__":
    main()