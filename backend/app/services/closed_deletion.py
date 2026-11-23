"""Closed scholarship permanent deletion service.

Implements the product rule: ALL scholarship records whose effective
lifecycle status is CLOSED must be permanently deleted from the catalogue.

This is a SEPARATE workstream from supervisor discovery.
"""

from __future__ import annotations

import json
import logging
import re
import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy import delete, select, func
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
            # ISO date: YYYY-MM-DD
            m = re.match(r'^\d{4}-\d{2}-\d{2}$', text)
            if m:
                try:
                    d = date.fromisoformat(text)
                except ValueError:
                    return None
            else:
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

    return {
        "professor_links": prof_links,
        "coverage_rows": coverage,
        "source_evidence": source_evidence,
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
        ))
    return manifest


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


def execute_deletion(db: Session, manifest: List[ClosedScholarshipManifest], dry_run: bool = True, reference_date=None) -> DeletionReport:
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
            report.deleted_official_contacts += deps["official_contacts"]
            report.preserved_application_records += deps["application_records"]
            report.preserved_applications += deps["application_records"]
            report.application_records_preserved += deps["application_records"]
        report.deleted_scholarships = len(manifest)
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
                    Scholarship.deadline_precision
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

            deps = audit_dependencies(db, sid)

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
            if dependency_mismatch:
                report.skipped_scholarship_ids.append(sid)
                report.skipped.append(sid)
                report.skipped_scholarships.append(sid)
                continue
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
            fp_src = "|".join(str(x or "") for x in (title, getattr(locked, "country", None), getattr(locked, "degree", None), url, link))
            fingerprint = hashlib.sha256(fp_src.encode("utf-8")).hexdigest()
            if existing_ts is None:
                ts = DeletedClosedScholarship(
                    official_source_url=url,
                    application_link=link,
                    title=title,
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
        report.preserved_application_records = 0
        report.preserved_applications = 0
        report.application_records_preserved = 0
        report.errors.append(f"Deletion failed: {type(e).__name__}: {str(e)}")
        report.completed_at = datetime.now(timezone.utc).isoformat()

    return report


def save_manifest(manifest: List[ClosedScholarshipManifest], output_path: str) -> None:
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
            "deletion_reason": m.deletion_reason,
        }
        for m in manifest
    ]
    Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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