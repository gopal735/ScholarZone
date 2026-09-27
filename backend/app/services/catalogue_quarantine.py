"""Quarantine records that are not scholarships, without destroying history.

A catalogue scrape can admit a page that is not a programme at all. The obvious
example found in this catalogue is id 490, titled "Welcome to GOV.UK", whose
official source is the bare site root ``https://gov.uk/`` and whose degree,
funding, description and every content list are empty.

Deleting such a row would destroy the audit trail and any evidence pointing at
where it came from, so nothing here deletes. Instead the record is:

* marked ``verification_status = 'quarantined'`` so it stops appearing as
  verified catalogue content,
* given ``status = 'closed'`` and a precise ``verification_notes`` reason,
* recorded in ``scholarship_reviews`` as a whole-record review with the
  evidence that justified the decision.

It stays in the table, is fully restorable, and remains traceable.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Scholarship, ScholarshipReview
from .scholarship_evidence import classify_source

logger = logging.getLogger(__name__)

QUARANTINE_STATUS = "quarantined"

# A record is only quarantined on hard structural evidence, never on a hunch.
_BARE_ROOT_RE = re.compile(r"^https?://(www\.)?[^/]+/?$")


@dataclass
class QuarantineVerdict:
    scholarship_id: int
    is_non_scholarship: bool
    reasons: list[str]
    evidence: dict[str, object]


def assess_record(scholarship: Scholarship) -> QuarantineVerdict:
    """Decide whether a record is structurally not a scholarship.

    Requires multiple independent signals so a genuinely sparse but real
    programme is never quarantined by accident.
    """
    reasons: list[str] = []

    url = (scholarship.official_source_url or "").strip()
    if url and _BARE_ROOT_RE.match(url):
        reasons.append(f"official_source_url is a bare site root, not a programme page: {url}")

    content_fields = [
        "description",
        "eligibility_summary",
        "deadline_display",
        "duration",
        "application_period",
        "best_fit",
        "english_requirement",
        "program_type",
    ]
    populated_text = [
        f for f in content_fields if getattr(scholarship, f, None) not in (None, "", [])
    ]
    if not populated_text:
        reasons.append("no descriptive, deadline, duration or eligibility content at all")

    list_fields = ["eligibility", "benefits", "coverage", "requirements", "documents", "application_method"]
    populated_lists = [f for f in list_fields if getattr(scholarship, f, None)]
    if not populated_lists:
        reasons.append("every content list is empty (eligibility/benefits/coverage/requirements/documents)")

    placeholders = 0
    for f in ("degree", "funding"):
        value = (getattr(scholarship, f, None) or "").strip().lower()
        if value in ("", "unknown", "n/a", "not specified"):
            placeholders += 1
    if placeholders == 2:
        reasons.append("both degree and funding are placeholders")

    # Title that is plainly a site name rather than a programme name.
    title = (scholarship.title or "").strip()
    if re.match(r"^(welcome to|home|homepage)\b", title, re.IGNORECASE):
        reasons.append(f"title looks like a site landing page, not a programme: {title!r}")

    # Needs at least three independent signals before acting.
    is_non_scholarship = len(reasons) >= 3

    return QuarantineVerdict(
        scholarship_id=scholarship.id,
        is_non_scholarship=is_non_scholarship,
        reasons=reasons,
        evidence={
            "title": scholarship.title,
            "official_source_url": scholarship.official_source_url,
            "source_type": classify_source(scholarship.official_source_url or "").value,
            "degree": scholarship.degree,
            "funding": scholarship.funding,
            "populated_text_fields": populated_text,
            "populated_list_fields": populated_lists,
        },
    )


def quarantine_record(
    session: Session,
    scholarship_id: int,
    *,
    dry_run: bool = True,
) -> QuarantineVerdict:
    """Mark a non-scholarship record as quarantined, preserving all history."""
    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        return QuarantineVerdict(scholarship_id, False, ["record not found"], {})

    verdict = assess_record(scholarship)
    if not verdict.is_non_scholarship:
        return verdict

    note = "Quarantined: not a scholarship record. " + "; ".join(verdict.reasons)
    existing_review = session.scalars(
        select(ScholarshipReview).where(
            ScholarshipReview.scholarship_id == scholarship_id,
            ScholarshipReview.field_name == "__record__",
        )
    ).first()

    if existing_review is None:
        session.add(
            ScholarshipReview(
                scholarship_id=scholarship_id,
                field_name="__record__",
                current_value=scholarship.title,
                proposed_value=None,
                conflict_reason=note[:255],
                verification_state=QUARANTINE_STATUS,
                confidence="high",
                source_urls=[scholarship.official_source_url]
                if scholarship.official_source_url
                else [],
                evidence_text="; ".join(verdict.reasons)[:4000],
                decision="quarantined",
                reviewed_at=datetime.now(timezone.utc),
                reviewed_by="catalogue_quality_audit",
                reviewer_note=note,
            )
        )

    if not dry_run:
        previous = scholarship.verification_status
        scholarship.verification_status = QUARANTINE_STATUS
        scholarship.status = "closed"
        scholarship.verification_notes = note
        scholarship.is_verified = False
        session.commit()
        logger.info(
            "quarantined scholarship %s (was verification_status=%s)",
            scholarship_id,
            previous,
        )
    else:
        session.rollback()

    return verdict


def quarantine_non_scholarships(
    session_factory: sessionmaker[Session],
    *,
    dry_run: bool = True,
) -> list[QuarantineVerdict]:
    """Scan the whole catalogue and quarantine everything that fails the test."""
    session = session_factory()
    try:
        ids = list(session.scalars(select(Scholarship.id).order_by(Scholarship.id)).all())
    finally:
        session.close()

    verdicts: list[QuarantineVerdict] = []
    for scholarship_id in ids:
        session = session_factory()
        try:
            verdict = quarantine_record(session, scholarship_id, dry_run=dry_run)
            if verdict.is_non_scholarship:
                verdicts.append(verdict)
        finally:
            session.close()
    return verdicts
