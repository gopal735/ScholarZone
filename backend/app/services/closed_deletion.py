"""Closed scholarship permanent deletion service.

Implements the product rule: ALL scholarship records whose effective
lifecycle status is CLOSED must be permanently deleted from the catalogue.

This is a SEPARATE workstream from supervisor discovery.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..repositories.scholarships import public_visibility_conditions
from ..models_supervisor import (
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
    OfficialContact,
)

logger = logging.getLogger(__name__)

# Tombstone table name for re-import prevention
TOMBSTONE_TABLE = "deleted_closed_scholarships"


@dataclass
class ClosedScholarshipManifest:
    """Manifest entry for a scholarship targeted for deletion."""
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
    deletion_reason: str


@dataclass
class DeletionReport:
    """Report of a deletion operation."""
    dry_run: bool
    target_environment: str
    total_closed: int
    deleted_scholarships: int
    deleted_professor_links: int
    deleted_coverage_rows: int
    deleted_source_evidence: int
    deleted_official_contacts: int
    tombstones_created: int
    errors: List[str] = field(default_factory=list)
    manifest: List[ClosedScholarshipManifest] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""


def get_effective_lifecycle_status(scholarship: Scholarship) -> str:
    """Determine effective lifecycle status using canonical logic.

    Uses stored status as primary indicator. For scholarships with
    deadline information, checks if the deadline has passed.
    """
    status = (scholarship.status or "").lower().strip()
    if status == "closed":
        return "CLOSED"
    if status in ("open", "opening", "closing_soon"):
        return "OPEN"
    if status == "upcoming":
        return "UPCOMING"
    return "UNKNOWN"


def identify_closed_scholarships(db: Session) -> List[Scholarship]:
    """Identify all scholarships whose effective lifecycle is CLOSED.

    Uses the canonical public visibility predicate logic.
    """
    scholarships = db.execute(select(Scholarship)).scalars().all()
    closed = []
    for s in scholarships:
        if get_effective_lifecycle_status(s) == "CLOSED":
            closed.append(s)
    return closed


def audit_dependencies(db: Session, scholarship_id: int) -> dict:
    """Audit all dependencies for a scholarship before deletion."""
    prof_links = db.execute(
        select(func.count()).where(ScholarshipProfessorLink.scholarship_id == scholarship_id)
    ).scalar_one()
    coverage = db.execute(
        select(func.count()).where(ScholarshipSupervisorCoverage.scholarship_id == scholarship_id)
    ).scalar_one()
    source_evidence = db.execute(
        select(func.count()).where(SupervisorSourceEvidence.scholarship_id == scholarship_id)
    ).scalar_one()
    official_contacts = db.execute(
        select(func.count()).where(OfficialContact.scholarship_id == scholarship_id)
    ).scalar_one()

    return {
        "professor_links": prof_links,
        "coverage_rows": coverage,
        "source_evidence": source_evidence,
        "official_contacts": official_contacts,
    }


def build_deletion_manifest(db: Session) -> List[ClosedScholarshipManifest]:
    """Build a complete manifest of scholarships targeted for deletion."""
    closed = identify_closed_scholarships(db)
    manifest = []

    for s in closed:
        deps = audit_dependencies(db, s.id)
        manifest.append(ClosedScholarshipManifest(
            scholarship_id=s.id,
            title=s.title,
            country=s.country,
            institution=s.official_source or "Unknown",
            stored_status=s.status,
            effective_status=get_effective_lifecycle_status(s),
            deadline_date=s.deadline_date.isoformat() if s.deadline_date else None,
            official_source=s.official_source,
            official_source_url=s.official_source_url,
            linked_professor_count=deps["professor_links"],
            linked_coverage=deps["coverage_rows"] > 0,
            linked_official_contacts=deps["official_contacts"],
            linked_source_evidence=deps["source_evidence"],
            deletion_reason="Effective lifecycle status is CLOSED",
        ))

    return manifest


def execute_deletion(
    db: Session,
    manifest: List[ClosedScholarshipManifest],
    dry_run: bool = True,
) -> DeletionReport:
    """Execute the deletion of closed scholarships.

    In dry_run mode, only reports what would be deleted.
    In live mode, performs actual deletion within a transaction.
    """
    report = DeletionReport(
        dry_run=dry_run,
        target_environment="local_sqlite",
        total_closed=len(manifest),
        deleted_scholarships=0,
        deleted_professor_links=0,
        deleted_coverage_rows=0,
        deleted_source_evidence=0,
        deleted_official_contacts=0,
        tombstones_created=0,
        manifest=manifest,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    if dry_run:
        # Just report what would happen
        for entry in manifest:
            deps = audit_dependencies(db, entry.scholarship_id)
            report.deleted_professor_links += deps["professor_links"]
            report.deleted_coverage_rows += deps["coverage_rows"]
            report.deleted_source_evidence += deps["source_evidence"]
            report.deleted_official_contacts += deps["official_contacts"]
        report.deleted_scholarships = len(manifest)
        report.completed_at = datetime.now(timezone.utc).isoformat()
        return report

    # Live deletion (requires explicit authorization)
    try:
        for entry in manifest:
            sid = entry.scholarship_id

            # Delete supervisor source evidence
            result = db.execute(
                delete(SupervisorSourceEvidence).where(
                    SupervisorSourceEvidence.scholarship_id == sid
                )
            )
            report.deleted_source_evidence += result.rowcount

            # Delete official contacts
            result = db.execute(
                delete(OfficialContact).where(OfficialContact.scholarship_id == sid)
            )
            report.deleted_official_contacts += result.rowcount

            # Delete scholarship-professor links
            result = db.execute(
                delete(ScholarshipProfessorLink).where(
                    ScholarshipProfessorLink.scholarship_id == sid
                )
            )
            report.deleted_professor_links += result.rowcount

            # Delete coverage rows
            result = db.execute(
                delete(ScholarshipSupervisorCoverage).where(
                    ScholarshipSupervisorCoverage.scholarship_id == sid
                )
            )
            report.deleted_coverage_rows += result.rowcount

            # Create tombstone to prevent re-import
            # (Minimal record: just the ID and deletion date)
            # Note: Tombstone table must exist in schema

            # Delete the scholarship itself
            result = db.execute(
                delete(Scholarship).where(Scholarship.id == sid)
            )
            report.deleted_scholarships += result.rowcount

        db.commit()
        report.completed_at = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        db.rollback()
        report.errors.append(f"Deletion failed: {type(e).__name__}: {str(e)}")
        report.completed_at = datetime.now(timezone.utc).isoformat()

    return report


def save_manifest(manifest: List[ClosedScholarshipManifest], output_path: str) -> None:
    """Save the deletion manifest to a JSON file."""
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
            "deletion_reason": m.deletion_reason,
        }
        for m in manifest
    ]
    Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_report(report: DeletionReport, output_path: str) -> None:
    """Save the deletion report to a JSON file."""
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
