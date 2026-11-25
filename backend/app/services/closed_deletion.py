"""Closed scholarship permanent deletion service.



Implements the product rule: ALL scholarship records whose effective

lifecycle status is CLOSED must be permanently deleted from the catalogue.



This is a SEPARATE workstream from supervisor discovery.

"""



from __future__ import annotations



import json
import hashlib

import logging

import re

import calendar

from dataclasses import dataclass, field

from datetime import date, datetime, timezone

from pathlib import Path

from typing import List, Optional



from sqlalchemy import delete, select, func, or_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session



from ..models import (

    Scholarship,

    ScholarshipVerificationHistory,

    ScholarshipReview,

    ScholarshipFetchAttempt,

    ScholarshipSnapshot,

    ImageReview,

    DiscoveryCandidate,

    ScholarshipRestoreRecord,

    SavedScholarship,

    ApplicationRecord,

    DeletedClosedScholarship,

    ScholarshipEvidence,

    ScholarshipEvidenceArchive,
    StudyPlan,
    StudyPlanTask,

)

from ..models_supervisor import (

    ScholarshipProfessorLink,

    ScholarshipSupervisorCoverage,

    SupervisorSourceEvidence,

    OfficialContact,

    ProfessorOutreachRecord,

)



logger = logging.getLogger(__name__)



TOMBSTONE_TABLE = "deleted_closed_scholarships"

def _dependency_fingerprint_data(db: Session, scholarship_id: int) -> dict:
    """Return a deterministic, canonical snapshot of every dependency row.

    Used for execution-time revalidation. The fingerprint covers every column of
    every dependency table for this scholarship, not just IDs, so any safety-
    relevant mutation - even an UPDATE on the same row ID - invalidates it.
    """
    from sqlalchemy import inspect as sa_inspect

    def rows_for(model, key):
        cols = [c.key for c in sa_inspect(model).columns]
        if key == "matched_scholarship_id":
            where = model.matched_scholarship_id == scholarship_id
        elif key == "scholarship_id":
            where = model.scholarship_id == scholarship_id
        else:
            link_ids = _link_ids_for_scholarship(db, scholarship_id)
            if link_ids:
                where = or_(model.scholarship_id == scholarship_id, model.link_id.in_(link_ids))
            else:
                where = model.scholarship_id == scholarship_id
        return [
            {c: getattr(row, c, None) for c in cols}
            for row in db.execute(select(model).where(where)).scalars()
        ]

    data = {
        "models": {
            model.__tablename__: sorted(rows_for(model, key), key=lambda r: str(r.get("id")))
            for model, key in (
                (ProfessorOutreachRecord, "scholarship_id"),
                (ApplicationRecord, "scholarship_id"),
                (SavedScholarship, "scholarship_id"),
                (DiscoveryCandidate, "matched_scholarship_id"),
                (ScholarshipVerificationHistory, "scholarship_id"),
                (ScholarshipReview, "scholarship_id"),
                (ScholarshipFetchAttempt, "scholarship_id"),
                (ScholarshipSnapshot, "scholarship_id"),
                (ScholarshipRestoreRecord, "scholarship_id"),
                (ImageReview, "scholarship_id"),
                (ScholarshipProfessorLink, "scholarship_id"),
                (ScholarshipSupervisorCoverage, "scholarship_id"),
                (OfficialContact, "scholarship_id"),
                (ScholarshipEvidence, "scholarship_id"),
            )
        },
        "source_evidence": sorted(
            [
                {c: getattr(row, c, None) for c in sa_inspect(SupervisorSourceEvidence).columns.keys()}
                for row in db.execute(
                    select(SupervisorSourceEvidence).where(
                        or_(SupervisorSourceEvidence.scholarship_id == scholarship_id,
                            SupervisorSourceEvidence.link_id.in_(_link_ids_for_scholarship(db, scholarship_id)))
                    )
                ).scalars()
            ],
            key=lambda r: str(r.get("id")),
        ),
    }
    return data


