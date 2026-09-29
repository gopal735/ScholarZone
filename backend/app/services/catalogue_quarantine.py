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
from .discovery_quality_gate import (
    is_navigation_url,
    title_problem,
    value_integrity_problems,
)
from .scholarship_evidence import classify_source

logger = logging.getLogger(__name__)

QUARANTINE_STATUS = "quarantined"

# Fields inspected for corruption. The gate's `value_integrity_problems` decides
# which of these actually count: structural fields only, because markup in a
# prose field is untidy data rather than a sign the record is not a scholarship.
_CORRUPTION_PROBE_FIELDS = (
    "title", "degree", "funding", "program_type", "best_fit", "duration",
    "status", "description", "eligibility_summary", "deadline_display",
    "application_period", "selection_notes", "notes",
)

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
    #
    # The title judgement is delegated to the pre-insert gate rather than
    # reimplemented. This module used to carry its own much weaker version
    # (`^(welcome to|home|homepage)`), which scored zero signals on a record
    # titled "Find your programme" - a search box over other people's
    # programmes, published as verified because the two implementations of this
    # judgement had drifted apart.
    title = (scholarship.title or "").strip()
    title_fault = title_problem(title)
    if title_fault:
        reasons.append(title_fault)

    provider = (scholarship.official_source or "").strip()
    if not provider:
        reasons.append(
            "no awarding body: official_source is empty, so the record does not "
            "say who offers the scholarship"
        )

    # Corrupt values are decisive on their own.
    #
    # Every other signal here is a count, and this sweep deliberately requires
    # three of them so a sparse but real programme is never quarantined by
    # accident. Markup inside a stored field is different in kind: it means the
    # record was built from a mis-parsed page, and no amount of corroborating
    # structure makes such a record trustworthy. A live round produced
    # `degree="Programmes[/LINK]"` and a 120-character marketing sentence in the
    # same field, and both records passed this sweep while being plainly wrong.
    corruption = value_integrity_problems(
        {name: getattr(scholarship, name, None) for name in _CORRUPTION_PROBE_FIELDS}
    )
    reasons.extend(corruption)

    if is_navigation_url(scholarship.official_source_url):
        reasons.append(
            "official_source_url is site navigation, not a programme page: "
            f"{scholarship.official_source_url}"
        )

    # Needs at least three independent signals before acting, unless the record
    # is corrupt, in which case one is enough.
    is_non_scholarship = len(reasons) >= 3 or bool(corruption)

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