def _dependency_fingerprint(db: Session, scholarship_id: int) -> str:
    """SHA-256 over the canonical dependency snapshot (all rows/cols, not just IDs)."""
    raw = json.dumps(_dependency_fingerprint_data(db, scholarship_id), sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _lock_dependents(db: Session, scholarship_id: int) -> None:
    """Lock every known dependent row FOR UPDATE to serialize with concurrent writes."""
    models = [
        ProfessorOutreachRecord, ApplicationRecord, SavedScholarship,
        DiscoveryCandidate, ScholarshipVerificationHistory, ScholarshipReview,
        ScholarshipFetchAttempt, ScholarshipSnapshot, ScholarshipRestoreRecord,
        ImageReview, ScholarshipSupervisorCoverage, OfficialContact,
        ScholarshipEvidence,
    ]
    for model in models:
        col = DiscoveryCandidate.matched_scholarship_id if model is DiscoveryCandidate else model.scholarship_id
        db.execute(select(model).where(col == scholarship_id).with_for_update())
    db.execute(select(ScholarshipProfessorLink).where(ScholarshipProfessorLink.scholarship_id == scholarship_id).with_for_update())
    link_ids = _link_ids_for_scholarship(db, scholarship_id)
    if link_ids:
        db.execute(
            select(SupervisorSourceEvidence)
            .where(or_(SupervisorSourceEvidence.scholarship_id == scholarship_id,
                       SupervisorSourceEvidence.link_id.in_(link_ids)))
            .with_for_update()
        )


def _unknown_fks_after_lock(db: Session) -> list[dict]:
    """Fail closed if any FK now points at scholarships outside the known set."""
    rows = db.execute(text(
        "SELECT n.nspname AS schema_name, c.relname AS table_name, con.conname AS constraint_name "
        "FROM pg_constraint con "
        "JOIN pg_class c ON c.oid = con.conrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE con.contype = 'f' AND con.confrelid = 'scholarships'::regclass"
    )).mappings().all()
    known = {
        ("public", t) for t in (
            "application_records", "saved_scholarships", "discovery_candidates",
            "professor_outreach_records", "scholarship_professor_links",
            "scholarship_supervisor_coverage", "supervisor_source_evidence",
            "official_contacts", "scholarship_snapshots", "scholarship_fetch_attempts",
            "scholarship_verification_history", "scholarship_reviews", "image_reviews",
            "scholarship_restore_records",
            "scholarship_evidence",
            "scholarship_evidence_archive",
            "study_plans",
            "study_plan_tasks",
        )
    }
    return [dict(r) for r in rows if (r["schema_name"], r["table_name"]) not in known]







def _evidence_content_hash(row) -> str:
    import json as _json
    payload = {
        "application_cycle": row.application_cycle,
        "official_domain": row.official_domain,
        "official_url": row.official_url,
        "source_title": row.source_title,
        "deadline": row.deadline.isoformat() if row.deadline else None,
        "deadline_precision": row.deadline_precision,
        "supporting_excerpt": row.supporting_excerpt,
        "excerpt_hash": row.excerpt_hash,
        "retrieval_date": row.retrieval_date.isoformat(),
        "reviewer": row.reviewer,
        "decision": row.decision,
        "provenance": row.provenance,
    }
    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _gate6_evidence_rows(db: Session, scholarship_id: int):
    return list(
        db.execute(
            select(ScholarshipEvidence)
            .where(ScholarshipEvidence.scholarship_id == scholarship_id)
            .with_for_update()
        ).scalars()
    )


def _archive_gate6_evidence(db: Session, scholarship_id: int, execution_id: Optional[str] = None) -> int:
    rows = _gate6_evidence_rows(db, scholarship_id)
    if not rows:
        return 0

    pre_hashes = {row.id: _evidence_content_hash(row) for row in rows}

    scholarship_row = db.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id)
    ).scalars().first()
    legacy_id = scholarship_row.legacy_id if scholarship_row is not None else None

    values = [
        {
            "original_evidence_id": row.id,
            "original_scholarship_id": scholarship_id,
            "scholarship_legacy_id": legacy_id,
            "application_cycle": row.application_cycle,
            "official_domain": row.official_domain,
            "official_url": row.official_url,
            "source_title": row.source_title,
            "deadline": row.deadline,
            "deadline_precision": row.deadline_precision,
            "supporting_excerpt": row.supporting_excerpt,
            "excerpt_hash": row.excerpt_hash,
            "retrieval_date": row.retrieval_date,
            "reviewer": row.reviewer,
            "decision": row.decision,
            "provenance": row.provenance,
            "content_hash": pre_hashes[row.id],
            "archive_execution_id": execution_id,
        }
        for row in rows
    ]

    db.execute(
        pg_insert(ScholarshipEvidenceArchive)
        .values(values)
        .on_conflict_do_update(
            index_elements=["original_evidence_id"],
            set_={
                "archive_execution_id": text(
                    "COALESCE(EXCLUDED.archive_execution_id, scholarship_evidence_archive.archive_execution_id)"
                ),
            },
        )
        .execution_options(synchronize_session=False)
    )
    db.expire_all()

    archived = db.execute(
        select(ScholarshipEvidenceArchive).where(
            ScholarshipEvidenceArchive.original_evidence_id.in_([row.id for row in rows])
        )
    ).scalars().all()
    by_id = {a.original_evidence_id: a for a in archived}
    original_ids = {row.id for row in rows}

    if len(archived) != len(original_ids):
        raise RuntimeError(
            f"Evidence preservation failed for scholarship {scholarship_id}: "
            f"archive holds {len(archived)} rows for {len(original_ids)} live evidence rows"
        )
    if set(by_id) != original_ids:
        raise RuntimeError(
            f"Evidence preservation failed for scholarship {scholarship_id}: "
            "archived evidence ids do not match live evidence ids"
        )
    for row in rows:
        archive_row = by_id[row.id]
        if archive_row.original_scholarship_id != scholarship_id:
            raise RuntimeError(
                f"Evidence preservation failed: archive row {archive_row.original_evidence_id} "
                f"does not reference scholarship {scholarship_id}"
            )
        if archive_row.content_hash != pre_hashes[row.id]:
            raise RuntimeError(
                f"Evidence preservation failed: content hash mismatch for archive row "
                f"{archive_row.original_evidence_id} (scholarship {scholarship_id})"
            )
        if archive_row.excerpt_hash != row.excerpt_hash:
            raise RuntimeError(
                f"Evidence preservation failed: excerpt hash mismatch for archive row "
                f"{archive_row.original_evidence_id} (scholarship {scholarship_id})"
            )
    return len(rows)


@dataclass

class ClosedScholarshipManifest:

    scholarship_id: int

    title: str

    country: str

    institution: str

    stored_status: str

    effective_status: str

    deadline_date: Optional[str]

    official_source: Optional[str]

    official_source_url: Optional[str]

    linked_professor_count: int

    linked_coverage: bool

    linked_official_contacts: int

    linked_source_evidence: int

    linked_application_count: int = 0

    linked_application_records: int = 0

    dependency_fingerprint: str = ""

    deletion_reason: str = "Effective lifecycle status is CLOSED"





@dataclass

class DeletionReport:

    dry_run: bool

    target_environment: str

    total_closed: int

    deleted_scholarships: int = 0

    deleted_professor_links: int = 0

    deleted_coverage_rows: int = 0

    deleted_source_evidence: int = 0

    deleted_official_contacts: int = 0

    tombstones_created: int = 0

    preserved_gate6_evidence: int = 0

    preserved_application_records: int = 0

    preserved_applications: int = 0

    application_records_preserved: int = 0

    skipped_scholarship_ids: List[int] = field(default_factory=list)

    skipped: List[int] = field(default_factory=list)

    skipped_scholarships: List[int] = field(default_factory=list)

    errors: List[str] = field(default_factory=list)

    manifest: List[ClosedScholarshipManifest] = field(default_factory=list)

    started_at: str = ""

    completed_at: str = ""





def _normalize_date(value) -> Optional[date]:

    if value is None:

        return None

    if isinstance(value, datetime):

        return value.date()

    if isinstance(value, date):

        return value

    return None





def _parse_future_date_from_text(text: str, ref_date: date) -> Optional[date]:

    if not text or not isinstance(text, str):

        return None

    # opens YYYY-MM-DD

    m = re.search(r"opens?\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})", text, re.I)

    if m:

        try:

            return date.fromisoformat(m.group(1))

        except ValueError:

            pass

    # 2027 cycle: call opens YYYY-MM-DD

    m = re.search(r"(\d{4})\s+cycle:?.*?opens?\s+(\d{4}-\d{2}-\d{2})", text, re.I)

    if m:

        try:

            return date.fromisoformat(m.group(2))

        except ValueError:

            pass

    # call opens Month YYYY

    m = re.search(r"(?:call|applications?)\s+opens?\s+([A-Za-z]+\s+\d{4})", text, re.I)

    if m:

        try:

            parsed = datetime.strptime(m.group(1).strip(), "%B %Y")

            return parsed.date().replace(day=1)

        except ValueError:

            try:

                parsed = datetime.strptime(m.group(1).strip(), "%b %Y")

                return parsed.date().replace(day=1)

            except ValueError:

                pass

    return None





def _parse_future_open_date(text: str, ref_date: date) -> date | None:

    """Parse a future open date from application_period or deadline_display text."""

    if not text or not isinstance(text, str):

        return None

    # opens YYYY-MM-DD

    for m in re.finditer(r"opens?\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})", text, re.I):

        try:

            d = date.fromisoformat(m.group(1))

            if d > ref_date:

                return d

        except ValueError:

            pass

    # 2027 cycle

    for m in re.finditer(r"(\d{4})\s+cycle:?.*?opens?\s+(\d{4}-\d{2}-\d{2})", text, re.I):

        try:

            d = date.fromisoformat(m.group(2))

            if d > ref_date:

                return d

        except ValueError:

            pass

    # call opens Month YYYY

    for m in re.finditer(r"(?:call|applications?)\s+opens?\s+([A-Za-z]+\s+\d{4})", text, re.I):

        try:

            parsed = datetime.strptime(m.group(1).strip(), "%B %Y")

            d = parsed.date().replace(day=1)

            if d > ref_date:

                return d

        except ValueError:

            try:

                parsed = datetime.strptime(m.group(1).strip(), "%b %Y")

                d = parsed.date().replace(day=1)

                if d > ref_date:

                    return d

            except ValueError:

                pass

    # re-opens in early December

    m = re.search(r"(?:re-)?opens?\s+in\s+(early|mid|late)\s+([A-Za-z]+)", text, re.I)

    if m:

        month_map = {

            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,

            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,

        }

        mon = month_map.get(m.group(2).lower())

        if mon is not None:

            day = 5 if m.group(1).lower() == "early" else (15 if m.group(1).lower() == "mid" else 25)

            year = ref_date.year

            try:

                d = date(year, mon, day)

                if d > ref_date:

                    return d

            except ValueError:

                pass

    return None





def _has_verified_future_cycle(scholarship, ref_date: date) -> bool:

    now_date = ref_date

    # Check application_period for future open dates

    ap = getattr(scholarship, "application_period", None)

    if isinstance(ap, str):

        if _parse_future_open_date(ap, now_date):

            return True

    # Check deadline_display for future open dates

    dd = getattr(scholarship, "deadline_display", None)

    if isinstance(dd, str):

        if _parse_future_open_date(dd, now_date):

            return True

    # recurring cycle indicators - only use canonical fields

    cycle_text = " ".join(

        str(x) for x in [

            getattr(scholarship, "application_period", None),

            getattr(scholarship, "deadline_display", None),

            getattr(scholarship, "deadline", None),

        ] if x

    )

    recurring = re.search(r"\b(annually|annual|every year|each year|per year|yearly|rounds? per year)\b", cycle_text, re.I)

    month = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", cycle_text, re.I)

    if recurring and month:

        return True



    return False





def _parse_date_from_text(text: str, month_only: bool = False) -> Optional[date]:

    """Parse a date from text, matching frontend parseLifecycleDate behavior."""

    if not isinstance(text, str) or not text.strip():

        return None

    text = text.strip()



    # ISO month: YYYY-MM

    m = re.match(r'^(\d{4})-(\d{2})$', text)

    if m:

        y, mo = int(m.group(1)), int(m.group(2))

        try:

            d = date(y, mo, 1)

        except ValueError:

            return None

        month_only = True

    else:

        # Named month: "Month YYYY"

        m = re.match(r'^([a-z]+)\s+(\d{4})$', text, re.I)

        if m:

            month_names = ['january', 'february', 'march', 'april', 'may', 'june',

                           'july', 'august', 'september', 'october', 'november', 'december']

            if m.group(1).lower() not in month_names:

                return None

            mi = month_names.index(m.group(1).lower())

            try:

                d = date(int(m.group(2)), mi + 1, 1)

            except ValueError:

                return None

            month_only = True

        else:

            # ISO date or full ISO timestamp: validate the entire string.
            iso_candidate = None
            if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
                iso_candidate = text
            elif "T" in text or " " in text:
                try:
                    from datetime import datetime as _dt
                    _dt.fromisoformat(text.replace("Z", "+00:00"))
                    iso_candidate = text[:10]
                except ValueError:
                    iso_candidate = None

            if iso_candidate is not None:
                try:
                    d = date.fromisoformat(iso_candidate)
                except ValueError:
                    d = None
            else:
                d = None

            if d is None:
                # General parse attempt
                for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d %b %Y", "%B %Y"):

                    try:

                        if fmt == "%B %Y":

                            dt = datetime.strptime(text, fmt)

                            d = dt.date().replace(day=1)

                            month_only = True

                        else:

                            d = datetime.strptime(text, fmt).date()

                        break

                    except ValueError:

                        continue

                else:

                    return None



    if month_only:

        last_day = calendar.monthrange(d.year, d.month)[1]

        d = d.replace(day=last_day)

    return d





def _resolve_deadline_date(scholarship) -> Optional[date]:

    """Resolve the effective deadline date, matching frontend parseDate behavior.



    Handles deadline_date field with month precision (last day of month),

    and falls back to deadline_display / deadline when deadline_date is absent.

    """

    precision = getattr(scholarship, "deadline_precision", None) or "month"

    is_month = (precision == "month")



    # Prefer explicit deadline_date

    dl = getattr(scholarship, "deadline_date", None)

    if isinstance(dl, str) and dl.strip():
        # Parse ISO date strings (possibly full timestamps)
        try:
            dl = date.fromisoformat(dl.strip()[:10])
        except ValueError:
            dl = None

    if dl is not None:

        d = _normalize_date(dl)

        if d is not None:

            if is_month:

                last_day = calendar.monthrange(d.year, d.month)[1]

                d = d.replace(day=last_day)

            return d



    # Fallback to display fields

    for field_name in ("deadline_display", "deadline"):

        val = getattr(scholarship, field_name, None)

        if isinstance(val, str) and val.strip():

            d = _parse_date_from_text(val, month_only=is_month)

            if d is not None:

                return d



    return None





def get_effective_lifecycle_status(scholarship, reference_date=None) -> str:

    if reference_date is None:

        reference_date = datetime.now(timezone.utc)

    ref_date = _normalize_date(reference_date)

    if ref_date is None:

        ref_date = reference_date if isinstance(reference_date, date) else datetime.now(timezone.utc).date()



    has_future = _has_verified_future_cycle(scholarship, ref_date)



    is_archived = bool(getattr(scholarship, "is_archived", False))

    status = (getattr(scholarship, "status", None) or "").lower().strip()



    if is_archived:

        if not has_future:

            return "CLOSED"



    if status == "closed":

        if not has_future:

            return "CLOSED"



    dl_date = _resolve_deadline_date(scholarship)

    if dl_date is not None and dl_date < ref_date and not has_future:

        return "CLOSED"



    if status == "upcoming":

        return "UPCOMING"

    if status in ("open",):

        return "OPEN"

    if status in ("opening",):

        return "OPENING"

    if status in ("closing_soon", "closing-soon"):

        return "CLOSING_SOON"

    if status == "closed" and has_future:

        return "UPCOMING"

    if not status:

        return "UNKNOWN"

    return status.upper()





def identify_closed_scholarships(db: Session, reference_date=None) -> List[Scholarship]:

    scholarships = db.execute(select(Scholarship)).scalars().all()

    closed = []

    for s in scholarships:

        if get_effective_lifecycle_status(s, reference_date) == "CLOSED":

            closed.append(s)

    return closed





def _link_ids_for_scholarship(db: Session, scholarship_id: int) -> List[int]:

    return list(db.execute(

        select(ScholarshipProfessorLink.id).where(ScholarshipProfessorLink.scholarship_id == scholarship_id)

    ).scalars().all())





def audit_dependencies(db: Session, scholarship_id: int) -> dict:

    prof_links = db.execute(

        select(func.count()).where(ScholarshipProfessorLink.scholarship_id == scholarship_id)

    ).scalar_one()

    coverage = db.execute(

        select(func.count()).where(ScholarshipSupervisorCoverage.scholarship_id == scholarship_id)

    ).scalar_one()

    link_ids = _link_ids_for_scholarship(db, scholarship_id)

    if link_ids:

        source_evidence = db.execute(

            select(func.count()).select_from(SupervisorSourceEvidence).where(

                (SupervisorSourceEvidence.scholarship_id == scholarship_id)

                | (SupervisorSourceEvidence.link_id.in_(link_ids))

            )

        ).scalar_one()

        # distinct to avoid double count (already distinct rows)

    else:

        source_evidence = db.execute(

            select(func.count()).where(SupervisorSourceEvidence.scholarship_id == scholarship_id)

        ).scalar_one()

    official_contacts = db.execute(

        select(func.count()).where(OfficialContact.scholarship_id == scholarship_id)

    ).scalar_one()

    application_records = db.execute(

        select(func.count()).where(ApplicationRecord.scholarship_id == scholarship_id)

    ).scalar_one()

    verification_history = db.execute(

        select(func.count()).where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)

    ).scalar_one()

    scholarship_reviews = db.execute(

        select(func.count()).where(ScholarshipReview.scholarship_id == scholarship_id)

    ).scalar_one()

    fetch_attempts = db.execute(

        select(func.count()).where(ScholarshipFetchAttempt.scholarship_id == scholarship_id)

    ).scalar_one()

    snapshots = db.execute(

        select(func.count()).where(ScholarshipSnapshot.scholarship_id == scholarship_id)

    ).scalar_one()

    image_reviews = db.execute(

        select(func.count()).where(ImageReview.scholarship_id == scholarship_id)

    ).scalar_one()

    restore_records = db.execute(

        select(func.count()).where(ScholarshipRestoreRecord.scholarship_id == scholarship_id)

    ).scalar_one()

    saved_scholarships = db.execute(

        select(func.count()).where(SavedScholarship.scholarship_id == scholarship_id)

    ).scalar_one()

    outreach_records = db.execute(

        select(func.count()).where(ProfessorOutreachRecord.scholarship_id == scholarship_id)

    ).scalar_one()

    discovery_candidates = db.execute(

        select(func.count()).where(DiscoveryCandidate.matched_scholarship_id == scholarship_id)

    ).scalar_one()

    gate6_evidence = db.execute(

        select(func.count()).where(ScholarshipEvidence.scholarship_id == scholarship_id)

    ).scalar_one()



    return {

        "professor_links": prof_links,

        "coverage_rows": coverage,

        "source_evidence": source_evidence,

        "gate6_evidence": gate6_evidence,

        "official_contacts": official_contacts,

        "application_records": application_records,

        "verification_history": verification_history,

        "scholarship_reviews": scholarship_reviews,

        "fetch_attempts": fetch_attempts,

        "snapshots": snapshots,

        "image_reviews": image_reviews,

        "restore_records": restore_records,

        "saved_scholarships": saved_scholarships,

        "outreach_records": outreach_records,

        "discovery_candidates": discovery_candidates,

    }





def build_deletion_manifest(db: Session, reference_date=None) -> List[ClosedScholarshipManifest]:

    closed = identify_closed_scholarships(db, reference_date)

    manifest = []

    for s in closed:
        if getattr(s, "deletion_protected", False):
            continue

        deps = audit_dependencies(db, s.id)

        manifest.append(ClosedScholarshipManifest(

            scholarship_id=s.id,

            title=s.title,

            country=s.country,

            institution=s.official_source or "Unknown",

            stored_status=s.status,

            effective_status=get_effective_lifecycle_status(s, reference_date),

            deadline_date=(_resolve_deadline_date(s).isoformat() if _resolve_deadline_date(s) else None),

            official_source=s.official_source,

            official_source_url=s.official_source_url,

            linked_professor_count=deps["professor_links"],

            linked_coverage=deps["coverage_rows"] > 0,

            linked_official_contacts=deps["official_contacts"],

            linked_source_evidence=deps["source_evidence"],

            linked_application_count=deps["application_records"],

            linked_application_records=deps["application_records"],

            dependency_fingerprint=_dependency_fingerprint(db, s.id),

        ))

    return manifest


def _collect_dependency_ids(db: Session, scholarship_id: int) -> dict:
    link_ids = _link_ids_for_scholarship(db, scholarship_id)
    if link_ids:
        source_evidence_ids = list(db.execute(
            select(SupervisorSourceEvidence.id).where(
                (SupervisorSourceEvidence.scholarship_id == scholarship_id)
                | (SupervisorSourceEvidence.link_id.in_(link_ids))
            )
        ).scalars().all())
    else:
        source_evidence_ids = list(db.execute(
            select(SupervisorSourceEvidence.id).where(SupervisorSourceEvidence.scholarship_id == scholarship_id)
        ).scalars().all())
    return {
        "professor_links": sorted(db.execute(select(ScholarshipProfessorLink.id).where(ScholarshipProfessorLink.scholarship_id == scholarship_id)).scalars().all()),
        "coverage_rows": sorted(db.execute(select(ScholarshipSupervisorCoverage.id).where(ScholarshipSupervisorCoverage.scholarship_id == scholarship_id)).scalars().all()),
        "source_evidence": sorted(source_evidence_ids),
        "official_contacts": sorted(db.execute(select(OfficialContact.id).where(OfficialContact.scholarship_id == scholarship_id)).scalars().all()),
        "application_records": sorted(db.execute(select(ApplicationRecord.id).where(ApplicationRecord.scholarship_id == scholarship_id)).scalars().all()),
        "saved_scholarships": sorted(db.execute(select(SavedScholarship.id).where(SavedScholarship.scholarship_id == scholarship_id)).scalars().all()),
        "discovery_candidates": sorted(db.execute(select(DiscoveryCandidate.id).where(DiscoveryCandidate.matched_scholarship_id == scholarship_id)).scalars().all()),
        "outreach_records": sorted(db.execute(select(ProfessorOutreachRecord.id).where(ProfessorOutreachRecord.scholarship_id == scholarship_id)).scalars().all()),
        "verification_history": sorted(db.execute(select(ScholarshipVerificationHistory.id).where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)).scalars().all()),
        "scholarship_reviews": sorted(db.execute(select(ScholarshipReview.id).where(ScholarshipReview.scholarship_id == scholarship_id)).scalars().all()),
        "fetch_attempts": sorted(db.execute(select(ScholarshipFetchAttempt.id).where(ScholarshipFetchAttempt.scholarship_id == scholarship_id)).scalars().all()),
        "snapshots": sorted(db.execute(select(ScholarshipSnapshot.id).where(ScholarshipSnapshot.scholarship_id == scholarship_id)).scalars().all()),
        "image_reviews": sorted(db.execute(select(ImageReview.id).where(ImageReview.scholarship_id == scholarship_id)).scalars().all()),
        "restore_records": sorted(db.execute(select(ScholarshipRestoreRecord.id).where(ScholarshipRestoreRecord.scholarship_id == scholarship_id)).scalars().all()),
    }


# (removed duplicate weak fingerprint definition; the canonical full-row implementation above is used)





def _target_environment(db: Session) -> str:

    bind = db.get_bind()

    name = getattr(bind.dialect, "name", "sqlite")

    if name == "postgresql":

        return "postgresql"

    return "local_sqlite"





def _populate_application_snapshot(app: ApplicationRecord, s: Scholarship) -> None:

    if app.scholarship_name_snapshot is None:

        app.scholarship_name_snapshot = getattr(s, "title", None)

    if app.scholarship_country_snapshot is None:

        app.scholarship_country_snapshot = getattr(s, "country", None)

    if app.scholarship_degree_snapshot is None:

        app.scholarship_degree_snapshot = getattr(s, "degree", None)

    if app.scholarship_provider_snapshot is None:

        app.scholarship_provider_snapshot = getattr(s, "official_source", None)

    if app.scholarship_funding_snapshot is None:

        app.scholarship_funding_snapshot = getattr(s, "funding", None)

    if app.scholarship_deadline_text_snapshot is None:

        app.scholarship_deadline_text_snapshot = getattr(s, "deadline_display", None)

    if app.scholarship_deadline_date_snapshot is None:

        app.scholarship_deadline_date_snapshot = _normalize_date(getattr(s, "deadline_date", None))

    if app.scholarship_source_url_snapshot is None:

        app.scholarship_source_url_snapshot = getattr(s, "official_source_url", None) or getattr(s, "application_link", None)





def execute_deletion(
    db: Session,
    manifest: List[ClosedScholarshipManifest],
    dry_run: bool = True,
    reference_date=None,
    execution_id: Optional[str] = None,
) -> DeletionReport:

    report = DeletionReport(

        dry_run=dry_run,

        target_environment=_target_environment(db),

        total_closed=len(manifest),

        manifest=manifest,

        started_at=datetime.now(timezone.utc).isoformat(),

    )



    if dry_run:

        for entry in manifest:

            deps = audit_dependencies(db, entry.scholarship_id)

            report.deleted_professor_links += deps["professor_links"]

            report.deleted_coverage_rows += deps["coverage_rows"]

            report.deleted_source_evidence += deps["source_evidence"]

            report.preserved_gate6_evidence += deps["gate6_evidence"]

            report.deleted_official_contacts += deps["official_contacts"]

            report.preserved_application_records += deps["application_records"]

            report.preserved_applications += deps["application_records"]

            report.application_records_preserved += deps["application_records"]

        report.deleted_scholarships = len(manifest)

        report.completed_at = datetime.now(timezone.utc).isoformat()

        return report



    if not dry_run and manifest and _target_environment(db) == "local_sqlite":
        for entry in manifest:
            row = db.execute(select(Scholarship).where(Scholarship.id == entry.scholarship_id)).scalars().first()
            if row is not None and bool(getattr(row, "deletion_protected", False)):
                report.skipped_scholarship_ids.append(entry.scholarship_id)
                report.skipped.append(entry.scholarship_id)
                report.skipped_scholarships.append(entry.scholarship_id)
                continue
            report.errors.append("Live deletion is not supported on SQLite: PostgreSQL row locking is required")
            report.completed_at = datetime.now(timezone.utc).isoformat()
            return report
        report.completed_at = datetime.now(timezone.utc).isoformat()
        return report

    try:

        for entry in manifest:

            sid = entry.scholarship_id



            # transactional re-check

            # Use a core query to bypass ORM identity map and get fresh data

            locked_row = db.execute(

                select(

                    Scholarship.id, Scholarship.status, Scholarship.is_archived,

                    Scholarship.deadline_date, Scholarship.application_period,

                    Scholarship.deadline_display, Scholarship.deadline_date,

                    Scholarship.notes, Scholarship.verification_notes,

                    Scholarship.selection_notes,

                    Scholarship.official_source_url, Scholarship.application_link,

                    Scholarship.title,

                    Scholarship.country, Scholarship.degree,

                    Scholarship.official_source, Scholarship.funding,

                    Scholarship.deadline_precision,

                    Scholarship.deletion_protected

                )

                .where(Scholarship.id == sid)

                .with_for_update()

            ).first()

            if locked_row is None:

                report.skipped_scholarship_ids.append(sid)

                report.skipped.append(sid)

                report.skipped_scholarships.append(sid)

                continue



            # Create a lightweight object with the fresh data for lifecycle check

            class _LockedScholarship:

                def __init__(self, row):

                    self.id = row.id

                    self.status = row.status

                    self.is_archived = row.is_archived

                    self.deadline_date = row.deadline_date

                    self.application_period = row.application_period

                    self.deadline_display = row.deadline_display

                    self.deadline = row.deadline_date  # use deadline_date column

                    self.notes = row.notes

                    self.verification_notes = row.verification_notes

                    self.selection_notes = row.selection_notes

                    self.official_source_url = row.official_source_url

                    self.application_link = row.application_link

                    self.title = row.title

                    self.country = row.country

                    self.degree = row.degree

                    self.official_source = row.official_source

                    self.funding = row.funding

                    self.deadline_precision = getattr(row, "deadline_precision", None) or "month"

                    self.deletion_protected = bool(getattr(row, "deletion_protected", False))



            locked = _LockedScholarship(locked_row)

            if locked is None:

                report.skipped_scholarship_ids.append(sid)

                report.skipped.append(sid)

                report.skipped_scholarships.append(sid)

                continue

            if get_effective_lifecycle_status(locked, reference_date) != "CLOSED":

                report.skipped_scholarship_ids.append(sid)

                report.skipped.append(sid)

                report.skipped_scholarships.append(sid)

                continue



            # Fail closed: a missing/None/invalid protection state is treated as protected.
            if locked.deletion_protected is not False:
                report.skipped_scholarship_ids.append(sid)
                report.skipped.append(sid)
                report.skipped_scholarships.append(sid)
                continue

            deps = audit_dependencies(db, sid)



            # Revalidate the live row identity against the approved manifest.

            # Counts alone cannot detect a replaced row with the same ID.

            identity_mismatch = (

                locked.title != entry.title

                or locked.country != entry.country

                or str(_resolve_deadline_date(locked)) != str(entry.deadline_date)

                or locked.status != entry.stored_status

                or getattr(locked, "official_source_url", None) != entry.official_source_url

            )

            if identity_mismatch:

                report.skipped_scholarship_ids.append(sid)

                report.skipped.append(sid)

                report.skipped_scholarships.append(sid)

                continue



            # Revalidate dependency state against the approved manifest before

            # deleting any rows. New dependencies are not covered by backup.

            dependency_mismatch = False

            if entry.linked_professor_count != deps["professor_links"]:

                dependency_mismatch = True

            if bool(entry.linked_coverage) != (deps["coverage_rows"] > 0):

                dependency_mismatch = True

            if entry.linked_official_contacts != deps["official_contacts"]:

                dependency_mismatch = True

            if entry.linked_source_evidence != deps["source_evidence"]:

                dependency_mismatch = True

            if entry.linked_application_count != deps["application_records"]:

                dependency_mismatch = True

            if entry.linked_application_records != deps["application_records"]:

                dependency_mismatch = True

            _lock_dependents(db, sid)

            if entry.dependency_fingerprint:

                if _dependency_fingerprint(db, sid) != entry.dependency_fingerprint:

                    dependency_mismatch = True

            unknown_fks = _unknown_fks_after_lock(db)

            if unknown_fks:

                report.errors.extend([f"Unknown FK dependency on scholarships: {fk}" for fk in unknown_fks])

                report.skipped_scholarship_ids.append(sid)

                report.skipped.append(sid)

                report.skipped_scholarships.append(sid)

                continue

            if dependency_mismatch:

                report.skipped_scholarship_ids.append(sid)

                report.skipped.append(sid)

                report.skipped_scholarships.append(sid)

                continue

            # Preserve Gate 6 evidence: archive the live evidence rows to the
            # immutable archive and verify the preservation inside this
            # transaction. Any failure raises and the deletion is rolled
            # back. Idempotent across retries.
            report.preserved_gate6_evidence += _archive_gate6_evidence(
                db, sid, execution_id=execution_id
            )

            # Live evidence rows are now archived; delete them so the
            # ON DELETE NO ACTION FK on scholarships.id allows the scholarship
            # delete below.
            db.execute(delete(ScholarshipEvidence).where(ScholarshipEvidence.scholarship_id == sid))

            link_ids = _link_ids_for_scholarship(db, sid)



            # delete source evidence (scholarship_id or link_id)

            if link_ids:

                res = db.execute(

                    delete(SupervisorSourceEvidence).where(

                        (SupervisorSourceEvidence.scholarship_id == sid)

                        | (SupervisorSourceEvidence.link_id.in_(link_ids))

                    )

                )

            else:

                res = db.execute(

                    delete(SupervisorSourceEvidence).where(SupervisorSourceEvidence.scholarship_id == sid)

                )

            report.deleted_source_evidence += (res.rowcount or 0)



            # official contacts

            res = db.execute(delete(OfficialContact).where(OfficialContact.scholarship_id == sid))

            report.deleted_official_contacts += (res.rowcount or 0)



            # professor links (after evidence)

            res = db.execute(delete(ScholarshipProfessorLink).where(ScholarshipProfessorLink.scholarship_id == sid))

            report.deleted_professor_links += (res.rowcount or 0)



            # coverage

            res = db.execute(delete(ScholarshipSupervisorCoverage).where(ScholarshipSupervisorCoverage.scholarship_id == sid))

            report.deleted_coverage_rows += (res.rowcount or 0)



            # other catalogue deps

            db.execute(delete(ScholarshipSnapshot).where(ScholarshipSnapshot.scholarship_id == sid))

            db.execute(delete(ScholarshipFetchAttempt).where(ScholarshipFetchAttempt.scholarship_id == sid))

            db.execute(delete(ScholarshipVerificationHistory).where(ScholarshipVerificationHistory.scholarship_id == sid))

            db.execute(delete(ScholarshipReview).where(ScholarshipReview.scholarship_id == sid))

            db.execute(delete(ImageReview).where(ImageReview.scholarship_id == sid))

            db.execute(delete(ScholarshipRestoreRecord).where(ScholarshipRestoreRecord.scholarship_id == sid))



            # saved scholarships: PRESERVE student-owned shortlist history; detach FK only

            saved_rows = db.execute(

                select(SavedScholarship).where(SavedScholarship.scholarship_id == sid)

            ).scalars().all()

            for sv in saved_rows:

                sv.scholarship_id = None

                if getattr(sv, "scholarship_title_snapshot", None) is None:

                    sv.scholarship_title_snapshot = getattr(locked, "title", None)



            # discovery candidates unlink

            db.execute(

                DiscoveryCandidate.__table__.update()

                .where(DiscoveryCandidate.matched_scholarship_id == sid)

                .values(matched_scholarship_id=None)

            )



            # professor outreach detach

            outreach_rows = db.execute(

                select(ProfessorOutreachRecord).where(ProfessorOutreachRecord.scholarship_id == sid)

            ).scalars().all()

            for o in outreach_rows:

                o.scholarship_id = None



            # application records preserve history + detach

            app_rows = db.execute(

                select(ApplicationRecord).where(ApplicationRecord.scholarship_id == sid)

            ).scalars().all()

            for app in app_rows:

                _populate_application_snapshot(app, locked)

                app.scholarship_id = None

                report.preserved_application_records += 1

                report.preserved_applications += 1

                report.application_records_preserved += 1



            # study planner detach: preserve plans/tasks, detach scholarship FK
            study_plan_rows = db.execute(
                select(StudyPlan).where(StudyPlan.scholarship_id == sid)
            ).scalars().all()
            for sp in study_plan_rows:
                sp.scholarship_id = None

            db.execute(
                StudyPlanTask.__table__.update()
                .where(StudyPlanTask.related_scholarship_id == sid)
                .values(related_scholarship_id=None)
            )

            # tombstone (idempotent)

            url = getattr(locked, "official_source_url", None)

            link = getattr(locked, "application_link", None)

            title = getattr(locked, "title", None)

            existing_ts = None

            if url:

                existing_ts = db.execute(

                    select(DeletedClosedScholarship).where(DeletedClosedScholarship.official_source_url == url)

                ).scalar_one_or_none()

            import hashlib

            fp_src = "|".join(str(x or "") for x in (title, getattr(locked, "country", None), getattr(locked, "degree", None)))

            fingerprint = hashlib.sha256(fp_src.encode("utf-8")).hexdigest()

            if existing_ts is None:

                ts = DeletedClosedScholarship(

                    legacy_id=getattr(locked, "legacy_id", None),

                    official_source_url=url,

                    application_link=link,

                    title=title,

                    country=getattr(locked, "country", None),

                    degree=getattr(locked, "degree", None),

                    reason="closed_permanent_deletion",

                    record_fingerprint=fingerprint,

                )

                db.add(ts)

                db.flush()

                report.tombstones_created += 1



            # delete scholarship

            res = db.execute(delete(Scholarship).where(Scholarship.id == sid))

            report.deleted_scholarships += (res.rowcount or 0)



        db.flush()

        report.completed_at = datetime.now(timezone.utc).isoformat()



    except Exception as e:

        db.rollback()

        report.deleted_scholarships = 0

        report.deleted_professor_links = 0

        report.deleted_coverage_rows = 0

        report.deleted_source_evidence = 0

        report.deleted_official_contacts = 0

        report.tombstones_created = 0

        report.preserved_gate6_evidence = 0

        report.preserved_application_records = 0

        report.preserved_applications = 0

        report.application_records_preserved = 0

        report.errors.append(f"Deletion failed: {type(e).__name__}: {str(e)}")

        report.completed_at = datetime.now(timezone.utc).isoformat()



    return report





def save_manifest(manifest: List[ClosedScholarshipManifest], output_path: str) -> None:
    save_deletion_manifest(manifest, output_path)





def save_report(report: DeletionReport, output_path: str) -> None:

    data = {

        "dry_run": report.dry_run,

        "target_environment": report.target_environment,

        "total_closed": report.total_closed,

        "deleted_scholarships": report.deleted_scholarships,

        "deleted_professor_links": report.deleted_professor_links,

        "deleted_coverage_rows": report.deleted_coverage_rows,

        "deleted_source_evidence": report.deleted_source_evidence,

        "deleted_official_contacts": report.deleted_official_contacts,

        "tombstones_created": report.tombstones_created,

        "preserved_gate6_evidence": report.preserved_gate6_evidence,

        "preserved_application_records": report.preserved_application_records,

        "preserved_applications": report.preserved_applications,

        "application_records_preserved": report.application_records_preserved,

        "skipped_scholarship_ids": report.skipped_scholarship_ids,

        "skipped": report.skipped,

        "skipped_scholarships": report.skipped_scholarships,

        "errors": report.errors,

        "started_at": report.started_at,

        "completed_at": report.completed_at,

        "manifest_count": len(report.manifest),

    }

    Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")





MANIFEST_SCHEMA_VERSION = "1.0"

_REQUIRED_ENTRY_FIELDS = (
    "scholarship_id", "title", "country", "institution", "stored_status",
    "effective_status", "deadline_date", "official_source", "official_source_url",
    "linked_professor_count", "linked_coverage", "linked_official_contacts",
    "linked_source_evidence", "linked_application_count", "linked_application_records",
    "dependency_fingerprint", "deletion_reason",
)


def save_deletion_manifest(manifest: List[ClosedScholarshipManifest], output_path: str,
                           metadata_path: Optional[str] = None) -> str:
    """Serialize the manifest with canonical deterministic digest and metadata."""
    data = [
        {
            "scholarship_id": m.scholarship_id,
            "title": m.title,
            "country": m.country,
            "institution": m.institution,
            "stored_status": m.stored_status,
            "effective_status": m.effective_status,
            "deadline_date": m.deadline_date,
            "official_source": m.official_source,
            "official_source_url": m.official_source_url,
            "linked_professor_count": m.linked_professor_count,
            "linked_coverage": m.linked_coverage,
            "linked_official_contacts": m.linked_official_contacts,
            "linked_source_evidence": m.linked_source_evidence,
            "linked_application_count": m.linked_application_count,
            "linked_application_records": m.linked_application_records,
            "dependency_fingerprint": m.dependency_fingerprint,
            "deletion_reason": m.deletion_reason,
        }
        for m in manifest
    ]
    raw = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    Path(output_path).write_bytes(raw.encode("utf-8"))
    digest = hashlib.sha256(Path(output_path).read_bytes()).hexdigest()
    if metadata_path is None:
        metadata_path = output_path + ".metadata.json"
    Path(metadata_path).write_text(json.dumps({
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_hash": digest,
        "manifest_target_count": len(data),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    return digest


def _validate_manifest_entry(entry: dict) -> None:
    missing = [f for f in _REQUIRED_ENTRY_FIELDS if f not in entry]
    if missing:
        raise ValueError(f"Manifest entry missing required fields: {missing}")
    if not isinstance(entry["scholarship_id"], int) or entry["scholarship_id"] <= 0:
        raise ValueError("Invalid scholarship_id in manifest entry")
    for f in ("title", "country", "institution", "stored_status", "effective_status", "deletion_reason"):
        if not isinstance(entry[f], str):
            raise ValueError(f"Manifest field {f} must be a string")
    for f in ("official_source", "official_source_url"):
        if entry[f] is not None and not isinstance(entry[f], str):
            raise ValueError(f"Manifest field {f} must be a string or null")
    for f in ("linked_professor_count", "linked_official_contacts",
              "linked_application_count", "linked_application_records"):
        if not isinstance(entry[f], int) or entry[f] < 0:
            raise ValueError(f"Manifest field {f} must be a non-negative integer")
    if not isinstance(entry["linked_coverage"], bool):
        raise ValueError("Manifest field linked_coverage must be a boolean")
    if not entry["dependency_fingerprint"]:
        raise ValueError("Manifest entry must contain a non-empty dependency_fingerprint")


def load_deletion_manifest(output_path: str, metadata_path: Optional[str] = None,
                           verify_digest: bool = True) -> List[ClosedScholarshipManifest]:
    """Load and strictly validate a saved deletion manifest.

    Fail closed: corrupted JSON, missing fields, unsupported schema versions,
    digest mismatch, or unparseable dates raise and never return a partial manifest.
    """
    raw_bytes = Path(output_path).read_bytes()
    raw = raw_bytes.decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise ValueError("Manifest must be a non-empty list")

    if metadata_path is None:
        metadata_path = output_path + ".metadata.json"
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if metadata.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"Unsupported manifest schema version: {metadata.get('schema_version')!r}")
    if verify_digest:
        actual = hashlib.sha256(raw_bytes).hexdigest()
        if actual != metadata.get("manifest_hash"):
            raise ValueError("Manifest digest mismatch")
    if metadata.get("manifest_target_count") != len(data):
        raise ValueError("Manifest target count mismatch")

    out: List[ClosedScholarshipManifest] = []
    for entry in data:
        _validate_manifest_entry(entry)
        dl = entry.get("deadline_date")
        if dl is not None:
            date.fromisoformat(dl)  # fail closed on malformed date
        out.append(ClosedScholarshipManifest(**entry))
    return out


__all__ = [

    "ClosedScholarshipManifest",

    "DeletionReport",

    "get_effective_lifecycle_status",

    "identify_closed_scholarships",

    "audit_dependencies",

    "build_deletion_manifest",

    "execute_deletion",

    "save_manifest",

    "save_report",

]
